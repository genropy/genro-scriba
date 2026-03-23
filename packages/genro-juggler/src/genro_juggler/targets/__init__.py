# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

from .base import TargetBase
from .file_target import FileTarget

__all__ = ["FileTarget", "TargetBase"]

# Conditional imports for optional targets
try:
    from .kubernetes_target import K8sTarget  # noqa: F401
    __all__.append("K8sTarget")
except ImportError:
    pass

try:
    from .ansible_target import AnsibleTarget  # noqa: F401
    __all__.append("AnsibleTarget")
except ImportError:
    pass
