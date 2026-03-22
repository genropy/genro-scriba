# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Basic tests for TraefikApp, compiler, and recipe_from_yaml."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import yaml

from genro_bag import Bag
from genro_traefik import TraefikApp, recipe_from_yaml


class SimpleProxy(TraefikApp):
    """Minimal proxy for testing."""

    def recipe(self, root: Any) -> None:
        root.entryPoint(name="web", address=":80")
        root.entryPoint(name="websecure", address=":443")
        http = root.http()
        http.routers().router(
            name="api", rule="Host(`api.test.com`)",
            service="api-svc", entryPoints=["websecure"],
        )
        svc = http.services().service(name="api-svc")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="http://10.0.0.1:8080")


class PointerProxy(TraefikApp):
    """Proxy using ^ pointers for testing data resolution."""

    def recipe(self, root: Any) -> None:
        root.entryPoint(name="web", address="^web.address")
        http = root.http()
        http.routers().router(
            name="api", rule="^api.rule", service="api-svc",
            entryPoints=["web"],
        )
        svc = http.services().service(name="api-svc")
        svc.loadBalancer().server(url="^api.backend")


class TestTraefikApp:
    """Tests for TraefikApp core functionality."""

    def test_to_yaml_produces_valid_yaml(self) -> None:
        proxy = SimpleProxy()
        output = proxy.to_yaml()
        parsed = yaml.safe_load(output)
        assert isinstance(parsed, dict)
        assert "entryPoints" in parsed
        assert "http" in parsed

    def test_entrypoints_rendered(self) -> None:
        proxy = SimpleProxy()
        parsed = yaml.safe_load(proxy.to_yaml())
        eps = parsed["entryPoints"]
        assert "web" in eps
        assert "websecure" in eps
        assert eps["web"]["address"] == ":80"

    def test_router_rendered(self) -> None:
        proxy = SimpleProxy()
        parsed = yaml.safe_load(proxy.to_yaml())
        routers = parsed["http"]["routers"]
        assert "api" in routers
        assert routers["api"]["rule"] == "Host(`api.test.com`)"
        assert routers["api"]["service"] == "api-svc"

    def test_service_rendered(self) -> None:
        proxy = SimpleProxy()
        parsed = yaml.safe_load(proxy.to_yaml())
        services = parsed["http"]["services"]
        assert "api-svc" in services
        lb = services["api-svc"]["loadBalancer"]
        assert lb["passHostHeader"] is True
        assert len(lb["servers"]) == 1
        assert lb["servers"][0]["url"] == "http://10.0.0.1:8080"

    def test_to_yaml_writes_file(self) -> None:
        proxy = SimpleProxy()
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            path = f.name
        try:
            proxy.to_yaml(path)
            content = Path(path).read_text()
            parsed = yaml.safe_load(content)
            assert "entryPoints" in parsed
        finally:
            Path(path).unlink(missing_ok=True)


class TestProperties:
    """Tests for TraefikApp properties."""

    def test_store_property(self) -> None:
        proxy = SimpleProxy()
        assert proxy.store is not None
        assert isinstance(proxy.store, Bag)

    def test_root_property(self) -> None:
        proxy = SimpleProxy()
        assert proxy.root is not None

    def test_data_property(self) -> None:
        proxy = SimpleProxy()
        assert isinstance(proxy.data, Bag)

    def test_data_setter_with_dict(self) -> None:
        proxy = PointerProxy()
        proxy.data = {"web.address": ":80", "api.rule": "Host(`a.com`)",
                      "api.backend": "http://localhost:8080"}
        parsed = yaml.safe_load(proxy.to_yaml())
        assert parsed["entryPoints"]["web"]["address"] == ":80"

    def test_data_setter_with_bag(self) -> None:
        proxy = PointerProxy()
        new_data = Bag()
        new_data["web.address"] = ":80"
        new_data["api.rule"] = "Host(`a.com`)"
        new_data["api.backend"] = "http://localhost:8080"
        proxy.data = new_data
        parsed = yaml.safe_load(proxy.to_yaml())
        assert parsed["entryPoints"]["web"]["address"] == ":80"

    def test_file_output_property(self) -> None:
        proxy = SimpleProxy()
        assert proxy.file_output is None

    def test_file_output_setter(self) -> None:
        proxy = SimpleProxy()
        proxy.file_output = "/tmp/test.yml"
        assert proxy.file_output == Path("/tmp/test.yml")
        proxy.file_output = None
        assert proxy.file_output is None

    def test_output_is_compiled_yaml(self) -> None:
        proxy = SimpleProxy()
        assert proxy.output is not None
        assert "entryPoints" in proxy.output

    def test_check_returns_list(self) -> None:
        proxy = SimpleProxy()
        errors = proxy.check()
        assert isinstance(errors, list)


