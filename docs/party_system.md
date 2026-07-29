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

## Extension points (documented, not built)

- **Shared combat and XP.** `members_in_room(player_id, room)` returns the co-located party-mates and
  is the seam a shared-damage / split-XP system reads. It returns `[player_id]` for a lone player, so a
  caller never special-cases "no party."
- **`party kick <player>`.** Leader-only removal hangs off the existing leader check; deferred as it is
  not needed for the foundation.
- **The guild.** A guild is the *persisted* big sibling of this transient primitive: a named, durable
  membership with a bank and ranks. It is a separate build, on a separate data model, and out of scope
  here.

## Testing

`tests/test_party.py` covers acceptance (form via invite+join, roster, party chat delivery, leadership
handoff, disband, logout cleanup, `members_in_room`), refusal (every validation path above), and
engine-tick reachability of both verbs through `handle_command`.
