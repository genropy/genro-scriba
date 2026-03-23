# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Remote control protocol for JugglerApp.

Same protocol as genro-textual: socket + pickle + token auth.
Allows REPL or external tools to control a running JugglerApp.

Frame format: 4-byte big-endian length header + pickle payload.
Max message size: 16MB.

Commands:
    ("__status__",)              → target status dict
    ("__yaml__", slot_name)      → compiled YAML string
    ("__apply__", slot_name)     → apply slot to target
    ("__apply_all__",)           → apply all slots
    ("__data_get__", path)       → read data value
    ("__data_set__", path, val)  → set data value (triggers reactive apply)
    ("__slots__",)               → list of slot names
    ("__quit__",)                → shutdown
"""

from __future__ import annotations

import pickle
import secrets
import socket
import struct
import threading
from typing import Any

_MAX_MESSAGE = 16 * 1024 * 1024  # 16MB


def _send_framed(sock: socket.socket, data: bytes) -> None:
    """Send a length-prefixed message."""
    header = struct.pack(">I", len(data))
    sock.sendall(header + data)


def _recv_framed(sock: socket.socket) -> bytes:
    """Receive a length-prefixed message."""
    header = b""
    while len(header) < 4:
        chunk = sock.recv(4 - len(header))
        if not chunk:
            raise ConnectionError("Connection closed")
        header += chunk
    length = struct.unpack(">I", header)[0]
    if length > _MAX_MESSAGE:
        raise ValueError(f"Message too large: {length}")
    data = b""
    while len(data) < length:
        chunk = sock.recv(min(length - len(data), 65536))
        if not chunk:
            raise ConnectionError("Connection closed")
        data += chunk
    return data


class RemoteServer:
    """Socket server that accepts commands for a JugglerApp."""

    def __init__(self, app: Any, port: int) -> None:
        self._app = app
        self._port = port
        self._token = secrets.token_hex(16)
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def token(self) -> str:
        return self._token

    @property
    def port(self) -> int:
        return self._port

    def start(self) -> None:
        """Start server in background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run(self) -> None:
        """Accept connections and handle commands."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", self._port))
        srv.listen(5)
        srv.settimeout(1.0)

        while self._running:
            try:
                conn, _addr = srv.accept()
            except TimeoutError:
                continue
            try:
                self._handle_connection(conn)
            except Exception:
                pass
            finally:
                conn.close()
        srv.close()

    def _handle_connection(self, conn: socket.socket) -> None:
        """Handle one connection: auth + command."""
        data = _recv_framed(conn)
        token, cmd = pickle.loads(data)

        if token != self._token:
            _send_framed(conn, pickle.dumps(("error", "Invalid token")))
            return

        try:
            result = self._dispatch(cmd)
            _send_framed(conn, pickle.dumps(("ok", result)))
        except Exception as e:
            _send_framed(conn, pickle.dumps(("error", str(e))))

    def _dispatch(self, cmd: tuple) -> Any:
        """Dispatch a command to the app."""
        action = cmd[0]

        if action == "__status__":
            return self._app.status()

        if action == "__yaml__":
            return self._app.to_yaml(cmd[1])

        if action == "__apply__":
            return self._app.apply(cmd[1])

        if action == "__apply_all__":
            return self._app.apply_all()

        if action == "__data_get__":
            return self._app.data[cmd[1]]

        if action == "__data_set__":
            self._app.data[cmd[1]] = cmd[2]
            return {"status": "ok", "path": cmd[1]}

        if action == "__slots__":
            return list(self._app._slots.keys())

        if action == "__quit__":
            self._running = False
            return {"status": "shutting_down"}

        msg = f"Unknown command: {action}"
        raise ValueError(msg)


class RemoteProxy:
    """Client proxy to control a remote JugglerApp."""

    def __init__(self, host: str, port: int, token: str) -> None:
        self._host = host
        self._port = port
        self._token = token

    def _send(self, cmd: tuple) -> Any:
        """Send command and return result."""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((self._host, self._port))
        try:
            message = (self._token, cmd)
            _send_framed(sock, pickle.dumps(message))
            response_data = _recv_framed(sock)
            status, result = pickle.loads(response_data)
            if status == "error":
                raise RuntimeError(f"Remote error: {result}")
            return result
        finally:
            sock.close()

    def status(self) -> dict[str, Any]:
        """Get status of all targets."""
        return self._send(("__status__",))

    def to_yaml(self, slot_name: str) -> str:
        """Get compiled YAML for a slot."""
        return self._send(("__yaml__", slot_name))

    def apply(self, slot_name: str) -> list[dict]:
        """Apply a slot to its target."""
        return self._send(("__apply__", slot_name))

    def apply_all(self) -> dict[str, list[dict]]:
        """Apply all slots."""
        return self._send(("__apply_all__",))

    def data_get(self, path: str) -> Any:
        """Read a data value."""
        return self._send(("__data_get__", path))

    def data_set(self, path: str, value: Any) -> dict:
        """Set a data value (triggers reactive apply)."""
        return self._send(("__data_set__", path, value))

    def slots(self) -> list[str]:
        """List available slots."""
        return self._send(("__slots__",))

    def quit(self) -> dict:
        """Shutdown the remote app."""
        return self._send(("__quit__",))


def connect(host: str = "127.0.0.1", port: int = 0,
            token: str = "") -> RemoteProxy:
    """Connect to a running JugglerApp.

    Args:
        host: Host address.
        port: Server port.
        token: Auth token.

    Returns:
        RemoteProxy for controlling the app.
    """
    return RemoteProxy(host, port, token)
