# Aethryn Quest Reward Balance

Rewards remain on current XP, currency, reputation, item, recipe, profession, service, access, and
world-effect ports. Extended records attach repeatability, budget, party distribution, contribution
requirements, and unique-item restrictions. Repeatable contracts cannot grant unique rewards or
create a trivial currency/crafting loop. Public rewards require the declared meaningful contribution.

The packet reward budget and threat range are authoring constraints. A completion transition is
idempotent because the existing workflow has no legal transition from its terminal state and the
existing adapter applies the effect only after `Fired`.
