# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""YAML compiler layer for Bag-based configuration builders.

Extends BagCompilerBase (which handles component expansion and ^pointer
resolution) with YAML-specific rendering: walk a compiled Bag tree and
produce a dict suitable for yaml.dump().

For each node with tag T, calls builder.compile_T(node, result).
If no compile method exists, falls back to compile_default
(tag as key, attrs + children as value).

Subclasses override _render_attr_entry() for tool-specific attribute
rendering (e.g. Traefik nests underscored attrs, Compose keeps them flat).
"""

from __future__ import annotations

import copy
from typing import Any

from genro_bag import Bag
from genro_builders import BagCompilerBase


class YamlCompilerBase(BagCompilerBase):
    """YAML compiler — walk a compiled Bag and produce a dict.

    BagCompilerBase handles: component expansion, ^pointer resolution.
    This class handles: walk-to-dict, compile_TAG dispatch, attr rendering.
    """

    def __init__(self, builder: Any = None) -> None:
        if builder is not None:
            super().__init__(builder)
        else:
            self.builder = None
            self._compile_handlers = dict(type(self)._class_compile_handlers)

    def compile_to_dict(self, root_node: Any, builder: Any) -> dict[str, Any]:
        """Compile a BagNode root to a YAML-compatible dict."""
        root_value = root_node.value if hasattr(root_node, "value") else root_node
        if not isinstance(root_value, Bag):
            return {}
        return self.walk(root_value, builder)

    def walk(self, bag: Bag, builder: Any) -> dict[str, Any]:
        """Walk a Bag and compile each child node."""
        result: dict[str, Any] = {}
        for node in bag:
            tag = node.node_tag or node.label
            method = self._get_compile_method(builder, tag)
            if method:
                method(node, result)
            else:
                self.compile_default(node, result, builder)
        return result

    def compile_default(self, node: Any, result: dict[str, Any],
                        builder: Any) -> None:
        """Default: use tag as YAML key, dump attrs + children."""
        tag = node.node_tag or node.label
        content = self.render_attrs(node, builder)
        result[tag] = content

    def render_attrs(self, node: Any, builder: Any) -> dict[str, Any]:
        """Render node attributes + children into a dict."""
        result: dict[str, Any] = {}

        for attr_name, attr_value in node.attr.items():
            if attr_name.startswith("_") or attr_name in ("name", "datapath"):
                continue
            if attr_value is None:
                continue
            if isinstance(attr_value, (dict, list)):
                attr_value = copy.deepcopy(attr_value)
            self._render_attr_entry(attr_name, attr_value, result)

        # Children
        node_value = node.get_value(static=True)
        if isinstance(node_value, Bag):
            children = self.walk(node_value, builder)
            result.update(children)

        return result

    def _render_attr_entry(self, attr_name: str, value: Any,
                           result: dict[str, Any]) -> None:
        """Add one attribute to the result dict.

        Override in subclasses for tool-specific rendering.
        Default: flat key = value (suitable for Compose / snake_case tools).
        """
        result[attr_name] = self._to_yaml_value(value)

    def _get_compile_method(self, builder: Any, tag: str) -> Any:
        """Find compile_TAG on the builder, bypassing __getattr__."""
        for cls in type(builder).__mro__:
            method = cls.__dict__.get(f"compile_{tag}")
            if method is not None:
                return method.__get__(builder)
        return None

    def _to_yaml_value(self, value: Any) -> Any:
        """Convert Python value to YAML-friendly value."""
        if isinstance(value, list):
            return value
        if isinstance(value, str) and "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return value
