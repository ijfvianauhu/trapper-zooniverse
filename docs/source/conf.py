import os
import sys
sys.path.insert(0, os.path.abspath('../../trapper_zooniverse'))

project = 'Tapper Zooniverse'
copyright = '2025, WildIntel project'
author = 'Iñaki Fernández de Viana y González'

extensions = [
    'sphinx.ext.autodoc',
    'sphinx_autodoc_typehints',
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

html_theme = 'alabaster'
html_static_path = ['_static']  

extensions.append('recommonmark')
