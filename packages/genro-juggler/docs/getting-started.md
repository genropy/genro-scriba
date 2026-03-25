# Getting Started

## Installation

```bash
pip install genro-juggler

# Optional targets
pip install genro-juggler[kubernetes]   # Real K8s cluster
pip install genro-juggler[ansible]      # ansible-runner
pip install genro-juggler[dashboard]    # TUI dashboard
```

## Your First Infrastructure

```python
from genro_juggler import JugglerApp
from genro_juggler.targets import MockK8sTarget

class MyInfra(JugglerApp):
    def kubernetes_recipe(self, root):
        dep = root.deployment(name="api", image="^api.image", replicas=2)
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)

        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)

app = MyInfra(
    targets={"kubernetes": MockK8sTarget()},
    data={"api.image": "myapp:v1"},
)
```

## Reactive Data Changes

When data changes, affected slots recompile and re-apply:

```python
# This triggers: recompile deployment → apply to target
app.data["api.image"] = "myapp:v2"
```

## Targets

| Target | Description |
|--------|-------------|
| `MockK8sTarget` | In-memory K8s mock (testing) |
| `MockAnsibleTarget` | In-memory Ansible mock (testing) |
| `FileTarget` | Write YAML to files |
| `K8sTarget` | Real Kubernetes API (requires `kubernetes` extra) |
| `AnsibleTarget` | Real ansible-runner (requires `ansible` extra) |

## Dry-Run (YAML Preview)

```python
print(app.to_yaml("kubernetes"))
```

## Multiple Slots

```python
class FullStack(JugglerApp):
    def kubernetes_recipe(self, root):
        root.deployment(name="api", image="^api.image")

    def ansible_recipe(self, root):
        play = root.play(name="Setup", hosts="^hosts", become=True)
        play.task(name="Install Docker", module="apt",
                  args_name="docker.io", args_state="present")
```

---

**Next:** [CLI](cli.md) | [API Reference](reference/juggler-app)
