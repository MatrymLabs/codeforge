# Aethryn: every wilderness is now an open, world-shaped FIELD

The World Topology Doctrine, applied to the whole map. All 14 zone wildernesses, once linear
trail-chains, are now OPEN fields generated at boot -- each terrain reads its BIOME, so the
map has real topographic variety, and a player crosses from a hand-authored hub into the
field and back seamlessly through the engine tick. Reproduce with `FORGE_SEED=aethryn`.

## Every zone: world-shaped, living, terrain that matches the biome

| zone | biome | verdict | rooms | loop | terrain reads |
|---|---|---|---|---|---|
| ashen_wastes | volcanic-flats | world_shaped | 682 | 100% | ash+hills |
| caeloria | temperate-meadow | world_shaped | 654 | 100% | trees+meadow+hills |
| duskwood_vale | wild-forest | world_shaped | 611 | 100% | trees+hills |
| eldryn_forest | wild-forest | world_shaped | 718 | 100% | trees+hills |
| frostspire_peaks | glacier-waste | world_shaped | 655 | 99% | snow+hills |
| korvash_highlands | highland-moor | world_shaped | 829 | 100% | marsh+hills |
| shattered_isles | coastal-strand | world_shaped | 813 | 100% | sand+shore+hills |
| skyward_spires | highland-moor | world_shaped | 779 | 100% | marsh+hills |
| thalorin | highland-moor | world_shaped | 718 | 100% | marsh+hills |
| the_deepreach | volcanic-flats | world_shaped | 789 | 100% | ash+hills |
| the_voidscar | volcanic-flats | world_shaped | 842 | 100% | ash+hills |
| veridia | temperate-meadow | world_shaped | 607 | 100% | trees+meadow+hills |
| xilnath_jungle | living-jungle | world_shaped | 829 | 100% | marsh+trees+hills |
| zhaar_desert | salt-desert | world_shaped | 768 | 100% | sand+hills |

**14 fields, 10294 generated rooms**, every one WORLD_SHAPED with a ~100% loop ratio
(the trails were 66% linear, ~0% looped). Rivers follow elevation and are crossed by fords and
bridges; cliffs (glacier, volcanic) and sea-inlets (coast) are real obstacles the field routes
around; roads thread the open ground between landmarks (trail AND field). Each field carries the
trail's living content -- ambient foes, gather nodes, and named guardians -- and its cull/forage
boards route by zone exactly as before.

## A seamless walk (authored Veridia hub -> the field -> back)

```
>>> look   (the AUTHORED hub, hand-written)
    == Veridia ==
    The Veridia zone (levels 1-30): green starter valleys of rivers and open road, where every journey begins. Within its bounds lie Greenhold, Elderwatch, Riverbend, Sunmeadow, The Sunken Barrow. Roads and routes run on to the neighbouring lands.
    [veridia | zone: veridia_zone]
>>> west   (cross the seam into the GENERATED field)
    == Veridia (11,12) ==
    Close-standing trees filter the light to green; water runs to the east.
    [veridia_11_12 | zone: field_veridia | exits: ['north', 'south', 'west', 'northwest', 'southwest', 'east']]
>>> northwest -> veridia_10_13    exits=8  foe(lvl 1)
>>> northeast -> veridia_11_14    exits=8  foe(lvl 1)
>>> northeast -> veridia_12_15    exits=8  foe(lvl 2)
>>> (back at the gate) east
    == Veridia ==
    [veridia | zone: veridia_zone] -- seam closed
```
