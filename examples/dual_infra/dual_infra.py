# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Dual infrastructure — Traefik + Compose from shared data.

ScribaApp coordinates multiple builders with a single data Bag.
Each builder uses only the data it needs (via ^ pointers).
When a data value changes, only the affected builder recompiles.

Run:
    PYTHONPATH=src:packages/genro-traefik/src:packages/genro-compose/src \
        python examples/dual_infra/dual_infra.py
"""

from __future__ import annotations

from pathlib import Path

from genro_scriba import ScribaApp


class DualInfra(ScribaApp):
    """Web API behind Traefik + Compose stack with shared data."""

    def traefik_recipe(self, root):
        # Entry points
        web = root.entryPoint(name="web", address=":80")
        web.redirect(to="websecure", scheme="https", permanent=True)
        root.entryPoint(name="websecure", address=":443")

        # Let's Encrypt
        le = root.certificateResolver(name="letsencrypt")
        acme = le.acme(email="^acme.email",
                       storage="/etc/traefik/acme.json")
        acme.httpChallenge(entryPoint="web")

        root.log(level="INFO", format="json")

        # Dynamic config
        http = root.http()
        mw = http.middlewares()
        mw.headers(name="security-headers",
                   stsSeconds=63072000, stsIncludeSubdomains=True,
                   stsPreload=True, contentTypeNosniff=True,
                   browserXssFilter=True, frameDeny=True,
                   referrerPolicy="strict-origin-when-cross-origin")

        r = http.routers().router(name="api-router", datapath="api",
                                  rule="^.rule", service="api-svc",
                                  entryPoints=["websecure"],
                                  middlewares=["security-headers"])
        r.routerTls(certResolver="letsencrypt")

        svc = http.services().service(name="api-svc", datapath="api")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="^.backend")
        lb.healthCheck(path="/health", interval="10s", timeout="3s")

    def compose_recipe(self, root):
        # API service
        api = root.service(
            name="api", image="myapi:latest", datapath="api",
            restart="unless-stopped",
            ports=["^.port"],
            environment={"DATABASE_URL": "^db.url"})
        api.healthcheck(test="curl -f http://localhost:8080/health",
                        interval="10s", timeout="3s", retries=3)
        api.depends_on_condition(service="db",
                                 condition="service_healthy")

        # Database
        db = root.service(
            name="db", image="postgres:16-alpine", datapath="db",
            restart="always",
            environment={"POSTGRES_DB": "^.name",
                         "POSTGRES_USER": "^.user",
                         "POSTGRES_PASSWORD": "^.password"},
            volumes=["pgdata:/var/lib/postgresql/data"])
        db.healthcheck(test="pg_isready -U app -d myapp",
                       interval="10s", timeout="5s", retries=5)

        root.volume(name="pgdata")


def main():
    here = Path(__file__).parent
    infra = DualInfra(
        traefik_output=str(here / "traefik.yml"),
        compose_output=str(here / "docker-compose.yml"),
    )

    # Shared data — Traefik and Compose each take what they need
    infra.data = {
        "acme.email": "infra@example.com",
        "api.rule": "Host(`api.example.com`)",
        "api.backend": "http://api:8080",
        "api.port": "8080:8080",
        "db.url": "postgresql://app:s3cret!@db:5432/myapp",
        "db.name": "myapp",
        "db.user": "app",
        "db.password": "s3cret!",
    }

    print("=== traefik.yml ===")
    print(infra.to_yaml("traefik"))
    print("=== docker-compose.yml ===")
    print(infra.to_yaml("compose"))


if __name__ == "__main__":
    main()
