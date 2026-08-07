# Aethryn Quest System

The quest system extends the existing `kernel.world.quest` workflow adapter. It does not replace the
state machine, event hooks, player save format, party registry, reward ports, or packet compiler.
Legacy YAML (`start`, `steps`, `terminal`, `labels`, `reward_xp`) is normalized into the structured
shape at load time, preserving quest ids and persisted state names.

## Terms and records

`QuestPressureSpec` explains why work is needed; `QuestSpec` describes one static graph; a
`QuestInstance` is live player/party/public progress. `QuestArcSpec` connects quests without making
every local task a campaign. `ContractTemplateSpec` is a bounded repeatable pressure response.
`PublicEventSpec` owns one shared state and a contribution ledger rather than one instance per
participant. `QuestWorldEffectSpec` declares target, scope, duration, persistence, and reversibility.

Packet records use `quests`, `quest_pressures`, `quest_arcs`, `contract_templates`, `public_events`,
`quest_world_effects`, and `quest_generation_profiles`. The compiler enriches every record with
source ids, packet id, seed, generator version, provenance, and digest. The materialization pass
copies compiled quest records into the ordinary seed quest directory.

## State and events

The old `WorkflowEngine` remains authoritative. Extended transitions use `from`, `event`, `to`,
optional `target_id`, conditions, effects, and idempotency. Natural events (`enter`, `take`,
`defeat`, `gather`, `craft`, `repair`, `deliver`, `public_contribution`, and current event aliases)
route through the existing `kernel.world.quest.on_event` hook. The `quest` command remains a fallback.

Validation checks start and terminal states, edge references, supported event names, reachability,
dead states, non-repeatable cycles, objective structure, references, reward duplication, prose,
provenance, canon status, and locked-lore leakage. Legacy records are exempt from new pressure/prose
requirements only through the explicit compatibility adapter.

## Consequences and persistence

`ConsequenceStore` is a small serializable adapter for local, party, instance, settlement, zone,
and regional effects. Generated records cannot promote themselves into locked canon. Effects are
visible state declarations and may be reset by scope or persisted through their declared policy.

## Commands

```text
PYTHONPATH=. .venv/bin/python -m tools.world quest-check veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world quest-graph-check veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world inspect-quest greenhold_water_repair veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world quest-lineage greenhold_water_repair veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world simulate-quest greenhold_water_repair veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world preview-contract greenhold_seasonal_field_watch --seed 41017 veridia_greenhold_living_slice.yaml
PYTHONPATH=. .venv/bin/python -m tools.world simulate-public-event greenhold_water_day_event veridia_greenhold_living_slice.yaml
```

Exact focused verification: `PYTHONPATH=. .venv/bin/pytest -q tests/test_aethryn_quests.py` → **11
passed**; `PYTHONPATH=. .venv/bin/pytest -q tests/test_quest.py tests/test_quest_archetypes.py` →
**27 passed**.
