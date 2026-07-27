# The Creator Experience

CodeForge is meant for creators, not only programmers. The Creator Experience is the system that
lets someone with a story to tell build and run an MMORPG world without writing code, editing config
files, or touching a terminal. It has two halves that share one responsibility split:

- **Creator Console** (outside the game): a standalone desktop app that manages the *running server*
  (start/stop/safe-restart, backups, health, logs, one-click repairs). This lives in the
  `codeforge-console` / client surface, not in the engine.
- **Creator Workshop** (inside the game): a protected administrative dimension, represented through
  the game itself, where the world's owner shapes NPCs, quests, items, and difficulty. This lives in
  the engine (`parts/world/creator_workshop.py`).

This document records the design decisions for the **Creator Workshop foundation** (the barrier and
its placement). The creation stations and the Console are staged behind it.

## The barrier: what the prompt makes absolute

The Workshop is not part of the playable world. The rules are hard:

- Every generated world automatically places a **Grand Library** (discoverable) containing the
  **Creator's Door**; beyond the door is the **Workshop**, an isolated instance.
- Only the **authenticated Seed Owner** may cross. Everyone else, including a wizard trying to
  teleport past it, receives exactly: `The barrier does not acknowledge your presence.`
- Players cannot **discover, observe, reveal, enter, or teleport into** it.

## Design decisions

**The Seed Owner is the `owner` crown.** CodeForge already orders authority `player < wizard <
owner` (`parts/world/ranks.py`), bootstrapped from the host shell. The Workshop reuses that: the
Seed Owner is whoever holds the top crown. A wizard is deliberately *not* enough (the prompt says
"only the owner"), so the check is `session.rank == "owner"`, not `has_rank(..., "wizard")`.

**The door is concealed by omission, not by a flag.** The Creator's Door is simply **not one of the
Grand Library's listed exits**. Because the renderer only shows `room["exits"]`, an unlisted
threshold cannot be discovered, observed, or revealed by any player, at any rank, through any normal
verb, no per-viewer render filtering required. The owner *names* the door (`go door`); the engine
intercepts that word only while standing in the Library. A player who guesses `go door` still meets
the barrier, so concealment and access control are independent layers.

**The crossing is unobservable.** Unlike ordinary movement, crossing the barrier announces no
"leaves"/"arrives" to the Library (`forge._cross_workshop_barrier`), so players can never see the
owner slip through. The Workshop's only tie back is a plain `out` exit to the Library.

**Placement is idempotent and seed-agnostic.** `install_workshop(world)` runs during world assembly
(`parts/world/world.py`), after the seed and the procedural generators, **before** the link audit,
so the canonical rooms pass the same `inspect_world_links` gate as authored ones. It anchors the
Library to the world's spawn (its first room) with a `library` noun exit, so *every* world, whatever
its geography, satisfies "walk into the Grand Library."

**Teleport is guarded at the source.** `ranks.teleport` refuses any Workshop room for a non-owner
with the same barrier message, closing the "teleport past the door" vector. `ranks` imports
`creator_workshop` (which imports neither, only `session`/`seed`), so there is no import cycle.

**No import cycle, by construction.** `creator_workshop` reads `session.rank` directly rather than
importing `ranks` (which imports `world`, which imports `creator_workshop`). The rank string is the
stable contract; the barrier does not need the rank *router*.

## Why this shape

| Question the prompt asks | How the foundation answers it |
|---|---|
| Can players discover it? | No, the door is unlisted; concealment is structural. |
| Can players observe the owner enter? | No, the crossing announces nothing. |
| Can a wizard teleport in? | No, teleport refuses Workshop rooms for non-owners. |
| Does every world have it? | Yes, `install_workshop` runs in assembly for every seed. |
| Is it testable without a GUI? | Yes, entirely through the engine tick (`handle_command`). |

## The Workshop is a place, not a menu

The Workshop is not one room but a small hub: a central hall ringed with **station rooms**, one per
CodeForge subsystem, that the owner *walks* (`go npc`, `go quests`, `go difficulty`). Each station
(`STATIONS` in `creator_workshop.py`) is data, a hall-noun, a room label, and a plain-language
description of what a creator shapes there, and `install_workshop` builds every station room and
wires the hall's exits from that table. The whole hub lives behind the barrier: every station room is
in `WORKSHOP_ROOMS`, so teleport refuses non-owners into any of them, not just the entry.

Each station room honestly **describes** its purpose in plain language and does not claim a command
it lacks. The create-tools are fitted into these rooms one at a time.

## Station tools: gating and the first one

