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
- ✅ **Generic login refusals** - no user-enumeration oracle.
- ✅ **Password floor raised to 8** (`MIN_PASSWORD_LEN`, NIST SP 800-63B).
  Was 4 (trivially brute-forceable).
- 🧭 **Argon2id migration.** Preferred modern KDF (memory-hard). pbkdf2@600k is
  acceptable today; migrate via rehash-on-login. Deferred: adds a dependency
  and a migration path decision.

## Online brute-force defense
- ✅ Per-connection 3-strikes-then-close at the front desk.
- ✅ **Cross-connection per-IP rate limiting** (`_gate_is_barred` /
  `_turnaway_ledger`, `MAX_LOGIN_FAILS` in a `LOGIN_FAIL_WINDOW`). Survives reconnects, which the
  per-connection 3-strikes did not. The ledger is bounded: barred-checks are
  read-only and each recorded turnaway sweeps aged-out addresses (self-audit
  fix, 2026-07-08). *Accepted trade-off:* shape errors (`Usage:` responses)
  count as turnaways - errs toward security; a fumbling newcomer waits out a
  5-minute window.

## Input & output handling
- ✅ **No shell-out; ORM-only (no raw SQL)** - command/SQL injection closed.
- ✅ **Telnet IAC stripping** keeps negotiation bytes out of secrets.
- ✅ **ANSI / control-character sanitization at the client boundary**
  (`_sanitize` in `_send`). The classic MUD sleeper: player-supplied text
  (chat) with raw ESC sequences could corrupt or spoof other terminals.
- ✅ **Read/idle timeouts** - see DoS section below.
- ✅ **Input line-length cap** - `MAX_LINE_BYTES = 4096` bounds `readline`
  (`parts/gateway.py:34`), so a single no-newline flood is not an unbounded read.

## Authorization & privilege separation
- ✅ `@`-verbs check rank before running (`parts/ranks.py`; architecture law #5).
- ✅ No `eval`/`exec` verb exposed (the classic MUD escalation vector).
- 📋 **Audit-log privileged actions** (actor + target + verb).

## Denial of service & resource limits
- ✅ **Idle/read timeouts** (`IDLE_TIMEOUT`, applied via the handler's socket
  timeout) - silent sockets are dropped instead of pinning a thread forever.
- ✅ **Concurrent-connection cap** (`MAX_CONNECTIONS`) - `ThreadingTCPServer` is
  thread-per-connection; over the cap, new sockets are refused cleanly.
- ✅ `TICK_LOCK` is held only around the tick, never across socket I/O.

## Transport security
- 🧭 **TLS for the admin API and (if ever internet-facing) telnet.** The echo
  blackout hides passwords from shoulder-surfing, not from a network sniffer.
  Deferred: a deployment concern (reverse proxy / stunnel / cert management)
  rather than an in-engine code change.

## Persistence & supply chain
- ✅ Parametrized ORM writes; state treated as untrusted on load (derive, don't
  store - law #3); absolute DB path closes the wrong-cwd footgun.
- ✅ `accounts.json` removed from tracking; credential material stays out of VCS.
- ✅ `make audit` (pip-audit) available; keep it in CI and dependencies patched.
- 📋 **Backups + SQLite WAL mode** for durability and concurrent reads.

## This pass (2026-07-08) - shipped ✅
1. ANSI/control-character output sanitization (gateway boundary).
2. Cross-connection per-IP login rate limiting.
3. Connection cap + idle/read timeouts.
4. Password floor raised to 8 (NIST-aligned).

All four landed with test twins (unit + over-the-wire socket tests); suite
grew 176 → 182, green. A same-day self-audit then found and fixed an
unbounded-growth bug in the turnaway ledger (182 → 184).

**Deferred by design (🧭):** TLS and Argon2id hinge on deployment/dependency
decisions and would be half-baked as drive-by code. **Still planned (📋):**
audit logging of privileged actions, backups + WAL.
