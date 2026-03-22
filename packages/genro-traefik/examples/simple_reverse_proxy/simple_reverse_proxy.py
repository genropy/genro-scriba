# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Simple reverse proxy — production-ready Traefik v3 configuration.

The recipe defines STRUCTURE, the data Bag holds VALUES.
^ pointers (absolute or relative via datapath) are resolved at compile time.

Run:
    PYTHONPATH=src python examples/simple_reverse_proxy/simple_reverse_proxy.py
"""

from __future__ import annotations

from pathlib import Path

from genro_traefik import TraefikApp


class SimpleReverseProxy(TraefikApp):
    """Production Traefik setup with HTTPS, auth, security headers."""

    def recipe(self, root):
        # Entry points
        web = root.entryPoint(name="web", address=":80")
        web.redirect(to="websecure", scheme="https", permanent=True)
        root.entryPoint(name="websecure", address=":443")
        root.api(dashboard=True, insecure=True)

        # Let's Encrypt
        le = root.certificateResolver(name="letsencrypt")
        acme = le.acme(email="^acme.email",
                       storage="/etc/traefik/acme.json")
        acme.httpChallenge(entryPoint="web")

        root.log(level="INFO", format="json")

        # Dynamic config
        http = root.http()
        mw = http.middlewares()
        mw.basicAuth(name="auth",
                     users=["admin:$apr1$H6uskkkW$IgXLP6ewTrSuBkTrqE8wj/"],
                     removeHeader=True)
        mw.headers(name="security-headers",
                   stsSeconds=31536000, stsIncludeSubdomains=True,
                   stsPreload=True, contentTypeNosniff=True,
                   browserXssFilter=True, frameDeny=True,
                   referrerPolicy="strict-origin-when-cross-origin")
        mw.rateLimit(name="rate-limit", average=100, period="1m", burst=50)
        mw.chain(name="secure-chain",
                 middlewares=["security-headers", "rate-limit"])

        r = http.routers().router(name="api-router", datapath="api",
                                  rule="^.rule",
                                  service="api-svc",
                                  entryPoints=["websecure"],
                                  middlewares=["secure-chain", "auth"])
        r.routerTls(certResolver="letsencrypt")

        svc = http.services().service(name="api-svc", datapath="api")
        lb = svc.loadBalancer(passHostHeader=True)
        lb.server(url="^.primary")
        lb.server(url="^.secondary")
        lb.healthCheck(path="/health", interval="10s", timeout="3s")


def main():
    proxy = SimpleReverseProxy()
    proxy.data["acme.email"] = "admin@example.com"
    proxy.data["api.rule"] = "Host(`api.example.com`)"
    proxy.data["api.primary"] = "http://192.168.1.10:8080"
    proxy.data["api.secondary"] = "http://192.168.1.11:8080"

    dest = Path(__file__).parent / "traefik.yml"
    yaml_str = proxy.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
