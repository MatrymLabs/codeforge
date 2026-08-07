# Aethryn Quest Review Examples

These are the ten restrained Greenhold examples in
`veridia_greenhold_living_slice.yaml`. All are local and use `AUTHORED_LOCAL` except the recurring
contract, which is `GENERATED_LOCAL`.

| Quest | Pressure and graph | References | Reward / consequence |
|---|---|---|---|
| The Cistern Below the Ledger | water shortage; offered → traveling → examining → resolved | Greenhold, cistern court, drainage ledger, Mara | XP; reveal local water evidence |
| Seat the Pale Valve | water shortage; offered → diagnose → ready → resolved | shallow hollow, Sen, Mara, sluice wheel | XP; flowing settlement cistern |
| The Broken Hedge | crop damage; warning → tracking → confronting → contained | farm lane, hollow, field-boar | XP/reputation; seasonal pressure reduction |
| A Dry Copy for the Mill | water/food record; offered → carrying → delivered | cistern court, Greenhold, ledger | XP/currency; personal notice access |
| Dye for the Market Cloth | damaged crop economy; offered → gathering → returning → supplied | farmstead, meadowfoil node, market | XP/currency; temporary trader stock |
| Three Accounts of the Wheel | civic dispute; offered → evidence → comparing → reported | Mara, Sen, hollow | XP/reputation; local dialogue record |
| Handles Before Harvest | missing labor/tools; offered → making → delivering → delivered | farmstead crew, valid local handle output | XP/currency; work-crew schedule |
| The Quiet Hollow Watch | vermin/maintenance pressure; warning → preparation → active → held | hollow, waste yard, vermin | XP/reputation; one-day danger reduction |
| Seasonal Field Watch | recurring crop pressure; offered → patrolling → resolved | compatible field-boar habitat | generated XP; one-day pressure cooldown |
| Water Day at the Civic Edge | public low-cistern event; preparation → active → success/failure | civic edge, Mara, Sen, contribution ledger | contribution-gated reputation; public schedule |

The first three form `greenhold_water_and_work_arc`; the investigation intentionally preserves
uncertain old-world history as evidence and conflicting testimony. The packet compiles all ten with
provenance and no runtime model call. Review commands are documented in
`AETHRYN_QUEST_SYSTEM.md`.
