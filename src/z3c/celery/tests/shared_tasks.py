from celery import shared_task
import zope.security.management
import logging
from ..logging import TaskFormatter


@shared_task
def get_principal_title_task():
    """Task returning the principal's title used to run it."""
    interaction = zope.security.management.getInteraction()
    return interaction.participations[0].principal.title


def log_exception(filename):
    """Common part for logging tasks."""
    log = logging.getLogger(__name__)
    log.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename)
    handler.setFormatter(
        TaskFormatter('task_id: %(task_id)s name: %(task_name)s %(message)s'))
    log.addHandler(handler)

    __traceback_info__ = ('we can handle traceback info')
    try:
        raise NotImplementedError()
    except NotImplementedError:
        log.error('we are logging', exc_info=True)
    handler.flush()
    handler.close()
    return "Successful logged."


@shared_task(bind=True)
def shared_logging_task(self, filename):
    return log_exception(filename)
