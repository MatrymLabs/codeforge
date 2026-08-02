# world_areas -- the area bench

Generated areas wait here between generation and publication. Each is one JSON file written by the
`world` developer tool (`kernel/world/area_store.py`):

```
python -m tools.world generate-area veridia --seed 7   # forge a cave, save it here, preview it
python -m tools.world preview-area gen_cave_veridia_7   # look again
python -m tools.world promote gen_cave_veridia_7        # GENERATED_LOCAL -> AUTHORED_LOCAL
python -m tools.world export gen_cave_veridia_7 out.json  # snapshot to a world-data file
python -m tools.world list-areas                        # what is on the bench
```

The contents are **git-ignored on purpose**: a generated area is mutable dev state, not canon, and
it is fully reproducible from its `(region, seed)` because the forge is deterministic. Only this
README is tracked. Static, established world canon lives in `seeds/aethryn/`, never here.
