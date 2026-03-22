# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Simple reverse proxy — production-ready Traefik v3 configuration.

Uses @component shortcuts for common patterns and EnvResolver for
environment-specific values (email, hostnames, backend IPs).

Run:
    ACME_EMAIL=admin@example.com API_RULE="Host(\`api.example.com\`)" \\
    API_PRIMARY=http://192.168.1.10:8080 API_SECONDARY=http://192.168.1.11:8080 \\
    PYTHONPATH=src python examples/simple_reverse_proxy/simple_reverse_proxy.py
"""

from __future__ import annotations

from pathlib import Path

from genro_bag.resolvers import EnvResolver
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
        "acme.email": EnvResolver("ACME_EMAIL", default="admin@example.com"),
        "api.rule": EnvResolver("API_RULE", default="Host(`api.example.com`)"),
        "api.primary": EnvResolver("API_PRIMARY", default="http://192.168.1.10:8080"),
        "api.secondary": EnvResolver("API_SECONDARY", default="http://192.168.1.11:8080"),
    })

    dest = Path(__file__).parent / "traefik.yml"
    yaml_str = proxy.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
