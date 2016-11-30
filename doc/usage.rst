Usage
=====

Running end to end tests using layers
-------------------------------------

Motivation: Celery 4.x provides py.test fixtures. There is some infrastructure
in this package to use these fixtures together with `plone.testing.Layer`.
The following steps are required to set the layers up correctly:

Create a layer which provides the following resources:

* ``celery_config``: dict of config options for the celery app. It has to
  include a key ``ZOPE_CONF`` which has to point to a `zope.conf` file.
  See the template in :mod:`z3c.celery.testing`.

* ``celery_parameters``: dict of parameters used to instantiate Celery

* ``celery_includes``: list of dotted names to load the tasks in the worker

Example::

    class CelerySettingsLayer(plone.testing.Layer):
        """Settings for the Celery end to end tests."""

        def setUp(self):
            self['celery_config'] = {
                'ZOPE_CONF': '/path/to/my/test-zope.conf'}
            self['celery_parameters'] = (
                z3c.celery.conftest.celery_parameters())
            self['celery_includes'] = ['my.module.tasks']

        def tearDown(self):
            del self['celery_config']
            del self['celery_includes']
            del self['celery_parameters']

Create a layer which brings the settings layer and the :class:`EndToEndLayer`
together, example::

    CELERY_SETTINGS_LAYER = CelerySettingsLayer()
    CONFIGURED_END_TO_END_LAYER = z3c.celery.layer.EndToEndLayer(
        bases=[CELERY_SETTINGS_LAYER], name="ConfiguredEndToEndLayer")

Create a layer which combines the configured EndToEndLayer with the ZCMLLayer
of your application. (This should be the one created by
:class:`plone.testing.zca.ZCMLSandbox`.)

Example::

    MY_PROJ_CELERY_END_TO_END_LAYER = plone.testing.Layer(
        bases=(CONFIGURED_END_TO_END_LAYER, ZCML_LAYER),
        name="MyProjectCeleryEndToEndLayer")

.. note::

    The ZCMLLayer has to be the last one in the list of the bases because the
    EndToEndLayer forks the workers when it is set up. If the ZCML is already
    there running a task in the worker will break because as first step it has
    to load the `zope.conf`.


.. caution::

    All tasks to be run in end to end tests have to shared tasks. Example::

        @celery.shared_task
        def my_task():
            do_stuff()
