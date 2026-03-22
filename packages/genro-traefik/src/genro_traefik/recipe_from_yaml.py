# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Generate a TraefikApp recipe from an existing Traefik YAML config.

Usage:
    from genro_traefik.recipe_from_yaml import recipe_from_yaml

    code = recipe_from_yaml("traefik.yml")
    print(code)

    # Or from command line:
    python -m genro_traefik.recipe_from_yaml traefik.yml > my_config.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Middleware YAML key → builder method name
_MW_METHODS: dict[str, str] = {
    "basicAuth": "basicAuth",
    "digestAuth": "digestAuth",
    "forwardAuth": "forwardAuth",
    "headers": "headers",
    "ipAllowList": "ipAllowList",
    "inFlightReq": "inFlightReq",
    "rateLimit": "rateLimit",
    "retry": "retry",
    "circuitBreaker": "circuitBreaker",
    "chain": "chain",
    "compress": "compress",
    "contentType": "contentType",
    "buffering": "buffering",
    "stripPrefix": "stripPrefix",
    "stripPrefixRegex": "stripPrefixRegex",
    "addPrefix": "addPrefix",
    "replacePath": "replacePath",
    "replacePathRegex": "replacePathRegex",
    "redirectScheme": "redirectScheme",
    "redirectRegex": "redirectRegex",
    "errors": "errorsPage",
    "grpcWeb": "grpcWeb",
    "passTLSClientCert": "passTLSClientCert",
    "plugin": "mwPlugin",
}

# Provider YAML key → builder method name
_PROV_METHODS: dict[str, str] = {
    "file": "_file",
}


def _load(source: str | Path | dict[str, Any]) -> dict[str, Any]:
    if isinstance(source, dict):
        return source
    import yaml
    result: dict[str, Any] = yaml.safe_load(Path(source).read_text(encoding="utf-8"))
    return result


def _kw(d: dict[str, Any], skip: set[str] | None = None) -> str:
    """Format dict as Python kwargs string."""
    parts = []
    for k, v in d.items():
        if skip and k in skip:
            continue
        if isinstance(v, str):
            parts.append(f'{k}="{v}"')
        elif isinstance(v, bool):
            parts.append(f"{k}={v}")
        elif isinstance(v, list):
            parts.append(f"{k}={v!r}")
        elif isinstance(v, (int, float)):
            parts.append(f"{k}={v}")
    return ", ".join(parts)


def _scalar_kwargs(d: dict[str, Any], skip: set[str] | None = None) -> dict[str, Any]:
    """Extract scalar (non-dict, non-list-of-dict) entries."""
    result = {}
    for k, v in d.items():
        if skip and k in skip:
            continue
        if isinstance(v, dict):
            continue
        if isinstance(v, list) and v and isinstance(v[0], dict):
            continue
        result[k] = v
    return result


def recipe_from_yaml(source: str | Path | dict[str, Any],
                     class_name: str = "MyTraefikConfig") -> str:
    """Generate Python recipe source from a Traefik YAML config.

    Args:
        source: Path to YAML file, or already-parsed dict.
        class_name: Name for the generated class.

    Returns:
        Python source code string.
    """
    data = _load(source)
    w = _Writer()

    w.line("from genro_traefik import TraefikApp")
    w.line("")
    w.line("")
    w.line(f"class {class_name}(TraefikApp):")
    w.line("")

    _gen_recipe_index(w, data)
    _gen_recipe_sections(w, data)

    return w.text()


_LOG_KEYS = ("log", "accessLog", "metrics", "tracing", "ping")

_INDEX_ENTRIES: list[tuple[str, str]] = [
    ("entryPoints", "self.entryPoints(root)"),
    ("certificatesResolvers", "self.certificates(root)"),
    ("api", "self.api(root)"),
    ("providers", "self.providers(root)"),
    ("http", "self.dynamic(root.http())"),
    ("tcp", "self.tcpConfig(root.tcp())"),
    ("udp", "self.udpConfig(root.udp())"),
    ("tls", "self.globalTls(root.globalTls())"),
]


def _gen_recipe_index(w: _Writer, data: dict[str, Any]) -> None:
    """Generate the recipe() method — the top-level index."""
    w.line("    def recipe(self, root):", indent=0)
    for key, call in _INDEX_ENTRIES:
        if key in data:
            w.body(call)
    if any(k in data for k in _LOG_KEYS):
        w.body("self.logging(root)")


def _gen_recipe_sections(w: _Writer, data: dict[str, Any]) -> None:
    """Generate all section methods based on data keys."""
    generators: dict[str, Any] = {
        "entryPoints": _gen_entry_points,
        "certificatesResolvers": _gen_certificates,
        "api": _gen_api,
        "providers": _gen_providers,
        "http": _gen_http,
        "tcp": _gen_tcp,
        "udp": _gen_udp,
        "tls": _gen_global_tls,
    }
    for key, gen_fn in generators.items():
        if key in data:
            gen_fn(w, data[key])
    if any(k in data for k in _LOG_KEYS):
        _gen_logging(w, data)


