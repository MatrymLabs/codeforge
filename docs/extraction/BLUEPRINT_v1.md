# BLUEPRINT v1 (DRAFT, derived)

**Not doctrine.** Extracted 2026-08-19 from DONE-1 and DONE-2. Every field below was USED by one
of those two builds. Fields that a Blueprint schema "obviously" wants and neither done actually
consumed are listed at the bottom as deliberately absent, so their absence is a recorded decision
rather than an oversight.

---

## The schema

```yaml
blueprint_id:            BP-M2-ENGINE-REAL          # DONE-1
blueprint_version:       1
source_request_id:       <intake id>
anchor:                  DONE-1                     # must be on the board's anchor set
target_product_name:     Done1
target_product_type:     standalone_game            # or: tool

source:
  repository:            codeforge
  baseline_commit:       8edcf069                   # the commit the pour was cut from

language_lanes:
  - lane_id:             python
    status:              PROVEN                     # see LANGUAGE_LANES_v1.md
    role:                core

modules_consumed:                                   # MEASURED from the proof's imports,
  - kernel.world.characters                         # not declared by hand
  - kernel.world.db
  - kernel.world.jobs
  - kernel.world.session
  - kernel.world.world

pour:
  command:               make cast TEMPLATE=blank_mud NAME=Done1 DEST=../codeforge-done1-target
  template:              blank_mud
  destination:           ../codeforge-done1-target
  validation:            boots + ticks

proof_runs:
  - proof_run_id:        PR-M2-PIPELINE
    command:             scripts/m2_pipeline_proof.py --target <dest>
    stages:              [isolation, persist, restart, survive]
    calibration:         --sabotage <stage>, each must exit non-zero
    expected:            PASS

evidence:
  transcript:            captured in the Bench Report
  artifacts:             reports/deploy/<date>-<name>-deploy.md   # deploy-proof only

known_limitations:       []
```

## The three fields that are load-bearing, and why

**`modules_consumed` is MEASURED, never declared.** DONE-1's list above came from grepping the
proof's actual imports, not from anyone writing down what they thought it used. A declared
dependency list is a claim; an extracted one is evidence. This is the field most likely to be
filled in by hand later, and doing so would quietly turn the Blueprint back into documentation.

**`stages` names the proof's parts so an absent stage is visible.** DONE-2 has no `persist` stage.
That is correct, because its intake said `persists_state: false`. Listing stages explicitly is what
makes a missing stage read as NOT_APPLICABLE rather than as something nobody ran.

**`calibration` is not optional.** Both dones ship a `--sabotage` switch and both were exercised
this session: four stages each, every one exiting non-zero when broken on purpose. A Blueprint
whose proof cannot be shown to fail records a gate that has never been shown to fail, which canon
13 calls decoration. If a Blueprint has no calibration field filled, its proof is unproven.

## DONE-2 in the same schema, to show the fields flex

```yaml
blueprint_id:            BP-RF-001
anchor:                  DONE-2
target_product_type:     tool
language_lanes:
  - {lane_id: python, status: PROVEN, role: core}
  - {lane_id: kotlin, status: GATED,  role: surface}     # L1 only; see the lane record
modules_consumed:
  - kernel.retroforge.artifact
  - kernel.retroforge.binary
  - kernel.retroforge.codec
  - kernel.retroforge.platforms.planar_2bpp
proof_runs:
  - proof_run_id:        PR-RF001-SLICE
    stages:              [synthesize, load, decode, manifest, display, integrity]
    calibration:         --sabotage [load, decode, manifest, integrity]
constraints:
  input_provenance:      "synthetic fixtures only; no cartridge image is read from disk or committed"
known_limitations:
  - "displays through Rider is L1: the run configuration is committed and the grid renders through
     the command Rider invokes, but Rider LOADING it has never been observed."
```

## Deliberately absent, each with its reason

| field a schema usually has | why it is not here |
|---|---|
| `compliance:` overlays | Neither done produced a fact that triggers one. Adding empty overlay blocks invites a boolean where a resolution belongs. |
| `hardware_store.consumed_parts` | Neither done consumed a Part. The search was run and logged for both; the honest value is an empty list, and an empty list of a thing nobody used is not yet a schema field. |
| `threat_model` | Neither product has an attack surface. RF-001 reads untrusted bytes, which is why it has hostile-input fixtures, but it exposes no service. |
| `work_orders:` | Both dones were driven directly. When a Blueprint generates orders, this earns its place; today it would be aspirational. |
| `deployment:` | `deploy-proof` produces a DEPLOYABLE label and a dated report, and that is a proof run, not a deployment. Nothing has been deployed. |

## Known limitation

Two Blueprints, and both are engine-shaped: one pours the engine, one reads a file. Neither has a
service, a database beyond SQLite, a network surface, or an outside user. **The schema has not been
tested against a product that is unlike CodeForge**, and the Excel-to-PDF converter named in the
plan as the generality proof is exactly that test. Expect fields to move when it arrives.
