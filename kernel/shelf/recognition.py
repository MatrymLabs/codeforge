"""CARD: recognition -- per-observer name resolution (short-descriptions + personal recognition).

Harvested (clean-room, pattern-not-code) from Evennia's rpg/rpsystem contrib (BSD-3-Clause,
github.com/evennia/evennia): the mechanism where an observer sees a generated SHORT-DESCRIPTION for
a character ("a tall man") until they RECOGNIZE that character under a personal alias ("Aragorn").
This is the smallest useful core of rpsystem: sdesc + recog + a pure resolution projection. The full
emote-parsing DSL and language obfuscation are deliberately NOT harvested here (bigger, separable).

Opened by RD-2026-0007 (the Game Arm / Evennia-archaeology campaign). codeforge's chat/characters/
npcs have no recognition layer (verified gap), so this is a genuine harvest, not a duplicate.

Architecture law honored: STATE is canonical, TEXT is a projection. `resolve` never mutates; it only
projects a target's name FROM the observer's recog book and the target's sdesc. Labels are
lowercase_snake_case ids; the display string is set only at resolve time. Clean-room, stdlib only.

  sdesc:  target_id -> short description (what strangers see)
  recog:  observer_id -> { target_id -> personal alias }   (what THIS observer has learned)
  resolve(observer_id, target_id): the observer's recog for the target, else the target's sdesc
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")
DEFAULT_MAX_LENGTH = 60


class RecognitionError(ValueError):
    """Raised loud and early on an invalid id or an out-of-bounds description/alias."""


def _check_label(name: str, kind: str) -> None:
    if not isinstance(name, str) or not _LABEL.match(name):
        raise RecognitionError(f"{kind} must be lowercase_snake_case (got {name!r})")  # noqa: TRY003


def _check_text(text: str, kind: str, max_length: int) -> str:
    if not isinstance(text, str):
        raise RecognitionError(f"{kind} must be a string (got {type(text).__name__})")  # noqa: TRY003
    stripped = text.strip()
    if not stripped:
        raise RecognitionError(f"{kind} cannot be blank")  # noqa: TRY003
    if len(stripped) > max_length:
        raise RecognitionError(f"{kind} exceeds {max_length} chars (got {len(stripped)})")  # noqa: TRY003
    return stripped


@dataclass(frozen=True)
class Book:
    """The canonical recognition state: every target's sdesc + each observer's recog map.

    Frozen + copy-on-write so a resolution can never mutate the world (text is a projection).
    """

    sdescs: dict[str, str] = field(default_factory=dict)
    recogs: dict[str, dict[str, str]] = field(default_factory=dict)

    def with_sdesc(
        self, target_id: str, sdesc: str, *, max_length: int = DEFAULT_MAX_LENGTH
    ) -> Book:
        """A new Book where `target_id` presents `sdesc` to strangers. Loud on a bad id/text."""
        _check_label(target_id, "target_id")
        clean = _check_text(sdesc, "sdesc", max_length)
        return Book({**self.sdescs, target_id: clean}, self.recogs)

    def with_recog(
        self,
        observer_id: str,
        target_id: str,
        alias: str,
        *,
        max_length: int = DEFAULT_MAX_LENGTH,
    ) -> Book:
        """A new Book where `observer_id` has recognized `target_id` as `alias`. An observer may not
        recognize themselves (you already know who you are). Fails loud on a bad id/alias."""
        _check_label(observer_id, "observer_id")
        _check_label(target_id, "target_id")
        if observer_id == target_id:
            raise RecognitionError("an observer cannot recognize themselves")  # noqa: TRY003
        clean = _check_text(alias, "alias", max_length)
        observer_book = {**self.recogs.get(observer_id, {}), target_id: clean}
        return Book(self.sdescs, {**self.recogs, observer_id: observer_book})

    def forget(self, observer_id: str, target_id: str) -> Book:
        """A new Book where `observer_id` has forgotten their alias for `target_id` (back to sdesc).
        Forgetting an unknown pair is a no-op (idempotent), never an error."""
        _check_label(observer_id, "observer_id")
        _check_label(target_id, "target_id")
        if target_id not in self.recogs.get(observer_id, {}):
            return self
        observer_book = {k: v for k, v in self.recogs[observer_id].items() if k != target_id}
        return Book(self.sdescs, {**self.recogs, observer_id: observer_book})


def resolve(book: Book, observer_id: str, target_id: str) -> str:
    """Project the name `observer_id` sees for `target_id`: their recog if they have learned
    one, else the target's short-description. Raises if the target has no sdesc AND is unrecognized
    (an unknown target has no name to show - a loud gap, never a silent empty string)."""
    _check_label(observer_id, "observer_id")
    _check_label(target_id, "target_id")
    recog = book.recogs.get(observer_id, {}).get(target_id)
    if recog is not None:
        return recog
    sdesc = book.sdescs.get(target_id)
    if sdesc is None:
        raise RecognitionError(  # noqa: TRY003
            f"{observer_id} cannot name {target_id}: no recognition and no sdesc on record"
        )
    return sdesc


def resolve_all(book: Book, observer_id: str, target_ids: list[str]) -> list[str]:
    """Project the names an observer sees for a list of targets, in order (a room's occupants)."""
    return [resolve(book, observer_id, t) for t in target_ids]