class TestDataPointers:
    """Tests for ^ pointer resolution."""

    def test_pointers_resolved(self) -> None:
        proxy = PointerProxy()
        proxy.data["web.address"] = ":80"
        proxy.data["api.rule"] = "Host(`example.com`)"
        proxy.data["api.backend"] = "http://localhost:8080"
        parsed = yaml.safe_load(proxy.to_yaml())
        assert parsed["entryPoints"]["web"]["address"] == ":80"
        assert parsed["http"]["routers"]["api"]["rule"] == "Host(`example.com`)"
        assert parsed["http"]["services"]["api-svc"]["loadBalancer"]["servers"][0]["url"] == "http://localhost:8080"

    def test_unresolved_pointer_produces_empty(self) -> None:
        proxy = PointerProxy()
        # Don't set any data — unresolved pointers produce empty values
        parsed = yaml.safe_load(proxy.to_yaml())
        # entryPoint "web" exists but address is absent (None filtered)
        assert "web" in parsed["entryPoints"]

    def test_data_change_updates_yaml(self) -> None:
        proxy = PointerProxy()
        proxy.data["web.address"] = ":80"
        proxy.data["api.rule"] = "Host(`a.com`)"
        proxy.data["api.backend"] = "http://host1:8080"
        yaml1 = proxy.to_yaml()

        proxy.data["api.backend"] = "http://host2:9090"
        yaml2 = proxy.to_yaml()

        assert "host1:8080" in yaml1
        assert "host2:9090" in yaml2

    def test_to_yaml_writes_file_with_pointers(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            path = f.name
        try:
            proxy = PointerProxy()
            proxy.data["web.address"] = ":80"
            proxy.data["api.rule"] = "Host(`x.com`)"
            proxy.data["api.backend"] = "http://a:1"

            proxy.to_yaml(path)
            content = Path(path).read_text()
            parsed = yaml.safe_load(content)
            assert parsed["entryPoints"]["web"]["address"] == ":80"

            proxy.data["api.backend"] = "http://b:2"
            proxy.to_yaml(path)
            content2 = Path(path).read_text()
            parsed2 = yaml.safe_load(content2)
            assert parsed2["http"]["services"]["api-svc"]["loadBalancer"]["servers"][0]["url"] == "http://b:2"
        finally:
            Path(path).unlink(missing_ok=True)


class TestRecipeFromYaml:
    """Tests for YAML to recipe conversion."""

    def test_generates_valid_python(self) -> None:
        sample = Path(__file__).parent.parent / "examples" / "sample_traefik.yml"
        if not sample.exists():
            return
        code = recipe_from_yaml(sample)
        assert "class MyTraefikConfig(TraefikApp):" in code
        assert "def recipe(self, root):" in code

    def test_from_dict(self) -> None:
        data = {
            "entryPoints": {"web": {"address": ":80"}},
            "http": {
                "routers": {
                    "test": {"rule": "Host(`test.com`)", "service": "svc"},
                },
                "services": {
                    "svc": {"loadBalancer": {"servers": [{"url": "http://localhost:8080"}]}},
                },
            },
        }
        code = recipe_from_yaml(data, class_name="TestConfig")
        assert "class TestConfig(TraefikApp):" in code
        assert 'root.entryPoint(name="web", address=":80")' in code
        assert "Host(`test.com`)" in code
