# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""JugglerDashboard — mediator between JugglerApp and DashboardUI.

JugglerApp owns the infrastructure Bag (recipes + compiled resources).
DashboardUI owns the UI (TextualApp + widgets).
JugglerDashboard connects them: compiles resources, transforms to tree
nodes, populates the UI.

Phase 1: static preview only (no reactive triggers).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from genro_juggler.dashboard.transforms import collect_slot_resources, resources_to_tree_nodes
from genro_juggler.dashboard.ui import DashboardUI

if TYPE_CHECKING:
    from genro_juggler.juggler_app import JugglerApp


class JugglerDashboard:
    """Mediator: connects a JugglerApp to a DashboardUI.

    Usage:
        app = MyInfra(targets={...}, data={...})
        dashboard = JugglerDashboard(app)
        dashboard.run()
    """

    def __init__(self, app: JugglerApp) -> None:
        self._app = app
        self._ui = DashboardUI(self)
        self._original_setup = self._ui.setup

    def run(self) -> None:
        """Start the dashboard TUI."""
        original_setup = self._ui.setup

        def patched_setup() -> None:
            original_setup()
            self._populate()

        self._ui.setup = patched_setup  # type: ignore[assignment]
        self._ui.run()

    def refresh_tree(self) -> None:
        """Refresh the resource tree from current JugglerApp state."""
        self._populate()

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
