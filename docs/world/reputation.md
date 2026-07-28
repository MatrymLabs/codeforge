# Reputation -- Standing with the Orders

*How a single hero STANDS with each Order over time, as distinct from which Order they are sworn to
(orders) and how the Orders stand with each other (factions). Roadmap item #2: the numeric-standing
substrate that faction-gated content and the faction-story archetype pull on. Design canon behind
`parts/world/reputation.py`.*

## Three layers, one politics

| Layer | Question it answers | Lives in |
| --- | --- | --- |
| Orders | Which Order am I sworn to? | `parts.world.orders` |
| Factions | How do the Orders stand with each other? | `parts.world.factions` |
| Reputation | How do *I* stand with each Order? | `parts.world.reputation` (this) |

Reputation is per character, per Order: a number that content raises and lowers, banded into named
tiers, and persisted (the tier recomputes from the number on restore -- derive-don't-store).

## Tiers

Standing bands into tiers, roughly one per 100:

| Standing | Tier |
| --- | --- |
| 600+ | Revered |
| 300-599 | Honored |
| 100-299 | Friendly |
| 0-99 | Neutral |
| -100 to -1 | Unfriendly |
| below -100 | Hostile |

## The single earn door: `grant`

`reputation.grant(session, order, amount)` is the one door content calls to move standing. It
composes with the faction politics rather than treating Orders as independent bars: a deed that
pleases one Order pleases its **allies** by half the amount and offends its **rivals** by half
(read from `factions.relations_of`). A negative amount flips the spillover -- hurting an Order
pleases its rivals. `grant` returns a line for each Order whose tier changed, and is a clean no-op
for an unknown Order.

Today's one wired earn is **swearing an Order**: `join <order>` grants `SWEAR_STANDING` (100 ->
Friendly) with the new Order, spilling over its allies and rivals, so allegiance and reputation move
together from the first oath. The `standing` verb shows a hero their reputation and tier with every
Order, their own marked.

## What #2 deliberately leaves for later

More earn sources (quest-completion effects, felling a rival Order's champions) and **rep-tier-gated
content** (a recipe or a door that needs "Honored with the Making Order," extending 1d's binary
Order gate to a numeric one) are follow-ons that call this same `grant`/`standing_of` surface. #2 is
the substrate: the standing model, its faction spillover, persistence, and the display.
