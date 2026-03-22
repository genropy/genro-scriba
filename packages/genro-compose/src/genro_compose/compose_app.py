# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""ComposeApp - Application class for building Docker Compose configurations.

Extends BagAppBase with YAML rendering. BagAppBase handles:
    - BuilderBag creation and lifecycle
    - Component expansion (materialize)
    - ^pointer resolution and reactive binding
    - Auto-recompile on data changes

Example:
    from genro_compose import ComposeApp

    class MyStack(ComposeApp):
        def recipe(self, root):
            web = root.service(name="web", image="nginx:alpine")
            web.port(published="80", target="80")

    stack = MyStack()
    print(stack.to_yaml())
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from genro_builders import BagAppBase

if TYPE_CHECKING:
    from genro_bag import Bag

from .builders.compose_builder import ComposeBuilder
from .compose_compiler import ComposeCompiler


class ComposeApp(BagAppBase):
    """Docker Compose configuration application.

    Subclass and override recipe(root) to define your stack.
    Call to_yaml() to generate the YAML output.
    """

    builder_class = ComposeBuilder
    compiler_class = ComposeCompiler

    def __init__(self, name: str = "compose",
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
        """The compose root BagNode."""
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
        self._root = self.store.compose(name=self._name)
        self.recipe(self._root)
        self.compile()
        self._auto_compile = True

    def recipe(self, root: Any) -> None:
        """Override to build your Docker Compose configuration."""

    def render(self, compiled_bag: Bag) -> str:
        """Render compiled Bag to YAML string via walk-to-dict."""
        compiler = ComposeCompiler()
        root_nodes = list(compiled_bag)
        if not root_nodes:
            return ""
        yaml_dict = compiler.compile_to_dict(root_nodes[0], self.store.builder)
        return yaml.dump(
            yaml_dict,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

    def to_yaml(self, destination: str | Path | None = None) -> str:
        """Compile to YAML and optionally write to file.

        Returns:
            YAML string.
        """
        yaml_str = self.output or ""
        dest = destination or self._file_output
        if dest:
            Path(dest).write_text(yaml_str, encoding="utf-8")
        return yaml_str

    def check(self) -> list[str]:
        """Validate the configuration structure.

        Returns:
            List of error messages (empty if valid).
        """
        check_target = (
            self._root.value
            if hasattr(self._root, "value") and self._root.value
            else self._root
        )
        results = self.store.builder.check(check_target)
        errors: list[str] = []
        for path, _node, reasons in results:
            for reason in reasons:
                errors.append(f"{path}: {reason}")
        return errors

    def _on_node_updated(self, node: Any) -> None:
        """Called by BindingManager when a bound node is updated."""
        if self._auto_compile:
            self._rerender()
            if self._file_output:
                self.to_yaml()
