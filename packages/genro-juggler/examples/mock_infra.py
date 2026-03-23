# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Example: full infrastructure with mock targets.

Demonstrates the complete juggler pipeline — K8s + Ansible recipes
compiled and applied to mock targets that log every operation.

Usage:
    python -m examples.mock_infra
    # or
    python packages/genro-juggler/examples/mock_infra.py
"""

from __future__ import annotations

from typing import Any

from genro_juggler import JugglerApp
from genro_juggler.targets.mock_ansible import MockAnsibleTarget
from genro_juggler.targets.mock_kubernetes import MockK8sTarget


class WebStack(JugglerApp):
    """Web application stack: K8s deployment + Ansible server setup."""

    def kubernetes_recipe(self, root: Any) -> None:
        # Database secret
        root.secret(name="db-creds", data={
            "username": "^db.user",
            "password": "^db.password",
        })

        # API deployment
        dep = root.deployment(name="api", image="^api.image", replicas=3)
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)
        c.env_var(name="DB_HOST", value="^db.host")
        c.env_var(name="DB_PASSWORD",
                  value_from_secret="db-creds", secret_key="password")

        # API service
        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)

        # Ingress
        ing = root.ingress(name="api-ingress")
        ing.ingress_rule(host="^api.host", path="/",
                         service_name="api", service_port=80)

    def ansible_recipe(self, root: Any) -> None:
        # Server setup play
        setup = root.play(
            name="Prepare application servers",
            hosts="^ansible.hosts",
            become=True,
        )
        setup.task(name="Install Docker", module="apt",
                   args_name="docker.io", args_state="present")
        setup.task(name="Install K3s", module="shell",
                   args_cmd="curl -sfL https://get.k3s.io | sh -")
        setup.task(name="Enable K3s", module="systemd",
                   args_name="k3s", args_state="started",
                   args_enabled=True)


def main() -> None:
    print("=" * 60)
    print("genro-juggler mock infrastructure demo")
    print("=" * 60)
    print()

    k8s_target = MockK8sTarget(verbose=True)
    ansible_target = MockAnsibleTarget(verbose=True)

    data = {
        "api.image": "myapp:v1.0.0",
        "api.host": "api.example.com",
        "db.host": "postgres.internal",
        "db.user": "appuser",
        "db.password": "s3cret-passw0rd",
        "ansible.hosts": "web-servers",
    }

    print("--- Creating infrastructure ---")
    print()
    app = WebStack(
        targets={"kubernetes": k8s_target, "ansible": ansible_target},
        data=data,
    )

    print()
    print("--- K8s resources in store ---")
    for key in k8s_target.get_applied():
        print(f"  {key}")

    print()
    print("--- Status ---")
    for name, info in app.status().items():
        print(f"  {name}: {info}")

    print()
    print("--- Changing api.image to v2.0.0 (triggers reactive reapply) ---")
    print()
    app.data["api.image"] = "myapp:v2.0.0"

    print()
    print("--- YAML dry-run (kubernetes) ---")
    print()
    print(app.to_yaml("kubernetes"))


if __name__ == "__main__":
    main()
