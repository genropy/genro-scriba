# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for ScribaApp — shared data, dual builder, selective recompile."""

from __future__ import annotations

import tempfile
from pathlib import Path

import yaml
from genro_bag import Bag
from genro_scriba import ScribaApp


class DualInfra(ScribaApp):
    """Test infra with both Traefik and Compose recipes."""

    def traefik_recipe(self, root):
        root.entryPoint(name="web", address="^web.port")
        http = root.http()
        http.routers().router(
            name="api", rule="^api.rule",
            service="api-svc", entryPoints=["web"])
        svc = http.services().service(name="api-svc")
        svc.loadBalancer().server(url="^api.backend")

    def compose_recipe(self, root):
        root.service(
            name="api", image="myapi:latest",
            environment={"DB_HOST": "^db.host"},
            restart="always")
        root.service(
            name="db", image="postgres:16",
            environment={"POSTGRES_PASSWORD": "^db.password"})
        root.volume(name="pgdata")


class TestScribaAppInit:

    def test_creates_both_slots(self) -> None:
        infra = DualInfra()
        assert "traefik" in infra._slots
        assert "compose" in infra._slots

    def test_shared_data(self) -> None:
        infra = DualInfra()
        assert isinstance(infra.data, Bag)


class TestDependencyTracking:

    def test_traefik_deps(self) -> None:
        infra = DualInfra()
        t = infra._slots["traefik"]
        assert "web.port" in t.resolved_paths
        assert "api.rule" in t.resolved_paths
        assert "api.backend" in t.resolved_paths
        assert "db.host" not in t.resolved_paths
        assert "db.password" not in t.resolved_paths

    def test_compose_deps(self) -> None:
        infra = DualInfra()
        c = infra._slots["compose"]
        assert "db.host" in c.resolved_paths
        assert "db.password" in c.resolved_paths
        assert "web.port" not in c.resolved_paths
        assert "api.rule" not in c.resolved_paths

    def test_depends_on_selective(self) -> None:
        infra = DualInfra()
        t = infra._slots["traefik"]
        c = infra._slots["compose"]

        assert t.depends_on("web.port") is True
        assert t.depends_on("db.password") is False

        assert c.depends_on("db.password") is True
        assert c.depends_on("web.port") is False


class TestDataResolution:

    def test_traefik_pointers_resolved(self) -> None:
        infra = DualInfra()
        infra.data["web.port"] = ":80"
        infra.data["api.rule"] = "Host(`test.com`)"
        infra.data["api.backend"] = "http://10.0.0.1:8080"
        parsed = yaml.safe_load(infra.to_yaml("traefik"))
        assert parsed["entryPoints"]["web"]["address"] == ":80"
        assert parsed["http"]["routers"]["api"]["rule"] == "Host(`test.com`)"

    def test_compose_pointers_resolved(self) -> None:
        infra = DualInfra()
        infra.data["db.host"] = "10.0.0.5"
        infra.data["db.password"] = "secret"
        parsed = yaml.safe_load(infra.to_yaml("compose"))
        assert parsed["services"]["api"]["environment"]["DB_HOST"] == "10.0.0.5"
        assert parsed["services"]["db"]["environment"]["POSTGRES_PASSWORD"] == "secret"

    def test_to_yaml_all(self) -> None:
        infra = DualInfra()
        infra.data["web.port"] = ":80"
        infra.data["api.rule"] = "Host(`x.com`)"
        infra.data["api.backend"] = "http://localhost:8080"
        infra.data["db.host"] = "db"
        infra.data["db.password"] = "pw"
        result = infra.to_yaml_all()
        assert "traefik" in result
        assert "compose" in result
        assert "entryPoints" in result["traefik"]
        assert "services" in result["compose"]


class TestSelectiveRecompile:

    def test_only_affected_builder_recompiles(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            traefik_path = Path(tmpdir) / "traefik.yml"
            compose_path = Path(tmpdir) / "compose.yml"

            infra = DualInfra(
                traefik_output=str(traefik_path),
                compose_output=str(compose_path),
            )

            infra.data = {
                "web.port": ":80",
                "api.rule": "Host(`a.com`)",
                "api.backend": "http://h1:8080",
                "db.host": "db1",
                "db.password": "pw1",
            }

            assert traefik_path.exists()
            assert compose_path.exists()

            infra.data["web.port"] = ":8080"
            traefik_parsed = yaml.safe_load(traefik_path.read_text())
            assert traefik_parsed["entryPoints"]["web"]["address"] == ":8080"

            infra.data["db.password"] = "new_pw"
            compose_parsed = yaml.safe_load(compose_path.read_text())
            assert compose_parsed["services"]["db"]["environment"]["POSTGRES_PASSWORD"] == "new_pw"


class TestDataSetter:

    def test_replace_with_dict(self) -> None:
        infra = DualInfra()
        infra.data = {
            "web.port": ":80",
            "api.rule": "Host(`a.com`)",
            "api.backend": "http://h:8080",
            "db.host": "db",
            "db.password": "pw",
        }
        parsed = yaml.safe_load(infra.to_yaml("traefik"))
        assert parsed["entryPoints"]["web"]["address"] == ":80"

    def test_replace_with_bag(self) -> None:
        infra = DualInfra()
        new_data = Bag()
        new_data["db.host"] = "newdb"
        new_data["db.password"] = "newpw"
        infra.data = new_data
        parsed = yaml.safe_load(infra.to_yaml("compose"))
        assert parsed["services"]["api"]["environment"]["DB_HOST"] == "newdb"
