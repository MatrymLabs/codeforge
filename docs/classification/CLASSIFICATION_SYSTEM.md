# CodeForge Classification Registry

*A hidden filing system beneath the fantasy.*

Players see a world: rooms, an Archivist, a training dummy, guidance documents.
Underneath, every object that matters is **filed** - given a unique designation,
a record, and a traceable line back to its source file, its tests, and the things
it depends on. The fiction is the surface; the registry is the engineering catalog
beneath it.

This is the same discipline as the Federal Guidance Library's
`data/source_registry.csv` - *trace everything to a source, date, version, owner,
and control* - applied to the whole ship.

---

## The one rule that makes it safe

**Designations are additive metadata. They never rename anything.**

Every runtime identifier stays frozen: room keys (`archive`), YAML seed keys,
database columns, CLI verbs (`serve`, `play`), CARD names, character/account handle
formats. Those are load-bearing - renaming them breaks save files, seeds, and
migrations.

A designation is *attached to* a label, not a replacement for it:

| Layer | Handle | Example | Who uses it |
|-------|--------|---------|-------------|
| Fantasy (runtime) | **label** | `archive` | the engine, save files, seeds |
| Filing (backend) | **designation** | `RM-08.001` | the registry, the ritual, you |

The registry row carries both: `label` is the runtime handle, `designation` is the
filing handle. If you can't map a designation back to a real label + file, the row
is invalid.

---

## The designation format

Subnet addressing (ADR-0008): a domain code and a stable ordinal, like an IP address.
The old Borg/Unimatrix format (`TYPE-UM##-S##-N###-SEQ-REV`) is retired to each row's
`aliases` and still resolves, so nothing that cited an old id breaks.

```
[TYPE]-[DD].[NNN]
   |     |     |
   |     |     ordinal (001... - stable object number in the domain; minted once, never renumbered)
   |     domain code (01... - the world domain, see below)
   type prefix (RM, MOD, CMD, PRT, ...)
```

Example: `RM-03.002` reads as *Room · Library/Classroom domain (03) · object 002.*
`MOD-05.009` is the `telnet_codec` module, filed in the Hardware Store domain (05).

Designations sort cleanly, grep cleanly, and never collide (a validator enforces
uniqueness - see below). You never hand-type one: a helper mints the next ordinal.
Identity is always the frozen `label`; the designation is a re-classifiable filing aid
layered over it (the four-layer model: identity, address, display, metadata).

### Type prefixes

| Prefix | Object | Prefix | Object |
|--------|--------|--------|--------|
| `RM`  | Room                     | `REG` | Regulation / guidance entry |
| `NPC` | Non-player character      | `DOC` | Source document |
| `ITM` | Item                     | `PDF` | Stored PDF artifact |
| `QST` | Quest                    | `TXT` | Extracted text analog |
| `CMD` | Command (engine-tick verb)| `LSN` | Lesson |
| `MOD` | Python module (`parts/*.py`)| `QZ`  | Quiz |
| `PRT` | Reusable code part (a cataloged capability)| `EV`  | Evidence record |
| `SYS` | System / safety service  | `LOG` | Log / report |
|       |                          | `API` | API connector |

`MOD` vs `PRT`: a **MOD** is a physical `parts/*.py` file. A **PRT** is a reusable
*capability* that file exposes (e.g. `FailsafeRunner`, `HardwareCatalog`). Often 1:1,
sometimes many-PRT-per-MOD.

### World domains (the `DD` codes)

Registry designations classify *where a thing lives in the ship/world*. The Hardware
Store catalog uses a separate 19-domain *engineering* taxonomy (what a reusable part
*does*), addressed the same `domain.ordinal` way; the TYPE prefix tells the two apart.

| Domain | Meaning | Domain | Meaning |
|--------|---------|--------|---------|
| `01` | Workshop / private engineering space | `06` | Compliance & regulations |
| `02` | City / public player space           | `07` | Finance systems |
| `03` | Library & Classroom                  | `08` | Records management |
| `04` | Game systems (combat, jobs, XP)      | `09` | AI NPC & API systems |
| `05` | Hardware Store / reusable parts      | `10` | Reports, logs & evidence |

### Status vocabulary (controlled - never let stale read as active)

`prototype` · `active` · `hardened` · `deprecated` · `archived` · `superseded`

Mirrors FGL's freshness discipline: a status is never assumed. `hardened` means
*tested and in production use*; `deprecated` still runs but is on the way out;
`superseded` points at the designation that replaced it.

