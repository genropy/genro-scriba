# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""JugglerApp — reactive infrastructure bus.

Coordinates multiple builder slots, each with a live target.
When data changes, the affected slot recompiles and applies
the changes to its target (Kubernetes API, ansible-runner, etc.).

Like TextualApp renders to widgets, JugglerApp renders to targets.

Example:
    from genro_juggler import JugglerApp
    from genro_juggler.targets import K8sTarget, FileTarget

    class MyInfra(JugglerApp):
        def kubernetes_recipe(self, root):
            dep = root.deployment(name="api", image="^api.image", replicas=3)
            c = dep.container(name="api", image="^api.image")
            c.port(container_port=8080)

            svc = root.service(name="api")
            svc.service_port(port=80, target_port=8080)

    app = MyInfra(targets={"kubernetes": K8sTarget()})
    app.data["api.image"] = "myapp:v2"  # → PATCH to cluster
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import yaml
from genro_bag import Bag
from genro_builders import BuilderBag

if TYPE_CHECKING:
    from genro_juggler.targets.base import TargetBase


class _JugglerSlot:
    """Internal: one builder + compiler + target."""

    def __init__(self, builder_class: type, root_tag: str,
                 compiler_class: type, compiler_module: Any,
                 target: TargetBase | None) -> None:
        self.store = BuilderBag(builder=builder_class)
        self.root_tag = root_tag
        self.compiler_class = compiler_class
        self.compiler_module = compiler_module
        self._bag_compiler = compiler_class(self.store.builder)
        self.target = target
        self.root: Any = None
        self._data: Bag | None = None
        self.resolved_paths: set[str] = set()

    def bind_data(self, data: Bag) -> None:
        self.store.builder.data = data
        self._data = data

    def init_root(self, name: str | None = None) -> Any:
        root_method = getattr(self.store, self.root_tag)
        self.root = root_method(name=name or self.root_tag)
        return self.root

    def compile_and_apply(self) -> list[dict[str, Any]]:
        """Compile to resource dicts and apply to target."""
        resources = self._compile_to_resources()
        if self.target and resources:
            return self.target.apply_many(resources)
        return []

    def compile_to_yaml(self) -> str:
        """Compile to YAML string (for dry-run or file output)."""
        resources = self._compile_to_resources()
        if not resources:
            return ""
        documents = []
        for resource in resources:
            documents.append(yaml.dump(
                resource, default_flow_style=False,
                sort_keys=False, allow_unicode=True,
            ))
        return "---\n".join(documents)

    def _compile_to_resources(self) -> list[dict[str, Any]]:
        """Compile the builder store to a list of resource dicts."""
        from genro_scriba.app import _collect_resolved_paths, _resolve_dict_pointers
        self.resolved_paths = _collect_resolved_paths(self.root)
        compiled_bag = self._bag_compiler.compile(self.store, self._data)
        compiled_nodes = list(compiled_bag)
        if not compiled_nodes:
            return []
        result = self.compiler_module.compile_to_dict(
            compiled_nodes[0], self.store.builder,
        )
        if self._data is not None:
            _resolve_dict_pointers(result, self._data)
        return result.get("_resources", [result])

    def depends_on(self, changed_path: str) -> bool:
        if not self.resolved_paths:
            return True
        return changed_path in self.resolved_paths


