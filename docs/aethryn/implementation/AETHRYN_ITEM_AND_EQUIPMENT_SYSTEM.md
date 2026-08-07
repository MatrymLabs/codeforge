# Aethryn Item and Equipment System

## Scope and authority

The material-culture layer extends the existing `items.py` prototype/clone registry, `equipment.py`
slot and modifier pipeline, `durability.py`, `crafting.py`, `professions.py`, `shop.py`, weighted NPC
loot, `gearsets.py`, character snapshots, and offline packet compiler. It does not create a second
inventory, equipment taxonomy, recipe executor, or runtime generator.

The authority chain remains `canon.yaml`, the Aethryn design and world graph, authored local seed
records, then generated local records. Generated content is `GENERATED_LOCAL`; the Veridia proof
catalog is `AUTHORED_LOCAL` because it is reviewed local content. Locked canon, unresolved history,
and unique campaign artifacts require explicit human review.

## Terminology

An item family is a structural pattern such as `field_spear` or `buckler`. A material describes
source, class, weight, durability, value, and cultural use. An item prototype is a reusable object
kind with complete presentation text and mechanics. An item instance is a live clone whose owner,
location, quantity, condition, quality, charges, custody, and provenance may differ. A unique item is
authored and cannot be ordinary stock or generated twice.

Environmental objects, ambient goods, interactive objects, and portable items are separate placement
layers. A workbench may be examined without becoming a portable hammer; merchant stock is owned and
must have a local source or documented import route.

## Runtime and persistence

`items.clone()` remains the spawn primitive. `items.create_instance()` adds structured instance facts
without copying prototype prose. Character snapshots preserve prototype, rolled name/modifiers,
durability, condition, quantity, charges, quality, maker, custody, stolen state, and instance
provenance. Reload re-clones the prototype and reapplies only instance facts.

## Determinism and provenance

`material_culture.compose_item()` is pure for `(family, material, quality, maker, condition, seed,
generator_version)`. Names, descriptions, composition ids, and digests are stable. The packet
compiler emits the catalog into one materialized package and adds source design ids, packet id,
generation seed, generator name/version, authority, and content digest to every record. Runtime
startup never calls a model or network service.

## Presentation contract

Meaningful portable records carry inventory, ground, examine, equipped, damaged, broken, use, repair,
crafting, consumption, and salvage text where those states apply. Dynamic condition and ownership
remain structured instance state; prototype prose is not rewritten per instance.

Representative rendered example:

```text
Inventory: a Greenhold field spear
Ground: A long alder shaft carries a leaf-shaped iron head, kept ready beside the gate rather than scattered as loot.
Examine: The spearhead is narrow enough for a boar charge and broad enough to discourage a rush through a cartway. The shaft is alder, the socket is iron, and a blue-green cord identifies Greenhold road service. Its reach buys space at the cost of a slower recovery.
```

## Sets and authored uniques

The existing set registry remains the bonus authority. The material catalog validates every piece,
slot, duplicate requirement, bonus budget, and canon status before packet publication. Generated
regional sets remain `GENERATED_LOCAL`. A named relic, royal object, campaign key, or object that
answers unresolved history must be authored, reviewed, placed once, and excluded from ordinary loot,
merchant stock, and procedural duplication.

## Builder commands

Use `world item-check`, `weapon-check`, `armor-check`, `crafting-check`, `merchant-check`,
`loot-check`, `inspect-item`, `inspect-material`, `inspect-recipe`, `inspect-merchant-stock`,
`item-lineage`, `item-provenance`, `recipe-tree`, `merchant-preview`, `loot-preview`,
`simulate-crafting`, `simulate-stock`, and the `find-*` commands listed by `world help`.
