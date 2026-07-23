# Keel Record: Typed event frames (the room bus, per-recipient)

*Human Keel Record (see [../human_keel_doctrine.md](../human_keel_doctrine.md)). This documents a
critical-junction design decision and its first build slice. Per the doctrine, AI proposes and Josh
approves; **AI does not assign ownership**. The level-4 ownership claim and the "what I learned"
reflection below are left for Josh to complete when he can defend the design to an interviewer.*

- **Build:** typed event frames for the room bus (`parts/frames.py` + `events.announce_frame`), the
  `say` verb migrated as the first call site.
- **Ownership level claimed:** *(pending Josh's own claim; undeclared until he defends it)*

## Intent
Begin turning the in-world event bus from a string broadcaster into the "validated event frames that
sinks render per-recipient" its own docstring promised. Today `announce(room, text)` bakes one line
for the whole room; a Frame carries structured fields so each sink renders for its own viewer (name,
tense, locale decided at delivery, not frozen at the call site). This is M5 (the engine climb),
slice "typed event frames."

## Problem
The room bus payload is an untyped `str`, pre-rendered once. There is nothing to validate, nothing to
route on, and no seam for per-viewer rendering. Naively this invites either a big-bang rewrite of the
whole broadcast layer or bolting per-recipient logic onto every call site. The problem was to
introduce typed, validated, per-recipient frames as real infrastructure without rewriting the bus.

## Constraints
- Smallest useful slice: one new frame kind, one new delivery function, one migrated verb. The string
  `announce`/`broadcast` path stays intact for every other call site.
- Behavior preserved: the bystander line for `say` is byte-identical to the old output, so the
  existing tick test passes unchanged.
- Transport contract untouched: `EchoSink = Callable[[str], None]` is unchanged, so the three
  surfaces (terminal `print`, TCP `_send`, web `outbox`) are not touched. Rendering happens in the
  announce layer, before the sink.
- Architecture laws honored: a Frame is a projection request, never a mutation; state stays canonical.
- Frameless / stdlib-first: a frozen dataclass that validates on construction and fails loud.
- Critical-junction rule: changing a core broadcast contract stops for a keel decision before code.

## Decision
Approved (pilot on `say` only). Add a frozen `Frame` marker base with a `render_for(viewer_id)`
method and one concrete `SpeechFrame(speaker_id, words)`; add `events.announce_frame(room, frame,
exclude)` that renders per recipient; migrate the `say` verb to emit a `SpeechFrame`. Everything else
keeps the string bus. This proves the typed frame + per-recipient seam and leaves a documented
migration path for the next verbs.

## Alternatives considered
- **Big-bang: migrate every `announce` call site + change the sink signature to accept frames.**
  Rejected: a rewrite of a core system across three transports; large blast radius, against the
  ship's "a refactor is a rename, not a rewrite" rule.
- **Base the frames on `parts/shelf/signal_bus.py` (the general typed pub/sub).** Considered and deferred:
  it would couple the in-world echo bus to the general bus; the two are deliberately distinct today.
  Revisit if a later slice wants routing/subscription semantics.
- **Render per-recipient inside each sink (push frames all the way to the transport).** Deferred:
  that changes `EchoSink`'s type and every transport. Keeping rendering in `announce_frame` gets the
  per-viewer seam now with zero transport churn; frames-to-the-sink can come later on evidence.

## AI contribution
AI-assisted implementation of `parts/frames.py` (`Frame`, `SpeechFrame`, `render_for`, the loud
`__post_init__` validator), `events.announce_frame`, the `say`-verb migration in `forge.py`, the test
twin `tests/test_frames.py` (acceptance + hostile refusal: empty/blank words, empty speaker, frozen,
base-frame refusal) and the `announce_frame` delivery test in `tests/test_events.py`, the Classification
Registry filing `MOD-04.047`, and this record.

## Human modification (the keel)
Josh directed the M5 engine climb, chose typed event frames as the active slice (after the scout
found the originally-planned "NPCs that fight back" already shipped), and approved the pilot-on-`say`
scope over the broader options. He holds the keel decisions: that the bus should evolve toward typed
per-recipient frames, the smallest-safe scope, and the acceptance bar (behavior preserved, blast
radius minimal).

## Tests / evidence
- `parts/frames.py` at 100% coverage; `tests/test_frames.py` (7 tests) + the `announce_frame`
  per-recipient/exclusion test in `tests/test_events.py`; the existing `say` tick test
  (`test_say_is_heard_by_the_room`) passes unchanged, proving behavior preserved through the frame path.
- `make check` green: ruff + mypy --strict (296 files) + 1457 passed, coverage 93.56% >= 85% gate.
- Registry completeness CLEAN: `unfiled_modules()` and `untwinned_modules()` both empty (frames filed
  as `MOD-04.047`, twinned by `tests/test_frames.py`).

## What Josh learned
*(For Josh to complete - the doctrine requires a human act beyond approval before a level-4 claim:
explain why rendering moved to `announce_frame` instead of the sink, trace a `say` from the verb to a
bystander's line, or name the failure mode the empty-words refusal guards.)*

## Final decision
Josh's, at the merge junction and of this record. The level-4 ownership claim is his to make on the
Career Board when he can defend the design; AI leaves it undeclared here.

## Uncertainty / review point
The pilot leaves every other broadcast on the string bus by design; the next slices migrate more
verbs (movement, combat) to frames, and only then is pushing frames all the way to the sink (a
transport-contract change) worth weighing. `render_for` ignores `viewer_id` today; that parameter is
the seam a future viewer-specific projection (perspective, locale) will use.
