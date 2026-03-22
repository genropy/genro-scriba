# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Deploy configuration sub-elements for Docker Compose services.

The deploy section controls how containers are deployed and managed:
replicas, resource limits, restart policies, rolling updates, and
placement constraints.

In standalone Docker Compose (not Swarm), only ``replicas``,
``resources``, and ``restart_policy`` are honored. The full deploy
spec is used by Docker Swarm and compatible orchestrators.

Docs: https://docs.docker.com/reference/compose-file/deploy/
"""

from __future__ import annotations

from genro_bag.builders import element


class DeployMixin:
    """Deploy, resources, update_config, restart_policy, placement."""

    @element(sub_tags="resources[:1], restart_policy[:1], update_config[:1], rollback_config[:1], placement[:1]")
    def deploy(self,
               replicas: int = 0,
               mode: str = "",
               endpoint_mode: str = "",
               labels: dict = ""):
        """Deployment configuration — how to run and scale the service.

        **Replicas**: Number of container instances. Default: 1.
        ``replicas=3`` runs 3 identical containers behind the service name.

        **Mode**: ``"replicated"`` (default) runs N replicas.
        ``"global"`` runs exactly one container per node (Swarm only).

        **Resources**: Use the ``resources`` sub-element to set CPU/memory
        limits and reservations. Limits are hard ceilings; reservations
        are guaranteed minimums.

        **Restart policy**: Use ``restart_policy`` sub-element for
        fine-grained control (condition, delay, max_attempts, window).
        For simple cases, use ``restart`` on the service directly.

        **Rolling updates**: Use ``update_config`` sub-element to control
        how updates are rolled out (parallelism, delay, order).

        Args:
            replicas: Number of container replicas.
            mode: "replicated" or "global" (Swarm).
            endpoint_mode: "vip" or "dnsrr" (Swarm).
            labels: Labels for the deployed service (Swarm).

        Docs: https://docs.docker.com/reference/compose-file/deploy/
        """
        ...

    # --- Resources ---

    @element(sub_tags="")
    def resources(self,
                  limits_cpus: str = "",
                  limits_memory: str = "",
                  limits_pids: int = 0,
                  reservations_cpus: str = "",
                  reservations_memory: str = "",
                  reservations_devices: list = ""):
        """Resource constraints — CPU, memory, PIDs, devices.

        **Limits** are hard ceilings. If a container exceeds its memory
        limit, it gets OOM-killed. If it exceeds CPU, it gets throttled.

        **Reservations** are guaranteed minimums. The scheduler ensures
        the host has enough resources before placing the container.

        **Common patterns**:
        ``limits_cpus="0.5", limits_memory="512M"`` — half a CPU core,
        512 MB RAM maximum.
        ``reservations_memory="256M"`` — guarantee 256 MB.

        **GPU access**: Use ``reservations_devices`` with capabilities:
        ``[{"driver": "nvidia", "count": 1, "capabilities": ["gpu"]}]``

        Args:
            limits_cpus: CPU limit as decimal (e.g. "0.5").
            limits_memory: Memory limit (e.g. "512M", "1G").
            limits_pids: Max number of PIDs.
            reservations_cpus: Guaranteed CPU (e.g. "0.25").
            reservations_memory: Guaranteed memory (e.g. "256M").
            reservations_devices: Device reservations (e.g. GPU).

        Docs: https://docs.docker.com/reference/compose-file/deploy/#resources
        """
        ...

    def compile_resources(self, node, result):
        """Render resources as nested limits/reservations dicts."""
        res: dict = {}
        attrs = node.attr
        limits: dict = {}
        reservations: dict = {}
        if attrs.get("limits_cpus"):
            limits["cpus"] = attrs["limits_cpus"]
        if attrs.get("limits_memory"):
            limits["memory"] = attrs["limits_memory"]
        if attrs.get("limits_pids"):
            limits["pids"] = attrs["limits_pids"]
        if attrs.get("reservations_cpus"):
            reservations["cpus"] = attrs["reservations_cpus"]
        if attrs.get("reservations_memory"):
            reservations["memory"] = attrs["reservations_memory"]
        if attrs.get("reservations_devices"):
            reservations["devices"] = attrs["reservations_devices"]
        if limits:
            res["limits"] = limits
        if reservations:
            res["reservations"] = reservations
        result["resources"] = res

    # --- Restart policy ---

    @element(sub_tags="")
    def restart_policy(self,
                       condition: str = "any",
                       delay: str = "",
                       max_attempts: int = 0,
                       window: str = ""):
        """Restart policy — when and how to restart failed containers.

        This is the deploy-level restart policy, used by Swarm and
        ``docker compose up``. For simpler use cases, the service-level
        ``restart`` attribute ("always", "on-failure", etc.) is sufficient.

        **Conditions**:
        - ``"any"`` (default): Always restart.
        - ``"on-failure"``: Only on non-zero exit.
        - ``"none"``: Never restart.

        **Window**: The evaluation window. If a container fails
        ``max_attempts`` times within ``window``, it stays down.

        Args:
            condition: "any", "on-failure", "none".
            delay: Time between restart attempts (e.g. "5s").
            max_attempts: Max restarts before giving up. 0 = unlimited.
            window: Time window for counting attempts (e.g. "120s").

        Docs: https://docs.docker.com/reference/compose-file/deploy/#restart_policy
        """
        ...

    # --- Update config ---

    @element(sub_tags="")
    def update_config(self,
                      parallelism: int = 0,
                      delay: str = "",
                      failure_action: str = "",
                      monitor: str = "",
                      max_failure_ratio: float = 0.0,
                      order: str = ""):
        """Rolling update configuration — how to roll out changes.

        Controls how Compose/Swarm updates running containers when the
        service definition changes.

        **Order**:
        - ``"stop-first"`` (default): Stop old container, then start new.
          Brief downtime but safe.
        - ``"start-first"``: Start new container, then stop old.
          Zero downtime but requires both to run simultaneously.

        **Parallelism**: How many containers to update at once.
        ``parallelism=1`` (default) updates one at a time.

        Args:
            parallelism: Number of containers to update simultaneously.
            delay: Delay between updating groups (e.g. "10s").
            failure_action: "continue", "rollback", or "pause".
            monitor: Duration to monitor after update (e.g. "30s").
            max_failure_ratio: Tolerated failure rate (0.0 to 1.0).
            order: "stop-first" or "start-first".

        Docs: https://docs.docker.com/reference/compose-file/deploy/#update_config
        """
        ...

    # --- Rollback config ---

    @element(sub_tags="")
    def rollback_config(self,
                        parallelism: int = 0,
                        delay: str = "",
                        failure_action: str = "",
                        monitor: str = "",
                        max_failure_ratio: float = 0.0,
                        order: str = ""):
        """Rollback configuration — how to rollback a failed update.

        Same options as ``update_config`` but applied when rolling back
        to the previous version after a failed update.

        Args:
            parallelism: Containers to rollback simultaneously.
            delay: Delay between rollback groups.
            failure_action: "continue" or "pause".
            monitor: Duration to monitor after rollback.
            max_failure_ratio: Tolerated failure rate.
            order: "stop-first" or "start-first".

        Docs: https://docs.docker.com/reference/compose-file/deploy/#rollback_config
        """
        ...

    # --- Placement ---

    @element(sub_tags="")
    def placement(self,
                  constraints: list = "",
                  preferences: list = "",
                  max_replicas_per_node: int = 0):
        """Placement constraints — where containers can run.

        **Constraints** filter which nodes can run this service:
        ``["node.role==manager", "node.labels.zone==us-east"]``

        **Preferences** influence placement spread:
        ``[{"spread": "node.labels.zone"}]`` spreads containers
        across zones evenly.

        Args:
            constraints: Placement constraint expressions.
            preferences: Placement preference rules.
            max_replicas_per_node: Max replicas per Swarm node.

        Docs: https://docs.docker.com/reference/compose-file/deploy/#placement
        """
        ...
