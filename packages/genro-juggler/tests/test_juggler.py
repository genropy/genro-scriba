# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for JugglerApp with FileTarget and recording target."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml
from genro_bag import Bag

from genro_juggler import JugglerApp
from genro_juggler.targets.base import TargetBase
from genro_juggler.targets.file_target import FileTarget


class RecordingTarget(TargetBase):
    """Target that records apply calls for testing."""

    def __init__(self) -> None:
        self.applied: list[dict[str, Any]] = []

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        self.applied.append(resource)
        return {"status": "recorded", "kind": resource.get("kind", "")}

    def status(self) -> dict[str, Any]:
        return {"status": "recording", "count": len(self.applied)}


class SimpleK8sInfra(JugglerApp):
    """Test infra with Kubernetes recipe."""

    def kubernetes_recipe(self, root):
        dep = root.deployment(name="api", image="^api.image", replicas=2)
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)

        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)


class SimpleAnsibleInfra(JugglerApp):
    """Test infra with Ansible recipe."""

    def ansible_recipe(self, root):
        play = root.play(name="Setup", hosts="all", become=True)
        play.task(name="Install nginx", module="apt",
                  args_name="nginx", args_state="present")


class DualInfra(JugglerApp):
    """Test infra with both Kubernetes and Ansible recipes."""

    def kubernetes_recipe(self, root):
        root.deployment(name="api", image="^api.image")

    def ansible_recipe(self, root):
        play = root.play(name="Setup", hosts="^hosts")
        play.task(name="Install", module="apt",
                  args_name="nginx", args_state="present")


# =========================================================================
# SLOTS
# =========================================================================


class TestSlotCreation:

    def test_kubernetes_slot_created(self) -> None:
        app = SimpleK8sInfra()
        assert "kubernetes" in app._slots

    def test_ansible_slot_created(self) -> None:
        app = SimpleAnsibleInfra()
        assert "ansible" in app._slots

    def test_dual_slots(self) -> None:
        app = DualInfra()
        assert "kubernetes" in app._slots
        assert "ansible" in app._slots


# =========================================================================
# TO_YAML (dry run)
# =========================================================================


class TestToYaml:

    def test_kubernetes_yaml(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:latest"})
        yaml_str = app.to_yaml("kubernetes")
        assert "kind: Deployment" in yaml_str
        assert "kind: Service" in yaml_str
        assert "myapp:latest" in yaml_str

    def test_ansible_yaml(self) -> None:
        app = SimpleAnsibleInfra()
        yaml_str = app.to_yaml("ansible")
        assert "Install nginx" in yaml_str
        assert "apt" in yaml_str


# =========================================================================
# RECORDING TARGET
# =========================================================================


class TestRecordingTarget:

    def test_apply_records_resources(self) -> None:
        recorder = RecordingTarget()
        SimpleK8sInfra(
            targets={"kubernetes": recorder},
            data={"api.image": "myapp:v1"},
        )
        # Initial apply happens in __init__
        assert len(recorder.applied) >= 2  # Deployment + Service
        kinds = {r.get("kind") for r in recorder.applied}
        assert "Deployment" in kinds
        assert "Service" in kinds

    def test_data_change_triggers_apply(self) -> None:
        recorder = RecordingTarget()
        app = SimpleK8sInfra(
            targets={"kubernetes": recorder},
            data={"api.image": "myapp:v1"},
        )
        initial_count = len(recorder.applied)

        app.data["api.image"] = "myapp:v2"
        assert len(recorder.applied) > initial_count

    def test_status(self) -> None:
        recorder = RecordingTarget()
        app = SimpleK8sInfra(targets={"kubernetes": recorder})
        status = app.status()
        assert "kubernetes" in status
        assert status["kubernetes"]["status"] == "recording"


# =========================================================================
# FILE TARGET
# =========================================================================


class TestFileTarget:

    def test_file_target_writes_yaml(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = FileTarget(output_dir=tmpdir)
            SimpleK8sInfra(
                targets={"kubernetes": target},
                data={"api.image": "myapp:v1"},
            )
            files = list(Path(tmpdir).glob("*.yaml"))
            assert len(files) >= 2

    def test_file_target_single_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            path = f.name
        try:
            target = FileTarget(filename=path)
            SimpleK8sInfra(
                targets={"kubernetes": target},
                data={"api.image": "myapp:v1"},
            )
            content = Path(path).read_text()
            assert "kind: Deployment" in content
            assert "---" in content
        finally:
            Path(path).unlink(missing_ok=True)

    def test_dry_run_no_target(self) -> None:
        target = FileTarget()  # No dir, no file → dry run
        result = target.apply({"kind": "Deployment", "metadata": {"name": "test"}})
        assert result["status"] == "dry_run"
        assert "yaml" in result


# =========================================================================
# POINTER RESOLUTION
# =========================================================================


class TestPointerResolution:

    def test_kubernetes_pointers_resolved(self) -> None:
        app = SimpleK8sInfra(data={"api.image": "myapp:v3"})
        yaml_str = app.to_yaml("kubernetes")
        parsed = list(yaml.safe_load_all(yaml_str))
        dep = next(d for d in parsed if d and d.get("kind") == "Deployment")
        image = dep["spec"]["template"]["spec"]["containers"][0]["image"]
        assert image == "myapp:v3"


# =========================================================================
# DATA SETTER
# =========================================================================


class TestDataSetter:

    def test_replace_with_dict(self) -> None:
        recorder = RecordingTarget()
        app = SimpleK8sInfra(targets={"kubernetes": recorder})
        app.data = {"api.image": "myapp:replaced"}
        yaml_str = app.to_yaml("kubernetes")
        assert "myapp:replaced" in yaml_str

    def test_replace_with_bag(self) -> None:
        app = SimpleK8sInfra()
        new_data = Bag()
        new_data["api.image"] = "myapp:bag"
        app.data = new_data
        yaml_str = app.to_yaml("kubernetes")
        assert "myapp:bag" in yaml_str
