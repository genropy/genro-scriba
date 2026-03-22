# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Service element and its sub-elements for Docker Compose.

A service is a container to run. It is the core entity of a Compose file.
Most of the configuration lives as attributes on service(); sub-elements
are used only for groups of related settings (healthcheck, logging, etc.).

Docs: https://docs.docker.com/reference/compose-file/services/
"""

from __future__ import annotations

from genro_builders.builder import element

from ..compose_compiler import render_attrs


class ServiceMixin:
    """Service entity and its sub-elements."""

    # =========================================================================
    # SERVICE
    # =========================================================================

    @element(sub_tags=(
        "build_config[:1], healthcheck[:1], deploy[:1],"
        " logging_config[:1], depends_on_condition"
    ))
    def service(self,
                name: str = "",
                # --- Image ---
                image: str = "",
                pull_policy: str = "",
                platform: str = "",
                # --- Container identity ---
                container_name: str = "",
                hostname: str = "",
                domainname: str = "",
                # --- Execution ---
                command: str | list = "",
                entrypoint: str | list = "",
                working_dir: str = "",
                user: str = "",
                group_add: list = "",
                # --- Restart ---
                restart: str = "",
                # --- Ports & exposure ---
                ports: list = "",
                expose: list = "",
                # --- Volumes ---
                volumes: list = "",
                volumes_from: list = "",
                # --- Environment ---
                environment: dict | list = "",
                env_file: list = "",
                # --- Networking ---
                networks: list | dict = "",
                network_mode: str = "",
                links: list = "",
                external_links: list = "",
                extra_hosts: list = "",
                dns: list = "",
                dns_search: list = "",
                dns_opt: list = "",
                # --- Labels & metadata ---
                labels: dict | list = "",
                annotations: dict | list = "",
                # --- Dependencies ---
                depends_on: list | dict = "",
                # --- Secrets & configs ---
                secrets: list = "",
                configs: list = "",
                # --- Security ---
                privileged: bool = False,
                read_only: bool = False,
                cap_add: list = "",
                cap_drop: list = "",
                security_opt: list = "",
                # --- Namespaces ---
                pid: str = "",
                ipc: str = "",
                uts: str = "",
                userns_mode: str = "",
                # --- Terminal ---
                stdin_open: bool = False,
                tty: bool = False,
                init: bool = False,
                # --- Lifecycle ---
                stop_grace_period: str = "",
                stop_signal: str = "",
                # --- Resource limits (shorthand, use deploy.resources for detailed) ---
                cpus: str = "",
                cpu_shares: int = 0,
                cpu_period: int = 0,
                cpu_quota: int = 0,
                cpu_rt_period: str = "",
                cpu_rt_runtime: str = "",
                cpuset: str = "",
                mem_limit: str = "",
                mem_reservation: str = "",
                mem_swappiness: int = -1,
                memswap_limit: str = "",
                pids_limit: int = 0,
                # --- Storage ---
                shm_size: str = "",
                tmpfs: list | str = "",
                devices: list = "",
                device_cgroup_rules: list = "",
                storage_opt: dict = "",
                # --- System ---
                sysctls: dict = "",
                ulimits: dict = "",
                # --- Misc ---
                runtime: str = "",
                scale: int = 0,
                profiles: list = "",
                extends: dict = "",
                isolation: str = "",
                oom_kill_disable: bool = False,
                oom_score_adj: int = 0,
                cgroup: str = "",
                cgroup_parent: str = "",
                ):
        """Service definition — a container to run.

        A service is the fundamental unit of a Compose application. Each
        service defines one container image and its runtime configuration.
        Compose starts, stops, and scales services together.

        **Image vs Build**: Either set ``image`` to pull a pre-built image,
        or use the ``build_config`` sub-element to build from a Dockerfile.
        You can set both: ``image`` names the built image, ``build_config``
        defines how to build it.

        **Ports**: List of port mappings as strings. Formats:
        ``"8080:80"`` (host:container), ``"8080:80/udp"`` (with protocol),
        ``"127.0.0.1:8080:80"`` (bind to host IP).

        **Volumes**: List of volume mounts as strings. Formats:
        ``"./data:/app/data"`` (bind mount), ``"dbdata:/var/lib/db"``
        (named volume), ``"./conf:/etc/conf:ro"`` (read-only).

        **Environment**: Dict ``{"KEY": "value"}`` or list ``["KEY=value"]``.
        For loading from files, use ``env_file=["path/.env"]``.

        **Networks**: List of network names ``["frontend", "backend"]``, or
        dict with per-network config ``{"backend": {"aliases": ["api"]}}``.
        Use ``network_mode="host"`` for host networking.

        **Dependencies**: Simple list ``depends_on=["db", "cache"]`` for
        startup ordering. For health-based dependencies, use the
        ``depends_on_condition`` sub-element.

        **Restart policies**: ``"no"`` (default), ``"always"``,
        ``"on-failure"``, ``"unless-stopped"``.

        **Resource limits**: For simple cases, use ``cpus``, ``mem_limit``
        directly. For production deployments, use the ``deploy`` sub-element
        with ``resources`` for fine-grained CPU/memory limits and reservations.

        **Security**: ``privileged=True`` gives full host access (avoid in
        production). Use ``cap_add``/``cap_drop`` for fine-grained capabilities.
        ``read_only=True`` makes the root filesystem read-only.

        **Namespaces**: ``pid="host"`` shares the host PID namespace (useful
        for debugging). ``network_mode="host"`` uses host networking directly.

        Args:
            name: Service name (YAML key). Used for inter-service DNS.
            image: Container image reference (e.g. "nginx:alpine").
            pull_policy: When to pull: "always", "never", "missing", "build".
            platform: Target platform (e.g. "linux/amd64").
            container_name: Explicit container name (prevents scaling).
            hostname: Container hostname.
            command: Override CMD. String or list.
            entrypoint: Override ENTRYPOINT. String or list.
            working_dir: Working directory inside the container.
            user: User to run as (e.g. "1000:1000", "www-data").
            group_add: Additional groups for the container process.
            restart: Restart policy. One of: no, always, on-failure, unless-stopped.
            ports: Port mappings as list of strings.
            expose: Internal ports to expose (no host mapping).
            volumes: Volume mounts as list of strings.
            volumes_from: Mount volumes from other containers.
            environment: Environment variables as dict or list.
            env_file: Paths to .env files.
            networks: Networks to attach to.
            network_mode: Network mode: host, bridge, none, service:name.
            links: Legacy links to other services.
            extra_hosts: Extra /etc/hosts entries ("host:ip").
            dns: DNS server addresses.
            dns_search: DNS search domains.
            labels: Container labels as dict or list.
            depends_on: Services to start before this one.
            secrets: Secrets to mount (list of names or long-form dicts).
            configs: Configs to mount (list of names or long-form dicts).
            privileged: Run with extended privileges.
            read_only: Read-only root filesystem.
            cap_add: Linux capabilities to add (e.g. ["NET_ADMIN"]).
            cap_drop: Linux capabilities to drop (e.g. ["ALL"]).
            pid: PID namespace mode ("host" or "service:name").
            ipc: IPC namespace mode ("host", "shareable", "service:name").
            stdin_open: Keep STDIN open (docker run -i).
            tty: Allocate a pseudo-TTY (docker run -t).
            init: Run an init process (PID 1) inside the container.
            stop_grace_period: Time to wait before force-killing (e.g. "10s").
            stop_signal: Signal to send for stop (e.g. "SIGTERM").
            cpus: CPU limit as decimal (e.g. "0.5" = half a core).
            mem_limit: Memory limit (e.g. "512m", "1g").
            mem_reservation: Soft memory limit.
            shm_size: Size of /dev/shm (e.g. "256m").
            tmpfs: tmpfs mounts as list or string.
            devices: Host devices to expose (e.g. ["/dev/sda:/dev/xvdc:rwm"]).
            sysctls: Kernel parameters as dict.
            ulimits: Resource limits as dict (e.g. {"nofile": {"soft": 1024, "hard": 65535}}).
            runtime: Container runtime (e.g. "nvidia" for GPU).
            scale: Number of containers (prefer deploy.replicas).
            profiles: Profiles this service belongs to.
            oom_kill_disable: Disable OOM killer for this container.
            oom_score_adj: OOM score adjustment (-1000 to 1000).

        Docs: https://docs.docker.com/reference/compose-file/services/
        """
        ...

    def compile_service(self, node, result):
        _named("services", node, result, self)

    # =========================================================================
    # HEALTHCHECK (sub-element of service)
    # =========================================================================

    @element(sub_tags="")
    def healthcheck(self,
                    test: str | list = "",
                    interval: str = "",
                    timeout: str = "",
                    retries: int = 0,
                    start_period: str = "",
                    start_interval: str = "",
                    disable: bool = False):
        """Health check — how Compose knows if a container is healthy.

        The health status is used by ``depends_on`` with
        ``condition: service_healthy``. Without a healthcheck, Compose can
        only wait for the container to start, not for the application to
        be ready.

        **Test command**: A shell command that returns 0 for healthy,
        non-zero for unhealthy. Common patterns:
        ``"curl -f http://localhost:8080/health"`` (HTTP check),
        ``"pg_isready -U postgres"`` (PostgreSQL),
        ``"redis-cli ping"`` (Redis).

        **Timing**: ``interval`` controls how often the check runs,
        ``timeout`` how long to wait for a response, ``start_period``
        gives the container time to initialize before checks count.

        **Disable**: Set ``disable=True`` to turn off a healthcheck
        inherited from the image's Dockerfile.

        Args:
            test: CMD-SHELL command or CMD list. Exit 0 = healthy.
            interval: Time between checks (e.g. "30s"). Default: 30s.
            timeout: Max wait per check (e.g. "10s"). Default: 30s.
            retries: Consecutive failures before unhealthy. Default: 3.
            start_period: Grace period before first check counts (e.g. "5s").
            start_interval: Time between checks during start_period.
            disable: Disable the healthcheck entirely.

        Docs: https://docs.docker.com/reference/compose-file/services/#healthcheck
        """
        ...

    # healthcheck uses compile_default — tag matches YAML key

    # =========================================================================
    # LOGGING (sub-element of service)
    # =========================================================================

    @element(sub_tags="")
    def logging_config(self,
                       driver: str = "",
                       options: dict = ""):
        """Logging configuration — where container logs go.

        By default, Docker uses the ``json-file`` driver, which stores logs
        as JSON on the host. For production, consider ``syslog``, ``fluentd``,
        or ``awslogs``.

        **Common options** for json-file driver:
        ``{"max-size": "10m", "max-file": "3"}`` limits log file size.

        Args:
            driver: Logging driver ("json-file", "syslog", "fluentd",
                "awslogs", "gcplogs", "none").
            options: Driver-specific options as dict.

        Docs: https://docs.docker.com/reference/compose-file/services/#logging
        """
        ...

    def compile_logging_config(self, node, result):
        result["logging"] = render_attrs(node, self)

    # =========================================================================
    # DEPENDS_ON with condition (sub-element of service)
    # =========================================================================

    @element(sub_tags="")
    def depends_on_condition(self,
                             service: str = "",
                             condition: str = "service_started",
                             restart: bool = True):
        """Dependency with startup condition — wait for a service to be ready.

        Use this instead of the simple ``depends_on`` list when you need
        to wait for a specific condition, not just container start.

        **Conditions**:
        - ``service_started``: Wait for container to start (default).
        - ``service_healthy``: Wait for healthcheck to pass. The target
          service MUST define a healthcheck.
        - ``service_completed_successfully``: Wait for container to exit 0.
          Useful for init/migration containers.

        **Example**: Web service waits for DB to be healthy::

            web = root.service(name="web", image="myapp")
            web.depends_on_condition(service="db",
                                     condition="service_healthy")

        Args:
            service: Target service name.
            condition: One of: service_started, service_healthy,
                service_completed_successfully.
            restart: Restart this service if dependency restarts. Default: True.

        Docs: https://docs.docker.com/reference/compose-file/services/#depends_on
        """
        ...

    def compile_depends_on_condition(self, node, result):
        svc = node.attr.get("service", node.label)
        condition = node.attr.get("condition", "service_started")
        restart_val = node.attr.get("restart", True)
        entry: dict = {"condition": condition}
        if not restart_val:
            entry["restart"] = False
        result.setdefault("depends_on", {})[svc] = entry


def _named(yaml_section, node, result, builder):
    """Render named entity into a YAML section dict."""
    name = node.attr.get("name", node.label)
    result.setdefault(yaml_section, {})[name] = render_attrs(node, builder)
