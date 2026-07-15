# The Blueprint renderer (the forge's planning spine)

A **Blueprint** is a software idea forged into a structured spec *before* any code: a
permanent label, a title, the intent, the requirements it must satisfy, and the tasks that
would build it. It is the first stage of the forge loop the project is growing toward
(`idea -> Blueprint -> requirements -> renderer -> preview -> test -> catalog -> proof`).

## The two parts

- **`parts/blueprint.py`** (MOD-10.015) - the model, the fail-loud validator,
  the JSON record + Markdown twin writer, and the `blueprint` tick verb.
- **`parts/blueprint_render.py`** (MOD-10.016) - the static HTML/CSS renderer.

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
blueprint draft <idea>    draft a NEW plan from a freeform idea with Claude (AI, key-away)
```

Reachable through `handle_command` and pinned by an engine-tick test (a feature is not wired
until the tick proves it).

## Drafting with AI (schema-enforced, honest)

`parts/blueprint_ai.py` turns a freeform idea into a **structured** Blueprint using the
Anthropic Messages API's `messages.parse` with a Pydantic schema (`BlueprintDraft`). The model
fills a schema; it never emits free prose we parse by hand. The draft is then re-validated
through the **same loud gate** every human-authored Blueprint passes (`from_dict`), so an
invalid draft fails loud, and its `status` is always forced to `draft` (AI output is Tier-4 -
a human reviews before filing). No autonomous coding is claimed: it drafts a plan, it does not
write code.

Same seam discipline as the Architect: the Anthropic client is **injected**, so tests drive a
fake and never touch the network (CI runs with no key); codeforge core never imports
`anthropic`. `blueprint draft` is one API key away - offline it returns an honest "needs the
Claude Architect" message. See `docs/architect_brain.md`.

## Why frameless

The renderer uses stdlib `html.escape` + f-strings and inline CSS - no template engine, no
new dependency (the same approach as `parts/dashboard.py`). This keeps the architecture-first
identity intact (`docs/frameless_python.md`) while proving semantic HTML5 + responsive,
accessible CSS. Hostile Blueprint text is escaped, never injected (tested).

## What it is not (scope discipline)

Read-only rendering of operator-authored plans. It does not generate code, does not call an
LLM, and does not mutate world state. Code generation, a live GPT NPC brain, and MUD-driven
Blueprint authoring are later phases (see `docs/full_stack_forge_decision.md`).
