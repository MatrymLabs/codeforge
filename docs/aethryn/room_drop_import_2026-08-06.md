# Aethryn room drop import, 2026-08-06

## Purpose

Four supplied Aethryn room manuscripts are now installed through the existing room-batch
authoring gate. The manuscripts remain editorial prose. The compiled YAML is the runtime input.

## Source audit

The headers claim more rooms than the files actually contain. This import uses only room blocks
that contain a title, bracketed room type, prose, three visible-content lines, and an `Obvious
exits` line.

| Source | Header claim | Imported room blocks | Batch records |
| --- | ---: | ---: | ---: |
| `Aethryn_Duskwood_BlackHollow_Batch01.txt` | 94 | 33 | 34 |
| `Aethryn_Duskwood_Vale_Batch01.txt` | 128 | 50 | 51 |
| `Aethryn_Skyward_Spires_Level_200_250_Massive_Room_Drop_01_500_Rooms.txt` | 500 | 500 | 501 |
| `Aethryn_Veridia_Massive_Batch_MaxEffort.txt` | 187 | 104 | 105 |
| **Total** | **909** | **687** | **691** |

The extra record in each batch is an existing Aethryn anchor overlay. No rooms were invented to
close the 222-room difference.

## Installed batches

The files live in `content/seeds/aethryn/room_batches/`:

| Batch | Label namespace | Anchor entry | Link status |
| --- | --- | --- | --- |
| `duskwood_black_hollow_0010.yaml` | `duskwood_black_hollow_*` | `the_black_hollow fringe` | `ordered_route` |
| `duskwood_vale_0011.yaml` | `duskwood_vale_*` | `ravenwatch gate` | `ordered_route` |
| `skyward_spires_0012.yaml` | `skyward_spires_*` | `skyward_spires verge` | `ordered_route` |
| `veridia_massive_0013.yaml` | `veridia_massive_*` | `greenhold wards` | `ordered_route` |

Each drop's first room has an `out` return to its anchor. The anchor receives one named exit into
the drop. This makes the content reachable without replacing existing canonical exits.

## Cartography authority and limitation

The supplied fantasy world map poster, `a_highly_detailed_fantasy_world_map_poster_layout.png`, is
the visual topology authority for Aethryn. Its zone boundaries, major settlements, landmark
dungeons, and sea relationships are represented by the machine-readable projection in
`content/seeds/aethryn/world_graph.yaml`.

The manuscripts list room directions but do not provide destination IDs for every individual room.
The importer therefore uses manuscript order only as a deterministic local route and records
`link_inference: ordered_route`. That label does not override the poster or the canonical region
graph. The four drops enter through poster landmarks: Greenhold, Ravenwatch, The Black Hollow, and
the Skyward Spires zone anchor.

A later room-cartography pass can replace local destination labels while keeping the stable room
IDs, prose, and poster-level zone topology intact.

Visible occupants and objects are carried through the room-batch runtime as peaceful NPCs and
readable room objects. No combat, quest, or bespoke behavior is inferred from prose.

## Verification evidence

From the CodeForge repository root:

```sh
FORGE_SEED=aethryn PYTHONPATH=. .venv/bin/python tools/validate_room_batches.py
# room prose batches: valid
#   batches: 8
#   rooms: 1047
#   assembled_world_rooms: 28731

PYTHONPATH=. .venv/bin/pytest -q tests/test_room_batches.py
# 8 passed
```

The room count reported by the validator includes the four existing room batches and their
anchors. The source-specific imported count is the 687-room audit above.
