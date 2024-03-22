=========================
Change log for z3c.celery
=========================

1.7.0 (2024-03-22)
==================

- Added support for Python 3.12


1.6.0 (2022-06-23)
==================

- Update to celery 5.x, drop Python-2 support


1.5.0 (2021-11-15)
==================

- Provide JsonFormatter if python-json-logger is installed


1.4.3 (2021-02-26)
==================

- Fix logging setup


1.4.2 (2019-12-12)
==================

- Make HandleAfterAbort compatible with celery-4.1.1 serialization changes


1.4.1 (2019-11-15)
==================

- Annotate transaction with principal and task name, like zope.app.publication


1.4.0 (2019-10-30)
==================

- Set the URL of the (fake) zope request (which is used to set the principal) to
  the task name


1.3.0 (2019-05-22)
==================

- Added support for Python 3.6 and 3.7.


1.2.3 (2018-06-28)
==================

- Add logging for task retry.


1.2.2 (2018-03-23)
==================

- Ensure ZODB connection can be closed, even if execution is aborted in the
  middle of a transaction


1.2.1 (2018-02-02)
==================

- Add bw-compat for persisted tasks that still have a `_task_id_` parameter


1.2.0 (2018-01-23)
==================

- Support task retry


1.1.0 (2017-10-11)
==================

- Make worker process boot timeout configurable


1.0.2 (2017-10-05)
==================

- Also apply "always endInteration" to HandleAfterAbort

- Also apply "retry on ConflictError" to HandleAfterAbort


1.0.1 (2017-10-04)
==================

- Always call endInteraction, even on error during commit or abort,
  so we don't pollute the interaction state for the next task run


1.0 (2017-09-29)
================

- Introduce ``Abort`` control flow exception

- Allow overriding the principal id the job runs as

- Support reading configuration from a filesystem-based (non-importable) python file

- Don't use celery's deprecated default app mechanism

- Support running an actual "celery worker" with the single-process "solo" worker_pool


0.1 (2017-02-21)
================

- Initial release. Extract from zeit.cms.
