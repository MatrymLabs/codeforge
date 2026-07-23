# Professional Development

A running ledger of skills demonstrated, lessons banked, and growth goals -
the "what am I getting better at" record behind CodeForge.

## How to use this

- When a working day teaches something durable, add it to **Lessons banked**
  (with the date and a link to that day's captain's log).
- Keep **Growth goals** honest and small - a few things actively in progress,
  not a wishlist.
- **Skills demonstrated** is the interviewer-facing map: "where in this repo
  can I see evidence of X?"

## Skills demonstrated

| Skill | Evidence in the repo |
|-------|----------------------|
| Secure credential handling | `parts/world/accounts.py` - pbkdf2-sha256 (600k iters), per-account salt, constant-time compare, generic (non-enumerating) refusals |
| Test-first discipline | Every `parts/` card has a test twin; new commands get an engine-tick test; hostile cases (mixed case, mismatches) are required |
| Protocol-level work | Telnet IAC WILL/WONT ECHO blackout + IAC stripping in `parts/gateway.py` |
| Clean architecture | "State is canonical, text is projection"; the engine tick is the only door; drivers are thin (see `docs/architecture.md`, ADRs) |
| Disciplined git workflow | Branch → `make check` → `--no-ff` merge → `make ship`; Conventional Commits |
| Operational debugging | Cornered a "ghost server" heisenbug (deploy ≠ restart) - see 2026-07-08 log |

## Lessons banked

- **2026-07-08 - Deploy ≠ restart.** A running server serves the code it
  imported at launch; suspect a ghost process before the code.
  ([log](../captains-log/2026-07-08.md))
- **2026-07-08 - Docs must match `main`.** A portfolio repo that contradicts
  its own stated rules reads worse than one with no rules.
  ([log](../captains-log/2026-07-08.md))

## Growth goals (in progress)

- **Harden the untrusted boundary end-to-end** - output sanitization, rate
  limiting, connection/idle limits (tracked in
  [`../security/security-roadmap.md`](../security/security-roadmap.md)).
- **Modern KDF migration** - understand Argon2id vs pbkdf2 trade-offs well
  enough to justify a migration path (rehash-on-login).
- **Deployment story** - TLS termination and a reproducible container/cloud
  deploy, so "runs on my Pi" becomes "runs anywhere."
