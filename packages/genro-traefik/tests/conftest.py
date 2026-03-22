# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Shared fixtures for genro-traefik tests."""

from __future__ import annotations

from typing import Any

import pytest

from genro_bag import Bag
from genro_traefik import TraefikApp
from genro_traefik.builders.traefik_builder import TraefikBuilder


@pytest.fixture
def store() -> Bag:
    """A fresh Bag with TraefikBuilder, root traefik node already created."""
    bag = Bag(builder=TraefikBuilder)
    bag.traefik(name="test")
    return bag


@pytest.fixture
def root(store: Bag) -> Any:
    """The traefik root BagNode."""
    return store.get_node("test")


class MinimalProxy(TraefikApp):
    """Minimal proxy for fixture use."""

    def recipe(self, root: Any) -> None:
        root.entryPoint(name="web", address=":80")
        http = root.http()
        routers = http.routers()
        routers.router(name="r1", rule="Host(`test.com`)", service="svc1",
                       entryPoints=["web"])
        svc = http.services().service(name="svc1")
        svc.loadBalancer().server(url="http://localhost:8080")


@pytest.fixture
def minimal_proxy() -> MinimalProxy:
    """A minimal TraefikApp instance."""
    return MinimalProxy()
