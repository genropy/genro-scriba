# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""KubernetesBuilder - Kubernetes manifest as a semantic Bag builder.

Each @element defines a Kubernetes resource or sub-resource. Parameters use
Kubernetes' snake_case conventions. compile_* methods tell the compiler how
to render resources that need special handling (e.g. multi-document output,
nested spec structures).

The builder IS the documentation — every @element docstring is an encyclopedic
reference for the corresponding Kubernetes concept. Reading the builder teaches
Kubernetes.

Docs: https://kubernetes.io/docs/reference/
"""

from __future__ import annotations

from genro_builders import BagBuilderBase
from genro_builders.builder import element

from ..kubernetes_compiler import render_attrs


def _resource(node, result, builder, api_version, kind):
    """Render a Kubernetes resource with standard metadata + spec wrapper."""
    name = node.attr.get("name", node.label)
    namespace = node.attr.get("namespace", "default")
    labels = node.attr.get("labels") or {"app": name}
    attrs = render_attrs(node, builder)

    resource = {
        "apiVersion": api_version,
        "kind": kind,
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
    }

    # Everything except metadata fields goes into spec
    spec = {}
    for key, value in attrs.items():
        if key not in ("namespace", "labels", "selector"):
            spec[key] = value

    if spec:
        resource["spec"] = spec

    result.setdefault("_resources", []).append(resource)


def _workload_resource(node, result, builder, api_version, kind):
    """Render a workload resource (Deployment, StatefulSet, Job) with pod template."""
    name = node.attr.get("name", node.label)
    namespace = node.attr.get("namespace", "default")
    replicas = node.attr.get("replicas", 1)
    labels = node.attr.get("labels") or {"app": name}
    selector = node.attr.get("selector") or {"matchLabels": {"app": name}}
    image = node.attr.get("image", "")

    resource = {
        "apiVersion": api_version,
        "kind": kind,
        "metadata": {
            "name": name,
            "namespace": namespace,
            "labels": labels,
        },
        "spec": {},
    }

    spec = resource["spec"]

    if kind != "Job":
        spec["replicas"] = replicas
        spec["selector"] = selector

    # Build pod template from children
    children = render_attrs(node, builder)
    containers = children.get("_containers", [])
    init_containers = children.get("_init_containers", [])
    volumes = children.get("_volumes", [])
    volume_claims = children.get("_volume_claims", [])

    # If no explicit container but image is set, create default container
    if not containers and image:
        containers = [{"name": name, "image": image}]

    template = {
        "metadata": {"labels": labels},
        "spec": {},
    }

    if containers:
        template["spec"]["containers"] = containers
    if init_containers:
        template["spec"]["initContainers"] = init_containers
    if volumes:
        template["spec"]["volumes"] = volumes

    if kind == "Job":
        restart_policy = node.attr.get("restart_policy", "Never")
        template["spec"]["restartPolicy"] = restart_policy
        spec["backoffLimit"] = node.attr.get("backoff_limit", 6)
        completions = node.attr.get("completions", 1)
        if completions != 1:
            spec["completions"] = completions
        spec["template"] = template
    elif kind == "StatefulSet":
        service_name = node.attr.get("service_name", "")
        if service_name:
            spec["serviceName"] = service_name
        spec["template"] = template
        if volume_claims:
            spec["volumeClaimTemplates"] = volume_claims
    else:
        # Deployment
        strategy = node.attr.get("strategy", "RollingUpdate")
        if strategy != "RollingUpdate":
            spec["strategy"] = {"type": strategy}
        else:
            max_surge = node.attr.get("max_surge", "25%")
            max_unavailable = node.attr.get("max_unavailable", "25%")
            spec["strategy"] = {
                "type": "RollingUpdate",
                "rollingUpdate": {
                    "maxSurge": max_surge,
                    "maxUnavailable": max_unavailable,
                },
            }
        spec["template"] = template

    result.setdefault("_resources", []).append(resource)


class KubernetesBuilder(BagBuilderBase):
    """Kubernetes manifest grammar.

    Models core Kubernetes resources: Deployments, StatefulSets, Jobs,
    Services, Ingresses, ConfigMaps, Secrets, PVCs.

    Multi-document YAML output: each resource is a separate YAML document
    separated by ---.

    Docs: https://kubernetes.io/docs/reference/
    """

    # =================================================================
    # ROOT — contains multiple resources
    # =================================================================

    @element(sub_tags=(
        "deployment, statefulset, job, service,"
        " ingress, configmap, secret, pvc"
    ))
    def manifest(self, name: str = ""):
        """Kubernetes manifest — a collection of resources.

        A manifest contains one or more Kubernetes resources. When compiled,
        each resource becomes a separate YAML document separated by ---.

        Docs: https://kubernetes.io/docs/concepts/overview/working-with-objects/
        """
        ...

    # =================================================================
    # WORKLOADS
    # =================================================================

    @element(sub_tags="container, init_container, volume")
    def deployment(self, name: str = "", namespace: str = "default",
                   replicas: int = 1, image: str = "",
                   labels: dict | None = None, selector: dict | None = None,
                   strategy: str = "RollingUpdate",
                   max_surge: str = "25%", max_unavailable: str = "25%"):
        """Deployment — manages a set of identical pods.

        A Deployment ensures the desired number of pod replicas are running.
        If a pod fails, the Deployment creates a replacement. Supports
        rolling updates for zero-downtime deploys.

        This is the most common way to run stateless applications.

        Args:
            name: Deployment name (also used as pod label).
            namespace: Kubernetes namespace (default: "default").
            replicas: Number of pod replicas to maintain.
            image: Default container image (used if container has no image).
            labels: Pod labels as dict (auto-generated from name if omitted).
            selector: Label selector (auto-generated from name if omitted).
            strategy: Update strategy: "RollingUpdate" or "Recreate".
            max_surge: Max pods above desired during update ("25%" or int).
            max_unavailable: Max pods unavailable during update.

        Docs: https://kubernetes.io/docs/concepts/workloads/controllers/deployment/
        """
        ...

    def compile_deployment(self, node, result):
        _workload_resource(node, result, self, "apps/v1", "Deployment")

    @element(sub_tags="container, init_container, volume, volume_claim")
    def statefulset(self, name: str = "", namespace: str = "default",
                    replicas: int = 1, image: str = "",
                    service_name: str = "", labels: dict | None = None):
        """StatefulSet — for stateful applications with stable identity.

        Unlike Deployments, StatefulSet pods get:
        - Stable hostname (pod-0, pod-1, pod-2)
        - Stable persistent storage (each pod keeps its volume)
        - Ordered startup and shutdown

        Use for databases (PostgreSQL, MySQL), message queues, or anything
        that needs persistent data tied to a specific pod.

        Args:
            name: StatefulSet name.
            namespace: Kubernetes namespace.
            replicas: Number of pod replicas.
            image: Default container image.
            service_name: Headless service name for pod DNS.
            labels: Pod labels as dict.

        Docs: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/
        """
        ...

    def compile_statefulset(self, node, result):
        _workload_resource(node, result, self, "apps/v1", "StatefulSet")

    @element(sub_tags="container, init_container, volume")
    def job(self, name: str = "", namespace: str = "default",
            image: str = "", restart_policy: str = "Never",
            backoff_limit: int = 6, completions: int = 1):
        """Job — runs a task to completion.

        A Job creates pods that run until they succeed. Use for batch
        processing, database migrations, backups, or any one-off task.

        Args:
            name: Job name.
            namespace: Kubernetes namespace.
            image: Default container image.
            restart_policy: "Never" or "OnFailure".
            backoff_limit: Retries before marking failed (default: 6).
            completions: Number of successful completions needed.

        Docs: https://kubernetes.io/docs/concepts/workloads/controllers/job/
        """
        ...

    def compile_job(self, node, result):
        _workload_resource(node, result, self, "batch/v1", "Job")

    # =================================================================
    # POD INTERNALS
    # =================================================================

    @element(sub_tags="port, env_var, volume_mount, probe")
    def container(self, name: str = "", image: str = "",
                  command: list | None = None, args: list | None = None,
                  resources_limits_cpu: str = "",
                  resources_limits_memory: str = "",
                  resources_requests_cpu: str = "",
                  resources_requests_memory: str = "",
                  image_pull_policy: str = ""):
        """Container — a single container within a pod.

        Most pods run a single container. The container specifies the
        image to run, ports to expose, environment variables, resource
        limits, and health probes.

        Args:
            name: Container name (unique within the pod).
            image: Docker image reference (e.g. "nginx:alpine").
            command: Override ENTRYPOINT (list of strings).
            args: Override CMD (list of strings).
            resources_limits_cpu: CPU ceiling (e.g. "500m" = half core).
            resources_limits_memory: Memory ceiling (e.g. "256Mi").
            resources_requests_cpu: Guaranteed CPU (e.g. "100m").
            resources_requests_memory: Guaranteed memory (e.g. "128Mi").
            image_pull_policy: "Always", "IfNotPresent", "Never".

        Docs: https://kubernetes.io/docs/concepts/containers/
        """
        ...

    def compile_container(self, node, result):
        _compile_container_node(node, result, self, "_containers")

    @element(sub_tags="port, env_var, volume_mount, probe")
    def init_container(self, name: str = "", image: str = "",
                       command: list | None = None, args: list | None = None):
        """Init container — runs before the main container starts.

        Init containers run to completion before any app container starts.
        Use for setup: wait for a database, run migrations, download config.

        Args:
            name: Init container name.
            image: Docker image.
            command: Command to run.
            args: Command arguments.

        Docs: https://kubernetes.io/docs/concepts/workloads/pods/init-containers/
        """
        ...

    def compile_init_container(self, node, result):
        _compile_container_node(node, result, self, "_init_containers")

    @element(sub_tags="")
    def port(self, container_port: int = 0, protocol: str = "TCP",
             name: str = ""):
        """Container port — a port the container listens on.

        Declaring a port is informational (the container listens regardless).
        But it enables: service discovery, port naming for probes, and
        documentation of what the container exposes.

        Args:
            container_port: Port number inside the container.
            protocol: "TCP" (default) or "UDP".
            name: Port name (used by services to reference this port).

        Docs: https://kubernetes.io/docs/concepts/services-networking/
        """
        ...

    def compile_port(self, node, result):
        port_dict = {}
        cp = node.attr.get("container_port", 0)
        if cp:
            port_dict["containerPort"] = cp
        protocol = node.attr.get("protocol", "TCP")
        if protocol != "TCP":
            port_dict["protocol"] = protocol
        name = node.attr.get("name", "")
        if name:
            port_dict["name"] = name
        result.setdefault("_ports", []).append(port_dict)

    @element(sub_tags="")
    def env_var(self, name: str = "", value: str = "",
                value_from_secret: str = "", secret_key: str = "",
                value_from_configmap: str = "", configmap_key: str = ""):
        """Environment variable — passed to the container.

        Can be a plain value, or loaded from a Secret or ConfigMap.

        Args:
            name: Variable name (e.g. "DATABASE_URL").
            value: Plain text value.
            value_from_secret: Secret name to load from.
            secret_key: Key within the Secret.
            value_from_configmap: ConfigMap name to load from.
            configmap_key: Key within the ConfigMap.

        Docs: https://kubernetes.io/docs/tasks/inject-data-application/define-environment-variable-container/
        """
        ...

    def compile_env_var(self, node, result):
        env_dict = {"name": node.attr.get("name", "")}
        value = node.attr.get("value", "")
        secret = node.attr.get("value_from_secret", "")
        configmap = node.attr.get("value_from_configmap", "")

        if secret:
            env_dict["valueFrom"] = {
                "secretKeyRef": {
                    "name": secret,
                    "key": node.attr.get("secret_key", ""),
                },
            }
        elif configmap:
            env_dict["valueFrom"] = {
                "configMapKeyRef": {
                    "name": configmap,
                    "key": node.attr.get("configmap_key", ""),
                },
            }
        elif value:
            env_dict["value"] = str(value)

        result.setdefault("_env", []).append(env_dict)

    @element(sub_tags="")
    def volume_mount(self, name: str = "", mount_path: str = "",
                     read_only: bool = False, sub_path: str = ""):
        """Volume mount — attach a volume to a path in the container.

        Args:
            name: Volume name (must match a volume defined in the pod).
            mount_path: Path inside the container (e.g. "/data").
            read_only: Mount as read-only (default: False).
            sub_path: Mount only a subdirectory of the volume.

        Docs: https://kubernetes.io/docs/concepts/storage/volumes/#using-volumes
        """
        ...

    def compile_volume_mount(self, node, result):
        mount = {
            "name": node.attr.get("name", ""),
            "mountPath": node.attr.get("mount_path", ""),
        }
        if node.attr.get("read_only"):
            mount["readOnly"] = True
        sub_path = node.attr.get("sub_path", "")
        if sub_path:
            mount["subPath"] = sub_path
        result.setdefault("_volume_mounts", []).append(mount)

    @element(sub_tags="")
    def probe(self, type: str = "liveness",
              http_get_path: str = "", http_get_port: int = 0,
              tcp_port: int = 0, exec_command: list | None = None,
              initial_delay: int = 0, period: int = 10, timeout: int = 1,
              failure_threshold: int = 3, success_threshold: int = 1):
        """Health probe — how Kubernetes checks if the container is alive.

        Three types:
        - **liveness**: Is the container alive? Failure -> restart.
        - **readiness**: Is the container ready for traffic? Failure -> remove from service.
        - **startup**: Is the container finished starting? Failure -> kill and retry.

        Three check methods:
        - HTTP GET: returns 200-399 = healthy.
        - TCP socket: connection succeeds = healthy.
        - Exec command: exit code 0 = healthy.

        Args:
            type: "liveness", "readiness", or "startup".
            http_get_path: HTTP endpoint path (e.g. "/health").
            http_get_port: HTTP port to check.
            tcp_port: TCP port to check (alternative to HTTP).
            exec_command: Command to execute (alternative to HTTP/TCP).
            initial_delay: Seconds before first probe (default: 0).
            period: Seconds between probes (default: 10).
            timeout: Seconds to wait for response (default: 1).
            failure_threshold: Failures before unhealthy (default: 3).
            success_threshold: Successes before healthy (default: 1).

        Docs: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
        """
        ...

    def compile_probe(self, node, result):
        probe_type = node.attr.get("type", "liveness")
        probe_dict = {}

        http_path = node.attr.get("http_get_path", "")
        tcp_port = node.attr.get("tcp_port", 0)
        exec_cmd = node.attr.get("exec_command")

        if http_path:
            probe_dict["httpGet"] = {
                "path": http_path,
                "port": node.attr.get("http_get_port", 80),
            }
        elif tcp_port:
            probe_dict["tcpSocket"] = {"port": tcp_port}
        elif exec_cmd:
            probe_dict["exec"] = {"command": exec_cmd}

        initial_delay = node.attr.get("initial_delay", 0)
        if initial_delay:
            probe_dict["initialDelaySeconds"] = initial_delay
        period = node.attr.get("period", 10)
        if period != 10:
            probe_dict["periodSeconds"] = period
        timeout_val = node.attr.get("timeout", 1)
        if timeout_val != 1:
            probe_dict["timeoutSeconds"] = timeout_val
        failure = node.attr.get("failure_threshold", 3)
        if failure != 3:
            probe_dict["failureThreshold"] = failure
        success = node.attr.get("success_threshold", 1)
        if success != 1:
            probe_dict["successThreshold"] = success

        key = f"_{probe_type}Probe"
        result[key] = probe_dict

    @element(sub_tags="")
    def volume(self, name: str = "", type: str = "emptyDir",
               source: str = "", default_mode: int = 0):
        """Pod volume — storage available to containers.

        Types:
        - emptyDir: Ephemeral, deleted with the pod. Good for temp data.
        - configMap: Mount a ConfigMap as files.
        - secret: Mount a Secret as files.
        - persistentVolumeClaim: Persistent storage from a PVC.

        Args:
            name: Volume name (referenced by volume_mount).
            type: "emptyDir", "configMap", "secret", "persistentVolumeClaim".
            source: Source name (ConfigMap name, Secret name, PVC name).
            default_mode: File permission mode (e.g. 0o644).

        Docs: https://kubernetes.io/docs/concepts/storage/volumes/
        """
        ...

    def compile_volume(self, node, result):
        vol_name = node.attr.get("name", "")
        vol_type = node.attr.get("type", "emptyDir")
        source = node.attr.get("source", "")
        default_mode = node.attr.get("default_mode", 0)

        vol = {"name": vol_name}
        if vol_type == "emptyDir":
            vol["emptyDir"] = {}
        elif vol_type == "configMap":
            cm = {"name": source}
            if default_mode:
                cm["defaultMode"] = default_mode
            vol["configMap"] = cm
        elif vol_type == "secret":
            sec = {"secretName": source}
            if default_mode:
                sec["defaultMode"] = default_mode
            vol["secret"] = sec
        elif vol_type == "persistentVolumeClaim":
            vol["persistentVolumeClaim"] = {"claimName": source}

        result.setdefault("_volumes", []).append(vol)

    # =================================================================
    # NETWORKING
    # =================================================================

    @element(sub_tags="service_port")
    def service(self, name: str = "", namespace: str = "default",
                type: str = "ClusterIP", selector: dict | None = None):
        """Service — stable network endpoint for a set of pods.

        Pods are ephemeral — they get new IPs when they restart. A Service
        provides a stable DNS name and IP that routes to the right pods.

        Types:
        - ClusterIP (default): Internal only. Other pods reach it by name.
        - NodePort: Exposed on every node at a fixed port.
        - LoadBalancer: Exposed via cloud load balancer (not on bare metal).

        Args:
            name: Service name (becomes DNS: name.namespace.svc.cluster.local).
            namespace: Kubernetes namespace.
            type: "ClusterIP", "NodePort", or "LoadBalancer".
            selector: Label selector to match pods (auto-generated from name if omitted).

        Docs: https://kubernetes.io/docs/concepts/services-networking/service/
        """
        ...

    def compile_service(self, node, result):
        name = node.attr.get("name", node.label)
        namespace = node.attr.get("namespace", "default")
        svc_type = node.attr.get("type", "ClusterIP")
        selector = node.attr.get("selector") or {"app": name}

        children = render_attrs(node, self)
        ports = children.get("_service_ports", [])

        resource = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "type": svc_type,
                "selector": selector,
            },
        }
        if ports:
            resource["spec"]["ports"] = ports

        result.setdefault("_resources", []).append(resource)

    @element(sub_tags="")
    def service_port(self, port: int = 0, target_port: int = 0,
                     protocol: str = "TCP", node_port: int = 0,
                     name: str = ""):
        """Service port — maps a service port to a container port.

        Args:
            port: Port the service listens on.
            target_port: Port on the container (defaults to port).
            protocol: "TCP" (default) or "UDP".
            node_port: Fixed port on nodes (NodePort type only, 30000-32767).
            name: Port name (required if service has multiple ports).

        Docs: https://kubernetes.io/docs/concepts/services-networking/service/#defining-a-service
        """
        ...

    def compile_service_port(self, node, result):
        port_val = node.attr.get("port", 0)
        target = node.attr.get("target_port", 0) or port_val
        sp = {"port": port_val, "targetPort": target}
        protocol = node.attr.get("protocol", "TCP")
        if protocol != "TCP":
            sp["protocol"] = protocol
        node_port = node.attr.get("node_port", 0)
        if node_port:
            sp["nodePort"] = node_port
        name = node.attr.get("name", "")
        if name:
            sp["name"] = name
        result.setdefault("_service_ports", []).append(sp)

    @element(sub_tags="ingress_rule, ingress_tls")
    def ingress(self, name: str = "", namespace: str = "default",
                ingress_class: str = "traefik", annotations: dict | None = None):
        """Ingress — HTTP routing from outside the cluster.

        An Ingress defines rules that map external HTTP(S) requests to
        internal Services based on hostname and path. Requires an Ingress
        Controller (Traefik, Nginx, etc.) running in the cluster.

        K3s includes Traefik as the default Ingress Controller.

        Args:
            name: Ingress name.
            namespace: Kubernetes namespace.
            ingress_class: Ingress controller class ("traefik" for K3s).
            annotations: Annotations as dict (controller-specific config).

        Docs: https://kubernetes.io/docs/concepts/services-networking/ingress/
        """
        ...

    def compile_ingress(self, node, result):
        name = node.attr.get("name", node.label)
        namespace = node.attr.get("namespace", "default")
        ingress_class = node.attr.get("ingress_class", "traefik")
        annotations = node.attr.get("annotations") or {}

        children = render_attrs(node, self)
        rules = children.get("_ingress_rules", [])
        tls_entries = children.get("_ingress_tls", [])

        resource = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": name,
                "namespace": namespace,
                "annotations": annotations,
            },
            "spec": {
                "ingressClassName": ingress_class,
            },
        }
        if rules:
            resource["spec"]["rules"] = rules
        if tls_entries:
            resource["spec"]["tls"] = tls_entries

        result.setdefault("_resources", []).append(resource)

    @element(sub_tags="")
    def ingress_rule(self, host: str = "", path: str = "/",
                     path_type: str = "Prefix",
                     service_name: str = "", service_port: int = 0):
        """Ingress rule — one routing rule within an Ingress.

        Maps a host + path to a backend Service.

        Args:
            host: Hostname to match (e.g. "api.example.com").
            path: URL path to match (default: "/").
            path_type: "Prefix" (default), "Exact", or "ImplementationSpecific".
            service_name: Backend service name.
            service_port: Backend service port number.

        Docs: https://kubernetes.io/docs/concepts/services-networking/ingress/#ingress-rules
        """
        ...

    def compile_ingress_rule(self, node, result):
        host = node.attr.get("host", "")
        path = node.attr.get("path", "/")
        path_type = node.attr.get("path_type", "Prefix")
        svc_name = node.attr.get("service_name", "")
        svc_port = node.attr.get("service_port", 0)

        rule = {
            "host": host,
            "http": {
                "paths": [{
                    "path": path,
                    "pathType": path_type,
                    "backend": {
                        "service": {
                            "name": svc_name,
                            "port": {"number": svc_port},
                        },
                    },
                }],
            },
        }
        result.setdefault("_ingress_rules", []).append(rule)

    @element(sub_tags="")
    def ingress_tls(self, hosts: list | None = None, secret_name: str = ""):
        """Ingress TLS — HTTPS termination.

        Args:
            hosts: List of hostnames for this TLS certificate.
            secret_name: Secret containing TLS cert and key.

        Docs: https://kubernetes.io/docs/concepts/services-networking/ingress/#tls
        """
        ...

    def compile_ingress_tls(self, node, result):
        tls = {}
        hosts = node.attr.get("hosts")
        if hosts:
            tls["hosts"] = hosts
        secret = node.attr.get("secret_name", "")
        if secret:
            tls["secretName"] = secret
        result.setdefault("_ingress_tls", []).append(tls)

    # =================================================================
    # CONFIG
    # =================================================================

    @element(sub_tags="")
    def configmap(self, name: str = "", namespace: str = "default",
                  data: dict | None = None):
        """ConfigMap — non-sensitive configuration data.

        Stores key-value pairs. Can be mounted as files in a container
        or exposed as environment variables.

        Args:
            name: ConfigMap name.
            namespace: Kubernetes namespace.
            data: Key-value pairs as dict {"key": "value"}.

        Docs: https://kubernetes.io/docs/concepts/configuration/configmap/
        """
        ...

    def compile_configmap(self, node, result):
        name = node.attr.get("name", node.label)
        namespace = node.attr.get("namespace", "default")
        data = node.attr.get("data") or {}

        resource = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "data": data,
        }
        result.setdefault("_resources", []).append(resource)

    @element(sub_tags="")
    def secret(self, name: str = "", namespace: str = "default",
               type: str = "Opaque", data: dict | None = None,
               string_data: dict | None = None):
        """Secret — sensitive data (passwords, tokens, keys).

        Like ConfigMap but base64 encoded and access-controlled.
        Use string_data for plain text (auto-encoded to base64).

        Args:
            name: Secret name.
            namespace: Kubernetes namespace.
            type: "Opaque" (default), "kubernetes.io/tls", etc.
            data: Base64-encoded data as dict.
            string_data: Plain text data as dict (auto-encoded).

        Docs: https://kubernetes.io/docs/concepts/configuration/secret/
        """
        ...

    def compile_secret(self, node, result):
        name = node.attr.get("name", node.label)
        namespace = node.attr.get("namespace", "default")
        secret_type = node.attr.get("type", "Opaque")
        data = node.attr.get("data")
        string_data = node.attr.get("string_data")

        resource = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "type": secret_type,
        }
        if data:
            resource["data"] = data
        if string_data:
            resource["stringData"] = string_data

        result.setdefault("_resources", []).append(resource)

    # =================================================================
    # STORAGE
    # =================================================================

    @element(sub_tags="")
    def pvc(self, name: str = "", namespace: str = "default",
            storage: str = "1Gi", access_modes: list | None = None,
            storage_class: str = ""):
        """PersistentVolumeClaim — request for persistent storage.

        A PVC requests storage from the cluster. The cluster provisions
        a PersistentVolume to satisfy it. The PVC is then mounted into
        pods via volume + volume_mount.

        Args:
            name: PVC name.
            namespace: Kubernetes namespace.
            storage: Requested storage size (e.g. "1Gi", "10Gi").
            access_modes: List of access modes. Default: ["ReadWriteOnce"].
            storage_class: StorageClass name (empty = cluster default).

        Docs: https://kubernetes.io/docs/concepts/storage/persistent-volumes/
        """
        ...

    def compile_pvc(self, node, result):
        name = node.attr.get("name", node.label)
        namespace = node.attr.get("namespace", "default")
        storage = node.attr.get("storage", "1Gi")
        access_modes = node.attr.get("access_modes") or ["ReadWriteOnce"]
        storage_class = node.attr.get("storage_class", "")

        resource = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {
                "name": name,
                "namespace": namespace,
            },
            "spec": {
                "accessModes": access_modes,
                "resources": {"requests": {"storage": storage}},
            },
        }
        if storage_class:
            resource["spec"]["storageClassName"] = storage_class

        result.setdefault("_resources", []).append(resource)

    @element(sub_tags="")
    def volume_claim(self, storage: str = "1Gi",
                     access_modes: list | None = None,
                     storage_class: str = ""):
        """VolumeClaimTemplate — PVC template for StatefulSet.

        Each StatefulSet pod gets its own PVC from this template.
        The PVC persists even if the pod is deleted.

        Args:
            storage: Requested size (e.g. "5Gi").
            access_modes: Default: ["ReadWriteOnce"].
            storage_class: StorageClass name.

        Docs: https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/#stable-storage
        """
        ...

    def compile_volume_claim(self, node, result):
        storage = node.attr.get("storage", "1Gi")
        access_modes = node.attr.get("access_modes") or ["ReadWriteOnce"]
        storage_class = node.attr.get("storage_class", "")

        vct = {
            "metadata": {"name": "data"},
            "spec": {
                "accessModes": access_modes,
                "resources": {"requests": {"storage": storage}},
            },
        }
        if storage_class:
            vct["spec"]["storageClassName"] = storage_class

        result.setdefault("_volume_claims", []).append(vct)


def _compile_container_node(node, result, builder, key):
    """Compile a container or init_container node."""
    name = node.attr.get("name", "")
    image = node.attr.get("image", "")

    container = {"name": name, "image": image}

    command = node.attr.get("command")
    if command:
        container["command"] = command
    args = node.attr.get("args")
    if args:
        container["args"] = args

    # Resources
    resources = {}
    limits = {}
    requests = {}
    for attr_name in ("resources_limits_cpu", "resources_limits_memory"):
        val = node.attr.get(attr_name, "")
        if val:
            field = attr_name.rsplit("_", 1)[1]
            limits[field] = val
    for attr_name in ("resources_requests_cpu", "resources_requests_memory"):
        val = node.attr.get(attr_name, "")
        if val:
            field = attr_name.rsplit("_", 1)[1]
            requests[field] = val
    if limits:
        resources["limits"] = limits
    if requests:
        resources["requests"] = requests
    if resources:
        container["resources"] = resources

    pull_policy = node.attr.get("image_pull_policy", "")
    if pull_policy:
        container["imagePullPolicy"] = pull_policy

    # Collect children (ports, env, volume_mounts, probes)
    children = render_attrs(node, builder)
    ports = children.get("_ports", [])
    env = children.get("_env", [])
    vol_mounts = children.get("_volume_mounts", [])

    if ports:
        container["ports"] = ports
    if env:
        container["env"] = env
    if vol_mounts:
        container["volumeMounts"] = vol_mounts

    for probe_type in ("liveness", "readiness", "startup"):
        probe_key = f"_{probe_type}Probe"
        if probe_key in children:
            container[f"{probe_type}Probe"] = children[probe_key]

    result.setdefault(key, []).append(container)