class JugglerApp:
    """Reactive infrastructure bus with multiple builder slots and targets.

    Subclass and override kubernetes_recipe() and/or ansible_recipe().
    Assign targets to push changes to live systems.
    """

    def __init__(self,
                 targets: dict[str, TargetBase] | None = None,
                 data: Bag | dict[str, Any] | None = None) -> None:
        self._data: Bag = Bag()
        self._auto_apply = False
        self._slots: dict[str, _JugglerSlot] = {}
        self._targets = targets or {}

        self._init_kubernetes()
        self._init_ansible()

        for slot in self._slots.values():
            slot.bind_data(self._data)

        k8s_slot = self._slots.get("kubernetes")
        if k8s_slot:
            k8s_slot.init_root()
            self.kubernetes_recipe(k8s_slot.root)

        ansible_slot = self._slots.get("ansible")
        if ansible_slot:
            ansible_slot.init_root()
            self.ansible_recipe(ansible_slot.root)

        for slot in self._slots.values():
            slot.compile_and_apply()

        if data is not None:
            self.data = data

        self._setup_data_trigger()

    def _init_kubernetes(self) -> None:
        try:
            from genro_kubernetes import kubernetes_compiler
            from genro_kubernetes.builders.kubernetes_builder import KubernetesBuilder
            from genro_kubernetes.kubernetes_compiler import KubernetesCompiler
            self._slots["kubernetes"] = _JugglerSlot(
                KubernetesBuilder, "manifest",
                KubernetesCompiler, kubernetes_compiler,
                self._targets.get("kubernetes"),
            )
        except ImportError:
            pass

    def _init_ansible(self) -> None:
        try:
            from genro_ansible import ansible_compiler
            from genro_ansible.ansible_compiler import AnsibleCompiler
            from genro_ansible.builders.ansible_builder import AnsibleBuilder
            self._slots["ansible"] = _JugglerSlot(
                AnsibleBuilder, "playbook",
                AnsibleCompiler, ansible_compiler,
                self._targets.get("ansible"),
            )
        except ImportError:
            pass

    # --- Data ---

    @property
    def data(self) -> Bag:
        return self._data

    @data.setter
    def data(self, value: Bag | dict[str, Any]) -> None:
        if isinstance(value, dict):
            new_bag: Bag = Bag()
            new_bag.fill_from(value)
            self._data = new_bag
        else:
            self._data = value
        for slot in self._slots.values():
            slot.bind_data(self._data)
        self._setup_data_trigger()
        self._apply_all()

    # --- Recipes ---

    def kubernetes_recipe(self, root: Any) -> None:
        """Override to build Kubernetes manifests."""

    def ansible_recipe(self, root: Any) -> None:
        """Override to build Ansible playbooks."""

    # --- Apply ---

    def apply(self, slot_name: str) -> list[dict[str, Any]]:
        """Compile and apply a specific slot to its target."""
        slot = self._slots.get(slot_name)
        if slot is None:
            msg = f"Slot '{slot_name}' not available"
            raise ValueError(msg)
        return slot.compile_and_apply()

    def apply_all(self) -> dict[str, list[dict[str, Any]]]:
        """Compile and apply all slots."""
        return {name: slot.compile_and_apply()
                for name, slot in self._slots.items()}

    def to_yaml(self, slot_name: str) -> str:
        """Compile a slot to YAML (dry-run, no target apply)."""
        slot = self._slots.get(slot_name)
        if slot is None:
            msg = f"Slot '{slot_name}' not available"
            raise ValueError(msg)
        return slot.compile_to_yaml()

    def status(self) -> dict[str, dict[str, Any]]:
        """Get status of all targets."""
        result = {}
        for name, slot in self._slots.items():
            if slot.target:
                result[name] = slot.target.status()
            else:
                result[name] = {"status": "no_target"}
        return result

    # --- Reactive ---

    def _setup_data_trigger(self) -> None:
        self._data.subscribe(
            "juggler_auto_apply",
            any=self._on_data_changed,
        )
        self._auto_apply = True

    def _on_data_changed(self, node: Any = None,
                         pathlist: list | None = None,
                         **_kwargs: Any) -> None:
        if not self._auto_apply:
            return
        changed_path = ".".join(pathlist) if pathlist else ""
        for _name, slot in self._slots.items():
            if slot.target and slot.depends_on(changed_path):
                slot.compile_and_apply()

    def _apply_all(self) -> None:
        for slot in self._slots.values():
            if slot.target:
                slot.compile_and_apply()
