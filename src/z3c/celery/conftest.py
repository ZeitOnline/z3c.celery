from __future__ import absolute_import
import collections
import pkg_resources
import plone.testing.zca
import plone.testing.zodb
import pytest
import tempfile
import transaction
import z3c.celery
import z3c.celery.testing
import zope.event
import zope.principalregistry.principalregistry
import zope.processlifetime
import zope.publisher.browser
import zope.security.management
import zope.security.testing


ZODBConnection = collections.namedtuple(
    'ZODBConnection', ['connection', 'rootFolder', 'zodb'])


@pytest.yield_fixture('function')
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


@pytest.fixture('function', autouse=True)
def automatic_transaction_begin():
    """Starts a new transaction for every test.

    We want to start with an empty celery_session for each test.

    """
    transaction.begin()
    zope.security.management.endInteraction()


@pytest.yield_fixture('function')
def interaction(automatic_transaction_begin):
    """Provide a zope interaction per test. Yields the principal."""
    principal = zope.security.testing.Principal(
        u'zope.user',
        groups=['zope.Authenticated'],
        description=u'test@example.com')
    z3c.celery.testing.login_principal(principal)
    yield principal
    zope.security.management.endInteraction()


@pytest.yield_fixture('session')
def storage_file():
    with tempfile.NamedTemporaryFile() as storage_file:
        yield storage_file.name


@pytest.yield_fixture('session')
def zope_conf(storage_file):
    with tempfile.NamedTemporaryFile() as conf:
        conf.write("""
# Identify the component configuration used to define the site:
site-definition {ftesting_path}

<zodb>
  <filestorage>
    path {zodb_path}
  </filestorage>
</zodb>

# logging is done using WSGI, but we need an empty entry here because
# eventlog is required.
<eventlog>
</eventlog>
""".format(zodb_path=storage_file,
           ftesting_path=pkg_resources.resource_filename(
               'z3c.celery', 'ftesting.zcml')))
        conf.flush()
        yield conf.name


@pytest.yield_fixture('function')
def eager_celery_app(zope_conf):
    conf = z3c.celery.celery.CELERY.conf
    conf['ZOPE_CONF'] = zope_conf
    conf['task_always_eager'] = True
    conf['task_eager_propagates'] = True
    yield conf
    conf['task_eager_propagates'] = False
    conf['task_always_eager'] = False
    conf.pop('ZOPE_CONF')


@pytest.fixture(scope='session')
def celery_config(zope_conf):
    return {
        'broker_url': 'redis://localhost:6379/1',
        'result_backend': 'redis://localhost:6379/1',
        'worker_send_task_events': True,
        'task_send_sent_event': True,
        'task_remote_tracebacks': True,
        'ZOPE_CONF': zope_conf,
    }


@pytest.fixture(scope='session')
def celery_parameters():
    return {
        'task_cls': z3c.celery.celery.TransactionAwareTask,
        'strict_typing': False,
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
