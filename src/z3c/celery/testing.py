import zope.publisher.browser
import zope.security.management


def login_principal(principal):
    """Start an interaction with `principal`."""
    request = zope.publisher.browser.TestRequest()
    request.setPrincipal(principal)
    zope.security.management.newInteraction(request)
