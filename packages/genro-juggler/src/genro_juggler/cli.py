# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""CLI for genro-juggler.

Commands:
    juggler run FILE.py              Run a JugglerApp from a Python file
    juggler list                     List running juggler apps
    juggler connect NAME             Connect REPL to a running app
    juggler stop NAME                Stop a running app
    juggler yaml FILE.py             Dry-run: print YAML without applying
    juggler dashboard FILE.py        Launch TUI dashboard (tmux split with REPL)
    juggler dashboard-run FILE.py    Run dashboard TUI only (internal, used by tmux)
    juggler dashboard-repl NAME      Connect REPL to a dashboard (internal, used by tmux)

Usage:
    juggler run examples/my_infra.py
    juggler connect my_infra
    juggler list
    juggler dashboard examples/my_infra.py
"""

from __future__ import annotations

import argparse
import code
import importlib.util
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

from . import registry
from .remote import RemoteProxy


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="juggler",
        description="genro-juggler: reactive infrastructure bus",
    )
    sub = parser.add_subparsers(dest="command")

    # run
    run_parser = sub.add_parser("run", help="Run a JugglerApp from a Python file")
    run_parser.add_argument("file", help="Python file with Application class")

    # list
    sub.add_parser("list", help="List running juggler apps")

    # connect
    connect_parser = sub.add_parser("connect", help="Connect REPL to a running app")
    connect_parser.add_argument("name", help="App name")

    # stop
    stop_parser = sub.add_parser("stop", help="Stop a running app")
    stop_parser.add_argument("name", help="App name")

    # yaml
    yaml_parser = sub.add_parser("yaml", help="Dry-run: print YAML")
    yaml_parser.add_argument("file", help="Python file with Application class")
    yaml_parser.add_argument("--slot", default="", help="Slot name (default: all)")

    # dashboard (user-facing: tmux split)
    dash_parser = sub.add_parser("dashboard", help="Launch TUI dashboard with REPL")
    dash_parser.add_argument("file", help="Python file with Application class")

    # dashboard-run (internal: TUI only, used by tmux top pane)
    dash_run_parser = sub.add_parser("dashboard-run", help=argparse.SUPPRESS)
    dash_run_parser.add_argument("file", help="Python file with Application class")

    # dashboard-repl (internal: REPL only, used by tmux bottom pane)
    dash_repl_parser = sub.add_parser("dashboard-repl", help=argparse.SUPPRESS)
    dash_repl_parser.add_argument("name", help="Dashboard app name")

    args = parser.parse_args()

    if args.command == "run":
        run_app(args.file)
    elif args.command == "list":
        list_running()
    elif args.command == "connect":
        connect_repl(args.name)
    elif args.command == "stop":
        stop_app(args.name)
    elif args.command == "yaml":
        dry_run(args.file, args.slot)
    elif args.command == "dashboard":
        launch_dashboard(args.file)
    elif args.command == "dashboard-run":
        dashboard_run(args.file)
    elif args.command == "dashboard-repl":
        dashboard_repl(args.name)
    else:
        parser.print_help()


def run_app(file_path: str) -> None:
    """Load and run a JugglerApp from a Python file."""
    path = Path(file_path).resolve()
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    # Import the module
    spec = importlib.util.spec_from_file_location("juggler_app", str(path))
    if spec is None or spec.loader is None:
        print(f"Cannot load: {path}")
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find Application class
    app_class = getattr(module, "Application", None)
    if app_class is None:
        print(f"No 'Application' class found in {path}")
        sys.exit(1)

    # Setup remote server
    port = registry.find_free_port()
    app_name = path.stem

    from .remote import RemoteServer
    app = app_class()

    remote = RemoteServer(app, port)
    remote.start()

    registry.register_app(app_name, port, remote.token)
    print(f"Juggler app '{app_name}' running on port {port}")
    print(f"Connect with: juggler connect {app_name}")
    print(f"Slots: {list(app._slots.keys())}")
    print(f"Status: {app.status()}")
    print()
    print("Press Ctrl+C to stop.")

    try:
        # Keep running until interrupted
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        remote.stop()
        registry.unregister_app(app_name)


def list_running() -> None:
    """List registered juggler apps and check if alive."""
    apps = registry.list_apps()
    if not apps:
        print("No juggler apps running.")
        return

    for name, info in apps.items():
        port = info.get("port", 0)
        alive = _check_alive(port)
        status = "alive" if alive else "dead"
        print(f"  {name}: port={port} [{status}]")

        if not alive:
            registry.unregister_app(name)


def connect_repl(name: str) -> None:
    """Connect an interactive REPL to a running JugglerApp."""
    info = registry.get_app_info(name)
    if info is None:
        print(f"App '{name}' not found. Run 'juggler list' to see available apps.")
        sys.exit(1)

    port = info["port"]
    token = info.get("token", "")

    proxy = RemoteProxy("127.0.0.1", port, token)

    # Verify connection
    try:
        slots = proxy.slots()
        status = proxy.status()
    except Exception as e:
        print(f"Cannot connect to '{name}': {e}")
        sys.exit(1)

    print(f"Connected to '{name}' (port {port})")
    print(f"Slots: {slots}")
    print(f"Status: {status}")
    print()
    print("Commands:")
    print("  app.status()                  — target status")
    print("  app.slots()                   — list slots")
    print("  app.to_yaml('kubernetes')     — show YAML")
    print("  app.apply('kubernetes')       — apply to target")
    print("  app.data_set('key', 'value')  — set data (triggers apply)")
    print("  app.data_get('key')           — read data")
    print("  /quit                         — disconnect")
    print()

    # Start REPL with proxy in namespace
    namespace: dict[str, Any] = {"app": proxy}

    class SlashConsole(code.InteractiveConsole):
        def runsource(self, source: str, filename: str = "<input>",
                      symbol: str = "single") -> bool:
            stripped = source.strip()
            if stripped == "/quit":
                raise SystemExit
            if stripped == "/help":
                _print_repl_help()
                return False
            if stripped == "/status":
                try:
                    print(proxy.status())
                except Exception as e:
                    print(f"Error: {e}")
                return False
            if stripped == "/slots":
                try:
                    print(proxy.slots())
                except Exception as e:
                    print(f"Error: {e}")
                return False
            if stripped.startswith("/yaml"):
                parts = stripped.split()
                slot = parts[1] if len(parts) > 1 else ""
                if slot:
                    try:
                        print(proxy.to_yaml(slot))
                    except Exception as e:
                        print(f"Error: {e}")
                else:
                    for s in proxy.slots():
                        print(f"--- {s} ---")
                        try:
                            print(proxy.to_yaml(s))
                        except Exception as e:
                            print(f"Error: {e}")
                return False
            return super().runsource(source, filename, symbol)

    console = SlashConsole(locals=namespace)
    console.interact(banner="", exitmsg="Disconnected.")


def stop_app(name: str) -> None:
    """Stop a running JugglerApp."""
    info = registry.get_app_info(name)
    if info is None:
        print(f"App '{name}' not found.")
        sys.exit(1)

    port = info["port"]
    token = info.get("token", "")

    try:
        proxy = RemoteProxy("127.0.0.1", port, token)
        proxy.quit()
        print(f"Sent shutdown to '{name}'.")
    except Exception as e:
        print(f"Could not stop '{name}': {e}")

    registry.unregister_app(name)


def dry_run(file_path: str, slot: str = "") -> None:
    """Load app and print YAML without applying to any target."""
    path = Path(file_path).resolve()
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("juggler_app", str(path))
    if spec is None or spec.loader is None:
        print(f"Cannot load: {path}")
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app_class = getattr(module, "Application", None)
    if app_class is None:
        print(f"No 'Application' class found in {path}")
        sys.exit(1)

    app = app_class()

    if slot:
        print(app.to_yaml(slot))
    else:
        for slot_name in app._slots:
            print(f"--- {slot_name} ---")
            print(app.to_yaml(slot_name))


def launch_dashboard(file_path: str) -> None:
    """Launch dashboard in tmux: TUI on top, REPL on bottom.

    Falls back to TUI-only mode if tmux is not available.
    """
    try:
        from genro_juggler.dashboard import JugglerDashboard  # noqa: F401
    except ImportError:
        print("Dashboard requires genro-textual. Install with:")
        print("  pip install genro-juggler[dashboard]")
        sys.exit(1)

    path = Path(file_path).resolve()
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    app_name = f"dashboard-{path.stem}"

    if shutil.which("tmux") is None:
        print("tmux not found. Running dashboard without REPL.")
        print("Install tmux for the split TUI+REPL experience.")
        print()
        dashboard_run(str(path))
        return

    _run_dashboard_tmux(str(path), app_name)


def _run_dashboard_tmux(file_path: str, app_name: str) -> None:
    """Create tmux session: TUI top pane, REPL bottom pane."""
    session = f"juggler-{app_name}"
    file_abs = os.path.abspath(file_path)
    juggler_bin = shutil.which("juggler") or f"{sys.executable} -m genro_juggler.cli"

    # Top pane: dashboard TUI (starts RemoteServer + registers in registry)
    run_cmd = (
        f"{juggler_bin} dashboard-run {file_abs}; "
        f"tmux kill-session -t {session}"
    )
    # Bottom pane: wait for registration, then connect REPL
    connect_cmd = (
        f"sleep 1 && {juggler_bin} dashboard-repl {app_name}"
    )

    subprocess.run(
        ["tmux", "new-session", "-d", "-s", session, "-x", "200", "-y", "50", run_cmd],
        check=True,
    )
    subprocess.run(
        ["tmux", "split-window", "-v", "-t", session, "-p", "30", connect_cmd],
        check=True,
    )
    subprocess.run(
        ["tmux", "set-option", "-t", session, "mouse", "on"],
        check=True,
    )
    subprocess.run(
        ["tmux", "select-pane", "-t", session + ":.0"],
        check=True,
    )
    os.execvp("tmux", ["tmux", "attach-session", "-t", session])


def dashboard_run(file_path: str) -> None:
    """Run dashboard TUI only (internal, called by tmux top pane)."""
    from genro_juggler.dashboard import JugglerDashboard

    path = Path(file_path).resolve()
    if not path.exists():
        print(f"File not found: {path}")
        sys.exit(1)

    app_instance = _load_app(path)
    app_name = f"dashboard-{path.stem}"
    dashboard = JugglerDashboard(app_instance, name=app_name)
    dashboard.run()


def dashboard_repl(name: str) -> None:
    """Connect REPL to a running dashboard (internal, called by tmux bottom pane)."""
    info = registry.get_app_info(name)
    if info is None:
        print(f"Dashboard '{name}' not found. Waiting...")
        # Retry a few times — the TUI pane may still be starting
        import time
        for _attempt in range(10):
            time.sleep(1)
            info = registry.get_app_info(name)
            if info is not None:
                break
        if info is None:
            print(f"Dashboard '{name}' not available after 10 seconds.")
            sys.exit(1)

    port = info["port"]
    token = info.get("token", "")

    proxy = RemoteProxy("127.0.0.1", port, token)

    try:
        slots = proxy.slots()
        status = proxy.status()
    except Exception as e:
        print(f"Cannot connect to '{name}': {e}")
        sys.exit(1)

    print(f"Connected to dashboard '{name}' (port {port})")
    print(f"Slots: {slots}")
    print(f"Status: {status}")
    print()
    _print_dashboard_repl_help()
    print()

    namespace: dict[str, Any] = {"app": proxy}

    class DashboardSlashConsole(code.InteractiveConsole):
        """REPL with dashboard-specific slash commands."""

        def runsource(self, source: str, filename: str = "<input>",
                      symbol: str = "single") -> bool:
            stripped = source.strip()
            if stripped == "/quit":
                raise SystemExit
            if stripped == "/help":
                _print_dashboard_repl_help()
                return False
            if stripped == "/status":
                _safe_print(proxy.status)
                return False
            if stripped == "/slots":
                _safe_print(proxy.slots)
                return False
            if stripped.startswith("/yaml"):
                parts = stripped.split()
                slot = parts[1] if len(parts) > 1 else ""
                if slot:
                    _safe_print(lambda: proxy.to_yaml(slot))
                else:
                    _print_all_yaml(proxy)
                return False
            if stripped.startswith("/apply"):
                parts = stripped.split()
                slot = parts[1] if len(parts) > 1 else ""
                if slot:
                    _safe_print(lambda: proxy.apply(slot))
                else:
                    _safe_print(proxy.apply_all)
                return False
            if stripped == "/live":
                _safe_print(proxy.apply_all)
                return False
            return super().runsource(source, filename, symbol)

    console = DashboardSlashConsole(locals=namespace)
    console.interact(banner="", exitmsg="Disconnected.")


def _check_alive(port: int) -> bool:
    """Check if a port is accepting connections."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("127.0.0.1", port))
        sock.close()
        return True
    except (ConnectionRefusedError, TimeoutError, OSError):
        return False


