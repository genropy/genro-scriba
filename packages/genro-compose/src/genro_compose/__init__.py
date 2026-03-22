# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""genro-compose: Docker Compose configuration builder for Genropy.

Generates validated Docker Compose YAML using the genro-bag builder system.
Each @element docstring references the official Docker Compose documentation.

Example:
    from genro_compose import ComposeApp

    class MyStack(ComposeApp):
        def recipe(self, root):
            web = root.service(name="web", image="nginx:alpine")
            web.port(published="80", target="80")

    stack = MyStack()
    print(stack.to_yaml())
"""

__version__ = "0.1.0"

from .builders.compose_builder import ComposeBuilder
from .compose_app import ComposeApp

__all__ = [
    "ComposeApp",
    "ComposeBuilder",
    "__version__",
]
