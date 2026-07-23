"""CARD: plugins -- discover and register third-party command plugins from a plugins/ directory.

The command spine (parts/commands.py) is the seam: a `Command` is data + a handler, and the spine
gates verbs by namespace (CORE / ADMIN / SEED) by construction. A plugin extends the engine WITHOUT
touching its code: it is a module in a plugins/ dir exposing a `register()` hook that returns
the `Command` objects it contributes. This Loader scans that directory, imports each module, calls
its hook, and VALIDATES the contribution before it touches the spine:

  - SEED namespace only: a plugin can never own a reserved CORE word or an ADMIN '@'-verb.
  - no verb collision with a built-in or another plugin.
  - atomic: a plugin whose commands don't all validate adds none of them.

A plugin that fails to import, lacks the hook, or contributes a bad/colliding command is recorded as
a loud error and SKIPPED -- one broken third-party plugin never bricks the engine, and no failure is
silent (every rejection is named in PluginLoad.errors). Reads + registers; writes nothing to disk.
"""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from parts.commands import SEED, Command, CommandSet

PLUGIN_HOOK = "register"  # a plugin module exposes `register() -> list[Command]`
_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_DIR = _ROOT / "plugins"  # the default discovery location (absent by default -> no plugins)


@dataclass(frozen=True)
class PluginLoad:
    """A discovery pass result: what registered, the verbs added, and every rejection named."""

    loaded: tuple[str, ...]  # plugin module names successfully registered
    commands: tuple[str, ...]  # the verbs they contributed, in registration order
    errors: tuple[str, ...]  # "<plugin>: <reason>" for each rejected plugin (never silent)


def _import_module(path: Path):
    """Import a plugin module from its file path, isolated under a codeforge_plugin_ name."""
    spec = importlib.util.spec_from_file_location(f"codeforge_plugin_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot build an import spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _reject(commands: list, existing: set[str], claimed: list[str]) -> str | None:
    """The first reason these commands are unacceptable, or None if the whole batch is clean."""
    for cmd in commands:
        if not isinstance(cmd, Command):
            return f"{PLUGIN_HOOK}() must return Command objects, got {type(cmd).__name__}"
        if cmd.namespace != SEED:
            return f"command '{cmd.verb}' must be SEED namespace, not '{cmd.namespace}'"
        if cmd.verb in existing or cmd.verb in claimed:
            return f"command '{cmd.verb}' collides with an existing verb"
    return None


def load_plugins(
    spine: CommandSet, plugins_dir: Path | str | None = None, *, importer=_import_module
) -> PluginLoad:
    """Discover, validate, and register the plugins under `plugins_dir` onto `spine` (in place).

    A missing directory registers nothing (the system is dormant until a plugins/ dir appears). Each
    plugin is validated atomically before any of its commands touch the spine; a rejected plugin is
    named in the result's errors and skipped. `importer` is the injectable seam so tests load real
    plugin modules from a tmp dir without packaging."""
    base = Path(plugins_dir) if plugins_dir is not None else PLUGINS_DIR
    if not base.is_dir():
        return PluginLoad((), (), ())
    existing = {c.verb for c in spine.commands}
    loaded: list[str] = []
    added: list[str] = []
    errors: list[str] = []
    for path in sorted(base.glob("*.py")):
        if path.stem.startswith("_"):
            continue
        name = path.stem
        try:
            module = importer(path)
        except Exception as exc:  # a broken plugin never bricks the engine; the error is recorded
            errors.append(f"{name}: import failed: {exc}")
            continue
        hook = getattr(module, PLUGIN_HOOK, None)
        if not callable(hook):
            errors.append(f"{name}: no {PLUGIN_HOOK}() hook")
            continue
        try:
            provided = list(hook())
        except Exception as exc:
            errors.append(f"{name}: {PLUGIN_HOOK}() raised: {exc}")
            continue
        reason = _reject(provided, existing, added)
        if reason is not None:
            errors.append(f"{name}: {reason}")
            continue
        for cmd in provided:
            spine.add(cmd)
            added.append(cmd.verb)
        loaded.append(name)
    return PluginLoad(tuple(loaded), tuple(added), tuple(errors))


def render_plugins(load: PluginLoad) -> str:
    """A human-readable load summary: what registered, and every rejection (loud, never hidden)."""
    lines = ["Plugins", "=" * 7, ""]
    if load.loaded:
        lines.append(f"  loaded ({len(load.loaded)}): {', '.join(load.loaded)}")
        lines.append(f"  verbs added ({len(load.commands)}): {', '.join(load.commands)}")
    else:
        lines.append("  loaded: none")
    lines.append("")
    if load.errors:
        lines.append(f"  rejected ({len(load.errors)}):")
        lines += [f"    - {e}" for e in load.errors]
    else:
        lines.append("  rejected: none")
    return "\n".join(lines)
