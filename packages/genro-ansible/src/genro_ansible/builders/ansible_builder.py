# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""AnsibleBuilder - Ansible playbook as a semantic Bag builder.

Each @element defines an Ansible concept: playbook, play, task, handler,
vars. The task element uses a generic module + args approach that covers
ALL Ansible modules with a single element.

The builder IS the documentation — every @element docstring is an encyclopedic
reference for the corresponding Ansible concept. Reading the builder teaches
Ansible.

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
    via generic module + args parameters.

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

        # Collect children: tasks, handlers, vars_section
        from genro_bag import Bag
        node_value = node.get_value(static=True)
        if isinstance(node_value, Bag):
            tasks: list[dict[str, Any]] = []
            handlers: list[dict[str, Any]] = []

            for child in node_value:
                tag = child.tag or child.label
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
             args: dict | None = None,
             when: str = "", register: str = "", notify: str = "",
             become: bool = False, loop: list | None = None,
             ignore_errors: bool = False):
        """Task — a single action to execute.

        A task calls one Ansible module with arguments. Tasks run in order.
        Each task should be idempotent — running it twice produces the
        same result.

        The module is specified as a string name. Arguments are a dict
        passed directly to the module. This covers ALL Ansible modules.

        Common modules:
            apt:             {"name": "nginx", "state": "present"}
            copy:            {"src": "file.conf", "dest": "/etc/file.conf"}
            template:        {"src": "tmpl.j2", "dest": "/etc/app.conf"}
            service/systemd: {"name": "nginx", "state": "started", "enabled": True}
            user:            {"name": "deploy", "shell": "/bin/bash"}
            file:            {"path": "/data", "state": "directory", "mode": "0755"}
            shell:           {"cmd": "echo hello"}
            authorized_key:  {"user": "deploy", "key": "ssh-rsa ..."}

        Args:
            name: Task description (shown during execution).
            module: Ansible module name ("apt", "copy", "systemd", ...).
            args: Module arguments as dict.
            when: Conditional expression ("ansible_os_family == 'Debian'").
            register: Save output to this variable name.
            notify: Handler name to trigger on change.
            become: Run this task with sudo (overrides play-level).
            loop: List to iterate over (task runs once per item).
            ignore_errors: Continue on failure (default: False).

        Docs: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_intro.html#tasks-list
        """
        ...

    # =================================================================
    # HANDLER
    # =================================================================

    @element(sub_tags="")
    def handler(self, name: str = "", module: str = "",
                args: dict | None = None):
        """Handler — a task triggered by notify.

        Handlers run once at the end of a play, only if notified by a
        task that made a change. Typical use: restart a service after
        config changes.

        Example: a task installs nginx.conf with notify="restart nginx".
        The handler "restart nginx" runs systemd restart once, even if
        multiple tasks notified it.

        Args:
            name: Handler name (must match the notify string in tasks).
            module: Ansible module name.
            args: Module arguments as dict.

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


def _render_task(node: Any) -> dict[str, Any]:
    """Render a task or handler node to Ansible YAML dict format."""
    name = node.attr.get("name", "")
    module = node.attr.get("module", "")
    args = node.attr.get("args")
    when = node.attr.get("when", "")
    register = node.attr.get("register", "")
    notify = node.attr.get("notify", "")
    become = node.attr.get("become", False)
    loop = node.attr.get("loop")
    ignore_errors = node.attr.get("ignore_errors", False)

    task_dict: dict[str, Any] = {"name": name}

    if module and args:
        task_dict[module] = args
    elif module:
        task_dict[module] = None

    if when:
        task_dict["when"] = when
    if register:
        task_dict["register"] = register
    if notify:
        task_dict["notify"] = notify
    if become:
        task_dict["become"] = True
    if loop:
        task_dict["loop"] = loop
    if ignore_errors:
        task_dict["ignore_errors"] = True

    return task_dict