class _Writer:
    """Accumulates lines of Python source."""

    MAX_LINE = 88

    def __init__(self) -> None:
        self._lines: list[str] = []

    def line(self, text: str, indent: int = 0) -> None:
        if text == "":
            self._lines.append("")
        else:
            self._lines.append(" " * indent + text)

    def method(self, name: str, params: str) -> None:
        """Start a new method."""
        self._lines.append("")
        self._lines.append(f"    def {name}({params}):")

    def body(self, text: str) -> None:
        """Add a line to the current method body, wrapping if too long."""
        full = f"        {text}"
        if len(full) <= self.MAX_LINE:
            self._lines.append(full)
            return
        self._lines.append(self._wrap(text))

    def _wrap(self, text: str) -> str:
        """Wrap a function call across multiple lines."""
        # Find the opening paren
        paren = text.find("(")
        if paren == -1 or not text.rstrip().endswith(")"):
            return f"        {text}"

        # Split: "assignment = func(" and kwargs and ")"
        prefix = text[:paren + 1]
        inner = text[paren + 1:-1]  # content between parens
        indent = "        "

        # Parse kwargs respecting nested brackets
        args = _split_kwargs(inner)
        if len(args) <= 1:
            return f"{indent}{text}"

        # Calculate continuation indent: align after opening paren
        # or use standard indent + 8 if prefix is too long
        cont_indent = indent + " " * (len(prefix))
        if len(cont_indent) > 40:
            cont_indent = indent + "        "

        lines = [f"{indent}{prefix}{args[0]},"]
        for arg in args[1:-1]:
            lines.append(f"{cont_indent}{arg},")
        lines.append(f"{cont_indent}{args[-1]})")

        return "\n".join(lines)

    def text(self) -> str:
        return "\n".join(self._lines) + "\n"


def _split_kwargs(s: str) -> list[str]:
    """Split kwargs string respecting nested brackets and quotes."""
    args = []
    current: list[str] = []
    depth = 0
    in_str = False
    str_char = ""

    for ch in s:
        if in_str:
            current.append(ch)
            if ch == str_char:
                in_str = False
            continue

        if ch in ('"', "'"):
            in_str = True
            str_char = ch
            current.append(ch)
        elif ch in ("(", "[", "{"):
            depth += 1
            current.append(ch)
        elif ch in (")", "]", "}"):
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            args.append("".join(current).strip())
            current = []
        else:
            current.append(ch)

    if current:
        rest = "".join(current).strip()
        if rest:
            args.append(rest)

    return args


# =========================================================================
# Section generators
# =========================================================================


def _gen_entry_points(w: _Writer, eps: dict[str, Any]) -> None:
    w.method("entryPoints", "self, root")
    for name, config in eps.items():
        redirect_config = None
        kwargs: dict[str, Any] = {}

        for k, v in config.items():
            if k == "http" and isinstance(v, dict):
                redir = v.get("redirections", {}).get("entryPoint")
                if redir:
                    redirect_config = redir
            else:
                kwargs[k] = v

        kw_str = _kw(kwargs)
        if redirect_config:
            w.body(f'ep = root.entryPoint(name="{name}", {kw_str})')
            redir_kw = _kw(redirect_config)
            w.body(f"ep.redirect({redir_kw})")
        else:
            w.body(f'root.entryPoint(name="{name}", {kw_str})')


def _gen_certificates(w: _Writer, resolvers: dict[str, Any]) -> None:
    w.method("certificates", "self, root")
    for name, config in resolvers.items():
        w.body(f'cr = root.certificateResolver(name="{name}")')
        acme_data = config.get("acme", {})
        if acme_data:
            challenges = ("httpChallenge", "tlsChallenge", "dnsChallenge")
            acme_kwargs = {k: v for k, v in acme_data.items() if k not in challenges}
            kw_str = _kw(acme_kwargs)
            w.body(f"acme = cr.acme({kw_str})")
            for ch in challenges:
                if ch in acme_data:
                    ch_data = acme_data[ch]
                    if isinstance(ch_data, dict) and ch_data:
                        w.body(f"acme.{ch}({_kw(ch_data)})")
                    else:
                        w.body(f"acme.{ch}()")


def _gen_api(w: _Writer, api_data: dict[str, Any]) -> None:
    w.method("api", "self, root")
    w.body(f"root.api({_kw(api_data)})")


