# Security Roadmap

Actionable hardening plan for the CodeForge engine, with current status.
For the background and citations behind these recommendations, see
[`mud-security-best-practices.md`](mud-security-best-practices.md).

**Threat model:** a long-running, stateful, line-oriented TCP/telnet server,
LAN-only by design (`parts/gateway.py` docstring). SQLite persistence, a
FastAPI admin surface. The realistic adversaries are a malicious LAN client
and, if ever exposed, the open internet.

## Status legend
✅ done · 🔨 in progress · 📋 planned · 🧭 deferred (needs infra/deploy decisions)

## Authentication & credentials
- ✅ **pbkdf2-sha256, per-account salt, constant-time compare** (`parts/accounts.py`).
- ✅ **Generic login refusals** — no user-enumeration oracle.
- 🔨 **Raise the password floor.** Min length was 4 (trivially brute-forceable);
  raising toward NIST-aligned length-first guidance.
- 🧭 **Argon2id migration.** Preferred modern KDF (memory-hard). pbkdf2@600k is
  acceptable today; migrate via rehash-on-login. Deferred: adds a dependency
  and a migration path decision.

## Online brute-force defense
- ✅ Per-connection 3-strikes-then-close at the front desk.
- 🔨 **Cross-connection per-IP rate limiting / lockout.** The 3-strikes reset on
  reconnect; add per-IP failure tracking with a cooldown.

## Input & output handling
- ✅ **No shell-out; ORM-only (no raw SQL)** — command/SQL injection closed.
- ✅ **Telnet IAC stripping** keeps negotiation bytes out of secrets.
- 🔨 **ANSI / control-character sanitization at the client boundary.** The
  classic MUD sleeper: player-supplied text (chat) containing raw ESC
  sequences can corrupt or spoof other players' terminals. Sanitize outbound
  text at the gateway edge.
- 🔨 **Input line-length caps + read timeouts** — bound `readline` to stop
  memory-exhaustion / slowloris-style stalls.

## Authorization & privilege separation
- ✅ `@`-verbs check rank before running (`parts/ranks.py`; architecture law #5).
- ✅ No `eval`/`exec` verb exposed (the classic MUD escalation vector).
- 📋 **Audit-log privileged actions** (actor + target + verb).

## Denial of service & resource limits
- 🔨 **Idle/read timeouts** — disconnect silent sockets.
- 🔨 **Concurrent-connection cap** — `ThreadingTCPServer` is thread-per-connection;
  bound it to resist connection floods.
- ✅ `TICK_LOCK` is held only around the tick, never across socket I/O.

## Transport security
- 🧭 **TLS for the admin API and (if ever internet-facing) telnet.** The echo
  blackout hides passwords from shoulder-surfing, not from a network sniffer.
  Deferred: a deployment concern (reverse proxy / stunnel / cert management)
  rather than an in-engine code change.

## Persistence & supply chain
- ✅ Parametrized ORM writes; state treated as untrusted on load (derive, don't
  store — law #3); absolute DB path closes the wrong-cwd footgun.
- ✅ `accounts.json` removed from tracking; credential material stays out of VCS.
- ✅ `make audit` (pip-audit) available; keep it in CI and dependencies patched.
- 📋 **Backups + SQLite WAL mode** for durability and concurrent reads.

## This pass (2026-07-08) — implementing now
1. ANSI/control-character output sanitization (gateway boundary).
2. Cross-connection per-IP login rate limiting.
3. Connection cap + idle/read timeouts.
4. Raise the password minimum length.

TLS and Argon2id are documented as deferred (🧭) — they hinge on
deployment/dependency decisions and would be half-baked as drive-by code.
