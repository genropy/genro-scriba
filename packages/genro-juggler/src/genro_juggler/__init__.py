# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""genro-juggler: Reactive infrastructure bus.

Transforms genro-scriba from a file generator into a reactive bus
that applies changes directly to live targets (Kubernetes API,
ansible-runner) without intermediate YAML files.
"""

__version__ = "0.1.0"

from .juggler_app import JugglerApp

__all__ = ["JugglerApp", "__version__"]
