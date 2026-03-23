# genro-juggler

Reactive infrastructure bus — apply genro-scriba recipes to live targets.

genro-scriba generates files. genro-juggler applies them directly to
Kubernetes clusters and Ansible targets via API, with reactive updates
when data changes.

## Installation

```bash
pip install genro-juggler                    # core
pip install genro-juggler[kubernetes]        # + K8s client
pip install genro-juggler[ansible]           # + ansible-runner
pip install genro-juggler[http]              # + HTTP API server
```

## Quick Start

```python
from genro_juggler import JugglerApp
from genro_juggler.targets import K8sTarget, AnsibleTarget

class MyInfra(JugglerApp):
    def recipe(self, root):
        dep = root.k8s.deployment(name="api", image="^api.image", replicas="^api.replicas")
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)

app = MyInfra(targets={"k8s": K8sTarget()})
app.data["api.image"] = "myapp:v2"   # → PATCH to cluster
app.data["api.replicas"] = 5         # → PATCH to cluster
```

## License

Apache License 2.0 — see LICENSE for details.
