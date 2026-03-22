# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Server setup — Ansible playbook for web server provisioning.

Module arguments use args_* parameters. Values prefixed with $
are Ansible variables (rendered as {{ var }} in YAML).

Run:
    PYTHONPATH=src python examples/server_setup/server_setup.py
"""

from __future__ import annotations

from pathlib import Path

from genro_ansible import AnsibleApp


class ServerSetup(AnsibleApp):
    """Production web server setup playbook."""

    def recipe(self, root):
        # Play 1: System setup
        sys_play = root.play(name="System setup", hosts="webservers",
                             become=True, gather_facts=True)
        sys_play.vars_section(data={
            "deploy_user": "deploy",
            "app_dir": "/opt/app",
        })

        sys_play.task(name="Update apt cache", module="apt",
                      args_update_cache=True, args_cache_valid_time=3600)
        sys_play.task(name="Install packages", module="apt",
                      args_name="$item", args_state="present",
                      loop=["nginx", "curl", "ufw", "python3-pip"])
        sys_play.task(name="Create deploy user", module="user",
                      args_name="$deploy_user",
                      args_shell="/bin/bash",
                      args_create_home=True)
        sys_play.task(name="Create app directory", module="file",
                      args_path="$app_dir",
                      args_state="directory",
                      args_owner="$deploy_user",
                      args_mode="0755")
        sys_play.task(name="Allow SSH", module="ufw",
                      args_rule="allow", args_port="22")
        sys_play.task(name="Allow HTTP", module="ufw",
                      args_rule="allow", args_port="80")
        sys_play.task(name="Allow HTTPS", module="ufw",
                      args_rule="allow", args_port="443")
        sys_play.task(name="Enable firewall", module="ufw",
                      args_state="enabled")

        # Play 2: Nginx configuration
        nginx_play = root.play(name="Configure nginx", hosts="webservers",
                               become=True)
        nginx_play.task(name="Copy nginx config", module="template",
                        args_src="nginx.conf.j2",
                        args_dest="/etc/nginx/sites-available/app",
                        notify="restart nginx")
        nginx_play.task(name="Enable site", module="file",
                        args_src="/etc/nginx/sites-available/app",
                        args_dest="/etc/nginx/sites-enabled/app",
                        args_state="link",
                        notify="restart nginx")
        nginx_play.handler(name="restart nginx", module="systemd",
                           args_name="nginx", args_state="restarted")


def main():
    app = ServerSetup()
    dest = Path(__file__).parent / "playbook.yml"
    yaml_str = app.to_yaml(destination=dest)
    print(yaml_str)


if __name__ == "__main__":
    main()
