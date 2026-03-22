# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Web application with database — Docker Compose configuration.

Uses @component shortcuts for common patterns:
- postgres: PostgreSQL service with healthcheck and named volume
- redis: Redis cache service with named volume

Run:
    PYTHONPATH=src python examples/web_with_database/web_with_database.py
"""

from __future__ import annotations

from pathlib import Path

from genro_compose import ComposeApp


class WebStack(ComposeApp):
    """Three-tier web application stack."""

    def recipe(self, root):
        root.postgres(name="db", db_name="^db.name",
                      user="^db.user", password="^db.password")
        root.redis()

        api = root.service(
            name="api", image="myapp-api:latest", datapath="api",
            restart="unless-stopped",
            ports=["8080:8080"],
            environment={"DATABASE_URL": "^.database_url",
                         "REDIS_URL": "^.redis_url"})
        api.build_config(context=".", target="production")
        api.healthcheck(test="curl -f http://localhost:8080/health",
                        interval="10s", timeout="3s", retries=3)
        api.depends_on_condition(service="db",
                                 condition="service_healthy")


def main():
    stack = WebStack(data={
        "db.name": "myapp",
        "db.user": "app",
        "db.password": "s3cret!",
        "api.database_url": "postgresql://app:s3cret!@db:5432/myapp",
        "api.redis_url": "redis://cache:6379/0",
    })

    dest = Path(__file__).parent / "docker-compose.yml"
    yaml_str = stack.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
