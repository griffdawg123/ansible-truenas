# Copyright (c) Ansible Project
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

# This file only contains a selection of the most common options. For a full list see the
# documentation:
# http://www.sphinx-doc.org/en/master/config

project = 'Ansible collections'
copyright = 'Ansible contributors'

title = 'Ansible Collections Documentation'
html_short_title = 'Ansible Collections Documentation'

extensions = ['sphinx.ext.autodoc', 'sphinx.ext.intersphinx', 'sphinx_antsibull_ext']

pygments_style = 'ansible'

highlight_language = 'YAML+Jinja'

html_theme = 'sphinx_ansible_theme'
html_show_sphinx = False

display_version = False

html_use_smartypants = True
html_use_modindex = False
html_use_index = False
html_copy_source = False

# See https://www.sphinx-doc.org/en/master/usage/extensions/intersphinx.html#confval-intersphinx_mapping for the syntax.
# Inventories are fetched live at build time; no local .inv fallbacks.
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'jinja2': ('https://jinja.palletsprojects.com/en/latest/', None),
    'ansible_devel': ('https://docs.ansible.com/ansible/devel/', None),
}

default_role = 'any'

nitpicky = True
