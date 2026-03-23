# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""FileTarget — write compiled resources to YAML files.

The simplest target: same as genro-scriba's to_yaml(), but conforming
to the TargetBase interface. Useful as fallback or for dry-run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .base import TargetBase


class FileTarget(TargetBase):
    """Target that writes resources to YAML files.

    Args:
        output_dir: Directory for output files.
        filename: Single output file (alternative to output_dir).
    """

    def __init__(self, output_dir: str | Path | None = None,
                 filename: str | Path | None = None) -> None:
        self._output_dir = Path(output_dir) if output_dir else None
        self._filename = Path(filename) if filename else None

    def apply(self, resource: dict[str, Any]) -> dict[str, Any]:
        """Write resource to YAML file."""
        yaml_str = yaml.dump(
            resource,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )

        if self._filename:
            self._filename.parent.mkdir(parents=True, exist_ok=True)
            self._filename.write_text(yaml_str, encoding="utf-8")
            return {"status": "written", "path": str(self._filename)}

        if self._output_dir:
            kind = resource.get("kind", "resource")
            name = resource.get("metadata", {}).get("name", "unnamed")
            fname = f"{kind.lower()}-{name}.yaml"
            path = self._output_dir / fname
            self._output_dir.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml_str, encoding="utf-8")
            return {"status": "written", "path": str(path)}

        return {"status": "dry_run", "yaml": yaml_str}

    def apply_many(self, resources: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Write all resources. If single filename, write multi-document."""
        if self._filename:
            documents = []
            for resource in resources:
                documents.append(yaml.dump(
                    resource,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                ))
            self._filename.parent.mkdir(parents=True, exist_ok=True)
            self._filename.write_text("---\n".join(documents), encoding="utf-8")
            return [{"status": "written", "path": str(self._filename)}]

        return [self.apply(r) for r in resources]
