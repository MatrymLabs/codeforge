# Aethryn Skills, Abilities, and Techniques

## Taxonomy

- Skill: a learned competency or rank-bearing progression item.
- Ability: a named mechanical component granted by a job, item, quest, or other source.
- Technique: a player-invoked specialized action; an ability may be exposed as a technique.
- Passive: an ability with no direct command and a persistent or triggered effect.
- Profession action: a non-combat skill/ability for crafting, gathering, or service.

Retain the current job schema's active abilities, counter, movement, inherent, signature, and
milestone perks. Do not flatten those slots into one untyped list.

## Text views

```
SKILLS — Matrym
  Combat       4 learned   |  Profession       0 learned
  Vanguard     1 active    |  Pathfinder       locked

  [x] Shield Discipline       Rank 1  passive
  [x] Hold the Line            Rank 1  technique  MP 2  cooldown 3 beats
  [LOCKED] Vanguard Mastery   unlocks at Job Level 30

NEXT: skill <name> | abilities | techniques | skills combat
```

`ability <name>` and `technique <name>` show cost, cooldown, cast time, range, target, effects,
requirements, and the exact unavailable reason. Locked entries are visible by default when their
existence is relevant to a current job; undiscovered content may show `[UNDISCOVERED]` instead of
requirements. This is a founder-facing visibility decision, so discovery can be configurable.

## Structured parity

`SkillPresentation`, `AbilityPresentation`, and `TechniquePresentation` share stable ids and a
`availability` object. Clicks submit the canonical command, never a direct state mutation. Filters
are category, source, availability, target, cost, cooldown, and recently learned.

