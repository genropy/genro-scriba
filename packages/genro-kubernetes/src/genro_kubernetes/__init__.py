# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""genro-kubernetes: Kubernetes manifest builder for Genropy.

Generates validated Kubernetes YAML manifests using the genro-bag builder
system. The builder IS the documentation — every @element docstring is an
encyclopedic reference for the corresponding Kubernetes concept.

Example:
    ```python
    from genro_kubernetes import KubernetesApp

    class MyManifest(KubernetesApp):
        def recipe(self, root):
            dep = root.deployment(name="api", image="myapp:latest", replicas=3)
            c = dep.container(name="api", image="myapp:latest")
            c.port(container_port=8080)
            c.probe(type="liveness", http_get_path="/health", http_get_port=8080)

            root.service(name="api", type="ClusterIP")
                .service_port(port=80, target_port=8080)

    app = MyManifest()
    print(app.to_yaml())
    ```
"""

__version__ = "0.1.0"

from .builders.kubernetes_builder import KubernetesBuilder
from .kubernetes_app import KubernetesApp
from .recipe_from_manifest import recipe_from_helm, recipe_from_manifest

__all__ = [
    "KubernetesApp",
    "KubernetesBuilder",
    "__version__",
    "recipe_from_helm",
    "recipe_from_manifest",
]
