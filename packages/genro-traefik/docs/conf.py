# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Sphinx configuration for Genro Traefik documentation."""

import sys
from pathlib import Path

# Add source directory to path for autodoc
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Read version from pyproject.toml (single source of truth)
try:
    import tomllib

    with open(Path(__file__).parent.parent / "pyproject.toml", "rb") as f:
        _pyproject = tomllib.load(f)
    release = _pyproject["project"]["version"]
except Exception:
    release = "0.0.0"
version = ".".join(release.split(".")[:2])

# Project information
project = "Genro Traefik"
copyright = "2025, Softwell S.r.l."
author = "Genropy Team"

# General configuration
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "sphinx.ext.todo",
    "sphinx.ext.coverage",
    "sphinx.ext.githubpages",
    "sphinx_autodoc_typehints",
    "myst_parser",
    "sphinxcontrib.mermaid",
]

# MyST Parser configuration (Markdown)
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3
myst_fence_as_directive = ["mermaid"]

# Source files
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}
master_doc = "index"

exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
]

# HTML output
html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "navigation_depth": 4,
    "collapse_navigation": False,
    "sticky_navigation": True,
    "includehidden": True,
    "titles_only": False,
    "prev_next_buttons_location": "bottom",
    "style_external_links": True,
    "logo_only": False,
    "vcs_pageview_mode": "blob",
}

html_static_path = ["_static"]
html_css_files = []

html_context = {
    "display_github": True,
    "github_user": "genropy",
    "github_repo": "genro-traefik",
    "github_version": "main",
    "conf_py_path": "/docs/",
}

# Autodoc
autodoc_default_options = {
    "members": True,
    "member-order": "bysource",
    "special-members": "__init__",
    "undoc-members": True,
    "exclude-members": "__weakref__",
}
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

# Napoleon (Google-style docstrings)
napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_use_admonition_for_examples = True
napoleon_use_admonition_for_notes = True
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_attr_annotations = True

# Intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

# Todo
todo_include_todos = True

# Type hints
typehints_fully_qualified = False
always_document_param_types = True
typehints_document_rtype = True
