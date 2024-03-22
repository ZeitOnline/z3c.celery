import celery.concurrency.asynpool
import celery.loaders.app
import celery.signals
import celery.utils.collections
import logging.config
import types
import os.path
import zope.app.wsgi


class ZopeLoader(celery.loaders.app.AppLoader):
    """Sets up the Zope environment in the Worker processes."""

    def on_worker_init(self):
        logging_ini = self.app.conf.get('LOGGING_INI')
        if not logging_ini:
            return

        @celery.signals.setup_logging.connect(weak=False)
        def setup_logging(*args, **kw):
            """Make the loglevel finely configurable via a config file."""
            config_file = os.path.abspath(logging_ini)
            logging.config.fileConfig(
                config_file, dict(
                    __file__=config_file, here=os.path.dirname(config_file)),
                disable_existing_loggers=False)

        if self.app.conf.get('DEBUG_WORKER'):
            assert self.app.conf.get('worker_pool') == 'solo'
            self.on_worker_process_init()

        # Work around <https://github.com/celery/celery/issues/4323>.
        if self.app.conf.get('worker_boot_timeout'):
            celery.concurrency.asynpool.PROC_ALIVE_TIMEOUT = float(
                self.app.conf['worker_boot_timeout'])

    def on_worker_process_init(self):
        conf = self.app.conf
        configfile = conf.get('ZOPE_CONF')
        if not configfile:
            raise ValueError(
                'Celery setting ZOPE_CONF not set, '
                'check celery worker config.')

        db = zope.app.wsgi.config(configfile)
        conf['ZODB'] = db

    def on_worker_shutdown(self):
        if 'ZODB' in self.app.conf:
            self.app.conf['ZODB'].close()

    def read_configuration(self):
        """Read configuration from either

        * an importable python module, given by its dotted name in
          CELERY_CONFIG_MODULE. Note that this can also be set via
          `$ bin/celery worker --config=<modulename>`. (Also note that "celery
          worker" includes the cwd on the pythonpath.)
        * or a plain python file (given by an absolute path in
          CELERY_CONFIG_FILE)

        If neither env variable is present, no configuration is read, and some
        defaults are used instead that most probably don't work (they assume
        amqp on localhost as broker, for example).
        """
        module = os.environ.get('CELERY_CONFIG_MODULE')
        if module:
            return super().read_configuration()
        pyfile = os.environ.get('CELERY_CONFIG_FILE')
        if pyfile:
            module = self._import_pyfile(pyfile)
            return celery.utils.collections.DictAttribute(module)

    def _import_pyfile(self, filename):
        """Applies Celery configuration by reading the given python file
        (absolute filename), which unfortunately Celery does not support.

        (Code inspired by flask.config.Config.from_pyfile)
        """
        module = types.ModuleType('config')
        module.__file__ = filename
        try:
            with open(filename) as config_file:
                exec(compile(
                    config_file.read(), filename, 'exec'), module.__dict__)
        except IOError as e:
            e.strerror = 'Unable to load configuration file (%s)' % e.strerror
            raise e
        else:
            return module
