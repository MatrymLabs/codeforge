# Aethryn Presentation, Command, Navigation, Character Flow, and Job Progression Research

Research baseline: 2026-08-06. This package is implementation-ready at the contract and vertical-
slice level. It is deliberately honest about unresolved founder choices and current-state gaps.

## 1. Executive Summary

Aethryn should keep the Seed Runtime authoritative and make every presentation a projection. The
highest-value change is a shared presentation grammar: short labelled sections, stable headings,
numeric progress, explicit status tokens, safe wrapping, and a complete linear text form. The Master
Client can then render the same room, character, combat, skill, and job data as panels without
creating a second game.

The current character sheet is the strongest design evidence. Preserve its identity header, paired
resource columns, aligned labels, grouped statistics, and view-model seam. Apply those rules to
rooms, combat, skills, and jobs without putting a box around every event.

Navigation should migrate by metadata and aliases. The authored map has 77 rooms and 170 exits; 107
are cardinal, compound, or vertical spatial directions (62.9%). Adopt 70% as the major-space target
and 80% for Creator's Hall where physical layout permits. Named portals, stations, and fast travel
remain explicit exceptions.

The job system already has 30 callings, primary/secondary loadouts, independent job progression,
and a rich data-driven design. Add a typed prerequisite graph and player-facing explanations before
changing availability. Preserve current characters through grandfathered unlocks and reversible
migration.

## 2. Current Verified Product Condition

### Verified source evidence

- The canonical server checkout is `codeforge`; the client is `codeforge-client-unified`.
- Aethryn seed data is in `content/seeds/aethryn/rooms.yaml` and `jobs.yaml`.
- The seed currently contains 77 authored rooms and 30 callings.
- `forge.py` exposes a single `handle_command(session, signal) -> str` tick seam.
- The gateway authenticates before entering the world, separates account and character handles,
  applies five failures per five-minute address window, and uses a password echo blackout.
- `Char.Vitals` and `Room.Info` are emitted as structured state after GMCP is enabled.
- The current Master Client now receives those frames through the corrected telnet subnegotiation
  buffer handling; the live Qt probe showed `HP 32/32`, `MP 7/7`, and one room in the map.
- Workspace Studio now includes live `game_status`, `arc`, and `observation` bodies alongside the
  engineering catalog.
- Creator's Workshop is installed as a protected owner-only dimension, reached from the Grand
  Library through a concealed door and returned from with `out`.

### Current classification

| Capability | Classification | Evidence / next check |
|---|---|---|
| account login | PRESERVE_AND_EXTEND | `adapters/gateway.py`, account modules |
| character selection | RESTRUCTURE | current front desk enters a character; state machine needs an explicit selection UI |
| character creation | PRESERVE_AND_EXTEND | current three starting callings and gateway dialogue |
| room prose | CLEAN_UP | seed descriptions are zone summaries; format sections are incomplete |
| exits | RESTRUCTURE | 62.9% spatial; named spokes and `out` semantics need metadata |
| score sheet | PRESERVE_AND_EXTEND | ADR-0005 and live transcript are strong evidence |
| GMCP vitals/map | REPAIR completed, EXTEND | live Qt regression passed after telnet fix |
| combat | PRESERVE_AND_EXTEND | continuous tick, cooldowns, status effects exist; output needs grouping modes |
| skills/abilities | PRESERVE_AND_EXTEND | job schema and ability commands exist; availability view needs a unified model |
| jobs | PRESERVE_AND_EXTEND | 30-callings YAML and job-system design; unlock graph not declared in seed data |
| creator space | KEEP_AS_IS foundation | owner gate and concealed door are deliberate founder decisions |
| structured panels | PRESERVE_AND_EXTEND | GMCP and panel host exist; parity contract is needed |

## 3. Research Method

Repository evidence was inspected before recommendations. External research prioritized official
Evennia documentation, Mudlet client/protocol documentation, W3C WCAG 2.2, ECMA-48, and GNU
terminal interaction documentation. Sources are recorded in `AETHRYN_SOURCE_REGISTRY.yaml` with
limitations and confidence. Public systems were studied for interaction patterns, never copied for
names, text, graphics, values, or job tables.

Evidence labels used here: `VERIFIED_SOURCE_FACT`, `OBSERVED_INTERFACE_PATTERN`,
`SOURCE_DERIVED_CONCLUSION`, `ENGINEERING_INFERENCE`, `AETHRYN-SPECIFIC RECOMMENDATION`,
`CURRENT IMPLEMENTATION EVIDENCE`, `UNVERIFIED CLAIM`, `OPEN QUESTION`, and
`FOUNDER DECISION REQUIRED`.

