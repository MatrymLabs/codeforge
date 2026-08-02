"""CARD: guild -- a PERSISTED player organization: a named guild with ranks and a chat channel.

The party's durable big sibling. Where a party is a moment (transient, dissolves on logout), a guild
is a record: a hero's guild and rank are saved columns on their character, so the guild survives
logout and restart, and a roster names members whether or not they are online right now. Ranks are
member < officer < leader, gating who may invite, promote, and disband.

The persisted membership is the single source of truth (queried via the CharacterStore's
`members_of_guild`); a live session only mirrors it. Every membership change writes through to the
store immediately (an online member via `save_character`, an offline one via `set_guild`), so the
roster stays consistent. Pending invitations are the one transient piece, held in this module and
dropped on logout, exactly like the party's. Guild chat reaches the online members through the event
bus; it moves no world state of its own.
"""

from __future__ import annotations

import re

import kernel.world.guild_store as guild_store
from kernel.world.characters import _default_store, save_character
from kernel.world.coinage import purse
from kernel.world.events import announce_to, push_channel
from kernel.world.session import SESSIONS, Session, display_name, sentence_case

#: Guild ranks in ascending authority. A rank gate ("officer or above may invite") reads this order.
GUILD_RANKS = ("member", "officer", "leader")

#: A guild name is a lowercase label (3-21 chars), like an Order id: a stable key, shown as-is.
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{2,20}$")

# The one transient piece: an invited player id -> the guild name offered. Dropped on logout.
_INVITES: dict[str, str] = {}


def _rank_at_least(rank: str, threshold: str) -> bool:
    """True when `rank` carries at least `threshold`'s authority (member < officer < leader)."""
    try:
        return GUILD_RANKS.index(rank) >= GUILD_RANKS.index(threshold)
    except ValueError:
        return False


def _members(guild: str) -> list[str]:
    """Every member of `guild`, online or not (the persisted roster). Empty for no such guild."""
    return _default_store().members_of_guild(guild)


def _online_members(guild: str) -> list[str]:
    return [name for name in _members(guild) if SESSIONS.get(name) is not None]


def _set_membership(name: str, guild: str, rank: str) -> None:
    """Write a member's guild + rank through to the store: their live session (persisted) if online,
    or their saved row directly if offline. Keeps the persisted roster the consistent authority."""
    session = SESSIONS.get(name)
    if session is not None:
        session.guild, session.guild_rank = guild, rank
        save_character(session)
    else:
        _default_store().set_guild(name, guild, rank)


def found(session: Session, name: str) -> str:
    """Found a new guild with yourself as leader. Fails loud on an invalid or taken name, or if you
    already in a guild."""
    guild = name.strip().lower()
    if session.guild:
        return f"You are already in a guild ('{session.guild}'). Leave it first."
    if not _NAME_RE.match(guild):
        return "A guild name is 3 to 21 letters, digits, or underscores (e.g. 'ironforge')."
    if _members(guild):
        return f"A guild named '{guild}' already exists."
    _set_membership(session.player_id, guild, "leader")
    guild_store.ensure(guild)  # open the guild's treasury (at zero)
    return f"You found the guild '{guild}'. You lead it. (guild invite <player> to grow it)"


def invite(session: Session, target_name: str) -> str:
    """Officer or leader: invite an online player. Fails loud on rank, or an absent target."""
    if not session.guild:
        return "You are not in a guild. (guild found <name> to start one)"
    if not _rank_at_least(session.guild_rank, "officer"):
        return "Only an officer or the leader may invite."
    target = target_name.strip().lower()
    if not target:
        return "Invite whom? (guild invite <player>)"
    other = SESSIONS.get(target)
    if other is None:
        return f"No one named '{target}' is here to invite."
    if other.guild:
        return f"{display_name(target)} is already in a guild."
    _INVITES[target] = session.guild
    announce_to(
        [target],
        f"\n{display_name(session.player_id)} invites you to the guild '{session.guild}'."
        " (guild accept)",
    )
    return f"You invite {display_name(target)} to '{session.guild}'."


def accept(session: Session) -> str:
    """Accept a pending guild invitation and join as a member."""
    guild = _INVITES.get(session.player_id)
    if guild is None:
        return "No guild has invited you."
    if session.guild:
        _INVITES.pop(session.player_id, None)
        return f"You are already in a guild ('{session.guild}')."
    if not _members(guild):  # the guild was disbanded before you accepted
        _INVITES.pop(session.player_id, None)
        return f"The guild '{guild}' no longer exists."
    _set_membership(session.player_id, guild, "member")
    _INVITES.pop(session.player_id, None)
    announce_to(
        [m for m in _online_members(guild) if m != session.player_id],
        f"\n{display_name(session.player_id)} joins the guild.",
    )
    return f"You join the guild '{guild}'."


