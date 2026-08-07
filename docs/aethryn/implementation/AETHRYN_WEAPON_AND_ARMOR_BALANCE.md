# Aethryn Weapon and Armor Balance

Weapon families are approved data, not name-driven stat rolls. The current validator checks family,
slot, damage type, reach, cadence, accuracy, base damage budget, level band, rarity, and positive
operating costs. The visible weapon budget is:

```text
base damage + accuracy + (reach - 1) + (cadence - 1)
<= 8 + floor(level-band-max / 2) + approved rarity allowance
```

Long reach and fast cadence therefore consume budget; unsupported damage types and unrestricted
special properties fail validation. Material and quality modify bounded durability/value outcomes,
not arbitrary combat power.

Armor uses the existing slots and modifier stack. Defense, magic defense, evasion, movement cost,
coverage, durability, and requirements are explicit. Shields occupy the existing `arm` slot. No
parallel slot taxonomy is introduced. The Veridia proof represents arming swords, field spears,
road-warden bows, a riverstone buckler, a work jacket, and a road-warden cloak.

The existing equipment renderer and set bonus fold remain authoritative at runtime.