## 4. Source Quality and Limitations

Evennia documents the useful distinction between command identity, aliases, help categories,
command sets, and locks, but CodeForge is not Evennia. Mudlet confirms the practical value of a
structured GMCP side channel and client aliases, but client automation cannot become authority. WCAG
principles transfer well to text and Qt, but a specialist must review actual screen-reader output.
ECMA-48 describes ANSI control functions, not semantic accessibility. Job progression conclusions
are a synthesis of the existing CodeForge job design and general progression principles, not a claim
that any external game table should be reused.

## 5. Current-State Audit

The full artifact inventory is split between this report, `AETHRYN_JOB_INVENTORY.yaml`,
`AETHRYN_MAIN_ROOM_EXIT_AUDIT.yaml`, and `AETHRYN_COMMAND_REGISTRY.yaml`. The audit method is
repeatable: read seed and runtime rooms, enumerate each exit, classify its direction/alias/state,
inspect reciprocal metadata, then run snapshot and graph tests. The current YAML is a macro map whose
parent hubs contain named child routes and whose child rooms use `out`; this is not necessarily a
broken graph, but it is an under-specified player-facing spatial model.

## 6. Character-Sheet Design Analysis

The sheet succeeds because it answers identity, resources, progression, attributes, derived combat
values, equipment, and resistances in one scan. Its hierarchy is stronger than its decoration:
name/job at the top; HP/MP/XP/JP next; attributes and loadout in paired rows; derived values and
resistances below. The view-model ADR explicitly separates rendering from Session/DB, which permits
shared text and panel projections. Keep this architecture. Improve only the ambiguous empty-value
behavior (`0/0` must not mean missing) and add narrow/linear renderers.

## 7. Aethryn Presentation Grammar

Use `TITLE`, `STATUS`, labelled sections, grouped rows, `[OK]`, `[WARN]`, `[LOCKED]`, `[x]`, and
`[ ]`. Color is supplemental. Borders are for reports and selection screens, not every room or
combat event. See `AETHRYN_PRESENTATION_STYLE_GUIDE.md`.

## 8. Text Width and Wrapping

Default 78 columns, with 48 narrow, 64 compact, 110 wide, and linear modes. Measure printable width
after ANSI removal. Tables become lists below 48 columns. Essential values are never clipped. The
current score renderer's clipping and fixed-column discipline are the pattern to retain.

## 9. ANSI, Unicode, and Plain-Text Policy

Basic ANSI may style headings, success, warning, and errors, but literal tokens carry meaning.
Unicode box drawing and bars need ASCII fallbacks. Client capability negotiation can select ANSI,
Unicode, or plain mode; the server's semantic text is identical.

## 10. Accessibility Requirements

Every essential panel has a complete command/text equivalent. Progress bars include numbers. Job
graphs have linear prerequisite lists. Combat has a screen-reader event profile. Keyboard focus is
predictable in the Master Client; terminal command order is the same conceptual order. Destructive
actions confirm. Status changes do not steal focus. See the accessibility YAML for test ids and
specialist review points.

## 11. Room Presentation Research

The useful synthesis across text games and engine documentation is that a room is a structured
decision surface, not a prose wall. The player needs location, a short description, present actors,
interactive objects, and exits. Dynamic environmental facts are shown only when relevant or changed.
Repeated prose can be suppressed while the title and exits remain reliable.

## 12. Recommended Room Format

`AREA — ROOM`, conditions if actionable, `DESCRIPTION`, `PRESENT`, `POINTS OF INTEREST`, and `EXITS`.
`look verbose` adds long prose. `exits`, `map`, and `examine` are focused commands. Creator stations
are a named administrative exception; player hubs should use spatial directions wherever geometry
can teach them.

## 13. Room Mockups

See `AETHRYN_ROOM_MOCKUPS.md` for standard, Creator's Hall, city, wilderness, dungeon, many-exit,
combat, narrow, and linear examples.

## 14. Exit and Navigation Research

Cardinal directions reduce memorization when the space is physically directional. Named movement is
valuable for portals, vehicles, elevators, instances, and administrative stations. The recommendation
is not “rename every noun”; it is “separate canonical direction, display label, and alias.”

## 15. Cardinal and Compound Direction Policy

