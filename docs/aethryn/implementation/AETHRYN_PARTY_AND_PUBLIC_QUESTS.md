# Party and Public Quests

The existing transient party registry remains the membership source. Quest records declare personal,
party, instance, or public scope and objectives declare `party_credit`. Shared defeat/interaction
credit is independent of final-blow ownership; proximity and meaningful contribution are explicit.
Late joins, leaving, reconnect, and disband behavior follow the existing party lifecycle.

Public events use one shared state plus `ContributionLedger`. Participants receive only rewards whose
contribution policy they satisfy. The ledger is aggregate data, so a crowd or event never creates
hundreds of persistent NPCs or duplicate quest instances. `simulate_public_event` provides a
deterministic builder preview.
