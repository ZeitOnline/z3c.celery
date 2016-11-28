from celery import shared_task
import ZODB.POSException
import celery.backends.base
import celery.exceptions
import mock
import pytest
import transaction
import zope.authentication.interfaces
import zope.security.management


@shared_task
def conflict_task(context=None, datetime=None):
    """Dummy task which injects a DataManager that votes a ConflictError."""
    transaction.get().join(VoteExceptionDataManager())


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
        celery_session_worker, interaction):
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
