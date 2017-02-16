from __future__ import absolute_import
import celery.loaders.app
import celery.signals
import logging.config
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
            logging.config.fileConfig(config_file, dict(
                __file__=config_file, here=os.path.dirname(config_file)))

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
