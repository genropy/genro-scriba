# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for recipe_from_manifest and recipe_from_helm."""

from __future__ import annotations

from genro_kubernetes.recipe_from_manifest import recipe_from_manifest


class TestDeploymentImport:

    def test_basic_deployment(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api", "namespace": "default"},
            "spec": {
                "replicas": 3,
                "selector": {"matchLabels": {"app": "api"}},
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "api",
                            "image": "myapp:latest",
                            "ports": [{"containerPort": 8080}],
                        }],
                    },
                },
            },
        }
        code = recipe_from_manifest(manifest)
        assert "class MyManifest(KubernetesApp):" in code
        assert "root.deployment(" in code
        assert 'name="api"' in code
        assert "replicas=3" in code
        assert ".container(" in code
        assert 'image="myapp:latest"' in code
        assert ".port(" in code
        assert "container_port=8080" in code

    def test_deployment_with_resources(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "api",
                            "image": "myapp:latest",
                            "resources": {
                                "limits": {"cpu": "500m", "memory": "256Mi"},
                                "requests": {"cpu": "100m", "memory": "128Mi"},
                            },
                        }],
                    },
                },
            },
        }
        code = recipe_from_manifest(manifest)
        assert 'resources_limits_cpu="500m"' in code
        assert 'resources_limits_memory="256Mi"' in code
        assert 'resources_requests_cpu="100m"' in code

    def test_deployment_with_probes(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "api",
                            "image": "myapp:latest",
                            "livenessProbe": {
                                "httpGet": {"path": "/health", "port": 8080},
                                "initialDelaySeconds": 10,
                            },
                            "readinessProbe": {
                                "tcpSocket": {"port": 8080},
                            },
                        }],
                    },
                },
            },
        }
        code = recipe_from_manifest(manifest)
        assert '.probe(type="liveness"' in code
        assert 'http_get_path="/health"' in code
        assert "initial_delay=10" in code
        assert '.probe(type="readiness"' in code
        assert "tcp_port=8080" in code

    def test_deployment_with_env_from_secret(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api"},
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "api",
                            "image": "myapp:latest",
                            "env": [
                                {"name": "DB_HOST", "value": "postgres"},
                                {
                                    "name": "DB_PASSWORD",
                                    "valueFrom": {
                                        "secretKeyRef": {
                                            "name": "db-creds",
                                            "key": "password",
                                        },
                                    },
                                },
                            ],
                        }],
                    },
                },
            },
        }
        code = recipe_from_manifest(manifest)
        assert 'env_var(name="DB_HOST", value="postgres")' in code
        assert 'value_from_secret="db-creds"' in code
        assert 'secret_key="password"' in code

    def test_deployment_with_init_container(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api"},
            "spec": {
                "template": {
                    "spec": {
                        "initContainers": [{
                            "name": "migrate",
                            "image": "myapp:latest",
                            "command": ["python", "manage.py", "migrate"],
                        }],
                        "containers": [{
                            "name": "api",
                            "image": "myapp:latest",
                        }],
                    },
                },
            },
        }
        code = recipe_from_manifest(manifest)
        assert ".init_container(" in code
        assert 'name="migrate"' in code


class TestServiceImport:

    def test_cluster_ip(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "api"},
            "spec": {
                "type": "ClusterIP",
                "selector": {"app": "api"},
                "ports": [{"port": 80, "targetPort": 8080}],
            },
        }
        code = recipe_from_manifest(manifest)
        assert "root.service(" in code
        assert "service_port(" in code
        assert "port=80" in code
        assert "target_port=8080" in code

    def test_node_port(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "api"},
            "spec": {
                "type": "NodePort",
                "ports": [{"port": 80, "targetPort": 8080, "nodePort": 30080}],
            },
        }
        code = recipe_from_manifest(manifest)
        assert 'type="NodePort"' in code
        assert "node_port=30080" in code


class TestIngressImport:

    def test_basic(self) -> None:
        manifest = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {"name": "api"},
            "spec": {
                "ingressClassName": "nginx",
                "rules": [{
                    "host": "api.example.com",
                    "http": {
                        "paths": [{
                            "path": "/",
                            "pathType": "Prefix",
                            "backend": {
                                "service": {
                                    "name": "api",
                                    "port": {"number": 80},
                                },
                            },
                        }],
                    },
                }],
                "tls": [{
                    "hosts": ["api.example.com"],
                    "secretName": "api-tls",
                }],
            },
        }
        code = recipe_from_manifest(manifest)
        assert "root.ingress(" in code
        assert 'ingress_class="nginx"' in code
        assert ".ingress_rule(" in code
        assert 'host="api.example.com"' in code
        assert ".ingress_tls(" in code
        assert 'secret_name="api-tls"' in code


class TestConfigSecretPVC:

    def test_configmap(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "app-config"},
            "data": {"APP_ENV": "production"},
        }
        code = recipe_from_manifest(manifest)
        assert "root.configmap(" in code
        assert "'APP_ENV': 'production'" in code

    def test_secret(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "db-creds"},
            "type": "Opaque",
            "stringData": {"password": "s3cret"},
        }
        code = recipe_from_manifest(manifest)
        assert "root.secret(" in code
        assert "string_data=" in code

    def test_pvc(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "data"},
            "spec": {
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "10Gi"}},
                "storageClassName": "ssd",
            },
        }
        code = recipe_from_manifest(manifest)
        assert "root.pvc(" in code
        assert 'storage="10Gi"' in code
        assert 'storage_class="ssd"' in code


class TestMultiDocument:

    def test_multi_resource(self) -> None:
        resources = [
            {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "api"},
                "spec": {
                    "replicas": 2,
                    "template": {
                        "spec": {"containers": [{"name": "api", "image": "myapp:latest"}]},
                    },
                },
            },
            {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "api"},
                "spec": {
                    "ports": [{"port": 80, "targetPort": 8080}],
                },
            },
        ]
        code = recipe_from_manifest(resources)
        assert "root.deployment(" in code
        assert "root.service(" in code

    def test_custom_class_name(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "web"},
            "spec": {"template": {"spec": {"containers": [{"name": "web", "image": "nginx"}]}}},
        }
        code = recipe_from_manifest(manifest, class_name="WebDeploy")
        assert "class WebDeploy(KubernetesApp):" in code

    def test_unsupported_kind(self) -> None:
        manifest = {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {"name": "myns"},
        }
        code = recipe_from_manifest(manifest)
        assert "# Unsupported resource kind: Namespace" in code


class TestRoundTrip:
    """Verify that imported code produces structurally valid output."""

    def test_generated_code_is_executable(self) -> None:
        manifest = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "api"},
            "spec": {
                "replicas": 2,
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "api",
                            "image": "myapp:latest",
                            "ports": [{"containerPort": 8080}],
                        }],
                    },
                },
            },
        }
        code = recipe_from_manifest(manifest)
        # Execute the generated code to verify it's valid Python
        namespace: dict[str, object] = {}
        exec(code, namespace)
        app_class = namespace["MyManifest"]
        app = app_class()
        yaml_str = app.to_yaml()
        assert "kind: Deployment" in yaml_str
        assert "name: api" in yaml_str
