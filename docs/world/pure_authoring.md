# Aethryn Pure Authoring Mode

Pure authoring is the content-build path for the open-world version of Aethryn.

During design, the compact canon, topography, fields, caves, settlements, and dungeon manifests are
expanded by the normal deterministic assembly pipeline. The authoring command then writes the result
as an ordinary seed package:

```sh
PYTHONPATH=. .venv/bin/python tools/materialize_aethryn.py \
  --scale 1 --output content/seeds/aethryn-authored-scale-1
```

The package contains materialized rooms, NPCs, items, gear sets, story and contract quests, the
canonical story zones, and the additional field/cave/delve zones. It also carries an
`authoring_manifest.yaml` pointing back to the canon, lore, topography, and generation contract that
produced it. The build applies the authored prose pass in `kernel/world/authoring_prose.py`: all 14
regions have their own terrain, history, pressure, route, wildlife, and resident voice; named source
landmarks have full descriptions; and materialized field, cave, dungeon, enemy, and resident records
inherit that regional authorship.

Boot the package without runtime world generation:

```sh
FORGE_SEED=aethryn \
FORGE_AUTHORING_SNAPSHOT=content/seeds/aethryn-authored-scale-1 \
PYTHONPATH=. .venv/bin/python tools/census.py
```

The snapshot is open-world data, not a corridor export. Every surface connection, named threshold,
settlement interior, cave, underzone, dungeon branch, lore inscription, NPC location, item placement,
and quest trigger is materialized and passes the same seed link gates as hand-authored data.

Scale is an offline build cost. Generate the million-cell field profile on a content host with
`--scale 38`; deploy the resulting seed artifact to game servers. Player boot reads the authored pack
and does not spend startup time constructing the world.

The distinction remains measurable: current scale-1 materialization is 27,721 authored runtime
rooms, 27,620 NPCs, 686 items, 56 zones, and 3,394 quests. The original source seed still contains
202 explicit hand-authored rooms; materialization turns the designed world into durable authored data,
while the prose pass supplies authored descriptions for the expanded world between those canonical
anchors.
