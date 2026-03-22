# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Generate a KubernetesApp recipe from existing Kubernetes YAML manifests.

Reads one or more Kubernetes YAML documents and produces Python code
using KubernetesBuilder. Supports:
- Single-document YAML files
- Multi-document YAML files (--- separator)
- Helm chart directories (via `helm template`)
- Direct dict/list input

Usage:
    from genro_kubernetes.recipe_from_manifest import recipe_from_manifest

    code = recipe_from_manifest("deployment.yaml")
    print(code)

    # From Helm chart:
    code = recipe_from_helm("./my-chart/")
    print(code)

    # From command line:
    python -m genro_kubernetes.recipe_from_manifest deployment.yaml
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _load_documents(source: str | Path | dict | list) -> list[dict[str, Any]]:
    """Load YAML documents from various sources."""
    if isinstance(source, list):
        return source
    if isinstance(source, dict):
        return [source]

    import yaml
    text = Path(source).read_text(encoding="utf-8")
    docs = list(yaml.safe_load_all(text))
    return [d for d in docs if d is not None]


def _kw(**kwargs: Any) -> str:
    """Format keyword arguments as Python code string."""
    parts = []
    for key, value in kwargs.items():
        if value is None or value in ("", 0) or value is False:
            continue
        if value is True:
            parts.append(f"{key}=True")
        elif isinstance(value, int):
            parts.append(f"{key}={value}")
        elif isinstance(value, str):
            parts.append(f'{key}="{value}"')
        elif isinstance(value, (list, dict)):
            parts.append(f"{key}={value!r}")
    return ", ".join(parts)


class _Writer:
    """Builds Python source code with indentation."""

    def __init__(self) -> None:
        self._lines: list[str] = []
        self._indent = 0

    def line(self, text: str = "") -> None:
        if text:
            self._lines.append("    " * self._indent + text)
        else:
            self._lines.append("")

    def indent(self) -> None:
        self._indent += 1

    def dedent(self) -> None:
        self._indent = max(0, self._indent - 1)

    def text(self) -> str:
        return "\n".join(self._lines) + "\n"


def _generate_deployment(w: _Writer, resource: dict, var: str = "dep") -> None:
    """Generate deployment code."""
    meta = resource.get("metadata", {})
    spec = resource.get("spec", {})
    name = meta.get("name", "")
    replicas = spec.get("replicas", 1)
    strategy = spec.get("strategy", {})
    strategy_type = strategy.get("type", "RollingUpdate")

    kw_parts = _kw(name=name, replicas=replicas)
    if strategy_type != "RollingUpdate":
        kw_parts += f', strategy="{strategy_type}"'
    elif strategy.get("rollingUpdate"):
        ru = strategy["rollingUpdate"]
        ms = ru.get("maxSurge", "25%")
        mu = ru.get("maxUnavailable", "25%")
        if ms != "25%" or mu != "25%":
            kw_parts += f', max_surge="{ms}", max_unavailable="{mu}"'

    w.line(f"{var} = root.deployment({kw_parts})")

    template = spec.get("template", {})
    pod_spec = template.get("spec", {})
    _generate_containers(w, pod_spec, var)
    _generate_volumes(w, pod_spec, var)


def _generate_statefulset(w: _Writer, resource: dict, var: str = "ss") -> None:
    """Generate statefulset code."""
    meta = resource.get("metadata", {})
    spec = resource.get("spec", {})
    name = meta.get("name", "")
    replicas = spec.get("replicas", 1)
    service_name = spec.get("serviceName", "")

    kw = _kw(name=name, replicas=replicas, service_name=service_name)
    w.line(f"{var} = root.statefulset({kw})")

    template = spec.get("template", {})
    pod_spec = template.get("spec", {})
    _generate_containers(w, pod_spec, var)
    _generate_volumes(w, pod_spec, var)

    for vct in spec.get("volumeClaimTemplates", []):
        vct_spec = vct.get("spec", {})
        storage = vct_spec.get("resources", {}).get("requests", {}).get("storage", "1Gi")
        access = vct_spec.get("accessModes", ["ReadWriteOnce"])
        sc = vct_spec.get("storageClassName", "")
        kw = _kw(storage=storage)
        if access != ["ReadWriteOnce"]:
            kw += f", access_modes={access!r}"
        if sc:
            kw += f', storage_class="{sc}"'
        w.line(f"{var}.volume_claim({kw})")


