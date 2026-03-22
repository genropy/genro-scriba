# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Multi-service platform — parametric Traefik v3 configuration.

Uses relative pointers (^.xxx) with datapath to keep the recipe clean.
The recipe defines STRUCTURE, the data Bag holds VALUES.
Change data → YAML updates automatically.

Run:
    PYTHONPATH=src python examples/multi_service_platform/multi_service_platform.py
"""

from __future__ import annotations

from pathlib import Path

from genro_traefik import TraefikApp


class MultiServicePlatform(TraefikApp):
    """Four services behind Traefik — structure fixed, values from data."""

    def recipe(self, root):
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
        root.accessLog(format="json", bufferingSize=100)

        # Shared middlewares
        http = root.http()
        mw = http.middlewares()
        mw.headers(name="security-headers",
                   stsSeconds=63072000, stsIncludeSubdomains=True,
                   stsPreload=True, contentTypeNosniff=True,
                   browserXssFilter=True, frameDeny=True,
                   referrerPolicy="strict-origin-when-cross-origin")
        mw.compress(name="compress-resp", minResponseBodyBytes=1024)
        mw.ipAllowList(name="ip-whitelist", datapath="admin",
                       sourceRange="^.allowed_ips")
        mw.rateLimit(name="rate-api", average=200, burst=50, period="1m")
        mw.forwardAuth(name="auth-admin", datapath="admin",
                       address="^.auth_url",
                       trustForwardHeader=True,
                       authResponseHeaders=["X-Auth-User", "X-Auth-Role"])

        routers = http.routers()
        services = http.services()

        # API — rate limited, 3 backends
        r = routers.router(name="api-router", datapath="api",
                           rule="^.rule", service="api-svc",
                           entryPoints=["websecure"],
                           middlewares=["security-headers", "compress-resp",
                                        "rate-api"])
        r.routerTls(certResolver="letsencrypt")
        svc = services.service(name="api-svc", datapath="api")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="^.primary")
        lb.server(url="^.secondary")
        lb.server(url="^.tertiary")
        lb.healthCheck(path="/healthz", interval="10s", timeout="3s")

        # Web — plain, 2 backends
        r = routers.router(name="web-router", datapath="web",
                           rule="^.rule", service="web-svc",
                           entryPoints=["websecure"],
                           middlewares=["security-headers", "compress-resp"])
        r.routerTls(certResolver="letsencrypt")
        svc = services.service(name="web-svc", datapath="web")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="^.primary")
        lb.server(url="^.secondary")
        lb.healthCheck(path="/", interval="10s", timeout="3s")

        # Admin — IP restricted + forward auth
        r = routers.router(name="admin-router", datapath="admin",
                           rule="^.rule", service="admin-svc",
                           entryPoints=["websecure"],
                           middlewares=["security-headers", "compress-resp",
                                        "ip-whitelist", "auth-admin"])
        r.routerTls(certResolver="letsencrypt")
        svc = services.service(name="admin-svc", datapath="admin")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="^.backend")
        lb.healthCheck(path="/health", interval="10s", timeout="3s")

        # WebSocket — plain, 2 backends
        r = routers.router(name="ws-router", datapath="ws",
                           rule="^.rule", service="ws-svc",
                           entryPoints=["websecure"],
                           middlewares=["security-headers", "compress-resp"])
        r.routerTls(certResolver="letsencrypt")
        svc = services.service(name="ws-svc", datapath="ws")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="^.primary")
        lb.server(url="^.secondary")
        lb.healthCheck(path="/ping", interval="10s", timeout="3s")


def main():
    platform = MultiServicePlatform()

    platform.data["acme.email"] = "infra@myplatform.io"

    platform.data["api.rule"] = "Host(`api.myplatform.io`)"
    platform.data["api.primary"] = "http://10.0.1.10:8000"
    platform.data["api.secondary"] = "http://10.0.1.11:8000"
    platform.data["api.tertiary"] = "http://10.0.1.12:8000"

    platform.data["web.rule"] = "Host(`web.myplatform.io`)"
    platform.data["web.primary"] = "http://10.0.2.10:3000"
    platform.data["web.secondary"] = "http://10.0.2.11:3000"

    platform.data["admin.rule"] = "Host(`admin.myplatform.io`)"
    platform.data["admin.backend"] = "http://10.0.3.10:9000"
    platform.data["admin.allowed_ips"] = ["192.168.1.0/24", "10.10.0.0/16"]
    platform.data["admin.auth_url"] = "http://auth-service:4181/verify"

    platform.data["ws.rule"] = "Host(`ws.myplatform.io`)"
    platform.data["ws.primary"] = "http://10.0.4.10:8080"
    platform.data["ws.secondary"] = "http://10.0.4.11:8080"

    dest = Path(__file__).parent / "traefik.yml"
    yaml_str = platform.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
