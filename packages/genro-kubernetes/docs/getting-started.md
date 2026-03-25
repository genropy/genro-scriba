# Getting Started

## Installation

```bash
pip install genro-kubernetes
```

## Your First Manifest

```python
from genro_kubernetes import KubernetesApp

class MyApp(KubernetesApp):
    def recipe(self, root):
        # Deployment
        dep = root.deployment(name="web", image="nginx:alpine", replicas=2)
        c = dep.container(name="web", image="nginx:alpine")
        c.port(container_port=80)

        # Service
        svc = root.service(name="web")
        svc.service_port(port=80, target_port=80)

app = MyApp()
print(app.to_yaml())
```

## Data Pointers

Use `^path` to parameterize manifests:

```python
class MyApp(KubernetesApp):
    def recipe(self, root):
        dep = root.deployment(name="api", image="^api.image", replicas="^api.replicas")
        c = dep.container(name="api", image="^api.image")

app = MyApp(data={"api.image": "myapp:v2", "api.replicas": 5})
```

## Available Resources

- **Workloads**: deployment, statefulset, job
- **Networking**: service, service_port, ingress, ingress_rule
- **Configuration**: configmap, secret
- **Storage**: persistent_volume_claim
- **Containers**: container, port, env_var, volume_mount, resources

## Import from YAML

Convert existing manifests to Python:

```python
from genro_kubernetes import recipe_from_manifest

code = recipe_from_manifest("my-deployment.yaml")
print(code)  # Python recipe ready to customize
```

---

**Next:** [API Reference](reference/kubernetes-app)
