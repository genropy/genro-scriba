# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for KubernetesBuilder compile_* methods and YAML output structure."""

from __future__ import annotations

import yaml
from genro_bag import Bag
from genro_builders import BuilderBag

from genro_kubernetes import KubernetesApp
from genro_kubernetes.builders.kubernetes_builder import KubernetesBuilder
from genro_kubernetes.kubernetes_compiler import (
    KubernetesCompiler,
    compile_to_dict,
)


def _build(recipe_fn) -> list[dict]:
    """Helper: create store, call recipe, compile, return resource list."""
    store = BuilderBag(builder=KubernetesBuilder)
    store.builder.data = Bag()
    root = store.manifest(name="test")
    recipe_fn(root)
    yaml_dict = compile_to_dict(root, store.builder)
    return KubernetesCompiler().to_multi_document(yaml_dict)


# =========================================================================
# DEPLOYMENT
# =========================================================================


class TestDeployment:

    def test_basic(self) -> None:
        def recipe(root):
            root.deployment(name="api", image="myapp:latest")

        resources = _build(recipe)
        assert len(resources) == 1
        dep = resources[0]
        assert dep["kind"] == "Deployment"
        assert dep["apiVersion"] == "apps/v1"
        assert dep["metadata"]["name"] == "api"
        assert dep["spec"]["replicas"] == 1
        assert dep["spec"]["template"]["spec"]["containers"][0]["image"] == "myapp:latest"

    def test_replicas(self) -> None:
        def recipe(root):
            root.deployment(name="api", image="myapp:latest", replicas=3)

        dep = _build(recipe)[0]
        assert dep["spec"]["replicas"] == 3

    def test_with_container(self) -> None:
        def recipe(root):
            dep = root.deployment(name="api")
            c = dep.container(name="api", image="myapp:v2")
            c.port(container_port=8080)
            c.env_var(name="DB_HOST", value="postgres")

        dep = _build(recipe)[0]
        containers = dep["spec"]["template"]["spec"]["containers"]
        assert len(containers) == 1
        assert containers[0]["name"] == "api"
        assert containers[0]["image"] == "myapp:v2"
        assert containers[0]["ports"][0]["containerPort"] == 8080
        assert containers[0]["env"][0]["name"] == "DB_HOST"
        assert containers[0]["env"][0]["value"] == "postgres"

    def test_resources_limits(self) -> None:
        def recipe(root):
            dep = root.deployment(name="api")
            dep.container(name="api", image="myapp:latest",
                          resources_limits_cpu="500m",
                          resources_limits_memory="256Mi",
                          resources_requests_cpu="100m",
                          resources_requests_memory="128Mi")

        dep = _build(recipe)[0]
        res = dep["spec"]["template"]["spec"]["containers"][0]["resources"]
        assert res["limits"]["cpu"] == "500m"
        assert res["limits"]["memory"] == "256Mi"
        assert res["requests"]["cpu"] == "100m"
        assert res["requests"]["memory"] == "128Mi"

    def test_rolling_update(self) -> None:
        def recipe(root):
            root.deployment(name="api", image="myapp:latest",
                            strategy="RollingUpdate",
                            max_surge="50%", max_unavailable="0")

        dep = _build(recipe)[0]
        strat = dep["spec"]["strategy"]
        assert strat["type"] == "RollingUpdate"
        assert strat["rollingUpdate"]["maxSurge"] == "50%"
        assert strat["rollingUpdate"]["maxUnavailable"] == "0"

    def test_recreate_strategy(self) -> None:
        def recipe(root):
            root.deployment(name="api", image="myapp:latest",
                            strategy="Recreate")

        dep = _build(recipe)[0]
        assert dep["spec"]["strategy"]["type"] == "Recreate"

    def test_probes(self) -> None:
        def recipe(root):
            dep = root.deployment(name="api")
            c = dep.container(name="api", image="myapp:latest")
            c.probe(type="liveness", http_get_path="/health", http_get_port=8080)
            c.probe(type="readiness", tcp_port=8080, initial_delay=5)

        dep = _build(recipe)[0]
        container = dep["spec"]["template"]["spec"]["containers"][0]
        assert container["livenessProbe"]["httpGet"]["path"] == "/health"
        assert container["readinessProbe"]["tcpSocket"]["port"] == 8080
        assert container["readinessProbe"]["initialDelaySeconds"] == 5

    def test_init_container(self) -> None:
        def recipe(root):
            dep = root.deployment(name="api")
            dep.init_container(name="migrate", image="myapp:latest",
                               command=["python", "manage.py", "migrate"])
            dep.container(name="api", image="myapp:latest")

        dep = _build(recipe)[0]
        init = dep["spec"]["template"]["spec"]["initContainers"]
        assert len(init) == 1
        assert init[0]["name"] == "migrate"
        assert init[0]["command"] == ["python", "manage.py", "migrate"]

    def test_volumes(self) -> None:
        def recipe(root):
            dep = root.deployment(name="api")
            c = dep.container(name="api", image="myapp:latest")
            c.volume_mount(name="config", mount_path="/etc/app")
            dep.volume(name="config", type="configMap", source="app-config")

        dep = _build(recipe)[0]
        template = dep["spec"]["template"]
        assert template["spec"]["volumes"][0]["name"] == "config"
        assert template["spec"]["volumes"][0]["configMap"]["name"] == "app-config"
        assert template["spec"]["containers"][0]["volumeMounts"][0]["mountPath"] == "/etc/app"


