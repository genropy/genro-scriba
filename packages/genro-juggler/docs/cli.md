# CLI Reference

## Commands

### `juggler run FILE.py`

Run a JugglerApp from a Python file. Starts a remote server for REPL connections.

```bash
juggler run examples/my_infra.py
```

The file must contain a class named `Application` that extends `JugglerApp`.

### `juggler list`

List running juggler apps and their connection status.

```bash
juggler list
```

### `juggler connect NAME`

Connect an interactive REPL to a running app.

```bash
juggler connect my_infra
```

REPL namespace:
- `app` — RemoteProxy to the running JugglerApp

Slash commands: `/status`, `/slots`, `/yaml [slot]`, `/help`, `/quit`

### `juggler stop NAME`

Stop a running juggler app.

```bash
juggler stop my_infra
```

### `juggler yaml FILE.py`

Dry-run: compile and print YAML without applying to targets.

```bash
juggler yaml examples/my_infra.py
juggler yaml examples/my_infra.py --slot kubernetes
```

### `juggler dashboard FILE.py`

Launch the TUI dashboard with tmux split: TUI on top, REPL on bottom.

```bash
juggler dashboard examples/my_infra.py
```

Features:
- **Infrastructure tab**: tree + Rich detail cards, Auto Live checkbox
- **ArtifactHub tab**: search Helm charts
- **Log tab**: operation history
- **REPL**: `/status`, `/slots`, `/yaml`, `/apply`, `/live`, `/help`

Requires: `pip install genro-juggler[dashboard]` and `tmux`.
