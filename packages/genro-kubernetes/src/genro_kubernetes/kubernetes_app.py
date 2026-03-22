# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""KubernetesApp - Application class for building Kubernetes manifests.

Extends BagAppBase with multi-document YAML rendering.

Example:
    from genro_kubernetes import KubernetesApp

    class MyManifest(KubernetesApp):
        def recipe(self, root):
            dep = root.deployment(name="api", image="myapp:latest", replicas=3)
            c = dep.container(name="api", image="myapp:latest")
            c.port(container_port=8080)

            svc = root.service(name="api")
            svc.service_port(port=80, target_port=8080)

    app = MyManifest()
    print(app.to_yaml())
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml
from genro_builders import BagAppBase

from .builders.kubernetes_builder import KubernetesBuilder
from .kubernetes_compiler import KubernetesCompiler

if TYPE_CHECKING:
    from genro_bag import Bag


class KubernetesApp(BagAppBase):
    """Base class for Kubernetes manifest applications.

    Subclass and override recipe(root) to define your manifests.
    Call to_yaml() to generate multi-document YAML output.
    """

    builder_class = KubernetesBuilder
    compiler_class = KubernetesCompiler

    def __init__(self, name: str = "manifest",
                 output: str | Path | None = None,
                 data: Bag | dict[str, Any] | None = None) -> None:
        self._name = name
        self._file_output = Path(output) if output else None
        super().__init__()
        if data is not None:
            self.data = data
        self.setup()

    @property
    def root(self) -> Any:
        """The manifest root BagNode."""
        return self._root

    @property
    def file_output(self) -> Path | None:
        """The output file path for auto-save."""
        return self._file_output

    @file_output.setter
    def file_output(self, value: str | Path | None) -> None:
        self._file_output = Path(value) if value else None

    def setup(self) -> None:
        """Create root node, run recipe, compile, enable auto-compile."""
        self._root = self.store.manifest(name=self._name)
        self.recipe(self._root)
        self.compile()
        self._auto_compile = True

    def recipe(self, root: Any) -> None:
        """Override to build your Kubernetes manifests.

        Use ^ prefix on attribute values to reference self.data paths.
        """

    def render(self, compiled_bag: Bag) -> str:
        """Render compiled Bag to multi-document YAML."""
        compiler = KubernetesCompiler()
        root_nodes = list(compiled_bag)
        if not root_nodes:
            return ""
        yaml_dict = compiler.compile_to_dict(root_nodes[0], self.store.builder)
        resources = compiler.to_multi_document(yaml_dict)

        if not resources:
            return ""

        documents = []
        for resource in resources:
            doc = yaml.dump(
                resource,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )
            documents.append(doc)

        return "---\n".join(documents)

    def to_yaml(self, destination: str | Path | None = None) -> str:
        """Compile to multi-document YAML and optionally write to file.

        Returns:
            YAML string with --- separators between resources.
        """
        self.compile()
        yaml_str = self.output or ""
        dest = destination or self._file_output
        if dest:
            Path(dest).write_text(yaml_str, encoding="utf-8")
        return yaml_str

    def _on_node_updated(self, node: Any) -> None:
        """Called by BindingManager when a bound node is updated."""
        if self._auto_compile:
            self._rerender()
            if self._file_output:
                self.to_yaml()
