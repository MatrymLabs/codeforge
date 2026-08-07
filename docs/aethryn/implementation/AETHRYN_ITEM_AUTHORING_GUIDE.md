# Aethryn Item Authoring Guide

1. Choose the correct layer: environmental, ambient good, interactive object, portable prototype,
   or authored unique.
2. Give the record a permanent lowercase id and one authority status. Ordinary generation defaults
   to `GENERATED_LOCAL`; local reviewed Veridia content may be `AUTHORED_LOCAL`.
3. Declare family, materials, source region/habitat, maker tradition, ownership, value, stack rules,
   and acquisition path.
4. Write inventory, ground, examine, equipped, condition, use, repair, crafting, consumption, and
   salvage text appropriate to the item. Describe old technology through visible input/output and
   failure behavior; do not explain unresolved global history.
5. Add a reachable recipe, station, profession, merchant source, loot reason, placement, or authored
   reward as appropriate. Validate creature-derived materials against body class and population.
6. Add provenance: source design ids and paths, packet, seed, generator/version, authority, and digest.
7. Run the item/weapon/armor/crafting/merchant/loot checks and the focused tests before materializing.

Review example ids: `greenhold_field_spear`, `greenhold_arming_sword`, `greenhold_roadwarden_bow`,
`riverstone_buckler`, `ditchwarden_jacket`, `field_hoe`, `greenhold_roadwarden_cloak`,
`meadowfoil_tonic`, `barley_ration`, `veridian_iron_ore`, `imported_tideglass_vial`, and the
rare authored-local `greenhold_valve_key`. Do not add a relic to fill a rarity tier.
