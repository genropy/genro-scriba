# Copyright 2025 Softwell S.r.l.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Sphinx configuration for Genro Scriba documentation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import tomllib

    with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as f:
        _pyproject = tomllib.load(f)
    release = _pyproject["project"]["version"]
except Exception:
    release = "0.0.0"
version = ".".join(release.split(".")[:2])

project = "Genro Scriba"
copyright = "2025, Softwell S.r.l."
author = "Genropy Team"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.doctest",
    "sphinx.ext.githubpages",
    "sphinx_autodoc_typehints",
    "myst_parser",
    "sphinxcontrib.mermaid",
]

myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3
myst_fence_as_directive = ["mermaid"]

source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

master_doc = "index"

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "temp",
]

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "display_version": True,
    "logo_only": False,
    "vcs_pageview_mode": "blob",
}

html_static_path = ["_static"]
html_css_files = []

html_context = {
    "display_github": True,
    "github_user": "genropy",
    "github_repo": "genro-scriba",
    "github_version": "main",
    "conf_py_path": "/docs/",
}

autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = True
napoleon_attr_annotations = True

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "genro-bag": ("https://genro-bag.readthedocs.io/en/latest/", None),
}

todo_include_todos = True
typehints_fully_qualified = False
always_document_param_types = True
typehints_document_rtype = True

linkcheck_anchors_ignore_for_url = [
    r"https://github\.com/genropy/genro-scriba/.*",
]
