# coding: utf-8
from .shared_tasks import get_principal_title_task
from celery import shared_task
from z3c.celery.celery import HandleAfterAbort, Abort
from z3c.celery.session import celery_session
from z3c.celery.testing import open_zodb_copy
import ZODB.POSException
import datetime
from unittest import mock
import pytest
import transaction
import z3c.celery
import z3c.celery.celery
import z3c.celery.testing
import zope.authentication.interfaces
import zope.security.management


@z3c.celery.task
def eager_task(context=None, datetime=None):
    """Dummy task to be used together with `eager_celery_app`."""


now = datetime.datetime.now()


def test_celery__TransactionAwareTask__delay__1():
    """It raises a TypeError if arguments are not JSON serializable."""
    with pytest.raises(TypeError):
        eager_task.delay(object(), datetime=now)


def test_celery__TransactionAwareTask__delay__2(interaction):
    """It registers a task if arguments are JSON serializable."""
    assert 0 == len(celery_session)
    eager_task.delay('http://url.to/testcontent',
                     datetime='2016-01-01 12:00:00')
    assert 1 == len(celery_session)


def test_celery__TransactionAwareTask__delay__3(interaction, eager_celery_app):
    """It extracts the principal from the interaction if run in async mode."""
    asynch = 'z3c.celery.celery.TransactionAwareTask._eager_use_session_'
    with mock.patch(asynch, new=True):
        eager_task.delay('1st param', datetime='now()')
    task_call = 'z3c.celery.celery.TransactionAwareTask.__call__'
    with mock.patch(task_call) as task_call:
        zope.security.management.endInteraction()
        transaction.commit()
    task_call.assert_called_with(
        '1st param', datetime='now()',
        _run_asynchronously_=True, _principal_id_=u'zope.user')


def test_celery__TransactionAwareTask__delay__4(interaction, eager_celery_app):
    """It calls the original function directly if we are in eager mode."""
    with mock.patch.object(eager_task, 'run') as task_call:
        eager_task.delay('1st param', datetime='now()')
    task_call.assert_called_with('1st param', datetime='now()')


def test_celery__TransactionAwareTask__delay__5(celery_session_worker, zcml):
    """It allows to run two tasks in a single session."""
    auth = zope.component.getUtility(
        zope.authentication.interfaces.IAuthentication)
    principal = auth.getPrincipal('example.user')
    z3c.celery.celery.login_principal(principal)
    result1 = get_principal_title_task.delay()

    zope.security.management.endInteraction()
    principal = auth.getPrincipal('zope.user')
    z3c.celery.celery.login_principal(principal)
    result2 = get_principal_title_task.delay()

    transaction.commit()

    assert 'Ben Utzer' == result1.get()
    assert 'User' == result2.get()


def test_celery__TransactionAwareTask__delay__6(celery_session_worker, zcml):
    """It allows overriding the principal."""
    auth = zope.component.getUtility(
        zope.authentication.interfaces.IAuthentication)
    principal = auth.getPrincipal('example.user')
    z3c.celery.celery.login_principal(principal)
    result = get_principal_title_task.delay(_principal_id_='zope.user')

    transaction.commit()
    assert 'User' == result.get()


def test_celery__TransactionAwareTask__apply_async__1():
    """It raises a TypeError if arguments are not JSON serializable."""
    with pytest.raises(TypeError):
        eager_task.apply_async(
            (object(),), {'datetime': now},
            task_id=now, countdown=now)


def test_celery__TransactionAwareTask__apply_async__2(interaction):
    """It registers a task if arguments are JSON serializable."""
    assert 0 == len(celery_session)
    eager_task.apply_async(
        ('http://url.to/testcontent',),
        {'datetime': '2016-01-01 12:00:00'},
        task_id=1, countdown=30)
    assert 1 == len(celery_session)


def test_celery__TransactionAwareTask__apply_async__3(
        interaction, eager_celery_app):
    """It extracts the principal from the interaction if run in async mode."""
    asynch = 'z3c.celery.celery.TransactionAwareTask._eager_use_session_'
    with mock.patch(asynch, new=True):
        eager_task.apply_async(('1st param',), dict(datetime='now()'))
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
    with mock.patch.object(eager_task, 'run') as task_call:
        eager_task.apply_async(('1st param',), dict(datetime='now()'))
    task_call.assert_called_with('1st param', datetime='now()')


