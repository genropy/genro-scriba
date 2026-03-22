# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""genro-ansible: Ansible playbook builder for Genropy.

Generates validated Ansible playbook YAML using the genro-bag builder system.
The builder IS the documentation — every @element docstring is an encyclopedic
reference for the corresponding Ansible concept.

Example:
    ```python
    from genro_ansible import AnsibleApp

    class ServerSetup(AnsibleApp):
        def recipe(self, root):
            play = root.play(name="Setup", hosts="all", become=True)
            play.task(name="Install nginx", module="apt",
                      args={"name": "nginx", "state": "present"})

    app = ServerSetup()
    print(app.to_yaml())
    ```
"""

__version__ = "0.1.0"

from .ansible_app import AnsibleApp
from .builders.ansible_builder import AnsibleBuilder

__all__ = [
    "AnsibleApp",
    "AnsibleBuilder",
    "__version__",
]
