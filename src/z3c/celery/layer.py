from __future__ import absolute_import
import mock
import celery.contrib.pytest
import plone.testing


class EndToEndLayer(plone.testing.Layer):
    """Run celery end to end tests in a plone.testing Layer.

    Expects the following resources:

    * `celery_config`: dict of config options for the celery app
    * `celery_parameters`: dict of parameters used to instantiate Celery
    * `celery_includes`: list of dotted names to load the tasks in the worker
    """

    def setUp(self):
        request_mock = mock.Mock()
        request_mock.node.get_marker.return_value = {}
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
                celery_worker_pool='prefork'))
        next(self['celery_worker_fixture'])

    def tearDown(self):
        next(self['celery_app_fixture'], None)
        del self['celery_app_fixture']
        next(self['celery_worker_fixture'], None)
        del self['celery_worker_fixture']