def leave(session: Session) -> str:
    """Leave your guild. A leader with other members must promote a new leader or disband first."""
    if not session.guild:
        return "You are not in a guild."
    guild = session.guild
    if session.guild_rank == "leader" and len(_members(guild)) > 1:
        return "As leader, promote a new leader (guild promote <player>) or disband before leaving."
    others = [m for m in _online_members(guild) if m != session.player_id]
    _set_membership(session.player_id, "", "")
    announce_to(others, f"\n{display_name(session.player_id)} leaves the guild.")
    return f"You leave the guild '{guild}'."


def disband(session: Session) -> str:
    """Leader only: dissolve the guild for every member, online or not."""
    if not session.guild:
        return "You are not in a guild."
    if session.guild_rank != "leader":
        return "Only the guild leader may disband it."
    guild = session.guild
    others = [m for m in _online_members(guild) if m != session.player_id]
    for name in _members(guild):
        _set_membership(name, "", "")
    guild_store.remove(guild)  # the treasury dissolves with the guild
    announce_to(others, f"\nThe guild '{guild}' is disbanded.")
    return f"You disband the guild '{guild}'."


def promote(session: Session, target_name: str) -> str:
    """Leader only: raise a guild-mate one rank (member -> officer -> leader). Promoting a member to
    leader TRANSFERS leadership: the old leader steps down to officer."""
    if not session.guild:
        return "You are not in a guild."
    if session.guild_rank != "leader":
        return "Only the guild leader may promote."
    target = target_name.strip().lower()
    if target == session.player_id:
        return "You already lead the guild."
    if target not in _members(session.guild):
        return f"'{target}' is not in your guild."
    current = _rank_of(target, session.guild)
    if current == "officer":  # officer -> leader: a leadership transfer
        _set_membership(target, session.guild, "leader")
        _set_membership(session.player_id, session.guild, "officer")
        announce_to(
            _online_members(session.guild),
            f"\n{display_name(target)} now leads the guild.",
        )
        return f"You hand leadership of '{session.guild}' to {display_name(target)}."
    _set_membership(target, session.guild, "officer")  # member -> officer
    announce_to(_online_members(session.guild), f"\n{display_name(target)} is now an officer.")
    return f"You promote {display_name(target)} to officer."


def _rank_of(name: str, guild: str) -> str:
    """A member's rank, read from their live session or their saved row."""
    session = SESSIONS.get(name)
    if session is not None and session.guild == guild:
        return session.guild_rank
    record = _default_store().find(name)
    return record.guild_rank if record is not None and record.guild == guild else ""


def guild_say(session: Session, message: str) -> str:
    """Speak on the guild channel (reaches online guild-mates). Fails loud if guildless/empty."""
    if not session.guild:
        return "You are not in a guild."
    text = message.strip()
    if not text:
        return "Say what to the guild? (gsay <message>)"
    announce_to(
        [m for m in _online_members(session.guild) if m != session.player_id],
        f"\n[Guild] {display_name(session.player_id)}: {text}",
    )
    push_channel(
        _online_members(session.guild), "guild", display_name(session.player_id), text
    )  # structured twin, includes the speaker so their own guild pane logs it
    return f"[Guild] You: {text}"


def render_guild(session: Session) -> str:
    """The roster: every member (online or not) with their rank, the leader and offline marked."""
    if not session.guild:
        return "You are not in a guild. (guild found <name> to start one)"
    members = _members(session.guild)
    lines = [f"The guild '{session.guild}' ({len(members)} members):"]
    rank_order = {"leader": 0, "officer": 1, "member": 2}
    ordered = sorted(members, key=lambda m: (rank_order.get(_rank_of(m, session.guild), 9), m))
    for name in ordered:
        rank = _rank_of(name, session.guild)
        here = "" if SESSIONS.get(name) is not None else "  [offline]"
        lines.append(f"  {display_name(name)} ({rank}){here}")
    return "\n".join(lines)


def bank_balance(session: Session) -> str:
    """Show the guild's shared treasury. Any member may look."""
    if not session.guild:
        return "You are not in a guild."
    return f"The guild '{session.guild}' treasury holds {purse(guild_store.coins(session.guild))}."


def bank_deposit(session: Session, amount_word: str) -> str:
    """Deposit coin from your purse into the guild treasury. Any member may give."""
    if not session.guild:
        return "You are not in a guild."
    amount = _parse_amount(amount_word)
    if amount is None or amount <= 0:
        return "Deposit how many coins? (guild deposit <number>)"
    if amount > session.coins:
        return "You do not have that many coins."
    session.coins -= amount
    save_character(session)  # the purse is persisted; keep it and the treasury in step
    balance = guild_store.adjust(session.guild, amount)
    announce_to(
        [m for m in _online_members(session.guild) if m != session.player_id],
        f"\n{display_name(session.player_id)} deposits {amount} coins into the guild treasury.",
    )
    return f"You deposit {amount} coins. The treasury holds {purse(balance)}."


