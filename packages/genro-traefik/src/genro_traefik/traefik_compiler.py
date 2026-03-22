# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Traefik YAML compiler.

Extends CompilerBase with Traefik-specific attribute rendering:
underscore in attr name → nested YAML (e.g. cookie_name → cookie.name).
"""

from __future__ import annotations

from typing import Any

from genro_scriba.compiler_base import CompilerBase


class TraefikCompiler(CompilerBase):
    """Compiler for TraefikBuilder — nests underscored attributes."""

    def _render_attr_entry(self, attr_name: str, resolved: Any,
                           result: dict[str, Any]) -> None:
        if "_" in attr_name:
            parts = attr_name.split("_", 1)
            result.setdefault(parts[0], {})[parts[1]] = self._to_yaml_value(resolved)
        else:
            result[attr_name] = self._to_yaml_value(resolved)


_compiler = TraefikCompiler()


# Module-level functions for backward compatibility with TraefikApp / builder
def compile_to_dict(root_node: Any, builder: Any) -> dict[str, Any]:
    """Compile a BagNode (the traefik root) to a YAML-compatible dict."""
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