def _generate_job(w: _Writer, resource: dict, var: str = "job") -> None:
    """Generate job code."""
    meta = resource.get("metadata", {})
    spec = resource.get("spec", {})
    name = meta.get("name", "")
    backoff = spec.get("backoffLimit", 6)

    template = spec.get("template", {})
    pod_spec = template.get("spec", {})
    restart = pod_spec.get("restartPolicy", "Never")

    kw = _kw(name=name, backoff_limit=backoff)
    if restart != "Never":
        kw += f', restart_policy="{restart}"'

    w.line(f"{var} = root.job({kw})")
    _generate_containers(w, pod_spec, var)
    _generate_volumes(w, pod_spec, var)


def _generate_containers(w: _Writer, pod_spec: dict, parent_var: str) -> None:
    """Generate container and init_container code."""
    for ic in pod_spec.get("initContainers", []):
        name = ic.get("name", "")
        image = ic.get("image", "")
        cmd = ic.get("command")
        args = ic.get("args")
        kw = _kw(name=name, image=image, command=cmd, args=args)
        w.line(f"{parent_var}.init_container({kw})")

    for i, c in enumerate(pod_spec.get("containers", [])):
        name = c.get("name", "")
        image = c.get("image", "")
        cvar = f"c{i}" if i > 0 else "c"

        res = c.get("resources", {})
        limits = res.get("limits", {})
        requests = res.get("requests", {})
        kw = _kw(
            name=name, image=image,
            command=c.get("command"),
            args=c.get("args"),
            resources_limits_cpu=limits.get("cpu", ""),
            resources_limits_memory=limits.get("memory", ""),
            resources_requests_cpu=requests.get("cpu", ""),
            resources_requests_memory=requests.get("memory", ""),
            image_pull_policy=c.get("imagePullPolicy", ""),
        )
        w.line(f"{cvar} = {parent_var}.container({kw})")

        for port in c.get("ports", []):
            pkw = _kw(
                container_port=port.get("containerPort", 0),
                name=port.get("name", ""),
            )
            protocol = port.get("protocol", "TCP")
            if protocol != "TCP":
                pkw += f', protocol="{protocol}"'
            w.line(f"{cvar}.port({pkw})")

        for env in c.get("env", []):
            env_name = env.get("name", "")
            value = env.get("value", "")
            vf = env.get("valueFrom", {})
            secret_ref = vf.get("secretKeyRef", {})
            cm_ref = vf.get("configMapKeyRef", {})

            if secret_ref:
                ekw = _kw(
                    name=env_name,
                    value_from_secret=secret_ref.get("name", ""),
                    secret_key=secret_ref.get("key", ""),
                )
            elif cm_ref:
                ekw = _kw(
                    name=env_name,
                    value_from_configmap=cm_ref.get("name", ""),
                    configmap_key=cm_ref.get("key", ""),
                )
            else:
                ekw = _kw(name=env_name, value=value)
            w.line(f"{cvar}.env_var({ekw})")

        for vm in c.get("volumeMounts", []):
            mkw = _kw(
                name=vm.get("name", ""),
                mount_path=vm.get("mountPath", ""),
                read_only=vm.get("readOnly", False),
                sub_path=vm.get("subPath", ""),
            )
            w.line(f"{cvar}.volume_mount({mkw})")

        for probe_type in ("liveness", "readiness", "startup"):
            probe = c.get(f"{probe_type}Probe")
            if probe:
                _generate_probe(w, cvar, probe_type, probe)