A station tool is a verb that is **owner-gated AND station-gated**: it works only for the Seed Owner
standing in the matching station room, and returns a plain "nothing here" to anyone else, so a
station leaks nothing about the workshop. Tools are added read-only first (safe, no persistence), and
mutating tools follow behind a change buffer with preview/publish/rollback.

Two read-only tools are live so far:

- **Planning Table `survey`** (`plan_survey`) reads the world's *shape*: it measures the live world
  (rooms, zones, inhabitants, wild creatures) and reads its scale against the **Seed Package**
  deployment tiers (nearest tier by room count), composing both Creator campaigns.
- **Statistics Wall `activity`** (`wall_activity`) reads the world's *life*: the live session roster,
  players online and the room/zone each stands in.

Both are read-only, so neither mutates world state (Architecture Law 1).

## The change buffer: preview → publish → rollback (live-only)

The first *mutating* tool arrives with the LIVE PREVIEW loop the prompt asks for, in its safest
honest form. The owner **stages** an edit into a per-session draft, **previews** it, then, at the
Publishing Portal, **publishes** it to the live world or **rolls it back**.

- **Live-only, by design.** Publish writes the in-memory world only, never the seed files. A change
  is reversible and simply vanishes on restart. Persistence to the seed (surviving a restart) is a
  deliberately separate, later decision, it touches the seed contract, the loader gates, and backups.
- **Law 1 stays intact.** A staged change is inert data. The single validated apply-path
  (`_apply`) is the only thing that mutates canonical state, and only at the owner's explicit
  `publish`. Adding a new editable thing means adding a `kind` to `_apply`, not a new mutation site.
- **Two kinds so far**, both the same staging move (name a thing, name a room), differing only in
  the apply-path: `create npc <name> at <room>` (NPC Studio, a peaceful townsperson, hp 0/atk 0) and
  `create item <name> at <room>` (Item Forge, a plain object a hero can find). Adding a kind is one
  row in `_CREATABLES` plus one `_apply_*` function; the parse, validation, preview, publish, and
  rollback are shared.
- **Station-gated flow.** Create at the matching station (NPC Studio / Item Forge), preview anywhere
  in the Workshop, publish and rollback at the Publishing Portal, so each station earns its place.

### Human Keel Record: live-only world mutation

- **Intent / problem.** The Creator Experience needs the owner to edit a running world (create an
  NPC, publish it) without files or a terminal, but Architecture Law 1 forbids ad-hoc mutation of
  canonical state.
- **Decision (Josh).** Ship a **session-scoped, live-only change buffer**: stage → preview →
  publish to the in-memory world → rollback. No seed-file writes yet.
- **Alternatives considered.** (a) Persist changes to `seeds/aethryn/*.yaml` on publish, more
  powerful, but a much larger surface (seed contract, loader gates, backups) and harder to reverse;
  (b) keep building read-only tools and defer mutation entirely.
- **Why this one.** It delivers the headline "create → publish" loop while keeping every change
  reversible and Law 1 intact (one validated apply-path). Persistence becomes its own considered
  slice rather than being smuggled in under a feature.
- **Evidence.** `tests/test_creator_workshop.py` proves the full loop through the tick (create →
  preview shows it while the world is still untouched → publish makes it live → rollback discards),
  plus the gating and validation refusals. `make check` green.
- **Review point.** Before any tool writes to the seed files, or mutates anything beyond adding a
  peaceful NPC, revisit this record and the persistence question with Josh.

## Roadmap (staged behind this foundation)

Each station is a subsystem surfaced as a welcoming space rather than a developer menu. The tools to
fit into the rooms that now exist:

- **NPC Studio / Creature Forge / Item Forge** wrapping the existing `@sg`, seed, and bestiary
  systems as plain-language create/edit flows.
- **Quest Archive** over the quest engine; **Difficulty controls** over combat/spawn/loot knobs
  (plain language in Beginner Mode, raw values only in Advanced Mode).
- **Live preview / undo / redo / publish / rollback** over a change buffer, so a creator understands
  the impact of a change before it goes live.
- **Beginner Mode** (guided, explains terms, recommends defaults, celebrates milestones) and
  **Advanced Mode** (blueprints, generation parameters, diagnostics), progressively revealed.

Each station composes an existing CodeForge subsystem; the accessibility layer is the new work. The
**Creator Console** (server management, health, one-click repairs) is the outside-the-game twin,
built on the client surface.

## Accessibility guideline

Every station added here must pass the same test: *a first-time creator, with no programming
background, can understand it, preview it, and undo it.* Plain language is the default; raw engine
values appear only under Advanced Mode. Nothing a creator can do in the Workshop should require a
file edit or a terminal.
