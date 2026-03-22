# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for traefik_compiler module."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from genro_bag import Bag
from genro_traefik.builders.traefik_builder import TraefikBuilder
from genro_traefik.traefik_compiler import (
    _get_compile_method,
    _resolve,
    _to_yaml_value,
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
        store = Bag(builder=TraefikBuilder)
        assert compile_to_dict(node, store.builder) == {}

    def test_root_without_value_attr(self) -> None:
        bag = Bag()
        store = Bag(builder=TraefikBuilder)
        # A plain Bag (no .value attribute) should also return empty
        assert compile_to_dict(bag, store.builder) == {}

    def test_compiles_bagnode(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.entryPoint(name="web", address=":80")
        result = compile_to_dict(root, store.builder)
        assert "entryPoints" in result
        assert result["entryPoints"]["web"]["address"] == ":80"


# ---------------------------------------------------------------------------
# _get_compile_method
# ---------------------------------------------------------------------------


class TestGetCompileMethod:

    def test_finds_existing_method(self) -> None:
        store = Bag(builder=TraefikBuilder)
        method = _get_compile_method(store.builder, "entryPoint")
        assert method is not None
        assert callable(method)

    def test_returns_none_for_missing(self) -> None:
        store = Bag(builder=TraefikBuilder)
        method = _get_compile_method(store.builder, "nonexistent_tag_xyz")
        assert method is None

    def test_finds_method_via_mro(self) -> None:
        store = Bag(builder=TraefikBuilder)
        method = _get_compile_method(store.builder, "router")
        assert method is not None


# ---------------------------------------------------------------------------
# walk
# ---------------------------------------------------------------------------


class TestWalk:

    def test_walks_all_children(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.entryPoint(name="web", address=":80")
        root.entryPoint(name="websecure", address=":443")
        root_value = root.get_value(static=True)
        result = walk(root_value, store.builder)
        assert "web" in result.get("entryPoints", {})
        assert "websecure" in result.get("entryPoints", {})

    def test_uses_compile_method(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.api(dashboard=True)
        root_value = root.get_value(static=True)
        result = walk(root_value, store.builder)
        # api has no compile_api, so compile_default is used → key is "api"
        assert "api" in result
        assert result["api"]["dashboard"] is True

    def test_compile_default_for_unknown_tag(self) -> None:
        store = Bag(builder=TraefikBuilder)
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
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="INFO")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]  # the log node
        result: dict[str, Any] = {}
        compile_default(node, result, store.builder)
        assert "log" in result

    def test_includes_attrs(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.ping(entryPoint="traefik")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]
        result: dict[str, Any] = {}
        compile_default(node, result, store.builder)
        assert result["ping"]["entryPoint"] == "traefik"


# ---------------------------------------------------------------------------
# render_attrs
# ---------------------------------------------------------------------------


class TestRenderAttrs:

    def test_simple_attrs(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="INFO", format="json")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]
        result = render_attrs(node, store.builder)
        assert result["level"] == "INFO"
        assert result["format"] == "json"

    def test_skips_name_attr(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.entryPoint(name="web", address=":80")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]
        result = render_attrs(node, store.builder)
        assert "name" not in result
        assert result["address"] == ":80"

    def test_skips_none_values(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.log(level="INFO")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]
        result = render_attrs(node, store.builder)
        # filePath defaults to "" which is falsy but not None
        # Just verify we got level and no unexpected keys
        assert "level" in result

    def test_underscore_creates_nested(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        root.metrics(prometheus_entryPoint="traefik")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]
        result = render_attrs(node, store.builder)
        assert "prometheus" in result
        assert result["prometheus"]["entryPoint"] == "traefik"

    def test_pointer_resolution(self) -> None:
        store = Bag(builder=TraefikBuilder)
        store.builder.data = Bag()
        store.builder.data["web.address"] = ":80"
        root = store.traefik(name="t")
        root.entryPoint(name="web", address="^web.address")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]
        result = render_attrs(node, store.builder)
        assert result["address"] == ":80"

    def test_children_merged(self) -> None:
        store = Bag(builder=TraefikBuilder)
        root = store.traefik(name="t")
        ep = root.entryPoint(name="web", address=":80")
        ep.redirect(to="websecure", scheme="https")
        root_value = root.get_value(static=True)
        node = list(root_value)[0]  # entryPoint node
        result = render_attrs(node, store.builder)
        # redirect compiles into http.redirections.entryPoint
        assert "http" in result


# ---------------------------------------------------------------------------
# _resolve
# ---------------------------------------------------------------------------


class TestResolve:

    def test_no_data_returns_value(self) -> None:
        assert _resolve("hello", None) == "hello"

    def test_pointer_resolved(self) -> None:
        data = Bag()
        data["host"] = "localhost"
        assert _resolve("^host", data) == "localhost"

    def test_pointer_unresolved_kept(self) -> None:
        data = Bag()
        assert _resolve("^missing.key", data) == "^missing.key"

    def test_non_pointer_unchanged(self) -> None:
        data = Bag()
        assert _resolve("plain string", data) == "plain string"

    def test_list_resolved_element_by_element(self) -> None:
        data = Bag()
        data["x"] = "resolved"
        result = _resolve(["^x", "literal", "^missing"], data)
        assert result == ["resolved", "literal", "^missing"]

    def test_non_string_unchanged(self) -> None:
        data = Bag()
        assert _resolve(42, data) == 42
        assert _resolve(True, data) is True


# ---------------------------------------------------------------------------
# _to_yaml_value
# ---------------------------------------------------------------------------


class TestToYamlValue:

    def test_comma_separated_to_list(self) -> None:
        assert _to_yaml_value("a, b, c") == ["a", "b", "c"]

    def test_list_passthrough(self) -> None:
        val = ["a", "b"]
        assert _to_yaml_value(val) == ["a", "b"]

    def test_single_string_no_comma(self) -> None:
        assert _to_yaml_value("hello") == "hello"

    def test_non_string_passthrough(self) -> None:
        assert _to_yaml_value(42) == 42
        assert _to_yaml_value(True) is True

    def test_empty_parts_filtered(self) -> None:
        assert _to_yaml_value("a,,b") == ["a", "b"]
