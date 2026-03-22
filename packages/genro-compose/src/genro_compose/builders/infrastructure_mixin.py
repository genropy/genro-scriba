# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Top-level infrastructure entities: networks, volumes, configs, secrets.

These are declared at the root level of a Compose file and referenced
by services. They define the shared infrastructure that services use.

Docs: https://docs.docker.com/reference/compose-file/
"""

from __future__ import annotations

from genro_builders.builder import element

from ..compose_compiler import render_attrs


class InfrastructureMixin:
    """Top-level network, volume, config, and secret entities."""

    # =========================================================================
    # NETWORKS
    # =========================================================================

    @element(sub_tags="")
    def network(self,
                name: str = "",
                driver: str = "",
                driver_opts: dict = "",
                external: bool = False,
                internal: bool = False,
                attachable: bool = False,
                enable_ipv6: bool = False,
                labels: dict = "",
                ipam_driver: str = "",
                ipam_config: list = ""):
        """Top-level network definition — a Docker network for services.

        Networks isolate groups of services. By default, Compose creates
        a single network and attaches all services to it. Define custom
        networks for isolation or special drivers.

        **Drivers**:
        - ``"bridge"`` (default): Isolated network on a single host.
        - ``"overlay"``: Multi-host network (Swarm).
        - ``"host"``: Use host networking (no isolation).
        - ``"none"``: No networking.
        - ``"macvlan"``: Assign a MAC address, appear as physical device.

        **External**: ``external=True`` means the network already exists
        outside Compose. Compose will not create or destroy it.

        **Internal**: ``internal=True`` prevents containers from reaching
        the outside world. Useful for backend services.

        **IPAM**: Configure IP address management with ``ipam_driver``
        and ``ipam_config`` (list of dicts with ``subnet``, ``gateway``).
        Example: ``ipam_config=[{"subnet": "172.28.0.0/16"}]``

        Args:
            name: Network name (YAML key).
            driver: Network driver ("bridge", "overlay", "host", etc.).
            driver_opts: Driver-specific options as dict.
            external: True if managed outside Compose.
            internal: True to prevent external access.
            attachable: Allow manual container attachment (Swarm).
            enable_ipv6: Enable IPv6 on this network.
            labels: Network labels as dict.
            ipam_driver: IPAM driver (default: "default").
            ipam_config: IPAM config as list of dicts with subnet/gateway.

        Docs: https://docs.docker.com/reference/compose-file/networks/
        """
        ...

    def compile_network(self, node, result):
        name = node.attr.get("name", node.label)
        attrs = render_attrs(node, self)
        # Restructure ipam_* into nested ipam dict
        ipam: dict = {}
        if "ipam_driver" in attrs:
            ipam["driver"] = attrs.pop("ipam_driver")
        if "ipam_config" in attrs:
            ipam["config"] = attrs.pop("ipam_config")
        if ipam:
            attrs["ipam"] = ipam
        result.setdefault("networks", {})[name] = attrs or None

    # =========================================================================
    # VOLUMES
    # =========================================================================

    @element(sub_tags="")
    def volume(self,
               name: str = "",
               driver: str = "",
               driver_opts: dict = "",
               external: bool = False,
               labels: dict = ""):
        """Top-level named volume — persistent data storage.

        Named volumes persist data across container restarts and removal.
        They are managed by Docker and stored in ``/var/lib/docker/volumes/``.

        **When to use named volumes vs bind mounts**:
        - Named volumes: database data, uploaded files, caches. Managed
          by Docker, portable, works on all platforms.
        - Bind mounts: source code (development), config files. Tied to
          the host filesystem path.

        **External**: ``external=True`` means the volume was created with
        ``docker volume create`` and is managed outside Compose.

        **Drivers**: ``"local"`` (default) stores data on the host.
        Custom drivers enable NFS, cloud storage, etc.

        Args:
            name: Volume name (YAML key).
            driver: Volume driver ("local" is default).
            driver_opts: Driver options as dict (e.g. NFS mount options).
            external: True if managed outside Compose.
            labels: Volume labels as dict.

        Docs: https://docs.docker.com/reference/compose-file/volumes/
        """
        ...

    def compile_volume(self, node, result):
        name = node.attr.get("name", node.label)
        attrs = render_attrs(node, self)
        result.setdefault("volumes", {})[name] = attrs or None

    # =========================================================================
    # CONFIGS
    # =========================================================================

    @element(sub_tags="")
    def config(self,
               name: str = "",
               file: str = "",
               external: bool = False,
               content: str = "",
               template_driver: str = ""):
        """Top-level config — non-sensitive configuration data.

        Configs are mounted read-only into containers. Unlike volumes,
        they are designed for small configuration files (not data storage).

        **When to use configs vs volumes**:
        - Configs: nginx.conf, app settings, templates. Immutable, versioned.
        - Volumes: databases, uploads, logs. Mutable, persistent.

        **File vs Content**: Either load from a file on the host
        (``file="./nginx.conf"``) or define inline (``content="..."``).

        **In services**: Reference with ``configs=["nginx_conf"]`` for
        simple mount, or use long-form for custom target path.

        Args:
            name: Config name (YAML key).
            file: Path to the config file on the host.
            external: True if managed outside Compose.
            content: Inline config content (alternative to file).
            template_driver: Template rendering engine.

        Docs: https://docs.docker.com/reference/compose-file/configs/
        """
        ...

    def compile_config(self, node, result):
        name = node.attr.get("name", node.label)
        attrs = render_attrs(node, self)
        result.setdefault("configs", {})[name] = attrs or None

    # =========================================================================
    # SECRETS
    # =========================================================================

    @element(sub_tags="")
    def secret(self,
               name: str = "",
               file: str = "",
               external: bool = False,
               environment: str = "",
               template_driver: str = ""):
        """Top-level secret — sensitive data (passwords, keys, certs).

        Secrets are mounted read-only at ``/run/secrets/<name>`` inside
        containers. They are never stored in the image or exposed in
        environment variables (which can leak in logs and debug output).

        **When to use secrets vs environment variables**:
        - Secrets: database passwords, API keys, TLS certificates.
          Secure, not visible in ``docker inspect`` or process listing.
        - Environment: non-sensitive config like ``LOG_LEVEL=debug``.

        **File vs Environment**: Load from a file on the host
        (``file="./db_password.txt"``) or from a host environment
        variable (``environment="DB_PASSWORD"``).

        **In services**: Reference with ``secrets=["db_password"]`` for
        default mount at ``/run/secrets/db_password``, or use long-form
        for custom target path, uid, gid, mode.

        Args:
            name: Secret name (YAML key).
            file: Path to the secret file on the host.
            external: True if managed outside Compose (e.g. Swarm secrets).
            environment: Host environment variable containing the secret.
            template_driver: Template rendering engine.

        Docs: https://docs.docker.com/reference/compose-file/secrets/
        """
        ...

    def compile_secret(self, node, result):
        name = node.attr.get("name", node.label)
        attrs = render_attrs(node, self)
        result.setdefault("secrets", {})[name] = attrs or None