---

## The record (what each row answers)

Every designation record carries these fields (schema:
`registry/schemas/designation.schema.json`):

| # | Field | Answers |
|---|-------|---------|
| 1 | `designation` | (the unique ID) |
| 2 | `name` | human-readable name |
| 3 | `type` | What is it? (TYPE prefix) |
| 4 | `domain` | Where does it belong? (world domain code) |
| 5 | `ordinal` | Its stable number within the domain |
| 9 | `status` | Active, prototype, archived, deprecated, superseded? |
| 10 | `function` | What does it do? |
| 11 | `label` | the frozen runtime handle it files |
| 12 | `file` | Where is its source? |
| 13 | `docs` | Where is its documentation? |
| 14 | `tests` | What proves it works? |
| 15 | `depends_on` | What does it depend on? (list of designations) |
| 16 | `related` | Related objects (list) |
| 17 | `reuse` | What can reuse it? |
| 18 | `tags` | free-text search tags |
| 19 | `notes` | anything else |
| 20 | `created` / `updated` | dates |

The **modularity story lives in fields 15-17**: `depends_on`, `related`, and
`reuse` make an object's seams visible. The designation is just the filing handle;
the dependency and reuse edges are what show a part is modular.

---

## Storage - start simple

**JSON**, mirroring FGL's `documents.json`: a list of records per type, loaded by a
validator that *fails loud* on a bad row. Not SQLite yet - same beginner-safe call we
made for the guidance library. Indexes are **generated, never hand-maintained.**

```
registry/
  collective_registry.json      # optional roll-up (generated)
  designations/
    rooms.json                  # a list of RM-* records
    npcs.json
    items.json
    commands.json
    modules.json                # MOD-*
    reusable_parts.json         # PRT-*
    documents.json              # DOC/PDF/TXT/REG-*
    lessons.json                # LSN/QZ-*
    evidence.json               # EV/LOG-*
  schemas/
    designation.schema.json     # the record contract
  indexes/                      # GENERATED by the validator, never edited by hand
    by_type.json  by_domain.json  by_tag.json  by_status.json
```

---

## How code links to its filing (the modularity tag)

Because the registry is a *backend* filing system, modules stay clean - no heavy
in-code annotations. The bridge is one line, both directions:

- **code → registry:** the existing CARD block gains one optional line, so you can
  grep from a file to its filing:
  ```python
  """CARD: library -- read the guidance library's documents.

  DESIGNATION: MOD-03.012
  """
  ```
- **registry → code:** the record's `file` + `tests` fields point back at the module
  and its twin.
- **the gate:** `make registry` fails if a stamp has no matching row, or a row points
  at a missing file/test. Neither side can silently rot. (*Verify by gates, not eyeballs.*)

---

## Validation rules (the "professional rules", enforced not hoped)

1. **No duplicate designations.** The minter guarantees the next free sequence.
2. **No orphans.** Every record's `label` maps to a real object; `file`/`tests` exist.
3. **No casual renames.** A designation is stable once minted. A change bumps the
   `revision` and records an **alias/migration** entry - the old ID still resolves.
4. **No deletes - archive instead.** Status → `archived`/`superseded`; the row stays.
5. **Controlled status.** `status` must be one of the six values above.
6. **Beginner-safe.** If a rule makes a new object hard to file, the rule is wrong.

---

## Implementation staircase (each step ships green)

- **Phase 1 - rules & schema.** *(this document + `designation.schema.json`)*
- **Phase 2 - the registry card.** `parts/registry.py`: `Designation` dataclass,
  `load_registry`, `mint_designation`, `validate` + a test twin. No wiring yet.
- **Phase 3 - file the 16 starter rooms.** First real data.
- **Phase 4 - NPCs & items.**
- **Phase 5 - documents, lessons, quizzes, evidence.**
- **Phase 6 - the sync gate.** `make registry` proves code ↔ registry never drift.
- **Phase 7 - MUD verbs.** `registry show/find/type/tag/status/related/validate`.
- **Phase 8 - ritual check.** The startup ritual validates the registry: required
  rooms, documents, parts, and evidence paths all exist and are filed.

## Definition of done

Every starter room, important NPC, stored document, PDF + text analog, and reusable
part is filed; duplicates are impossible; the MUD can display a record; the startup
ritual validates the whole registry; and a beginner can file a new object in one
step. Precise, engineered, traceable - and invisible until you look.
