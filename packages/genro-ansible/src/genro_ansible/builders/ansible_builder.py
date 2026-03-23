# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""AnsibleBuilder - Ansible playbook as a semantic Bag builder.

Each @element defines an Ansible concept: playbook, play, task, handler,
vars. The task element covers ALL Ansible modules via flat args_* parameters.

Module arguments are passed as args_<param>=<value>:
    play.task(name="Install nginx", module="apt",
              args_name="nginx", args_state="present")

Values prefixed with $ are Ansible variables, rendered as {{ var }}:
    play.task(name="Create user", module="user",
              args_name="$deploy_user", args_shell="/bin/bash")
    # → user: {name: "{{ deploy_user }}", shell: /bin/bash}

Three prefix conventions:
    ^value  → genro-scriba pointer (resolved from data Bag at compile time)
    $value  → Ansible variable (rendered as {{ value }} in YAML)
    value   → literal (passed as-is)

Docs: https://docs.ansible.com/ansible/latest/playbook_guide/
"""

from __future__ import annotations

from typing import Any

from genro_builders import BagBuilderBase
from genro_builders.builder import element


class AnsibleBuilder(BagBuilderBase):
    """Ansible playbook grammar.

    Models Ansible playbooks with 5 elements: playbook, play, task,
    handler, vars_section. The task element covers ALL Ansible modules
    via flat args_* parameters.

    YAML output follows Ansible format: a list of plays (not a dict).

    Docs: https://docs.ansible.com/ansible/latest/playbook_guide/
    """

    # =================================================================
    # ROOT
    # =================================================================

    @element(sub_tags="play")
    def playbook(self, name: str = ""):
        """Ansible playbook — a list of plays to execute in order.

        A playbook is the top-level entry point. It contains one or more
        plays, each targeting a group of hosts.

        Docs: https://docs.ansible.com/ansible/latest/playbook_guide/
        """
        ...

    # =================================================================
    # PLAY
    # =================================================================

    @element(sub_tags="task, handler, vars_section")
    def play(self, name: str = "", hosts: str = "",
             become: bool = False, gather_facts: bool = True,
             vars: dict | None = None):
        """Play — a set of tasks executed on a group of hosts.

        A play maps a group of hosts to a list of tasks. It defines
        the execution context: which hosts, whether to use sudo (become),
        whether to gather system facts first.

        Args:
            name: Play description (shown during execution).
            hosts: Target hosts/group ("all", "webservers", "10.0.0.1").
            become: Run tasks with sudo (default: False).
            gather_facts: Collect system info before tasks (default: True).
            vars: Play-level variables as dict.

        Docs: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html
        """
        ...

    def compile_play(self, node: Any, result: dict[str, Any]) -> None:
        """Render a play as a dict in the _plays list."""
        name = node.attr.get("name", "")
        hosts = node.attr.get("hosts", "all")
        become = node.attr.get("become", False)
        gather_facts = node.attr.get("gather_facts", True)
        play_vars = node.attr.get("vars")

        play: dict[str, Any] = {"name": name, "hosts": hosts}

        if become:
            play["become"] = True
        if not gather_facts:
            play["gather_facts"] = False
        if play_vars:
            play["vars"] = play_vars

        from genro_bag import Bag
        node_value = node.get_value(static=True)
        if isinstance(node_value, Bag):
            tasks: list[dict[str, Any]] = []
            handlers: list[dict[str, Any]] = []

            for child in node_value:
                tag = child.node_tag or child.label
                if tag == "task":
                    tasks.append(_render_task(child))
                elif tag == "handler":
                    handlers.append(_render_task(child))
                elif tag == "vars_section":
                    data = child.attr.get("data")
                    if data:
                        play["vars"] = data

            if tasks:
                play["tasks"] = tasks
            if handlers:
                play["handlers"] = handlers

        result.setdefault("_plays", []).append(play)

    # =================================================================
    # TASK
    # =================================================================

    @element(sub_tags="")
    def task(self, name: str = "", module: str = "",
             when: str = "", register: str = "", notify: str = "",
             become: bool = False, loop: list | None = None,
             ignore_errors: bool = False):
        """Task — a single action to execute.

        A task calls one Ansible module with arguments. Tasks run in order.
        Each task should be idempotent — running it twice produces the
        same result.

        Module arguments are passed as args_<param>=<value> attributes.
        Values prefixed with $ are Ansible variables (rendered as {{ var }}).

        Example:
            play.task(name="Install nginx", module="apt",
                      args_name="nginx", args_state="present")

            play.task(name="Create user", module="user",
                      args_name="$deploy_user", args_shell="/bin/bash")
            # → user: {name: "{{ deploy_user }}", shell: /bin/bash}

        Common modules:
            apt:      args_name="nginx", args_state="present"
            copy:     args_src="file.conf", args_dest="/etc/file.conf"
            template: args_src="tmpl.j2", args_dest="/etc/app.conf"
            systemd:  args_name="nginx", args_state="started", args_enabled=True
            user:     args_name="deploy", args_shell="/bin/bash"
            file:     args_path="/data", args_state="directory", args_mode="0755"
            shell:    args_cmd="echo hello"

        Args:
            name: Task description (shown during execution).
            module: Ansible module name ("apt", "copy", "systemd", ...).
            when: Conditional expression ("ansible_os_family == 'Debian'").
            register: Save output to this variable name.
            notify: Handler name to trigger on change.
            become: Run this task with sudo (overrides play-level).
            loop: List to iterate over (task runs once per item).
            ignore_errors: Continue on failure (default: False).

        Additional args_* kwargs are passed as module arguments.

        Docs: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html#tasks-list
        """
        ...

    # =================================================================
    # HANDLER
    # =================================================================

    @element(sub_tags="")
    def handler(self, name: str = "", module: str = ""):
        """Handler — a task triggered by notify.

        Handlers run once at the end of a play, only if notified by a
        task that made a change. Typical use: restart a service after
        config changes.

        Module arguments are passed as args_* attributes, same as task().

        Example:
            play.handler(name="restart nginx", module="systemd",
                         args_name="nginx", args_state="restarted")

        Args:
            name: Handler name (must match the notify string in tasks).
            module: Ansible module name.

        Additional args_* kwargs are passed as module arguments.

        Docs: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_handlers.html
        """
        ...

    # =================================================================
    # VARS
    # =================================================================

    @element(sub_tags="")
    def vars_section(self, data: dict | None = None):
        """Variables section — key-value pairs for the play.

        Variables defined here are available to all tasks in the play.
        Use for values that change between environments.

        Args:
            data: Variables as dict {"key": "value"}.

        Docs: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_variables.html
        """
        ...


def _resolve_ansible_value(value: Any) -> Any:
    """Convert $variable references to {{ variable }} Jinja2 syntax."""
    if isinstance(value, str) and value.startswith("$"):
        return "{{ " + value[1:] + " }}"
    return value


def _collect_module_args(node: Any) -> dict[str, Any]:
    """Collect args_* attributes from a node into a module args dict."""
    args: dict[str, Any] = {}
    for attr_name, attr_value in node.attr.items():
        if attr_name.startswith("args_"):
            param_name = attr_name[5:]
            args[param_name] = _resolve_ansible_value(attr_value)
    return args


def _render_task(node: Any) -> dict[str, Any]:
    """Render a task or handler node to Ansible YAML dict format."""
    name = node.attr.get("name", "")
    module = node.attr.get("module", "")
    when = node.attr.get("when", "")
    register = node.attr.get("register", "")
    notify = node.attr.get("notify", "")
    become = node.attr.get("become", False)
    loop = node.attr.get("loop")
    ignore_errors = node.attr.get("ignore_errors", False)

    task_dict: dict[str, Any] = {"name": name}

    args = _collect_module_args(node)
    if module and args:
        task_dict[module] = args
    elif module:
        task_dict[module] = None

    if when:
        task_dict["when"] = _resolve_ansible_value(when)
    if register:
        task_dict["register"] = register
    if notify:
        task_dict["notify"] = notify
    if become:
        task_dict["become"] = True
    if loop:
        task_dict["loop"] = [_resolve_ansible_value(item) for item in loop]
    if ignore_errors:
        task_dict["ignore_errors"] = True

    return task_dict
