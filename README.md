# genro-scriba

[![Python versions](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

**Infrastructure as Python.** Write Traefik, Docker Compose, Kubernetes, and Ansible configs as Python programs instead of YAML files. Then apply them to live systems with genro-juggler.

## Why?

YAML is great until you have 5 services, 3 environments, and shared conventions. Then it becomes copy-paste with manual coordination. genro-scriba lets you use Python — loops, conditionals, parameters, shared data — to generate validated configuration files.

## Packages

| Package | Description | Tests | Status |
| ------- | ----------- | ----- | ------ |
| [genro-scriba](src/genro_scriba/) | ScribaApp core, YamlCompiler, ArtifactHub | 27 | Alpha |
| [genro-traefik](packages/genro-traefik/) | Traefik v3 reverse proxy (~150 @element, 3 @component) | 169 | Alpha |
| [genro-compose](packages/genro-compose/) | Docker Compose stacks (~15 @element, 2 @component) | 36 | Alpha |
| [genro-kubernetes](packages/genro-kubernetes/) | Kubernetes manifests (20 @element + importers) | 42 | Alpha |
| [genro-ansible](packages/genro-ansible/) | Ansible playbooks (5 @element, args_* flat params) | 22 | Alpha |
| [genro-juggler](packages/genro-juggler/) | Reactive infrastructure bus (targets + CLI/REPL) | 39 | Alpha |

**335 tests total.**

Each package works independently. The `genro-scriba` meta-package installs everything.

## Installation

```bash
pip install genro-scriba              # everything
pip install genro-traefik             # standalone Traefik builder
pip install genro-compose             # standalone Compose builder
pip install genro-kubernetes          # standalone Kubernetes builder
pip install genro-ansible             # standalone Ansible builder
pip install genro-juggler             # reactive bus with targets
```

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
        root.service(
            name="web", image="nginx:alpine", restart="always",
            ports=["80:80", "443:443"],
            depends_on=["api"])

        api = root.service(
            name="api", image="myapp:latest",
            restart="unless-stopped",
            ports=["8080:8080"],
            environment={
                "DATABASE_URL": f"postgresql://app:{self._db_password}@db:5432/myapp",
                "REDIS_URL": "redis://cache:6379/0",
            })
        api.healthcheck(test="curl -f http://localhost:8080/health",
                        interval="10s", timeout="3s", retries=3)
        api.depends_on_condition(service="db", condition="service_healthy")

        if self._replicas > 1:
            api.deploy(replicas=self._replicas)

        db = root.service(
            name="db", image="postgres:16-alpine", restart="always",
            environment={
                "POSTGRES_DB": "myapp",
                "POSTGRES_PASSWORD": self._db_password,
            },
            volumes=["pgdata:/var/lib/postgresql/data"])
        db.healthcheck(test="pg_isready -U postgres",
                       interval="10s", retries=5)

        root.service(
            name="cache", image="redis:7-alpine", restart="always",
            volumes=["redisdata:/data"])

        root.volume(name="pgdata")
        root.volume(name="redisdata")

stack = MyStack(db_password="s3cret!", replicas=3)
stack.to_yaml("docker-compose.yml")
```

---

## Kubernetes — Manifest Generation

```python
from genro_kubernetes import KubernetesApp

class MyCluster(KubernetesApp):
    def recipe(self, root):
        # Secret for database credentials
        root.secret(name="db-creds",
                    data={"username": "admin", "password": "s3cret"})

        # Deployment with environment from secret
        dep = root.deployment(name="api", image="myapp:v1", replicas=3)
        c = dep.container(name="api", image="myapp:v1")
        c.port(container_port=8080)
        c.env_var(name="DB_PASSWORD",
                  value_from_secret="db-creds", secret_key="password")
        c.resources(cpu_request="100m", memory_request="128Mi",
                    cpu_limit="500m", memory_limit="512Mi")
        c.liveness_probe(path="/health", port=8080, period=10)

        # Service
        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)

        # Ingress with TLS
        ing = root.ingress(name="api-ingress")
        ing.ingress_rule(host="api.example.com", path="/",
                         service_name="api", service_port=80)
        ing.ingress_tls(hosts=["api.example.com"],
                        secret_name="api-tls")

app = MyCluster()
app.to_yaml("manifests.yaml")
```

Also imports existing manifests back to Python:

```python
from genro_kubernetes.recipe_from_manifest import recipe_from_manifest

code = recipe_from_manifest("existing-deployment.yaml")
print(code)  # → Python recipe that reproduces the YAML
```

---

## Ansible — Playbook Generation

```python
from genro_ansible import AnsibleApp

class ServerSetup(AnsibleApp):
    def recipe(self, root):
        play = root.play(name="Setup web servers",
                         hosts="web", become=True)
        play.task(name="Install Docker", module="apt",
                  args_name="docker.io", args_state="present")
        play.task(name="Start Docker", module="systemd",
                  args_name="docker", args_state="started",
                  args_enabled=True)
        play.task(name="Deploy config", module="template",
                  args_src="app.conf.j2",
                  args_dest="/etc/app/config.yml")

app = ServerSetup()
app.to_yaml("playbook.yml")
```

The `$` prefix maps to Ansible `{{ }}` variables: `args_dest="$deploy_dir/config.yml"` becomes `dest: "{{ deploy_dir }}/config.yml"`.

---

## Juggler — Reactive Infrastructure Bus

genro-juggler connects builders to live targets. When data changes, affected slots recompile and apply automatically.

```python
from genro_juggler import JugglerApp
from genro_juggler.targets import K8sTarget, MockK8sTarget

class MyInfra(JugglerApp):
    def kubernetes_recipe(self, root):
        dep = root.deployment(name="api", image="^api.image", replicas=2)
        c = dep.container(name="api", image="^api.image")
        c.port(container_port=8080)

        svc = root.service(name="api")
        svc.service_port(port=80, target_port=8080)

    def ansible_recipe(self, root):
        play = root.play(name="Setup", hosts="all", become=True)
        play.task(name="Install Docker", module="apt",
                  args_name="docker.io", args_state="present")

# With mock target (testing)
app = MyInfra(
    targets={"kubernetes": MockK8sTarget()},
    data={"api.image": "myapp:v1"},
)
# [MockK8s] APPLY  Deployment/default/api → applied
# [MockK8s] APPLY  Service/default/api → applied

# Reactive: change data → automatic reapply
app.data["api.image"] = "myapp:v2"
# [MockK8s] APPLY  Deployment/default/api → applied
# [MockK8s] APPLY  Service/default/api → applied

# With real target (production)
# app = MyInfra(targets={"kubernetes": K8sTarget()}, data={...})
```

### Targets

| Target | Description |
| ------ | ----------- |
| `K8sTarget` | Server-side apply to Kubernetes cluster via dynamic client |
| `AnsibleTarget` | Execute playbooks via ansible-runner |
| `FileTarget` | Write YAML files to disk |
| `MockK8sTarget` | In-memory K8s mock with logging (testing) |
| `MockAnsibleTarget` | In-memory Ansible mock with logging (testing) |

### CLI

```bash
juggler run infra.py          # start app with remote server
juggler list                  # list running apps
juggler connect myinfra       # REPL with /status, /slots, /yaml
juggler yaml infra.py         # dry-run: print YAML without applying
juggler stop myinfra          # stop remote app
```

---

## ScribaApp — Unified Infrastructure with Shared Data

One Python program generates multiple config files with shared data and selective recompile.

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

infra = MyInfra(
    traefik_output="traefik.yml",
    compose_output="docker-compose.yml",
)

infra.data["web.port"] = ":80"
infra.data["api.rule"] = "Host(`api.example.com`)"
infra.data["api.backend"] = "http://api:8080"
infra.data["api.port"] = "8080:8080"
infra.data["db.url"] = "postgresql://app:secret@db:5432/myapp"
infra.data["db.password"] = "secret"

# Change db.password → only docker-compose.yml is regenerated
# Change web.port → only traefik.yml is regenerated
```

---

## The Builder IS the Documentation

Every `@element` has an encyclopedic docstring that teaches the underlying tool:

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
├── src/genro_scriba/              # ScribaApp core, YamlCompiler, ArtifactHub
├── packages/
│   ├── genro-traefik/             # TraefikApp + TraefikBuilder
│   ├── genro-compose/             # ComposeApp + ComposeBuilder
│   ├── genro-kubernetes/          # KubernetesApp + KubernetesBuilder + importers
│   ├── genro-ansible/             # AnsibleApp + AnsibleBuilder
│   └── genro-juggler/             # JugglerApp + targets + CLI/REPL
├── pyproject.toml                 # meta-package
└── README.md
```

## License

Apache License 2.0 — see LICENSE file for details.
