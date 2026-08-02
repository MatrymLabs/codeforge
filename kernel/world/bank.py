"""CARD: bank -- a hero's personal vault: put items away, and they wait until you want them back.

The first thing the loose-item persistence keystone unlocks. Where the bag is what you carry, the
vault is what you store: an item you deposit LEAVES the world (it is not carried, not on any floor)
and sits in storage under a non-player owner (`vault:<hero>`) on the same items table, until you
withdraw it back into your bag. So a spare sword is safe between sessions and out of your pack.

It composes the pieces already built: `loose_store.stow/take/contents` move a single item in and out
of storage (the item-level twin of the whole-bag save/load), and `characters.snapshot_item` /
`reclone_item` turn a live instance into a stored snapshot and back, rolled affixes intact. No coin,
no other player, no atomicity across accounts here: a personal vault is the simplest use of the
non-player-owner pattern that guild vaults, mail attachments, and the auction house all extend.
"""

from __future__ import annotations

from kernel.world.session import Session, sentence_case


def _vault(player_id: str) -> str:
    """The storage owner key for a hero's personal vault (a non-player owner on the items table)."""
    return f"vault:{player_id}"


def deposit(session: Session, keyword: str) -> str:
    """`bank deposit <item>`: put a carried item away into your vault. Refused for a bad word or a
    worn item (unequip it first); worn gear persists on its own and is not loose to store."""
    from kernel.world import loose_store
    from kernel.world.characters import snapshot_item
    from kernel.world.items import ITEMS, carrier, trace_item

    kw = keyword.strip().lower()
    if not kw:
        return "Deposit what? (bank deposit <item>)"
    iid = trace_item(kw, carrier(session.player_id))
    if iid is None:
        return "You aren't carrying that."
    if iid in set(session.equipped.values()):
        return "That is worn. Unequip it before you bank it."
    snapshot = snapshot_item(iid)
    if snapshot is None:
        return "You aren't carrying that."
    name = ITEMS[iid]["name"]
    loose_store.stow(_vault(session.player_id), snapshot)
    ITEMS.pop(iid, None)  # it leaves the world, into the vault
    return f"You deposit {name} into your vault."


def withdraw(session: Session, arg: str) -> str:
    """`bank withdraw <n|item>`: take a vaulted item back into the bag, by its list number or a
    word from its name. Refused when the vault is empty or nothing matches."""
    from kernel.world import loose_store
    from kernel.world.characters import reclone_item
    from kernel.world.items import carrier

    stored = loose_store.contents(_vault(session.player_id))
    if not stored:
        return "Your vault is empty. (bank deposit <item>)"
    picked = loose_store.match(stored, arg)
    if picked is None:
        return "You have nothing like that in your vault. (bank to list it)"
    row_id, _snap = picked
    taken = loose_store.take(row_id, _vault(session.player_id))
    if taken is None:
        return "It is no longer in your vault."
    reclone_item(taken, carrier(session.player_id))
    return f"You withdraw {taken['name']} from your vault."


def render(session: Session) -> str:
    """The vault's contents, numbered so `bank withdraw <n>` can name one."""
    from kernel.world import loose_store

    stored = loose_store.contents(_vault(session.player_id))
    if not stored:
        return "Your vault is empty. (bank deposit <item>)"
    lines = [f"Your vault ({len(stored)}):"]
    for i, (_row_id, snap) in enumerate(stored, 1):
        lines.append(f"  {i}. {sentence_case(str(snap['name']))}")
    lines.append("(bank deposit <item>, bank withdraw <n>)")
    return "\n".join(lines)
