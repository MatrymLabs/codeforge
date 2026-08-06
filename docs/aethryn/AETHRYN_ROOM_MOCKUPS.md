# Aethryn Room Mockups

Original examples; names and values are illustrative. They demonstrate hierarchy, not final prose.

## Standard room

```
VERIDIA — GREENHOLD MARKET ROAD

DESCRIPTION
  Green fields meet the town wall here. Carts move toward the market and the road stays open.

PRESENT
  A townsfolk pauses beside a loaded cart.

EXITS
  west — Veridia road
  east — Market Gate

NEXT: look, examine cart, east, west, map
```

## Creator's Hall

```
CREATOR'S SPACE — THE CREATOR'S WORKSHOP

DESCRIPTION
  A bright central hall. Doorways lead to the stations where the owner shapes the Seed.

STATIONS
  north — Planning Table       east — NPC Studio
  southeast — Quest Archive    south — Item Forge
  southwest — Creature Forge   west — Difficulty Desk
  northwest — Blueprint Repository   northeast — Statistics Wall
  up — Publishing Portal       out — Grand Library

NEXT: exits, map, help creator
```

## Busy city

```
CAELORIA — CAPITAL CROSSING
CONDITIONS: daylight | crowded | safe

DESCRIPTION
  Bells and foot traffic compress the high road into a single bright crossing.

PRESENT
  3 players, 2 guards, a courier

POINTS OF INTEREST
  noticeboard [quests]   fountain [examine]   eastbound coach [travel]

EXITS
  north — Palace Avenue   east — River Road   west — Westgate Road   south — Eldryn Road
```

## Wilderness

```
DUSKWOOD VALE — ROOT-LIT TRAIL
CONDITIONS: dusk | wet ground | visibility reduced

DESCRIPTION
  Roots break the old trail into dark steps. Something moves beyond the ferns.

RESOURCES
  bitterleaf [gather]   fallen branch [examine]

EXITS
  north — Veridia road   east — Eldryn Forest   south — Zhaar trail
```

## Dungeon

```
THE SUNKEN BARROW — STAIR MOUTH
CONDITIONS: dim | stale air | hazard: unstable stone

DESCRIPTION
  The grassed stone mouth drops below the valley. The lower passage is blocked by a sealed slab.

POINTS OF INTEREST
  sealed slab [LOCKED]   old mark [examine]

EXITS
  down — Lower Barrow [LOCKED]
  out — Veridia
```

## Many exits

```
KORVASH — HIGH ROAD FORK

EXITS
  north — Ashen Wastes       northwest — Zhaar Desert
  southeast — The Voidscar   down — The Deepreach
  east — Highreach            west — Stonehelm road
```

## Combat-active room

```
COMBAT — THE COLD FORGE
Target: Ember Wisp | Range: near | Beat: 2
FOE: Ember Wisp 9/14 HP | YOU: 28/32 HP

EXITS
  out — Forge threshold [flee available]
```

## Minimal, narrow, and linear forms

```
GREENHOLD MARKET ROAD
Description: Green fields meet the town wall.
Present: 1 townsfolk.
Exits: west Veridia road; east Market Gate.
Next: look; examine cart; east; west; map.
```

```
ROOM: Greenhold Market Road
DESCRIPTION: Green fields meet the town wall. The road stays open.
PRESENT: townsfolk (1)
EXITS: west (Veridia road); east (Market Gate)
```

