# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

from .base import TargetBase
from .file_target import FileTarget
from .mock_ansible import MockAnsibleTarget
from .mock_kubernetes import MockK8sTarget

__all__ = ["FileTarget", "MockAnsibleTarget", "MockK8sTarget", "TargetBase"]

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
