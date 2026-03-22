# Copyright 2025 Softwell S.r.l. - Licensed under Apache License 2.0
# See LICENSE file for details

"""Tests for AnsibleBuilder compile_* methods and YAML output structure."""

from __future__ import annotations

import yaml
from genro_bag import Bag
from genro_builders import BuilderBag

from genro_ansible import AnsibleApp
from genro_ansible.ansible_compiler import AnsibleCompiler, compile_to_dict
from genro_ansible.builders.ansible_builder import AnsibleBuilder


def _build(recipe_fn) -> list[dict]:
    """Helper: create store, call recipe, compile, return play list."""
    store = BuilderBag(builder=AnsibleBuilder)
    store.builder.data = Bag()
    root = store.playbook(name="test")
    recipe_fn(root)
    yaml_dict = compile_to_dict(root, store.builder)
    return AnsibleCompiler().to_play_list(yaml_dict)


# =========================================================================
# PLAY
# =========================================================================


class TestPlay:

    def test_basic(self) -> None:
        def recipe(root):
            root.play(name="Setup", hosts="all")

        plays = _build(recipe)
        assert len(plays) == 1
        assert plays[0]["name"] == "Setup"
        assert plays[0]["hosts"] == "all"

    def test_become(self) -> None:
        def recipe(root):
            root.play(name="Setup", hosts="all", become=True)

        play = _build(recipe)[0]
        assert play["become"] is True

    def test_gather_facts_disabled(self) -> None:
        def recipe(root):
            root.play(name="Quick", hosts="all", gather_facts=False)

        play = _build(recipe)[0]
        assert play["gather_facts"] is False

    def test_multiple_plays(self) -> None:
        def recipe(root):
            root.play(name="Play 1", hosts="webservers")
            root.play(name="Play 2", hosts="dbservers")

        plays = _build(recipe)
        assert len(plays) == 2
        assert plays[0]["hosts"] == "webservers"
        assert plays[1]["hosts"] == "dbservers"


# =========================================================================
# TASK
# =========================================================================


