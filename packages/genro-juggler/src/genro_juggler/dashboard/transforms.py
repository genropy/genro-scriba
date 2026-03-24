# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Transform compiled Juggler resources into tree node structures.

Pure functions: no UI, no Bag, no side effects.
Input: slot data from JugglerApp (compiled resource dicts).
Output: list of TreeNode dicts for the dashboard tree widget.

Tree structure:
    slot_name (kubernetes/ansible)
      kind (Deployment/Service/Secret/...)
        resource_name [status]
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


def collect_slot_resources(app: Any) -> dict[str, list[dict[str, Any]]]:
    """Extract compiled resources from all slots of a JugglerApp.

    Compiles each slot without applying to targets.
    """
    result = {}
    for slot_name, slot in app._slots.items():
        resources = slot._compile_to_resources()
        result[slot_name] = resources
    return result
