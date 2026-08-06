# Aethryn Character Interface Family

The current score sheet is the family ancestor. Preserve its identity header, paired resource and
progress rows, aligned labels, grouped statistics, and honest empty values. `score` remains the
full view; specialized views share the same view models and tokens.

## Shared components

`IdentityBlock`, `ResourceBlock`, `ProgressRow`, `StatRows`, `EquipmentSlots`, `StatusList`,
`RequirementRows`, `SelectionCursor`, `FooterCommands`, `PageControls`, `FilterSummary`.

Every component has text, ANSI, narrow, linear, and structured renderings. A panel title states the
subject, not the implementation (`JOB UNLOCKS`, not `JobPrerequisiteWidget`). Empty values use
`Unassigned`, `None`, or `Not discovered`; never `0/0` for an unknown resource. Numeric zero is
distinct from missing.

## Family views

`score`, `attributes`, `equipment`, `inventory`, `skills`, `abilities`, `techniques`, `jobs`,
`job <name>`, `quests`, `factions`, `professions`, `status`, and `combat` all use the same section
heading, progress, lock, and footer conventions. The Master Client may use tabs/cards, but tab order
must be mirrored by command order and screen-reader linearization.

