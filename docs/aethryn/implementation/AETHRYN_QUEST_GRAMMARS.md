# Aethryn Quest Grammars

Quest grammar is a validation vocabulary, not a mandatory identical quest shape. The packet
`quest_type` selects the intended structural family and the existing workflow stores the actual
states and transitions.

Supported families are: discovery, retrieval, delivery, hunt, repair, defense, escort, rescue,
investigation, crafting commission, gathering commission, diplomacy, infiltration, dungeon
objective, faction contract, public event, repeatable contract, and tutorial.

Every grammar requires a reachable start, a completion/failure/ongoing terminal, valid event names,
and references appropriate to its work. Hunt and defense records must reference compatible creature
and encounter records; crafting and gathering records must reference obtainable outputs or regional
nodes; delivery and escort records must reference reachable rooms/routes. Public and repeatable
grammars may loop only under their declared cooldown/recurrence policy.

Veridia demonstrates discovery, repair, hunt, delivery, gathering, investigation, crafting,
defense, repeatable contract, and public event forms without manufacturing a global campaign claim.
