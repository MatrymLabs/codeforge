# The party system

The **party** is CodeForge's first shared-purpose multiplayer primitive: a small, leader-led band of
heroes with its own private chat channel. Before it, the world was multiplayer in *presence* (players
shared rooms) but solo in *purpose* (they shared no cause). The party is the foundation the
shared-combat, dungeon, and raid layers build on, and it was the deepest structural gap the AAA
benchmark scorecard named.

Part: `parts/world/party.py` (MOD-04.111). Verbs: `party` (CMD-04.099), `psay` (CMD-04.100).

## Player-facing commands

| Command | Effect |
|---------|--------|
| `party` | Show your party roster (leader marked, offline members flagged). |
| `party invite <player>` | Invite a player to your band. Forms the band (you as leader) if you have none. Leader-only once formed. |
| `party join <player>` | Accept a pending invitation from `<player>` and join their band. |
| `party leave` | Leave your band. If you led it, leadership passes to the next member; if you were the last, it disbands. |
| `party disband` | Leader-only: dissolve the whole band for everyone. |
| `psay <message>` | Speak on the party channel (message case preserved). |

## Design

**Transient by design.** A party is a moment, not a record. All party state lives in the module's own
registry (`_BANDS` keyed by player id; `_INVITES` for pending offers), never in the database and never
on the `Session`. This mirrors the afflictions it sits beside: it dissolves cleanly on logout and asks
no persistence questions. A reconnect *within* a session's lifetime keeps you banded; a logout removes
you. That is the correct MUD semantic (you cannot be in a party while logged out).

**Why a module registry, not a `Session` field.** Keeping the state in `party.py` avoids a circular
import (`session.py` is imported by `party.py`), keeps the party a self-contained module with one
responsibility, and sidesteps the persistence question entirely. Other systems read party membership
through the small public surface (`party_of`, `members_in_room`), not by reaching into a session.

**Delivery.** Party chat and join/leave notices reach the band through `events.announce_to(ids, text)`,
the player-set-scoped complement to the room-scoped `events.announce`. An offline member (no bound echo
sink) is simply skipped, so a party message never fails because someone logged out.

**Leadership.** `members[0]` is always the leader, so a handoff is just dropping the leaver and
promoting the new head of the list. There is no separate leader field to drift out of sync.

**Validation (fail loud).** Every operation refuses bad input with a returned message and mutates
nothing: a self-invite, an offline or already-partied target, a non-leader inviting or disbanding, a
full party (`MAX_PARTY = 5`, the genre-standard dungeon size), a join with no invitation, and any party
action while unpartied.

**Logout cleanup.** `party.on_disconnect(player_id)` removes a departing hero from their band (with
leadership handoff) and drops their pending invites. It is called from both gateway teardowns (TCP and
WebSocket), under the same `TICK_LOCK` as the rest of session cleanup, so a party never carries a ghost.

## Shared combat: the reward half (`parts/world/party_rewards.py`, MOD-04.112)

Fighting together pays. When a partied hero fells a foe, `party_rewards.share_kill` spreads the kill's
**advancement** (XP / JP / TP) to every party-mate present in the same room, so grouping is worthwhile
rather than a way to split one prize thinner. It hangs off combat's single kill/reward seam
(`combat.land_hit`) with one call, so combat itself is untouched, and it reads the party's
`members_in_room` seam.

- **Full-credit policy.** `SHARE_POLICY = "full"`: every present member earns the *full* reward (the
  tag-credit model that makes grouping purely rewarding). The policy is **data, not hard-coded logic**
  (Hardware Store principle): an alternative economy (even-split, diminishing returns, level-scaled)
  swaps `SHARE_POLICY` without touching the callers.
- **Progression only.** XP/JP/TP are shared; **coins and loot are not** auto-split here. Loot rules
  (round-robin, need/greed, master looter) are their own feature and their own extension point.
- **Fail-safe sharing.** An offline or callingless mate earns nothing (they cannot advance) and is
  skipped without error; delivery rides the dead-sink-safe `announce_to`.
- **The killer's own reward is untouched** (awarded by `land_hit` as before); `share_kill` only reaches
  the mates, so the seam adds sharing without double-awarding.

## Player trade: the first economy loop (`parts/world/trade.py`, MOD-04.113)

Two co-located heroes can swap goods and coin safely. `trade <player>` proposes; `trade accept` opens
the window; `trade add <item>` and `trade coins <n>` stake each side; `trade confirm` locks a side, and
when both sides have confirmed the exchange **executes atomically**. `trade cancel` (or a logout)
aborts. Built on per-player inventory (items move by carrier-tag reassignment) and the purse scalar.

- **Atomicity is the whole point.** `_execute` validates *every* staked item and coin on *both* sides
  first, then moves them all in one pass (validate-all-then-apply). A swap can never duplicate an item,
  lose one, or pay coin a hero no longer has: if anything is missing at seal time (an item dropped, coin
  spent, a partner stepped away), the entire trade aborts and nothing changes hands.
- **No confirm-then-alter.** Any change to an offer voids both confirmations, so a locked deal cannot be
  quietly changed after the other party agreed.
- **Nothing moves until the seal**, so cancel and logout unwind with nothing to restore (transient
  module registry, never persisted; `on_disconnect` hooked into both gateway teardowns).
- **Reusable pattern:** the atomic two-party exchange (validate-all-then-apply) is the seam a market /
  auction house is built on.

## Extension points (documented, not built)

- **Shared threat / aggro.** The reward half is shipped; the *threat* half (a foe engaging one member
  pulls the whole co-located party) is the natural next slice, hanging off the aggression beat and the
  same `members_in_room` seam.
- **Market / auction house.** Trade is face-to-face; an asynchronous market (list, bid, buy) is the
  next economy rung, reusing the atomic-exchange discipline.
- **Loot rules.** Round-robin / need-vs-greed / master-looter distribution of coins and drops, the
  companion to shared XP.
- **`party kick <player>`.** Leader-only removal hangs off the existing leader check; deferred as it is
  not needed for the foundation.
- **The guild.** A guild is the *persisted* big sibling of this transient primitive: a named, durable
  membership with a bank and ranks. It is a separate build, on a separate data model, and out of scope
  here.

## Testing

`tests/test_party.py` covers acceptance (form via invite+join, roster, party chat delivery, leadership
handoff, disband, logout cleanup, `members_in_room`), refusal (every validation path above), and
engine-tick reachability of both verbs through `handle_command`.
