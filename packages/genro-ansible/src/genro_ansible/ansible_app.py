# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""AnsibleApp - Application class for building Ansible playbooks.

Extends BagAppBase with list-of-plays YAML rendering.

Example:
    from genro_ansible import AnsibleApp

    class ServerSetup(AnsibleApp):
        def recipe(self, root):
            play = root.play(name="Setup", hosts="all", become=True)
            play.task(name="Install nginx", module="apt",
                      args={"name": "nginx", "state": "present"})

    app = ServerSetup()
    print(app.to_yaml())
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from genro_builders import BagAppBase

from .ansible_compiler import AnsibleCompiler
from .builders.ansible_builder import AnsibleBuilder

if TYPE_CHECKING:
    from genro_bag import Bag


class AnsibleApp(BagAppBase):
    """Base class for Ansible playbook applications.

    Subclass and override recipe(root) to define your playbook.
    Call to_yaml() to generate the YAML output.
    """

    builder_class = AnsibleBuilder
    compiler_class = AnsibleCompiler

    def __init__(self, name: str = "playbook",
                 output: str | Path | None = None,
                 data: Bag | dict[str, Any] | None = None) -> None:
        self._name = name
        self._file_output = Path(output) if output else None
        super().__init__()
        if data is not None:
            self.data = data
        self.setup()

    @property
    def root(self) -> Any:
        """The playbook root BagNode."""
        return self._root

    @property
    def file_output(self) -> Path | None:
        """The output file path for auto-save."""
        return self._file_output

    @file_output.setter
    def file_output(self, value: str | Path | None) -> None:
        self._file_output = Path(value) if value else None

    def setup(self) -> None:
        """Create root node, run recipe, compile, enable auto-compile."""
        self._root = self.store.playbook(name=self._name)
        self.recipe(self._root)
        self.compile()
        self._auto_compile = True

    def recipe(self, root: Any) -> None:
        """Override to build your Ansible playbook."""

    def render(self, compiled_bag: Bag) -> str:
        """Render compiled Bag to Ansible playbook YAML (list of plays)."""
        compiler = AnsibleCompiler()
        root_nodes = list(compiled_bag)
        if not root_nodes:
            return ""
        yaml_dict = compiler.compile_to_dict(root_nodes[0], self.store.builder)
        plays = compiler.to_play_list(yaml_dict)

        if not plays:
            return ""

        return yaml.dump(
            plays,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    def to_yaml(self, destination: str | Path | None = None) -> str:
        """Compile to YAML and optionally write to file.

        Returns:
            YAML string (list of plays).
        """
        self.compile()
        yaml_str = self.output or ""
        dest = destination or self._file_output
        if dest:
            Path(dest).write_text(yaml_str, encoding="utf-8")
        return yaml_str

    def _on_node_updated(self, node: Any) -> None:
        """Called by BindingManager when a bound node is updated."""
        if self._auto_compile:
            self._rerender()
            if self._file_output:
                self.to_yaml()
