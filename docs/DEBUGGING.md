# Case File: The Dead Sink

A debugging story from CodeForge — the kind of intermittent, "impossible" bug
that only yields to a controlled reproduction. Written up because *how* a bug is
cornered says more about an engineer than the diff that fixes it.

## Symptom

One player typed a normal command — `say hi`, or a step north — and **their**
command crashed the server thread, dropping *them*, even though they had done
nothing wrong. It was intermittent. It never happened when I tested the client
by hand. It only showed up "in the wild," through the full launch ritual
(`make` → `bash` → a backgrounded server) with more than one connection.

## First (wrong) instinct

The traceback pointed at a broadcast: `OSError: [Errno 9] Bad file descriptor`,
raised while delivering a room event. The tempting read was "the acting player's
socket died." But the acting player was fine — they were mid-command. So *whose*
descriptor was bad?

## The reproduction

The bug vanished under a pipe and reappeared only through the ritual, which was
the tell: this was a **process-group / terminal-state** effect, not pure logic.
A bug that behaves differently under `make → bash → backgrounded server` than it
does when you run the binary directly needs a real terminal to reproduce — so I
drove it under a **PTY** (`pty.fork`), with a second, deliberately half-dead
connection in the same room. That reproduced it every time. The server log's
`BrokenPipeError` confirmed the direction: the *peer* closed first, not us.

## Root cause

The event bus fanned a room event out to **every** session's echo sink. When one
of those sinks belonged to a client whose socket had already closed, the write
raised — and the exception propagated **up the call stack of the player who
triggered the broadcast**. One dead spectator could kill a live actor's command.
A second, quieter contributor: a session that dropped *during* the login
handshake could leave its sink bound, so it lingered as a landmine for the next
broadcast.

## The fix (three seams, not one patch)

1. **Isolate sink failures at the bus.** `announce()` now delivers through a
   guard that swallows and **prunes** a raising sink — one bad client can never
   take down another. (`parts/events.py`)
2. **Never leak a session.** `_serve_player` unbinds its session in a `finally`,
   even if the front-desk handshake raises, so a mid-login drop can't linger.
   (`parts/gateway.py`)
3. **Stop manufacturing the landmine.** A health check that *connects* to the
   live gateway spawns a real session; if it disconnects rudely it becomes the
   dead sink. Health is now read from the server's log line, not a socket.

Each seam got a test twin, including one that broadcasts into a room containing a
deliberately-closed sink and asserts the actor's command still returns.

## The lesson

- **A shared fan-out must treat every consumer as hostile.** One slow or dead
  consumer cannot be allowed to fault the producer.
- **Reproduce before you theorize.** The fix was small; finding it required
  admitting the "impossible" report was real and building the exact conditions
  (a PTY, two connections, one half-dead) to see it.
- **Clean up in `finally`, always** — a resource bound on the way in must be
  released on every way out, including the exceptional one.

The terse version of this pattern lives in the failure-pattern log in
[`AI_WORKFLOW.md`](AI_WORKFLOW.md); this file is the long-form case study.
