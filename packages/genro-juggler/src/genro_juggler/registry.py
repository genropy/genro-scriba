# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""App registry — name → {port, token} mapping for REPL connections.

Same pattern as genro-textual registry: JSON file in temp directory
with file locking for concurrent access.
"""

from __future__ import annotations

import fcntl
import json
import os
import socket
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any

REGISTRY_DIR = Path(tempfile.gettempdir()) / f"genro_juggler_{os.getuid()}"
REGISTRY_FILE = REGISTRY_DIR / "registry.json"


def find_free_port() -> int:
    """Find a free port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def register_app(name: str, port: int, token: str = "") -> None:
    """Register an app in the registry."""
    with _locked_registry(write=True) as reg:
        reg[name] = {"port": port, "token": token}


def get_app_info(name: str) -> dict[str, Any] | None:
    """Get {port, token} for a registered app."""
    with _locked_registry() as reg:
        return reg.get(name)


def list_apps() -> dict[str, dict[str, Any]]:
    """List all registered apps."""
    with _locked_registry() as reg:
        return dict(reg)


def unregister_app(name: str) -> None:
    """Remove an app from the registry."""
    with _locked_registry(write=True) as reg:
        reg.pop(name, None)


@contextmanager
def _locked_registry(write: bool = False):
    """Context manager with file locking for registry access."""
    REGISTRY_DIR.mkdir(parents=True, exist_ok=True)

    if not REGISTRY_FILE.exists():
        REGISTRY_FILE.write_text("{}", encoding="utf-8")

    mode = "r+" if write else "r"
    with open(REGISTRY_FILE, mode, encoding="utf-8") as f:
        lock_type = fcntl.LOCK_EX if write else fcntl.LOCK_SH
        fcntl.flock(f, lock_type)
        try:
            f.seek(0)
            content = f.read().strip()
            reg = json.loads(content) if content else {}
            yield reg
            if write:
                f.seek(0)
                f.truncate()
                json.dump(reg, f, indent=2)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
