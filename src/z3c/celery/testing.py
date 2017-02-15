import ZODB
import ZODB.FileStorage
import contextlib
import os
import shutil


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


@contextlib.contextmanager
def open_zodb_copy(zodb_path):
    """Context manager which opens a copy of the given ZODB.

    This might be useful if the actual ZODB is still opened by another process.
    Yields the application object inside the ZODB.
    """
    new_zodb_path = zodb_path + '.copy'
    shutil.copy(zodb_path, new_zodb_path)
    zodbDB = ZODB.DB(ZODB.FileStorage.FileStorage(file_name=new_zodb_path))
    connection = zodbDB.open()
    try:
        yield connection.root()['Application']
    finally:
        connection.close()
        zodbDB.close()
        os.unlink(new_zodb_path)
