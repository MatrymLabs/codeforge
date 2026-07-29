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
        lines.append(f"  {mark}{i}. from {display_name(letter.sender)}: {snippet}")
    lines.append("(mail read <n>, mail delete <n>, mail send <player> <message>)")
    return "\n".join(lines)


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
