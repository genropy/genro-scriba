# Getting Started

## Installation

```bash
pip install genro-compose
```

## Your First Compose File

```python
from genro_compose import ComposeApp

class MyStack(ComposeApp):
    def recipe(self, root):
        # Web service
        web = root.service(name="web", image="^app.image")
        web.port(published=8080, target=80)
        web.environment(name="DATABASE_URL", value="^db.url")
        web.depends_on(service="db")

        # PostgreSQL via built-in component
        root.postgres(name="db")

stack = MyStack(data={"app.image": "myapp:latest", "db.url": "postgresql://db:5432/app"})
print(stack.to_yaml())
```

## Built-in Components

genro-compose includes ready-made components:

- **`postgres()`** — PostgreSQL service with healthcheck and named volume
- **`redis()`** — Redis service with healthcheck and persistence

```python
def recipe(self, root):
    root.postgres(name="db", version="16-alpine")
    root.redis(name="cache", version="7-alpine")
```

## Mixins

The builder includes 4 mixins for common patterns:

- **ServiceMixin** — service, port, environment, volume, depends_on, etc.
- **BuildMixin** — build context, dockerfile, args
- **DeployMixin** — replicas, resources, placement
- **InfrastructureMixin** — networks, volumes, configs, secrets

## Data Pointers

Use `^path` to reference shared data:

```python
class MyStack(ComposeApp):
    def recipe(self, root):
        web = root.service(name="web", image="^app.image")
        web.port(published="^app.port", target=80)

stack = MyStack(data={"app.image": "myapp:v2", "app.port": 8080})
```

---

**Next:** [API Reference](reference/compose-app)
