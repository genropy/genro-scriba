# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for ComposeBuilder."""

from __future__ import annotations

import yaml

from genro_bag import Bag
from genro_compose import ComposeApp
from genro_compose.builders.compose_builder import ComposeBuilder
from genro_compose.compose_compiler import compile_to_dict


def _build(recipe_fn) -> dict:
    """Helper: create store, call recipe, compile to dict."""
    store = Bag(builder=ComposeBuilder)
    store.builder.data = Bag()
    root = store.compose(name="test")
    recipe_fn(root)
    return compile_to_dict(root, store.builder)


# =========================================================================
# SERVICE — scalar attributes
# =========================================================================


class TestService:

    def test_basic(self) -> None:
        d = _build(lambda r: r.service(name="web", image="nginx:alpine"))
        assert d["services"]["web"]["image"] == "nginx:alpine"

    def test_multiple(self) -> None:
        def recipe(root):
            root.service(name="web", image="nginx")
            root.service(name="db", image="postgres:16")
        d = _build(recipe)
        assert "web" in d["services"]
        assert "db" in d["services"]

    def test_scalar_attrs(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp:latest",
            container_name="my-app",
            hostname="app-host",
            command="python serve.py",
            working_dir="/app",
            user="1000:1000",
            restart="unless-stopped",
            privileged=True,
            tty=True,
        ))
        svc = d["services"]["app"]
        assert svc["image"] == "myapp:latest"
        assert svc["container_name"] == "my-app"
        assert svc["restart"] == "unless-stopped"
        assert svc["privileged"] is True
        assert svc["tty"] is True


# =========================================================================
# SERVICE — list/dict attributes
# =========================================================================


class TestServiceCollections:

    def test_ports(self) -> None:
        d = _build(lambda r: r.service(
            name="web", image="nginx",
            ports=["80:80", "443:443/tcp"]))
        assert d["services"]["web"]["ports"] == ["80:80", "443:443/tcp"]

    def test_volumes(self) -> None:
        d = _build(lambda r: r.service(
            name="web", image="nginx",
            volumes=["./html:/usr/share/nginx/html:ro", "data:/data"]))
        assert len(d["services"]["web"]["volumes"]) == 2

    def test_environment_dict(self) -> None:
        d = _build(lambda r: r.service(
            name="db", image="postgres",
            environment={"POSTGRES_PASSWORD": "secret", "POSTGRES_DB": "app"}))
        env = d["services"]["db"]["environment"]
        assert env["POSTGRES_PASSWORD"] == "secret"

    def test_environment_list(self) -> None:
        d = _build(lambda r: r.service(
            name="db", image="postgres",
            environment=["POSTGRES_PASSWORD=secret"]))
        assert d["services"]["db"]["environment"] == ["POSTGRES_PASSWORD=secret"]

    def test_labels(self) -> None:
        d = _build(lambda r: r.service(
            name="web", image="nginx",
            labels={"traefik.enable": "true", "app": "web"}))
        assert d["services"]["web"]["labels"]["traefik.enable"] == "true"

    def test_env_file(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            env_file=[".env", ".env.local"]))
        assert d["services"]["app"]["env_file"] == [".env", ".env.local"]

    def test_cap_add_drop(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            cap_add=["NET_ADMIN", "SYS_PTRACE"],
            cap_drop=["ALL"]))
        assert "NET_ADMIN" in d["services"]["app"]["cap_add"]
        assert "ALL" in d["services"]["app"]["cap_drop"]

    def test_dns(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            dns=["8.8.8.8", "8.8.4.4"]))
        assert d["services"]["app"]["dns"] == ["8.8.8.8", "8.8.4.4"]

    def test_extra_hosts(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            extra_hosts=["myhost:192.168.1.1"]))
        assert "myhost:192.168.1.1" in d["services"]["app"]["extra_hosts"]

    def test_tmpfs(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            tmpfs=["/tmp", "/run"]))
        assert d["services"]["app"]["tmpfs"] == ["/tmp", "/run"]

    def test_sysctls(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            sysctls={"net.core.somaxconn": "1024"}))
        assert d["services"]["app"]["sysctls"]["net.core.somaxconn"] == "1024"

    def test_ulimits(self) -> None:
        d = _build(lambda r: r.service(
            name="app", image="myapp",
            ulimits={"nofile": {"soft": 1024, "hard": 65535}}))
        ul = d["services"]["app"]["ulimits"]["nofile"]
        assert ul["soft"] == 1024

    def test_networks_list(self) -> None:
        d = _build(lambda r: r.service(
            name="web", image="nginx",
            networks=["frontend", "backend"]))
        assert d["services"]["web"]["networks"] == ["frontend", "backend"]

    def test_secrets_configs(self) -> None:
        d = _build(lambda r: r.service(
            name="web", image="nginx",
            secrets=["db_password"],
            configs=["nginx_conf"]))
        assert "db_password" in d["services"]["web"]["secrets"]
        assert "nginx_conf" in d["services"]["web"]["configs"]


