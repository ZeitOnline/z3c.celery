from ..session import celery_session, CeleryDataManager


def test_session__CeleryDataManager____repr____1():
    """It has a custom repr."""
    dm = CeleryDataManager(celery_session)
    assert repr(dm).startswith(
        '<z3c.celery.session.CeleryDataManager for <transaction')
