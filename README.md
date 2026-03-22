# genro-scriba

[![Python versions](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

**Infrastructure configuration file generator for Genropy.** Write Traefik, Docker Compose, and other infrastructure configs as Python programs instead of YAML files.

## Why?

YAML is great until you have 5 services, 3 environments, and shared conventions. Then it becomes copy-paste with manual coordination. genro-scriba lets you use Python — loops, conditionals, parameters, shared data — to generate validated configuration files.

## Installation

```bash
pip install genro-scriba              # everything
pip install genro-scriba[traefik]     # only Traefik
pip install genro-scriba[compose]     # only Docker Compose
pip install genro-traefik             # standalone
pip install genro-compose             # standalone
```

## Packages

| Package | Description | Status |
|---------|-------------|--------|
| [genro-traefik](packages/genro-traefik/) | Traefik v3 reverse proxy configuration | Alpha |
| [genro-compose](packages/genro-compose/) | Docker Compose stack configuration | Alpha |

Each package works independently. The `genro-scriba` meta-package installs everything.

---

## Traefik — Reverse Proxy Configuration

```python
from genro_traefik import TraefikApp

class MyProxy(TraefikApp):
    def recipe(self, root):
        # HTTP → HTTPS redirect
        web = root.entryPoint(name="web", address=":80")
        web.redirect(to="websecure", scheme="https", permanent=True)
        root.entryPoint(name="websecure", address=":443")

        # Let's Encrypt automatic TLS
        le = root.certificateResolver(name="letsencrypt")
        acme = le.acme(email="admin@example.com", storage="acme.json")
        acme.httpChallenge(entryPoint="web")

        # Route api.example.com → backend with auth + rate limiting
        http = root.http()
        mw = http.middlewares()
        mw.basicAuth(name="auth", users=["admin:$apr1$hash"])
        mw.rateLimit(name="rate", average=100, burst=50, period="1m")

        r = http.routers().router(
            name="api", rule="Host(`api.example.com`)",
            service="api-svc", entryPoints=["websecure"],
            middlewares=["auth", "rate"])
        r.routerTls(certResolver="letsencrypt")

        svc = http.services().service(name="api-svc")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="http://10.0.0.1:8080")
        lb.server(url="http://10.0.0.2:8080")
        lb.healthCheck(path="/health", interval="10s")

proxy = MyProxy()
proxy.to_yaml("traefik.yml")
```

**Python advantage**: Generate routers and services in a loop for N microservices, share middleware stacks with variables, use conditionals for dev/prod differences.

---

## Docker Compose — Stack Configuration

```python
from genro_compose import ComposeApp

class MyStack(ComposeApp):
    def __init__(self, db_password="changeme", replicas=1):
        self._db_password = db_password
        self._replicas = replicas
        super().__init__()

    def recipe(self, root):
        # Web frontend
        root.service(
            name="web", image="nginx:alpine", restart="always",
            ports=["80:80", "443:443"],
            volumes=["./nginx.conf:/etc/nginx/nginx.conf:ro"],
            depends_on=["api"])

        # API backend with health check and deploy config
        api = root.service(
            name="api", image="myapp:latest",
            restart="unless-stopped",
            ports=["8080:8080"],
            environment={
                "DATABASE_URL": f"postgresql://app:{self._db_password}@db:5432/myapp",
                "REDIS_URL": "redis://cache:6379/0",
            })
        api.build_config(context=".", target="production")
        api.healthcheck(test="curl -f http://localhost:8080/health",
                        interval="10s", timeout="3s", retries=3)
        api.depends_on_condition(service="db", condition="service_healthy")

        if self._replicas > 1:
            api.deploy(replicas=self._replicas)

        # PostgreSQL with health check
        db = root.service(
            name="db", image="postgres:16-alpine", restart="always",
            environment={
                "POSTGRES_DB": "myapp",
                "POSTGRES_PASSWORD": self._db_password,
            },
            volumes=["pgdata:/var/lib/postgresql/data"])
        db.healthcheck(test="pg_isready -U postgres",
                       interval="10s", retries=5)

        # Redis cache
        root.service(
            name="cache", image="redis:7-alpine", restart="always",
            volumes=["redisdata:/data"])

        # Persistent volumes
        root.volume(name="pgdata")
        root.volume(name="redisdata")

# Production: 3 API replicas
stack = MyStack(db_password="s3cret!", replicas=3)
stack.to_yaml("docker-compose.yml")
```

**Python advantage**: Database password defined once and used in API connection string and DB config. Replicas controlled by a parameter. Health check ensures startup order.

---

## ScribaApp — Unified Infrastructure with Shared Data

The real power: **one Python program generates both `traefik.yml` and `docker-compose.yml`** with shared data.

```python
from genro_scriba import ScribaApp

class MyInfra(ScribaApp):
    def traefik_recipe(self, root):
        root.entryPoint(name="web", address="^web.port")
        http = root.http()
        r = http.routers().router(
            name="api", rule="^api.rule",
            service="api-svc", entryPoints=["web"])
        svc = http.services().service(name="api-svc")
        svc.loadBalancer().server(url="^api.backend")

    def compose_recipe(self, root):
        root.service(
            name="api", image="myapi:latest",
            environment={"DATABASE_URL": "^db.url"},
            ports=["^api.port"])
        root.service(
            name="db", image="postgres:16",
            environment={"POSTGRES_PASSWORD": "^db.password"},
            volumes=["pgdata:/var/lib/postgresql/data"])
        root.volume(name="pgdata")

# Create infrastructure with auto-save
infra = MyInfra(
    traefik_output="/etc/traefik/traefik.yml",
    compose_output="docker-compose.yml",
)

# Set shared data — files are written automatically
infra.data["web.port"] = ":80"
infra.data["api.rule"] = "Host(`api.example.com`)"
infra.data["api.backend"] = "http://api:8080"
infra.data["api.port"] = "8080:8080"
infra.data["db.url"] = "postgresql://app:secret@db:5432/myapp"
infra.data["db.password"] = "secret"
```

### Selective Recompile

ScribaApp tracks which `^pointers` each builder uses. When you change a value, **only the affected builder recompiles**:

```python
infra.data["db.password"] = "new_secret"
# → only docker-compose.yml is regenerated (Traefik doesn't use db.password)

infra.data["web.port"] = ":8080"
# → only traefik.yml is regenerated (Compose doesn't use web.port)
```

### Live Configuration

Combined with Traefik's file provider (`watch: true`), ScribaApp becomes a **live control plane**:

```python
# Traefik watches for file changes, picks up new config automatically
infra = MyInfra(traefik_output="/etc/traefik/dynamic.yml")

# Later, in your application:
infra.data["api.backend"] = "http://new-server:8080"
# → traefik.yml is regenerated → Traefik reloads automatically
```

---

## The Builder IS the Documentation

Every `@element` has an encyclopedic docstring that teaches the underlying tool. Reading the builder is a tutorial:

```python
# In your IDE, hover over any method to learn:
svc.healthcheck(
    # Shows: "Health check — how Compose knows if a container is healthy.
    #         The health status is used by depends_on with
    #         condition: service_healthy..."
)
```

---

## Monorepo Structure

```
genro-scriba/
├── src/genro_scriba/          # ScribaApp (unified, shared data)
├── packages/
│   ├── genro-traefik/         # TraefikApp + TraefikBuilder (standalone)
│   └── genro-compose/         # ComposeApp + ComposeBuilder (standalone)
├── pyproject.toml             # meta-package
└── README.md
```

## License

Apache License 2.0 — see LICENSE file for details.
