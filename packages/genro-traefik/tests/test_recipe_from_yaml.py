# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for recipe_from_yaml module."""

from __future__ import annotations

from genro_traefik.recipe_from_yaml import (
    _kw,
    _scalar_kwargs,
    _split_kwargs,
    _Writer,
    recipe_from_yaml,
)


# =========================================================================
# _Writer
# =========================================================================


class TestWriter:

    def test_line_adds_text(self) -> None:
        w = _Writer()
        w.line("hello")
        assert "hello" in w.text()

    def test_line_empty_adds_blank(self) -> None:
        w = _Writer()
        w.line("")
        assert w.text() == "\n"

    def test_method_signature(self) -> None:
        w = _Writer()
        w.method("foo", "self, x")
        text = w.text()
        assert "    def foo(self, x):" in text

    def test_body_short_line(self) -> None:
        w = _Writer()
        w.body("x = 1")
        assert "        x = 1" in w.text()

    def test_body_long_line_wraps(self) -> None:
        w = _Writer()
        long_call = 'root.entryPoint(name="web", address=":80", proxyProtocol_insecure=True, extra_very_long_param="value")'
        w.body(long_call)
        text = w.text()
        # Should be split across multiple lines
        assert "\n" in text.strip()

    def test_text_joins_with_newlines(self) -> None:
        w = _Writer()
        w.line("a")
        w.line("b")
        assert w.text() == "a\nb\n"


# =========================================================================
# _split_kwargs
# =========================================================================


class TestSplitKwargs:

    def test_simple(self) -> None:
        assert _split_kwargs("a=1, b=2") == ["a=1", "b=2"]

    def test_nested_brackets(self) -> None:
        assert _split_kwargs("a=[1,2], b=3") == ["a=[1,2]", "b=3"]

    def test_nested_parens(self) -> None:
        assert _split_kwargs("a=f(1,2), b=3") == ["a=f(1,2)", "b=3"]

    def test_quoted_strings(self) -> None:
        result = _split_kwargs('a="x,y", b=3')
        assert result == ['a="x,y"', "b=3"]

    def test_empty(self) -> None:
        assert _split_kwargs("") == []

    def test_single_arg(self) -> None:
        assert _split_kwargs("a=1") == ["a=1"]

    def test_nested_braces(self) -> None:
        assert _split_kwargs("a={1:2}, b=3") == ["a={1:2}", "b=3"]


# =========================================================================
# _kw
# =========================================================================


class TestKw:

    def test_string_value(self) -> None:
        assert _kw({"key": "val"}) == 'key="val"'

    def test_bool_value(self) -> None:
        assert _kw({"key": True}) == "key=True"

    def test_int_value(self) -> None:
        assert _kw({"key": 42}) == "key=42"

    def test_list_value(self) -> None:
        result = _kw({"key": ["a", "b"]})
        assert "key=" in result
        assert "'a'" in result

    def test_skip_keys(self) -> None:
        result = _kw({"a": 1, "b": 2}, skip={"b"})
        assert "a=1" in result
        assert "b" not in result

    def test_float_value(self) -> None:
        assert _kw({"key": 3.14}) == "key=3.14"


# =========================================================================
# _scalar_kwargs
# =========================================================================


class TestScalarKwargs:

    def test_extracts_scalars(self) -> None:
        result = _scalar_kwargs({"a": 1, "b": "x", "c": {"nested": True}})
        assert result == {"a": 1, "b": "x"}

    def test_keeps_simple_lists(self) -> None:
        result = _scalar_kwargs({"a": ["x", "y"]})
        assert result == {"a": ["x", "y"]}

    def test_skips_list_of_dicts(self) -> None:
        result = _scalar_kwargs({"a": [{"url": "http://x"}]})
        assert result == {}

    def test_skip_param(self) -> None:
        result = _scalar_kwargs({"a": 1, "b": 2}, skip={"a"})
        assert result == {"b": 2}


# =========================================================================
# recipe_from_yaml: entry points
# =========================================================================


