from __future__ import absolute_import
from ..loader import ZopeLoader
from .shared_tasks import get_principal_title_task
from zope.principalregistry.principalregistry import principalRegistry
import contextlib
import plone.testing.zca
import pytest
import zope.app.appsetup.appsetup


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
