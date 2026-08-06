# Aethryn Help and Discoverability

`help` is generated from the authoritative command registry. `help <topic>` explains the concept;
`help <command>` explains syntax, target rules, permissions, side effects, errors, and examples;
`commands [category]` lists available commands in context; `syntax <command>` is the terse form.

Every error follows: what happened, why, next action. Examples:

```
You cannot use Hold the Line: it costs 2 MP, but you have 1 MP.
Try: rest, or use another technique.
```

```
Which guard do you mean?
  1. guard captain
  2. guard novice
Use `examine guard 1` or type the full name.
```

First-use hints are per-command/per-character and dismissible. Repeated hints are suppressed after
success or `settings hints off`. Contextual suggestions are never the only way to discover a
command. Help output has a linear mode and every Master Client action links to its text command.

