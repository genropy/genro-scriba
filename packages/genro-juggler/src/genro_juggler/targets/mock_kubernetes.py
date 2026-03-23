# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""MockK8sTarget — simulates a Kubernetes API server for testing.

Accepts the same apply/delete calls as K8sTarget but stores resources
in memory and logs every operation. Useful for validating the full
juggler pipeline without a live cluster.
"""

from __future__ import annotations

import time
from typing import Any

from .base import TargetBase


class MockK8sTarget(TargetBase):
    """In-memory Kubernetes API mock. Logs operations, stores resources.

    Args:
        verbose: Print operations to stdout.
        server_version: Simulated server version string.
    """

    def __init__(self, verbose: bool = True,
                 server_version: str = "1.29.0") -> None:
        self._verbose = verbose
        self._server_version = server_version
        self._store: dict[str, dict[str, Any]] = {}
        self._log: list[dict[str, Any]] = []
        self._version_counter = 0

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Store a resource and return a realistic response."""
        kind = resource.get("kind", "Unknown")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "unnamed")
        namespace = metadata.get("namespace", "default")

        self._version_counter += 1
        key = f"{kind}/{namespace}/{name}"
        self._store[key] = resource

        result = {
            "status": "applied",
            "kind": kind,
            "name": name,
            "namespace": namespace,
            "resource_version": str(self._version_counter),
        }

        self._record("apply", key, result)
        return result

    def delete(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Remove a resource from the store."""
        kind = resource.get("kind", "Unknown")
        metadata = resource.get("metadata", {})
        name = metadata.get("name", "unnamed")
        namespace = metadata.get("namespace", "default")

        key = f"{kind}/{namespace}/{name}"
        self._store.pop(key, None)

        result = {"status": "deleted", "kind": kind, "name": name,
                  "namespace": namespace}

        self._record("delete", key, result)
        return result

    def status(self) -> dict[str, Any]:
        """Return simulated cluster status."""
        return {
            "status": "connected",
            "server_version": self._server_version,
            "platform": "mock",
            "resources": len(self._store),
        }

    def get_applied(self) -> dict[str, dict[str, Any]]:
        """Return all resources currently in the store."""
        return dict(self._store)

    def get_log(self) -> list[dict[str, Any]]:
        """Return the full operation log."""
        return list(self._log)

    def _record(self, operation: str, key: str,
                result: dict[str, Any]) -> None:
        entry = {
            "timestamp": time.time(),
            "operation": operation,
            "key": key,
            "result": result,
        }
        self._log.append(entry)

        if self._verbose:
            print(f"[MockK8s] {operation.upper():6s} {key}"
                  f" → {result['status']}")
