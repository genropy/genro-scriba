# genro-traefik

Traefik v3 configuration builder for the [Genropy](https://genropy.org) ecosystem.

**Status**: Alpha

## How it works

`TraefikApp` is the base class. You subclass it and override `recipe(root)` to
describe your infrastructure. The recipe builds a validated tree of Traefik
entities using the genro-bag builder system. Calling `to_yaml()` compiles the
tree into a Traefik YAML configuration file.

```
TraefikApp
    │
    ├── recipe(root)     ← you define the structure here
    │     uses TraefikBuilder (@element decorators with validation)
    │
    ├── self.data        ← Bag with runtime values (optional)
    │     recipe attributes starting with ^ point here
    │
    ├── to_yaml()        ← compiles the tree, resolves ^ pointers, writes YAML
    │
    └── check()          ← validates sub_tags cardinality and parent_tags rules
```

The recipe reads like a description of your infrastructure: entrypoints,
certificates, middlewares, routers, services. Each method is a logical section.
The `recipe()` method is the index — you see the whole architecture at a glance.

Attribute names use Traefik's original camelCase (no conversion, no mapping).
Entity names that conflict with Python keywords use a `_` prefix (`_file`).

### Key features

- Full Traefik v3 grammar: entryPoints, providers, ACME, logging, metrics, tracing
- All protocols: HTTP, TCP, UDP, TLS
- All 23+ HTTP middlewares with schema validation
- `sub_tags` cardinality and `parent_tags` placement rules
- `^` pointer system: recipe is the template, data Bag is the values
- Reactive: data changes auto-recompile and write YAML
- `recipe_from_yaml`: import existing YAML configs as Python recipes

### Future directions

Since the data Bag supports resolvers, values can be lazily loaded from
external sources at compile time — REST APIs, environment variables, databases,
Docker socket, Consul, etcd. This opens the door to resolver-driven service
discovery without external infrastructure.

## Installation

```bash
pip install genro-traefik
```

## Quick start

```python
from genro_traefik import TraefikApp


class MyProxy(TraefikApp):

    def recipe(self, root):
        self.entryPoints(root)
        self.certificates(root)
        self.dynamic(root.http())

    def entryPoints(self, root):
        web = root.entryPoint(name="web", address=":80")
        web.redirect(to="websecure", scheme="https", permanent=True)
        root.entryPoint(name="websecure", address=":443")
        root.api(dashboard=True, insecure=True)

    def certificates(self, root):
        le = root.certificateResolver(name="letsencrypt")
        acme = le.acme(email="admin@example.com",
                       storage="/etc/traefik/acme.json")
        acme.httpChallenge(entryPoint="web")

    def dynamic(self, http):
        self.middlewares(http.middlewares())
        self.routing(http.routers())
        self.backends(http.services())

    def middlewares(self, mw):
        mw.basicAuth(name="auth",
                     users=["admin:$apr1$H6uskkkW$IgXLP6ewTrSuBkTrqE8wj/"],
                     removeHeader=True)
        mw.headers(name="security-headers",
                   stsSeconds=31536000, frameDeny=True,
                   referrerPolicy="strict-origin-when-cross-origin")
        mw.rateLimit(name="rate-limit", average=100, burst=50)
        mw.chain(name="secure-chain",
                 middlewares=["security-headers", "rate-limit"])

    def routing(self, routers):
        r = routers.router(name="api-router",
                           rule="Host(`api.example.com`)",
                           service="api-service",
                           entryPoints=["websecure"],
                           middlewares=["secure-chain", "auth"])
        r.routerTls(certResolver="letsencrypt")

    def backends(self, services):
        svc = services.service(name="api-service")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="http://192.168.1.10:8080")
        lb.server(url="http://192.168.1.11:8080")
        lb.healthCheck(path="/health", interval="10s", timeout="3s")


proxy = MyProxy()
print(proxy.to_yaml())
```

## Data Bag and ^ pointers

Separate structure from values. The recipe is a reusable template, the data
changes per environment.

```python
class MyProxy(TraefikApp):

    def recipe(self, root):
        root.entryPoint(name="web", address="^web.address")
        http = root.http()
        http.routers().router(name="api", rule="^api.rule",
                              service="api-svc", entryPoints=["web"])
        svc = http.services().service(name="api-svc")
        svc.loadBalancer().server(url="^api.backend")


# Same recipe, different data per environment
proxy = MyProxy(output="/etc/traefik/dynamic.yml")
proxy.data["web.address"] = ":80"
proxy.data["api.rule"] = 'Host(`api.example.com`)'
proxy.data["api.backend"] = "http://localhost:8080"
# YAML is written automatically

# Change a value -> YAML is rewritten
proxy.data["api.backend"] = "http://10.0.0.5:9090"
# Traefik detects the file change and reloads
```

## Import from existing YAML

Convert a `traefik.yml` into a Python recipe:

```python
from genro_traefik import recipe_from_yaml

code = recipe_from_yaml("traefik.yml", class_name="MyConfig")
print(code)
```

Or from the command line:

```bash
python -m genro_traefik.recipe_from_yaml traefik.yml MyConfig > my_config.py
```

## Validation

```python
proxy = MyProxy()
errors = proxy.check()
for e in errors:
    print(e)
```

The builder validates:
- **sub_tags cardinality**: a service must have exactly one type (loadBalancer, weighted, mirroring, failover)
- **parent_tags**: a `server` can only exist inside a `loadBalancer`
- **Required children**: a `loadBalancer` needs at least one `server`

## Dependencies

- [genro-bag](https://github.com/genropy/genro-bag) >= 0.1.0
- [PyYAML](https://pyyaml.org/) >= 6.0

## License

Apache License 2.0 — Copyright 2025 Softwell S.r.l.
