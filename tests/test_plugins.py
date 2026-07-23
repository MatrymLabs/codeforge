"""Test twin for parts/plugins.py -- the third-party command plugin loader.

Acceptance: a well-formed plugin registers its SEED command onto the spine. Refusal (the whole point
of a plugin boundary): a plugin that claims a CORE/ADMIN verb, collides with a built-in or another
plugin, lacks the hook, raises, or returns a non-Command is REJECTED and named -- never silently
loaded, and never bricking the others. Edge: a missing plugins dir loads nothing; _-prefixed files
and non-.py files are ignored.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.commands import CORE, Command, CommandSet
from parts.plugins import PluginLoad, load_plugins, render_plugins

# A minimal valid plugin: one SEED command.
_GOOD = """
from parts.commands import Command


def _dance(session, arg):
    return "You dance a jig."


def register():
    return [Command("dance", "PLG-001", "dance a jig", _dance)]
"""


def _write_plugin(plugins_dir: Path, name: str, source: str) -> None:
    plugins_dir.mkdir(parents=True, exist_ok=True)
    (plugins_dir / f"{name}.py").write_text(source)


def _look(session, arg):
    return "You look around."


def test_a_wellformed_plugin_registers_its_command(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "dancer", _GOOD)
    spine = CommandSet()
    load = load_plugins(spine, plugins)
    assert load.loaded == ("dancer",) and load.commands == ("dance",) and load.errors == ()
    assert "dance" in {c.verb for c in spine.commands}  # actually on the spine now


def test_a_plugin_claiming_a_nonseed_namespace_is_rejected(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(
        plugins,
        "sneaky",
        "from parts.commands import Command\n"
        "def register():\n"
        '    return [Command("look", "PLG-X", "shadow", lambda s, a: "x", namespace="core")]\n',
    )
    spine = CommandSet()
    load = load_plugins(spine, plugins)
    assert load.loaded == () and "must be SEED namespace" in load.errors[0]
    assert "look" not in {c.verb for c in spine.commands}  # never reached the spine


def test_a_plugin_colliding_with_a_builtin_is_rejected(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(
        plugins,
        "clash",
        "from parts.commands import Command\n"
        "def register():\n"
        '    return [Command("look", "PLG-Y", "collide", lambda s, a: "x")]\n',
    )
    spine = CommandSet()
    spine.add(Command("look", "CMD-CORE", "the built-in look", _look, namespace=CORE))
    load = load_plugins(spine, plugins)
    assert load.loaded == () and "collides" in load.errors[0]


def test_two_plugins_claiming_the_same_verb_second_is_rejected(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "a_first", _GOOD)  # registers 'dance'
    _write_plugin(
        plugins,
        "b_second",
        "from parts.commands import Command\n"
        "def register():\n"
        '    return [Command("dance", "PLG-Z", "a second dance", lambda s, a: "x")]\n',
    )
    spine = CommandSet()
    load = load_plugins(spine, plugins)
    assert load.loaded == ("a_first",)  # sorted: a_first wins the verb
    assert any("b_second" in e and "collides" in e for e in load.errors)


def test_a_plugin_without_the_hook_is_rejected(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "hookless", "X = 1\n")  # no register()
    load = load_plugins(CommandSet(), plugins)
    assert load.loaded == () and "no register() hook" in load.errors[0]


def test_a_plugin_whose_hook_raises_is_rejected(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "boomer", "def register():\n    raise RuntimeError('boom')\n")
    load = load_plugins(CommandSet(), plugins)
    assert load.loaded == () and "register() raised: boom" in load.errors[0]


def test_a_plugin_returning_non_commands_is_rejected(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "junk", "def register():\n    return ['not a command']\n")
    load = load_plugins(CommandSet(), plugins)
    assert load.loaded == () and "must return Command objects" in load.errors[0]


def test_an_unimportable_plugin_is_rejected_without_bricking_others(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "a_broken", "def register(:\n")  # syntax error
    _write_plugin(plugins, "b_good", _GOOD)
    spine = CommandSet()
    load = load_plugins(spine, plugins)
    assert load.loaded == ("b_good",)  # the good one still loaded
    assert any("a_broken" in e and "import failed" in e for e in load.errors)


def test_a_missing_plugins_dir_loads_nothing(tmp_path: Path) -> None:
    load = load_plugins(CommandSet(), tmp_path / "no_such_dir")
    assert load == PluginLoad((), (), ())


def test_underscore_and_non_py_files_are_ignored(tmp_path: Path) -> None:
    plugins = tmp_path / "plugins"
    _write_plugin(plugins, "_private", _GOOD)  # _-prefixed: skipped
    plugins.mkdir(parents=True, exist_ok=True)
    (plugins / "README.md").write_text("not a plugin")
    load = load_plugins(CommandSet(), plugins)
    assert load.loaded == () and load.errors == ()


def test_import_module_fails_loud_when_no_spec(tmp_path: Path, monkeypatch) -> None:
    import parts.plugins as pl

    monkeypatch.setattr(pl.importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(ImportError, match="cannot build an import spec"):
        pl._import_module(tmp_path / "x.py")


def test_render_plugins_names_loaded_and_rejected() -> None:
    load = PluginLoad(
        ("dancer",), ("dance",), ("sneaky: command 'look' collides with an existing verb",)
    )
    out = render_plugins(load)
    assert "loaded (1): dancer" in out and "verbs added (1): dance" in out
    assert "rejected (1):" in out and "sneaky:" in out
    clean = render_plugins(PluginLoad((), (), ()))
    assert "loaded: none" in clean and "rejected: none" in clean
