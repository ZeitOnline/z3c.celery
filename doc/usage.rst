Usage
=====

Integration with Zope
---------------------

To successfully configure Celery in Zope place the ``celeryconfig.py`` in the
``PYTHONPATH``. The configuration will be taken from there.

Define your tasks as ``shared_task()`` so they can be used in the tests and
when running the server.

`z3c.celery` provides its own celery app: ``z3c.celery.CELERY``. It does the
actual the integration work.

Jobs by default run as the same principal that was active when the job was
enqueued. You can override this by passing a different principal id to ``delay``::

    my_task.delay(my, args, etc, _principal_id_='zope.otheruser')


Worker setup
------------

Place the ``celeryconfig.py`` in your working directory. Now you can start the
celery worker using the following command:

.. code-block:: console

    $ celery worker --app=z3c.celery.CELERY --config=celeryconfig

The `celeryconfig`_ can include all default celery config options. In addition
the variable ``ZOPE_CONF`` pointing to your ``zope.conf`` has to be present.
This ``celeryconfig.py`` and the referenced ``zope.conf`` should be identical to
the ones, your Zope is started with.

Additionally you can specify a variable ``LOGGING_INI`` pointing to a logging
config (an ini file in `configuration file format`_, which might be your
paste.ini). See `Logging`_ for details.

Example::

    ZOPE_CONF = '/path/to/zope.conf'
    LOGGING_INI = '/path/to/paste.ini'
    broker_url = 'redis://localhost:6379/0'
    result_backend = 'redis://localhost:6379/0'
    imports = ['my.tasks']


.. _`celeryconfig` : http://docs.celeryproject.org/en/latest/userguide/configuration.html
.. _`configuration file format` : https://docs.python.org/2/library/logging.config.html#configuration-file-format


Execute code after ``transaction.abort()``
------------------------------------------

If running a task fails the transaction is aborted. In case you need to write
something to the ZODB raise :class:`z3c.celery.celery.HandleAfterAbort` in your
task. This exception takes a callable and its arguments. It is run in a
separate transaction after ``transaction.abort()`` for the task was called.

It is possible to pass a keyword argument ``message`` into
:class:`~z3c.celery.celery.HandleAfterAbort`. This message will be serialized
and returned to celery in the task result. It is not passed to the callback.


Accessing the ``task_id`` in the task
-------------------------------------

There seems currently no way to get the task_id from inside the task when it is
a shared task. The task implementation in ``z3c.celery`` provides a solution.
You have to bind the shared task. This allows you to access the task instance
as first parameter of the task function. The ``task_id`` is stored there on the
``task_id`` attribute. Example::

    @shared_task(bind=True)
    def get_task_id(self):
        """Get the task id of the job."""
        return self.task_id


Logging
-------

``z3c.celery`` provides a special formatter for the python logging module,
which can also be used as a generic formatter as it will omit task specific
output if there is none. It allows to include task id and task name of the
current task in the log message if they are available. Include it in your
logging configuration:

.. code-block:: ini

    [formatter_generic]
    class = z3c.celery.logging.TaskFormatter
    format = %(asctime)s %(task_name)s %(task_id)s %(message)s

If ``python-json-logger`` is installed, we also provide ``z3c.celery.logging.JsonFormatter``.


Running end to end tests using layers
-------------------------------------

Motivation: Celery 4.x provides py.test fixtures. There is some infrastructure
in this package to use these fixtures together with `plone.testing.Layer`.
The following steps are required to set the layers up correctly:

In your package depend on ``z3c.celery[layer]``.

Create a layer which provides the following resources:

* ``celery_config``: dict of config options for the celery app. It has to
  include a key ``ZOPE_CONF`` which has to point to a `zope.conf` file.
  See the template in :mod:`z3c.celery.testing`.

* ``celery_parameters``: dict of parameters used to instantiate Celery

* ``celery_worker_parameters``: dict of parameters used to instantiate celery
  workers

* ``celery_includes``: list of dotted names to load the tasks in the worker

Example::

    class CelerySettingsLayer(plone.testing.Layer):
        """Settings for the Celery end to end tests."""

        def setUp(self):
            self['celery_config'] = {
                'ZOPE_CONF': '/path/to/my/test-zope.conf'}
            self['celery_parameters'] = (
                z3c.celery.conftest.celery_parameters())
            self['celery_worker_parameters'] = {'queues': ('celery',)}
            self['celery_includes'] = ['my.module.tasks']

        def tearDown(self):
            del self['celery_config']
            del self['celery_includes']
            del self['celery_parameters']
            del self['celery_worker_parameters']

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

    All tasks to be run in end to end tests have to shared tasks. This is
    necessary because the end to end tests have to use a different Celery
    instance than ``z3c.celery.CELERY``. Example::

        @celery.shared_task
        def my_task():
            do_stuff()


Implementation notes
--------------------

In case of a ``ZODB.POSException.ConflictError`` the worker process will wait
and restart the operation again. This is done with active wait
(``time.sleep()``) and not via the ``self.retry()`` mechanism of celery, as we
were not able to figure out to get it flying.
