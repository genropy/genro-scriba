# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Simple reverse proxy — production-ready Traefik v3 configuration.

Uses @component shortcuts for common patterns:
- https_setup: HTTP→HTTPS redirect + Let's Encrypt
- security_headers: OWASP security headers middleware
- web_service: router + TLS + load balancer + health check

Run:
    PYTHONPATH=src python examples/simple_reverse_proxy/simple_reverse_proxy.py
"""

from __future__ import annotations

from pathlib import Path

from genro_traefik import TraefikApp


class SimpleReverseProxy(TraefikApp):
    """Production Traefik setup with HTTPS, auth, security headers."""

    def recipe(self, root):
        root.https_setup(email="^acme.email")
        root.log(level="INFO", format="json")

        http = root.http()
        mw = http.middlewares()
        mw.security_headers()
        mw.rateLimit(name="rate-limit", average=100, period="1m", burst=50)
        mw.basicAuth(name="auth",
                     users=["admin:$apr1$H6uskkkW$IgXLP6ewTrSuBkTrqE8wj/"],
                     removeHeader=True)

        http.web_service(name="api", rule="^api.rule",
                         backends=["^api.primary", "^api.secondary"],
                         middlewares=["security-headers", "rate-limit", "auth"])


def main():
    proxy = SimpleReverseProxy(data={
        "acme.email": "admin@example.com",
        "api.rule": "Host(`api.example.com`)",
        "api.primary": "http://192.168.1.10:8080",
        "api.secondary": "http://192.168.1.11:8080",
    })

    dest = Path(__file__).parent / "traefik.yml"
    yaml_str = proxy.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
