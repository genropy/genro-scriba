# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for ArtifactHub explorer.

Uses real HTTP calls to the public API — these tests require network access.
They test the actual API integration, not mocked responses.
"""

from __future__ import annotations

import pytest

from genro_scriba.artifact_hub import ArtifactHub


@pytest.fixture
def hub() -> ArtifactHub:
    return ArtifactHub()


class TestSearchCharts:

    def test_search_returns_results(self, hub: ArtifactHub) -> None:
        results = hub.search_charts("postgresql", limit=3)
        assert len(results) > 0
        assert results[0]["name"] == "postgresql"

    def test_result_has_expected_fields(self, hub: ArtifactHub) -> None:
        results = hub.search_charts("redis", limit=1)
        chart = results[0]
        assert "name" in chart
        assert "version" in chart
        assert "description" in chart
        assert "repo" in chart
        assert "stars" in chart

    def test_verified_publisher_filter(self, hub: ArtifactHub) -> None:
        results = hub.search_charts("nginx", limit=5, verified_publisher=True)
        for chart in results:
            assert chart["verified_publisher"] is True

    def test_empty_query_returns_results(self, hub: ArtifactHub) -> None:
        results = hub.search_charts("xyznonexistent12345", limit=3)
        assert isinstance(results, list)


class TestSearchImages:

    def test_search_returns_results(self, hub: ArtifactHub) -> None:
        results = hub.search_images("nginx", limit=3)
        assert len(results) > 0

    def test_result_kind_is_container(self, hub: ArtifactHub) -> None:
        results = hub.search_images("postgres", limit=1)
        if results:
            assert results[0]["kind"] == 12


class TestChartDetail:

    def test_bitnami_postgresql(self, hub: ArtifactHub) -> None:
        detail = hub.chart_detail("bitnami", "postgresql")
        assert detail["name"] == "postgresql"
        assert detail["version"]
        assert detail["description"]
        assert detail["install_command"]
        assert "bitnami" in detail["install_command"]

    def test_has_container_images(self, hub: ArtifactHub) -> None:
        detail = hub.chart_detail("bitnami", "postgresql")
        assert isinstance(detail["containers_images"], list)

    def test_has_available_versions(self, hub: ArtifactHub) -> None:
        detail = hub.chart_detail("bitnami", "postgresql")
        assert len(detail["available_versions"]) > 0

    def test_has_keywords(self, hub: ArtifactHub) -> None:
        detail = hub.chart_detail("bitnami", "postgresql")
        assert "postgresql" in detail["keywords"]
