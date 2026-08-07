# Aethryn Quest Authoring Guide

Start with a pressure record and identify its affected rooms, people, resources, creatures,
factions, and valid outcome. Choose a grammar only after the pressure supports it. Write structured
objectives and transitions; prose is presentation, never the mechanics store.

Use stable lowercase ids. Keep generated content `GENERATED_LOCAL`; use `AUTHORED_LOCAL` for reviewed
local work. Include `source_design_ids`, provenance, generation seed/version when generated, and
state-aware prose for discovery, journal, progress, success, failure, aftermath, and unresolved
remainder. Do not claim Forge, Ember, Unforging, Netharion survival, divine motives, or other locked
questions as facts.

Before publication run `world quest-check`, `world quest-reference-check`, `world quest-graph-check`,
`world quest-reward-check`, `world quest-consequence-check`, and the focused quest tests.
