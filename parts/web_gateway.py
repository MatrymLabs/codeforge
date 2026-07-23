"""CARD: web_gateway -- the browser gate: play the forge over a WebSocket.

The engine's fourth driver, and the first one a stranger can click. A
single-page xterm terminal opens a WebSocket to /ws; this module runs the
same front-desk-then-tick ritual as the TCP gateway, but over WS text
frames on the asyncio loop. handle_command stays the only door -- the
dialogue out here only assembles tick commands, same law as every gate.

Built for a PUBLIC demo, so it is deliberately hostile to abuse: an
ephemeral database (point CODEFORGE_DB at tmp), a seat cap, and an idle
timeout, so a link on a resume cannot be farmed or accrete state. No admin
surface is mounted here; @-verbs stay rank-gated in the tick and a demo
visitor is only ever rank 'player'.
"""

from __future__ import annotations

import asyncio
import contextlib
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

from forge import handle_command, render_scene
from parts.gateway import (
    IDLE_TIMEOUT,
    MAX_CONNECTIONS,
    TICK_LOCK,
    _next_player_id,
    _sanitize,
)
from parts.world.accounts import password_fixable
from parts.world.characters import save_character
from parts.world.events import bind_echo, unbind_echo
from parts.world.seed import load_splash
from parts.world.session import SESSIONS, Session

_PAGE = (Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")

app = FastAPI(title="CodeForge -- play in the browser", docs_url=None, redoc_url=None)

# One shared counter for the seats the browser gate has filled. All WS
# handlers live on a single asyncio loop, so a plain int with no await
# between check-and-claim is race-free.
_web_seats = 0


@app.get("/health")
async def health() -> dict[str, str | int]:
    return {"status": "alive", "engine": "codeforge", "surface": "web", "seats": _web_seats}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _PAGE


async def _pump(ws: WebSocket, outbox: asyncio.Queue[str]) -> None:
    """The one mouth: every line the visitor should see -- prompts, tick
    responses, and broadcasts from other players' sinks -- leaves through
    here, in order. Keeping sends single-writer avoids interleaved frames.
    Every line is sanitized at this transport edge (as the TCP gateway's _send
    does), so player-supplied chat can't inject terminal escapes into another
    visitor's xterm.js session -- this is the public, internet-facing surface."""
    while True:
        await ws.send_text(_sanitize(await outbox.get()))


async def _recv(ws: WebSocket) -> str:
    """One line in, or the visitor is gone. Silence past the idle timeout
    counts as leaving -- a dead socket must never pin a seat forever."""
    return await asyncio.wait_for(ws.receive_text(), timeout=IDLE_TIMEOUT)


async def _ask(ws: WebSocket, outbox: asyncio.Queue[str], prompt: str) -> str:
    outbox.put_nowait(prompt)
    return (await _recv(ws)).strip()


_REGISTER_TRIES = 3


async def _register_dialogue(ws: WebSocket, outbox: asyncio.Queue[str], session: Session) -> str:
    """NEW-account sub-dialogue over WS: a password the tick rejects (too short, or
    wrong for an existing account) re-prompts the password in place -- keeping the
    chosen handle -- instead of dropping to the top menu. Returns the final response."""
    handle = await _ask(ws, outbox, "Choose your character@account:")
    response = ""
    for attempt in range(_REGISTER_TRIES):
        secret = await _ask(ws, outbox, "Choose a password:")
        with TICK_LOCK:
            response = handle_command(session, f"register {handle} {secret}")
        if not password_fixable(response) or attempt == _REGISTER_TRIES - 1:
            return response
        outbox.put_nowait(response)  # nudge, then re-ask the password in place
    return response


async def _front_desk(ws: WebSocket, outbox: asyncio.Queue[str], session: Session) -> bool:
    """The connection ritual over WS: authenticate before the world. The
    dialogue assembles login/register tick commands; the tick decides."""
    outbox.put_nowait(load_splash())
    for _ in range(3):
        who = (await _ask(ws, outbox, "Character (character@account) or NEW:")).lower()
        if not who:
            outbox.put_nowait("Login required: enter your character@account, or type NEW.")
            continue
        if who == "new":
            response = await _register_dialogue(ws, outbox, session)
        else:
            secret = await _ask(ws, outbox, "Password:")
            with TICK_LOCK:
                response = handle_command(session, f"login {who} {secret}")
        outbox.put_nowait(response)
        if response.startswith("Welcome back,"):
            return True  # the restore response already rendered the scene
        if response.startswith("Welcome,"):
            outbox.put_nowait(render_scene(session.location, viewer=session.player_id))
            return True
    outbox.put_nowait("Too many attempts. The door closes.")
    return False


async def _world_loop(ws: WebSocket, outbox: asyncio.Queue[str], session: Session) -> None:
    """One command in, one response out -- the tick, driven from a browser."""
    while session.alive:
        text = await _recv(ws)
        if not text.strip():
            continue
        with TICK_LOCK:
            response = handle_command(session, text)
        if response:
            outbox.put_nowait(response)


@app.websocket("/ws")
async def play(ws: WebSocket) -> None:
    global _web_seats
    if _web_seats >= MAX_CONNECTIONS:
        await ws.accept()
        await ws.send_text("The forge is full right now. Try again shortly.")
        await ws.close()
        return
    # Claim the seat, then do ALL of setup inside the try -- so if accept() or the
    # registration raises (a client aborting the handshake is routine on a public link:
    # health probes, scanners, bots), the finally still frees the seat. Otherwise the
    # counter climbs monotonically and, after MAX_CONNECTIONS aborts, turns real
    # visitors away forever -- an unauthenticated denial of the demo.
    _web_seats += 1
    outbox: asyncio.Queue[str] = asyncio.Queue()
    session = Session(player_id=_next_player_id())
    mouth: asyncio.Task[None] | None = None
    entered = False
    try:
        await ws.accept()
        with TICK_LOCK:
            SESSIONS[session.player_id] = session
            bind_echo(session.player_id, outbox.put_nowait)
        mouth = asyncio.create_task(_pump(ws, outbox))
        entered = await _front_desk(ws, outbox, session)
        if entered:
            await _world_loop(ws, outbox, session)
    except (WebSocketDisconnect, TimeoutError):
        pass  # visitor left or idled out -- fall through to teardown
    finally:
        if mouth is not None:
            mouth.cancel()
        # Deliver any last queued line -- the quit farewell, a final broadcast --
        # before closing. If the visitor already hung up, these sends no-op.
        with contextlib.suppress(WebSocketDisconnect, RuntimeError, OSError):
            while not outbox.empty():
                await ws.send_text(_sanitize(outbox.get_nowait()))
        with TICK_LOCK:
            if entered:
                save_character(session)  # only real (registered) players persist
            unbind_echo(session.player_id)
            SESSIONS.pop(session.player_id, None)
        _web_seats -= 1
        with contextlib.suppress(RuntimeError):
            await ws.close()  # already closed if the visitor hung up
