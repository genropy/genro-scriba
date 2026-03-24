# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""JugglerDashboard — mediator between JugglerApp and DashboardUI.

JugglerApp owns the infrastructure Bag (recipes + compiled resources).
DashboardUI owns the UI (TextualApp + widgets).
JugglerDashboard connects them: compiles resources, transforms to tree
nodes, populates the UI.

Reactive: subscribes to JugglerApp.data via Bag.subscribe(). When data
changes, JugglerApp recompiles the affected slots (its own trigger),
then the dashboard re-reads the compiled resources and refreshes the tree.
Uses call_from_thread for thread safety (data changes may come from
the remote REPL in a different thread).

Remote: starts a RemoteServer so the REPL in the bottom tmux pane can
control the JugglerApp (set data, apply, status, yaml).

ArtifactHub: search Helm charts and display details in the dashboard.
"""

from __future__ import annotations

import sys
import traceback
from typing import TYPE_CHECKING, Any

from genro_scriba import ArtifactHub

from genro_juggler import registry
from genro_juggler.dashboard.transforms import collect_slot_resources, resources_to_tree_nodes
from genro_juggler.dashboard.ui import DashboardUI
from genro_juggler.remote import RemoteServer

if TYPE_CHECKING:
    from genro_juggler.juggler_app import JugglerApp


class JugglerDashboard:
    """Mediator: connects a JugglerApp to a DashboardUI.

    Usage:
        app = MyInfra(targets={...}, data={...})
        dashboard = JugglerDashboard(app)
        dashboard.run()

    With REPL (tmux):
        dashboard = JugglerDashboard(app, name="my_infra")
        dashboard.run()  # starts RemoteServer + registers in registry
    """

    _SUBSCRIBER_ID = "dashboard_refresh"

    def __init__(self, app: JugglerApp, name: str = "") -> None:
        self._app = app
        self._ui = DashboardUI(self)
        self._subscribed = False
        self._auto_live = False
        self._name = name
        self._remote: RemoteServer | None = None
        self._hub = ArtifactHub()
        self._last_search_results: list[dict[str, Any]] = []

    def run(self) -> None:
        """Start the dashboard TUI (and RemoteServer if name is set)."""
        original_setup = self._ui.setup

        def patched_setup() -> None:
            try:
                original_setup()
                self._populate()
                self._subscribe()
            except Exception as e:
                self._handle_error("setup", e)

        self._ui.setup = patched_setup  # type: ignore[assignment]

        if self._name:
            self._start_remote()

        try:
            self._ui.run()
        finally:
            self._stop_remote()

    def refresh_tree(self) -> None:
        """Refresh the resource tree from current JugglerApp state."""
        try:
            self._populate()
        except Exception as e:
            self._handle_error("refresh_tree", e)

    def set_auto_live(self, enabled: bool) -> None:
        """Toggle auto-apply mode. When ON, data changes apply to targets."""
        self._auto_live = enabled
        label = "ON" if enabled else "OFF"
        self._log(f"Auto Live {label}")
        if enabled:
            self.go_live()

    def go_live(self) -> None:
        """Apply all slots to their targets and log results."""
        self._log("Applying all slots...")
        try:
            results = self._app.apply_all()
            for slot_name, slot_results in results.items():
                for result in slot_results:
                    status = result.get("status", "unknown")
                    kind = result.get("kind", "")
                    name = result.get("name", "")
                    self._log(f"  {slot_name}: {kind}/{name} → {status}")
            total = sum(len(r) for r in results.values())
            self._log(f"Applied {total} resources")
        except Exception as e:
            self._handle_error("go_live", e)
        self._populate()

    def search_charts(self, query: str) -> None:
        """Search ArtifactHub for Helm charts and display results."""
        try:
            results = self._hub.search_charts(query, limit=15)
            self._last_search_results = results
            self._ui.populate_hub_results(results)
            self._ui.update_hub_detail(f"Found {len(results)} charts for '{query}'")
        except Exception as e:
            self._handle_error("search_charts", e)
            self._ui.update_hub_detail(f"Search error: {e}")
            self._last_search_results = []

    def get_search_results(self) -> list[dict[str, Any]]:
        """Return last ArtifactHub search results (for testing)."""
        return list(self._last_search_results)

    def _log(self, message: str) -> None:
        """Write a message to the UI operation log."""
        self._ui.log_message(message)

    def _handle_error(self, context: str, exc: Exception) -> None:
        """Log an error to the UI and stderr."""
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        error_text = "".join(tb)
        self._log(f"ERROR in {context}: {exc}")
        print(f"[Dashboard] ERROR in {context}:\n{error_text}", file=sys.stderr)

    def _start_remote(self) -> None:
        """Start RemoteServer and register in the app registry."""
        port = registry.find_free_port()
        self._remote = RemoteServer(self._app, port)
        self._remote.start()
        registry.register_app(self._name, port, self._remote.token)

    def _stop_remote(self) -> None:
        """Stop RemoteServer and unregister from registry."""
        if self._remote is not None:
            self._remote.stop()
            self._remote = None
        if self._name:
            registry.unregister_app(self._name)

    def _subscribe(self) -> None:
        """Subscribe to data changes on the JugglerApp Bag."""
        if self._subscribed:
            return
        self._app.data.subscribe(
            self._SUBSCRIBER_ID,
            any=self._on_data_changed,
        )
        self._subscribed = True

    def _unsubscribe(self) -> None:
        """Remove the data subscription."""
        if not self._subscribed:
            return
        self._app.data.unsubscribe(self._SUBSCRIBER_ID, any=True)
        self._subscribed = False

    def _on_data_changed(self, **_kwargs: Any) -> None:
        """Callback fired by Bag.subscribe when data changes.

        JugglerApp's own trigger already recompiles the affected slots.
        We re-read the compiled resources and refresh the tree.
        If auto_live is ON, we also apply to targets and log results.
        Uses call_from_thread because the change may come from the remote REPL.
        """
        live_app = self._ui._live_app
        if live_app is not None:
            live_app.call_from_thread(self._on_data_changed_sync)
        else:
            self._on_data_changed_sync()

    def _on_data_changed_sync(self) -> None:
        """Synchronous handler for data changes (runs on the main thread)."""
        try:
            self._populate()
            if self._auto_live:
                self.go_live()
        except Exception as e:
            self._handle_error("data_changed", e)

    def _populate(self) -> None:
        """Compile resources and populate the tree."""
        slot_resources = collect_slot_resources(self._app)
        statuses = self._app.status()
        tree_nodes = resources_to_tree_nodes(slot_resources, statuses)
        self._ui.populate_tree(tree_nodes)

        total_resources = sum(len(r) for r in slot_resources.values())
        slot_names = ", ".join(slot_resources.keys())
        self._ui.update_status(
            f"Slots: {slot_names} | Resources: {total_resources}"
        )

    def get_tree_data(self) -> list[dict[str, Any]]:
        """Return tree node data without UI (for testing)."""
        slot_resources = collect_slot_resources(self._app)
        statuses = self._app.status()
        return resources_to_tree_nodes(slot_resources, statuses)
