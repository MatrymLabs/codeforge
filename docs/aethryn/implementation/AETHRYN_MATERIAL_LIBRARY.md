# Aethryn Material Library

Materials are sourced records, not abstract crafting tokens. Each declares a class, region and
habitat, gathering method and profession, refinement path, uses, scarcity, weight, durability,
value, repair compatibility, and local interpretation.

The Veridia slice uses local iron ore, alder, meadowfoil, field-boar hide, riverstone, and imported
tideglass. Tideglass is imported through `greenhold_southern_caravan`; it is not mislabeled as local.
Boar hide comes from a supported biological population and is a crop-protection byproduct. Ancient
infrastructure remains an interactive object with observable behavior, not a new material source.

The demonstrated chains are:

```text
iron ore -> wrought iron -> iron fitting -> riverstone buckler
alder wood -> alder haft -> spear/sword/tool
meadowfoil -> travel tonic
field-boar -> hide -> repairable leather-bound gear
```

No material may be gatherable without one gathering profession or lack a source unless it is marked
imported, ancient, artificial, intentionally unobtainable, or authoring-required.