Canonical directions are north, northeast, east, southeast, south, southwest, west, northwest, up,
down, in, and out. Abbreviations are safe only when unambiguous. Primary physical exits target 70%
in major game spaces and 80% in Creator's Hall. Exceptions require a reason in content data.

## 16. Creator's Hall Navigation Audit

The current Workshop is an explicit station hub: named station nouns are appropriate because it is a
protected administrative space. The Grand Library's `door` is concealed and owner-gated by design;
do not make it a normal visible exit. Add `exits`, `map`, and `help creator` only if they reveal no
protected information. See the exact audit YAML.

## 17. Major Game-Room Navigation Audit

The current zone hubs have appropriate spatial inter-zone exits, but child settlement spokes such as
`greenhold`, `brightwater`, and `starfall` are named. Parent-to-child placement must be decided by
content authoring before converting them to cardinal directions. Child `out` routes are a threshold
pattern and may remain `out` with a display label. Every semantic pair should carry an explicit
reciprocal record, even when command words differ.

## 18. Navigation Migration Plan

Add metadata first, then migrate Creator's Hall/onboarding, then zones in progression order. Keep safe
legacy aliases for two release cycles, publish help changes, and rollback by version. No destructive
seed rewrite is needed for the first slice.

## 19. Combat Presentation Research

The current engine is continuous and tick-based, with cooldowns, status effects, and enemy menace.
The design bible already identifies a compact status line and telegraph/result cadence. Preserve
those truths. Group ambient repeated events; keep player decisions, warnings, consequential effects,
defeats, and rewards visible.

## 20. Recommended Combat Format

Standard mode uses encounter title, target/range/beat, actor-labelled events, status line, and next
actions. Compact mode reduces repeated auto-attacks. Detailed mode preserves mitigation and element
details. Linear mode gives one event per line. Summary mode retains decisive events and rewards.

## 21. Combat Mockups

See `AETHRYN_COMBAT_MOCKUPS.md` for one-on-one, multi-foe, party, boss, status-heavy, compact,
screen-reader, and reward-summary transcripts.

## 22. Skills, Abilities, and Techniques

Keep the distinction already present in the job system: active abilities, automatic attack, counter,
movement, inherent, signature, and milestone perks. Present skill, ability, and technique as typed
views with cost, cooldown, target, requirements, availability, and source. Never show a locked row
without a reason unless discovery secrecy is an intentional founder choice.

## 23. Related Character Interfaces

`score` is the full sheet; `attributes`, `equipment`, `inventory`, `skills`, `abilities`, `techniques`,
`jobs`, `job <name>`, `quests`, `factions`, `professions`, `status`, and `combat` are focused views.
They share IdentityBlock, ResourceBlock, ProgressRow, RequirementRows, filters, and footer commands.

## 24. Unified Command Architecture

One canonical registry owns syntax, aliases, permissions, help, and client action ids. The engine
tick remains the authority. Parser stages are normalization -> command exact match -> argument
tokenization -> exact target -> numbered target -> unique prefix -> ambiguity/typo response ->
authorization -> execution -> typed result. Context-sensitive creator commands are additive and
permission-scoped, not an unrelated parser.

## 25. Canonical Command Registry

The YAML registry covers the core movement, perception, object, inventory, combat, progression,
account, system, and creator families. Existing branches not yet extracted remain legacy and must be
added during Phase 1 rather than silently removed. The current `HELP_TEXT` is evidence of a large
surface, not a complete machine-readable registry.

## 26. Parser and Alias Rules

Normalize case and Unicode, preserve quoted multiword targets, exact-match before prefix-match, number
duplicates, suggest only a few close typos, and never let a client alias bypass server authorization.
Command names win over named exits; `go <word>` may resolve a safe exact exit. Destructive commands
require confirmation and should support cancellation.

## 27. Help and Discoverability

Generate `help`, `commands`, and `syntax` from the registry. Contextual hints are dismissible and
rate-limited. Errors explain what happened, why, and what to do next. Master Client buttons link to
the same syntax.

## 28. Account Creation and Login

The current gateway already has a splash, prompt-driven login/new flow, secret echo suppression,
address failure budget, and authentication before world entry. Preserve those strengths. Insert an
explicit post-auth character selection state. Keep account and character names distinct; the current
handle syntax is a compatibility constraint, not a reason to collapse identities.

## 29. Character Selection

After successful auth, show an empty or populated character list. Include last location, level, job,
availability, and migration warnings. Selection is explicit. Delete/archive is separate and
confirmed. See `AETHRYN_CHARACTER_SELECTION_SPEC.md`.

