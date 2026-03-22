# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""TraefikBuilder - Traefik v3 configuration as a semantic Bag builder.

Each @element defines a Traefik entity. Parameters use Traefik's original
camelCase names. compile_* methods tell the compiler how to render entities
that need special handling. Entities without compile_* use compile_default
(tag as YAML key, dump attrs + recurse children).

Naming:
    - camelCase everywhere, matching Traefik YAML names
    - _ prefix only for Python keyword/builtin conflicts (_file)
    - compile_* only where rendering differs from default
"""

from __future__ import annotations

from genro_bag import BagBuilderBase
from genro_bag.builders import element

from ..traefik_compiler import render_attrs


def _named(yaml_section, node, result, builder):
    """Render named entity into a YAML section dict."""
    name = node.attr.get("name", node.label)
    result.setdefault(yaml_section, {})[name] = render_attrs(node, builder)


def _named_direct(node, result, builder):
    """Render named entity directly into parent dict."""
    name = node.attr.get("name", node.label)
    result[name] = render_attrs(node, builder)


def _list_item(yaml_key, node, result, builder):
    """Render entity as list item."""
    result.setdefault(yaml_key, []).append(render_attrs(node, builder))


def _middleware(mw_type_key, node, result, builder):
    """Render middleware as name → {type: attrs}."""
    name = node.attr.get("name", node.label)
    result[name] = {mw_type_key: render_attrs(node, builder)}


class TraefikBuilder(BagBuilderBase):
    """Traefik v3 configuration grammar."""

    # =========================================================================
    # ROOT
    # =========================================================================

    @element(sub_tags=(
        "entryPoint, api, certificateResolver, providers,"
        " log, accessLog, metrics, tracing, ping,"
        " http, tcp, udp, globalTls"
    ))
    def traefik(self, checkNewVersion: bool = True,
                sendAnonymousUsage: bool = True):
        """Root of the Traefik v3 configuration.

        Args:
            checkNewVersion: Check for Traefik updates. Default: True.
            sendAnonymousUsage: Send anonymous stats. Default: True.

        Docs: https://doc.traefik.io/traefik/
        """
        ...

    # =========================================================================
    # STATIC: ENTRYPOINTS
    # =========================================================================

    @element(sub_tags="redirect")
    def entryPoint(self, name: str = "", address: str = "",
                   proxyProtocol_trustedIPs: str = "",
                   proxyProtocol_insecure: bool = False,
                   forwardedHeaders_trustedIPs: str = "",
                   forwardedHeaders_insecure: bool = False):
        """Network listener for incoming connections.

        Args:
            name: EntryPoint name (e.g. "web", "websecure").
            address: Listen address (e.g. ":80", ":443").
        """
        ...

    def compile_entryPoint(self, node, result):
        _named("entryPoints", node, result, self)

    @element(sub_tags="")
    def redirect(self, to: str = "", scheme: str = "https",
                 permanent: bool = True):
        """EntryPoint-level HTTP → HTTPS redirect.

        Args:
            to: Target entryPoint name (e.g. "websecure").
            scheme: Target scheme. Default: "https".
            permanent: 301 (True) or 302 (False).
        """
        ...

    def compile_redirect(self, node, result):
        result.setdefault("http", {}).setdefault(
            "redirections", {})["entryPoint"] = render_attrs(node, self)

    # =========================================================================
    # STATIC: API
    # =========================================================================

    @element(sub_tags="")
    def api(self, dashboard: bool = True, insecure: bool = False,
            debug: bool = False):
        """Traefik API and web dashboard.

        Args:
            dashboard: Enable web UI.
            insecure: Expose without auth. NEVER in production.
            debug: Enable debug endpoints.
        """
        ...

    # =========================================================================
    # STATIC: CERTIFICATES
    # =========================================================================

    @element(sub_tags="acme")
    def certificateResolver(self, name: str = ""):
        """Automatic TLS certificate resolver (e.g. Let's Encrypt).

        Args:
            name: Resolver name. Referenced by routers via
                routerTls(certResolver="letsencrypt").
        """
        ...

    def compile_certificateResolver(self, node, result):
        _named("certificatesResolvers", node, result, self)

    @element(sub_tags="httpChallenge[:1], tlsChallenge[:1], dnsChallenge[:1]")
    def acme(self, email: str = "", storage: str = "acme.json",
             caServer: str = ""):
        """ACME protocol. Exactly ONE challenge type required.

        Args:
            email: Contact email.
            storage: Cert storage file (persistent, 600 permissions).
            caServer: CA server URL.
        """
        ...

    @element(sub_tags="")
    def httpChallenge(self, entryPoint: str = "web"):
        """HTTP-01 challenge — CA verifies via HTTP on port 80."""
        ...

    @element(sub_tags="")
    def tlsChallenge(self):
        """TLS-ALPN-01 challenge — CA verifies via TLS on port 443."""
        ...

    def compile_tlsChallenge(self, node, result):
        result["tlsChallenge"] = {}

    @element(sub_tags="")
    def dnsChallenge(self, provider: str = "",
                     delayBeforeCheck: str = "",
                     resolvers: str = "",
                     disablePropagationCheck: bool = False):
        """DNS-01 challenge — supports wildcard certs.

        Args:
            provider: DNS provider ("cloudflare", "route53", etc.).
            resolvers: DNS servers (comma-separated).
        """
        ...

    # =========================================================================
    # STATIC: PROVIDERS
    # =========================================================================

    @element(sub_tags=(
        "_file, docker, kubernetesCRD, kubernetesIngress,"
        " redis, etcd, zooKeeper,"
        " consul, consulCatalog, nomad, ecs"
    ))
    def providers(self):
        """Provider configuration — where Traefik discovers services."""
        ...

    @element(sub_tags="")
    def _file(self, directory: str = "", filename: str = "",
              watch: bool = True):
        """File provider — config from YAML/TOML files.

        Args:
            directory: Path to directory with config files.
            filename: Single config file (mutually exclusive with directory).
            watch: Auto-reload on changes. Default: True.
        """
        ...

    def compile__file(self, node, result):
        result["file"] = render_attrs(node, self)

    @element(sub_tags="")
    def docker(self, endpoint: str = "",
               exposedByDefault: bool = True,
               network: str = "", watch: bool = True):
        """Docker provider — discover from container labels.

        Args:
            endpoint: Docker daemon endpoint.
            exposedByDefault: Auto-expose all containers. False in production.
            network: Default Docker network.
            watch: React to container events.
        """
        ...

    @element(sub_tags="")
    def redis(self, endpoints: str = "",
              rootKey: str = "traefik",
              username: str = "", password: str = "",
              db: int = 0):
        """Redis KV provider."""
        ...

    @element(sub_tags="")
    def etcd(self, endpoints: str = "",
             rootKey: str = "traefik",
             username: str = "", password: str = ""):
        """etcd KV provider."""
        ...

    @element(
        tags=(
            "kubernetesCRD, kubernetesIngress,"
            " zooKeeper, consul, consulCatalog, nomad, ecs"
        ),
        sub_tags="",
    )
    def otherProvider(self):
        """Other providers (Kubernetes, ZooKeeper, Consul, Nomad, ECS)."""
        ...

    # =========================================================================
    # STATIC: LOGGING
    # =========================================================================

    @element(sub_tags="")
    def log(self, level: str = "ERROR", filePath: str = "",
            format: str = "common", maxSize: int = 0,
            maxBackups: int = 0, maxAge: int = 0,
            compress: bool = False, noColor: bool = False):
        """Application log.

        Args:
            level: DEBUG, INFO, WARN, ERROR (default), FATAL, PANIC.
            filePath: Log file. Empty = stdout.
            format: "common" or "json".
        """
        ...

    @element(sub_tags="")
    def accessLog(self, filePath: str = "", format: str = "common",
                  bufferingSize: int = 0, statusCodes: str = "",
                  retryAttempts: bool = False,
                  minDuration: str = ""):
        """HTTP access log. Adding this element enables it."""
        ...

    # =========================================================================
    # STATIC: METRICS, TRACING, PING
    # =========================================================================

    @element(sub_tags="")
    def metrics(self, prometheus_entryPoint: str = "traefik",
                addRoutersLabels: bool = False,
                addServicesLabels: bool = False,
                buckets: str = ""):
        """Prometheus metrics at /metrics."""
        ...

    @element(sub_tags="")
    def tracing(self, otlp: bool = True):
        """OpenTelemetry distributed tracing."""
        ...

    @element(sub_tags="")
    def ping(self, entryPoint: str = "traefik",
             manualRouting: bool = False,
             terminatingStatusCode: int = 503):
        """Health check endpoint (/ping)."""
        ...

    # =========================================================================
    # DYNAMIC: HTTP
    # =========================================================================

    @element(sub_tags="routers, services, middlewares, serversTransports")
    def http(self):
        """HTTP dynamic configuration."""
        ...

    @element(sub_tags="router")
    def routers(self):
        """HTTP routers container."""
        ...

    @element(sub_tags="service")
    def services(self):
        """HTTP services container."""
        ...

    @element(sub_tags=(
        "basicAuth, digestAuth, forwardAuth,"
        " headers, ipAllowList, inFlightReq,"
        " rateLimit, retry, circuitBreaker,"
        " chain, compress, contentType, buffering,"
        " stripPrefix, stripPrefixRegex,"
        " addPrefix, replacePath, replacePathRegex,"
        " redirectScheme, redirectRegex,"
        " errorsPage, grpcWeb,"
        " passTLSClientCert, mwPlugin"
    ))
    def middlewares(self):
        """HTTP middlewares container."""
        ...

    @element(sub_tags="serversTransport")
    def serversTransports(self):
        """HTTP serversTransports container."""
        ...

    # --- Routers ---

    @element(sub_tags="routerTls, observability")
    def router(self, name: str = "", rule: str = "",
               service: str = "", entryPoints: str | list = "",
               middlewares: str | list = "", priority: int = 0):
        """HTTP router — matches requests, forwards to service.

        Args:
            name: Router name (YAML key).
            rule: Match expression (Host, PathPrefix, etc.).
            service: Target service name.
            entryPoints: EntryPoint(s) — list or comma-separated.
            middlewares: Middleware(s) in order.
            priority: Evaluation order. Auto if 0.
        """
        ...

    def compile_router(self, node, result):
        _named_direct(node, result, self)

    @element(sub_tags="domain")
    def routerTls(self, certResolver: str = "", options: str = ""):
        """TLS on HTTP router. Adding this enables HTTPS.

        Args:
            certResolver: Certificate resolver name.
            options: TLS options set name.
        """
        ...

    def compile_routerTls(self, node, result):
        result["tls"] = render_attrs(node, self)

    @element(sub_tags="")
    def domain(self, main: str = "", sans: str = ""):
        """Domain for TLS certificate generation."""
        ...

    def compile_domain(self, node, result):
        result.setdefault("domains", []).append(render_attrs(node, self))

    @element(sub_tags="")
    def observability(self, accessLogs: bool = True,
                      metrics: bool = True, tracing: bool = True,
                      traceVerbosity: str = ""):
        """Per-router observability overrides (Traefik v3)."""
        ...

    # --- Services ---

    @element(sub_tags="loadBalancer[:1], weighted[:1], mirroring[:1], failover[:1]")
    def service(self, name: str = ""):
        """HTTP service. Must contain exactly ONE type."""
        ...

    def compile_service(self, node, result):
        _named_direct(node, result, self)

    @element(sub_tags="server[1:], healthCheck[:1], sticky[:1], passiveHealthCheck[:1]")
    def loadBalancer(self, passHostHeader: bool = True,
                     serversTransport: str = ""):
        """Load balancer — round-robin across backends.

        Args:
            passHostHeader: Forward original Host header.
            serversTransport: Transport name for backend TLS.
        """
        ...

    @element(sub_tags="")
    def server(self, url: str = "", weight: int = 1,
               preservePath: bool = False):
        """Backend server in load balancer pool.

        Args:
            url: Full URL (e.g. "http://192.168.1.10:8080").
            weight: Traffic weight. 0 = drain.
        """
        ...

    def compile_server(self, node, result):
        _list_item("servers", node, result, self)

    @element(sub_tags="")
    def healthCheck(self, path: str = "", interval: str = "30s",
                    timeout: str = "5s", scheme: str = "",
                    hostname: str = "", port: int = 0,
                    method: str = "GET", status: int = 0,
                    followRedirects: bool = True,
                    mode: str = "http"):
        """Active health check — probe backends periodically.

        Args:
            path: HTTP path (e.g. "/health").
            interval: Between probes. Default: "30s".
            timeout: Max wait. Default: "5s".
        """
        ...

    @element(sub_tags="")
    def sticky(self, cookie_name: str = "", cookie_secure: bool = False,
               cookie_httpOnly: bool = False, cookie_sameSite: str = "",
               cookie_maxAge: int = 0, cookie_path: str = "",
               cookie_domain: str = ""):
        """Sticky sessions via cookie."""
        ...

    @element(sub_tags="")
    def passiveHealthCheck(self, failureWindow: str = "30s",
                           maxFailedAttempts: int = 0):
        """Passive health check — watches real traffic failures."""
        ...

    @element(sub_tags="weightedService, sticky")
    def weighted(self):
        """Weighted round-robin (canary, A/B testing)."""
        ...

    @element(sub_tags="")
    def weightedService(self, name: str = "", weight: int = 1):
        """Service in weighted pool."""
        ...

    def compile_weightedService(self, node, result):
        _list_item("services", node, result, self)

    @element(sub_tags="mirror")
    def mirroring(self, service: str = "",
                  mirrorBody: bool = True, maxBodySize: int = -1):
        """Traffic mirroring — copy traffic to test services."""
        ...

    @element(sub_tags="")
    def mirror(self, name: str = "", percent: int = 100):
        """Mirror target."""
        ...

    def compile_mirror(self, node, result):
        _list_item("mirrors", node, result, self)

    @element(sub_tags="")
    def failover(self, service: str = "", fallback: str = ""):
        """Failover — primary with automatic fallback."""
        ...

    # =========================================================================
    # DYNAMIC: HTTP MIDDLEWARES
    # =========================================================================

    @element(sub_tags="")
    def basicAuth(self, name: str = "", users: list | str = "",
                  usersFile: str = "", realm: str = "traefik",
                  removeHeader: bool = False, headerField: str = ""):
        """HTTP Basic authentication. Always use with HTTPS."""
        ...

    def compile_basicAuth(self, node, result):
        _middleware("basicAuth", node, result, self)

    @element(sub_tags="")
    def digestAuth(self, name: str = "", users: list | str = "",
                   usersFile: str = "", realm: str = "traefik",
                   removeHeader: bool = False, headerField: str = ""):
        """HTTP Digest authentication."""
        ...

    def compile_digestAuth(self, node, result):
        _middleware("digestAuth", node, result, self)

    @element(sub_tags="")
    def forwardAuth(self, name: str = "", address: str = "",
                    trustForwardHeader: bool = False,
                    authResponseHeaders: str | list = "",
                    authResponseHeadersRegex: str = "",
                    authRequestHeaders: str | list = "",
                    headerField: str = "",
                    forwardBody: bool = False,
                    maxBodySize: int = 0,
                    preserveLocationHeader: bool = False,
                    preserveRequestMethod: bool = False):
        """External authentication (RECOMMENDED for production)."""
        ...

    def compile_forwardAuth(self, node, result):
        _middleware("forwardAuth", node, result, self)

    @element(sub_tags="")
    def headers(self, name: str = "",
                customRequestHeaders: str = "",
                customResponseHeaders: str = "",
                accessControlAllowCredentials: bool = False,
                accessControlAllowHeaders: str = "",
                accessControlAllowMethods: str = "",
                accessControlAllowOriginList: str = "",
                accessControlAllowOriginListRegex: str = "",
                accessControlExposeHeaders: str = "",
                accessControlMaxAge: int = 0,
                addVaryHeader: bool = False,
                stsSeconds: int = 0,
                stsIncludeSubdomains: bool = False,
                stsPreload: bool = False,
                forceSTSHeader: bool = False,
                frameDeny: bool = False,
                customFrameOptionsValue: str = "",
                contentTypeNosniff: bool = False,
                browserXssFilter: bool = False,
                contentSecurityPolicy: str = "",
                referrerPolicy: str = "",
                permissionsPolicy: str = "",
                isDevelopment: bool = False):
        """Headers — custom headers + CORS + security."""
        ...

    def compile_headers(self, node, result):
        _middleware("headers", node, result, self)

    @element(sub_tags="")
    def ipAllowList(self, name: str = "", sourceRange: str | list = "",
                    rejectStatusCode: int = 403,
                    ipStrategy_depth: int = 0,
                    ipStrategy_excludedIPs: str = ""):
        """IP-based access control."""
        ...

    def compile_ipAllowList(self, node, result):
        _middleware("ipAllowList", node, result, self)

    @element(sub_tags="")
    def rateLimit(self, name: str = "", average: int = 0,
                  burst: int = 1, period: str = "1s",
                  sourceCriterion_requestHeaderName: str = "",
                  sourceCriterion_requestHost: bool = False):
        """Rate limiting (token bucket)."""
        ...

    def compile_rateLimit(self, node, result):
        _middleware("rateLimit", node, result, self)

    @element(sub_tags="")
    def inFlightReq(self, name: str = "", amount: int = 0,
                    sourceCriterion_requestHeaderName: str = "",
                    sourceCriterion_requestHost: bool = False):
        """Concurrent request limit."""
        ...

    def compile_inFlightReq(self, node, result):
        _middleware("inFlightReq", node, result, self)

    @element(sub_tags="")
    def retry(self, name: str = "", attempts: int = 1,
              initialInterval: str = "100ms"):
        """Retry failed requests on next server."""
        ...

    def compile_retry(self, node, result):
        _middleware("retry", node, result, self)

    @element(sub_tags="")
    def circuitBreaker(self, name: str = "", expression: str = "",
                       checkPeriod: str = "100ms",
                       fallbackDuration: str = "10s",
                       recoveryDuration: str = "10s",
                       responseCode: int = 503):
        """Circuit breaker — stop forwarding on failures."""
        ...

    def compile_circuitBreaker(self, node, result):
        _middleware("circuitBreaker", node, result, self)

    @element(sub_tags="")
    def chain(self, name: str = "", middlewares: str | list = ""):
        """Combine multiple middlewares into one."""
        ...

    def compile_chain(self, node, result):
        _middleware("chain", node, result, self)

    @element(sub_tags="")
    def compress(self, name: str = "",
                 excludedContentTypes: str = "",
                 includedContentTypes: str = "",
                 minResponseBodyBytes: int = 1024,
                 encodings: str = "", defaultEncoding: str = ""):
        """Response compression (gzip, brotli, zstd)."""
        ...

    def compile_compress(self, node, result):
        _middleware("compress", node, result, self)

    @element(sub_tags="")
    def contentType(self, name: str = "", autoDetect: bool = True):
        """Content-Type auto-detection."""
        ...

    def compile_contentType(self, node, result):
        _middleware("contentType", node, result, self)

    @element(sub_tags="")
    def buffering(self, name: str = "",
                  maxRequestBodyBytes: int = 0,
                  memRequestBodyBytes: int = 1048576,
                  maxResponseBodyBytes: int = 0,
                  memResponseBodyBytes: int = 1048576,
                  retryExpression: str = ""):
        """Request/response buffering."""
        ...

    def compile_buffering(self, node, result):
        _middleware("buffering", node, result, self)

    @element(sub_tags="")
    def stripPrefix(self, name: str = "", prefixes: str | list = "",
                    forceSlash: bool = False):
        """Strip URL prefix. Original in X-Forwarded-Prefix."""
        ...

    def compile_stripPrefix(self, node, result):
        _middleware("stripPrefix", node, result, self)

    @element(sub_tags="")
    def stripPrefixRegex(self, name: str = "", regex: str | list = ""):
        """Strip prefix using regex."""
        ...

    def compile_stripPrefixRegex(self, node, result):
        _middleware("stripPrefixRegex", node, result, self)

    @element(sub_tags="")
    def addPrefix(self, name: str = "", prefix: str = ""):
        """Prepend path prefix."""
        ...

    def compile_addPrefix(self, node, result):
        _middleware("addPrefix", node, result, self)

    @element(sub_tags="")
    def replacePath(self, name: str = "", path: str = ""):
        """Replace entire request path."""
        ...

    def compile_replacePath(self, node, result):
        _middleware("replacePath", node, result, self)

    @element(sub_tags="")
    def replacePathRegex(self, name: str = "",
                         regex: str = "", replacement: str = ""):
        """Replace path using regex."""
        ...

    def compile_replacePathRegex(self, node, result):
        _middleware("replacePathRegex", node, result, self)

    @element(sub_tags="")
    def redirectScheme(self, name: str = "", scheme: str = "https",
                       port: str = "", permanent: bool = False):
        """Redirect to different scheme (HTTP → HTTPS)."""
        ...

    def compile_redirectScheme(self, node, result):
        _middleware("redirectScheme", node, result, self)

    @element(sub_tags="")
    def redirectRegex(self, name: str = "", regex: str = "",
                      replacement: str = "", permanent: bool = False):
        """Redirect using regex."""
        ...

    def compile_redirectRegex(self, node, result):
        _middleware("redirectRegex", node, result, self)

    @element(sub_tags="")
    def errorsPage(self, name: str = "", status: str = "",
                   service: str = "", query: str = ""):
        """Custom error pages."""
        ...

    def compile_errorsPage(self, node, result):
        _middleware("errors", node, result, self)

    @element(sub_tags="")
    def grpcWeb(self, name: str = "", allowOrigins: str | list = ""):
        """gRPC-Web protocol support."""
        ...

    def compile_grpcWeb(self, node, result):
        _middleware("grpcWeb", node, result, self)

    @element(sub_tags="")
    def passTLSClientCert(self, name: str = "", pem: bool = False):
        """Forward client TLS certificate (mTLS)."""
        ...

    def compile_passTLSClientCert(self, node, result):
        _middleware("passTLSClientCert", node, result, self)

    @element(sub_tags="")
    def mwPlugin(self, name: str = ""):
        """External middleware plugin (WASM)."""
        ...

    def compile_mwPlugin(self, node, result):
        _middleware("plugin", node, result, self)

    # --- ServersTransports ---

    @element(sub_tags="")
    def serversTransport(self, name: str = "",
                         serverName: str = "",
                         insecureSkipVerify: bool = False,
                         rootCAs: str = "",
                         maxIdleConnsPerHost: int = 200,
                         disableHTTP2: bool = False,
                         peerCertURI: str = "",
                         dialTimeout: str = "30s",
                         responseHeaderTimeout: str = "",
                         idleConnTimeout: str = "90s"):
        """Backend connection transport settings."""
        ...

    def compile_serversTransport(self, node, result):
        _named_direct(node, result, self)

    # =========================================================================
    # DYNAMIC: TCP
    # =========================================================================

    @element(sub_tags="tcpRouters, tcpServices, tcpMiddlewares, tcpServersTransports")
    def tcp(self):
        """TCP dynamic configuration."""
        ...

    @element(sub_tags="tcpRouter")
    def tcpRouters(self):
        """TCP routers container."""
        ...

    def compile_tcpRouters(self, node, result):
        result["routers"] = render_attrs(node, self)

    @element(sub_tags="tcpService")
    def tcpServices(self):
        """TCP services container."""
        ...

    def compile_tcpServices(self, node, result):
        result["services"] = render_attrs(node, self)

    @element(sub_tags="tcpIpAllowList, tcpInFlightConn")
    def tcpMiddlewares(self):
        """TCP middlewares container."""
        ...

    def compile_tcpMiddlewares(self, node, result):
        result["middlewares"] = render_attrs(node, self)

    @element(sub_tags="tcpServersTransport")
    def tcpServersTransports(self):
        """TCP serversTransports container."""
        ...

    def compile_tcpServersTransports(self, node, result):
        result["serversTransports"] = render_attrs(node, self)

    @element(sub_tags="tcpTls")
    def tcpRouter(self, name: str = "", rule: str = "",
                  service: str = "", entryPoints: str | list = "",
                  middlewares: str | list = "", priority: int = 0):
        """TCP router. Rule: HostSNI(`...`) or HostSNI(`*`)."""
        ...

    def compile_tcpRouter(self, node, result):
        _named_direct(node, result, self)

    @element(sub_tags="")
    def tcpTls(self, passthrough: bool = False,
               certResolver: str = "", options: str = ""):
        """TLS for TCP router."""
        ...

    def compile_tcpTls(self, node, result):
        result["tls"] = render_attrs(node, self)

    @element(sub_tags="tcpLoadBalancer[:1], tcpWeighted[:1]")
    def tcpService(self, name: str = ""):
        """TCP service."""
        ...

    def compile_tcpService(self, node, result):
        _named_direct(node, result, self)

    @element(sub_tags="tcpServer[1:]")
    def tcpLoadBalancer(self, serversTransport: str = "",
                        terminationDelay: str = "100ms"):
        """TCP load balancer."""
        ...

    def compile_tcpLoadBalancer(self, node, result):
        result["loadBalancer"] = render_attrs(node, self)

    @element(sub_tags="")
    def tcpServer(self, address: str = "", tls: bool = False):
        """TCP backend server."""
        ...

    def compile_tcpServer(self, node, result):
        _list_item("servers", node, result, self)

    @element(sub_tags="tcpWeightedEntry")
    def tcpWeighted(self):
        """TCP weighted round-robin."""
        ...

    def compile_tcpWeighted(self, node, result):
        result["weighted"] = render_attrs(node, self)

    @element(sub_tags="")
    def tcpWeightedEntry(self, name: str = "", weight: int = 1):
        """TCP weighted service entry."""
        ...

    def compile_tcpWeightedEntry(self, node, result):
        _list_item("services", node, result, self)

    @element(sub_tags="")
    def tcpIpAllowList(self, name: str = "",
                       sourceRange: str | list = ""):
        """TCP IP allow list middleware."""
        ...

    def compile_tcpIpAllowList(self, node, result):
        _middleware("ipAllowList", node, result, self)

    @element(sub_tags="")
    def tcpInFlightConn(self, name: str = "", amount: int = 0):
        """TCP concurrent connection limit."""
        ...

    def compile_tcpInFlightConn(self, node, result):
        _middleware("inFlightConn", node, result, self)

    @element(sub_tags="")
    def tcpServersTransport(self, name: str = "",
                            dialTimeout: str = "30s",
                            dialKeepAlive: str = "",
                            terminationDelay: str = ""):
        """TCP backend transport settings."""
        ...

    def compile_tcpServersTransport(self, node, result):
        _named_direct(node, result, self)

    # =========================================================================
    # DYNAMIC: UDP
    # =========================================================================

    @element(sub_tags="udpRouters, udpServices")
    def udp(self):
        """UDP dynamic configuration."""
        ...

    @element(sub_tags="udpRouter")
    def udpRouters(self):
        """UDP routers container."""
        ...

    def compile_udpRouters(self, node, result):
        result["routers"] = render_attrs(node, self)

    @element(sub_tags="udpService")
    def udpServices(self):
        """UDP services container."""
        ...

    def compile_udpServices(self, node, result):
        result["services"] = render_attrs(node, self)

    @element(sub_tags="")
    def udpRouter(self, name: str = "", service: str = "",
                  entryPoints: str | list = ""):
        """UDP router. No rules — just entryPoint binding."""
        ...

    def compile_udpRouter(self, node, result):
        _named_direct(node, result, self)

    @element(sub_tags="udpLoadBalancer[:1], udpWeighted[:1]")
    def udpService(self, name: str = ""):
        """UDP service."""
        ...

    def compile_udpService(self, node, result):
        _named_direct(node, result, self)

    @element(sub_tags="udpServer[1:]")
    def udpLoadBalancer(self):
        """UDP load balancer."""
        ...

    def compile_udpLoadBalancer(self, node, result):
        result["loadBalancer"] = render_attrs(node, self)

    @element(sub_tags="")
    def udpServer(self, address: str = ""):
        """UDP backend server."""
        ...

    def compile_udpServer(self, node, result):
        _list_item("servers", node, result, self)

    @element(sub_tags="udpWeightedEntry")
    def udpWeighted(self):
        """UDP weighted round-robin."""
        ...

    def compile_udpWeighted(self, node, result):
        result["weighted"] = render_attrs(node, self)

    @element(sub_tags="")
    def udpWeightedEntry(self, name: str = "", weight: int = 1):
        """UDP weighted service entry."""
        ...

    def compile_udpWeightedEntry(self, node, result):
        _list_item("services", node, result, self)

    # =========================================================================
    # DYNAMIC: TLS (global)
    # =========================================================================

    @element(sub_tags="tlsCertificate, tlsOptions, tlsStore")
    def globalTls(self):
        """Global TLS — manual certs, protocol options, stores."""
        ...

    def compile_globalTls(self, node, result):
        result["tls"] = render_attrs(node, self)

    @element(sub_tags="")
    def tlsCertificate(self, certFile: str = "", keyFile: str = "",
                       stores: str = "default"):
        """Manual TLS certificate."""
        ...

    def compile_tlsCertificate(self, node, result):
        _list_item("certificates", node, result, self)

    @element(sub_tags="clientAuth[:1]")
    def tlsOptions(self, name: str = "",
                   minVersion: str = "VersionTLS12",
                   maxVersion: str = "VersionTLS13",
                   cipherSuites: str = "",
                   curvePreferences: str = "",
                   sniStrict: bool = False,
                   alpnProtocols: str = ""):
        """TLS protocol options set."""
        ...

    def compile_tlsOptions(self, node, result):
        _named("options", node, result, self)

    @element(sub_tags="")
    def clientAuth(self, caFiles: str = "",
                   clientAuthType: str = "NoClientCert"):
        """Client TLS authentication (mTLS)."""
        ...

    @element(sub_tags="")
    def tlsStore(self, name: str = "default",
                 defaultCertificate_certFile: str = "",
                 defaultCertificate_keyFile: str = "",
                 defaultGeneratedCert_resolver: str = "",
                 defaultGeneratedCert_domain_main: str = "",
                 defaultGeneratedCert_domain_sans: str = ""):
        """TLS certificate store."""
        ...

    def compile_tlsStore(self, node, result):
        _named("stores", node, result, self)
