# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for JugglerDashboard — Phase 1: transforms and tree data."""

from __future__ import annotations

from typing import Any

from genro_juggler import JugglerApp
from genro_juggler.dashboard.dashboard import JugglerDashboard
from genro_juggler.dashboard.transforms import (
    collect_slot_resources,
    resources_to_tree_nodes,
)
from genro_juggler.targets.mock_kubernetes import MockK8sTarget

# =========================================================================
# Test infra definitions
# =========================================================================


class SimpleK8sInfra(JugglerApp):
    """Kubernetes infra for dashboard tests."""

    def kubernetes_recipe(self, root: Any) -> None:
        dep = root.deployment(name="api", image="^api.image", replicas=2)
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)

        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)


class MultiResourceInfra(JugglerApp):
    """Kubernetes infra with multiple resource types."""

    def kubernetes_recipe(self, root: Any) -> None:
        root.deployment(name="frontend", image="frontend:v1")
        root.deployment(name="backend", image="backend:v1")
        root.service(name="frontend")
        root.service(name="backend")
        root.secret(name="db-creds")


# =========================================================================
# transforms: resources_to_tree_nodes
# =========================================================================


class TestResourcesToTreeNodes:

    def test_empty_slots(self) -> None:
        result = resources_to_tree_nodes({}, {})
        assert result == []

    def test_single_k8s_resource(self) -> None:
        slots = {
            "kubernetes": [
                {"kind": "Deployment", "metadata": {"name": "api"}},
            ],
        }
        statuses = {"kubernetes": {"status": "connected"}}
        result = resources_to_tree_nodes(slots, statuses)

        assert len(result) == 1
        slot_node = result[0]
        assert slot_node["key"] == "kubernetes"
        assert "[connected]" in slot_node["label"]

        kind_children = slot_node["children"]
        assert len(kind_children) == 1
        assert "Deployment" in kind_children[0]["label"]

        res_children = kind_children[0]["children"]
        assert len(res_children) == 1
        assert res_children[0]["label"] == "api"

    def test_multiple_kinds(self) -> None:
        slots = {
            "kubernetes": [
                {"kind": "Deployment", "metadata": {"name": "api"}},
                {"kind": "Service", "metadata": {"name": "api"}},
            ],
        }
        statuses = {"kubernetes": {"status": "connected"}}
        result = resources_to_tree_nodes(slots, statuses)

        kind_children = result[0]["children"]
        assert len(kind_children) == 2
        kind_labels = {c["label"] for c in kind_children}
        assert any("Deployment" in label for label in kind_labels)
        assert any("Service" in label for label in kind_labels)

    def test_multiple_resources_same_kind(self) -> None:
        slots = {
            "kubernetes": [
                {"kind": "Deployment", "metadata": {"name": "frontend"}},
                {"kind": "Deployment", "metadata": {"name": "backend"}},
            ],
        }
        statuses = {"kubernetes": {"status": "connected"}}
        result = resources_to_tree_nodes(slots, statuses)

        dep_node = result[0]["children"][0]
        assert "(2)" in dep_node["label"]
        names = {c["label"] for c in dep_node["children"]}
        assert names == {"frontend", "backend"}

    def test_no_target_status(self) -> None:
        slots = {"kubernetes": [{"kind": "Deployment", "metadata": {"name": "api"}}]}
        statuses = {"kubernetes": {"status": "no_target"}}
        result = resources_to_tree_nodes(slots, statuses)
        assert "[no_target]" in result[0]["label"]

    def test_missing_status(self) -> None:
        slots = {"kubernetes": [{"kind": "Deployment", "metadata": {"name": "api"}}]}
        result = resources_to_tree_nodes(slots, {})
        assert "[unknown]" in result[0]["label"]

    def test_ansible_resource(self) -> None:
        slots = {
            "ansible": [
                {"name": "Setup", "hosts": "all", "tasks": []},
            ],
        }
        statuses = {"ansible": {"status": "available"}}
        result = resources_to_tree_nodes(slots, statuses)

        slot_node = result[0]
        assert "ansible" in slot_node["label"]
        kind_children = slot_node["children"]
        assert len(kind_children) == 1
        assert "Play" in kind_children[0]["label"]

    def test_unnamed_resource(self) -> None:
        slots = {"kubernetes": [{"kind": "ConfigMap"}]}
        result = resources_to_tree_nodes(slots, {})
        res_node = result[0]["children"][0]["children"][0]
        assert res_node["label"] == "(unnamed)"

    def test_key_uniqueness(self) -> None:
        slots = {
            "kubernetes": [
                {"kind": "Deployment", "metadata": {"name": "api"}},
                {"kind": "Service", "metadata": {"name": "api"}},
            ],
        }
        result = resources_to_tree_nodes(slots, {})

        all_keys = set()
        for slot in result:
            all_keys.add(slot["key"])
            for kind in slot["children"]:
                all_keys.add(kind["key"])
                for res in kind["children"]:
                    all_keys.add(res["key"])

        assert len(all_keys) == 5  # kubernetes, Deployment, Service, Dep/api, Svc/api


# =========================================================================
# transforms: collect_slot_resources
# =========================================================================


class TestCollectSlotResources:

    def test_collect_k8s_resources(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        resources = collect_slot_resources(app)

        assert "kubernetes" in resources
        k8s = resources["kubernetes"]
        assert len(k8s) >= 2
        kinds = {r.get("kind") for r in k8s}
        assert "Deployment" in kinds
        assert "Service" in kinds

    def test_collect_multi_resource(self) -> None:
        app = MultiResourceInfra()
        resources = collect_slot_resources(app)

        k8s = resources["kubernetes"]
        assert len(k8s) >= 5
        names = {r.get("metadata", {}).get("name") for r in k8s}
        assert "frontend" in names
        assert "backend" in names
        assert "db-creds" in names


# =========================================================================
# JugglerDashboard: get_tree_data (no UI)
# =========================================================================


class TestJugglerDashboardData:

    def test_get_tree_data_no_target(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)
        tree_data = dashboard.get_tree_data()

        assert len(tree_data) >= 1
        k8s_slot = tree_data[0]
        assert k8s_slot["key"] == "kubernetes"
        assert "[no_target]" in k8s_slot["label"]

        all_res_names = []
        for kind in k8s_slot["children"]:
            for res in kind["children"]:
                all_res_names.append(res["label"])
        assert "api" in all_res_names

    def test_get_tree_data_with_mock_target(self) -> None:
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)
        tree_data = dashboard.get_tree_data()

        k8s_slot = tree_data[0]
        assert "[connected]" in k8s_slot["label"]

    def test_tree_data_reflects_resources(self) -> None:
        app = MultiResourceInfra()
        dashboard = JugglerDashboard(app)
        tree_data = dashboard.get_tree_data()

        k8s_slot = tree_data[0]
        all_res_names = []
        for kind in k8s_slot["children"]:
            for res in kind["children"]:
                all_res_names.append(res["label"])

        assert "frontend" in all_res_names
        assert "backend" in all_res_names
        assert "db-creds" in all_res_names
