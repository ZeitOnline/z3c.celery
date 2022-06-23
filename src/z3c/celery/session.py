import threading
import transaction
import zope.interface
import transaction.interfaces


class CelerySession(threading.local):
    """Thread local session of data to be sent to Celery."""

    def __init__(self):
        self.tasks = []
        self._needs_to_join = True

    def add_call(self, method, *args, **kw):
        self._join_transaction()
        self.tasks.append((method, args, kw))

    def reset(self):
        self.tasks = []
        self._needs_to_join = True

    def _join_transaction(self):
        if not self._needs_to_join:
            return
        dm = CeleryDataManager(self)
        transaction.get().join(dm)
        self._needs_to_join = False

    def _flush(self):
        for method, args, kw in self.tasks:
            method(*args, **kw)
        self.reset()

    def __len__(self):
        """Number of tasks in the session."""
        return len(self.tasks)


celery_session = CelerySession()


@zope.interface.implementer(transaction.interfaces.IDataManager)
class CeleryDataManager:
    """DataManager embedding the access to celery into the transaction."""

    transaction_manager = None

    def __init__(self, session):
        self.session = session

    def abort(self, transaction):
        self.session.reset()

    def tpc_begin(self, transaction):
        pass

    def commit(self, transaction):
        pass

    tpc_abort = abort

    def tpc_vote(self, transaction):
        self.session._flush()

    def tpc_finish(self, transaction):
        pass

    def sortKey(self):
        # Sort last, so that sending to celery is done after all other
        # DataManagers signalled an okay.
        return "~z3c.celery"

    def __repr__(self):
        """Custom repr."""
        return '<{0.__module__}.{0.__name__} for {1}, {2}>'.format(
            self.__class__, transaction.get(), self.session)
