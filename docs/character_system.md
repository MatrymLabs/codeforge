# The Character System

The JRPG character system: identity, jobs, attributes, progression, combat, equipment, and
the score sheet that projects it all. This is both a **player guide** (the commands) and an
**author/developer guide** (the data schema and how the pieces compose). Balance numbers below
are **prototype** (`prototype_balance_only`) and live in one place each, meant to be tuned.

Design records: [ADR-0002](adr/0002-derive-dont-store.md) (derive, don't store),
[ADR-0005](adr/0005-character-sheet-view-model.md) (render through a view model),
[ADR-0006](adr/0006-derived-stats-prototype.md) (derived stats are formula-driven, prototype).

---

## Part 1 - Playing

Everything runs through the engine tick (`handle_command`), so these are the words you type.

### Choose a calling

| Command | Effect |
|---|---|
| `jobs` | list the callings you can take |
| `job <calling>` | take up a primary job (builds your stats and resources) |
| `subjob <calling>` | equip a secondary job (its kit is borrowable; its level/JP track separately) |

Example: `job engineer`, then `subjob scholar`.

### Read your score sheet

`score` renders the full sheet. `score <mode>` picks a focused view:

| Command | Shows |
|---|---|
| `score` | the full sheet (all groups) |
| `score compact` | identity, level, job, HP/MP, core stats, loadout |
| `score jobs` | every unlocked job with its level, JP, and TP (the active one marked) |
| `score equipment` | worn gear and the derived stats it shapes |
| `score resistances` | the elemental / status grid |
| `score developer` | raw + derived values with their sources (internal view) |

### Two progression axes (they are independent)

- **PLvl (Player Level)** advances with **XP**, earned by defeating enemies. Global, capped at 255.
- **Job Level** advances with **JP (Job Points)**, per job, capped at 30. Changing jobs never
  erases a prior job's level.
- **TP (Training Progress)** fills toward **milestone perks**: each full milestone
  (currently 500 TP) unlocks the job's next passive perk, which raises a derived stat.

Both curves are locked design (`parts/world/progression.py`); XP, JP, and TP are all awarded on a kill.

### Fight, and the Engineer's kit

| Command | Effect |
|---|---|
| `attack <target>` | strike an enemy; on defeat you gain XP, JP, and TP |
| `repair` | **Field Repair** - heal HP for MP, then a short cooldown (Engineer) |
| `scan <target>` | **Diagnostic Scan** - reveal a target and apply `Analyzed` (Engineer) |
| `deploy` | **Deploy Barrier** - spend Power Cells to raise a barrier (Engineer) |

The Engineer also has passives that fire automatically: **Systems Thinking** (lengthens
`Analyzed`) and the **Emergency Repair** counter (auto-heals once when HP falls to/below 30%,
then cools down).

**Power Cells (PC)** are the Engineer's custom resource - shown on the sheet, spent by
`deploy`, and regenerated each combat action.

### Gear

| Command | Effect |
|---|---|
| `take <item>` / `drop <item>` | pick up / put down an item |
| `equip <item>` | wear a carried, equippable item in its slot; its modifiers raise your derived stats |
| `unequip <slot>` | remove the gear in a slot (weapon/body/head/arm/accessory_1/accessory_2) |

---

## Part 2 - Authoring and architecture

### The data model: jobs are data

Jobs live in a seed pack's `seeds/<pack>/jobs.yaml`. The loader (`parts/seed.load_jobs`) gates
every field and fills sensible defaults, so a simple calling stays a three-liner while a full
JRPG job declares its whole loadout. The full `Job` schema:

| Field | Type | Meaning |
|---|---|---|
| `name` | str | display name |
| `description` | str | one line |
| `stats` | map | the six attributes: `strength, speed, magic, stamina, wisdom, luck` (loader fills any omitted to 8) |
| `role_tags` | list | role identity, e.g. `[support, control, technical]` |
| `abilities` | list | active skill labels |
| `automatic_attack` | str | the auto-attack label |
| `counter` / `movement` / `inherent` / `signature` | str | the reaction / mobility / passive / defining ability labels |
| `resistances` | map | element code to level (`Weak/Normal/Resist/Immune/Absorb`); undeclared reads Normal |
| `power_cells` | int | size of the custom resource pool (0 = the job runs on MP) |
| `power_regen` | int | power cells regained per combat tick |
| `milestone_perks` | list | ordered `{name, target, amount}` perks, one unlocked per TP milestone |

A malformed value (a non-integer stat, an unknown resistance level, a perk missing a key)
**fails loud at load** - bad content never reaches the game.

Equippable **items** (`seeds/<pack>/items.yaml`) add two optional fields to the normal item
schema: `slot` (weapon/body/head/arm/accessory_1/accessory_2) and `mods` (a map of target
stat to a flat amount, e.g. `{ATK: 6, ACC: 3}`).

### The derived-stat pipeline

Derived combat stats (ATK, DEF, EVA, MAG DEF, ACC) are computed, never stored, in three
layers - all folded through the same order-independent `ModifierStack` (`parts/stats.py`):

```
base = derived_stats(attributes, level)        # parts/world/derived.py (prototype formulas)
  -> apply_equipment(...)                       # equipped gear's mods       (parts/world/equipment.py)
  -> apply_stat_modifiers(..., perk_modifiers)  # unlocked milestone perks   (parts/world/character_view.py)
```

Because everything flows through one stack, gear and perks stack the same way, and rebalancing
means editing one file (`parts/world/derived.py` for the base formulas, the seed data for gear/perks).

### The view-model seam (why the renderer is engine-free)

The score sheet is a **projection** ([ADR-0005](adr/0005-character-sheet-view-model.md)):

- `parts/world/score_sheet.py` - a pure `CharacterSheet` view model + `render_score_sheet(sheet, mode)`.
  It reads only the view model: no database, no `Session`. That is why it is reusable (a
  personnel dashboard, a training transcript) and testable from a fixture.
- `parts/world/character_view.py` - `sheet_from_session(session)` does the engine-coupled assembly:
  attributes from the stat block, resources from the pools, per-job level/JP/TP from the
  persisted record, derived stats through the pipeline above.

### Persistence (derive, don't store)

A saved character keeps only minimal facts; stats and resources recompute on restore
([ADR-0002](adr/0002-derive-dont-store.md)). Two SQL tables (SQLAlchemy + Alembic migrations):

- `characters` - identity, primary `job`, `secondary_job`, `level`, `xp`, location, rank, account.
- `job_progress` - one row per job the character has taken (`job_level`, `jp`, `tp`), so
  switching jobs never erases a prior job's rank.

### Prototype balance knobs (where to tune)

| Knob | Where |
|---|---|
| Base derived-stat formulas | `parts/world/derived.py` |
| XP -> PLvl and JP -> Job Level curves (locked) | `parts/world/progression.py` |
| TP per milestone (500) | `character_view.TP_MILESTONE` |
| Engineer costs/cooldowns/thresholds | constants at the top of `parts/world/engineer.py` |
| Job stats, resistances, power, perks, gear | the seed YAML (`seeds/<pack>/`) |

### Worked example: add a new job

1. Add an entry to `seeds/<pack>/jobs.yaml` with the fields above (only `name` is truly
   required; everything else defaults).
2. `make check` - the loader validates it; a bad field fails loud.
3. `job <yourjob>` in game, then `score` - it renders through the same pipeline, no code change.

Reusable pieces from this system are filed in the Hardware Store (`make hardware`):
`score-sheet-renderer`, `derived-stat-calculator`, `job-loadout-schema`, `modifier-stack`,
`equipment-slots`, `cooldown-status-clock`.