def _generate_probe(w: _Writer, cvar: str, probe_type: str, probe: dict) -> None:
    """Generate probe code."""
    http = probe.get("httpGet", {})
    tcp = probe.get("tcpSocket", {})
    exec_cmd = probe.get("exec", {}).get("command")

    kw = f'type="{probe_type}"'
    if http:
        kw += f', http_get_path="{http.get("path", "")}"'
        kw += f", http_get_port={http.get('port', 80)}"
    elif tcp:
        kw += f", tcp_port={tcp.get('port', 0)}"
    elif exec_cmd:
        kw += f", exec_command={exec_cmd!r}"

    for field, yaml_key in [
        ("initial_delay", "initialDelaySeconds"),
        ("period", "periodSeconds"),
        ("timeout", "timeoutSeconds"),
        ("failure_threshold", "failureThreshold"),
        ("success_threshold", "successThreshold"),
    ]:
        val = probe.get(yaml_key)
        if val is not None:
            kw += f", {field}={val}"

    w.line(f"{cvar}.probe({kw})")


def _generate_volumes(w: _Writer, pod_spec: dict, parent_var: str) -> None:
    """Generate volume code."""
    for vol in pod_spec.get("volumes", []):
        name = vol.get("name", "")
        if "emptyDir" in vol:
            w.line(f'{parent_var}.volume(name="{name}", type="emptyDir")')
        elif "configMap" in vol:
            source = vol["configMap"].get("name", "")
            w.line(f'{parent_var}.volume(name="{name}", type="configMap", source="{source}")')
        elif "secret" in vol:
            source = vol["secret"].get("secretName", "")
            w.line(f'{parent_var}.volume(name="{name}", type="secret", source="{source}")')
        elif "persistentVolumeClaim" in vol:
            source = vol["persistentVolumeClaim"].get("claimName", "")
            w.line(f'{parent_var}.volume(name="{name}", type="persistentVolumeClaim",'
                   f' source="{source}")')


def _generate_service(w: _Writer, resource: dict) -> None:
    """Generate service code."""
    meta = resource.get("metadata", {})
    spec = resource.get("spec", {})
    name = meta.get("name", "")
    svc_type = spec.get("type", "ClusterIP")

    kw = _kw(name=name)
    if svc_type != "ClusterIP":
        kw += f', type="{svc_type}"'
    selector = spec.get("selector")
    if selector and selector != {"app": name}:
        kw += f", selector={selector!r}"

    w.line(f"svc = root.service({kw})")
    for port in spec.get("ports", []):
        pkw = _kw(
            port=port.get("port", 0),
            target_port=port.get("targetPort", 0),
            node_port=port.get("nodePort", 0),
            name=port.get("name", ""),
        )
        protocol = port.get("protocol", "TCP")
        if protocol != "TCP":
            pkw += f', protocol="{protocol}"'
        w.line(f"svc.service_port({pkw})")


def _generate_ingress(w: _Writer, resource: dict) -> None:
    """Generate ingress code."""
    meta = resource.get("metadata", {})
    spec = resource.get("spec", {})
    name = meta.get("name", "")
    ingress_class = spec.get("ingressClassName", "traefik")
    annotations = meta.get("annotations", {})

    kw = _kw(name=name)
    if ingress_class != "traefik":
        kw += f', ingress_class="{ingress_class}"'
    if annotations:
        kw += f", annotations={annotations!r}"

    w.line(f"ing = root.ingress({kw})")

    for rule in spec.get("rules", []):
        host = rule.get("host", "")
        for path_entry in rule.get("http", {}).get("paths", []):
            path = path_entry.get("path", "/")
            path_type = path_entry.get("pathType", "Prefix")
            backend = path_entry.get("backend", {}).get("service", {})
            svc_name = backend.get("name", "")
            svc_port = backend.get("port", {}).get("number", 0)

            rkw = _kw(host=host, service_name=svc_name, service_port=svc_port)
            if path != "/":
                rkw += f', path="{path}"'
            if path_type != "Prefix":
                rkw += f', path_type="{path_type}"'
            w.line(f"ing.ingress_rule({rkw})")

    for tls in spec.get("tls", []):
        tkw = ""
        hosts = tls.get("hosts")
        if hosts:
            tkw = f"hosts={hosts!r}"
        secret = tls.get("secretName", "")
        if secret:
            if tkw:
                tkw += ", "
            tkw += f'secret_name="{secret}"'
        w.line(f"ing.ingress_tls({tkw})")


