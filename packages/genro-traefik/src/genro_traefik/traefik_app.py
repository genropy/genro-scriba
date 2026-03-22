# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""TraefikApp - Application class for building Traefik v3 configurations.

Extends BagAppBase with YAML rendering. BagAppBase handles:
    - BuilderBag creation and lifecycle
    - Component expansion (materialize)
    - ^pointer resolution and reactive binding
    - Auto-recompile on data changes

TraefikApp adds:
    - Root traefik node creation
    - recipe(root) API for subclasses
    - to_yaml() rendering via TraefikCompiler walk-to-dict + yaml.dump
    - check() validation
    - File output on data changes

Example:
    from genro_traefik import TraefikApp

    class MyProxy(TraefikApp):
        def recipe(self, root):
            root.entryPoint(name="web", address="^web.address")
            http = root.http()
            r = http.routers().router(
                name="api", rule="^api.rule", service="api-svc",
                entryPoints=["web"])
            svc = http.services().service(name="api-svc")
            lb = svc.loadBalancer()
            lb.server(url="^api.backend")

    proxy = MyProxy(output="/etc/traefik/dynamic.yml")
    proxy.data["web.address"] = ":80"
    proxy.data["api.rule"] = "Host(`api.example.com`)"
    proxy.data["api.backend"] = "http://localhost:8080"
    # → auto-compiles and writes to /etc/traefik/dynamic.yml
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from genro_builders import BagAppBase

if TYPE_CHECKING:
    from genro_bag import Bag

from .builders.traefik_builder import TraefikBuilder
from .traefik_compiler import TraefikCompiler


class TraefikApp(BagAppBase):
    """Base class for Traefik v3 configuration applications.

    Subclass and override recipe(root) to define your configuration.
    Call to_yaml() to generate the YAML output.
    Call check() to validate the structure.
    """

    builder_class = TraefikBuilder
    compiler_class = TraefikCompiler

    def __init__(self, name: str = "traefik",
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
        """The traefik root BagNode."""
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
        self._root = self.store.traefik(name=self._name)
        self.recipe(self._root)
        self.compile()
        self._auto_compile = True

    def recipe(self, root: Any) -> None:
        """Override to build your Traefik configuration.

        Use ^ prefix on attribute values to reference self.data paths.
        Example: root.entryPoint(name="web", address="^web.address")
        """

    def render(self, compiled_bag: Bag) -> str:
        """Render compiled Bag to YAML string via walk-to-dict."""
        compiler = TraefikCompiler()
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
        self.compile()
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
