# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""TargetBase — abstract interface for infrastructure targets.

A target receives compiled resource dicts and applies them somewhere:
Kubernetes API, ansible-runner, file system, or any other destination.
"""

from __future__ import annotations

from typing import Any


class TargetBase:
    """Abstract base for infrastructure targets.

    Subclasses implement apply() to push a resource dict to a live system.
    """

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Apply a single resource. Returns the resulting state.

        Args:
            resource: Compiled resource dict (e.g. K8s manifest, Ansible play).

        Returns:
            Result dict with status information.
        """
        raise NotImplementedError

    def apply_many(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Apply multiple resources in order.

        Default: call apply() for each. Override for batch operations.
        """
        return [self.apply(r) for r in resources]

    def delete(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Delete a resource. Returns result status.

        Default: not implemented (not all targets support deletion).
        """
        raise NotImplementedError

    def status(self) -> dict[str, Any]:
        """Get current target status.

        Returns:
            Status dict (target-specific).
        """
        return {"status": "unknown"}
