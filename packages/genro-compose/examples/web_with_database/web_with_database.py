# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Web application with database — Docker Compose configuration.

The recipe defines STRUCTURE, the data Bag holds VALUES.
^ pointers (absolute or relative via datapath) are resolved at compile time.

Run:
    PYTHONPATH=src python examples/web_with_database/web_with_database.py
"""

from __future__ import annotations

from pathlib import Path

from genro_compose import ComposeApp


class WebStack(ComposeApp):
    """Three-tier web application stack."""

    def recipe(self, root):
        # Nginx reverse proxy
        proxy = root.service(
            name="proxy", image="nginx:alpine", restart="always",
            ports=["80:80", "443:443"],
            volumes=["./nginx/conf.d:/etc/nginx/conf.d:ro"])
        proxy.depends_on_condition(service="api",
                                   condition="service_healthy")

        # Python API
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
        api.deploy(replicas="^.replicas")

        # PostgreSQL
        db = root.service(
            name="db", image="postgres:16-alpine", datapath="db",
            restart="always",
            environment={"POSTGRES_DB": "^.name",
                         "POSTGRES_USER": "^.user",
                         "POSTGRES_PASSWORD": "^.password"},
            volumes=["pgdata:/var/lib/postgresql/data"])
        db.healthcheck(test="pg_isready -U app -d myapp",
                       interval="10s", timeout="5s", retries=5)

        # Redis
        root.service(name="cache", image="redis:7-alpine",
                     restart="always", volumes=["redisdata:/data"])

        # Volumes
        root.volume(name="pgdata")
        root.volume(name="redisdata")


def main():
    stack = WebStack()

    stack.data["db.name"] = "myapp"
    stack.data["db.user"] = "app"
    stack.data["db.password"] = "s3cret!"

    stack.data["api.database_url"] = "postgresql://app:s3cret!@db:5432/myapp"
    stack.data["api.redis_url"] = "redis://cache:6379/0"
    stack.data["api.replicas"] = 2

    dest = Path(__file__).parent / "docker-compose.yml"
    yaml_str = stack.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
