# Data Pointers

## Separating Structure from Values

The `^` pointer system lets you define the configuration **structure** once in the recipe and inject **values** separately at runtime.

```python
class MyProxy(TraefikApp):
    def recipe(self, root):
        # Structure — fixed
        root.entryPoint(name="web", address="^web.address")
        http = root.http()
        http.routers().router(
            name="api", rule="^api.rule",
            service="api-svc", entryPoints=["web"])
        svc = http.services().service(name="api-svc")
        svc.loadBalancer().server(url="^api.backend")

# Values — injected
proxy = MyProxy(output="/etc/traefik/dynamic.yml")
proxy.data["web.address"] = ":80"
proxy.data["api.rule"] = "Host(`api.example.com`)"
proxy.data["api.backend"] = "http://localhost:8080"
```

## Auto-Recompile

When you set `output` on a `TraefikApp`, any change to `proxy.data` automatically:

1. Recompiles the configuration (resolving all `^` pointers)
2. Writes the YAML to the output file

This is designed for Traefik's **file provider** with `watch: true` — Traefik picks up changes automatically.

## Multi-Environment

```python
proxy = MyProxy(output="/etc/traefik/dynamic.yml")

# Development
proxy.data["api.backend"] = "http://localhost:8080"

# Production (just change the data)
proxy.data["api.backend"] = "http://10.0.0.1:8080"
```

## Replacing Data

You can replace the entire data bag:

```python
# From a dict
proxy.data = {"web.address": ":80", "api.rule": "Host(`a.com`)"}

# From another Bag
from genro_bag import Bag
new_data = Bag()
new_data["web.address"] = ":443"
proxy.data = new_data
```

## Unresolved Pointers

If a `^path` has no matching value in `proxy.data`, the literal string `^path` is written to the YAML. This lets you build templates that are completed later.
