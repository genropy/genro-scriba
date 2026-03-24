# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""DashboardUI — TextualApp subclass for the Juggler dashboard.

Defines the TUI layout: header, tabbed content with Infrastructure,
ArtifactHub and Log tabs.

Layout:
    Header: "Juggler Dashboard"
    TabbedContent:
        Tab "Infrastructure":
            Tree (resource hierarchy: slot > kind > name)
            Checkbox "Auto Live" (toggle auto-apply to targets)
            Static (status summary)
        Tab "ArtifactHub":
            Input (search query)
            DataTable (search results: name, repo, version, stars)
            Static (chart detail)
        Tab "Log":
            RichLog (operation history)
    Footer
"""

from __future__ import annotations

import datetime
from typing import Any

from genro_textual import TextualApp


class DashboardUI(TextualApp):
    """TUI for the Juggler dashboard. Driven by JugglerDashboard."""

    def __init__(self, dashboard: Any) -> None:
        super().__init__()
        self._dashboard = dashboard

    def recipe(self, page: Any) -> None:
        """Define the dashboard layout."""
        page.css(DASHBOARD_CSS)
        page.binding(key="q", action="quit", description="Quit")
        page.binding(key="r", action="refresh", description="Refresh")
        page.binding(key="l", action="switch_log", description="Log tab")
        page.binding(key="a", action="switch_hub", description="ArtifactHub")

        page.header(content="Juggler Dashboard")

        tabs = page.tabbedcontent(initial="infrastructure")

        infra_tab = tabs.tabpane(title="Infrastructure", id="infrastructure")
        infra_tab.tree(label="Resources", id="resource_tree")
        infra_tab.checkbox(content="Auto Live", value=False, id="auto_live")
        infra_tab.static("", id="status_summary")

        hub_tab = tabs.tabpane(title="ArtifactHub", id="artifacthub")
        hub_tab.input(placeholder="Search Helm charts...", id="hub_search")
        hub_tab.datatable(id="hub_results", show_header=True, cursor_type="row")
        hub_tab.static("", id="hub_detail")

        log_tab = tabs.tabpane(title="Log", id="log")
        log_tab.richlog(id="operation_log", max_lines=500, wrap=True)

        page.footer()

    def action_refresh(self) -> None:
        """Refresh the resource tree."""
        self._dashboard.refresh_tree()

    def action_quit(self) -> None:
        """Quit the dashboard."""
        if self._live_app is not None:
            self._live_app.exit()

    def action_switch_log(self) -> None:
        """Switch to the Log tab."""
        if self._live_app is None:
            return
        tabs = self._live_app.query_one("TabbedContent")
        tabs.active = "log"  # type: ignore[union-attr]

    def action_switch_hub(self) -> None:
        """Switch to the ArtifactHub tab."""
        if self._live_app is None:
            return
        tabs = self._live_app.query_one("TabbedContent")
        tabs.active = "artifacthub"  # type: ignore[union-attr]

    def on_input_changed(self, event: Any) -> None:
        """Handle input changes — trigger ArtifactHub search on hub_search."""
        widget = getattr(event, "input", None)
        if widget is None:
            return
        widget_id = getattr(widget, "id", "")
        if widget_id == "hub_search" and len(event.value) >= 3:
            self._dashboard.search_charts(event.value)

    def on_checkbox_changed(self, event: Any) -> None:
        """Handle Auto Live checkbox toggle."""
        widget = getattr(event, "checkbox", None) or getattr(event, "input", None)
        if widget is None:
            return
        widget_id = getattr(widget, "id", "")
        if widget_id == "auto_live":
            self._dashboard.set_auto_live(event.value)

    def populate_tree(self, tree_nodes: list[dict[str, Any]]) -> None:
        """Populate the Tree widget with resource nodes."""
        if self._live_app is None:
            return
        tree_widget = self._live_app.query_one("#resource_tree")
        tree_widget.clear()
        tree_widget.root.expand()
        for slot_node in tree_nodes:
            slot_branch = tree_widget.root.add(slot_node["label"])
            slot_branch.expand()
            for kind_node in slot_node.get("children", []):
                kind_branch = slot_branch.add(kind_node["label"])
                kind_branch.expand()
                for res_node in kind_node.get("children", []):
                    kind_branch.add_leaf(res_node["label"])

    def update_status(self, summary: str) -> None:
        """Update the status summary text."""
        if self._live_app is None:
            return
        widget = self._live_app.query_one("#status_summary")
        widget.update(summary)

    def populate_hub_results(self, results: list[dict[str, Any]]) -> None:
        """Populate the ArtifactHub DataTable with search results."""
        if self._live_app is None:
            return
        table = self._live_app.query_one("#hub_results")
        table.clear(columns=True)  # type: ignore[union-attr]
        table.add_columns("Name", "Repo", "Version", "Stars", "Description")  # type: ignore[union-attr]
        for chart in results:
            table.add_row(  # type: ignore[union-attr]
                chart.get("name", ""),
                chart.get("repo", ""),
                chart.get("version", ""),
                str(chart.get("stars", 0)),
                (chart.get("description", "")[:60] + "..."
                 if len(chart.get("description", "")) > 60
                 else chart.get("description", "")),
            )

    def update_hub_detail(self, detail: str) -> None:
        """Update the ArtifactHub detail text."""
        if self._live_app is None:
            return
        widget = self._live_app.query_one("#hub_detail")
        widget.update(detail)  # type: ignore[union-attr]

    def log_message(self, message: str) -> None:
        """Append a message to the operation log."""
        if self._live_app is None:
            return
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_widget = self._live_app.query_one("#operation_log")
        log_widget.write(f"[{timestamp}] {message}")  # type: ignore[union-attr]


DASHBOARD_CSS = """
#resource_tree {
    height: 1fr;
    min-height: 10;
}

#auto_live {
    height: auto;
    padding: 0 1;
}

#status_summary {
    height: auto;
    padding: 1;
    color: $text-muted;
}

#hub_search {
    height: auto;
    margin: 1;
}

#hub_results {
    height: 1fr;
    min-height: 8;
}

#hub_detail {
    height: auto;
    padding: 1;
    color: $text-muted;
}

#operation_log {
    height: 1fr;
    min-height: 10;
}
"""
