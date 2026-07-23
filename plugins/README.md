# Command plugins

Drop a Python module here to add gameplay verbs **without touching the engine**. At boot,
`parts/plugins.py` scans this directory, imports each module, calls its `register()` hook, and
validates what it returns before anything reaches the command spine.

A plugin is a module exposing `register() -> list[Command]`:

```python
# plugins/dancer.py
from parts.commands import Command


def _dance(session, arg):
    return "You dance a jig."


def register():
    return [Command("dance", "PLG-001", "dance a jig", _dance)]
```

## The rules (enforced, not trusted)

- **SEED namespace only.** A plugin can never own a reserved `CORE` word (look, go, say, ...) or an
  `@`-sigil `ADMIN` verb. The command spine refuses it by construction, and the loader rejects it.
- **No verb collision.** A verb that clashes with a built-in or another plugin is rejected.
- **Atomic.** If any of a plugin's commands fail validation, none of them are registered.
- **Loud, never silent.** A plugin that fails to import, lacks `register()`, raises, or contributes a
  bad command is named in the load report and skipped. One broken plugin never bricks the engine.

Run `make plugins` to see what loaded and what (if anything) was rejected.

This directory ships empty: the plugin system is dormant until you add a module.
