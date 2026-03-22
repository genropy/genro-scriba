# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Artifact Hub explorer — search Helm charts and container images.

Queries the Artifact Hub public API to discover infrastructure packages.
No authentication required.

Usage:
    from genro_scriba.artifact_hub import ArtifactHub

    hub = ArtifactHub()

    # Search Helm charts
    charts = hub.search_charts("postgresql")
    for chart in charts:
        print(f"{chart['repo']}/{chart['name']} v{chart['version']}")
        print(f"  {chart['description']}")

    # Search container images
    images = hub.search_images("nginx")

    # Get chart details (values, readme, install command)
    detail = hub.chart_detail("bitnami", "postgresql")
    print(detail['install_command'])

    # Get default values.yaml for a chart
    values = hub.chart_values("bitnami", "postgresql")

API docs: https://artifacthub.io/docs/api/
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

_BASE_URL = "https://artifacthub.io/api/v1"

# Artifact Hub kind codes
KIND_HELM_CHART = 0
KIND_OLM_OPERATOR = 3
KIND_CONTAINER_IMAGE = 12


class ArtifactHub:
    """Client for the Artifact Hub public REST API."""

    def __init__(self, base_url: str = _BASE_URL) -> None:
        self._base_url = base_url.rstrip("/")

    def _get(self, path: str) -> Any:
        """Make a GET request and return parsed JSON."""
        url = f"{self._base_url}{path}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def search(self, query: str, kind: int | None = None,
               limit: int = 10, offset: int = 0,
               verified_publisher: bool = False,
               official: bool = False) -> list[dict[str, Any]]:
        """Search packages on Artifact Hub.

        Args:
            query: Search text.
            kind: Package kind filter (0=Helm, 12=Container, None=all).
            limit: Max results (default 10, max 60).
            offset: Pagination offset.
            verified_publisher: Only verified publishers.
            official: Only official packages.

        Returns:
            List of package summary dicts.
        """
        params = [f"ts_query_web={query}", f"limit={limit}", f"offset={offset}"]
        if kind is not None:
            params.append(f"kind={kind}")
        if verified_publisher:
            params.append("verified_publisher=true")
        if official:
            params.append("official=true")

        data = self._get(f"/packages/search?{'&'.join(params)}")
        packages = data.get("packages") or []

        return [_summarize_package(pkg) for pkg in packages]

    def search_charts(self, query: str, limit: int = 10,
                      verified_publisher: bool = False) -> list[dict[str, Any]]:
        """Search Helm charts.

        Args:
            query: Search text (e.g. "postgresql", "redis", "nginx").
            limit: Max results.
            verified_publisher: Only verified publishers.

        Returns:
            List of chart summary dicts with keys:
            name, version, app_version, description, repo, repo_url,
            stars, deprecated, signed, security_summary.
        """
        return self.search(query, kind=KIND_HELM_CHART, limit=limit,
                           verified_publisher=verified_publisher)

    def search_images(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Search container images.

        Args:
            query: Search text (e.g. "nginx", "postgres", "redis").
            limit: Max results.

        Returns:
            List of image summary dicts.
        """
        return self.search(query, kind=KIND_CONTAINER_IMAGE, limit=limit)

    def chart_detail(self, repo_name: str, chart_name: str,
                     version: str = "") -> dict[str, Any]:
        """Get detailed information about a Helm chart.

        Args:
            repo_name: Repository name (e.g. "bitnami").
            chart_name: Chart name (e.g. "postgresql").
            version: Specific version (empty = latest).

        Returns:
            Dict with: name, version, app_version, description,
            readme, install_command, values_url, keywords,
            maintainers, home_url, containers_images, links.
        """
        path = f"/packages/helm/{repo_name}/{chart_name}"
        if version:
            path += f"/{version}"

        data = self._get(path)
        return _detail_from_response(data, repo_name)

    def chart_values(self, repo_name: str, chart_name: str,
                     version: str = "") -> str | None:
        """Get the default values.yaml content for a Helm chart.

        Args:
            repo_name: Repository name.
            chart_name: Chart name.
            version: Specific version (empty = latest).

        Returns:
            values.yaml content as string, or None if not available.
        """
        detail = self.chart_detail(repo_name, chart_name, version)
        values_url = detail.get("values_url")
        if not values_url:
            return None
        req = urllib.request.Request(values_url)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")

    def list_chart_versions(self, repo_name: str,
                            chart_name: str) -> list[dict[str, str]]:
        """List available versions of a Helm chart.

        Returns:
            List of dicts with: version, app_version, created.
        """
        detail = self.chart_detail(repo_name, chart_name)
        return detail.get("available_versions", [])


def _summarize_package(pkg: dict[str, Any]) -> dict[str, Any]:
    """Extract summary fields from a search result package."""
    repo = pkg.get("repository", {})
    return {
        "name": pkg.get("name", ""),
        "display_name": pkg.get("display_name", ""),
        "version": pkg.get("version", ""),
        "app_version": pkg.get("app_version", ""),
        "description": pkg.get("description", ""),
        "repo": repo.get("name", ""),
        "repo_display": repo.get("display_name", ""),
        "repo_url": repo.get("url", ""),
        "stars": pkg.get("stars", 0),
        "deprecated": pkg.get("deprecated", False),
        "signed": pkg.get("signed", False),
        "verified_publisher": repo.get("verified_publisher", False),
        "security_summary": pkg.get("security_report_summary"),
        "kind": repo.get("kind"),
    }


def _detail_from_response(data: dict[str, Any],
                          repo_name: str) -> dict[str, Any]:
    """Extract detail fields from a package detail response."""
    name = data.get("name", "")
    version = data.get("version", "")
    repo_url = data.get("repository", {}).get("url", "")

    # Build install command
    if repo_url.startswith("oci://"):
        install_cmd = f"helm install my-{name} {repo_url}/{name} --version {version}"
    else:
        install_cmd = (
            f"helm repo add {repo_name} {repo_url}\n"
            f"helm install my-{name} {repo_name}/{name} --version {version}"
        )

    # Extract container images used by the chart
    containers = []
    for img in data.get("containers_images", []):
        containers.append({
            "image": img.get("image", ""),
            "whitelisted": img.get("whitelisted", False),
        })

    # Extract available versions
    available_versions = []
    for ver in data.get("available_versions", []):
        available_versions.append({
            "version": ver.get("version", ""),
            "created": str(ver.get("ts", "")),
        })

    # Extract links
    links = []
    for link in data.get("links", []):
        links.append({
            "name": link.get("name", ""),
            "url": link.get("url", ""),
        })

    # Values URL
    default_values = data.get("default_values")
    values_url = None
    if default_values:
        values_url = default_values

    return {
        "name": name,
        "version": version,
        "app_version": data.get("app_version", ""),
        "description": data.get("description", ""),
        "readme": data.get("readme", ""),
        "install_command": install_cmd,
        "values_url": values_url,
        "keywords": data.get("keywords", []),
        "home_url": data.get("home_url", ""),
        "containers_images": containers,
        "links": links,
        "available_versions": available_versions,
        "maintainers": data.get("maintainers", []),
        "license": data.get("license", ""),
        "signed": data.get("signed", False),
        "security_report_summary": data.get("security_report_summary"),
    }