class TestRecipeEntryPoints:

    def test_basic(self) -> None:
        data = {"entryPoints": {"web": {"address": ":80"}}}
        code = recipe_from_yaml(data)
        assert 'root.entryPoint(name="web", address=":80")' in code

    def test_with_redirect(self) -> None:
        data = {
            "entryPoints": {
                "web": {
                    "address": ":80",
                    "http": {
                        "redirections": {
                            "entryPoint": {
                                "to": "websecure",
                                "scheme": "https",
                            }
                        }
                    },
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "ep.redirect(" in code
        assert 'to="websecure"' in code


# =========================================================================
# recipe_from_yaml: api
# =========================================================================


class TestRecipeApi:

    def test_api(self) -> None:
        data = {"api": {"dashboard": True, "insecure": True}}
        code = recipe_from_yaml(data)
        assert "root.api(" in code
        assert "dashboard=True" in code


# =========================================================================
# recipe_from_yaml: certificates
# =========================================================================


class TestRecipeCertificates:

    def test_acme_http(self) -> None:
        data = {
            "certificatesResolvers": {
                "le": {
                    "acme": {
                        "email": "a@b.com",
                        "storage": "acme.json",
                        "httpChallenge": {"entryPoint": "web"},
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'certificateResolver(name="le")' in code
        assert "cr.acme(" in code
        assert "acme.httpChallenge(" in code

    def test_acme_tls(self) -> None:
        data = {
            "certificatesResolvers": {
                "le": {"acme": {"email": "a@b.com", "tlsChallenge": {}}}
            }
        }
        code = recipe_from_yaml(data)
        assert "acme.tlsChallenge()" in code

    def test_acme_dns(self) -> None:
        data = {
            "certificatesResolvers": {
                "le": {
                    "acme": {
                        "email": "a@b.com",
                        "dnsChallenge": {"provider": "cloudflare"},
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "acme.dnsChallenge(" in code
        assert 'provider="cloudflare"' in code


# =========================================================================
# recipe_from_yaml: providers
# =========================================================================


class TestRecipeProviders:

    def test_file(self) -> None:
        data = {"providers": {"file": {"directory": "/etc/traefik/conf.d"}}}
        code = recipe_from_yaml(data)
        assert "prov._file(" in code

    def test_docker(self) -> None:
        data = {"providers": {"docker": {"exposedByDefault": False}}}
        code = recipe_from_yaml(data)
        assert "prov.docker(" in code


# =========================================================================
# recipe_from_yaml: logging
# =========================================================================


class TestRecipeLogging:

    def test_log(self) -> None:
        data = {"log": {"level": "INFO", "format": "json"}}
        code = recipe_from_yaml(data)
        assert "root.log(" in code
        assert 'level="INFO"' in code

    def test_access_log(self) -> None:
        data = {"accessLog": {"format": "json"}}
        code = recipe_from_yaml(data)
        assert "root.accessLog(" in code

    def test_multiple(self) -> None:
        data = {
            "log": {"level": "INFO"},
            "metrics": {"addRoutersLabels": True},
        }
        code = recipe_from_yaml(data)
        assert "root.log(" in code
        assert "root.metrics(" in code


# =========================================================================
# recipe_from_yaml: HTTP
# =========================================================================


class TestRecipeHttp:

    def test_routers_basic(self) -> None:
        data = {
            "http": {
                "routers": {
                    "r1": {"rule": "Host(`a.com`)", "service": "svc"},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'routers.router(name="r1"' in code

    def test_routers_with_tls(self) -> None:
        data = {
            "http": {
                "routers": {
                    "r1": {
                        "rule": "Host(`a.com`)",
                        "service": "svc",
                        "tls": {"certResolver": "le"},
                    },
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "r.routerTls(" in code
        assert 'certResolver="le"' in code

    def test_routers_with_observability(self) -> None:
        data = {
            "http": {
                "routers": {
                    "r1": {
                        "rule": "Host(`a.com`)",
                        "service": "svc",
                        "observability": {"accessLogs": True},
                    },
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "r.observability(" in code

    def test_services_load_balancer(self) -> None:
        data = {
            "http": {
                "services": {
                    "svc1": {
                        "loadBalancer": {
                            "passHostHeader": True,
                            "servers": [{"url": "http://localhost:8080"}],
                            "healthCheck": {"path": "/health"},
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.loadBalancer(" in code
        assert "lb.server(" in code
        assert "lb.healthCheck(" in code

    def test_services_weighted(self) -> None:
        data = {
            "http": {
                "services": {
                    "svc1": {
                        "weighted": {
                            "services": [
                                {"name": "canary", "weight": 10},
                                {"name": "stable", "weight": 90},
                            ]
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.weighted()" in code
        assert "w.weightedService(" in code

    def test_services_mirroring(self) -> None:
        data = {
            "http": {
                "services": {
                    "svc1": {
                        "mirroring": {
                            "service": "main",
                            "mirrors": [{"name": "test", "percent": 20}],
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.mirroring(" in code
        assert "m.mirror(" in code

    def test_services_failover(self) -> None:
        data = {
            "http": {
                "services": {
                    "svc1": {
                        "failover": {"service": "primary", "fallback": "backup"}
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.failover(" in code

    def test_middlewares(self) -> None:
        data = {
            "http": {
                "middlewares": {
                    "auth": {"basicAuth": {"users": ["admin:hash"]}},
                    "rl": {"rateLimit": {"average": 100}},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'mw.basicAuth(name="auth"' in code
        assert 'mw.rateLimit(name="rl"' in code

    def test_middleware_errors_mapped(self) -> None:
        data = {
            "http": {
                "middlewares": {
                    "err": {"errors": {"status": "500-599", "service": "error-svc"}},
                }
            }
        }
        code = recipe_from_yaml(data)
        # "errors" YAML key maps to errorsPage builder method
        assert "mw.errorsPage(" in code

    def test_servers_transports(self) -> None:
        data = {
            "http": {
                "serversTransports": {
                    "mytls": {"insecureSkipVerify": True},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'st.serversTransport(name="mytls"' in code

    def test_sticky_load_balancer(self) -> None:
        data = {
            "http": {
                "services": {
                    "svc1": {
                        "loadBalancer": {
                            "servers": [{"url": "http://localhost:8080"}],
                            "sticky": {"cookie": {"name": "srv_id", "secure": True}},
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "lb.sticky(" in code

    def test_passive_health_check(self) -> None:
        data = {
            "http": {
                "services": {
                    "svc1": {
                        "loadBalancer": {
                            "servers": [{"url": "http://localhost:8080"}],
                            "passiveHealthCheck": {"maxFailedAttempts": 5},
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "lb.passiveHealthCheck(" in code


# =========================================================================
# recipe_from_yaml: TCP
# =========================================================================


class TestRecipeTcp:

    def test_routers(self) -> None:
        data = {
            "tcp": {
                "routers": {
                    "tr1": {"rule": "HostSNI(`*`)", "service": "tsvc"},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'routers.tcpRouter(name="tr1"' in code

    def test_routers_with_tls(self) -> None:
        data = {
            "tcp": {
                "routers": {
                    "tr1": {
                        "rule": "HostSNI(`a.com`)",
                        "service": "tsvc",
                        "tls": {"passthrough": True},
                    },
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "r.tcpTls(" in code

    def test_services_load_balancer(self) -> None:
        data = {
            "tcp": {
                "services": {
                    "tsvc": {
                        "loadBalancer": {
                            "servers": [{"address": "10.0.0.1:3306"}],
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.tcpLoadBalancer(" in code
        assert "lb.tcpServer(" in code

    def test_services_weighted(self) -> None:
        data = {
            "tcp": {
                "services": {
                    "tsvc": {
                        "weighted": {
                            "services": [{"name": "s1", "weight": 80}],
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.tcpWeighted()" in code
        assert "w.tcpWeightedEntry(" in code

    def test_middlewares(self) -> None:
        data = {
            "tcp": {
                "middlewares": {
                    "tip": {"ipAllowList": {"sourceRange": ["10.0.0.0/8"]}},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "tcpIpAllowList" in code


# =========================================================================
# recipe_from_yaml: UDP
# =========================================================================


class TestRecipeUdp:

    def test_routers(self) -> None:
        data = {
            "udp": {
                "routers": {
                    "ur1": {"service": "usvc", "entryPoints": ["udp-ep"]},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'routers.udpRouter(name="ur1"' in code

    def test_services(self) -> None:
        data = {
            "udp": {
                "services": {
                    "usvc": {
                        "loadBalancer": {
                            "servers": [{"address": "10.0.0.1:5353"}],
                        }
                    }
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "svc.udpLoadBalancer()" in code
        assert "lb.udpServer(" in code


# =========================================================================
# recipe_from_yaml: Global TLS
# =========================================================================


class TestRecipeGlobalTls:

    def test_certificates(self) -> None:
        data = {
            "tls": {
                "certificates": [
                    {"certFile": "/certs/cert.pem", "keyFile": "/certs/key.pem"},
                ]
            }
        }
        code = recipe_from_yaml(data)
        assert "tls.tlsCertificate(" in code

    def test_options(self) -> None:
        data = {
            "tls": {
                "options": {
                    "strict": {"minVersion": "VersionTLS12", "sniStrict": True},
                }
            }
        }
        code = recipe_from_yaml(data)
        assert 'tls.tlsOptions(name="strict"' in code

    def test_options_with_client_auth(self) -> None:
        data = {
            "tls": {
                "options": {
                    "mtls": {
                        "minVersion": "VersionTLS13",
                        "clientAuth": {"clientAuthType": "RequireAndVerifyClientCert"},
                    },
                }
            }
        }
        code = recipe_from_yaml(data)
        assert "opt.clientAuth(" in code

    def test_stores(self) -> None:
        data = {"tls": {"stores": {"default": {}}}}
        code = recipe_from_yaml(data)
        assert 'tls.tlsStore(name="default"' in code


# =========================================================================
# recipe_from_yaml: class generation
# =========================================================================


class TestRecipeGeneral:

    def test_custom_class_name(self) -> None:
        data = {"entryPoints": {"web": {"address": ":80"}}}
        code = recipe_from_yaml(data, class_name="MyProxy")
        assert "class MyProxy(TraefikApp):" in code

    def test_import_present(self) -> None:
        data = {"entryPoints": {"web": {"address": ":80"}}}
        code = recipe_from_yaml(data)
        assert "from genro_traefik import TraefikApp" in code

    def test_recipe_method(self) -> None:
        data = {"entryPoints": {"web": {"address": ":80"}}}
        code = recipe_from_yaml(data)
        assert "def recipe(self, root):" in code

    def test_from_dict_comprehensive(self) -> None:
        """Test with a comprehensive config covering many sections."""
        data = {
            "entryPoints": {"web": {"address": ":80"}},
            "api": {"dashboard": True},
            "certificatesResolvers": {
                "le": {"acme": {"email": "a@b.com", "httpChallenge": {"entryPoint": "web"}}}
            },
            "log": {"level": "INFO"},
            "providers": {"docker": {"exposedByDefault": False}},
            "http": {
                "routers": {"r1": {"rule": "Host(`a.com`)", "service": "svc"}},
                "services": {
                    "svc": {"loadBalancer": {"servers": [{"url": "http://localhost:8080"}]}}
                },
                "middlewares": {"auth": {"basicAuth": {"users": ["admin:hash"]}}},
            },
        }
        code = recipe_from_yaml(data)
        assert "self.entryPoints(root)" in code
        assert "self.certificates(root)" in code
        assert "self.dynamic(root.http())" in code
        assert "self.logging(root)" in code
        assert "self.providers(root)" in code
        assert "self.api(root)" in code
