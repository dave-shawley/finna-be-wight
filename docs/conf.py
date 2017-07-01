import batcher

project = 'batch-server'
copyright = '2017, Dave Shawley'
release = '.'.join(str(c) for c in batcher.version_info[:2])
version = batcher.version
needs_sphinx = '1.0'
extensions = ['sphinx.ext.intersphinx',
              'sphinxcontrib.autotornado']

master_doc = 'index'
html_sidebars = {'**': ['about.html', 'navigation.html']}
intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'tornado': ('http://tornadoweb.org/en/branch4.5', None),
}
