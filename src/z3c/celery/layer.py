from celery.contrib.testing.app import TestApp, setup_default_app
from celery.contrib.testing.worker import start_worker
import plone.testing
import z3c.celery


class EagerLayer(plone.testing.Layer):

    def setUp(self):
        # No isolation problem, end to end tests use a separate celery app
        # which is provided by EndToEndLayer (below).
        z3c.celery.CELERY.conf.task_always_eager = True

    def tearDown(self):
        z3c.celery.CELERY.conf.task_always_eager = False


EAGER_LAYER = EagerLayer()


class EndToEndLayer(plone.testing.Layer):
    """Run celery end to end tests in a plone.testing Layer.

    Expects the following resources:

    * `celery_config`: dict of config options for the celery app
    * `celery_parameters`: dict of parameters used to instantiate Celery
    * `celery_worker_parameters`: dict of parameters used to instantiate
       celery workers
    * `celery_includes`: list of dotted names to load the tasks in the worker
    """

    def setUp(self):
        celery_app = TestApp(
            set_as_current=False, enable_logging=True,
            config=self['celery_config'], **self['celery_parameters'])
        self['celery_app_fixture'] = setup_default_app(celery_app)
        self['celery_app_fixture'].__enter__()

        for module in self['celery_includes']:
            celery_app.loader.import_task_module(module)

        self['celery_worker_fixture'] = start_worker(
            celery_app, pool='prefork', **self['celery_worker_parameters'])
        self['celery_worker_fixture'].__enter__()

    def tearDown(self):
        self['celery_app_fixture'].__exit__(None, None, None)
        del self['celery_app_fixture']
        self['celery_worker_fixture'].__exit__(None, None, None)
        del self['celery_worker_fixture']
