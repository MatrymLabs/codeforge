# Aethryn Quest Migration

Existing quest files and ids are preserved. `kernel.world.seed.load_quest` accepts the old step form
and the extended transition form; `kernel.world.aethryn_quests.normalize_quest_record` maps old
`steps` and `on_enter`/`on_take`/`on_defeat` triggers to structured transitions. The current
`WorkflowEngine`, `_RUNS` save map, legacy bare-state restore, rewards, and natural event hooks are
unchanged.

Migration policy:

1. Keep the old id and state labels.
2. Add pressure, objectives, references, prose, and consequences around the old graph.
3. Preserve `reward_xp` and recognized event names.
4. Validate persisted `{quest_id: state}` maps before replacing a record.
5. Do not rename a live id without an explicit persistence/reference audit.

Verification: `PYTHONPATH=. .venv/bin/pytest -q tests/test_quest.py tests/test_aethryn_quests.py`.
