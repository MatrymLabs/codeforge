# The Blueprint renderer (the forge's planning spine)

A **Blueprint** is a software idea forged into a structured spec *before* any code: a
permanent label, a title, the intent, the requirements it must satisfy, and the tasks that
would build it. It is the first stage of the forge loop the project is growing toward
(`idea -> Blueprint -> requirements -> renderer -> preview -> test -> catalog -> proof`).

## The two parts

- **`parts/blueprint.py`** (MOD-UM10-S01-N001-015-R0) - the model, the fail-loud validator,
  the JSON record + Markdown twin writer, and the `blueprint` tick verb.
- **`parts/blueprint_render.py`** (MOD-UM10-S01-N001-016-R0) - the static HTML/CSS renderer.

## The data contract

A Blueprint is validated at the gate; every gap fails loud, early, and by name:

| Field | Rule |
|---|---|
| `blueprint_id` | required, `lowercase_snake_case` (a permanent, frozen identity) |
| `title` | required, non-empty |
| `intent` | required, non-empty (one line: what and why) |
| `requirements` | required, a list of non-empty strings, at least one |
| `tasks` | optional list of strings (a draft may not have tasks yet) |
| `stack` | optional mapping of `layer -> choice` |
| `status` | `draft` or `validated` (a VeritasGate label, never inflated) |

The **JSON record is canonical**; the Markdown twin and the HTML page are projections
(architecture law 1: text never mutates the record). Authored Blueprints live under
`blueprints/` (examples under `blueprints/examples/`); rendered HTML is **regenerable
evidence** under `reports/blueprints/` (git-ignored), so the source of truth stays the JSON.

## The tick verb

```
blueprint                 list every filed plan
blueprint list            (the same)
blueprint show <id>       print the plan as Markdown
blueprint render <id>     project it to a static HTML page under reports/blueprints/
```

Reachable through `handle_command` and pinned by an engine-tick test (a feature is not wired
until the tick proves it). The Architect NPC *advises* on a plan but never invents one - the
operator authors the Blueprint, so no autonomous-coding claim is made.

## Why frameless

The renderer uses stdlib `html.escape` + f-strings and inline CSS - no template engine, no
new dependency (the same approach as `parts/dashboard.py`). This keeps the architecture-first
identity intact (`docs/frameless_python.md`) while proving semantic HTML5 + responsive,
accessible CSS. Hostile Blueprint text is escaped, never injected (tested).

## What it is not (scope discipline)

Read-only rendering of operator-authored plans. It does not generate code, does not call an
LLM, and does not mutate world state. Code generation, a live GPT NPC brain, and MUD-driven
Blueprint authoring are later phases (see `docs/full_stack_forge_decision.md`).
