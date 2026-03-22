# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Base compiler for Bag-based configuration builders.

Walks a Bag tree and produces a YAML-compatible dict. For each node
with tag T, calls builder.compile_T(). If no compile method exists,
falls back to compile_default (tag as key, attrs + children as value).

Supports ^ pointers resolved against builder.data:
    ^foo.bar       — absolute, resolved as data["foo.bar"]
    ^.bar          — relative, resolved from the node's datapath

Nodes can declare datapath="..." to set a data context.
Relative datapaths (leading dot) compose with ancestors:
    root(datapath="platform")
        child(datapath=".services")
            leaf(datapath=".api", rule="^.rule")
    → rule resolves as data["platform.services.api.rule"]

Subclasses override _render_attr_entry() for tool-specific attribute
rendering (e.g. Traefik nests underscored attrs, Compose keeps them flat).
"""

from __future__ import annotations

from typing import Any

from genro_bag import Bag


class CompilerBase:
    """Base compiler — walk, resolve, render."""

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
            tag = node.tag or node.label
            method = self._get_compile_method(builder, tag)
            if method:
                method(node, result)
            else:
                self.compile_default(node, result, builder)
        return result

    def compile_default(self, node: Any, result: dict[str, Any],
                        builder: Any) -> None:
        """Default: use tag as YAML key, dump attrs + children."""
        tag = node.tag or node.label
        content = self.render_attrs(node, builder)
        result[tag] = content

    def render_attrs(self, node: Any, builder: Any) -> dict[str, Any]:
        """Render node attributes + children into a dict."""
        data = getattr(builder, "data", None)
        datapath = self._resolve_datapath(node)
        result: dict[str, Any] = {}

        for attr_name, attr_value in node.attr.items():
            if attr_name.startswith("_") or attr_name in ("name", "datapath"):
                continue
            if attr_value is None:
                continue
            resolved = self._resolve(attr_value, data, datapath)
            self._render_attr_entry(attr_name, resolved, result)

        # Children
        node_value = node.get_value(static=True)
        if isinstance(node_value, Bag):
            children = self.walk(node_value, builder)
            result.update(children)

        return result

    def _render_attr_entry(self, attr_name: str, resolved: Any,
                           result: dict[str, Any]) -> None:
        """Add one resolved attribute to the result dict.

        Override in subclasses for tool-specific rendering.
        Default: flat key = value (suitable for Compose / snake_case tools).
        """
        result[attr_name] = self._to_yaml_value(resolved)

    def _get_compile_method(self, builder: Any, tag: str) -> Any:
        """Find compile_TAG on the builder, bypassing __getattr__."""
        for cls in type(builder).__mro__:
            method = cls.__dict__.get(f"compile_{tag}")
            if method is not None:
                return method.__get__(builder)
        return None

    def _resolve_datapath(self, node: Any) -> str:
        """Compose the datapath by walking up the ancestor chain."""
        parts: list[str] = []
        current = node
        while current:
            dp = current.attr.get("datapath", "") if hasattr(current, "attr") else ""
            if dp:
                parts.append(dp)
                if not dp.startswith("."):
                    break
            pb = getattr(current, "parent_bag", None)
            if pb and getattr(pb, "parent_node", None):
                current = pb.parent_node
            else:
                break
        parts.reverse()
        result = ""
        for p in parts:
            if p.startswith("."):
                result = result + "." + p[1:] if result else p[1:]
            else:
                result = p
        return result

    def _resolve(self, value: Any, data: Bag | None,
                 datapath: str = "") -> Any:
        """Resolve ^ pointers against the data Bag.

        ^path      — absolute, resolved as data[path]
        ^.path     — relative, resolved as data[datapath.path]
        """
        if data is None:
            return value
        if isinstance(value, str) and value.startswith("^"):
            path = value[1:]
            if path.startswith(".") and datapath:
                path = datapath + "." + path[1:]
            elif path.startswith("."):
                path = path[1:]
            resolved = data[path]
            return resolved if resolved is not None else value
        if isinstance(value, list):
            return [self._resolve(item, data, datapath) for item in value]
        if isinstance(value, dict):
            return {k: self._resolve(v, data, datapath)
                    for k, v in value.items()}
        return value

    def _to_yaml_value(self, value: Any) -> Any:
        """Convert Python value to YAML-friendly value."""
        if isinstance(value, list):
            return value
        if isinstance(value, str) and "," in value:
            return [v.strip() for v in value.split(",") if v.strip()]
        return value
