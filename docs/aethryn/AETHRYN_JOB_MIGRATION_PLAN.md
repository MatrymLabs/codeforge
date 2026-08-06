# Existing Character Job Migration Plan

No current character loses progression silently. Before applying a job graph, create a database
backup, produce a dry-run report per character, and expose a player preview. Preserve learned
abilities and job levels; if a job is renamed, retain the old id as an alias. If a job splits, map
progress to the closest successor and refund the affected JP/TP once. If a job becomes gated, keep
the grandfathered unlock and mark the source as `legacy_grant`; do not retroactively remove power.

Migration record fields: character id, old job id, new job id(s), old levels, retained abilities,
refund, reason, source version, operator, timestamp, validation result, rollback token.

Procedure: backup -> dry run -> review counts -> player preview -> approval -> transactional apply ->
rebuild derived stats -> validate abilities/equipment -> emit evidence -> monitor -> rollback if any
invalid state. A rollback restores the backup or reverse record, never a guessed reconstruction.

