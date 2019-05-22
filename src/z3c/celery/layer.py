from __future__ import absolute_import
import mock
import celery.contrib.pytest
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
        request_mock = mock.Mock()
        # some old celery needs this:
        request_mock.node.get_marker.return_value = {}
        # celery 4.3.0 needs this:
        request_mock.node.get_closest_marker.return_value = {}
        self['celery_app_fixture'] = celery.contrib.pytest.celery_session_app(
            request_mock,
            self['celery_config'],
            self['celery_parameters'],
            celery_enable_logging=True,
            use_celery_app_trap=False)

        celery_app = next(self['celery_app_fixture'])
        self['celery_worker_fixture'] = (
            celery.contrib.pytest.celery_session_worker(
                request_mock,
                celery_app,
                self['celery_includes'],
                celery_worker_pool='prefork',
                celery_worker_parameters=self['celery_worker_parameters']))
        next(self['celery_worker_fixture'])

    def tearDown(self):
        next(self['celery_app_fixture'], None)
        del self['celery_app_fixture']
        next(self['celery_worker_fixture'], None)
        del self['celery_worker_fixture']
