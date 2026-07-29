"""CARD: mail -- asynchronous letters between heroes (send now, read later).

The social layer's patient channel: where party/guild chat reach whoever is online right now, mail
reaches a hero who is offline, and waits in their inbox until they read it. A letter is a persisted
row (mail_store); this module is the rules on top: who may be written to, how long a letter may be,
how full an inbox gets, and how the inbox reads. It moves no world state and stores no auth.

A letter may be sent to any real character, online or not (that is the point). The body is plain
text the transport sanitizes on the way out; nothing here executes it. Inbox growth is bounded so a
mailbox cannot be flooded without limit.
"""

from __future__ import annotations

from datetime import UTC, datetime

import parts.world.mail_store as mail_store
from parts.world.characters import _default_store
from parts.world.events import announce_to
from parts.world.session import SESSIONS, Session, display_name

MAX_BODY = 500  # the longest a single letter may be
MAX_INBOX = 50  # the most letters an inbox may hold (bounds flooding)


def _character_exists(name: str) -> bool:
    """True if `name` is a real saved hero (mail reaches the offline, so we check the store, not
    who is logged in)."""
    return _default_store().find(name) is not None


def send(session: Session, arg: str) -> str:
    """`mail send <player> <message>`: post a letter. Fails loud on a missing recipient/message, an
    over-long body, an unknown hero, or a full inbox."""
    parts = arg.split(maxsplit=1)
    if len(parts) < 2:
        return "Write to whom, and what? (mail send <player> <message>)"
    target, message = parts[0].strip().lower(), parts[1].strip()
    if not message:
        return "Your letter is empty."
    if len(message) > MAX_BODY:
        return f"A letter is at most {MAX_BODY} characters (yours is {len(message)})."
    if not _character_exists(target):
        return f"There is no hero named '{target}' to write to."
    if mail_store.count(target) >= MAX_INBOX:
        return f"{display_name(target)}'s inbox is full; your letter is returned."
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    mail_store.send(target, session.player_id, message, sent_utc=stamp)
    if SESSIONS.get(target) is not None:  # a live nudge if they happen to be online
        announce_to([target], f"\nYou have new mail from {display_name(session.player_id)}. (mail)")
    return f"Your letter is sent to {display_name(target)}."


def render_inbox(session: Session) -> str:
    """The inbox, newest first, unread marked with a star."""
    letters = mail_store.inbox(session.player_id)
    if not letters:
        return "Your inbox is empty."
    lines = [f"Your inbox ({len(letters)}/{MAX_INBOX}):"]
    for i, letter in enumerate(letters, 1):
        mark = " " if letter.read else "*"
        snippet = letter.body[:40] + ("..." if len(letter.body) > 40 else "")
        parcel = f"  [+ {letter.attachment['name']}]" if letter.attachment else ""
        lines.append(f"  {mark}{i}. from {display_name(letter.sender)}: {snippet}{parcel}")
    lines.append("(mail read <n>, mail claim <n>, mail send/gift <player> ...)")
    return "\n".join(lines)


def gift(session: Session, arg: str) -> str:
    """`mail gift <player> <item>`: mail a carried item to a hero (online or not). It waits in their
    inbox as a parcel until they `mail claim` it. Fails loud on a bad target, a full inbox, an item
    you are not carrying, or a worn item."""
    from parts.world.characters import snapshot_item
    from parts.world.items import ITEMS, carrier, trace_item

    parts = arg.split(maxsplit=1)
    if len(parts) < 2:
        return "Gift whom, and what? (mail gift <player> <item>)"
    target, item_kw = parts[0].strip().lower(), parts[1].strip().lower()
    if not _character_exists(target):
        return f"There is no hero named '{target}' to send to."
    if mail_store.count(target) >= MAX_INBOX:
        return f"{display_name(target)}'s inbox is full; your parcel is returned."
    iid = trace_item(item_kw, carrier(session.player_id))
    if iid is None:
        return "You aren't carrying that."
    if iid in set(session.equipped.values()):
        return "That is worn. Unequip it before you mail it."
    snapshot = snapshot_item(iid)
    if snapshot is None:
        return "You aren't carrying that."
    name = ITEMS[iid]["name"]
    stamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = f"A parcel from {display_name(session.player_id)}."
    mail_store.send(target, session.player_id, body, sent_utc=stamp, attachment=snapshot)
    ITEMS.pop(iid, None)  # it leaves your bag, into the mail
    if SESSIONS.get(target) is not None:
        announce_to([target], f"\nA parcel from {display_name(session.player_id)} awaits. (mail)")
    return f"You mail {name} to {display_name(target)}."


def claim(session: Session, n_word: str) -> str:
    """`mail claim <n>`: take the item attached to the nth letter into your bag (once)."""
    from parts.world.characters import reclone_item
    from parts.world.items import carrier

    letters = mail_store.inbox(session.player_id)
    letter = _pick(letters, n_word)
    if letter is None:
        return "No such letter. (mail to list your inbox)"
    if letter.attachment is None:
        return "That letter carries no parcel."
    snapshot = mail_store.claim(letter.id, session.player_id)
    if snapshot is None:
        return "There is nothing left to claim."
    reclone_item(snapshot, carrier(session.player_id))
    return f"You claim {snapshot['name']} from the letter."


def read_mail(session: Session, n_word: str) -> str:
    """`mail read <n>`: read the nth letter (as listed) in full and mark it read."""
    letters = mail_store.inbox(session.player_id)
    letter = _pick(letters, n_word)
    if letter is None:
        return "No such letter. (mail to list your inbox)"
    mail_store.mark_read(letter.id)
    return f"From {display_name(letter.sender)} ({letter.sent_utc}):\n{letter.body}"


def delete_mail(session: Session, n_word: str) -> str:
    """`mail delete <n>`: discard the nth letter."""
    letters = mail_store.inbox(session.player_id)
    letter = _pick(letters, n_word)
    if letter is None:
        return "No such letter to delete."
    mail_store.delete(letter.id, session.player_id)
    return "The letter is discarded."


def _pick(letters: list[mail_store.Letter], n_word: str) -> mail_store.Letter | None:
    """The letter at 1-based position `n_word`, or None if out of range or unparsable."""
    try:
        n = int(n_word.strip())
    except (ValueError, AttributeError):
        return None
    return letters[n - 1] if 1 <= n <= len(letters) else None
