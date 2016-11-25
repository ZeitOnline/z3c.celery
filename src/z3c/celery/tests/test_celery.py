from z3c.celery.session import celery_session
from celery import shared_task
import celery.backends.base
import celery.exceptions
import datetime
import mock
import pytest
import transaction
import z3c.celery
import z3c.celery.testing
import ZODB.POSException
import zope.authentication.interfaces
import zope.security.management


@shared_task
def dummy_task(context=None, datetime=None):
    """Dummy task to test our framework."""


@shared_task
def get_principal_title_task():
    """Task returning the principal's title used to run it."""
    interaction = zope.security.management.getInteraction()
    return interaction.participations[0].principal.title


@shared_task
def conflict_task(context=None, datetime=None):
    """Dummy task which injects a DataManager that votes a ConflictError."""
    transaction.get().join(VoteExceptionDataManager())


now = datetime.datetime.now()


def test_celery__TransactionAwareTask__delay__1():
    """It raises a TypeError if arguments are not JSON serializable."""
    with pytest.raises(TypeError):
        dummy_task.delay(object(), datetime=now)


def test_celery__TransactionAwareTask__delay__2(interaction):
    """It registers a task if arguments are JSON serializable."""
    assert 0 == len(celery_session)
    dummy_task.delay('http://url.to/testcontent',
                     datetime='2016-01-01 12:00:00')
    assert 1 == len(celery_session)


def test_celery__TransactionAwareTask__delay__3(interaction, eager_celery_app):
    """It extracts the principal from the interaction if run in async mode."""
    run_instantly = 'z3c.celery.celery.TransactionAwareTask.run_instantly'
    with mock.patch(run_instantly, return_value=False):
        dummy_task.delay('1st param', datetime='now()')
    task_call = 'z3c.celery.celery.TransactionAwareTask.__call__'
    with mock.patch(task_call) as task_call:
        zope.security.management.endInteraction()
        transaction.commit()
    task_call.assert_called_with(
        '1st param', datetime='now()',
        _run_asynchronously_=True, _principal_id_=u'zope.user')


def test_celery__TransactionAwareTask__delay__4(interaction, eager_celery_app):
    """It calls the original function directly if we are in eager mode."""
    with mock.patch.object(dummy_task, 'run') as task_call:
        dummy_task.delay('1st param', datetime='now()')
    task_call.assert_called_with('1st param', datetime='now()')


def test_celery__TransactionAwareTask__apply_async__1():
    """It raises a TypeError if arguments are not JSON serializable."""
    with pytest.raises(TypeError):
        dummy_task.apply_async(
            (object(),), {'datetime': now},
            task_id=now, countdown=now)


def test_celery__TransactionAwareTask__apply_async__2(interaction):
    """It registers a task if arguments are JSON serializable."""
    assert 0 == len(celery_session)
    dummy_task.apply_async(
        ('http://url.to/testcontent',),
        {'datetime': '2016-01-01 12:00:00'},
        task_id=1, countdown=30)
    assert 1 == len(celery_session)


def test_celery__TransactionAwareTask__apply_async__3(
        interaction, eager_celery_app):
    """It extracts the principal from the interaction if run in async mode."""
    run_instantly = 'z3c.celery.celery.TransactionAwareTask.run_instantly'
    with mock.patch(run_instantly, return_value=False):
        dummy_task.apply_async(('1st param',), dict(datetime='now()'))
    task_call = 'z3c.celery.celery.TransactionAwareTask.__call__'
    with mock.patch(task_call) as task_call:
        zope.security.management.endInteraction()
        transaction.commit()
    task_call.assert_called_with(
        '1st param', datetime='now()',
        _run_asynchronously_=True, _principal_id_=u'zope.user')


def test_celery__TransactionAwareTask__apply_async__4(
        interaction, eager_celery_app):
    """It calls the original function directly if we are in eager mode."""
    with mock.patch.object(dummy_task, 'run') as task_call:
        dummy_task.apply_async(('1st param',), dict(datetime='now()'))
    task_call.assert_called_with('1st param', datetime='now()')


def test_celery__TransactionAwareTask__apply_async__5(
        interaction, eager_celery_app):
    """It processes the missing kw argument as emtpy dict."""
    # We need to make this a bit complicated as we want to see the actual call
    # of __call__ after the argument handling
    run_instantly = 'z3c.celery.celery.TransactionAwareTask.run_instantly'
    with mock.patch(run_instantly, return_value=False):
        dummy_task.apply_async(('1st param',))
    task_call = 'z3c.celery.celery.TransactionAwareTask.__call__'
    with mock.patch(task_call) as task_call:
        transaction.commit()
    task_call.assert_called_with(
        '1st param', _run_asynchronously_=True, _principal_id_=u'zope.user')


