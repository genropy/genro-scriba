# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""genro-traefik: Traefik v3 configuration builder for Genropy.

Generates validated Traefik v3 configuration (static + dynamic) using
the genro-bag builder system. The builder IS the documentation — every
@element docstring is an encyclopedic reference for the corresponding
Traefik concept.

Recipe defines STRUCTURE, data Bag holds VALUES.
Attribute values starting with ^ are pointers resolved at compile time.
Changes to data auto-trigger recompile and save.

Example:
    ```python
    from genro_traefik import TraefikApp

    class MyProxy(TraefikApp):
        def recipe(self, root):
            root.entryPoint(name="web", address="^web.address")
            http = root.http()
            http.routers().router(
                name="api", rule="^api.rule",
                service="api-svc", entryPoints=["web"])
            svc = http.services().service(name="api-svc")
            svc.loadBalancer().server(url="^api.backend")

    proxy = MyProxy(output="/etc/traefik/dynamic.yml")
    proxy.data["web.address"] = ":80"
    proxy.data["api.rule"] = "Host(`api.example.com`)"
    proxy.data["api.backend"] = "http://localhost:8080"
    # auto-compiles and writes YAML on every data change
    ```
"""

__version__ = "0.1.0"

from .builders.traefik_builder import TraefikBuilder
from .recipe_from_yaml import recipe_from_yaml
from .traefik_app import TraefikApp

__all__ = [
    "TraefikApp",
    "TraefikBuilder",
    "__version__",
    "recipe_from_yaml",
]