# =========================================================================
# SUB-ELEMENTS: build_config
# =========================================================================


class TestBuildConfig:

    def test_basic(self) -> None:
        def recipe(root):
            svc = root.service(name="app")
            svc.build_config(context=".", dockerfile="Dockerfile.prod",
                             target="production")
        d = _build(recipe)
        build = d["services"]["app"]["build"]
        assert build["context"] == "."
        assert build["dockerfile"] == "Dockerfile.prod"
        assert build["target"] == "production"

    def test_with_args(self) -> None:
        def recipe(root):
            svc = root.service(name="app")
            svc.build_config(context=".",
                             args={"NODE_ENV": "production", "VERSION": "1.0"})
        d = _build(recipe)
        assert d["services"]["app"]["build"]["args"]["NODE_ENV"] == "production"


# =========================================================================
# SUB-ELEMENTS: healthcheck
# =========================================================================


class TestHealthcheck:

    def test_basic(self) -> None:
        def recipe(root):
            svc = root.service(name="db", image="postgres")
            svc.healthcheck(test="pg_isready", interval="10s",
                            timeout="5s", retries=5)
        d = _build(recipe)
        hc = d["services"]["db"]["healthcheck"]
        assert hc["test"] == "pg_isready"
        assert hc["retries"] == 5
        assert hc["interval"] == "10s"

    def test_disable(self) -> None:
        def recipe(root):
            svc = root.service(name="app", image="myapp")
            svc.healthcheck(disable=True)
        d = _build(recipe)
        assert d["services"]["app"]["healthcheck"]["disable"] is True


# =========================================================================
# SUB-ELEMENTS: deploy
# =========================================================================


class TestDeploy:

    def test_replicas(self) -> None:
        def recipe(root):
            svc = root.service(name="web", image="nginx")
            svc.deploy(replicas=3)
        d = _build(recipe)
        assert d["services"]["web"]["deploy"]["replicas"] == 3

    def test_resources(self) -> None:
        def recipe(root):
            svc = root.service(name="web", image="nginx")
            dep = svc.deploy(replicas=2)
            dep.resources(limits_cpus="0.5", limits_memory="512M",
                          reservations_cpus="0.25", reservations_memory="256M")
        d = _build(recipe)
        res = d["services"]["web"]["deploy"]["resources"]
        assert res["limits"]["cpus"] == "0.5"
        assert res["limits"]["memory"] == "512M"
        assert res["reservations"]["cpus"] == "0.25"

    def test_restart_policy(self) -> None:
        def recipe(root):
            svc = root.service(name="web", image="nginx")
            dep = svc.deploy()
            dep.restart_policy(condition="on-failure", max_attempts=3)
        d = _build(recipe)
        rp = d["services"]["web"]["deploy"]["restart_policy"]
        assert rp["condition"] == "on-failure"


# =========================================================================
# SUB-ELEMENTS: logging_config
# =========================================================================


class TestLogging:

    def test_basic(self) -> None:
        def recipe(root):
            svc = root.service(name="web", image="nginx")
            svc.logging_config(driver="json-file",
                               options={"max-size": "10m", "max-file": "3"})
        d = _build(recipe)
        log = d["services"]["web"]["logging"]
        assert log["driver"] == "json-file"
        assert log["options"]["max-size"] == "10m"


