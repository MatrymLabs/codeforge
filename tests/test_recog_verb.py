"""Engine-tick test for the `recog` verb (RD-2026-0007: recognition part consumer).

A verb is not wired until handle_command proves it reachable. Proves the whole loop: two players in
a room, A privately names B; render_scene shows A the alias while others see the real name.
"""

from __future__ import annotations

import forge
from forge import handle_command, render_scene
from kernel.world.session import SESSIONS, Session


def _seat(pid: str, where: str) -> Session:
    s = Session(player_id=pid)
    s.location = where
    SESSIONS[pid] = s
    return s


def test_recog_gives_a_per_viewer_alias():
    forge._RECOG = forge.recognition.Book()  # isolate from any other test's state
    room = next(iter(forge.WORLD))
    ana = _seat("ana", room)
    _seat("bob", room)
    _seat("cid", room)
    try:
        # before: Ana sees Bob's real name in the scene
        assert "Bob is here." in render_scene(room, viewer="ana")
        # Ana privately names Bob
        out = handle_command(ana, "recog bob as Shadow")
        assert "Shadow" in out
        # after: Ana sees the alias; Cid (who did not recog) still sees the real name
        assert "Shadow is here." in render_scene(room, viewer="ana")
        assert "Bob is here." in render_scene(room, viewer="cid")
        assert "Shadow" not in render_scene(room, viewer="cid")
        # recog list shows it; forget reverts
        assert "Shadow" in handle_command(ana, "recog")
        handle_command(ana, "recog forget bob")
        assert "Bob is here." in render_scene(room, viewer="ana")
    finally:
        for pid in ("ana", "bob", "cid"):
            SESSIONS.pop(pid, None)
        forge._RECOG = forge.recognition.Book()


def test_recog_refuses_a_stranger():
    forge._RECOG = forge.recognition.Book()
    room = next(iter(forge.WORLD))
    ana = _seat("ana", room)
    try:
        out = handle_command(ana, "recog nobody as Ghost")
        assert "no one called" in out.lower()
    finally:
        SESSIONS.pop("ana", None)
        forge._RECOG = forge.recognition.Book()
