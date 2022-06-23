from celery._state import get_current_task
import zope.exceptions.log


class TaskId:

    def format(self, record):
        task = get_current_task()
        if task:
            record.__dict__.update(
                task_id=task.request.id,
                task_name=task.name)
        else:
            record.__dict__.setdefault('task_name', '')
            record.__dict__.setdefault('task_id', '')
        return super().format(record)


class TaskFormatter(TaskId, zope.exceptions.log.Formatter):
    """Provides `task_id` and `task_name` variables for the log format.

    We want to have a general formatter so we want to get rid of '???' which
    are rendered by celery.app.log.TaskFormatter. Also we inherit from
    zope.exceptions to support `__traceback_info__`.
    """


try:
    import pythonjsonlogger.jsonlogger
except ImportError:
    pass
else:
    class JsonFormatter(TaskId, pythonjsonlogger.jsonlogger.JsonFormatter):
        pass
