# Getting Started

## Installation

```bash
pip install genro-traefik
```

## Your First Config

Every genro-traefik configuration is a Python class:

```python
from genro_traefik import TraefikApp

class MyProxy(TraefikApp):
    def recipe(self, root):
        # Static: where Traefik listens
        root.entryPoint(name="web", address=":80")

        # Dynamic: what Traefik does with requests
        http = root.http()
        http.routers().router(
            name="my-app",
            rule="Host(`app.example.com`)",
            service="my-service",
            entryPoints=["web"],
        )
        svc = http.services().service(name="my-service")
        svc.loadBalancer().server(url="http://localhost:8080")

proxy = MyProxy()
print(proxy.to_yaml())
```

This produces valid Traefik YAML:

```yaml
entryPoints:
  web:
    address: :80
http:
  routers:
    my-app:
      rule: Host(`app.example.com`)
      service: my-service
      entryPoints:
      - web
  services:
    my-service:
      loadBalancer:
        servers:
        - url: http://localhost:8080
```

## Adding HTTPS

```python
def recipe(self, root):
    # HTTP -> HTTPS redirect
    web = root.entryPoint(name="web", address=":80")
    web.redirect(to="websecure", scheme="https", permanent=True)
    root.entryPoint(name="websecure", address=":443")

    # Let's Encrypt
    le = root.certificateResolver(name="letsencrypt")
    acme = le.acme(email="admin@example.com", storage="acme.json")
    acme.httpChallenge(entryPoint="web")

    # Router with TLS
    http = root.http()
    r = http.routers().router(
        name="my-app", rule="Host(`app.example.com`)",
        service="my-service", entryPoints=["websecure"])
    r.routerTls(certResolver="letsencrypt")

    svc = http.services().service(name="my-service")
    svc.loadBalancer().server(url="http://localhost:8080")
```

## Adding Middlewares

```python
http = root.http()
mw = http.middlewares()

# Rate limiting
mw.rateLimit(name="rate-limit", average=100, burst=50, period="1m")

# Security headers
mw.headers(name="security", stsSeconds=31536000, frameDeny=True,
           contentTypeNosniff=True)

# Apply to router
http.routers().router(
    name="my-app", rule="Host(`app.example.com`)",
    service="my-service", middlewares=["rate-limit", "security"])
```

## Validation

Check your configuration for structural errors before deploying:

```python
proxy = MyProxy()
errors = proxy.check()
if errors:
    for err in errors:
        print(f"ERROR: {err}")
else:
    proxy.to_yaml("/etc/traefik/traefik.yml")
```

## Writing to File

```python
# Write directly
proxy.to_yaml("/etc/traefik/traefik.yml")

# Or set output for auto-save on data changes
proxy = MyProxy(output="/etc/traefik/dynamic.yml")
```

---

**Next:** [Concepts](concepts.md) — understand the architecture