# =========================================================================
# SUB-ELEMENTS: depends_on_condition
# =========================================================================


class TestDependsOnCondition:

    def test_healthy(self) -> None:
        def recipe(root):
            svc = root.service(name="web", image="nginx")
            svc.depends_on_condition(service="db",
                                     condition="service_healthy")
        d = _build(recipe)
        dep = d["services"]["web"]["depends_on"]["db"]
        assert dep["condition"] == "service_healthy"

    def test_restart_false(self) -> None:
        def recipe(root):
            svc = root.service(name="web", image="nginx")
            svc.depends_on_condition(service="db", restart=False)
        d = _build(recipe)
        assert d["services"]["web"]["depends_on"]["db"]["restart"] is False


# =========================================================================
# TOP-LEVEL: NETWORKS
# =========================================================================


class TestNetwork:

    def test_basic(self) -> None:
        d = _build(lambda r: r.network(name="frontend", driver="bridge"))
        assert d["networks"]["frontend"]["driver"] == "bridge"

    def test_external(self) -> None:
        d = _build(lambda r: r.network(name="ext", external=True))
        assert d["networks"]["ext"]["external"] is True

    def test_empty(self) -> None:
        d = _build(lambda r: r.network(name="default"))
        assert "default" in d["networks"]


# =========================================================================
# TOP-LEVEL: VOLUMES
# =========================================================================


class TestVolume:

    def test_basic(self) -> None:
        d = _build(lambda r: r.volume(name="pgdata"))
        assert "pgdata" in d["volumes"]

    def test_with_driver(self) -> None:
        d = _build(lambda r: r.volume(name="nfs", driver="local",
                                       driver_opts={"type": "nfs"}))
        vol = d["volumes"]["nfs"]
        assert vol["driver"] == "local"
        assert vol["driver_opts"]["type"] == "nfs"


# =========================================================================
# TOP-LEVEL: CONFIGS / SECRETS
# =========================================================================


class TestConfig:

    def test_file(self) -> None:
        d = _build(lambda r: r.config(name="nginx", file="./nginx.conf"))
        assert d["configs"]["nginx"]["file"] == "./nginx.conf"


class TestSecret:

    def test_file(self) -> None:
        d = _build(lambda r: r.secret(name="cert", file="./cert.pem"))
        assert d["secrets"]["cert"]["file"] == "./cert.pem"

    def test_external(self) -> None:
        d = _build(lambda r: r.secret(name="db_pass", external=True))
        assert d["secrets"]["db_pass"]["external"] is True


# =========================================================================
# INTEGRATION
# =========================================================================


class TestFullStack:

    def test_yaml_round_trip(self) -> None:
        class FullStack(ComposeApp):
            def recipe(self, root):
                web = root.service(
                    name="web", image="nginx:alpine", restart="always",
                    ports=["80:80"],
                    labels={"app": "web"})
                web.depends_on_condition(service="api",
                                         condition="service_healthy")

                api = root.service(
                    name="api", image="myapp:latest",
                    ports=["8080:8080"],
                    environment={"DB_HOST": "db"})
                api.healthcheck(test="curl -f http://localhost:8080/health",
                                interval="10s")

                root.service(
                    name="db", image="postgres:16",
                    environment={"POSTGRES_PASSWORD": "secret"},
                    volumes=["pgdata:/var/lib/postgresql/data"])

                root.volume(name="pgdata")
                root.network(name="backend", driver="bridge")

        stack = FullStack()
        yaml_str = stack.to_yaml()
        parsed = yaml.safe_load(yaml_str)

        assert len(parsed["services"]) == 3
        assert parsed["services"]["web"]["ports"] == ["80:80"]
        assert parsed["services"]["db"]["environment"]["POSTGRES_PASSWORD"] == "secret"
        assert "pgdata" in parsed["volumes"]
        assert parsed["networks"]["backend"]["driver"] == "bridge"
