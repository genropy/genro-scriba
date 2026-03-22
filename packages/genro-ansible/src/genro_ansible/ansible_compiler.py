# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Ansible YAML compiler.

Extends YamlCompilerBase with Ansible-specific rendering:
- Output is a list of plays (not a dict)
- Tasks render as: {name: ..., <module>: {<args>}}
- Handlers render identically to tasks but under 'handlers' key

Ansible playbook YAML format:
    - name: Play 1
      hosts: all
      tasks:
        - name: Install nginx
          apt:
            name: nginx
            state: present
"""

from __future__ import annotations

from typing import Any

from genro_scriba.yaml_compiler import YamlCompilerBase


class AnsibleCompiler(YamlCompilerBase):
    """Compiler for AnsibleBuilder — list-of-plays YAML output."""

    def compile_to_dict(self, root_node: Any, builder: Any) -> dict[str, Any]:
        """Compile playbook to a dict with _plays list."""
        return super().compile_to_dict(root_node, builder)

    def to_play_list(self, yaml_dict: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the list of plays from compiled dict."""
        return yaml_dict.get("_plays", [])


_compiler = AnsibleCompiler()


def compile_to_dict(root_node: Any, builder: Any) -> dict[str, Any]:
    """Compile a BagNode (the playbook root) to a dict with _plays."""
    return _compiler.compile_to_dict(root_node, builder)


def render_attrs(node: Any, builder: Any) -> dict[str, Any]:
    """Render node attributes + children into a dict."""
    return _compiler.render_attrs(node, builder)
