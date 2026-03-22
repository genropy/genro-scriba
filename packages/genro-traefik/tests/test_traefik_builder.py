# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for TraefikBuilder compile_* methods and YAML output structure.

Each test builds a mini-config via the builder API, compiles it with
compile_to_dict, and verifies the resulting dict structure.
"""

from __future__ import annotations

import yaml

from genro_bag import Bag
from genro_traefik import TraefikApp
from genro_traefik.builders.traefik_builder import TraefikBuilder
from genro_traefik.traefik_compiler import compile_to_dict


def _build_and_compile(recipe_fn) -> dict:
    """Helper: create store, call recipe, compile to dict."""
    store = Bag(builder=TraefikBuilder)
    store.builder.data = Bag()  # prevent ^pointer resolution errors
    root = store.traefik(name="t")
    recipe_fn(root)
    return compile_to_dict(root, store.builder)


# =========================================================================
# STATIC: ENTRYPOINTS
# =========================================================================


class TestEntryPoints:

    def test_basic(self) -> None:
        d = _build_and_compile(lambda r: r.entryPoint(name="web", address=":80"))
        assert d["entryPoints"]["web"]["address"] == ":80"

    def test_with_redirect(self) -> None:
        def recipe(root):
            ep = root.entryPoint(name="web", address=":80")
            ep.redirect(to="websecure", scheme="https", permanent=True)

        d = _build_and_compile(recipe)
        redir = d["entryPoints"]["web"]["http"]["redirections"]["entryPoint"]
        assert redir["to"] == "websecure"
        assert redir["scheme"] == "https"
        assert redir["permanent"] is True

    def test_multiple(self) -> None:
        def recipe(root):
            root.entryPoint(name="web", address=":80")
            root.entryPoint(name="websecure", address=":443")

        d = _build_and_compile(recipe)
        assert "web" in d["entryPoints"]
        assert "websecure" in d["entryPoints"]

    def test_proxy_protocol_nesting(self) -> None:
        d = _build_and_compile(
            lambda r: r.entryPoint(name="web", address=":80",
                                   proxyProtocol_insecure=True)
        )
        assert d["entryPoints"]["web"]["proxyProtocol"]["insecure"] is True


# =========================================================================
# STATIC: API
# =========================================================================


class TestApi:

    def test_basic(self) -> None:
        d = _build_and_compile(lambda r: r.api(dashboard=True, insecure=True))
        assert d["api"]["dashboard"] is True
        assert d["api"]["insecure"] is True


# =========================================================================
# STATIC: CERTIFICATES
# =========================================================================


class TestCertificates:

    def test_acme_http_challenge(self) -> None:
        def recipe(root):
            le = root.certificateResolver(name="le")
            acme = le.acme(email="a@b.com", storage="acme.json")
            acme.httpChallenge(entryPoint="web")

        d = _build_and_compile(recipe)
        resolver = d["certificatesResolvers"]["le"]
        assert resolver["acme"]["email"] == "a@b.com"
        assert resolver["acme"]["httpChallenge"]["entryPoint"] == "web"

    def test_acme_tls_challenge(self) -> None:
        def recipe(root):
            le = root.certificateResolver(name="le")
            acme = le.acme(email="a@b.com")
            acme.tlsChallenge()

        d = _build_and_compile(recipe)
        resolver = d["certificatesResolvers"]["le"]
        assert resolver["acme"]["tlsChallenge"] == {}

    def test_acme_dns_challenge(self) -> None:
        def recipe(root):
            le = root.certificateResolver(name="le")
            acme = le.acme(email="a@b.com")
            acme.dnsChallenge(provider="cloudflare")

        d = _build_and_compile(recipe)
        resolver = d["certificatesResolvers"]["le"]
        assert resolver["acme"]["dnsChallenge"]["provider"] == "cloudflare"


# =========================================================================
# STATIC: PROVIDERS
# =========================================================================


class TestProviders:

    def test_docker_provider(self) -> None:
        def recipe(root):
            prov = root.providers()
            prov.docker(endpoint="unix:///var/run/docker.sock",
                        exposedByDefault=False)

        d = _build_and_compile(recipe)
        assert d["providers"]["docker"]["endpoint"] == "unix:///var/run/docker.sock"
        assert d["providers"]["docker"]["exposedByDefault"] is False

    def test_redis_provider(self) -> None:
        def recipe(root):
            prov = root.providers()
            prov.redis(endpoints="localhost:6379", rootKey="traefik")

        d = _build_and_compile(recipe)
        assert d["providers"]["redis"]["rootKey"] == "traefik"


# =========================================================================
# STATIC: LOGGING
# =========================================================================


class TestLogging:

    def test_log(self) -> None:
        d = _build_and_compile(lambda r: r.log(level="INFO", format="json"))
        assert d["log"]["level"] == "INFO"
        assert d["log"]["format"] == "json"

    def test_access_log(self) -> None:
        d = _build_and_compile(lambda r: r.accessLog(format="json", bufferingSize=100))
        assert d["accessLog"]["format"] == "json"
        assert d["accessLog"]["bufferingSize"] == 100

    def test_metrics(self) -> None:
        d = _build_and_compile(lambda r: r.metrics(prometheus_entryPoint="traefik"))
        assert d["metrics"]["prometheus"]["entryPoint"] == "traefik"

    def test_tracing(self) -> None:
        d = _build_and_compile(lambda r: r.tracing(otlp=True))
        assert d["tracing"]["otlp"] is True

    def test_ping(self) -> None:
        d = _build_and_compile(lambda r: r.ping(entryPoint="traefik"))
        assert d["ping"]["entryPoint"] == "traefik"


# =========================================================================
# DYNAMIC: HTTP ROUTERS
# =========================================================================


class TestHttpRouters:

    def test_basic(self) -> None:
        def recipe(root):
            http = root.http()
            http.routers().router(name="r1", rule="Host(`a.com`)",
                                  service="svc", entryPoints=["websecure"])

        d = _build_and_compile(recipe)
        r = d["http"]["routers"]["r1"]
        assert r["rule"] == "Host(`a.com`)"
        assert r["service"] == "svc"

    def test_with_tls(self) -> None:
        def recipe(root):
            http = root.http()
            r = http.routers().router(name="r1", rule="Host(`a.com`)",
                                      service="svc")
            r.routerTls(certResolver="le")

        d = _build_and_compile(recipe)
        assert d["http"]["routers"]["r1"]["tls"]["certResolver"] == "le"

    def test_tls_with_domains(self) -> None:
        def recipe(root):
            http = root.http()
            r = http.routers().router(name="r1", rule="Host(`a.com`)",
                                      service="svc")
            tls = r.routerTls(certResolver="le")
            tls.domain(main="a.com", sans="*.a.com")

        d = _build_and_compile(recipe)
        domains = d["http"]["routers"]["r1"]["tls"]["domains"]
        assert isinstance(domains, list)
        assert domains[0]["main"] == "a.com"

    def test_with_observability(self) -> None:
        def recipe(root):
            http = root.http()
            r = http.routers().router(name="r1", rule="Host(`a.com`)",
                                      service="svc")
            r.observability(accessLogs=True, metrics=False)

        d = _build_and_compile(recipe)
        obs = d["http"]["routers"]["r1"]["observability"]
        assert obs["accessLogs"] is True
        assert obs["metrics"] is False

    def test_middlewares_as_list(self) -> None:
        def recipe(root):
            http = root.http()
            http.routers().router(name="r1", rule="Host(`a.com`)",
                                  service="svc",
                                  middlewares=["auth", "rate"])

        d = _build_and_compile(recipe)
        assert d["http"]["routers"]["r1"]["middlewares"] == ["auth", "rate"]


# =========================================================================
# DYNAMIC: HTTP SERVICES
# =========================================================================


class TestHttpServices:

    def test_load_balancer_with_servers(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            lb = svc.loadBalancer(passHostHeader=True)
            lb.server(url="http://10.0.0.1:8080")
            lb.server(url="http://10.0.0.2:8080")

        d = _build_and_compile(recipe)
        lb = d["http"]["services"]["svc1"]["loadBalancer"]
        assert lb["passHostHeader"] is True
        assert len(lb["servers"]) == 2
        assert lb["servers"][0]["url"] == "http://10.0.0.1:8080"

    def test_load_balancer_with_health_check(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            lb = svc.loadBalancer()
            lb.server(url="http://10.0.0.1:8080")
            lb.healthCheck(path="/health", interval="10s", timeout="3s")

        d = _build_and_compile(recipe)
        hc = d["http"]["services"]["svc1"]["loadBalancer"]["healthCheck"]
        assert hc["path"] == "/health"
        assert hc["interval"] == "10s"

    def test_load_balancer_with_sticky(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            lb = svc.loadBalancer()
            lb.server(url="http://10.0.0.1:8080")
            lb.sticky(cookie_name="srv_id", cookie_secure=True)

        d = _build_and_compile(recipe)
        sticky = d["http"]["services"]["svc1"]["loadBalancer"]["sticky"]
        assert sticky["cookie"]["name"] == "srv_id"
        assert sticky["cookie"]["secure"] is True

    def test_load_balancer_with_passive_health_check(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            lb = svc.loadBalancer()
            lb.server(url="http://10.0.0.1:8080")
            lb.passiveHealthCheck(maxFailedAttempts=5)

        d = _build_and_compile(recipe)
        phc = d["http"]["services"]["svc1"]["loadBalancer"]["passiveHealthCheck"]
        assert phc["maxFailedAttempts"] == 5

    def test_weighted_service(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            w = svc.weighted()
            w.weightedService(name="canary", weight=10)
            w.weightedService(name="stable", weight=90)

        d = _build_and_compile(recipe)
        services = d["http"]["services"]["svc1"]["weighted"]["services"]
        assert len(services) == 2

    def test_mirroring_service(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            m = svc.mirroring(service="main-svc", mirrorBody=True)
            m.mirror(name="test-svc", percent=20)

        d = _build_and_compile(recipe)
        mirr = d["http"]["services"]["svc1"]["mirroring"]
        assert mirr["service"] == "main-svc"
        assert mirr["mirrors"][0]["percent"] == 20

    def test_failover_service(self) -> None:
        def recipe(root):
            http = root.http()
            svc = http.services().service(name="svc1")
            svc.failover(service="primary", fallback="backup")

        d = _build_and_compile(recipe)
        fo = d["http"]["services"]["svc1"]["failover"]
        assert fo["service"] == "primary"
        assert fo["fallback"] == "backup"


# =========================================================================
# DYNAMIC: HTTP MIDDLEWARES
# =========================================================================


class TestHttpMiddlewares:
    """Test all 23+ middleware compile_* methods."""

    def _compile_mw(self, setup_fn) -> dict:
        def recipe(root):
            http = root.http()
            mw = http.middlewares()
            setup_fn(mw)
        return _build_and_compile(recipe)

    def test_basic_auth(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.basicAuth(name="auth", users=["admin:hash"],
                                    removeHeader=True))
        mw = d["http"]["middlewares"]["auth"]["basicAuth"]
        assert mw["users"] == ["admin:hash"]
        assert mw["removeHeader"] is True

    def test_digest_auth(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.digestAuth(name="da", users=["u:r:h"],
                                     realm="test"))
        assert "digestAuth" in d["http"]["middlewares"]["da"]

    def test_forward_auth(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.forwardAuth(name="fa", address="http://auth:4181",
                                      trustForwardHeader=True))
        fa = d["http"]["middlewares"]["fa"]["forwardAuth"]
        assert fa["address"] == "http://auth:4181"
        assert fa["trustForwardHeader"] is True

    def test_headers(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.headers(name="sec", stsSeconds=31536000,
                                  frameDeny=True, contentTypeNosniff=True))
        h = d["http"]["middlewares"]["sec"]["headers"]
        assert h["stsSeconds"] == 31536000
        assert h["frameDeny"] is True

    def test_ip_allow_list(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.ipAllowList(name="ip", sourceRange=["10.0.0.0/8"]))
        assert "ipAllowList" in d["http"]["middlewares"]["ip"]

    def test_rate_limit(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.rateLimit(name="rl", average=100, burst=50,
                                    period="1m"))
        rl = d["http"]["middlewares"]["rl"]["rateLimit"]
        assert rl["average"] == 100
        assert rl["burst"] == 50

    def test_in_flight_req(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.inFlightReq(name="ifr", amount=100))
        assert d["http"]["middlewares"]["ifr"]["inFlightReq"]["amount"] == 100

    def test_retry(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.retry(name="rt", attempts=3,
                                initialInterval="100ms"))
        assert d["http"]["middlewares"]["rt"]["retry"]["attempts"] == 3

    def test_circuit_breaker(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.circuitBreaker(name="cb",
                                         expression="NetworkErrorRatio() > 0.30"))
        cb = d["http"]["middlewares"]["cb"]["circuitBreaker"]
        assert "NetworkErrorRatio" in cb["expression"]

    def test_chain(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.chain(name="ch", middlewares=["a", "b"]))
        assert d["http"]["middlewares"]["ch"]["chain"]["middlewares"] == ["a", "b"]

    def test_compress(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.compress(name="cmp", minResponseBodyBytes=1024))
        assert d["http"]["middlewares"]["cmp"]["compress"]["minResponseBodyBytes"] == 1024

    def test_content_type(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.contentType(name="ct", autoDetect=True))
        assert "contentType" in d["http"]["middlewares"]["ct"]

    def test_buffering(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.buffering(name="buf", maxRequestBodyBytes=1048576))
        assert "buffering" in d["http"]["middlewares"]["buf"]

    def test_strip_prefix(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.stripPrefix(name="sp", prefixes=["/api"]))
        assert d["http"]["middlewares"]["sp"]["stripPrefix"]["prefixes"] == ["/api"]

    def test_strip_prefix_regex(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.stripPrefixRegex(name="spr", regex=["/api/v[0-9]+"]))
        assert "stripPrefixRegex" in d["http"]["middlewares"]["spr"]

    def test_add_prefix(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.addPrefix(name="ap", prefix="/api"))
        assert d["http"]["middlewares"]["ap"]["addPrefix"]["prefix"] == "/api"

    def test_replace_path(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.replacePath(name="rp", path="/new"))
        assert d["http"]["middlewares"]["rp"]["replacePath"]["path"] == "/new"

    def test_replace_path_regex(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.replacePathRegex(name="rpr", regex="^/old/(.*)",
                                           replacement="/new/$1"))
        rpr = d["http"]["middlewares"]["rpr"]["replacePathRegex"]
        assert rpr["regex"] == "^/old/(.*)"

    def test_redirect_scheme(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.redirectScheme(name="rs", scheme="https",
                                         permanent=True))
        assert d["http"]["middlewares"]["rs"]["redirectScheme"]["scheme"] == "https"

    def test_redirect_regex(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.redirectRegex(name="rr", regex="^http://(.*)",
                                        replacement="https://$1"))
        assert "redirectRegex" in d["http"]["middlewares"]["rr"]

    def test_errors_page(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.errorsPage(name="err", status="500-599",
                                     service="error-svc", query="/{status}.html"))
        # errorsPage compiles as "errors" YAML key
        assert "errors" in d["http"]["middlewares"]["err"]

    def test_grpc_web(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.grpcWeb(name="gw", allowOrigins=["*"]))
        assert "grpcWeb" in d["http"]["middlewares"]["gw"]

    def test_pass_tls_client_cert(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.passTLSClientCert(name="tcc", pem=True))
        assert "passTLSClientCert" in d["http"]["middlewares"]["tcc"]

    def test_mw_plugin(self) -> None:
        d = self._compile_mw(
            lambda mw: mw.mwPlugin(name="plug"))
        # mwPlugin compiles as "plugin" YAML key
        assert "plugin" in d["http"]["middlewares"]["plug"]


# =========================================================================
# DYNAMIC: HTTP SERVERS TRANSPORTS
# =========================================================================


class TestServersTransports:

    def test_basic(self) -> None:
        def recipe(root):
            http = root.http()
            st = http.serversTransports()
            st.serversTransport(name="mytls", insecureSkipVerify=True,
                                maxIdleConnsPerHost=100)

        d = _build_and_compile(recipe)
        t = d["http"]["serversTransports"]["mytls"]
        assert t["insecureSkipVerify"] is True
        assert t["maxIdleConnsPerHost"] == 100


# =========================================================================
# DYNAMIC: TCP
# =========================================================================


class TestTcp:

    def test_tcp_router_basic(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            tcp.tcpRouters().tcpRouter(name="tr1", rule="HostSNI(`*`)",
                                       service="tsvc", entryPoints=["web"])

        d = _build_and_compile(recipe)
        r = d["tcp"]["routers"]["tr1"]
        assert r["rule"] == "HostSNI(`*`)"

    def test_tcp_router_with_tls(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            r = tcp.tcpRouters().tcpRouter(name="tr1", rule="HostSNI(`a.com`)",
                                           service="tsvc")
            r.tcpTls(passthrough=True)

        d = _build_and_compile(recipe)
        assert d["tcp"]["routers"]["tr1"]["tls"]["passthrough"] is True

    def test_tcp_service_load_balancer(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            svc = tcp.tcpServices().tcpService(name="tsvc")
            lb = svc.tcpLoadBalancer()
            lb.tcpServer(address="10.0.0.1:3306")
            lb.tcpServer(address="10.0.0.2:3306")

        d = _build_and_compile(recipe)
        lb = d["tcp"]["services"]["tsvc"]["loadBalancer"]
        assert len(lb["servers"]) == 2
        assert lb["servers"][0]["address"] == "10.0.0.1:3306"

    def test_tcp_service_weighted(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            svc = tcp.tcpServices().tcpService(name="tsvc")
            w = svc.tcpWeighted()
            w.tcpWeightedEntry(name="s1", weight=80)
            w.tcpWeightedEntry(name="s2", weight=20)

        d = _build_and_compile(recipe)
        services = d["tcp"]["services"]["tsvc"]["weighted"]["services"]
        assert len(services) == 2

    def test_tcp_middleware_ip_allow_list(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            tcp.tcpMiddlewares().tcpIpAllowList(
                name="tip", sourceRange=["10.0.0.0/8"])

        d = _build_and_compile(recipe)
        assert "ipAllowList" in d["tcp"]["middlewares"]["tip"]

    def test_tcp_middleware_in_flight_conn(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            tcp.tcpMiddlewares().tcpInFlightConn(name="tifc", amount=100)

        d = _build_and_compile(recipe)
        assert d["tcp"]["middlewares"]["tifc"]["inFlightConn"]["amount"] == 100

    def test_tcp_servers_transport(self) -> None:
        def recipe(root):
            tcp = root.tcp()
            tcp.tcpServersTransports().tcpServersTransport(
                name="tst", dialTimeout="10s")

        d = _build_and_compile(recipe)
        assert d["tcp"]["serversTransports"]["tst"]["dialTimeout"] == "10s"


# =========================================================================
# DYNAMIC: UDP
# =========================================================================


class TestUdp:

    def test_udp_router(self) -> None:
        def recipe(root):
            udp = root.udp()
            udp.udpRouters().udpRouter(name="ur1", service="usvc",
                                       entryPoints=["udp-ep"])

        d = _build_and_compile(recipe)
        assert d["udp"]["routers"]["ur1"]["service"] == "usvc"

    def test_udp_service_load_balancer(self) -> None:
        def recipe(root):
            udp = root.udp()
            svc = udp.udpServices().udpService(name="usvc")
            lb = svc.udpLoadBalancer()
            lb.udpServer(address="10.0.0.1:5353")

        d = _build_and_compile(recipe)
        servers = d["udp"]["services"]["usvc"]["loadBalancer"]["servers"]
        assert servers[0]["address"] == "10.0.0.1:5353"

    def test_udp_service_weighted(self) -> None:
        def recipe(root):
            udp = root.udp()
            svc = udp.udpServices().udpService(name="usvc")
            w = svc.udpWeighted()
            w.udpWeightedEntry(name="s1", weight=50)

        d = _build_and_compile(recipe)
        services = d["udp"]["services"]["usvc"]["weighted"]["services"]
        assert len(services) == 1


# =========================================================================
# DYNAMIC: GLOBAL TLS
# =========================================================================


class TestGlobalTls:

    def test_tls_certificate(self) -> None:
        def recipe(root):
            tls = root.globalTls()
            tls.tlsCertificate(certFile="/certs/cert.pem",
                               keyFile="/certs/key.pem")

        d = _build_and_compile(recipe)
        certs = d["tls"]["certificates"]
        assert isinstance(certs, list)
        assert certs[0]["certFile"] == "/certs/cert.pem"

    def test_tls_options(self) -> None:
        def recipe(root):
            tls = root.globalTls()
            tls.tlsOptions(name="strict", minVersion="VersionTLS12",
                           sniStrict=True)

        d = _build_and_compile(recipe)
        opts = d["tls"]["options"]["strict"]
        assert opts["minVersion"] == "VersionTLS12"
        assert opts["sniStrict"] is True

    def test_tls_options_with_client_auth(self) -> None:
        def recipe(root):
            tls = root.globalTls()
            opt = tls.tlsOptions(name="mtls", minVersion="VersionTLS13")
            opt.clientAuth(clientAuthType="RequireAndVerifyClientCert")

        d = _build_and_compile(recipe)
        ca = d["tls"]["options"]["mtls"]["clientAuth"]
        assert ca["clientAuthType"] == "RequireAndVerifyClientCert"

    def test_tls_store(self) -> None:
        def recipe(root):
            tls = root.globalTls()
            tls.tlsStore(name="default",
                         defaultCertificate_certFile="/certs/cert.pem",
                         defaultCertificate_keyFile="/certs/key.pem")

        d = _build_and_compile(recipe)
        store = d["tls"]["stores"]["default"]
        assert store["defaultCertificate"]["certFile"] == "/certs/cert.pem"


# =========================================================================
# VALIDATION (check)
# =========================================================================


class TestCheck:

    def test_valid_config(self) -> None:
        class ValidProxy(TraefikApp):
            def recipe(self, root):
                root.entryPoint(name="web", address=":80")
                http = root.http()
                http.routers().router(name="r", rule="Host(`a.com`)",
                                      service="s")
                svc = http.services().service(name="s")
                svc.loadBalancer().server(url="http://localhost:8080")

        proxy = ValidProxy()
        errors = proxy.check()
        assert errors == []

    def test_yaml_round_trip(self) -> None:
        """Build config, compile to YAML, parse back — structure must match."""
        class FullProxy(TraefikApp):
            def recipe(self, root):
                ep = root.entryPoint(name="web", address=":80")
                ep.redirect(to="websecure", scheme="https", permanent=True)
                root.entryPoint(name="websecure", address=":443")
                root.api(dashboard=True)

                le = root.certificateResolver(name="le")
                acme = le.acme(email="a@b.com", storage="acme.json")
                acme.httpChallenge(entryPoint="web")

                root.log(level="INFO", format="json")

                http = root.http()
                mw = http.middlewares()
                mw.basicAuth(name="auth", users=["admin:hash"])
                mw.rateLimit(name="rl", average=100, burst=50, period="1m")
                mw.chain(name="ch", middlewares=["auth", "rl"])

                r = http.routers().router(name="api", rule="Host(`api.test.com`)",
                                          service="api-svc",
                                          entryPoints=["websecure"],
                                          middlewares=["ch"])
                r.routerTls(certResolver="le")

                svc = http.services().service(name="api-svc")
                lb = svc.loadBalancer(passHostHeader=True)
                lb.server(url="http://10.0.0.1:8080")
                lb.server(url="http://10.0.0.2:8080")
                lb.healthCheck(path="/health", interval="10s")

        proxy = FullProxy()
        yaml_str = proxy.to_yaml()
        parsed = yaml.safe_load(yaml_str)

        assert "entryPoints" in parsed
        assert "http" in parsed
        assert "certificatesResolvers" in parsed
        assert parsed["http"]["routers"]["api"]["tls"]["certResolver"] == "le"
        assert len(parsed["http"]["services"]["api-svc"]["loadBalancer"]["servers"]) == 2
