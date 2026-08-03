"""CARD: ondemand_stage -- derive a time-staged state only when observed (no background ticking).

Harvested clean-room from Evennia scripts/ondemandhandler (BSD-3-Clause).
Reimplemented from behavior, not source: instead of a script that fires on a
timer to advance a crop, a torch, or a wound, we store only a start beat and a
stage table and DERIVE the current stage the moment something looks at it.

This fits codeforge's "derive, don't store" law and its 1M-room scale: a million
crops cost nothing until observed, and there is no background timer to run.

Pure functions only: no mutation, no I/O, no timers. Fail loud via StageError.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# A stage name is lowercase snake_case: a word, optionally _-joined to more words.
_SNAKE_RE = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class StageError(ValueError):
    """Raised loud on a malformed stage table or an impossible time query."""


@dataclass(frozen=True)
class Stage:
    """One stage in a derived timeline: a name and the elapsed-beat threshold it begins at."""

    name: str
    at_beat: int


def _validate(stages: list[Stage]) -> None:
    """Guard the stage table: non-empty, first threshold 0, strictly increasing, snake_case."""
    if not stages:
        raise StageError("stages must be non-empty")
    if stages[0].at_beat != 0:
        raise StageError(f"first stage must start at beat 0, got {stages[0].at_beat}")
    previous = -1
    for stage in stages:
        if not _SNAKE_RE.match(stage.name):
            raise StageError(f"stage name {stage.name!r} must be lowercase snake_case")
        if stage.at_beat <= previous:
            raise StageError(
                f"stage at_beats must strictly increase, {stage.at_beat} follows {previous}"
            )
        previous = stage.at_beat


def stage_at(stages: list[Stage], start_beat: int, now_beat: int) -> Stage:
    """Derive the current stage: the last stage whose at_beat <= elapsed beats.

    elapsed = now_beat - start_beat. Before the first non-zero threshold the
    stage is stage 0; past the last threshold the stage is the last stage.
    """
    _validate(stages)
    if now_beat < start_beat:
        raise StageError(f"now_beat {now_beat} precedes start_beat {start_beat}")
    elapsed = now_beat - start_beat
    current = stages[0]
    for stage in stages:
        if stage.at_beat <= elapsed:
            current = stage
        else:
            break
    return current


def progress(
    stages: list[Stage], start_beat: int, now_beat: int
) -> tuple[Stage, Stage | None, int]:
    """Report (current stage, next stage or None, beats until next stage or 0).

    When the current stage is the last one, next is None and the countdown is 0.
    """
    current = stage_at(stages, start_beat, now_beat)
    index = stages.index(current)
    if index + 1 >= len(stages):
        return current, None, 0
    upcoming = stages[index + 1]
    elapsed = now_beat - start_beat
    beats_until_next = upcoming.at_beat - elapsed
    return current, upcoming, beats_until_next