def test_celery__TransactionAwareTask__apply_async__5(
        interaction, eager_celery_app):
    """It processes the missing kw argument as emtpy dict."""
    # We need to make this a bit complicated as we want to see the actual call
    # of __call__ after the argument handling
    asynch = 'z3c.celery.celery.TransactionAwareTask._eager_use_session_'
    with mock.patch(asynch, new=True):
        eager_task.apply_async(('1st param',))
    task_call = 'z3c.celery.celery.TransactionAwareTask.__call__'
    with mock.patch(task_call) as task_call:
        transaction.commit()
    task_call.assert_called_with(
        '1st param', _run_asynchronously_=True, _principal_id_=u'zope.user')


@shared_task
def exception_task(context=None, datetime=None):
    """Dummy task which raises an exception to test our framework."""
    raise RuntimeError()


def test_celery__TransactionAwareTask____call____1(celery_session_worker):
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
    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    with mock.patch(configure_zope), \
            mock.patch.object(eager_task, 'run',
                              side_effect=RuntimeError) as run, \
            mock.patch('transaction.abort') as abort:

        zope.security.management.endInteraction()
        with pytest.raises(RuntimeError):
            # We want to simulate a run in worker. The RuntimeError is raised
            # by the mock
            eager_task(_run_asynchronously_=True)

    assert run.called
    assert abort.called


@shared_task(max_retries=1)
def conflict_task(bind=True, context=None, datetime=None):
    """Dummy task which injects a DataManager that votes a ConflictError."""
    transaction.get().join(VoteExceptionDataManager())


class NoopDatamanager:
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


def test_celery__TransactionAwareTask____call____2(
        celery_session_worker, interaction):
    """It aborts the transaction and retries in case of an ConflictError."""
    result = conflict_task.delay()
    transaction.commit()
    with pytest.raises(Exception) as err:
        result.get()
    assert 'MaxRetriesExceededError' == err.value.__class__.__name__


@shared_task(max_retries=2)
def conflict_after_abort_task():
    """Dummy task which injects a DataManager that votes a ConflictError."""
    raise HandleAfterAbort(conflicts_once)


conflicts_after_abort = 0


def conflicts_once():
    global conflicts_after_abort
    if conflicts_after_abort == 0:
        transaction.get().join(VoteExceptionDataManager())
    conflicts_after_abort += 1


def test_celery__TransactionAwareTask____call____2a(eager_celery_app):
    """It retries on ConflictError during HandleAfterAbort."""
    assert conflicts_after_abort == 0
    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    with mock.patch(configure_zope), \
            mock.patch('time.sleep') as sleep:
        with pytest.raises(HandleAfterAbort):
            conflict_after_abort_task(_run_asynchronously_=True)
        assert sleep.call_count == 1
        assert conflicts_after_abort == 2


def test_celery__TransactionAwareTask____call____3(
        celery_session_worker, zcml):
    """It runs as given principal in asynchronous mode."""
    auth = zope.component.getUtility(
        zope.authentication.interfaces.IAuthentication)
    principal = auth.getPrincipal('example.user')
    z3c.celery.celery.login_principal(principal)
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


@shared_task(bind=True)
def get_task_id(self):
    """Get the task id of the job."""
    return self.request.id


def test_celery__TransactionAwareTask____call____4(
        celery_session_worker, interaction):
    """It propagates the task_id to the worker."""
    job = get_task_id.apply_async(task_id='my-nice-task-id')
    transaction.commit()
    assert 'my-nice-task-id' == job.get()


@shared_task
def except_with_handler():
    """Raise an exception which is handled after abort."""
    site = zope.component.hooks.getSite()
    site['foo'] = 'bar'

    def handler(arg1, arg2, kw1=1, kw2=2):
        interaction = zope.security.management.getInteraction()
        site['data'] = (arg1, arg2, kw1, kw2,
                        interaction.participations[0].principal.title)

    raise HandleAfterAbort(handler, 'a1', 'a2', kw2=4)


