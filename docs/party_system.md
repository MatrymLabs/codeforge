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

## Mail: the async channel (`parts/world/mail.py` + `mail_store.py`, MOD-04.117/118)

Party and guild chat reach whoever is online *now*; **mail** reaches a hero who is offline and waits
in their inbox until they read it. A letter is a persisted row (the `mail` table, `MailRow`; migration
`a3e7c9b1d5f4`). `mail send <player> <message>` posts to any real character (validated against the
character store, online or not, and nudged if online); bare `mail` lists the inbox newest-first with
unread starred; `mail read <n>` shows a letter and clears its unread mark; `mail delete <n>` discards
one.

- **Bounded + safe.** A body is capped at `MAX_BODY` and an inbox at `MAX_INBOX` (a mailbox cannot be
  flooded); the body is plain text the transport sanitizes on the way out; `delete` is scoped to the
  recipient in the store, so no one removes another's mail by guessing an id.
- **Value-object boundary.** The store returns a `Letter` value object, never an ORM row.

## The guild: a persisted organization (`parts/world/guild.py`, MOD-04.115)

The party's durable big sibling. Where a party is a moment (transient), a **guild is a record**: a
hero's `guild` and `guild_rank` are saved columns on their character (migration `e7a3c1b5f2d8`), so
the guild survives logout and restart, and its roster names members whether or not they are online.

- **Verbs:** `guild found <name>` | `invite <player>` | `accept` | `promote <player>` | `leave` |
  `disband`; bare `guild` is the roster; `gsay <message>` is guild chat.
- **Ranks** are `member < officer < leader`: an officer or leader may invite, the leader may promote
  and disband. Promoting a member to leader **transfers leadership** (the old leader steps down to
  officer), which is how a leader hands off before leaving.
- **The persisted membership is the source of truth.** The `CharacterStore` gained
  `members_of_guild` (the full roster, including offline members) and `set_guild` (write a member's
  columns, even an offline one). Every change writes through immediately (an online member via
  `save_character`, an offline one via `set_guild`), so `disband` clears *every* member's row and the
  roster is always consistent. A live session only mirrors the stored fact.
- **Only the invitation is transient** (in-memory, dropped on logout, like the party's); the
  membership itself persists, which is the whole point.
### The guild bank (`parts/world/guild_store.py`, MOD-04.116)

A guild's shared **treasury**: guild-level coin, persisted in its own `guilds` table (`GuildRow`;
migration `f1b9d3e6c284`), created when the guild founds and dropped on disband. `guild deposit <n>`
moves coin from your purse into the treasury (any member may give); `guild withdraw <n>` moves it back
(officer or leader only, so a member cannot drain the guild funds); `guild bank` shows the balance.
Both purse and treasury are persisted and kept in step. Guild-level state lives here, distinct from
the per-member columns on characters.

- **Coin-only for now.** A guild *item* vault is a documented extension: it needs loose-item
  persistence first (today only equipped gear persists), so v1 banks coin.

- **Further extensions:** a message of the day, a guild level, guild quests.

## Shared combat: the loot half (`parts/world/party_loot.py`, MOD-04.114)

The XP half pays everyone; this is the loot half. A solo hero's kill still drops to the floor to be
taken (unchanged). But when a party fells a foe, each drop is **awarded to a co-located mate by
round-robin** and moved straight into their hands, so nobody races for the floor and the haul is
shared fairly over a fight. It hangs off combat's single loot-spawn seam (`_spawn_loot`) with one
call, reading the party's `members_in_room` and moving the drop by carrier-tag reassignment
(per-player inventory).

- **`LOOT_POLICY = "round-robin"`** is the data-driven policy seam: a need-vs-greed roll, a master
  looter, or free-for-all would branch here without touching combat.
- **Solo behavior is untouched** (a lone or alone-here hero's loot falls to the floor, first-come).

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

## Friends (the personal roster)

Party, guild, and mail are *shared* channels; a friends list is one hero's own private ledger of
people worth keeping track of. It is deliberately the smallest social primitive: `parts/world/friends.py`
(MOD-04.119), one comma-joined column on the character row, no new table beyond a column migration.

- **One-directional by design.** Your list is yours. `friend add <player>` puts a name on *your* roster
  and does not touch theirs, enlist them in anything, or notify them. The only power a friends list
  holds is sight.
- **Validated, bounded, persisted.** A name is added only after the character store confirms a real
  hero wears it (a friend may be offline, so we check the store, not who is logged in). The list is
  capped at `MAX_FRIENDS` to bound growth, and serialize/restore mirror the professions/reputation
  columns so the roster survives a logout.
- **`friends` shows who is around.** The render lists online friends first, each marked online/offline,
  so a returning hero sees at a glance who is available to adventure with. `friend` and `friends` are
  both filed verbs (CMD-04.105 / CMD-04.106) routing to one dispatcher.

### A note on the import cycle

`characters` imports `friends` at module load (for the column's serialize/restore), so `friends` must
*not* import `characters` at the top level. The two functions that need the store (`add`, `_character_exists`)
and `save_character` import them lazily inside the call; serialize/restore touch only the session and
carry no such import. This keeps the boundary one-way and the closure test green.

### Testing

`tests/test_friends.py` covers acceptance (add a real hero, render's online/offline marks, remove,
save+restore round-trip, the one-directional guarantee), refusal (missing name, yourself, unknown hero,
duplicate, full list, removing a non-friend), a serialize/restore round-trip, and engine-tick
reachability of the `friend`/`friends` verbs through `handle_command`.

## Chat (the world channel)

The widest voice in the social layer. Party reaches your band, guild reaches your order, mail reaches
one offline hero; `chat <message>` reaches *everyone* online at that moment, the town square of the
whole world. `parts/world/chat.py` (MOD-04.120), verb `chat` (CMD-04.107).

- **Transient by nature.** A live channel carries a line of text and nothing else; it persists nothing
  and moves no world state. Delivery is `events.announce_to(roster(), exclude=self)`, so offline heroes
  are simply skipped and the speaker hears their own line only as the `[World] You:` confirmation.
- **Validated.** A speaker must be a named hero already in the world (the login desk does not chat) and
  a message must not be empty; both refusals fail loud and broadcast nothing.
- **Smallest useful version.** A per-speaker rate limit and an opt-out mute are documented extension
  points, deliberately not built until a crowd is large enough to need them.

### Testing

`tests/test_chat.py` covers acceptance (a shout reaches every other hero but not the speaker's own
channel, message case preserved), refusal (empty message, an unnamed speaker still at the login desk),
and engine-tick reachability of the `chat` verb through `handle_command`.