def _gen_logging(w: _Writer, data: dict[str, Any]) -> None:
    w.method("logging", "self, root")
    for key in ("log", "accessLog", "metrics", "tracing", "ping"):
        if key in data:
            w.body(f"root.{key}({_kw(_scalar_kwargs(data[key]))})")


def _gen_providers(w: _Writer, providers: dict[str, Any]) -> None:
    w.method("providers", "self, root")
    w.body("prov = root.providers()")
    for key, config in providers.items():
        method = _PROV_METHODS.get(key, key)
        kw_str = _kw(_scalar_kwargs(config)) if isinstance(config, dict) else ""
        w.body(f"prov.{method}({kw_str})")


def _gen_http(w: _Writer, http_data: dict[str, Any]) -> None:
    w.method("dynamic", "self, http")
    if "middlewares" in http_data:
        w.body("self.middlewares(http.middlewares())")
    if "routers" in http_data:
        w.body("self.routing(http.routers())")
    if "services" in http_data:
        w.body("self.backends(http.services())")
    if "serversTransports" in http_data:
        w.body("self.transports(http.serversTransports())")

    if "middlewares" in http_data:
        _gen_middlewares(w, http_data["middlewares"])
    if "routers" in http_data:
        _gen_routers(w, http_data["routers"])
    if "services" in http_data:
        _gen_services(w, http_data["services"])
    if "serversTransports" in http_data:
        _gen_transports(w, http_data["serversTransports"])


def _gen_middlewares(w: _Writer, middlewares: dict[str, Any]) -> None:
    w.method("middlewares", "self, mw")
    for name, config in middlewares.items():
        for mw_type, mw_config in config.items():
            method = _MW_METHODS.get(mw_type, mw_type)
            kw_str = _kw(_scalar_kwargs(mw_config)) if isinstance(mw_config, dict) else ""
            if kw_str:
                w.body(f'mw.{method}(name="{name}", {kw_str})')
            else:
                w.body(f'mw.{method}(name="{name}")')
            break  # one type per middleware


def _gen_routers(w: _Writer, routers: dict[str, Any]) -> None:
    w.method("routing", "self, routers")
    for name, config in routers.items():
        tls_config = config.get("tls")
        obs_config = config.get("observability")
        kwargs = _scalar_kwargs(config, skip={"tls", "observability"})
        kw_str = _kw(kwargs)

        if tls_config or obs_config:
            w.body(f'r = routers.router(name="{name}", {kw_str})')
            if tls_config:
                if isinstance(tls_config, dict) and tls_config:
                    w.body(f"r.routerTls({_kw(_scalar_kwargs(tls_config))})")
                else:
                    w.body("r.routerTls()")
            if obs_config and isinstance(obs_config, dict):
                w.body(f"r.observability({_kw(obs_config)})")
        else:
            w.body(f'routers.router(name="{name}", {kw_str})')


def _gen_services(w: _Writer, services: dict[str, Any]) -> None:
    w.method("backends", "self, services")
    for name, config in services.items():
        w.body(f'svc = services.service(name="{name}")')
        if "loadBalancer" in config:
            _gen_load_balancer(w, config["loadBalancer"])
        elif "weighted" in config:
            _gen_weighted(w, config["weighted"])
        elif "mirroring" in config:
            _gen_mirroring(w, config["mirroring"])
        elif "failover" in config:
            w.body(f"svc.failover({_kw(config['failover'])})")


def _gen_load_balancer(w: _Writer, lb_data: dict[str, Any]) -> None:
    lb_data = dict(lb_data)
    servers = lb_data.pop("servers", [])
    hc = lb_data.pop("healthCheck", None)
    sticky = lb_data.pop("sticky", None)
    phc = lb_data.pop("passiveHealthCheck", None)
    w.body(f"lb = svc.loadBalancer({_kw(_scalar_kwargs(lb_data))})")
    for s in servers:
        w.body(f"lb.server({_kw(s)})")
    if hc:
        w.body(f"lb.healthCheck({_kw(hc)})")
    if sticky and isinstance(sticky, dict):
        sticky_kw: dict[str, Any] = {}
        for sk, sv in sticky.items():
            if isinstance(sv, dict):
                for k2, v2 in sv.items():
                    sticky_kw[f"{sk}_{k2}"] = v2
            else:
                sticky_kw[sk] = sv
        w.body(f"lb.sticky({_kw(sticky_kw)})")
    if phc:
        w.body(f"lb.passiveHealthCheck({_kw(phc)})")


def _gen_weighted(w: _Writer, w_data: dict[str, Any]) -> None:
    w.body("w = svc.weighted()")
    for s in w_data.get("services", []):
        w.body(f"w.weightedService({_kw(s)})")


def _gen_mirroring(w: _Writer, m_data: dict[str, Any]) -> None:
    m_data = dict(m_data)
    mirrors = m_data.pop("mirrors", [])
    w.body(f"m = svc.mirroring({_kw(_scalar_kwargs(m_data))})")
    for mirror in mirrors:
        w.body(f"m.mirror({_kw(mirror)})")