## 30. Character Creation

Use a resumable wizard with name, appearance, origin, one of the three current starting callings,
preview, and confirmation. Skin color must persist and be test-visible; this directly addresses the
reported “skin color didn't work” issue as an implementation acceptance criterion. Do not expose all
30 callings at creation.

## 31. Reconnection and Session Flow

On link loss, autosave and mark presence offline; on reconnection authenticate again and return to
character selection, not directly to a potentially stale world session. Selection restores the last
safe location and authoritative values. The state machine YAML defines transitions and security review
gates.

## 32. Calling, Job, and Profession Terminology

Proposed taxonomy: Calling is the initial broad identity; Job is a switchable combat discipline;
Profession is crafting/gathering/service; Skill is learned competency; Ability is a mechanical
component; Technique is an invoked specialized action. This aligns with current use but remains a
founder decision because existing content calls the YAML roster “callings” while the wider docs call
them jobs.

## 33. Current Job Inventory

There are 30 current roster entries: three initial callings, five martial, six precision/arcane
crossings, five divine, four engineering, four nature, and cross-family specialists. Exact ids are in
`AETHRYN_JOB_INVENTORY.yaml`; current unlock rules are not declared in `jobs.yaml`, so any claim that
all jobs are properly gated is unverified.

## 34. Progressive Job Architecture

Use independent job levels already supported by the engine. Starting jobs teach fundamentals;
foundational jobs extend one identity; intermediate jobs deepen; hybrids combine meaningful arcs;
specialists reward focused mastery; prestige jobs require a coherent long-term path plus a trial.
No arbitrary unrelated grind.

## 35. Job Families and Tiers

The proposed matrix uses six families and six conceptual tiers including starting and prestige. It is
not a final content table: current names remain and founder approval is required before reclassifying
them.

## 36. Job Unlock Graph

The directed graph is in `AETHRYN_JOB_UNLOCK_GRAPH.yaml`. It is deliberately a proposed DAG with
multiple paths and no exact external game table. Every node must have a solo-valid path and every
edge must teach a mechanic, express lore, preserve balance, reward exploration, or support a party
role.

## 37. Job Requirement Contracts

Requirements are typed and composable with ALL, ANY, and MINIMUM_TOTAL. The UI shows checked and
missing requirements, values such as `Level 3 of 5`, the purpose/explanation, and alternatives.
Quest/trial/reputation requirements are used only when they express narrative or mechanical meaning.

## 38. Job Interface Mockups

```
JOB: Chronomancer                         [LOCKED]
Role: tempo support / control
Requirements:
  [x] Arcanist — Job Level 5
  [x] Pathfinder — Job Level 3
  [ ] Discover Elderwatch
Why: combines force shaping with route-reading and timing.
NEXT: job chronomancer | jobs locked | help jobs
```

Text job trees use indented arrows and prerequisite rows. Structured graphs must expose the same
edges as a list and support keyboard traversal.

## 39. Existing-Character Migration

Grandfather current unlocks, preserve learned abilities, alias renamed ids, refund split/removed
paths once, and provide dry-run previews and rollback records. Never silently delete progression.

## 40. Master Client Structured Interfaces

Room cards, exit compass, vitals HUD, combat log, skill filters, job graph, selection list, and
creation wizard are valid projections. Every click maps to an authorized command. Server sequence and
source fields prevent stale frames. The recent GMCP transport repair proves why this contract needs
end-to-end tests, not only panel unit tests.

## 41. Text and Structured Parity

Parity means same authoritative ids, values, exits, job state, requirements, and action availability;
it does not require identical layout. A panel can be richer spatially, but the text command can always
produce the equivalent facts. A stale or missing frame must leave the text stream usable.

## 42. Testing Strategy

Use view-model unit tests, reviewed snapshots at four widths, ANSI stripping, ASCII fallback,
parser/property tests, graph audits, gateway state tests, combat grouping tests, job prerequisite
tests, migration dry runs, and live Master Client probes. The existing client regression suite passed
the focused test suite after the telnet subnegotiation fix; this is historical implementation evidence for the
client seam, not proof that the entire product package is complete.

## 43. Anti-Patterns

