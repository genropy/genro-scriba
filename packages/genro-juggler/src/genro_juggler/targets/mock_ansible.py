# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""MockAnsibleTarget — simulates ansible-runner for testing.

Accepts the same apply calls as AnsibleTarget but only logs the
plays and tasks without executing anything. Generates realistic
stats based on task count.
"""

from __future__ import annotations

import time
from typing import Any

from .base import TargetBase


class MockAnsibleTarget(TargetBase):
    """In-memory ansible-runner mock. Logs plays/tasks, returns stats.

    Args:
        verbose: Print operations to stdout.
    """

    def __init__(self, verbose: bool = True) -> None:
        self._verbose = verbose
        self._log: list[dict[str, Any]] = []

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Simulate playbook execution. Returns realistic stats."""
        if isinstance(resource, dict):
            plays = [resource]
        elif isinstance(resource, list):
            plays = resource
        else:
            result = {"status": "error",
                      "error": f"Unexpected type: {type(resource)}"}
            self._record("apply", plays=[], result=result)
            return result

        task_count = sum(
            len(play.get("tasks", []))
            for play in plays
        )
        play_count = len(plays)

        stats = {
            "ok": task_count,
            "changed": task_count,
            "unreachable": 0,
            "failed": 0,
            "skipped": 0,
            "rescued": 0,
            "ignored": 0,
        }

        result = {
            "status": "successful",
            "rc": 0,
            "stats": stats,
        }

        self._record("apply", plays=plays, result=result)

        if self._verbose:
            for play in plays:
                play_name = play.get("name", "unnamed")
                hosts = play.get("hosts", "all")
                tasks = play.get("tasks", [])
                print(f"[MockAnsible] PLAY [{play_name}] hosts={hosts}")
                for task in tasks:
                    task_name = task.get("name", "unnamed")
                    module = task.get("module", "?")
                    print(f"[MockAnsible]   TASK [{task_name}] "
                          f"module={module}")
            print(f"[MockAnsible] STATS: {play_count} plays, "
                  f"{task_count} tasks → ok={task_count}")

        return result

    def status(self) -> dict[str, Any]:
        """Return simulated ansible-runner availability."""
        return {"status": "available", "ansible_runner_version": "mock"}

    def get_log(self) -> list[dict[str, Any]]:
        """Return the full operation log."""
        return list(self._log)

    def _record(self, operation: str, plays: list[dict[str, Any]],
                result: dict[str, Any]) -> None:
        self._log.append({
            "timestamp": time.time(),
            "operation": operation,
            "play_count": len(plays),
            "plays": plays,
            "result": result,
        })
