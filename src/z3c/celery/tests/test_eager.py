import celery.result
import pytest
import unittest
import z3c.celery.layer


@z3c.celery.task
def echo_task(text):
    return text


@z3c.celery.task
def provoke_error_task():
    raise RuntimeError('provoked')


class EagerLayerTest(unittest.TestCase):

    layer = z3c.celery.layer.EAGER_LAYER

    def test_async_result_works_in_eager_mode(self):
        job = echo_task.delay('foo')
        result = celery.result.AsyncResult(job.id)
        assert 'foo' == result.get()

    def test_async_result_raises_in_eager_mode(self):
        with pytest.raises(RuntimeError):
            job = provoke_error_task.delay()
            result = celery.result.AsyncResult(job.id)
            with pytest.raises(RuntimeError):
                result.get()
