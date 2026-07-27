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

The first live tool is the **Planning Table's `survey`** (`creator_workshop.plan_survey`). It
composes both Creator campaigns: it measures the *live* world (rooms, zones, inhabitants, wild
creatures) and reads its scale against the **Seed Package** deployment tiers (nearest tier by room
count), giving the owner an honest, plain-language overview. It is read-only, so it never mutates
world state (Architecture Law 1).

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
