# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""ScribaApp — Unified infrastructure configuration with shared data.

ScribaApp coordinates multiple builders (Traefik, Compose, etc.) that
share a single data Bag. When a data value changes, only the builders
that actually use that value (via ^ pointers) are recompiled.

Each builder tracks which ^pointer paths it resolved during compilation.
On data change, the app checks each builder's dependency set before
triggering a recompile.

Example:
    from genro_scriba import ScribaApp

    class MyInfra(ScribaApp):
        def traefik_recipe(self, root):
            root.entryPoint(name="web", address="^web.port")
            ...

        def compose_recipe(self, root):
            root.service(name="db", image="postgres",
                         environment={"HOST": "^db.host"})
            ...

    infra = MyInfra(
        traefik_output="/etc/traefik/traefik.yml",
        compose_output="docker-compose.yml",
    )
    infra.data["web.port"] = ":80"    # recompiles only traefik
    infra.data["db.host"] = "10.0.1.5"  # recompiles only compose
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from genro_bag import Bag
from genro_builders import BuilderBag


class _BuilderSlot:
    """Internal: holds one builder's store, root, compiler, and dependencies."""

    def __init__(self, builder_class: type, root_tag: str,
                 compiler_module: Any, compiler_class: type,
                 output: Path | None) -> None:
        self.store = BuilderBag(builder=builder_class)
        self.root_tag = root_tag
        self.compiler = compiler_module
        self._bag_compiler = compiler_class(self.store.builder)
        self.output = output
        self.root: Any = None
        self._data: Bag | None = None
        self.resolved_paths: set[str] = set()

    def bind_data(self, data: Bag) -> None:
        """Point the builder's data reference to the shared Bag."""
        self.store.builder.data = data
        self._data = data

    def init_root(self, name: str | None = None) -> Any:
        """Create the root element."""
        root_method = getattr(self.store, self.root_tag)
        self.root = root_method(name=name or self.root_tag)
        return self.root

    def compile_to_dict(self) -> dict[str, Any]:
        """Compile (materialize + resolve pointers) then walk to dict."""
        self.resolved_paths.clear()
        compiled_bag = self._bag_compiler.compile(self.store, self._data)
        compiled_nodes = list(compiled_bag)
        if not compiled_nodes:
            return {}
        result = self.compiler.compile_to_dict(compiled_nodes[0], self.store.builder)
        self.resolved_paths = _collect_resolved_paths(compiled_nodes[0])
        return result

    def depends_on(self, changed_path: str) -> bool:
        """Check if this builder depends on the changed data path."""
        if not self.resolved_paths:
            return True
        return changed_path in self.resolved_paths

    def to_yaml(self, yaml_dict: dict[str, Any],
                destination: Path | None = None) -> str:
        """Serialize dict to YAML and optionally write to file."""
        yaml_str = yaml.dump(
            yaml_dict,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
        dest = destination or self.output
        if dest:
            Path(dest).write_text(yaml_str, encoding="utf-8")
        return yaml_str


def _collect_resolved_paths(root_node: Any) -> set[str]:
    """Walk the tree and collect all ^pointer paths used in attributes."""
    paths: set[str] = set()
    _walk_for_pointers(root_node, paths)
    return paths


def _walk_for_pointers(node: Any, paths: set[str]) -> None:
    """Recursively collect ^pointer paths from node attributes."""
    if hasattr(node, "attr"):
        for _name, value in node.attr.items():
            _extract_pointer_paths(value, paths)
    node_value = node.get_value(static=True) if hasattr(node, "get_value") else None
    if isinstance(node_value, Bag):
        for child in node_value:
            _walk_for_pointers(child, paths)


def _extract_pointer_paths(value: Any, paths: set[str]) -> None:
    """Extract ^pointer paths from a value (recursing into lists and dicts)."""
    if isinstance(value, str) and value.startswith("^"):
        paths.add(value[1:])
    elif isinstance(value, list):
        for item in value:
            _extract_pointer_paths(item, paths)
    elif isinstance(value, dict):
        for v in value.values():
            _extract_pointer_paths(v, paths)


class ScribaApp:
    """Unified infrastructure app with shared data and selective recompile.

    Subclass and override traefik_recipe() and/or compose_recipe().
    Set outputs for auto-save on data changes.
    """

    def __init__(self,
                 traefik_output: str | Path | None = None,
                 compose_output: str | Path | None = None,
                 data: Bag | dict[str, Any] | None = None) -> None:
        self._data: Bag = Bag()
        self._auto_compile = False
        self._slots: dict[str, _BuilderSlot] = {}

        self._init_traefik(traefik_output)
        self._init_compose(compose_output)

        for slot in self._slots.values():
            slot.bind_data(self._data)

        traefik_slot = self._slots.get("traefik")
        if traefik_slot:
            traefik_slot.init_root()
            self.traefik_recipe(traefik_slot.root)

        compose_slot = self._slots.get("compose")
        if compose_slot:
            compose_slot.init_root()
            self.compose_recipe(compose_slot.root)

        for slot in self._slots.values():
            slot.compile_to_dict()

        if data is not None:
            self.data = data

        self._setup_data_trigger()

    def _init_traefik(self, output: str | Path | None) -> None:
        """Initialize Traefik builder slot."""
        try:
            from genro_traefik import traefik_compiler
            from genro_traefik.builders.traefik_builder import TraefikBuilder
            from genro_traefik.traefik_compiler import TraefikCompiler
            self._slots["traefik"] = _BuilderSlot(
                TraefikBuilder, "traefik", traefik_compiler, TraefikCompiler,
                Path(output) if output else None,
            )
        except ImportError:
            pass

    def _init_compose(self, output: str | Path | None) -> None:
        """Initialize Compose builder slot."""
        try:
            from genro_compose import compose_compiler
            from genro_compose.builders.compose_builder import ComposeBuilder
            from genro_compose.compose_compiler import ComposeCompiler
            self._slots["compose"] = _BuilderSlot(
                ComposeBuilder, "compose", compose_compiler, ComposeCompiler,
                Path(output) if output else None,
            )
        except ImportError:
            pass

    # --- Data ---

    @property
    def data(self) -> Bag:
        """The shared data Bag. Values referenced by ^ pointers."""
        return self._data

    @data.setter
    def data(self, value: Bag | dict[str, Any]) -> None:
        """Replace the data Bag."""
        if isinstance(value, dict):
            new_bag: Bag = Bag()
            new_bag.fill_from(value)
            self._data = new_bag
        else:
            self._data = value
        for slot in self._slots.values():
            slot.bind_data(self._data)
        self._setup_data_trigger()
        self._recompile_all()

    # --- Recipes (override in subclass) ---

    def traefik_recipe(self, root: Any) -> None:
        """Override to build the Traefik configuration."""

    def compose_recipe(self, root: Any) -> None:
        """Override to build the Docker Compose configuration."""

    # --- Output ---

    def to_yaml(self, builder_name: str,
                destination: str | Path | None = None) -> str:
        """Compile a specific builder to YAML."""
        slot = self._slots.get(builder_name)
        if slot is None:
            msg = f"Builder '{builder_name}' not available"
            raise ValueError(msg)
        yaml_dict = slot.compile_to_dict()
        return slot.to_yaml(yaml_dict, Path(destination) if destination else None)

    def to_yaml_all(self) -> dict[str, str]:
        """Compile all builders to YAML."""
        result = {}
        for name, slot in self._slots.items():
            yaml_dict = slot.compile_to_dict()
            result[name] = slot.to_yaml(yaml_dict)
        return result

    # --- Selective recompile ---

    def _setup_data_trigger(self) -> None:
        """Subscribe to data changes for selective recompile."""
        self._data.subscribe(
            "scriba_app_auto_compile",
            any=self._on_data_changed,
        )
        self._auto_compile = True

    def _on_data_changed(self, node: Any = None, pathlist: list | None = None,
                         **_kwargs: Any) -> None:
        """Callback on data change: recompile only affected builders."""
        if not self._auto_compile:
            return
        changed_path = ".".join(pathlist) if pathlist else ""
        for _name, slot in self._slots.items():
            if slot.output and slot.depends_on(changed_path):
                yaml_dict = slot.compile_to_dict()
                slot.to_yaml(yaml_dict)

    def _recompile_all(self) -> None:
        """Force recompile all builders."""
        for slot in self._slots.values():
            if slot.output:
                yaml_dict = slot.compile_to_dict()
                slot.to_yaml(yaml_dict)
