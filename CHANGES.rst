=========================
Change log for z3c.celery
=========================

1.1.0 (unreleased)
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
