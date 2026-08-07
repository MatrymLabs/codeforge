# Aethryn Loot and Merchant System

Merchant profiles are deterministic projections beside the existing NPC `shop` implementation.
Profiles name settlement, shop type, ordinary and conditional stock, quantities, restock interval,
supply sources, imports, scarcity behavior, pricing, and restrictions. Greenhold has a field/travel
merchant and a civic/militia quartermaster; neither sees the entire item registry. Unique items are
never ordinary stock.

Loot profiles name source class, body class where biological, guaranteed/weighted outcomes, quantity,
threat band, ownership, region, production reason, recurrence, and unique restrictions. The field
boar may yield hide or nothing; hollow vermin mostly yield nothing; road thieves carry used local
supplies. A phenomenon or incompatible body class cannot yield a pelt.

Ambient workshop stock and household goods are placement records, not automatic portable loot.
Ownership distinguishes household property, civic property, military issue, merchant stock, stolen
goods, salvage rights, and unowned material. The existing crime system remains out of scope; custody
is preserved as structured state for future integration.
