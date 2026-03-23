# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for MockK8sTarget and MockAnsibleTarget."""

from __future__ import annotations

from typing import Any

from genro_juggler import JugglerApp
from genro_juggler.targets.mock_ansible import MockAnsibleTarget
from genro_juggler.targets.mock_kubernetes import MockK8sTarget

# =========================================================================
# MockK8sTarget
# =========================================================================


class TestMockK8sApply:

    def test_apply_returns_realistic_response(self) -> None:
        target = MockK8sTarget(verbose=False)
        result = target.apply({
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api", "namespace": "prod"},
            "spec": {},
        })
        assert result["status"] == "applied"
        assert result["kind"] == "Deployment"
        assert result["name"] == "api"
        assert result["namespace"] == "prod"
        assert result["resource_version"] == "1"

    def test_resource_version_increments(self) -> None:
        target = MockK8sTarget(verbose=False)
        r1 = target.apply({"kind": "Service", "metadata": {"name": "a"}})
        r2 = target.apply({"kind": "Service", "metadata": {"name": "b"}})
        assert int(r2["resource_version"]) > int(r1["resource_version"])

    def test_default_namespace(self) -> None:
        target = MockK8sTarget(verbose=False)
        result = target.apply({"kind": "Pod", "metadata": {"name": "x"}})
        assert result["namespace"] == "default"


class TestMockK8sStore:

    def test_store_holds_resources(self) -> None:
        target = MockK8sTarget(verbose=False)
        resource = {"kind": "ConfigMap", "metadata": {"name": "cfg"}}
        target.apply(resource)
        store = target.get_applied()
        assert "ConfigMap/default/cfg" in store
        assert store["ConfigMap/default/cfg"] is resource

    def test_apply_overwrites_same_key(self) -> None:
        target = MockK8sTarget(verbose=False)
        target.apply({"kind": "Secret", "metadata": {"name": "s"},
                       "data": {"v": "1"}})
        target.apply({"kind": "Secret", "metadata": {"name": "s"},
                       "data": {"v": "2"}})
        store = target.get_applied()
        assert store["Secret/default/s"]["data"]["v"] == "2"


class TestMockK8sDelete:

    def test_delete_removes_from_store(self) -> None:
        target = MockK8sTarget(verbose=False)
        target.apply({"kind": "Pod", "metadata": {"name": "p"}})
        assert len(target.get_applied()) == 1
        result = target.delete({"kind": "Pod", "metadata": {"name": "p"}})
        assert result["status"] == "deleted"
        assert len(target.get_applied()) == 0

    def test_delete_nonexistent_is_safe(self) -> None:
        target = MockK8sTarget(verbose=False)
        result = target.delete({"kind": "Pod", "metadata": {"name": "x"}})
        assert result["status"] == "deleted"


class TestMockK8sStatus:

    def test_status_connected(self) -> None:
        target = MockK8sTarget(verbose=False)
        status = target.status()
        assert status["status"] == "connected"
        assert status["server_version"] == "1.29.0"
        assert status["platform"] == "mock"

    def test_status_resource_count(self) -> None:
        target = MockK8sTarget(verbose=False)
        target.apply({"kind": "Deployment", "metadata": {"name": "a"}})
        target.apply({"kind": "Service", "metadata": {"name": "b"}})
        assert target.status()["resources"] == 2


class TestMockK8sLog:

    def test_log_records_operations(self) -> None:
        target = MockK8sTarget(verbose=False)
        target.apply({"kind": "Pod", "metadata": {"name": "a"}})
        target.delete({"kind": "Pod", "metadata": {"name": "a"}})
        log = target.get_log()
        assert len(log) == 2
        assert log[0]["operation"] == "apply"
        assert log[1]["operation"] == "delete"
        assert "timestamp" in log[0]


# =========================================================================
# MockAnsibleTarget
# =========================================================================


