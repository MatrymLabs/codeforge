# Veridia: trail -> field (World Topology Doctrine, Veridia pilot)

Aethryn's cradle wilderness, once a linear trail-chain, is now an OPEN, WORLD-SHAPED, LIVING
field -- and a player crosses from the hand-authored hub into it and back seamlessly through
the engine tick (`handle_command`). Reproduce with `FORGE_SEED=aethryn` (deterministic, seed 9).

## The shape verdict (the field subgraph)

| metric | old trail (measured) | new field |
|---|---|---|
| verdict | TRAIL_SHAPED | **WORLD_SHAPED** |
| linearity (exactly-2-exit) | 66% | **0%** |
| loop ratio (on a cycle) | ~0% | **100%** |
| mean exit degree | 2.0 | **7.38** |
| rooms | ~800 | 607 |

Living content: **604 foes**, **121 gather nodes**, **15 named guardians**; a river crossed by a **ford and a bridge**; **35 road cells**.

On-ramp preserved: the field's life deepens from the ENTRANCE, so a newcomer meets **level 1** wild at the door (the field spans levels 1-30).

## The seamless walk (authored hub -> field -> back)

```
>>> look   (the AUTHORED hub, hand-written)
    == Veridia ==
    The Veridia zone (levels 1-30): green starter valleys of rivers and open road, where every journey begins. Within its bounds lie Greenhold, Elderwatch, Riverbend, Sunmeadow, The Sunken Barrow. Roads and routes run on to the neighbouring lands.
    [location: veridia | zone: veridia_zone]

>>> west   (cross the seam: authored hub -> GENERATED field)
    == Veridia (11,12) ==
    Close-standing trees filter the light to green; water runs to the east.
    [location: veridia_11_12 | zone: field_veridia | exits: ['north', 'south', 'west', 'northwest', 'southwest', 'east']]

>>> northwest -> veridia_10_13    exits=8  foe(lvl 1)
>>> northeast -> veridia_11_14    exits=8  foe(lvl 1)
>>> northeast -> veridia_12_15    exits=8  foe(lvl 2)
>>> northeast -> veridia_13_16    exits=5  foe(lvl 3)

>>> (return to the gate veridia_11_12) then  east
    == Veridia ==
    [location: veridia | zone: veridia_zone]  -- back in the authored hub, seam closed
```
