# Getting Started

## Installation

```bash
pip install genro-ansible
```

## Your First Playbook

```python
from genro_ansible import AnsibleApp

class Setup(AnsibleApp):
    def recipe(self, root):
        play = root.play(name="Configure web servers", hosts="all", become=True)

        play.task(name="Update apt cache", module="apt",
                  args_update_cache=True, args_cache_valid_time=3600)

        play.task(name="Install packages", module="apt",
                  args_name="nginx,certbot", args_state="present")

        play.task(name="Enable nginx", module="systemd",
                  args_name="nginx", args_state="started", args_enabled=True)

app = Setup()
print(app.to_yaml())
```

## Task Arguments

Module arguments use the `args_*` prefix. The prefix is stripped in YAML:

```python
# Python
play.task(name="Install", module="apt", args_name="nginx", args_state="present")

# Produces YAML
# - name: Install
#   apt:
#     name: nginx
#     state: present
```

## Ansible Variables

Use `$` prefix for Ansible variables (converted to `{{ }}` in YAML):

```python
play.task(name="Copy config", module="template",
          args_src="nginx.conf.j2", args_dest="/etc/nginx/nginx.conf",
          args_owner="$nginx_user")
# → owner: "{{ nginx_user }}"
```

## Data Pointers

Use `^path` to parameterize from the data Bag:

```python
class Setup(AnsibleApp):
    def recipe(self, root):
        play = root.play(name="Setup", hosts="^target", become=True)

app = Setup(data={"target": "production-servers"})
```

---

**Next:** [API Reference](reference/ansible-app)
