# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""ComposeApp - Application class for building Docker Compose configurations.

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
from typing import Any

from genro_bag import Bag

from .builders.compose_builder import ComposeBuilder
from .compose_compiler import compile_to_dict


class ComposeApp:
    """Docker Compose configuration application.

    Subclass and override recipe(root) to define your stack.
    Call to_yaml() to generate the YAML output.
    """

    def __init__(self, name: str = "compose",
                 output: str | Path | None = None) -> None:
        self._store = Bag(builder=ComposeBuilder)
        self._data: Bag = Bag()
        self._store.builder.data = self._data
        self._output = Path(output) if output else None
        self._auto_compile = False
        self._root = self._store.compose(name=name)
        self.recipe(self._root)
        self._setup_data_trigger()

    @property
    def store(self) -> Bag:
        """The root Bag containing the configuration."""
        return self._store

    @property
    def root(self) -> Any:
        """The compose root BagNode."""
        return self._root

    @property
    def data(self) -> Bag:
        """The data Bag. Values referenced by ^ pointers in the recipe."""
        return self._data

    @data.setter
    def data(self, value: Bag | dict[str, Any]) -> None:
        """Replace the data Bag. Accepts a Bag or dict."""
        if isinstance(value, dict):
            new_bag: Bag = Bag()
            new_bag.fill_from(value)
            self._data = new_bag
        else:
            self._data = value
        self._store.builder.data = self._data
        self._setup_data_trigger()
        self._on_data_changed()

    @property
    def output(self) -> Path | None:
        """The output file path for auto-save."""
        return self._output

    @output.setter
    def output(self, value: str | Path | None) -> None:
        self._output = Path(value) if value else None

    def _setup_data_trigger(self) -> None:
        """Subscribe to data changes for auto-compile."""
        self._data.subscribe(
            "compose_auto_compile",
            any=self._on_data_changed,
        )
        self._auto_compile = True

    def _on_data_changed(self, *_args: Any, **_kwargs: Any) -> None:
        """Callback on data change: recompile and save if output is set."""
        if not self._auto_compile:
            return
        if self._output:
            self.to_yaml(self._output)

    def recipe(self, root: Any) -> None:
        """Override to build your Docker Compose configuration."""

    def to_yaml(self, destination: str | Path | None = None) -> str:
        """Compile the configuration to YAML.

        Returns:
            YAML string.
        """
        try:
            import yaml
        except ImportError as e:
            msg = "PyYAML required: pip install pyyaml"
            raise ImportError(msg) from e

        yaml_dict = compile_to_dict(self._root, self._store.builder)

        yaml_str = yaml.dump(
            yaml_dict,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        dest = destination or self._output
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
        results = self._store.builder.check(check_target)
        errors: list[str] = []
        for path, _node, reasons in results:
            for reason in reasons:
                errors.append(f"{path}: {reason}")
        return errors
