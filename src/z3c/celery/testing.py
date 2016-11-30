import zope.publisher.browser
import zope.security.management


def login_principal(principal):
    """Start an interaction with `principal`."""
    request = zope.publisher.browser.TestRequest()
    request.setPrincipal(principal)
    zope.security.management.newInteraction(request)


ZOPE_CONF_TEMPLATE = """
site-definition {ftesting_path}

<zodb>
  <filestorage>
    path {zodb_path}
  </filestorage>
</zodb>

{product_config}

# eventlog is required :-(
<eventlog>
</eventlog>
"""