@shared_task
def exception_task(context=None, datetime=None):
    """Dummy task which raises an exception to test our framework."""
    raise RuntimeError()


def test_celery__TransactionAwareTask____call____1(
        celery_session_worker, celery_app):
    """It aborts the transaction in case of an error during task execution."""
    result = exception_task.delay()
    transaction.commit()
    with pytest.raises(Exception) as err:
        result.get()
    # Celery wraps errors dynamically as celery.backends.base.<ErrorName>, so
    # we have to dig deep here.
    assert 'RuntimeError' == err.value.__class__.__name__


def test_celery__TransactionAwareTask____call____1__cov(
        interaction, eager_celery_app):
    """It aborts the transaction in case of an error during task execution.

    As it is hard to collect coverage for subprocesses we use this test for
    coverage only.
    """
    task_call = 'celery.Task.__call__'
    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    with mock.patch(configure_zope), \
            mock.patch(task_call, side_effect=RuntimeError) as task_call, \
            mock.patch('transaction.abort') as abort:

        zope.security.management.endInteraction()
        with pytest.raises(RuntimeError):
            # We want to simulate a run in worker. The RuntimeError is raised
            # by the mock
            dummy_task(_run_asynchronously_=True)

    assert task_call.called
    assert abort.called


class NoopDatamanager(object):
    """Datamanager which does nothing."""

    def abort(self, trans):
        pass

    def commit(self, trans):
        pass

    def tpc_begin(self, trans):
        pass

    def tpc_abort(self, trans):
        pass


class VoteExceptionDataManager(NoopDatamanager):
    """DataManager which raises an exception in tpc_vote."""

    def tpc_vote(self, trans):
        raise ZODB.POSException.ConflictError()

    def sortKey(self):
        # Make sure we are running after the in thread execution of the task so
        # that we can throw an Error as last part of vote:
        return '~~sort-me-last'


@pytest.mark.skip('Is traped in retry logic in tests.')
def test_celery__TransactionAwareTask____call____2(
        celery_worker, celery_app, interaction):
    """It aborts the transaction and retries in case of an ConflictError."""
    result = conflict_task.apply_async(max_retries=0)

    transaction.commit()
    with pytest.raises(Exception) as err:
        result.get()
    # Celery wraps errors dynamically as celery.backends.base.<ErrorName>, so
    # we have to dig deep here.
    assert 'RuntimeError' == err.value.__class__.__name__

    run_instantly = 'z3c.celery.celery.TransactionAwareTask.run_instantly'
    with mock.patch(run_instantly, return_value=False):
        conflict_task.delay()
    zope.security.management.endInteraction()
    with pytest.raises(celery.exceptions.MaxRetriesExceededError):
        transaction.commit()


def test_celery__TransactionAwareTask____call____2__cov(
        interaction, eager_celery_app):
    """It aborts the transaction and retries in case of an ConflictError.

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    task_call = 'celery.Task.__call__'
    retry = 'celery.Task.retry'
    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    commit = 'z3c.celery.celery.TransactionAwareTask.transaction_commit'
    with mock.patch(configure_zope), \
            mock.patch(task_call) as task_call, \
            mock.patch(commit, side_effect=ZODB.POSException.ConflictError),\
            mock.patch('transaction.abort') as abort, \
            mock.patch(retry) as retry:

        zope.security.management.endInteraction()
        dummy_task(_run_asynchronously_=True)

    assert task_call.called
    assert abort.called
    assert retry.called


def test_celery__TransactionAwareTask____call____3(
        celery_session_worker, celery_session_app, zcml):
    """It runs as given principal in asynchronous mode."""
    auth = zope.component.getUtility(
        zope.authentication.interfaces.IAuthentication)
    principal = auth.getPrincipal('example.user')
    z3c.celery.testing.login_principal(principal)
    result = get_principal_title_task.delay()
    transaction.commit()
    assert 'Ben Utzer' == result.get()


def test_celery__TransactionAwareTask____call____3__cov(
        interaction, eager_celery_app, zcml):
    """It runs as given principal in asynchronous mode.

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    with mock.patch(configure_zope):

        zope.security.management.endInteraction()
        result = get_principal_title_task(
            _run_asynchronously_=True, _principal_id_='example.user')

    assert "Ben Utzer" == result