# =========================================================================
# STATEFULSET
# =========================================================================


class TestStatefulSet:

    def test_basic(self) -> None:
        def recipe(root):
            ss = root.statefulset(name="db", image="postgres:16",
                                  service_name="db-headless", replicas=1)
            c = ss.container(name="postgres", image="postgres:16")
            c.port(container_port=5432)
            ss.volume_claim(storage="10Gi")

        resources = _build(recipe)
        assert len(resources) == 1
        ss = resources[0]
        assert ss["kind"] == "StatefulSet"
        assert ss["spec"]["serviceName"] == "db-headless"
        vct = ss["spec"]["volumeClaimTemplates"][0]
        assert vct["spec"]["resources"]["requests"]["storage"] == "10Gi"


# =========================================================================
# JOB
# =========================================================================


class TestJob:

    def test_basic(self) -> None:
        def recipe(root):
            root.job(name="migrate", image="myapp:latest")

        resources = _build(recipe)
        job = resources[0]
        assert job["kind"] == "Job"
        assert job["apiVersion"] == "batch/v1"
        assert job["spec"]["template"]["spec"]["restartPolicy"] == "Never"

    def test_backoff_limit(self) -> None:
        def recipe(root):
            root.job(name="batch", image="worker:latest", backoff_limit=3)

        job = _build(recipe)[0]
        assert job["spec"]["backoffLimit"] == 3


# =========================================================================
# SERVICE
# =========================================================================


class TestService:

    def test_cluster_ip(self) -> None:
        def recipe(root):
            svc = root.service(name="api")
            svc.service_port(port=80, target_port=8080)

        resources = _build(recipe)
        svc = resources[0]
        assert svc["kind"] == "Service"
        assert svc["spec"]["type"] == "ClusterIP"
        assert svc["spec"]["selector"] == {"app": "api"}
        assert svc["spec"]["ports"][0]["port"] == 80
        assert svc["spec"]["ports"][0]["targetPort"] == 8080

    def test_node_port(self) -> None:
        def recipe(root):
            svc = root.service(name="api", type="NodePort")
            svc.service_port(port=80, target_port=8080, node_port=30080)

        svc = _build(recipe)[0]
        assert svc["spec"]["type"] == "NodePort"
        assert svc["spec"]["ports"][0]["nodePort"] == 30080

    def test_multiple_ports(self) -> None:
        def recipe(root):
            svc = root.service(name="api")
            svc.service_port(port=80, target_port=8080, name="http")
            svc.service_port(port=443, target_port=8443, name="https")

        svc = _build(recipe)[0]
        assert len(svc["spec"]["ports"]) == 2


# =========================================================================
# INGRESS
# =========================================================================


class TestIngress:

    def test_basic(self) -> None:
        def recipe(root):
            ing = root.ingress(name="api-ingress")
            ing.ingress_rule(host="api.example.com",
                             service_name="api", service_port=80)

        resources = _build(recipe)
        ing = resources[0]
        assert ing["kind"] == "Ingress"
        assert ing["spec"]["ingressClassName"] == "traefik"
        rules = ing["spec"]["rules"]
        assert rules[0]["host"] == "api.example.com"
        backend = rules[0]["http"]["paths"][0]["backend"]
        assert backend["service"]["name"] == "api"

    def test_tls(self) -> None:
        def recipe(root):
            ing = root.ingress(name="api-ingress")
            ing.ingress_rule(host="api.example.com",
                             service_name="api", service_port=80)
            ing.ingress_tls(hosts=["api.example.com"],
                            secret_name="api-tls")

        ing = _build(recipe)[0]
        tls = ing["spec"]["tls"]
        assert tls[0]["hosts"] == ["api.example.com"]
        assert tls[0]["secretName"] == "api-tls"


# =========================================================================
# CONFIGMAP & SECRET
# =========================================================================


