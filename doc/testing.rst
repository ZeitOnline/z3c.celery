Running the tests
=================

To run the test suite you need a ``redis-server`` listening on the default
port. The tests use the redis database ``/1``, which means that no other celery
worker should be connected to that database.

To run the actual tests, simply run `tox`_ in the package root directory.

.. _`tox`:https://tox.readthedocs.io/en/latest/

Together with the tests, this documentation will be build by `tox`_.