class TestTask:

    def test_basic(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Install nginx", module="apt",
                      args={"name": "nginx", "state": "present"})

        play = _build(recipe)[0]
        tasks = play["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["name"] == "Install nginx"
        assert tasks[0]["apt"] == {"name": "nginx", "state": "present"}

    def test_multiple_tasks(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Install nginx", module="apt",
                      args={"name": "nginx", "state": "present"})
            play.task(name="Start nginx", module="systemd",
                      args={"name": "nginx", "state": "started", "enabled": True})

        play = _build(recipe)[0]
        assert len(play["tasks"]) == 2
        assert play["tasks"][1]["systemd"]["enabled"] is True

    def test_when_condition(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Install apt pkg", module="apt",
                      args={"name": "nginx"},
                      when="ansible_os_family == 'Debian'")

        task = _build(recipe)[0]["tasks"][0]
        assert task["when"] == "ansible_os_family == 'Debian'"

    def test_register(self) -> None:
        def recipe(root):
            play = root.play(name="Check", hosts="all")
            play.task(name="Check file", module="stat",
                      args={"path": "/etc/nginx/nginx.conf"},
                      register="nginx_conf")

        task = _build(recipe)[0]["tasks"][0]
        assert task["register"] == "nginx_conf"

    def test_notify(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Copy config", module="copy",
                      args={"src": "nginx.conf", "dest": "/etc/nginx/nginx.conf"},
                      notify="restart nginx")

        task = _build(recipe)[0]["tasks"][0]
        assert task["notify"] == "restart nginx"

    def test_become_override(self) -> None:
        def recipe(root):
            play = root.play(name="Mixed", hosts="all")
            play.task(name="Root task", module="apt",
                      args={"name": "nginx"}, become=True)

        task = _build(recipe)[0]["tasks"][0]
        assert task["become"] is True

    def test_loop(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Install packages", module="apt",
                      args={"name": "{{ item }}", "state": "present"},
                      loop=["nginx", "curl", "vim"])

        task = _build(recipe)[0]["tasks"][0]
        assert task["loop"] == ["nginx", "curl", "vim"]

    def test_ignore_errors(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Try something", module="shell",
                      args={"cmd": "test -f /opt/app"},
                      ignore_errors=True)

        task = _build(recipe)[0]["tasks"][0]
        assert task["ignore_errors"] is True

    def test_module_without_args(self) -> None:
        def recipe(root):
            play = root.play(name="Check", hosts="all")
            play.task(name="Gather facts", module="setup")

        task = _build(recipe)[0]["tasks"][0]
        assert task["setup"] is None


# =========================================================================
# HANDLER
# =========================================================================


class TestHandler:

    def test_basic(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.task(name="Copy config", module="copy",
                      args={"src": "nginx.conf", "dest": "/etc/nginx/nginx.conf"},
                      notify="restart nginx")
            play.handler(name="restart nginx", module="systemd",
                         args={"name": "nginx", "state": "restarted"})

        play = _build(recipe)[0]
        assert "handlers" in play
        assert len(play["handlers"]) == 1
        handler = play["handlers"][0]
        assert handler["name"] == "restart nginx"
        assert handler["systemd"]["state"] == "restarted"


# =========================================================================
# VARS
# =========================================================================


class TestVars:

    def test_vars_section(self) -> None:
        def recipe(root):
            play = root.play(name="Setup", hosts="all")
            play.vars_section(data={"http_port": 80, "max_clients": 200})
            play.task(name="Use var", module="debug",
                      args={"msg": "Port is {{ http_port }}"})

        play = _build(recipe)[0]
        assert play["vars"]["http_port"] == 80
        assert play["vars"]["max_clients"] == 200

    def test_play_vars_parameter(self) -> None:
        def recipe(root):
            root.play(name="Setup", hosts="all",
                      vars={"env": "production"})

        play = _build(recipe)[0]
        assert play["vars"]["env"] == "production"


# =========================================================================
# APP
# =========================================================================


class TestAnsibleApp:

    def test_produces_valid_yaml(self) -> None:
        class MyPlaybook(AnsibleApp):
            def recipe(self, root):
                play = root.play(name="Setup", hosts="all", become=True)
                play.task(name="Install nginx", module="apt",
                          args={"name": "nginx", "state": "present"})

        app = MyPlaybook()
        yaml_str = app.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["name"] == "Setup"
        assert parsed[0]["tasks"][0]["apt"]["name"] == "nginx"

    def test_multi_play(self) -> None:
        class MultiPlay(AnsibleApp):
            def recipe(self, root):
                p1 = root.play(name="Setup web", hosts="webservers", become=True)
                p1.task(name="Install nginx", module="apt",
                        args={"name": "nginx", "state": "present"})

                p2 = root.play(name="Setup db", hosts="dbservers", become=True)
                p2.task(name="Install postgres", module="apt",
                        args={"name": "postgresql", "state": "present"})

        app = MultiPlay()
        yaml_str = app.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        assert len(parsed) == 2
        assert parsed[0]["hosts"] == "webservers"
        assert parsed[1]["hosts"] == "dbservers"

    def test_complete_playbook(self) -> None:
        class ServerSetup(AnsibleApp):
            def recipe(self, root):
                play = root.play(name="Configure server", hosts="all",
                                 become=True, gather_facts=True)
                play.vars_section(data={"http_port": 80})
                play.task(name="Install packages", module="apt",
                          args={"name": "{{ item }}", "state": "present"},
                          loop=["nginx", "curl"])
                play.task(name="Copy config", module="template",
                          args={"src": "nginx.conf.j2",
                                "dest": "/etc/nginx/nginx.conf"},
                          notify="restart nginx")
                play.handler(name="restart nginx", module="systemd",
                             args={"name": "nginx", "state": "restarted"})

        app = ServerSetup()
        yaml_str = app.to_yaml()
        parsed = yaml.safe_load(yaml_str)
        play = parsed[0]
        assert play["become"] is True
        assert play["vars"]["http_port"] == 80
        assert len(play["tasks"]) == 2
        assert play["tasks"][0]["loop"] == ["nginx", "curl"]
        assert play["tasks"][1]["notify"] == "restart nginx"
        assert play["handlers"][0]["systemd"]["state"] == "restarted"
