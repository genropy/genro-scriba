# genro-kubernetes

Kubernetes manifest builder for Genropy — validated YAML generation.

## Installation

```bash
pip install genro-kubernetes
```

## Quick Start

```python
from genro_kubernetes import KubernetesApp

class MyManifest(KubernetesApp):
    def recipe(self, root):
        dep = root.deployment(name="api", image="myapp:latest", replicas=3)
        c = dep.container(name="api", image="myapp:latest")
        c.port(container_port=8080)
        c.probe(type="liveness", http_get_path="/health", http_get_port=8080)

        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)

app = MyManifest()
print(app.to_yaml())
```

## License

Apache License 2.0 — see LICENSE for details.
