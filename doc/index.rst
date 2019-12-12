z3c.celery
==========

Integration of Celery 4 with Zope 3.

This package is compatible with Python version 2.7, 3.6 and 3.7.

Features
--------

* integration into the Zope transaction (schedule tasks at
  ``transaction.commit()``)
* runs jobs

  * in a Zope environment with loaded ZCML and ZODB connection
  * in a transaction with retry on `ConflictError`
  * as the user who scheduled the job
* test infrastructure to run tests in-line or in a worker
* support for py.test fixtures and zope.testrunner layers

.. toctree::
    :maxdepth: 2

    usage
    testing
    api
    about
    changes


- :ref:`genindex`
