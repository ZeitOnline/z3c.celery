from ..logging import TaskFormatter
from .shared_tasks import shared_logging_task
import logging
import pytest
import tempfile
import transaction
import uuid


@pytest.fixture(scope='function')
def logger_and_stream():
    """Return a logger and the stream it writes to."""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    from io import StringIO
    logged = StringIO()
    handler = logging.StreamHandler(logged)
    handler.setFormatter(
        TaskFormatter('task_id: %(task_id)s name: %(task_name)s %(message)s'))
    logger.addHandler(handler)

    yield (logger, logged)

    logger.removeHandler(handler)


def test_logging__TaskFormatter__format__1(logger_and_stream):
    """It provides task_id and task_name, which are empty if there is none."""

    log, logged = logger_and_stream
    log.debug("We have no task.")

    assert 'task_id:  name:  We have no task.\n' == logged.getvalue()


def test_logging__TaskFormatter__format__2(celery_session_worker):
    """It provides task_id and task_name in async mode."""

    task_id = '<task_id_{}>'.format(uuid.uuid4())
    with tempfile.NamedTemporaryFile(delete=False) as logfile:
        result = shared_logging_task.apply_async(
            (logfile.name,), task_id=task_id)
        transaction.commit()

        assert "Successful logged." == result.get()
        logfile.seek(0)
        log_result = logfile.read().decode('utf-8')
        assert ('task_id: {} '
                'name: z3c.celery.tests.shared_tasks.shared_logging_task '
                'we are logging'.format(task_id) in log_result)
        assert "__traceback_info__: we can handle traceback info" in log_result
        assert "NotImplementedError" in log_result