def _load_app(path: Path) -> Any:
    """Load a JugglerApp from a Python file."""
    spec = importlib.util.spec_from_file_location("juggler_app", str(path))
    if spec is None or spec.loader is None:
        print(f"Cannot load: {path}")
        sys.exit(1)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app_class = getattr(module, "Application", None)
    if app_class is None:
        print(f"No 'Application' class found in {path}")
        sys.exit(1)
    return app_class()


def _safe_print(fn: Any) -> None:
    """Call fn() and print result, catching errors."""
    try:
        result = fn()
        print(result)
    except Exception as e:
        print(f"Error: {e}")


def _print_all_yaml(proxy: RemoteProxy) -> None:
    """Print YAML for all slots."""
    for slot in proxy.slots():
        print(f"--- {slot} ---")
        _safe_print(lambda s=slot: proxy.to_yaml(s))


def _print_repl_help() -> None:
    print("Slash commands:")
    print("  /status           — target status")
    print("  /slots            — list slots")
    print("  /yaml [slot]      — show YAML (all slots if no name)")
    print("  /help             — this help")
    print("  /quit             — disconnect")
    print()
    print("Python expressions:")
    print("  app.status()")
    print("  app.data_set('api.image', 'myapp:v2')")
    print("  app.data_get('api.image')")
    print("  app.apply('kubernetes')")
    print("  app.to_yaml('ansible')")


def _print_dashboard_repl_help() -> None:
    print("Slash commands:")
    print("  /status           — target status")
    print("  /slots            — list slots")
    print("  /yaml [slot]      — show YAML (all slots if no name)")
    print("  /apply [slot]     — apply slot to target (all if no name)")
    print("  /live             — apply all slots (Go Live)")
    print("  /help             — this help")
    print("  /quit             — disconnect")
    print()
    print("Python expressions:")
    print("  app.status()")
    print("  app.data_set('api.image', 'myapp:v2')  # triggers tree refresh")
    print("  app.data_get('api.image')")
    print("  app.apply('kubernetes')")
    print("  app.to_yaml('ansible')")
