# Aethryn room prose batches

This is the handoff surface for expanding Aethryn in authoring drops. Give each batch a permanent
sequence and one record per room. Existing room labels overlay their prose; new labels are allowed
when the batch supplies explicit exits that link them into the assembled graph.

Room batches may contain any positive number of rooms; `final` is an editorial marker rather than a
size constraint. Every record needs at least 20 words of prose. `name`, `room_type`, `tags`, and `notes` are optional. `occupants` and
`objects` are optional visible content lists; they compile into peaceful NPCs and room items.
`exits` is required for a new room and may replace exits on an existing room.

Copy this shape into `batch_0001.yaml`:

```yaml
batch:
  id: aethryn_rooms_0001
  sequence: 1
  status: ready
  size: 100
  final: false

  rooms:
  field_veridia_r0001_c0001:
    name: A Named Place
    room_type: Field Path
    desc: >-
      A full room description goes here. Include what the player can see, hear, smell, and use,
      then give the place a local detail that connects it to the surrounding route and lore.
    exits: {west: veridia}
    occupants: [A named local resident waits beside the road.]
    objects: [A weathered marker stone stands in the grass.]
    tags: [veridia, road, authored]
    notes: "Optional editorial note; not shown to players."
```

To get a mechanically selected next batch of stable room IDs, generate a draft in the ignored
`incoming/` area:

```sh
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python tools/room_batch_template.py --sequence 1
```

Use `--final` when the drop is intentionally the last editorial batch.

Edit the draft, replace every placeholder, set `status: ready`, and move it into
`content/seeds/aethryn/room_batches/`. Files under `incoming/` are deliberately not loaded by the
world build, so unfinished work cannot accidentally ship.

Build and validate the batches before materializing the authored world:

```sh
PYTHONPATH=. .venv/bin/python tools/validate_room_batches.py
PYTHONPATH=. .venv/bin/python tools/materialize_aethryn.py \
  --scale 1 --output content/seeds/aethryn-authored-scale-1 --overwrite
```

For the classic plain-text format, save the editorial drop as a `.txt` file and compile it without
rewriting the prose by hand:

```sh
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python tools/import_mud_batch.py \
  incoming/veridia_drop.txt --sequence 2 --output-dir content/seeds/aethryn/room_batches
```

The importer preserves title, bracketed room type, prose, visible content, and exit directions. If
the text names directions but not destination IDs, it uses the drop order as a deterministic
continuous route and marks the batch `link_inference: ordered_route`; replace those links later as
cartography is refined.

The validator fails on duplicate ownership, unknown room IDs, incomplete non-final batches, short
prose, unapproved status, or unsupported fields. The materialized package then contains the exact
descriptions in `rooms.yaml`, and its manifest records the batch totals.
