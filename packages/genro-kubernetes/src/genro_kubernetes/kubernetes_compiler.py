# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Kubernetes YAML compiler.

Extends YamlCompilerBase with Kubernetes-specific rendering:
- Multi-document output (--- separator between resources)
- Resources collected in _resources list during walk, then rendered

Kubernetes manifests use snake_case in the builder but camelCase in YAML.
The compile_* methods on the builder handle the conversion directly.
"""

from __future__ import annotations

from typing import Any

from genro_scriba.yaml_compiler import YamlCompilerBase


class KubernetesCompiler(YamlCompilerBase):
    """Compiler for KubernetesBuilder — multi-document YAML output."""

    def compile_to_dict(self, root_node: Any, builder: Any) -> dict[str, Any]:
        """Compile manifest to a dict with _resources list."""
        return super().compile_to_dict(root_node, builder)

    def to_multi_document(self, yaml_dict: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract individual resource documents from compiled dict."""
        return yaml_dict.get("_resources", [])


_compiler = KubernetesCompiler()


def compile_to_dict(root_node: Any, builder: Any) -> dict[str, Any]:
    """Compile a BagNode (the manifest root) to a dict with _resources."""
    return _compiler.compile_to_dict(root_node, builder)


def walk(bag: Any, builder: Any) -> dict[str, Any]:
    """Walk a Bag and compile each child node."""
    return _compiler.walk(bag, builder)


def render_attrs(node: Any, builder: Any) -> dict[str, Any]:
    """Render node attributes + children into a dict."""
    return _compiler.render_attrs(node, builder)
