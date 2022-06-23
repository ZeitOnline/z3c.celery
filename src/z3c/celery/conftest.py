import celery.contrib.testing.app
import collections
import contextlib
import os
import pkg_resources
import plone.testing.zca
import pytest
import tempfile
import transaction
import z3c.celery
import z3c.celery.celery
import z3c.celery.testing
import zope.principalregistry.principalregistry
import zope.security.management
import zope.security.testing


ZODBConnection = collections.namedtuple(
    'ZODBConnection', ['connection', 'rootFolder', 'zodb'])


@pytest.fixture(scope='function')
def zcml():
    """Load ZCML on session scope."""
    layer = plone.testing.zca.ZCMLSandbox(
        name="CeleryZCML", filename='ftesting.zcml',
        module=__name__, package=z3c.celery)
    layer.setUp()
    yield layer
    # We might define principles in ftesting.zcml and we want to have a clean
    # state for each test, so we clear the registry here.
    layer.tearDown()
    zope.principalregistry.principalregistry.principalRegistry._clear()


@pytest.fixture(scope='function', autouse=True)
def automatic_transaction_begin():
    """Starts a new transaction for every test.

    We want to start with an empty celery_session for each test.

    """
    transaction.begin()
    zope.security.management.endInteraction()


@pytest.fixture(scope='function')
def interaction(automatic_transaction_begin):
    """Provide a zope interaction per test. Yields the principal."""
    principal = zope.security.testing.Principal(
        u'zope.user',
        groups=['zope.Authenticated'],
        description=u'test@example.com')
    z3c.celery.celery.login_principal(principal)
    yield principal
    zope.security.management.endInteraction()


@pytest.fixture(scope='session')
def storage_file():
    with tempfile.NamedTemporaryFile() as storage_file:
        yield storage_file.name


@pytest.fixture(scope='session')
def zope_conf(storage_file):
    with _zope_conf(storage_file) as x:
        yield x


@contextlib.contextmanager
def _zope_conf(storage_file):
    with tempfile.NamedTemporaryFile() as conf:
        conf.write(
            z3c.celery.testing.ZOPE_CONF_TEMPLATE.format(
                zodb_path=storage_file,
                ftesting_path=pkg_resources.resource_filename(
                    'z3c.celery', 'ftesting.zcml'),
                product_config='').encode('ascii'))
        conf.flush()
        yield conf.name


@pytest.fixture(scope='function')
def eager_celery_app(zope_conf):
    app = z3c.celery.CELERY
    conf = app.conf
    # deepcopy fails on py3 with infinite recursion,
    # but tests pass also with a simple copy of the conf
    old_conf = dict(conf)
    conf['ZOPE_CONF'] = zope_conf
    conf['task_always_eager'] = True
    conf['task_eager_propagates'] = True
    with celery.contrib.testing.app.setup_default_app(app):
        app.set_current()
        yield app
    app.conf.update(old_conf)


@pytest.fixture(scope='session')
def celery_config(zope_conf):
    return _celery_config(zope_conf)


def _celery_config(zope_conf):
    return {
        'broker_url': os.environ['Z3C_CELERY_BROKER'],
        'result_backend': os.environ['Z3C_CELERY_BROKER'],
        'worker_send_task_events': True,
        'task_send_sent_event': True,
        'task_remote_tracebacks': True,
        'ZOPE_CONF': zope_conf,
    }


@pytest.fixture(scope='session')
def celery_parameters():
    return _celery_parameters()


def _celery_parameters():
    return {
        'task_cls': z3c.celery.celery.TransactionAwareTask,
        'strict_typing': False,
        'loader': z3c.celery.celery.ZopeLoader,
    }


@pytest.fixture(scope='session')
def celery_enable_logging():
    return True


@pytest.fixture(scope='session')
def celery_includes():
    return ('z3c.celery.tests.shared_tasks',)


@pytest.fixture(scope='session')
def celery_worker_pool():
    return 'prefork'
