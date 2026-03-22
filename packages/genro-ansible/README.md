# genro-ansible

Ansible playbook builder for Genropy — validated YAML generation.

## Installation

```bash
pip install genro-ansible
```

## Quick Start

```python
from genro_ansible import AnsibleApp

class ServerSetup(AnsibleApp):
    def recipe(self, root):
        play = root.play(name="Setup web server", hosts="webservers", become=True)
        play.task(name="Install nginx", module="apt",
                  args={"name": "nginx", "state": "present"})
        play.task(name="Start nginx", module="systemd",
                  args={"name": "nginx", "state": "started", "enabled": True})

app = ServerSetup()
print(app.to_yaml())
```

## License

Apache License 2.0 — see LICENSE for details.
