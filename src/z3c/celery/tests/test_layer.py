from ..layer import EndToEndLayer
from .shared_tasks import get_principal_title_task
import plone.testing
import plone.testing.zca
import tempfile
import transaction
import unittest
import z3c.celery.celery
import z3c.celery.conftest
import z3c.celery.testing
import zope.authentication.interfaces
import zope.component


ZCML_LAYER = plone.testing.zca.ZCMLSandbox(
    name="CeleryZCML", filename='ftesting.zcml',
    module=__name__, package=z3c.celery)


class SettingsLayer(plone.testing.Layer):
    """Settings for the EndToEndLayer."""

    def setUp(self):
        self['storage_file_fixture'] = tempfile.NamedTemporaryFile()
        storage_file = self['storage_file_fixture'].__enter__()
        self['zope_conf_fixture'] = z3c.celery.conftest._zope_conf(
            storage_file.name)

        zope_conf = self['zope_conf_fixture'].__enter__()
        self['celery_config'] = z3c.celery.conftest._celery_config(zope_conf)
        self['celery_parameters'] = z3c.celery.conftest._celery_parameters()
        self['celery_worker_parameters'] = {'queues': ('hiprio', 'celery')}
        self['celery_includes'] = ['z3c.celery.tests.shared_tasks']

    def tearDown(self):
        self['zope_conf_fixture'].__exit__(None, None, None)
        del self['zope_conf_fixture']
        self['storage_file_fixture'].__exit__(None, None, None)
        del self['storage_file_fixture']
        del self['celery_config']
        del self['celery_includes']
        del self['celery_parameters']
        del self['celery_worker_parameters']


SETTINGS_LAYER = SettingsLayer()
CONFIGURED_END_TO_END_LAYER = EndToEndLayer(
    bases=[SETTINGS_LAYER], name="ConfiguredEndToEndLayer")
ZOPE_END_TO_END_LAYER = plone.testing.Layer(
    bases=(CONFIGURED_END_TO_END_LAYER, ZCML_LAYER),
    name="ZopeEndToEndLayer")


class EndToEndLayerTests(unittest.TestCase):
    """Testing ..layer.EndToEndLayer."""

    layer = ZOPE_END_TO_END_LAYER

    def test_layer__EndToEndLayer__1(self):
        auth = zope.component.getUtility(
            zope.authentication.interfaces.IAuthentication)
        principal = auth.getPrincipal('example.user')
        z3c.celery.celery.login_principal(principal)
        result = get_principal_title_task.apply_async(queue='hiprio')

        transaction.commit()

        assert 'Ben Utzer' == result.get(timeout=10)
