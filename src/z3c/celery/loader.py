from __future__ import absolute_import
import celery.loaders.app
import zope.app.wsgi


class ZopeLoader(celery.loaders.app.AppLoader):
    """Sets up the Zope environment in the Worker processes."""

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
