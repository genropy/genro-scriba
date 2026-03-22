# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""TraefikApp - Application class for building Traefik v3 configurations.

Follows the standard genro-bag App pattern:
    1. Create a Bag with TraefikBuilder
    2. Populate via recipe(root) — structure with optional ^ pointers to data
    3. Compile to YAML with to_yaml()

The recipe defines the STRUCTURE (what routers, services, middlewares exist).
The data Bag holds the VALUES (ports, hostnames, IPs, credentials).

Attribute values starting with ^ are pointers to self.data paths.
At compile time the compiler resolves them to actual values.

If output is set, any change to self.data triggers recompile and save —
making it a live control plane for Traefik (with file provider watch=True).

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
from typing import Any

from genro_bag import Bag

from .builders.traefik_builder import TraefikBuilder
from .traefik_compiler import compile_to_dict


class TraefikApp:
    """Base class for Traefik v3 configuration applications.

    Subclass and override recipe(root) to define your configuration.
    Call to_yaml() to generate the YAML output.
    Call check() to validate the structure.

    Args:
        name: Root element name.
        output: Optional file path. If set, every data change triggers
            recompile and write to this path.
    """

    def __init__(self, name: str = "traefik",
                 output: str | Path | None = None) -> None:
        self._store = Bag(builder=TraefikBuilder)
        self._data: Bag = Bag()
        self._store.builder.data = self._data
        self._output = Path(output) if output else None
        self._auto_compile = False
        self._root = self._store.traefik(name=name)
        self.recipe(self._root)
        self._setup_data_trigger()

    @property
    def store(self) -> Bag:
        """The root Bag containing the configuration."""
        return self._store

    @property
    def root(self) -> Any:
        """The traefik root BagNode (returned by traefik() element)."""
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
            "traefik_app_auto_compile",
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
        """Override to build your Traefik configuration.

        Use ^ prefix on attribute values to reference self.data paths.
        Example: root.entryPoint(name="web", address="^web.address")
        """

    def to_yaml(self, destination: str | Path | None = None) -> str:
        """Compile the configuration to YAML, resolving ^ pointers.

        Args:
            destination: Optional file path. If provided, writes YAML
                to the file and returns the YAML string.

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
