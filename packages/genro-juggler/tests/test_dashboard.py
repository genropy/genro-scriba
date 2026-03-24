# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for JugglerDashboard — transforms, tree data, and reactive triggers."""

from __future__ import annotations

from typing import Any

from genro_juggler import JugglerApp, registry
from genro_juggler.dashboard.dashboard import JugglerDashboard
from genro_juggler.dashboard.transforms import (
    collect_slot_resources,
    resources_to_tree_nodes,
)
from genro_juggler.remote import RemoteProxy
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


# =========================================================================
# JugglerDashboard: reactive trigger (Phase 2)
# =========================================================================


class TestReactiveTrigger:

    def test_subscribe_and_unsubscribe(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)

        assert not dashboard._subscribed
        dashboard._subscribe()
        assert dashboard._subscribed

        dashboard._unsubscribe()
        assert not dashboard._subscribed

    def test_subscribe_idempotent(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)

        dashboard._subscribe()
        dashboard._subscribe()  # second call is a no-op
        assert dashboard._subscribed

        dashboard._unsubscribe()
        assert not dashboard._subscribed

    def test_data_change_updates_tree_data(self) -> None:
        """After subscribing, data changes are reflected in get_tree_data."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)
        dashboard._subscribe()

        # Verify initial image is resolved in compiled resources
        initial_resources = collect_slot_resources(app)
        k8s = initial_resources["kubernetes"]
        dep = next(r for r in k8s if r.get("kind") == "Deployment")
        containers = dep["spec"]["template"]["spec"]["containers"]
        assert containers[0]["image"] == "myapp:v1"

        # Change data — JugglerApp recompiles automatically
        app.data["api.image"] = "myapp:v2"

        # Verify the compiled resources now reflect v2
        updated_resources = collect_slot_resources(app)
        k8s_updated = updated_resources["kubernetes"]
        dep_updated = next(r for r in k8s_updated if r.get("kind") == "Deployment")
        containers_updated = dep_updated["spec"]["template"]["spec"]["containers"]
        assert containers_updated[0]["image"] == "myapp:v2"

        # Tree data should still be consistent
        tree_data = dashboard.get_tree_data()
        assert len(tree_data) >= 1

    def test_mock_target_records_reapply_after_data_change(self) -> None:
        """MockK8sTarget log grows when data changes trigger recompile."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)
        dashboard._subscribe()

        initial_log_count = len(mock.get_log())

        # Change data — triggers JugglerApp recompile + apply
        app.data["api.image"] = "myapp:v2"

        assert len(mock.get_log()) > initial_log_count

        # Dashboard tree data reflects updated status
        tree_data = dashboard.get_tree_data()
        k8s_slot = tree_data[0]
        assert "[connected]" in k8s_slot["label"]

    def test_on_data_changed_without_live_app(self) -> None:
        """_on_data_changed works without a running LiveApp (falls back to direct call)."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)

        # No live_app is running — _on_data_changed should still work
        # by calling _populate directly
        dashboard._on_data_changed()

        # No crash, and tree data is consistent
        tree_data = dashboard.get_tree_data()
        assert len(tree_data) >= 1


# =========================================================================
# JugglerDashboard: remote server + REPL (Phase 3)
# =========================================================================


class TestDashboardRemote:

    def test_start_and_stop_remote(self) -> None:
        """Dashboard with name starts RemoteServer and registers in registry."""
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app, name="test_dash_remote")

        dashboard._start_remote()
        try:
            assert dashboard._remote is not None

            info = registry.get_app_info("test_dash_remote")
            assert info is not None
            assert "port" in info
            assert "token" in info

            # RemoteProxy can connect and get status
            proxy = RemoteProxy("127.0.0.1", info["port"], info["token"])
            status = proxy.status()
            assert "kubernetes" in status
        finally:
            dashboard._stop_remote()

        assert dashboard._remote is None
        assert registry.get_app_info("test_dash_remote") is None

    def test_remote_data_set_triggers_recompile(self) -> None:
        """Setting data via RemoteProxy triggers recompile in JugglerApp."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app, name="test_dash_data")

        dashboard._start_remote()
        try:
            info = registry.get_app_info("test_dash_data")
            proxy = RemoteProxy("127.0.0.1", info["port"], info["token"])

            initial_log = len(mock.get_log())

            # Set data via remote — triggers reactive recompile + apply
            proxy.data_set("api.image", "myapp:v2")

            assert len(mock.get_log()) > initial_log

            # Verify the new value
            value = proxy.data_get("api.image")
            assert value == "myapp:v2"
        finally:
            dashboard._stop_remote()

    def test_remote_yaml_and_slots(self) -> None:
        """RemoteProxy can get YAML and slot list."""
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app, name="test_dash_yaml")

        dashboard._start_remote()
        try:
            info = registry.get_app_info("test_dash_yaml")
            proxy = RemoteProxy("127.0.0.1", info["port"], info["token"])

            slots = proxy.slots()
            assert "kubernetes" in slots

            yaml_str = proxy.to_yaml("kubernetes")
            assert "kind: Deployment" in yaml_str
            assert "myapp:v1" in yaml_str
        finally:
            dashboard._stop_remote()

    def test_dashboard_without_name_no_remote(self) -> None:
        """Dashboard without name does not start RemoteServer."""
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)

        assert dashboard._remote is None
        assert dashboard._name == ""


# =========================================================================
# JugglerDashboard: Auto Live + Log (Phase 4)
# =========================================================================


class TestAutoLiveAndLog:

    def test_auto_live_default_off(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)
        assert not dashboard._auto_live

    def test_set_auto_live_on(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)
        dashboard.set_auto_live(True)
        assert dashboard._auto_live

    def test_set_auto_live_off(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)
        dashboard.set_auto_live(True)
        dashboard.set_auto_live(False)
        assert not dashboard._auto_live

    def test_go_live_applies_all_slots(self) -> None:
        """go_live() calls apply_all() on the JugglerApp."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        initial_log = len(mock.get_log())

        dashboard = JugglerDashboard(app)
        dashboard.go_live()

        assert len(mock.get_log()) > initial_log

    def test_go_live_returns_results_in_tree(self) -> None:
        """After go_live(), tree data still reflects resources."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)
        dashboard.go_live()

        tree_data = dashboard.get_tree_data()
        assert len(tree_data) >= 1

    def test_auto_live_triggers_apply_on_data_change(self) -> None:
        """With auto_live ON, data changes trigger apply_all."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)
        dashboard._subscribe()
        dashboard._auto_live = True

        log_before = len(mock.get_log())

        # _on_data_changed_sync simulates what happens on data change
        dashboard._on_data_changed_sync()

        assert len(mock.get_log()) > log_before

    def test_auto_live_off_no_apply_on_sync(self) -> None:
        """With auto_live OFF, _on_data_changed_sync does NOT apply."""
        mock = MockK8sTarget(verbose=False)
        app = SimpleK8sInfra(
            targets={"kubernetes": mock},
            data={"api.image": "myapp:v1"},
        )
        dashboard = JugglerDashboard(app)
        dashboard._subscribe()

        log_before = len(mock.get_log())

        dashboard._on_data_changed_sync()

        # No new apply — log unchanged
        assert len(mock.get_log()) == log_before

    def test_go_live_without_targets(self) -> None:
        """go_live() works even without targets (no crash)."""
        app = SimpleK8sInfra(data={"api.image": "myapp:v1"})
        dashboard = JugglerDashboard(app)
        dashboard.go_live()  # should not raise

        tree_data = dashboard.get_tree_data()
        assert len(tree_data) >= 1
