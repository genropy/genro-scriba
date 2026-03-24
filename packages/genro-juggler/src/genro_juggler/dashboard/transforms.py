# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Transform compiled Juggler resources into display structures.

Pure functions: no UI, no Bag, no side effects.
Input: slot data from JugglerApp (compiled resource dicts).
Output: tree nodes for navigation + Rich markup for detail cards.
"""

from __future__ import annotations

from typing import Any


def resources_to_tree_nodes(
    slots: dict[str, list[dict[str, Any]]],
    statuses: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert compiled resources from all slots into tree nodes.

    Args:
        slots: {slot_name: [resource_dict, ...]} from JugglerApp.
        statuses: {slot_name: {status: ...}} from JugglerApp.status().

    Returns:
        List of slot nodes, each with kind children, each with resource children.
        [
            {
                "label": "kubernetes [connected]",
                "key": "kubernetes",
                "children": [
                    {
                        "label": "Deployment",
                        "key": "kubernetes/Deployment",
                        "children": [
                            {"label": "api", "key": "kubernetes/Deployment/api", "children": []},
                        ],
                    },
                ],
            },
        ]
    """
    result = []
    for slot_name, resources in slots.items():
        slot_status = statuses.get(slot_name, {}).get("status", "unknown")
        slot_node = {
            "label": f"{slot_name} [{slot_status}]",
            "key": slot_name,
            "children": _group_by_kind(slot_name, resources),
        }
        result.append(slot_node)
    return result


def _group_by_kind(
    slot_name: str,
    resources: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group resources by kind into tree nodes."""
    by_kind: dict[str, list[dict[str, Any]]] = {}
    for resource in resources:
        kind = _extract_kind(resource)
        by_kind.setdefault(kind, []).append(resource)

    kind_nodes = []
    for kind, kind_resources in by_kind.items():
        children = []
        for res in kind_resources:
            name = _extract_name(res)
            children.append({
                "label": name,
                "key": f"{slot_name}/{kind}/{name}",
                "children": [],
            })
        kind_nodes.append({
            "label": f"{kind} ({len(kind_resources)})",
            "key": f"{slot_name}/{kind}",
            "children": children,
        })
    return kind_nodes


def _extract_kind(resource: dict[str, Any]) -> str:
    """Extract kind from a compiled resource dict.

    Kubernetes: resource["kind"]
    Ansible: "Play" for top-level, "Task" for tasks
    """
    if "kind" in resource:
        return str(resource["kind"])
    if "hosts" in resource:
        return "Play"
    return "Resource"


def _extract_name(resource: dict[str, Any]) -> str:
    """Extract name from a compiled resource dict.

    Kubernetes: resource["metadata"]["name"]
    Ansible: resource["name"]
    """
    metadata = resource.get("metadata")
    if isinstance(metadata, dict):
        name = metadata.get("name", "")
        if name:
            return str(name)
    name = resource.get("name", "")
    if name:
        return str(name)
    return "(unnamed)"


def resources_to_rich_text(
    slots: dict[str, list[dict[str, Any]]],
    statuses: dict[str, dict[str, Any]],
) -> str:
    """Render all resources as Rich markup text for the detail panel.

    Output uses Rich console markup: [bold], [dim], [green], etc.
    """
    lines: list[str] = []
    for slot_name, resources in slots.items():
        slot_status = statuses.get(slot_name, {}).get("status", "unknown")
        lines.append(f"[bold cyan]{slot_name}[/] [dim]\\[{slot_status}][/]")
        lines.append("")

        by_kind: dict[str, list[dict[str, Any]]] = {}
        for res in resources:
            kind = _extract_kind(res)
            by_kind.setdefault(kind, []).append(res)

        for kind, kind_resources in by_kind.items():
            for res in kind_resources:
                name = _extract_name(res)
                lines.append(f"  [bold yellow]{kind}[/] [bold]{name}[/]")
                for prop_line in _resource_properties(res):
                    lines.append(f"    {prop_line}")
                lines.append("")

    return "\n".join(lines)


def _resource_properties(resource: dict[str, Any]) -> list[str]:
    """Extract key properties from a resource as Rich-formatted lines."""
    props: list[str] = []
    spec = resource.get("spec", {})
    if isinstance(spec, dict):
        _spec_properties(spec, props)
    _secret_properties(resource, props)
    _ansible_properties(resource, props)
    return props


def _spec_properties(spec: dict[str, Any], props: list[str]) -> None:
    """Extract properties from a K8s spec."""
    replicas = spec.get("replicas")
    if replicas is not None:
        props.append(f"replicas: [green]{replicas}[/]")

    template_spec = spec.get("template", {}).get("spec", {})
    containers = template_spec.get("containers", [])
    if isinstance(containers, list):
        for container in containers:
            if isinstance(container, dict):
                _container_properties(container, props)

    for sp in spec.get("ports", []):
        if isinstance(sp, dict) and sp.get("port"):
            props.append(f"port: [green]{sp['port']} → {sp.get('targetPort', '')}[/]")

    for rule in spec.get("rules", []):
        if isinstance(rule, dict) and rule.get("host"):
            props.append(f"host: [green]{rule['host']}[/]")


def _container_properties(container: dict[str, Any], props: list[str]) -> None:
    """Extract properties from a K8s container."""
    image = container.get("image", "")
    if image:
        props.append(f"image: [green]{image}[/]")
    for port in container.get("ports", []):
        if isinstance(port, dict) and port.get("containerPort"):
            props.append(f"port: [green]{port['containerPort']}[/]")
    for env in container.get("env", []):
        if isinstance(env, dict) and env.get("name") and env.get("value"):
            props.append(f"env: [dim]{env['name']}[/]=[green]{env['value']}[/]")


def _secret_properties(resource: dict[str, Any], props: list[str]) -> None:
    """Extract properties from a K8s Secret."""
    data = resource.get("data", {})
    if isinstance(data, dict) and data:
        props.append(f"keys: [dim]{', '.join(data.keys())}[/]")


def _ansible_properties(resource: dict[str, Any], props: list[str]) -> None:
    """Extract properties from an Ansible play."""
    hosts = resource.get("hosts")
    if hosts:
        props.append(f"hosts: [green]{hosts}[/]")
    tasks = resource.get("tasks", [])
    if isinstance(tasks, list) and tasks:
        props.append(f"tasks: [green]{len(tasks)}[/]")
        for task in tasks:
            if isinstance(task, dict) and task.get("name"):
                module = task.get("module", "")
                props.append(f"  [dim]→ {task['name']}[/] [cyan]{module}[/]")


def collect_slot_resources(app: Any) -> dict[str, list[dict[str, Any]]]:
    """Extract compiled resources from all slots of a JugglerApp.

    Compiles each slot without applying to targets.
    """
    result = {}
    for slot_name, slot in app._slots.items():
        resources = slot._compile_to_resources()
        result[slot_name] = resources
    return result
