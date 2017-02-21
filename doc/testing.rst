Running the tests
=================

To run the test suite you need a ``redis-server`` listening on the default
port. The tests use the redis database ``/12``, which means that no other
celery worker should be connected to that database and this database should not
be used for other purposes.

To run the actual tests, simply run `tox`_ in the package root directory.

Together with the tests, this documentation will be build by `tox`_.

.. _`tox` : https://tox.readthedocs.io/en/latest/
