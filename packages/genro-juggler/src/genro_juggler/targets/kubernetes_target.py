# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""K8sTarget — apply resources to a Kubernetes cluster via API.

Uses the official kubernetes Python client with server-side apply
(PATCH with fieldManager) for idempotent resource management.

Requires: pip install kubernetes
"""

from __future__ import annotations

from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException
from kubernetes.dynamic import DynamicClient

from .base import TargetBase

# apiVersion → API group mapping for common resources
_API_MAPPING = {
    "v1": "",
    "apps/v1": "apps",
    "batch/v1": "batch",
    "networking.k8s.io/v1": "networking.k8s.io",
}


class K8sTarget(TargetBase):
    """Target that applies resources to a Kubernetes cluster.

    Uses server-side apply (PATCH) for idempotent operations.
    Supports all standard resource types via dynamic client.

    Args:
        kubeconfig: Path to kubeconfig file (None = default).
        context: Kubernetes context name (None = current).
        namespace: Default namespace (overridden by resource metadata).
        field_manager: Field manager name for server-side apply.
        dry_run: If True, validate without applying.
    """

    def __init__(self, kubeconfig: str | None = None,
                 context: str | None = None,
                 namespace: str = "default",
                 field_manager: str = "genro-juggler",
                 dry_run: bool = False) -> None:
        if kubeconfig:
            config.load_kube_config(config_file=kubeconfig, context=context)
        else:
            try:
                config.load_incluster_config()
            except config.ConfigException:
                config.load_kube_config(context=context)

        self._api_client = client.ApiClient()
        self._dynamic = DynamicClient(self._api_client)
        self._namespace = namespace
        self._field_manager = field_manager
        self._dry_run = dry_run

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Apply a resource via server-side apply (PATCH).

        Args:
            resource: Kubernetes resource dict with apiVersion, kind, metadata, spec.

        Returns:
            Dict with status, kind, name, namespace.
        """
        api_version = resource.get("apiVersion", "v1")
        kind = resource.get("kind", "")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        namespace = metadata.get("namespace", self._namespace)

        resource_api = self._dynamic.resources.get(
            api_version=api_version, kind=kind,
        )

        try:
            result = resource_api.server_side_apply(
                body=resource,
                name=name,
                namespace=namespace,
                field_manager=self._field_manager,
                dry_run="All" if self._dry_run else None,
            )
            return {
                "status": "applied",
                "kind": kind,
                "name": name,
                "namespace": namespace,
                "resource_version": result.metadata.resourceVersion,
            }
        except ApiException as e:
            return {
                "status": "error",
                "kind": kind,
                "name": name,
                "error": str(e),
                "code": e.status,
            }

    def delete(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Delete a resource from the cluster."""
        api_version = resource.get("apiVersion", "v1")
        kind = resource.get("kind", "")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "")
        namespace = metadata.get("namespace", self._namespace)

        resource_api = self._dynamic.resources.get(
            api_version=api_version, kind=kind,
        )

        try:
            resource_api.delete(name=name, namespace=namespace)
            return {"status": "deleted", "kind": kind, "name": name}
        except ApiException as e:
            return {"status": "error", "kind": kind, "name": name,
                    "error": str(e), "code": e.status}

    def status(self) -> dict[str, Any]:
        """Get cluster connection status."""
        try:
            v1 = client.VersionApi(self._api_client)
            info = v1.get_code()
            return {
                "status": "connected",
                "server_version": f"{info.major}.{info.minor}",
                "platform": info.platform,
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