def test_celery__TransactionAwareTask____call__5(
        interaction):
    """It handles specific exceptions when running synchronously."""
    data = {}
    with mock.patch('zope.component.hooks.getSite', return_value=data):
        with pytest.raises(HandleAfterAbort):
            except_with_handler()
    assert {'data': ('a1', 'a2', 1, 4, u'zope.user'), 'foo': 'bar'} == data


def test_celery__TransactionAwareTask__run_in_worker__1(
        celery_session_worker, storage_file, interaction):
    """It handles specific exceptions in a new transaction after abort."""
    job = except_with_handler.delay()
    transaction.commit()
    with pytest.raises(Exception):
        job.get()

    with open_zodb_copy(storage_file) as app:
        assert [('data', ('a1', 'a2', 1, 4, u'User'))] == list(app.items())


def test_celery__TransactionAwareTask__run_in_worker__1__cov(
        interaction, eager_celery_app, zcml):
    """It handles specific exceptions in a new transaction after abort.

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    data = {}
    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    with mock.patch(configure_zope),\
            mock.patch('zope.component.hooks.getSite', return_value=data):
        zope.security.management.endInteraction()
        with pytest.raises(HandleAfterAbort):
            except_with_handler(
                _run_asynchronously_=True, _principal_id_='example.user')

    # transaction.abort() does not remove items from a dict, so 'foo': 'bar'
    # also shows up here:
    assert {'data': ('a1', 'a2', 1, 4, u'Ben Utzer'), 'foo': 'bar'} == data


@shared_task
def success_but_abort_transaction():
    site = zope.component.hooks.getSite()
    site['flub'] = 'will not be written'
    raise Abort(lambda: None, message='done')


def test_celery__TransactionAwareTask__run_in_worker__2(
        celery_session_worker, storage_file, interaction):
    """It handles a specific exceptions to abort the transaction but still
    count as a successful job."""
    job = success_but_abort_transaction.delay()
    transaction.commit()
    assert 'done' == job.get()

    with open_zodb_copy(storage_file) as app:
        assert 'flub' not in app


def test_celery__HandleAfterAbort__1():
    """It returns the message in the exception unicode which was passed in."""
    err = HandleAfterAbort(lambda: None, message=u'test-messäge')
    err()
    assert 'test-messäge' == str(err)


def test_celery__HandleAfterAbort__1_5():
    """It returns the message in the exception string which was passed in."""
    err = HandleAfterAbort(lambda: None, message='test-messäge')
    err()
    assert 'test-messäge' == str(err)


def test_celery__HandleAfterAbort__2():
    """It does not pass the message as argument to the callback."""
    data = {}

    def save_args(*args, **kwargs):
        data['args'] = args
        data['kwargs'] = kwargs

    err = HandleAfterAbort(save_args, 2, 3, message=u'test-messäge', kw1='23')
    err()
    assert {'args': (2, 3), 'kwargs': {'kw1': '23'}} == data


class CommitExceptionDataManager(NoopDatamanager):
    """DataManager which raises an exception in tpc_vote."""

    def tpc_vote(self, trans):
        raise RuntimeError('provoked')

    def sortKey(self):
        # Make sure we are running after the in thread execution of the task so
        # that we can throw an Error as last part of vote:
        return '~~sort-me-last'


@shared_task
def commit_error_task(bind=True):
    transaction.get().join(CommitExceptionDataManager())


def test_celery__TransactionAwareTask__run_in_worker__3(
        celery_session_worker, interaction):
    """It always ends the interaction even when commit raises."""
    commit_error_task.delay()
    transaction.commit()
    result = get_principal_title_task.delay()
    transaction.commit()
    assert 'User' == result.get()


@shared_task(bind=True)
def get_principal_retry(self):
    if not self.request.retries:
        self.retry(countdown=0)
    interaction = zope.security.management.getInteraction()
    return [
        self.request.retries, interaction.participations[0].principal.title]


def test_celery__TransactionAwareTask_retry(
        interaction, celery_session_worker):
    """It keeps the interaction on retry."""
    result = get_principal_retry.delay()
    transaction.commit()
    assert [1, 'User'] == result.get()