def _gen_transports(w: _Writer, transports: dict[str, Any]) -> None:
    w.method("transports", "self, st")
    for name, config in transports.items():
        w.body(f'st.serversTransport(name="{name}", {_kw(_scalar_kwargs(config))})')


def _gen_tcp(w: _Writer, tcp_data: dict[str, Any]) -> None:
    w.method("tcpConfig", "self, tcp")
    for section, items in tcp_data.items():
        match section:
            case "routers":
                _gen_tcp_routers(w, items)
            case "services":
                _gen_tcp_services(w, items)
            case "middlewares":
                _gen_tcp_middlewares(w, items)


def _gen_tcp_routers(w: _Writer, routers: dict[str, Any]) -> None:
    w.body("routers = tcp.tcpRouters()")
    for name, config in routers.items():
        tls_config = config.get("tls")
        kw_str = _kw(_scalar_kwargs(config, skip={"tls"}))
        if tls_config:
            w.body(f'r = routers.tcpRouter(name="{name}", {kw_str})')
            tls_kw = _kw(_scalar_kwargs(tls_config)) if isinstance(tls_config, dict) else ""
            w.body(f"r.tcpTls({tls_kw})")
        else:
            w.body(f'routers.tcpRouter(name="{name}", {kw_str})')


def _gen_tcp_services(w: _Writer, services: dict[str, Any]) -> None:
    w.body("services = tcp.tcpServices()")
    for name, config in services.items():
        w.body(f'svc = services.tcpService(name="{name}")')
        if "loadBalancer" in config:
            lb = dict(config["loadBalancer"])
            servers = lb.pop("servers", [])
            w.body(f"lb = svc.tcpLoadBalancer({_kw(_scalar_kwargs(lb))})")
            for s in servers:
                w.body(f"lb.tcpServer({_kw(s)})")
        elif "weighted" in config:
            w.body("w = svc.tcpWeighted()")
            for s in config["weighted"].get("services", []):
                w.body(f"w.tcpWeightedEntry({_kw(s)})")


def _gen_tcp_middlewares(w: _Writer, middlewares: dict[str, Any]) -> None:
    w.body("mw = tcp.tcpMiddlewares()")
    for name, config in middlewares.items():
        for mw_type, mw_config in config.items():
            kw_str = _kw(_scalar_kwargs(mw_config)) if isinstance(mw_config, dict) else ""
            method = f"tcp{mw_type[0].upper()}{mw_type[1:]}"
            w.body(f'mw.{method}(name="{name}", {kw_str})' if kw_str
                   else f'mw.{method}(name="{name}")')
            break


def _gen_udp(w: _Writer, udp_data: dict[str, Any]) -> None:
    w.method("udpConfig", "self, udp")
    if "routers" in udp_data:
        w.body("routers = udp.udpRouters()")
        for name, config in udp_data["routers"].items():
            w.body(f'routers.udpRouter(name="{name}", {_kw(_scalar_kwargs(config))})')

    if "services" in udp_data:
        w.body("services = udp.udpServices()")
        for name, config in udp_data["services"].items():
            w.body(f'svc = services.udpService(name="{name}")')
            if "loadBalancer" in config:
                w.body("lb = svc.udpLoadBalancer()")
                for s in config["loadBalancer"].get("servers", []):
                    w.body(f"lb.udpServer({_kw(s)})")


def _gen_global_tls(w: _Writer, tls_data: dict[str, Any]) -> None:
    w.method("globalTls", "self, tls")
    for cert in tls_data.get("certificates", []):
        w.body(f"tls.tlsCertificate({_kw(cert)})")
    for name, opts in tls_data.get("options", {}).items():
        ca = opts.get("clientAuth")
        other = {k: v for k, v in opts.items() if k != "clientAuth"}
        if ca:
            w.body(f'opt = tls.tlsOptions(name="{name}", {_kw(_scalar_kwargs(other))})')
            w.body(f"opt.clientAuth({_kw(ca)})")
        else:
            w.body(f'tls.tlsOptions(name="{name}", {_kw(_scalar_kwargs(other))})')
    for name, store in tls_data.get("stores", {}).items():
        w.body(f'tls.tlsStore(name="{name}", {_kw(_scalar_kwargs(store))})')


# =========================================================================
# CLI
# =========================================================================


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m genro_traefik.recipe_from_yaml <traefik.yml> [ClassName]")
        sys.exit(1)
    yaml_path = sys.argv[1]
    cls_name = sys.argv[2] if len(sys.argv) > 2 else "MyTraefikConfig"
    print(recipe_from_yaml(yaml_path, cls_name))
