# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for traefik_compiler module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from genro_bag import Bag
from genro_builders import BuilderBag
from genro_traefik.builders.traefik_builder import TraefikBuilder
from genro_traefik.traefik_compiler import (
    TraefikCompiler,
    compile_default,
    compile_to_dict,
    render_attrs,
    walk,
)


# ---------------------------------------------------------------------------
# compile_to_dict
# ---------------------------------------------------------------------------


class TestCompileToDict:

    def test_non_bag_root_returns_empty(self) -> None:
        node = MagicMock()
        node.value = "not a bag"
        store = BuilderBag(builder=TraefikBuilder)
        assert compile_to_dict(node, store.builder) == {}

    def test_root_without_value_attr(self) -> None:
        bag = Bag()
        store = BuilderBag(builder=TraefikBuilder)
        assert compile_to_dict(bag, store.builder) == {}

    def test_compiles_bagnode(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.entryPoint(name="web", address=":80")
        result = compile_to_dict(root, store.builder)
        assert "entryPoints" in result
        assert result["entryPoints"]["web"]["address"] == ":80"


# ---------------------------------------------------------------------------
# walk
# ---------------------------------------------------------------------------


class TestWalk:

    def test_walks_all_children(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.entryPoint(name="web", address=":80")
        root.entryPoint(name="websecure", address=":443")
        root_value = root.get_value(static=True)
        result = walk(root_value, store.builder)
        assert "web" in result.get("entryPoints", {})
        assert "websecure" in result.get("entryPoints", {})

    def test_uses_compile_method(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.api(dashboard=True)
        root_value = root.get_value(static=True)
        result = walk(root_value, store.builder)
        assert "api" in result
        assert result["api"]["dashboard"] is True

    def test_compile_default_for_unknown_tag(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="DEBUG", format="json")
        root_value = root.get_value(static=True)
        result = walk(root_value, store.builder)
        assert "log" in result
        assert result["log"]["level"] == "DEBUG"


# ---------------------------------------------------------------------------
# compile_default
# ---------------------------------------------------------------------------


class TestCompileDefault:

    def test_uses_tag_as_key(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="INFO")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result: dict[str, Any] = {}
        compile_default(node, result, store.builder)
        assert "log" in result

    def test_includes_attrs(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.ping(entryPoint="traefik")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result: dict[str, Any] = {}
        compile_default(node, result, store.builder)
        assert result["ping"]["entryPoint"] == "traefik"


# ---------------------------------------------------------------------------
# render_attrs
# ---------------------------------------------------------------------------


class TestRenderAttrs:

    def test_simple_attrs(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="INFO", format="json")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result = render_attrs(node, store.builder)
        assert result["level"] == "INFO"
        assert result["format"] == "json"

    def test_skips_name_attr(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.entryPoint(name="web", address=":80")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result = render_attrs(node, store.builder)
        assert "name" not in result
        assert result["address"] == ":80"

    def test_skips_none_values(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="INFO")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result = render_attrs(node, store.builder)
        assert "level" in result

    def test_underscore_creates_nested(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.metrics(prometheus_entryPoint="traefik")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result = render_attrs(node, store.builder)
        assert "prometheus" in result
        assert result["prometheus"]["entryPoint"] == "traefik"

    def test_children_merged(self) -> None:
        store = BuilderBag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        ep = root.entryPoint(name="web", address=":80")
        ep.redirect(to="websecure", scheme="https")
        root_value = root.get_value(static=True)
        node = next(iter(root_value))
        result = render_attrs(node, store.builder)
        assert "http" in result


# ---------------------------------------------------------------------------
# YamlCompilerBase methods (via TraefikCompiler instance)
# ---------------------------------------------------------------------------


class TestCompilerMethods:

    def test_get_compile_method_finds_existing(self) -> None:
        compiler = TraefikCompiler()
        store = BuilderBag(builder=TraefikBuilder)
        method = compiler._get_compile_method(store.builder, "entryPoint")
        assert method is not None
        assert callable(method)

    def test_get_compile_method_returns_none_for_missing(self) -> None:
        compiler = TraefikCompiler()
        store = BuilderBag(builder=TraefikBuilder)
        method = compiler._get_compile_method(store.builder, "nonexistent_xyz")
        assert method is None

    def test_to_yaml_value_comma_separated(self) -> None:
        compiler = TraefikCompiler()
        assert compiler._to_yaml_value("a, b, c") == ["a", "b", "c"]

    def test_to_yaml_value_list_passthrough(self) -> None:
        compiler = TraefikCompiler()
        assert compiler._to_yaml_value(["a", "b"]) == ["a", "b"]

    def test_to_yaml_value_single_string(self) -> None:
        compiler = TraefikCompiler()
        assert compiler._to_yaml_value("hello") == "hello"

    def test_to_yaml_value_non_string(self) -> None:
        compiler = TraefikCompiler()
        assert compiler._to_yaml_value(42) == 42
        assert compiler._to_yaml_value(True) is True

    def test_to_yaml_value_empty_parts_filtered(self) -> None:
        compiler = TraefikCompiler()
        assert compiler._to_yaml_value("a,,b") == ["a", "b"]
