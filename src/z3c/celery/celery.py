from .loader import ZopeLoader
from .session import celery_session
from celery._state import _task_stack
from celery.utils.serialization import raise_with_context
import ZODB.POSException
import celery
import celery.exceptions
import celery.utils
import contextlib
import json
import logging
import random
import socket
import time
import transaction
import zope.app.publication.zopepublication
import zope.authentication.interfaces
import zope.component
import zope.component.hooks
import zope.publisher.browser
import zope.security.management


log = logging.getLogger(__name__)


class HandleAfterAbort(RuntimeError):
    """Exception whose callback is executed after ``transaction.abort()``."""

    def __init__(self, callback, *args, **kwargs):
        self.message = kwargs.pop('message', u'')
        # Conform to BaseException API so it works with celery's serialization
        # (before 4.1.1 it just worked, but that was rather accidental)
        if isinstance(callback, str):
            self.message = callback
        if isinstance(self.message, bytes):
            self.message = self.message.decode('utf-8')

        super().__init__(self.message)

        self.callback = callback
        self.c_args = args
        self.c_kwargs = kwargs

    def __call__(self):
        self.callback(*self.c_args, **self.c_kwargs)

    def __str__(self):
        return self.message


class Abort(HandleAfterAbort):
    """Exception to signal successful task completion, but transaction should
    be aborted instead of commited.
    """


class Retry(celery.exceptions.Retry, HandleAfterAbort):
    """With cooperation from TransactionAwareTask.retry(), this moves the
    actual re-queueing of the task into the proper "error handling"
    transaction phase.
    """

    def __init__(self, *args, **kw):
        self.signature = kw.pop('signature', None)
        celery.exceptions.Retry.__init__(self, *args, **kw)

    def __call__(self):
        try:
            self.signature.apply_async()
            log.warning('Task submitted for retry in %s seconds.', self.when)
        except Exception as exc:
            log.error('Task retry failed', exc_info=True)
            raise celery.exceptions.Reject(exc, requeue=False)


def get_principal(principal_id):
    """Return the principal to the principal_id."""
    auth = zope.component.getUtility(
        zope.authentication.interfaces.IAuthentication)
    return auth.getPrincipal(principal_id)


def login_principal(principal, task_name=None):
    """Start an interaction with `principal`."""
    request = zope.publisher.browser.TestRequest(
        environ={'SERVER_URL': 'http://%s' % socket.getfqdn()})
    if task_name:
        # I'd rather set PATH_INFO, but that doesn't influence getURL().
        request._traversed_names = ['celery', task_name]
    request.setPrincipal(principal)
    zope.security.management.newInteraction(request)