Prevent walls of room text, decorative borders wider than clients, color-only semantics, combat spam,
unexplained locks, all jobs at creation, arbitrary prerequisites, account/character conflation,
named-exit replacement of physical directions, creator command collisions, client-only actions,
stale panels, vague errors, unconfirmed destructive actions, and silent migration loss. Detection is
provided by snapshots, width tests, registry audits, graph validators, parity probes, and migration
dry runs.

## 44. Recommended Architecture

Keep `handle_command` as the authoritative tick. Add a presentation package with pure view models and
renderers; add exit metadata/validation beside world loading; generate help from the command registry;
emit typed structured frames from the gateway; have the client consume frames into panels. Job
requirements and migration records belong in seed/data and persistence layers, never in client-only
logic.

## 45. Implementation Roadmap

The YAML roadmap defines eleven phases. Phase 1 is the immediate audit; Phase 2 establishes the
presentation seam; navigation, commands, combat, skills, account flow, jobs, and client integration
follow in dependency order. Job graph and migration are approval gates.

## 46. First Vertical Slice

The first complete proof is: authenticate account -> explicit character selection -> create/select
test character -> enter Creator's Hall -> see clean room and exits -> move cardinal and via one safe
legacy alias -> open score and skills -> inspect a locked job -> run controlled combat -> read summary
-> disconnect -> reconnect -> select -> verify persistence. It proves account separation, direction
policy, command/help parity, presentation consistency, accessibility, and persistence before broad
content migration.

## 47. Founder Decision Packet

Open decisions and recommended defaults are in `AETHRYN_FOUNDER_DECISIONS.yaml`: 78-column standard,
headings-only room separators, basic ANSI, standard combat, visible locked requirements, three starting
jobs, six conceptual tiers, retained learned skills with slots, grandfathered migration, recoverable
archive, portal/creator named exceptions, 70/80 direction threshold, context-plus-permission creator
namespace, current terminology with a clean taxonomy, and deprecation rather than removal.

## 48. Open Questions

The major gaps are runtime generated-room inventory, full command branch extraction, controlled combat
transcripts, appearance persistence, live unlock behavior, profession terminology, account recovery,
and actual screen-reader/width review. They are recorded with owners and required evidence in the
open-gaps YAML.

## 49. Deferred and Rejected Approaches

Deferred: persistent Workshop seed-file mutation; global named movement verbs; exposing every job at
creation; graphical-only job graphs; client-authoritative state; password recovery without security
review. Rejected: silent removal of current progression, exact copying of external job tables, and
separate parsers for gameplay, creator mode, and client actions.

## 50. Source Registry

See `AETHRYN_SOURCE_REGISTRY.yaml`. The most relevant sources are the official [Evennia command-set
documentation](https://www.evennia.com/docs/latest/Components/Command-Sets.html), [Evennia command
API](https://www.evennia.com/docs/latest/api/evennia.commands.command.html), [Mudlet protocol
documentation](https://wiki.mudlet.org/w/Manual:Supported_Protocols), [W3C WCAG 2.2](https://www.w3.org/TR/WCAG22/),
[W3C status-message guidance](https://www.w3.org/WAI/WCAG22/Understanding/status-messages), and
[ECMA-48](https://ecma-international.org/publications-and-standards/standards/ecma-48/).

The complete 15-domain comparison set is in `AETHRYN_COMPARISON_MATRICES.md`: room displays, combat,
skills, sheets, exits, command grammars, help, account flow, character selection/creation, layered
progression, accessibility, structured clients, and terminal styling.

## 51. Glossary

Seed Runtime: authoritative game state and rules. Master Client: projection and command surface.
Calling: proposed starting identity. Job: switchable combat discipline. Profession: noncombat
specialization. Skill: learned competency. Ability: mechanical component. Technique: invoked action.
Primary/Secondary Job: current build slots. JP/TP: current per-job progression currencies. GMCP:
structured MUD side channel. Canonical direction: spatial movement token. Alias: compatibility token.

## 52. Appendices

Appendix A: requested artifacts are in this directory. Appendix B: current seed inventory and proposed
families are YAML. Appendix C: original room/combat mockups are separate Markdown. Appendix D: tests,
roadmap, founder decisions, and gaps are YAML. Appendix E: exact current implementation paths include
`forge.py`, `adapters/gateway.py`, `kernel/world/world.py`, `kernel/world/creator_workshop.py`,
`kernel/world/character_view.py`, `kernel/world/score_sheet.py`, `kernel/world/jobs.py`,
`kernel/world/combat.py`, `content/seeds/aethryn/rooms.yaml`, and `content/seeds/aethryn/jobs.yaml`.
