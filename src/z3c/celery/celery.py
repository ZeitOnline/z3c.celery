from __future__ import absolute_import
from .loader import ZopeLoader
from .session import celery_session
import ZODB.POSException
import celery
import celery.bootsteps
import celery.exceptions
import celery.loaders.app
import celery.signals
import celery.utils
import contextlib
import json
import logging
import random
import time
import transaction
import transaction.interfaces
import zope.app.publication.zopepublication
import zope.app.wsgi
import zope.authentication.interfaces
import zope.component
import zope.component.hooks
import zope.exceptions.log
import zope.publisher.browser
import zope.security.management


log = logging.getLogger(__name__)


class HandleAfterAbort(RuntimeError):
    """Exception whose callback is executed after ``transaction.abort()``."""

    def __init__(self, callback, *args, **kwargs):
        self.message = kwargs.pop('message', u'')
        if isinstance(self.message, bytes):
            self.message = self.message.decode('utf-8')

        super(HandleAfterAbort, self).__init__(self.message)

        self.callback = callback
        self.c_args = args
        self.c_kwargs = kwargs

    def __call__(self):
        self.callback(*self.c_args, **self.c_kwargs)

    def __str__(self):
        return self.message.encode('utf-8')

    def __unicode__(self):
        return self.message


def get_principal(principal_id):
    """Return the principal to the principal_id."""
    auth = zope.component.getUtility(
        zope.authentication.interfaces.IAuthentication)
    return auth.getPrincipal(principal_id)


def login_principal(principal):
    """Start an interaction with `principal`."""
    request = zope.publisher.browser.TestRequest()
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
            _task_id_ ... id of the task

        Returns whatever the task returns itself.

        """
        running_asynchronously = kw.pop('_run_asynchronously_', False)
        principal_id = kw.pop('_principal_id_', None)
        # There is currently no other way to get the task_id to the worker, see
        # https://github.com/celery/celery/issues/2633
        task_id = kw.pop('_task_id_', None)
        if task_id:
            self.task_id = task_id

        if running_asynchronously:
            result = self.run_in_worker(principal_id, args, kw)
        else:
            result = self.run_in_same_process(args, kw)
        return result

    def run_in_same_process(self, args, kw):
        try:
            return super(TransactionAwareTask, self).__call__(*args, **kw)
        except HandleAfterAbort as handle:
            handle()
            raise

    def run_in_worker(self, principal_id, args, kw, retries=0):
        if retries > self.max_retries:
            raise celery.exceptions.MaxRetriesExceededError(
                principal_id, args, kw)

        retry = False
        with self.configure_zope():
            self.transaction_begin(principal_id)
            try:
                result = super(TransactionAwareTask, self).__call__(
                    *args, **kw)
            except HandleAfterAbort as handle:
                self.transaction_abort()
                self.transaction_begin(principal_id)
                handle()
                self.transaction_commit()
                raise
            except Exception:
                self.transaction_abort()
                raise
            try:
                self.transaction_commit()
            except ZODB.POSException.ConflictError:
                log.warning('Conflict while publishing', exc_info=True)
                self.transaction_abort()
                retry = True

        if retry:
            countdown = random.uniform(0, 2 ** retries)
            log.warning('Retry in {} seconds.'.format(countdown))
            time.sleep(countdown)
            result = self.run_in_worker(
                principal_id, args, kw, retries=retries + 1)
        return result

    def transaction_begin(self, principal_id):
        if principal_id:
            transaction.begin()
            login_principal(get_principal(principal_id))

    def transaction_abort(self):
        transaction.abort()
        zope.security.management.endInteraction()

    def transaction_commit(self):
        transaction.commit()
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

    def delay(self, *args, **kw):
        self._assert_json_serializable(*args, **kw)
        task_id = celery.utils.gen_unique_id()

        kw['_principal_id_'] = self._get_current_principal_id()
        kw['_task_id_'] = task_id
        if self.run_instantly():
            self.__call__(*args, **kw)
        elif not kw['_principal_id_']:
            # Tests run a `ping.delay()` task beforehand which we handle here
            # separately:
            return super(TransactionAwareTask, self).apply_async(
                args, kw, task_id=task_id)
        else:
            kw['_run_asynchronously_'] = self.run_asynchronously()
            celery_session.add_call(
                super(TransactionAwareTask, self).apply_async,
                args, kw, task_id=task_id)
        return self.AsyncResult(task_id)

    def apply_async(
            self, args=(), kw=None, task_id=None, *arguments, **options):
        self._assert_json_serializable(
            args, kw, task_id, *arguments, **options)
        if kw is None:
            kw = {}
        if task_id is None:
            task_id = celery.utils.gen_unique_id()
        kw['_task_id_'] = task_id

        if self.run_instantly():
            self.__call__(*args, **kw)
        else:
            kw['_principal_id_'] = self._get_current_principal_id()
            kw['_run_asynchronously_'] = self.run_asynchronously()
            celery_session.add_call(
                super(TransactionAwareTask, self).apply_async,
                args, kw, task_id, *arguments, **options)
        return self.AsyncResult(task_id)

    def run_instantly(self):
        """If `True` run the task instantly.

        Otherwise starting the task is delayed to the end of the transaction.
        By default in tests tasks run instantly.

        This method is a hook to be able to change this behaviour in tests.
        """
        return self.app.conf['task_always_eager']

    def run_asynchronously(self):
        """If `True` the task is run in its own transaction context.

        Default: `True`

        This method is a hook to be able to change the behaviour in tests.
        """
        return True

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


def get_config_source():
    """Provide the correct source to configure the app.

    In case the application uses grok, it is possible that a default app is
    instantiated before our app (see below). The default app gets the
    configuration specified in celeryconfig.py and our app is not configured
    with it.
    """
    try:
        config_source = celery.app.default_app.conf
    except AttributeError:
        config_source = None
    return config_source


CELERY = celery.Celery(
    __name__, task_cls=TransactionAwareTask, loader=ZopeLoader,
    strict_typing=False, config_source=get_config_source())
CELERY.set_default()