def bank_withdraw(session: Session, amount_word: str) -> str:
    """Withdraw coin from the treasury into your purse. Officer or leader only, so a member cannot
    drain the guild funds."""
    if not session.guild:
        return "You are not in a guild."
    if not _rank_at_least(session.guild_rank, "officer"):
        return "Only an officer or the leader may withdraw from the treasury."
    amount = _parse_amount(amount_word)
    if amount is None or amount <= 0:
        return "Withdraw how many coins? (guild withdraw <number>)"
    if amount > guild_store.coins(session.guild):
        return "The treasury does not hold that many coins."
    balance = guild_store.adjust(session.guild, -amount)
    session.coins += amount
    save_character(session)
    announce_to(
        [m for m in _online_members(session.guild) if m != session.player_id],
        f"\n{display_name(session.player_id)} withdraws {amount} coins from the guild treasury.",
    )
    return f"You withdraw {amount} coins. The treasury holds {purse(balance)}."


# --- the guild item-vault: shared storage, the coin treasury's item twin ----------------------
def _guild_vault(guild: str) -> str:
    """The storage owner key for a guild's shared item vault (a non-player owner on the items)."""
    return f"guildvault:{guild}"


def vault_render(session: Session) -> str:
    """The guild's shared item vault, numbered. Any member may look."""
    from kernel.world import loose_store

    if not session.guild:
        return "You are not in a guild."
    stored = loose_store.contents(_guild_vault(session.guild))
    if not stored:
        return f"The '{session.guild}' vault is empty. (guild vault deposit <item>)"
    lines = [f"The '{session.guild}' vault ({len(stored)}):"]
    for i, (_row_id, snap) in enumerate(stored, 1):
        lines.append(f"  {i}. {sentence_case(str(snap['name']))}")
    lines.append("(guild vault deposit <item>, guild vault withdraw <n>)")
    return "\n".join(lines)


def vault_deposit(session: Session, keyword: str) -> str:
    """Contribute a carried item to the guild vault. Any member may give (like a coin deposit)."""
    from kernel.world import loose_store
    from kernel.world.characters import snapshot_item
    from kernel.world.items import ITEMS, carrier, trace_item

    if not session.guild:
        return "You are not in a guild."
    kw = keyword.strip().lower()
    if not kw:
        return "Deposit what? (guild vault deposit <item>)"
    iid = trace_item(kw, carrier(session.player_id))
    if iid is None:
        return "You aren't carrying that."
    if iid in set(session.equipped.values()):
        return "That is worn. Unequip it before you bank it."
    snapshot = snapshot_item(iid)
    if snapshot is None:
        return "You aren't carrying that."
    name = ITEMS[iid]["name"]
    loose_store.stow(_guild_vault(session.guild), snapshot)
    ITEMS.pop(iid, None)
    announce_to(
        [m for m in _online_members(session.guild) if m != session.player_id],
        f"\n{display_name(session.player_id)} deposits {name} into the guild vault.",
    )
    return f"You deposit {name} into the guild vault."


def vault_withdraw(session: Session, arg: str) -> str:
    """Take an item from the guild vault. Officer or leader only, so a member cannot loot the
    guild's shared goods (the same gate the coin treasury keeps)."""
    from kernel.world import loose_store
    from kernel.world.characters import reclone_item
    from kernel.world.items import carrier

    if not session.guild:
        return "You are not in a guild."
    if not _rank_at_least(session.guild_rank, "officer"):
        return "Only an officer or the leader may withdraw from the guild vault."
    stored = loose_store.contents(_guild_vault(session.guild))
    if not stored:
        return "The guild vault is empty."
    picked = loose_store.match(stored, arg)
    if picked is None:
        return "The vault holds nothing like that. (guild vault to list it)"
    taken = loose_store.take(picked[0], _guild_vault(session.guild))
    if taken is None:
        return "It is no longer in the vault."
    reclone_item(taken, carrier(session.player_id))
    announce_to(
        [m for m in _online_members(session.guild) if m != session.player_id],
        f"\n{display_name(session.player_id)} withdraws {taken['name']} from the guild vault.",
    )
    return f"You withdraw {taken['name']} from the guild vault."


def _parse_amount(word: str) -> int | None:
    try:
        return int(word.strip())
    except ValueError:
        return None


def on_disconnect(player_id: str) -> None:
    """Logout cleanup: drop any pending guild invitation to or from the departing hero. The guild
    membership itself persists (that is the point); only the transient invite is cleared."""
    _INVITES.pop(player_id, None)


def _reset() -> None:
    """Clear pending invites. For tests, so one test's offers never leak into the next."""
    _INVITES.clear()
