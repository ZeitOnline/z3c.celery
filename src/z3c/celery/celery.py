from __future__ import absolute_import
from .session import celery_session
import ZODB.POSException
import celery
import celery.bootsteps
import celery.loaders.app
import celery.signals
import celery.utils
import json
import logging
import logging.config
import os
import random
import transaction
import transaction.interfaces
import zope.authentication.interfaces
import zope.app.wsgi
import zope.component
import zope.component.hooks
import zope.exceptions.log
import zope.publisher.browser
import zope.security.management


log = logging.getLogger(__name__)


class TransactionAwareTask(celery.Task):
    """Wraps every Task execution in a transaction begin/commit/abort.
    If 'ZOPE_PRINCIPAL' is set in the celery configuration, also sets up a
    zope.security interaction.

    (Code inspired by gocept.runner.runner.MainLoop)
    """

    abstract = True  # Base class. Don't register as an excecutable task.

    @classmethod
    def bind(cls, app):
        # Unfortunately, Celery insists on setting up everything at import
        # time, which doesn't work for our clients, since the Zope
        # product-configuration is not available then. Thus we perform an
        # additional bind() in the configure_celery_app event handler.
        if getattr(app, 'configure_done', False):
            return app
        return super(TransactionAwareTask, cls).bind(app)

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
        running_asynchronously = kw.pop('_run_asynchronously_', False)
        principal_id = kw.pop('_principal_id_', None)

        if running_asynchronously:
            result = self.run_in_worker(principal_id, args, kw)
        else:
            result = super(TransactionAwareTask, self).__call__(*args, **kw)
        return result

    def run_in_worker(self, principal_id, args, kw):
        configfile = self.app.conf.get('ZOPE_CONF')
        if not configfile:
            raise ValueError(
                'Celery setting ZOPE_CONF not set, check in '
                'CELERY_CONFIG=%s' % os.environ.get('CELERY_CONFIG'))

        old_site = zope.component.hooks.getSite()

        db = self.configure_zope(configfile)
        self.transaction_begin(principal_id)
        try:
            result = super(TransactionAwareTask, self).__call__(
                *args, **kw)
        except Exception:
            self.transaction_abort()
            raise
        finally:
            zope.component.hooks.setSite(old_site)
        try:
            self.transaction_commit()
        except ZODB.POSException.ConflictError:
            log.warning('Conflict while publishing', exc_info=True)
            self.transaction_abort()
            self.retry(max_retries=3,
                       countdown=random.randint(1, 2 ** self.request.retries))
        finally:
            db.close()
        return result

    def transaction_begin(self, principal_id):
        if principal_id:
            transaction.begin()
            request = zope.publisher.browser.TestRequest()
            request.setPrincipal(self.get_principal(principal_id))
            zope.security.management.newInteraction(request)

    def transaction_abort(self):
        transaction.abort()
        zope.security.management.endInteraction()

    def transaction_commit(self):
        transaction.commit()
        zope.security.management.endInteraction()

    def get_principal(self, principal_id):
        auth = zope.component.getUtility(
            zope.authentication.interfaces.IAuthentication)
        return auth.getPrincipal(principal_id)

    def configure_zope(self, configfile):
        db = zope.app.wsgi.config(configfile)
        root_folder = db.open().root()['Application']
        zope.component.hooks.setSite(root_folder)
        return db

    def delay(self, *args, **kw):
        self._assert_json_serializable(*args, **kw)
        task_id = celery.utils.gen_unique_id()

        kw['_principal_id_'] = self._get_current_principal_id()
        if self.run_instantly():
            self.__call__(*args, **kw)
        elif not kw['_principal_id_']:
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
        if task_id is None:
            task_id = celery.utils.gen_unique_id()
        if kw is None:
            kw = {}

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


CELERY = celery.Celery(
    __name__, task_cls=TransactionAwareTask, strict_typing=False)