def _generate_configmap(w: _Writer, resource: dict) -> None:
    """Generate configmap code."""
    meta = resource.get("metadata", {})
    name = meta.get("name", "")
    data = resource.get("data", {})
    w.line(f"root.configmap(name=\"{name}\", data={data!r})")


def _generate_secret(w: _Writer, resource: dict) -> None:
    """Generate secret code."""
    meta = resource.get("metadata", {})
    name = meta.get("name", "")
    secret_type = resource.get("type", "Opaque")
    data = resource.get("data")
    string_data = resource.get("stringData")

    kw = _kw(name=name)
    if secret_type != "Opaque":
        kw += f', type="{secret_type}"'
    if data:
        kw += f", data={data!r}"
    if string_data:
        kw += f", string_data={string_data!r}"
    w.line(f"root.secret({kw})")


def _generate_pvc(w: _Writer, resource: dict) -> None:
    """Generate PVC code."""
    meta = resource.get("metadata", {})
    spec = resource.get("spec", {})
    name = meta.get("name", "")
    storage = spec.get("resources", {}).get("requests", {}).get("storage", "1Gi")
    access_modes = spec.get("accessModes", ["ReadWriteOnce"])
    storage_class = spec.get("storageClassName", "")

    kw = _kw(name=name, storage=storage)
    if access_modes != ["ReadWriteOnce"]:
        kw += f", access_modes={access_modes!r}"
    if storage_class:
        kw += f', storage_class="{storage_class}"'
    w.line(f"root.pvc({kw})")


# Resource kind → generator function
_GENERATORS: dict[str, Any] = {
    "Deployment": _generate_deployment,
    "StatefulSet": _generate_statefulset,
    "Job": _generate_job,
    "Service": _generate_service,
    "Ingress": _generate_ingress,
    "ConfigMap": _generate_configmap,
    "Secret": _generate_secret,
    "PersistentVolumeClaim": _generate_pvc,
}


def recipe_from_manifest(
    source: str | Path | dict | list,
    class_name: str = "MyManifest",
) -> str:
    """Generate KubernetesApp recipe from Kubernetes YAML manifest(s).

    Args:
        source: Path to YAML file, dict, or list of resource dicts.
        class_name: Name for the generated class.

    Returns:
        Python source code string.
    """
    documents = _load_documents(source)

    w = _Writer()
    w.line("from genro_kubernetes import KubernetesApp")
    w.line()
    w.line()
    w.line(f"class {class_name}(KubernetesApp):")
    w.indent()
    w.line("def recipe(self, root):")
    w.indent()

    for i, doc in enumerate(documents):
        kind = doc.get("kind", "")
        generator = _GENERATORS.get(kind)
        if generator:
            if i > 0:
                w.line()
            generator(w, doc)
        else:
            w.line(f"# Unsupported resource kind: {kind}")

    if not documents:
        w.line("pass")

    w.dedent()
    w.dedent()

    return w.text()


def recipe_from_helm(
    chart_path: str | Path,
    class_name: str = "MyManifest",
    release_name: str = "release",
    values_file: str | Path | None = None,
    extra_args: list[str] | None = None,
) -> str:
    """Generate KubernetesApp recipe from a Helm chart.

    Requires `helm` CLI to be installed and available in PATH.

    Args:
        chart_path: Path to the Helm chart directory.
        class_name: Name for the generated class.
        release_name: Release name for helm template.
        values_file: Optional values.yaml override file.
        extra_args: Additional helm template arguments.

    Returns:
        Python source code string.
    """
    cmd = ["helm", "template", release_name, str(chart_path)]
    if values_file:
        cmd.extend(["-f", str(values_file)])
    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)

    import yaml
    documents = list(yaml.safe_load_all(result.stdout))
    documents = [d for d in documents if d is not None]

    return recipe_from_manifest(documents, class_name=class_name)


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m genro_kubernetes.recipe_from_manifest <file.yaml>")
        sys.exit(1)
    print(recipe_from_manifest(sys.argv[1]))
