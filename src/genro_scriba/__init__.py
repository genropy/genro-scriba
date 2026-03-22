# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""genro-scriba: Infrastructure configuration file generator.

Install individual builders or everything:
    pip install genro-scriba          # all builders
    pip install genro-scriba[traefik] # only Traefik
    pip install genro-scriba[compose] # only Docker Compose
    pip install genro-traefik         # standalone
    pip install genro-compose         # standalone
"""

__version__ = "0.1.0"

from .app import ScribaApp
from .artifact_hub import ArtifactHub, ArtifactHubResolver
from .yaml_compiler import YamlCompilerBase

CompilerBase = YamlCompilerBase

__all__ = [
    "ArtifactHub",
    "ArtifactHubResolver",
    "CompilerBase",
    "ScribaApp",
    "YamlCompilerBase",
    "__version__",
]
