# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Example: JugglerDashboard demo with mock targets.

Usage:
    juggler dashboard packages/genro-juggler/examples/dashboard_demo.py
"""

from __future__ import annotations

from typing import Any

from genro_juggler import JugglerApp
from genro_juggler.targets.mock_kubernetes import MockK8sTarget


class Application(JugglerApp):
    """Web API stack for dashboard demo."""

    targets = {"kubernetes": MockK8sTarget(verbose=False)}

    def __init__(self) -> None:
        super().__init__(
            targets=self.targets,
            data={
                "api.image": "myapp:v1.0.0",
                "api.host": "api.example.com",
                "db.host": "postgres.internal",
                "db.password": "s3cret",
            },
        )

    def kubernetes_recipe(self, root: Any) -> None:
        root.secret(name="db-creds", data={
            "password": "^db.password",
        })

        dep = root.deployment(name="api", image="^api.image", replicas=3)
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)
        c.env_var(name="DB_HOST", value="^db.host")

        root.service(name="api")
        root.service(name="frontend")

        ing = root.ingress(name="api-ingress")
        ing.ingress_rule(host="^api.host", path="/",
                         service_name="api", service_port=80)
