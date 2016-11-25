from .celery import CELERY

# Export decorator, so client modules can simply say `@z3c.celery.task()`.
task = CELERY.task

# We do not want to expose the app here.
del CELERY
