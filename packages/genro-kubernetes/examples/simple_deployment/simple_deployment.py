# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Simple deployment — Kubernetes manifest with Deployment + Service + Ingress.

The recipe defines STRUCTURE, the data Bag holds VALUES.
^ pointers are resolved at compile time.

Run:
    PYTHONPATH=src python examples/simple_deployment/simple_deployment.py
"""

from __future__ import annotations

from pathlib import Path

from genro_kubernetes import KubernetesApp


class SimpleDeployment(KubernetesApp):
    """Web API deployed on Kubernetes with health checks and Ingress."""

    def recipe(self, root):
        # ConfigMap for app settings
        root.configmap(name="api-config",
                       data={"LOG_LEVEL": "info", "APP_ENV": "production"})

        # Secret for database credentials
        root.secret(name="db-creds",
                    string_data={"password": "^db.password"})

        # Deployment with container, probes, env from secret
        dep = root.deployment(name="api", replicas=3)
        c = dep.container(name="api", image="^api.image",
                          resources_requests_cpu="100m",
                          resources_requests_memory="128Mi",
                          resources_limits_cpu="500m",
                          resources_limits_memory="256Mi")
        c.port(container_port=8080, name="http")
        c.env_var(name="DB_PASSWORD", value_from_secret="db-creds",
                  secret_key="password")
        c.env_var(name="LOG_LEVEL", value_from_configmap="api-config",
                  configmap_key="LOG_LEVEL")
        c.volume_mount(name="config", mount_path="/etc/app")
        c.probe(type="liveness", http_get_path="/health", http_get_port=8080,
                initial_delay=10, period=15)
        c.probe(type="readiness", http_get_path="/ready", http_get_port=8080,
                initial_delay=5)
        dep.volume(name="config", type="configMap", source="api-config")

        # Service
        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)

        # Ingress
        ing = root.ingress(name="api", ingress_class="traefik")
        ing.ingress_rule(host="^api.host",
                         service_name="api", service_port=80)
        ing.ingress_tls(hosts=["^api.host"], secret_name="api-tls")


def main():
    app = SimpleDeployment(data={
        "api.image": "myapp:v1.2.3",
        "api.host": "api.example.com",
        "db.password": "s3cret!",
    })

    dest = Path(__file__).parent / "manifests.yaml"
    yaml_str = app.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
