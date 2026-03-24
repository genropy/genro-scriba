# Stop Writing YAML by Hand: Infrastructure Configuration as Typed Python

## What if your infrastructure config files came with autocompletion, validation, and documentation built in?

Every DevOps engineer knows the drill. You open a 300-line `docker-compose.yml`, squint at the indentation, wonder if it's `depends_on` or `dependsOn`, check the docs for the third time today, and pray the typo you just introduced won't take down staging on Friday afternoon.

YAML is the lingua franca of modern infrastructure. Traefik, Docker Compose, Kubernetes, Ansible — they all speak it. But YAML is a *serialization format*, not a *programming language*. It has no types, no autocompletion, no validation, and no way to express reusable patterns without bolting on a template engine.

**What if we stopped writing YAML altogether?**

Not by replacing it with another markup language or a DSL that compiles to YAML. Instead, by writing plain Python methods that *are* the configuration — with full IDE support, runtime validation, and encyclopedic documentation baked into every parameter.

This is the idea behind **genro-scriba**, an open-source library built on the [Genropy](https://www.genropy.org) framework. And the implications go far beyond developer comfort.

---

## The Core Idea: The Builder *Is* the Grammar

At the heart of genro-scriba is a simple principle: **every concept in a tool's configuration language becomes a Python method**.

A Traefik entry point? It's a method called `entryPoint()`. A Docker Compose service? It's `service()`. A Kubernetes deployment? `deployment()`. Each method's parameters mirror the tool's own configuration options — same names, same types, same defaults.

```python
class SimpleReverseProxy(TraefikApp):

    def recipe(self, root):
        root.https_setup(email="^acme.email")
        root.log(level="INFO", format="json")

        http = root.http()
        mw = http.middlewares()
        mw.security_headers()
        mw.rateLimit(name="rate-limit", average=100, period="1m", burst=50)

        http.web_service(name="api", rule="^api.rule",
                         backends=["^api.primary", "^api.secondary"],
                         middlewares=["security-headers", "rate-limit"])
```

That's a complete, production-ready Traefik configuration: HTTPS with Let's Encrypt, HTTP-to-HTTPS redirect, security headers, rate limiting, and a load-balanced backend with two servers. **16 lines of Python** that generate a correct, validated `traefik.yml`.

But this isn't just code generation. Let's look at what you actually get.

---

## What You Get (That YAML Can't Give You)

### 1. Autocompletion That Knows Your Infrastructure

Every `@element` is a standard Python method. When you type `root.entryPoint(`, your IDE shows:

```
entryPoint(
    name: str = "",
    address: str = "",
    proxyProtocol_trustedIPs: str = "",
    proxyProtocol_insecure: bool = False,
    forwardedHeaders_trustedIPs: str = "",
    forwardedHeaders_insecure: bool = False
)
```

No more guessing parameter names. No more switching to browser tabs. The builder's method signature **is** the documentation for that configuration concept.

### 2. The Docstring Is the Manual

Hover over any element in your IDE and you get the full explanation:

```python
@element(sub_tags="redirect")
def entryPoint(self, name: str = "", address: str = ""):
    """Network listener for incoming connections.

    Args:
        name: EntryPoint name (e.g. "web", "websecure").
        address: Listen address (e.g. ":80", ":443").
    """
```

The builder doesn't *reference* the documentation — it *is* the documentation. Every `@element` carries a docstring that explains what the concept does, what its parameters mean, and how they relate to the underlying tool. You learn the tool by using the builder.

### 3. Structural Validation Before Render

The `@element` decorator declares which children are allowed:

```python
@element(sub_tags="server[1:], healthCheck[:1], sticky[:1]")
def loadBalancer(self, passHostHeader: bool = True):
    """Load balancer — round-robin across backends."""
```

This says: a `loadBalancer` must have *at least one* `server`, *at most one* `healthCheck`, and *at most one* `sticky` session config. Try to nest something else inside it, and validation catches it at build time — not when Traefik rejects your YAML at 2 AM.

### 4. Reusable Patterns Without Template Engines

Common configuration patterns become `@component` methods — reusable, parameterized, transparent:

```python
@component(sub_tags="")
def https_setup(self, c, email="", storage="/etc/traefik/acme.json"):
    """Complete HTTPS: HTTP->HTTPS redirect + Let's Encrypt.

    One call instead of five manual elements.
    """
    web = c.entryPoint(name="web", address=":80")
    web.redirect(to="websecure", scheme="https", permanent=True)
    c.entryPoint(name="websecure", address=":443")
    le = c.certificateResolver(name="letsencrypt")
    acme = le.acme(email=email, storage=storage)
    acme.httpChallenge(entryPoint="web")
```

Usage: `root.https_setup(email="admin@example.com")`. One line. Five elements. Fully validated. And because it's Python, you can compose components, pass parameters, and build abstractions that make sense for your organization.

---

## Separating Structure from Values

One of the most powerful ideas in genro-scriba is the **pointer system**. Configuration recipes define *structure*. Values come from a separate data layer, referenced with `^` pointers:

```python
class MultiServicePlatform(TraefikApp):

    def recipe(self, root):
        # Structure is fixed
        r = http.routers().router(name="api-router", datapath="api",
                                   rule="^.rule",          # <- pointer
                                   service="api-svc",
                                   entryPoints=["websecure"])
        svc = http.services().service(name="api-svc", datapath="api")
        lb = svc.loadBalancer()
        lb.server(url="^.primary")                         # <- pointer
        lb.server(url="^.secondary")                       # <- pointer
```

Values are provided separately:

```python
platform.data["api.rule"] = "Host(`api.myplatform.io`)"
platform.data["api.primary"] = "http://10.0.1.10:8000"
platform.data["api.secondary"] = "http://10.0.1.11:8000"
```

This means the same recipe works across environments. Dev, staging, production — same structure, different data. And the data can come from anywhere: dictionaries, environment variables via `EnvResolver`, external APIs, or even Helm chart discovery via `ArtifactHubResolver`.

```python
proxy = SimpleReverseProxy(data={
    "acme.email": EnvResolver("ACME_EMAIL", default="admin@example.com"),
    "api.rule": EnvResolver("API_RULE", default="Host(`api.example.com`)"),
    "api.primary": EnvResolver("API_PRIMARY", default="http://192.168.1.10:8080"),
})
```

---

## One Data Layer, Multiple Tools

Real infrastructure doesn't live in one config file. You need Traefik *and* Docker Compose. Or Kubernetes *and* Ansible. These tools share concepts — hostnames, ports, credentials — but each has its own file format and naming conventions.

`ScribaApp` coordinates multiple builders with a **shared data Bag**:

```python
class DualInfra(ScribaApp):

    def traefik_recipe(self, root):
        root.entryPoint(name="web", address=":80")
        # ... routers, services using ^api.rule, ^api.backend

    def compose_recipe(self, root):
        root.service(name="api", image="myapi:latest",
                     ports=["^api.port"],
                     environment={"DATABASE_URL": "^db.url"})
        root.service(name="db", image="postgres:16-alpine",
                     environment={"POSTGRES_PASSWORD": "^db.password"})

infra = DualInfra(
    traefik_output="traefik.yml",
    compose_output="docker-compose.yml",
)

infra.data = {
    "api.rule": "Host(`api.example.com`)",
    "api.backend": "http://api:8080",
    "api.port": "8080:8080",
    "db.url": "postgresql://app:s3cret!@db:5432/myapp",
    "db.password": "s3cret!",
}
```

Both files are generated from the same data source. Change `api.backend` and only `traefik.yml` is regenerated. Change `db.password` and only `docker-compose.yml` is updated. The framework tracks which pointers each builder resolved and triggers **selective recompilation** — only the affected files are rewritten.

---

## Each Tool Gets Its Own Dialect

A subtle but important design decision: each builder follows the **naming conventions of its target tool**.

- Traefik builder uses `camelCase` (matching Traefik's YAML): `entryPoint`, `loadBalancer`, `routerTls`
- Compose builder uses `snake_case` (matching Docker Compose): `depends_on_condition`, `build_config`, `healthcheck`
- Kubernetes builder uses its own conventions: `metadata`, `spec`, resource wrappers

The Python code reads like the tool's native configuration. There's no mental translation layer. If you know Traefik, you know `TraefikBuilder`. The compiler handles the mapping to the correct output format — YAML with the right structure, the right nesting, the right key names.

---

## The MCP Angle: AI-Native Infrastructure

Here's where it gets interesting.

The `@element` decorator captures everything an AI agent needs to manipulate infrastructure configuration:

- **Method name** = tool name
- **Parameters with types** = tool input schema
- **Docstring** = tool description
- **`sub_tags`** = structural constraints (what can go where)

This maps directly to the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) tool specification. Every `@element` can be exposed as an MCP tool, automatically. An LLM could:

1. **Build recipes via conversation**: "Add a Redis service with a health check and connect it to the API service"
2. **Modify existing configurations**: "Change the rate limit to 500 requests per minute"
3. **Query the structure**: "What middlewares are applied to the admin router?"
4. **Validate before applying**: the same structural and type validation that catches human errors catches AI errors too

The builder becomes a **typed, validated, documented interface between natural language and infrastructure**. The AI doesn't generate raw YAML (which it might get wrong). It calls typed Python methods (which validate themselves).

Three clients, one codebase:

| Client | Interface | Validation |
|--------|-----------|------------|
| Human in IDE | Autocompletion + type hints | Static + runtime |
| AI via MCP | Tool schema from decorators | Same runtime checks |
| CI/CD pipeline | Python script, headless | Same runtime checks |

Same builder. Same validation. Same documentation. Three modes of interaction.

---

## How It Compares

| | Raw YAML | Helm/Kustomize | Pulumi/CDK | genro-scriba |
|---|---|---|---|---|
| **Autocompletion** | No | No | Yes | Yes |
| **Built-in docs** | No | No | Partial | Full (docstrings) |
| **Structural validation** | No | Schema | Runtime | Build-time |
| **Multi-tool** | No | No | Yes | Yes (shared data) |
| **Reusable patterns** | Copy-paste | Templates | Functions | @component |
| **AI-ready** | No | No | Partial | Native (MCP) |
| **Selective recompile** | N/A | No | Partial | Yes |
| **Learning curve** | Tool docs | Tool + Helm | Tool + SDK | Just Python |

Helm and Kustomize are YAML preprocessors — they operate at the text level, not the semantic level. Pulumi and CDK are closer in spirit, but they're designed to *orchestrate* infrastructure, not just *configure* it.

genro-scriba deliberately does less: **it generates configuration files, nothing more**. No state management, no API calls, no drift detection. It's a compiler from typed Python to YAML. This constraint is a feature — it composes with any deployment workflow rather than replacing it.

---

## Getting Started

Install the core and the builders you need:

```bash
pip install genro-scriba genro-traefik genro-compose
```

Write a recipe:

```python
from genro_traefik import TraefikApp

class MyProxy(TraefikApp):
    def recipe(self, root):
        root.https_setup(email="^acme.email")
        http = root.http()
        http.web_service(name="api", rule="^api.rule",
                         backends=["^api.backend"])

proxy = MyProxy(data={
    "acme.email": "ops@mycompany.com",
    "api.rule": "Host(`api.mycompany.com`)",
    "api.backend": "http://localhost:8080",
})
print(proxy.to_yaml())
```

That's it. Valid, production-ready Traefik YAML from 10 lines of Python.

---

## The Bigger Picture

For fifteen years, the [Genropy](https://www.genropy.org) framework has been built on a data structure called `Bag` — a hierarchical, observable, pointer-aware tree. It was designed for building web applications, but the abstraction turns out to be exactly what infrastructure configuration needs: a semantic tree with typed nodes, structural constraints, and reactive updates.

genro-scriba is a natural extension of this idea. And with LLMs becoming the de facto interface for developer tools, having a typed, documented, structurally validated tree of configuration elements — one that maps directly to MCP tool calls — isn't just convenient. It might be the right abstraction for the next era of infrastructure management.

**The builder is the grammar. The grammar is the documentation. The documentation is the AI tool schema.**

Same code, three audiences. That's the bet.

---

*genro-scriba is open source under the Apache 2.0 license. The project is in alpha — contributions and feedback are welcome.*

*[GitHub: genro-scriba](https://github.com/niccolomineo/genro-scriba) | [Genropy](https://www.genropy.org)*
