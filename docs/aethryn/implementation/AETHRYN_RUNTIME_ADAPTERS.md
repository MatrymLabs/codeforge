# Aethryn Runtime Adapters

`kernel/world/aethryn_runtime.py` is the read-only bridge between compiled Aethryn sidecars and the
live CodeForge room renderer.

## Runtime flow

```text
generated/*/records.yaml
        -> RuntimeCatalog
        -> room id + world beat
        -> routine, trade, ecology, and pressure signals
        -> room description projection
```

Startup reads static package artifacts only. It never invokes a model, creates a package, or edits a
room. The shared climate beat is the only changing input, so schedule selection is deterministic:
the beat selects one declared schedule entry by stable modulo indexing.

## Adapter coverage

- NPC schedules project a current routine for compiled NPC records located in the room.
- Economy flows project a trade signal when a room is the source or sink endpoint, resolving NPCs,
  resource nodes, and room ids through compiled records.
- Ecology flows project pressure when the compiled creature is located in the room.
- Quest pressures project the local cause when an affected record resolves to the room.
- World state remains a separate persistence seam and is rendered before these signals.

The adapter does not yet simulate NPC movement, production quantities, shop inventory depletion, or
creature population changes. Player mutations enter through separate packet-declared actions and
validated engine logic.

## Verification

```text
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_aethryn_runtime.py
PYTHONPATH=. .venv/bin/python -m pytest -q tests/test_aethryn_runtime.py tests/test_aethryn_world_compiler.py
```

The tests prove deterministic projections, beat-sensitive schedule selection, empty behavior for
non-Aethryn seeds, and live room-renderer integration.
