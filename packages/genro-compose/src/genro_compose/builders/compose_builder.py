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

from genro_builders import BagBuilderBase
from genro_builders.builder import element

from .build_mixin import BuildMixin
from .deploy_mixin import DeployMixin
from .infrastructure_mixin import InfrastructureMixin
from .service_mixin import ServiceMixin


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

    @element(sub_tags="service, network, volume, config, secret")
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
