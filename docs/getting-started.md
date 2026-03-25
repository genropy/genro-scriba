# Getting Started

## Installation

```bash
# Core only
pip install genro-scriba

# With specific builders
pip install genro-traefik
pip install genro-compose
pip install genro-kubernetes
pip install genro-ansible

# Reactive bus
pip install genro-juggler
```

## Concept

genro-scriba turns infrastructure configuration into Python programs. Instead of writing YAML directly, you:

1. **Subclass** an App (TraefikApp, ComposeApp, KubernetesApp, etc.)
2. **Override** `recipe(root)` to build a configuration tree
3. **Compile** to YAML with `to_yaml()`

## ScribaApp — Unified Configuration

`ScribaApp` combines multiple builders (Traefik + Compose) with shared data:

```python
from genro_scriba import ScribaApp

class MyInfra(ScribaApp):
    def traefik_recipe(self, root):
        root.entryPoint(name="web", address=":80")

    def compose_recipe(self, root):
        root.service(name="api", image="^api.image")

infra = MyInfra(data={"api.image": "myapp:v1"})
```

Both recipes share the same data Bag. Change `api.image` once, both configs update.

## Data Pointers

The `^path` syntax references values from the shared data Bag:

```python
# In recipe
root.deployment(name="api", image="^api.image")

# Set data
app = MyApp(data={"api.image": "myapp:v2"})
# → image resolves to "myapp:v2" in compiled YAML
```

## ArtifactHub

Search and inspect Helm charts from Python:

```python
from genro_scriba import ArtifactHub

hub = ArtifactHub()
charts = hub.search_charts("postgresql", limit=5)
detail = hub.chart_detail("bitnami", "postgresql")
```

---

**Next:** See individual package documentation for builder-specific guides.
