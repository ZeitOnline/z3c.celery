import datetime
import os
import os.path
import shutil


author = 'gocept, Zeit Online'
_year_started = 2016
_year = datetime.date.today().year
if _year != _year_started:
    _year = u'%s-%s' % (_year_started, _year)
copyright = u' %s %s' % (_year, author)
source_suffix = '.rst'
master_doc = 'index'

needs_sphinx = '1.0'
extensions = [
    'sphinx.ext.autosummary',
    'sphinx.ext.autodoc',
    'sphinx.ext.viewcode',
]

templates_path = [
    '.',
]

html_sidebars = {
    '**': ['globaltoc.html', 'searchbox.html', 'project-links.html'],
}


# We use the autosummary extension to build API docs from source code.
# However, this extension doesn't update the generated docs if the source
# files change. Therefore, we need to remove the generated stuff before
# each run. The _autosummary_output variable tells the relative path to
# the directory that autosummary uses to put its generated files and which
# we, therefore, need to remove. It must be the same that the autosummary
# directive in api.rst points to.

autosummary_generate = ['api.rst']
_autosummary_output = './_api/'
if os.path.isdir(_autosummary_output):
    shutil.rmtree(_autosummary_output)
elif os.path.exists(_autosummary_output):
    raise RuntimeError('Expected %s to be a directory.' %
                       os.path.abspath(_autosummary_output))
os.mkdir(_autosummary_output)
