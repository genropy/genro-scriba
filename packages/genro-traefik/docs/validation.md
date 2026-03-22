# Validation

## The check() Method

`TraefikApp.check()` validates the configuration tree and returns a list of error messages:

```python
proxy = MyProxy()
errors = proxy.check()
for err in errors:
    print(err)
```

An empty list means the configuration is structurally valid.

## What Gets Validated

### Sub-tags Cardinality

The builder schema defines which children each element can have, and how many:

| Syntax | Meaning |
|--------|---------|
| `foo` | 0 or more `foo` children |
| `foo[1:]` | At least 1 `foo` child |
| `foo[:1]` | At most 1 `foo` child |
| `""` | No children allowed (leaf node) |

For example, `loadBalancer` requires at least 1 `server`:

```python
@element(sub_tags="server[1:], healthCheck[:1], sticky[:1]")
def loadBalancer(self, ...): ...
```

### Service Mutual Exclusivity

A `service` must have **exactly one** type: `loadBalancer`, `weighted`, `mirroring`, or `failover`. Having zero or more than one is an error:

```python
# Valid
svc = services.service(name="svc")
svc.loadBalancer().server(url="http://localhost:8080")

# Invalid — two types
svc = services.service(name="svc")
svc.loadBalancer().server(url="http://localhost:8080")
svc.weighted()  # ERROR: service must have exactly one type
```

## Validate Before Deploy

```python
proxy = MyProxy()
errors = proxy.check()
if errors:
    print("Configuration errors:")
    for err in errors:
        print(f"  - {err}")
    sys.exit(1)
proxy.to_yaml("/etc/traefik/traefik.yml")
```
