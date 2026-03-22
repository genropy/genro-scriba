# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""ComposeBuilder - Docker Compose configuration as a semantic Bag builder.

The builder is composed from domain-specific mixins:
- ServiceMixin: service entity + healthcheck, logging, depends_on
- BuildMixin: build configuration sub-element
- DeployMixin: deploy + resources + restart_policy + update_config + placement
- InfrastructureMixin: network, volume, config, secret (top-level)

Each @element docstring is an encyclopedic reference for the corresponding
Docker Compose concept. Reading the builder teaches Docker Compose.

Docs: https://docs.docker.com/reference/compose-file/
"""

from __future__ import annotations

from genro_bag import Bag
from genro_builders import BagBuilderBase
from genro_builders.builder import component, element

from ..compose_compiler import walk
from .build_mixin import BuildMixin
from .deploy_mixin import DeployMixin
from .infrastructure_mixin import InfrastructureMixin
from .service_mixin import ServiceMixin


def _deep_merge(target, source):
    """Recursively merge source dict into target dict."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            _deep_merge(target[key], value)
        else:
            target[key] = value


def _merge_children(node, result, builder):
    """Merge component children into parent dict (transparent component)."""
    node_value = node.get_value(static=True)
    if isinstance(node_value, Bag):
        children = walk(node_value, builder)
        _deep_merge(result, children)


class ComposeBuilder(
    ServiceMixin,
    BuildMixin,
    DeployMixin,
    InfrastructureMixin,
    BagBuilderBase,
):
    """Docker Compose configuration grammar.

    Composed from mixins that model each domain area.
    The root element is ``compose()``, containing services,
    networks, volumes, configs, and secrets.

    Docs: https://docs.docker.com/reference/compose-file/
    """

    # =========================================================================
    # ROOT
    # =========================================================================

    @element(sub_tags="service, network, volume, config, secret, postgres, redis")
    def compose(self,
                name: str = ""):
        """Root of Docker Compose configuration.

        A Compose file defines a multi-container application. The root
        contains five top-level sections:

        - **services**: The containers to run (the core of Compose).
        - **networks**: Custom networks for service isolation.
        - **volumes**: Named volumes for persistent data.
        - **configs**: Non-sensitive configuration files.
        - **secrets**: Sensitive data (passwords, keys, certs).

        Docs: https://docs.docker.com/reference/compose-file/
        """
        ...

    # =========================================================================
    # COMPONENTS — reusable service patterns
    # =========================================================================

    def compile_postgres(self, node, result):
        """Merge postgres component into parent (transparent)."""
        _merge_children(node, result, self)

    @component(sub_tags="")
    def postgres(self, c, name="db", version="16-alpine",
                 db_name="", user="", password="", **_kw):
        """PostgreSQL service with healthcheck and named volume.

        Args:
            name: Service and volume base name (default: "db").
            version: PostgreSQL image tag (default: "16-alpine").
            db_name: Database name (POSTGRES_DB).
            user: Database user (POSTGRES_USER).
            password: Database password (POSTGRES_PASSWORD).
        """
        svc = c.service(name=name, image=f"postgres:{version}",
                        restart="always",
                        environment={"POSTGRES_DB": db_name,
                                     "POSTGRES_USER": user,
                                     "POSTGRES_PASSWORD": password},
                        volumes=[f"{name}data:/var/lib/postgresql/data"])
        svc.healthcheck(test=f"pg_isready -U {user} -d {db_name}",
                        interval="10s", timeout="5s", retries=5)
        c.volume(name=f"{name}data")

    def compile_redis(self, node, result):
        """Merge redis component into parent (transparent)."""
        _merge_children(node, result, self)

    @component(sub_tags="")
    def redis(self, c, name="cache", version="7-alpine", **_kw):
        """Redis cache service with named volume.

        Args:
            name: Service and volume base name (default: "cache").
            version: Redis image tag (default: "7-alpine").
        """
        c.service(name=name, image=f"redis:{version}",
                  restart="always", volumes=[f"{name}data:/data"])
        c.volume(name=f"{name}data")
