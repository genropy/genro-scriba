# genro-compose

[![Python versions](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](https://opensource.org/licenses/Apache-2.0)

**Docker Compose configuration builder for Genropy.** Write docker-compose.yml as Python programs.

## Status: Alpha

## Quick Start

```bash
pip install genro-compose
```

```python
from genro_compose import ComposeApp

class MyStack(ComposeApp):
    def recipe(self, root):
        # Web service
        web = root.service(name="web", image="nginx:alpine", restart="always")
        web.port(published="80", target="80")
        web.port(published="443", target="443")
        web.volume_mount(source="./html", target="/usr/share/nginx/html")

        # Database
        db = root.service(name="db", image="postgres:16", restart="always")
        db.environment(name="POSTGRES_PASSWORD", value="secret")
        db.volume_mount(source="pgdata", target="/var/lib/postgresql/data")

        # Named volume
        root.volume(name="pgdata")

stack = MyStack()
print(stack.to_yaml())
```

## License

Apache License 2.0 - see LICENSE file for details.
