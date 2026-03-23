# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""AnsibleTarget — execute playbooks via ansible-runner.

Receives compiled playbook dicts (list of plays) and runs them
directly via ansible_runner.run() without intermediate YAML files.

Requires: pip install ansible-runner
"""

from __future__ import annotations

from typing import Any

import ansible_runner

from .base import TargetBase


class AnsibleTarget(TargetBase):
    """Target that executes Ansible playbooks via ansible-runner.

    Args:
        inventory: Inventory file path or inline inventory string.
        private_data_dir: Working directory for ansible-runner.
            Created automatically if not specified.
        extra_vars: Additional variables passed to all playbooks.
    """

    def __init__(self, inventory: str | None = None,
                 private_data_dir: str | None = None,
                 extra_vars: dict[str, Any] | None = None) -> None:
        self._inventory = inventory
        self._private_data_dir = private_data_dir
        self._extra_vars = extra_vars or {}

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Execute a playbook (single play dict or list of plays).

        Args:
            resource: A play dict or list of play dicts.

        Returns:
            Dict with status, rc, stdout, stats.
        """
        if isinstance(resource, dict):
            playbook = [resource]
        elif isinstance(resource, list):
            playbook = resource
        else:
            return {"status": "error", "error": f"Unexpected type: {type(resource)}"}

        runner_kwargs: dict[str, Any] = {"playbook": playbook}

        if self._inventory:
            runner_kwargs["inventory"] = self._inventory
        if self._private_data_dir:
            runner_kwargs["private_data_dir"] = self._private_data_dir
        if self._extra_vars:
            runner_kwargs["extravars"] = self._extra_vars

        result = ansible_runner.run(**runner_kwargs)

        return {
            "status": result.status,
            "rc": result.rc,
            "stats": result.stats,
        }

    def status(self) -> dict[str, Any]:
        """Check ansible-runner availability."""
        try:
            version = ansible_runner.__version__
            return {"status": "available", "ansible_runner_version": version}
        except Exception as e:
            return {"status": "error", "error": str(e)}
