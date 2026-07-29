"""CARD: maintenance_mode -- a runtime gate that closes the forge to non-staff for a clean shutdown.

An operations control, not world state. When maintenance is ON, the login front desk turns away
anyone below wizard rank with a stated reason, so staff can drain and stop the server (autosave +
save-on-shutdown handle the persistence) without new players walking into a world about to sleep.
Wizards and the owner still get in, to verify or to keep working.

Deliberately transient: the flag lives in this module for the process lifetime and is NOT persisted.
A restart clears it, which is correct -- a fresh boot is not in maintenance until an admin says so.
The three readers (is_on / reason, plus enable / disable) are the whole surface; the gateway reads
them at the door and the `@maintenance` verb writes them.
"""

from __future__ import annotations

_STATE: dict[str, object] = {"on": False, "reason": ""}

_DEFAULT_REASON = "scheduled maintenance"


def enable(reason: str = "") -> str:
    """Close the forge to non-staff. Returns the reason now in effect (a blank falls back to a
    generic one, so the door always has something honest to say)."""
    _STATE["on"] = True
    _STATE["reason"] = reason.strip() or _DEFAULT_REASON
    return str(_STATE["reason"])


def disable() -> None:
    """Re-open the forge to everyone."""
    _STATE["on"] = False
    _STATE["reason"] = ""


def is_on() -> bool:
    """True while the forge is closed to non-staff."""
    return bool(_STATE["on"])


def reason() -> str:
    """The current maintenance reason, or "" when open."""
    return str(_STATE["reason"])
