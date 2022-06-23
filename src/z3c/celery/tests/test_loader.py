from ..loader import ZopeLoader
from .shared_tasks import get_principal_title_task
from unittest import mock
from zope.principalregistry.principalregistry import principalRegistry
import celery.signals
import contextlib
import logging
import plone.testing.zca
import pytest
import tempfile
import z3c.celery
import zope.app.appsetup.appsetup
import zope.security.management


LOGGING_TEMPLATE = """
[loggers]
keys = root, root

[handlers]
keys = logfile

[formatters]
keys = taskformatter

[logger_root]
level = DEBUG
handlers = logfile
qualname = root

[handler_logfile]
class = FileHandler
formatter = taskformatter
args = ('{filename}',)

[formatter_taskformatter]
class = z3c.celery.logging.TaskFormatter
format = task_id: %(task_id)s name: %(task_name)s %(message)s
"""


def test_loader__ZopeLoader__on_worker_init__1__cov(
        interaction, eager_celery_app, zcml):
    """It connects a signal for logging setup if LOGGING_INI is present in

    the configuration.

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    @z3c.celery.task
    def simple_log():
        """Just log something."""
        log = logging.getLogger(__name__)
        log.debug('Hello Log!')

    configure_zope = 'z3c.celery.celery.TransactionAwareTask.configure_zope'
    with tempfile.NamedTemporaryFile(delete=False) as logging_ini, \
            tempfile.NamedTemporaryFile(delete=False) as logfile:
        logging_ini.write(
            LOGGING_TEMPLATE.format(filename=logfile.name).encode('utf-8'))
        logging_ini.flush()
        eager_celery_app.conf['LOGGING_INI'] = logging_ini.name
        loader = ZopeLoader(app=eager_celery_app)
        loader.on_worker_init()
        celery.signals.setup_logging.send(sender=None)

        with mock.patch(configure_zope):
            zope.security.management.endInteraction()
            simple_log(
                _run_asynchronously_=True, _principal_id_='example.user')

        logfile.seek(0)
        log_result = logfile.read().decode('utf-8')

        assert ('task_id: None name: z3c.celery.tests.test_loader.'
                'simple_log Hello Log!\n' in log_result)


def test_loader__ZopeLoader__on_worker_process_init__1__cov(
        interaction, eager_celery_app):
    """It raises a ValueError if there is no `ZOPE_CONF` in the configuration.

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    eager_celery_app.conf['ZOPE_CONF'] = None

    loader = ZopeLoader(app=eager_celery_app)
    with pytest.raises(ValueError) as err:
        loader.on_worker_process_init()
    assert (
        'Celery setting ZOPE_CONF not set, check celery worker config.' ==
        str(err.value))


@contextlib.contextmanager
def zope_loader(app):
    plone.testing.zca.pushGlobalRegistry()
    try:
        app.loader.on_worker_process_init()
        yield
    finally:
        app.loader.on_worker_shutdown()
        plone.testing.zca.popGlobalRegistry()
        principalRegistry._clear()
        zope.app.appsetup.appsetup.reset()


def test_loader__ZopeLoader__1__cov(eager_celery_app):
    """It sets up and tears down Zope on worker init and teardown.

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    with zope_loader(eager_celery_app):
        assert ('Ben Utzer' ==
                principalRegistry.getPrincipal('example.user').title)


def test_loader__ZopeLoader__2__cov(eager_celery_app):
    """It provides the Zope environment to the task."

    As it is hard to collect coverage for sub-processes we use this test for
    coverage only.
    """
    with zope_loader(eager_celery_app):
        assert "Ben Utzer" == get_principal_title_task(
            _run_asynchronously_=True, _principal_id_='example.user')
