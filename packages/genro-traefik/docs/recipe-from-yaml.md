# Recipe from YAML

## Importing Existing Configurations

If you already have a Traefik YAML file, you can convert it to a genro-traefik Python recipe:

```python
from genro_traefik import recipe_from_yaml

code = recipe_from_yaml("traefik.yml")
print(code)
```

This generates a complete Python class that reproduces your YAML configuration.

## Command Line

```bash
python -m genro_traefik.recipe_from_yaml traefik.yml MyProxy > my_proxy.py
```

## From a Dictionary

```python
data = {
    "entryPoints": {"web": {"address": ":80"}},
    "http": {
        "routers": {"api": {"rule": "Host(`api.example.com`)", "service": "svc"}},
        "services": {"svc": {"loadBalancer": {"servers": [{"url": "http://localhost:8080"}]}}},
    },
}
code = recipe_from_yaml(data, class_name="ApiProxy")
```

## Generated Code Structure

The generated class follows the same pattern as hand-written recipes:

```python
from genro_traefik import TraefikApp

class MyProxy(TraefikApp):

    def recipe(self, root):
        self.entryPoints(root)
        self.dynamic(root.http())

    def entryPoints(self, root):
        root.entryPoint(name="web", address=":80")

    def dynamic(self, http):
        self.routing(http.routers())
        self.backends(http.services())

    def routing(self, routers):
        routers.router(name="api", rule="Host(`api.example.com`)", service="svc")

    def backends(self, services):
        svc = services.service(name="svc")
        lb = svc.loadBalancer()
        lb.server(url="http://localhost:8080")
```

## Supported Sections

The converter handles all Traefik v3 sections:

- Entry points (with redirects)
- Certificate resolvers (ACME with all challenge types)
- API configuration
- Providers (file, Docker, etc.)
- Logging (log, accessLog, metrics, tracing, ping)
- HTTP (routers, services, middlewares, serversTransports)
- TCP (routers, services, middlewares)
- UDP (routers, services)
- Global TLS (certificates, options, stores)
