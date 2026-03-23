# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for remote server/proxy protocol."""

from __future__ import annotations

import time

from genro_juggler import JugglerApp
from genro_juggler.registry import find_free_port
from genro_juggler.remote import RemoteProxy, RemoteServer
from genro_juggler.targets.base import TargetBase


class RecordingTarget(TargetBase):
    def __init__(self):
        self.applied = []

    def apply(self, resource):
        self.applied.append(resource)
        return {"status": "recorded"}

    def status(self):
        return {"status": "recording", "count": len(self.applied)}


class SimpleInfra(JugglerApp):
    def kubernetes_recipe(self, root):
        root.deployment(name="api", image="^api.image")
        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)


class TestRemoteProtocol:

    def _start_server(self):
        """Helper: create app + server, return (app, server, proxy)."""
        recorder = RecordingTarget()
        app = SimpleInfra(
            targets={"kubernetes": recorder},
            data={"api.image": "myapp:v1"},
        )
        port = find_free_port()
        server = RemoteServer(app, port)
        server.start()
        time.sleep(0.1)  # let server start
        proxy = RemoteProxy("127.0.0.1", port, server.token)
        return app, server, proxy, recorder

    def test_status(self) -> None:
        _app, server, proxy, _recorder = self._start_server()
        try:
            result = proxy.status()
            assert "kubernetes" in result
        finally:
            server.stop()

    def test_slots(self) -> None:
        _app, server, proxy, _recorder = self._start_server()
        try:
            slots = proxy.slots()
            assert "kubernetes" in slots
        finally:
            server.stop()

    def test_to_yaml(self) -> None:
        _app, server, proxy, _recorder = self._start_server()
        try:
            yaml_str = proxy.to_yaml("kubernetes")
            assert "kind: Deployment" in yaml_str
        finally:
            server.stop()

    def test_data_get_set(self) -> None:
        _app, server, proxy, recorder = self._start_server()
        try:
            val = proxy.data_get("api.image")
            assert val == "myapp:v1"

            initial_count = len(recorder.applied)
            proxy.data_set("api.image", "myapp:v2")
            assert len(recorder.applied) > initial_count
        finally:
            server.stop()

    def test_apply(self) -> None:
        _app, server, proxy, recorder = self._start_server()
        try:
            initial_count = len(recorder.applied)
            proxy.apply("kubernetes")
            assert len(recorder.applied) > initial_count
        finally:
            server.stop()

    def test_invalid_token(self) -> None:
        import pytest
        _app, server, _proxy, _recorder = self._start_server()
        try:
            bad_proxy = RemoteProxy("127.0.0.1", server.port, "wrong_token")
            with pytest.raises(RuntimeError, match="Invalid token"):
                bad_proxy.status()
        finally:
            server.stop()

    def test_quit(self) -> None:
        _app, server, proxy, _recorder = self._start_server()
        result = proxy.quit()
        assert result["status"] == "shutting_down"
        time.sleep(0.2)
        assert not server._running
