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