class TransactionAwareTask(celery.Task):
    """Wrap every Task execution in a transaction begin/commit/abort.

    (Code inspired by gocept.runner.runner.MainLoop)
    """

    abstract = True  # Base class. Don't register as an executable task.

    def __call__(self, *args, **kw):
        """Run the task.

        Parameters:
            _run_asynchronously_ ... if `True` run the task its own transaction
                                     context, otherwise run it in inline
                                     (optional, default: `False` to be able to
                                      run tasks easily inline)
            _principal_id_ ... run asynchronous task as this user, ignored if
                               running synchronously (optional)

        Returns whatever the task returns itself.

        """
        run_asynchronously = kw.pop('_run_asynchronously_', False)
        principal_id = kw.pop('_principal_id_', None)
        # BBB This was removed in 1.2.0 but there still might be (scheduled)
        # tasks that transmit this argument, so we need to remove it.
        kw.pop('_task_id_', None)

        is_eager = self.app.conf['task_always_eager']
        if is_eager:
            # This is the only part of celery.Task.__call__ that actually is
            # relevant -- since in non-eager mode, it's not called at all:
            # celery.app.trace.build_tracer() says, "if the task doesn't define
            # a custom __call__ method we optimize it away by simply calling
            # the run method directly".
            # (Note that the push_request() call in __call__ would be actively
            # harmful in non-eager mode, since it hides the actual request that
            # was set by app.trace; but as it's not called, it's not an issue.)
            _task_stack.push(self)
        try:
            if run_asynchronously:
                result = self.run_in_worker(principal_id, args, kw)
            else:
                result = self.run_in_same_process(args, kw)
        finally:
            if is_eager:
                _task_stack.pop()
        return result

    def run_in_same_process(self, args, kw):
        try:
            return self.run(*args, **kw)
        except Abort as handle:
            transaction.abort()
            handle()
            return handle.message
        except HandleAfterAbort as handle:
            handle()
            raise

    def run_in_worker(self, principal_id, args, kw, retries=0):
        with self.configure_zope():
            try:
                with self.transaction(principal_id):
                    return self.run(*args, **kw)
            except HandleAfterAbort as handle:
                for handle_retries in range(self.max_retries):
                    try:
                        with self.transaction(principal_id):
                            handle()
                    except celery.exceptions.Retry:
                        # We have to handle ConflictErrors manually, since we
                        # don't want to retry the whole task (which was
                        # erroneous anyway), but only the after-abort portion.
                        countdown = random.uniform(0, 2 ** handle_retries)
                        log.warning('Waiting %s seconds for retry.', countdown)
                        time.sleep(countdown)
                        continue
                    else:
                        break
                else:
                    log.warning('Giving up on %r after %s retries',
                                handle, self.max_retries)

                if isinstance(handle, Abort):
                    return handle.message
                else:
                    raise handle

    @contextlib.contextmanager
    def transaction(self, principal_id):
        if principal_id:
            transaction.begin()
            login_principal(get_principal(principal_id), self.name)
            txn = transaction.get()
            txn.setUser(str(principal_id))
            txn.setExtendedInfo('task_name', self.name)
        try:
            yield
        except Exception:
            transaction.abort()
            raise
        else:
            try:
                transaction.commit()
            except ZODB.POSException.ConflictError:
                log.warning('Conflict while publishing', exc_info=True)
                transaction.abort()
                self.retry(
                    countdown=random.uniform(0, 2 ** self.request.retries))
        finally:
            transaction.abort()
            zope.security.management.endInteraction()

    @contextlib.contextmanager
    def configure_zope(self):
        old_site = zope.component.hooks.getSite()
        db = self.app.conf.get('ZODB')
        connection = db.open()
        root_folder = connection.root()[
            zope.app.publication.zopepublication.ZopePublication.root_name]
        zope.component.hooks.setSite(root_folder)
        try:
            yield
        finally:
            connection.close()
            zope.component.hooks.setSite(old_site)

    _eager_use_session_ = False  # Hook for tests

    def apply_async(self, args=None, kw=None, task_id=None, **options):
        self._assert_json_serializable(args, kw)
        if kw is None:
            kw = {}
        if task_id is None:
            task_id = celery.utils.gen_unique_id()
        kw.setdefault('_principal_id_', self._get_current_principal_id())

        # Accomodations for tests:
        # 1. Normally we defer (asynchronous) task execution to the transaction
        # commit via celery_session (see else-branch below). But in
        # always_eager mode the execution is synchronous, so the whole task
        # would run _during_ the commit phase, which totally breaks if inside
        # the task the transaction is touched in any way, e.g. by calling for a
        # savepoint. Since we need to support this kind of completely normal
        # behaviour, we bypass the session in always_eager mode.
        # 2. To simplify tests concerning our celery-integration mechanics we
        # provide a hook so tests can force using the session even in
        # always_eager mode (because otherwise those tests would have to use an
        # end-to-end setup, which would make the introspection they need
        # complicated if not impossible).
        # XXX These actually rather belongs into CelerySession, but that would
        # get mechanically complicated.
        if self.app.conf['task_always_eager'] and not self._eager_use_session_:
            self.__call__(*args, **kw)
        elif self.name == 'celery.ping':
            # Part of celery.contrib.testing setup, we need to perform this
            # immediately, because it has no transaction integration.
            return super().apply_async(args, kw, task_id=task_id, **options)
        else:
            # Hook so tests can force __call__ to use run_in_worker even when
            # always_eager is True, by passing in this kw explicitly.
            kw.setdefault('_run_asynchronously_', True)
            celery_session.add_call(
                super().apply_async, args, kw, task_id, **options)
        return self.AsyncResult(task_id)

    def _assert_json_serializable(self, *args, **kw):
        json.dumps(args)
        json.dumps(kw)

    def _get_current_principal_id(self):
        interaction = zope.security.management.queryInteraction()
        if interaction is None:
            principal_id = None
        else:
            principal_id = interaction.participations[0].principal.id
        return principal_id

    def retry(self, args=None, kwargs=None, exc=None, throw=True,
              eta=None, countdown=None, max_retries=None, **options):
        # copy&paste from superclass, we need to use a Retry exception that
        # uses the HandleAfterAbort mechanics to integrate with transactions.
        request = self.request
        retries = request.retries + 1
        max_retries = self.max_retries if max_retries is None else max_retries

        if request.called_directly:
            raise_with_context(
                exc or celery.exceptions.Retry('Task can be retried', None))

        if not eta and countdown is None:
            countdown = self.default_retry_delay

        # Add interaction information now, while it's still present. Our
        # apply_async() would normally do this, but it's called via
        # HandleAfterAbort when the original interaction has already ended.
        options.setdefault('_principal_id_', self._get_current_principal_id())

        S = self.signature_from_request(
            request, args, kwargs,
            countdown=countdown, eta=eta, retries=retries,
            **options
        )

        if max_retries is not None and retries > max_retries:
            if exc:
                raise_with_context(exc)
            raise self.MaxRetriesExceededError(
                "Can't retry {0}[{1}] args:{2} kwargs:{3}".format(
                    self.name, request.id, S.args, S.kwargs))

        ret = Retry(exc=exc, when=eta or countdown, signature=S)

        if request.is_eager:
            S.apply().get()
            if throw:
                raise ret
            return ret

        if throw:
            raise ret
        else:
            ret()
            return ret


CELERY = celery.Celery(
    __name__, task_cls=TransactionAwareTask, loader=ZopeLoader,
    strict_typing=False)