class TestMockAnsibleApply:

    def test_single_play(self) -> None:
        target = MockAnsibleTarget(verbose=False)
        play = {
            "name": "Setup",
            "hosts": "all",
            "tasks": [
                {"name": "Install nginx", "module": "apt"},
                {"name": "Start nginx", "module": "systemd"},
            ],
        }
        result = target.apply(play)
        assert result["status"] == "successful"
        assert result["rc"] == 0
        assert result["stats"]["ok"] == 2
        assert result["stats"]["changed"] == 2
        assert result["stats"]["failed"] == 0

    def test_multiple_plays(self) -> None:
        target = MockAnsibleTarget(verbose=False)
        plays = [
            {"name": "Play1", "hosts": "web", "tasks": [
                {"name": "T1", "module": "apt"},
            ]},
            {"name": "Play2", "hosts": "db", "tasks": [
                {"name": "T2", "module": "apt"},
                {"name": "T3", "module": "systemd"},
            ]},
        ]
        result = target.apply(plays)
        assert result["stats"]["ok"] == 3  # 1 + 2

    def test_play_without_tasks(self) -> None:
        target = MockAnsibleTarget(verbose=False)
        result = target.apply({"name": "Empty", "hosts": "all"})
        assert result["status"] == "successful"
        assert result["stats"]["ok"] == 0


class TestMockAnsibleStatus:

    def test_status_available(self) -> None:
        target = MockAnsibleTarget(verbose=False)
        status = target.status()
        assert status["status"] == "available"
        assert status["ansible_runner_version"] == "mock"


class TestMockAnsibleLog:

    def test_log_records_plays(self) -> None:
        target = MockAnsibleTarget(verbose=False)
        target.apply({"name": "P1", "hosts": "all", "tasks": []})
        target.apply({"name": "P2", "hosts": "all", "tasks": []})
        log = target.get_log()
        assert len(log) == 2
        assert log[0]["play_count"] == 1
        assert "timestamp" in log[0]


# =========================================================================
# End-to-end with JugglerApp
# =========================================================================


class FullInfra(JugglerApp):
    """Test infra with both K8s and Ansible recipes."""

    def kubernetes_recipe(self, root: Any) -> None:
        dep = root.deployment(name="web", image="^app.image", replicas=2)
        c = dep.container(name="web", image="^app.image")
        c.port(container_port=8080)
        c.env_var(name="DB_HOST", value="^db.host")

        svc = root.service(name="web")
        svc.service_port(port=80, target_port=8080)

        root.secret(name="db-creds",
                    data={"password": "^db.password"})

    def ansible_recipe(self, root: Any) -> None:
        play = root.play(name="Prepare servers", hosts="all", become=True)
        play.task(name="Install Docker", module="apt",
                  args_name="docker.io", args_state="present")
        play.task(name="Start Docker", module="systemd",
                  args_name="docker", args_state="started")


class TestEndToEnd:

    def test_full_infra_with_mock_targets(self) -> None:
        k8s = MockK8sTarget(verbose=False)
        ansible = MockAnsibleTarget(verbose=False)

        app = FullInfra(
            targets={"kubernetes": k8s, "ansible": ansible},
            data={
                "app.image": "myapp:v1",
                "db.host": "postgres.internal",
                "db.password": "s3cret",
            },
        )

        # K8s resources were applied
        store = k8s.get_applied()
        kinds = {r.get("kind") for r in store.values()}
        assert "Deployment" in kinds
        assert "Service" in kinds
        assert "Secret" in kinds

        # Ansible playbook was executed
        ansible_log = ansible.get_log()
        assert len(ansible_log) >= 1
        assert ansible_log[0]["result"]["status"] == "successful"

        # Status works
        status = app.status()
        assert status["kubernetes"]["status"] == "connected"
        assert status["ansible"]["status"] == "available"

    def test_data_change_triggers_mock_reapply(self) -> None:
        k8s = MockK8sTarget(verbose=False)
        app = FullInfra(
            targets={"kubernetes": k8s},
            data={"app.image": "myapp:v1",
                  "db.host": "pg", "db.password": "x"},
        )
        initial_log_count = len(k8s.get_log())

        app.data["app.image"] = "myapp:v2"
        assert len(k8s.get_log()) > initial_log_count

    def test_yaml_dry_run_with_mock(self) -> None:
        app = FullInfra(
            data={"app.image": "myapp:v1",
                  "db.host": "pg", "db.password": "x"},
        )
        yaml_str = app.to_yaml("kubernetes")
        assert "myapp:v1" in yaml_str
        assert "kind: Deployment" in yaml_str
