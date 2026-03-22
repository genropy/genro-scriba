# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Docker Compose YAML compiler.

Extends CompilerBase with default (flat) attribute rendering.
Docker Compose uses snake_case natively — no underscore nesting needed.
"""

from __future__ import annotations

from typing import Any

from genro_scriba.yaml_compiler import YamlCompilerBase


class ComposeCompiler(YamlCompilerBase):
    """Compiler for ComposeBuilder — flat attribute rendering."""


_compiler = ComposeCompiler()


# Module-level functions for backward compatibility with ComposeApp / builder
def compile_to_dict(root_node: Any, builder: Any) -> dict[str, Any]:
    """Compile a BagNode (the compose root) to a YAML-compatible dict."""
    return _compiler.compile_to_dict(root_node, builder)


def walk(bag: Any, builder: Any) -> dict[str, Any]:
    """Walk a Bag and compile each child node."""
    return _compiler.walk(bag, builder)


def compile_default(node: Any, result: dict[str, Any], builder: Any) -> None:
    """Default: use tag as YAML key, dump attrs + children."""
    _compiler.compile_default(node, result, builder)


def render_attrs(node: Any, builder: Any) -> dict[str, Any]:
    """Render node attributes + children into a dict."""
    return _compiler.render_attrs(node, builder)