class TestConfigAndSecret:

    def test_configmap(self) -> None:
        def recipe(root):
            root.configmap(name="app-config",
                           data={"APP_ENV": "production", "LOG_LEVEL": "info"})

        cm = _build(recipe)[0]
        assert cm["kind"] == "ConfigMap"
        assert cm["data"]["APP_ENV"] == "production"

    def test_secret(self) -> None:
        def recipe(root):
            root.secret(name="db-creds",
                        string_data={"password": "s3cret"})

        sec = _build(recipe)[0]
        assert sec["kind"] == "Secret"
        assert sec["type"] == "Opaque"
        assert sec["stringData"]["password"] == "s3cret"


# =========================================================================
# PVC
# =========================================================================


class TestPVC:

    def test_basic(self) -> None:
        def recipe(root):
            root.pvc(name="data", storage="10Gi")

        pvc = _build(recipe)[0]
        assert pvc["kind"] == "PersistentVolumeClaim"
        assert pvc["spec"]["resources"]["requests"]["storage"] == "10Gi"
        assert pvc["spec"]["accessModes"] == ["ReadWriteOnce"]

    def test_storage_class(self) -> None:
        def recipe(root):
            root.pvc(name="fast-data", storage="50Gi",
                     storage_class="ssd")

        pvc = _build(recipe)[0]
        assert pvc["spec"]["storageClassName"] == "ssd"


# =========================================================================
# MULTI-RESOURCE & APP
# =========================================================================


class TestMultiResource:

    def test_deployment_plus_service(self) -> None:
        def recipe(root):
            dep = root.deployment(name="api", image="myapp:latest", replicas=2)
            c = dep.container(name="api", image="myapp:latest")
            c.port(container_port=8080)

            svc = root.service(name="api")
            svc.service_port(port=80, target_port=8080)

        resources = _build(recipe)
        assert len(resources) == 2
        kinds = {r["kind"] for r in resources}
        assert kinds == {"Deployment", "Service"}

    def test_full_stack(self) -> None:
        def recipe(root):
            root.configmap(name="app-config",
                           data={"DB_HOST": "db"})
            root.secret(name="db-creds",
                        string_data={"password": "s3cret"})
            root.pvc(name="db-data", storage="10Gi")

            dep = root.deployment(name="api", image="myapp:latest")
            c = dep.container(name="api", image="myapp:latest")
            c.port(container_port=8080)
            c.env_var(name="DB_PASSWORD", value_from_secret="db-creds",
                      secret_key="password")

            svc = root.service(name="api")
            svc.service_port(port=80, target_port=8080)

            ing = root.ingress(name="api")
            ing.ingress_rule(host="api.example.com",
                             service_name="api", service_port=80)

        resources = _build(recipe)
        assert len(resources) == 6
        kinds = [r["kind"] for r in resources]
        assert "ConfigMap" in kinds
        assert "Secret" in kinds
        assert "PersistentVolumeClaim" in kinds
        assert "Deployment" in kinds
        assert "Service" in kinds
        assert "Ingress" in kinds


class TestKubernetesApp:

    def test_produces_multi_document_yaml(self) -> None:
        class MyManifest(KubernetesApp):
            def recipe(self, root):
                root.deployment(name="api", image="myapp:latest")
                svc = root.service(name="api")
                svc.service_port(port=80, target_port=8080)

        app = MyManifest()
        yaml_str = app.to_yaml()
        assert "---" in yaml_str
        docs = yaml_str.split("---")
        assert len(docs) == 2

    def test_valid_yaml_documents(self) -> None:
        class MyManifest(KubernetesApp):
            def recipe(self, root):
                root.deployment(name="web", image="nginx:alpine")

        app = MyManifest()
        yaml_str = app.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert parsed["kind"] == "Deployment"
        assert parsed["metadata"]["name"] == "web"

    def test_pointer_resolution(self) -> None:
        class MyManifest(KubernetesApp):
            def recipe(self, root):
                root.deployment(name="api", image="^api.image")

        app = MyManifest(data={
            "api.image": "myapp:v3",
        })
        yaml_str = app.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert parsed["spec"]["template"]["spec"]["containers"][0]["image"] == "myapp:v3"

    def test_env_from_secret(self) -> None:
        class MyManifest(KubernetesApp):
            def recipe(self, root):
                dep = root.deployment(name="api")
                c = dep.container(name="api", image="myapp:latest")
                c.env_var(name="DB_PASSWORD",
                          value_from_secret="db-creds",
                          secret_key="password")

        app = MyManifest()
        parsed = yaml.safe_load(app.to_yaml())
        env = parsed["spec"]["template"]["spec"]["containers"][0]["env"][0]
        assert env["valueFrom"]["secretKeyRef"]["name"] == "db-creds"
        assert env["valueFrom"]["secretKeyRef"]["key"] == "password"
