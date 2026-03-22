# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Build configuration sub-element for Docker Compose services.

The build section tells Compose how to build an image from source instead
of pulling a pre-built one. It maps to ``docker build`` options.

Docs: https://docs.docker.com/reference/compose-file/build/
"""

from __future__ import annotations

from genro_bag.builders import element

from ..compose_compiler import render_attrs


class BuildMixin:
    """Build configuration sub-element."""

    @element(sub_tags="")
    def build_config(self,
                     context: str = ".",
                     dockerfile: str = "",
                     dockerfile_inline: str = "",
                     target: str = "",
                     args: dict = "",
                     cache_from: list = "",
                     cache_to: list = "",
                     labels: dict = "",
                     network: str = "",
                     shm_size: str = "",
                     no_cache: bool = False,
                     pull: bool = False,
                     platforms: list = "",
                     secrets: list = "",
                     ssh: list = "",
                     extra_hosts: list = "",
                     privileged: bool = False,
                     tags: list = "",
                     outputs: list = ""):
        """Build configuration — how to build the service image.

        Use ``build_config`` when you want Compose to build the image from
        source instead of pulling it. You can combine ``build_config`` with
        ``image`` on the service: ``image`` names the resulting image,
        ``build_config`` defines how to build it.

        **Context**: The build context directory. Defaults to ``"."``.
        Docker sends this directory to the daemon for building.
        Use ``.dockerignore`` to exclude files.

        **Multi-stage builds**: Set ``target`` to build only up to a
        specific stage in a multi-stage Dockerfile. Common pattern:
        ``target="production"`` to skip dev/test stages.

        **Build arguments**: ``args`` are variables available during build
        (``ARG`` in Dockerfile). Use for versions, config values — never
        for secrets (use ``secrets`` instead).

        **Build secrets**: ``secrets`` grants access to sensitive data
        during build without baking it into the image. Uses BuildKit
        secret mounts.

        **Platforms**: ``platforms=["linux/amd64", "linux/arm64"]`` for
        multi-architecture builds using BuildKit.

        **Inline Dockerfile**: ``dockerfile_inline`` lets you define the
        Dockerfile content directly in the Compose file, without a
        separate file.

        Args:
            context: Build context directory or URL. Default: ".".
            dockerfile: Path to Dockerfile (relative to context).
            dockerfile_inline: Inline Dockerfile content (string).
            target: Target stage in multi-stage Dockerfile.
            args: Build arguments as dict {"KEY": "value"}.
            cache_from: Images to use as cache sources.
            cache_to: Cache export destinations.
            labels: Labels to apply to the built image.
            network: Network mode during build ("host", "none").
            shm_size: Size of /dev/shm during build (e.g. "256m").
            no_cache: Do not use cache when building.
            pull: Always pull base images before building.
            platforms: Target platforms for multi-arch build.
            secrets: Build secrets to expose during build.
            ssh: SSH agent forwarding during build.
            extra_hosts: Extra /etc/hosts entries during build.
            privileged: Enable privileged build (BuildKit).
            tags: Additional tags for the built image.
            outputs: Build output configuration.

        Docs: https://docs.docker.com/reference/compose-file/build/
        """
        ...

    def compile_build_config(self, node, result):
        result["build"] = render_attrs(node, self)
