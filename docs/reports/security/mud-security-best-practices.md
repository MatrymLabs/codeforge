# Security Best Practices for MUD-Style Game Servers

*A reference report for **CodeForge** - a threaded TCP/telnet MUD engine (line-oriented protocol, SQLite + SQLAlchemy persistence, PBKDF2 account authentication, a FastAPI admin surface, LAN-only by design).*

---

## Executive Summary

MUDs (Multi-User Dungeons) are one of the oldest classes of networked multi-user
application, and they inherit an equally old set of security problems: a
plaintext transport (telnet), long-lived stateful connections, a privileged
"immortal/wizard" command tier, and player-supplied text that is rendered
directly into other players' terminals. Modern web-security guidance from OWASP
and NIST maps onto these problems cleanly, even though MUDs are not web
applications.

This report translates authoritative guidance - the OWASP Top 10, OWASP Cheat
Sheet Series and ASVS, NIST SP 800-63B, the telnet RFCs, and the Argon2 / PHC
references - into concrete recommendations for a codebase shaped like CodeForge.
The headline conclusions:

- **Telnet is plaintext by definition.** Echo-blackout (turning off local echo
  during password entry) hides the password from the *screen*, not from the
  *wire*. Confidentiality requires TLS (native, `stunnel`, SSH tunnel, or
  TLS-WebSocket), and this holds even on a LAN.
- **PBKDF2 is acceptable but no longer the first choice.** OWASP now recommends
  **Argon2id** for new designs; PBKDF2 is the fallback for FIPS-140 environments
  and requires ~600,000 SHA-256 iterations to remain defensible.
- **Password *policy* should follow NIST SP 800-63B**: length over composition,
  screen against breached-password corpora, no forced periodic rotation.
- **The classic MUD vulnerability is privilege escalation** through the
  wizard/immortal command tier - and, historically, `eval`/`exec`-style "coder"
  commands. Least privilege and never exposing a live interpreter are
  non-negotiable.
- **The MUD-specific injection risk** is ANSI/terminal control-character
  injection through player-supplied names and chat, which can corrupt or, in
  some emulators, actively attack other players' and admins' terminals.

"LAN-only" reduces exposure but does not remove it: a single compromised host,
a guest on the Wi-Fi, or a misconfigured port-forward converts a LAN service
into an internet-facing one. Treat every control below as defence-in-depth
rather than assuming the network boundary is the whole defence.

---

## 1. Transport Security

### 1.1 Telnet is plaintext, and echo-blackout is not confidentiality

The telnet protocol (RFC 854) defines a Network Virtual Terminal over a raw TCP
stream with no encryption; the ECHO option (RFC 857) only governs *which end
echoes typed characters back to the terminal*, not whether the data is protected
in transit ([RFC 854](https://www.rfc-editor.org/rfc/rfc854.html),
[RFC 857](https://www.rfc-editor.org/rfc/rfc857)). When a MUD "blacks out" the
password prompt, it is asking the client (or negotiating via telnet ECHO) to
stop echoing keystrokes so a shoulder-surfer cannot read the password off the
screen. The bytes still traverse the network in cleartext. Anyone able to
observe the segment - a switch SPAN port, a compromised host doing ARP spoofing,
a promiscuous NIC on shared Wi-Fi - can read credentials and session content
verbatim.

**Do not treat "LAN-only" as equivalent to "confidential."** LANs are routinely
shared with untrusted guests, IoT devices, and personal laptops, and the first
move after any host compromise is lateral network sniffing.

### 1.2 Options for encrypting a MUD transport

There is **no single official "TLS-MUD" RFC**. (Note: an IETF document does use
the acronym "MUD" - RFC 9761, *Manufacturer Usage Description* - but that is an
unrelated IoT-networking specification, not a game protocol; do not cite it as a
MUD-game standard.) In practice the community uses a handful of conventions:

- **Native TLS on a dedicated port.** Terminate TLS inside the server (or in
  front of it) and expose an encrypted listener, commonly advertised alongside
  the plaintext port. MUD clients such as Mudlet document explicit TLS
  connection support, and drivers such as LDMud ship integrated TLS
  ([Mudlet TLS](https://wiki.mudlet.org/w/Sample_TLS_Configuration),
  [LDMud TLS](https://abathur.github.io/ldmud-doc/build/html/topics/tls.html)).
- **`stunnel` wrapper.** `stunnel` adds TLS to an unmodified server by proxying
  an encrypted external port to the plaintext internal one - a well-established
  MUD pattern ([Discworld MUD: Stunnel](https://dwwiki.mooo.com/wiki/Stunnel)).
  Trade-off: the MUD sees `stunnel`'s local address as the client IP unless the
  PROXY protocol is used, which breaks per-IP throttling and audit logging
  ([Discworld MUD: Stunnel](https://dwwiki.mooo.com/wiki/Stunnel)). Driver-
  integrated TLS preserves the real client IP.
- **SSH tunnel.** Users forward the MUD port over SSH. Strong, but pushes setup
  onto players and offers no in-band UX.
- **TLS-WebSocket.** For browser-based clients, wrap the line protocol in a
  `wss://` WebSocket. This is the natural fit if CodeForge ever grows a web
  client and lets you reuse the same TLS/HTTP stack as the FastAPI admin surface.

**Recommendation for CodeForge:** offer a TLS listener (native or via `stunnel`)
even on the LAN, keep any plaintext port clearly labelled and ideally opt-in,
and prefer an approach that preserves the real client IP so §3's rate limiting
and §5's audit logging remain meaningful. Use modern TLS only (TLS 1.2+;
prefer 1.3) and disable legacy protocol versions and cipher suites.

The FastAPI admin surface must be served over HTTPS with the same rigour - an
admin panel is exactly the asset an attacker wants, and OWASP classifies
transmitting sensitive data in cleartext under *Cryptographic Failures* in the
Top 10.

---

## 2. Authentication and Credential Storage

### 2.1 Choice of key-derivation function (KDF)

Argon2 won the Password Hashing Competition in 2015 and is the current
state-of-the-art memory-hard password hash; **Argon2id**, the hybrid variant, is
the recommended default because it combines Argon2i's side-channel resistance
with Argon2d's GPU-cracking resistance
([P-H-C/phc-winner-argon2](https://github.com/P-H-C/phc-winner-argon2),
[Argon2 - Wikipedia](https://en.wikipedia.org/wiki/Argon2)).

OWASP's current, quotable parameter guidance
([OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)):

| Algorithm | OWASP minimum |
|---|---|
| **Argon2id** (preferred) | 19 MiB memory, iterations `t=2`, parallelism `p=1` (equivalently 46 MiB/`t=1`, 12 MiB/`t=3`, etc.) |
| **scrypt** (if no Argon2) | `N=2^17` (128 MiB), `r=8`, `p=1` |
| **bcrypt** (legacy) | work factor ≥ 10; **72-byte input limit** - enforce a max password length or pre-hash |
| **PBKDF2** (FIPS-140 only) | PBKDF2-HMAC-SHA256 ≥ **600,000** iterations (SHA-512 ≥ 220,000) |

**Implications for CodeForge's current PBKDF2:** PBKDF2 is *not wrong* - it is
FIPS-approved and OWASP-listed - but it is the weakest of the four against
GPU/ASIC attackers because it is not memory-hard. If you keep it, verify the
iteration count meets ~600,000 for SHA-256. The stronger move is to migrate to
Argon2id via a well-maintained library (e.g. `argon2-cffi`). A clean migration
path is to record the algorithm/parameters *in the stored hash string* (both the
PHC-format Argon2 output and `passlib` hashes do this), and to transparently
re-hash a user's password to the new scheme on their next successful login.

### 2.2 Salts, peppers, and comparison

- **Per-user random salt is mandatory** to defeat rainbow tables; modern KDF
  libraries generate and embed a unique salt automatically, so do not hand-roll
  salting ([OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)).
- **Pepper (optional, defence-in-depth):** a secret shared across all hashes,
  stored *outside* the database (secrets manager / HSM / env var loaded at
  runtime), so a database-only leak does not immediately expose the hashes
  ([OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html)).
- **Constant-time comparison:** compare the *final* verification value with a
  constant-time function (in Python, `hmac.compare_digest`
  <https://docs.python.org/3/library/hmac.html>) to avoid leaking information
  through comparison timing. Note that a proper Argon2/bcrypt `verify()` already
  performs a constant-time check internally, so the main place to be careful is
  any *hand-written* token or hash comparison (session tokens, admin API keys).

### 2.3 Password policy - follow NIST SP 800-63B

NIST SP 800-63B inverts a generation of "complexity rule" habits
([NIST SP 800-63B](https://pages.nist.gov/800-63-3/sp800-63b.html),
[NIST SP 800-63B-4 passwords](https://pages.nist.gov/800-63-4/sp800-63b/passwords/)):

- **Favour length over composition.** Support long passphrases (accept at least
  64 characters), enforce a sensible minimum (SP 800-63B requires ≥ 8; the
  latest revision raises the recommended floor toward 15 for password-only
  auth), and **do not impose mandatory character-class rules** - NIST states
  composition rules make it *harder* for people to choose strong passwords.
- **Screen against breached/weak passwords.** Reject passwords found in known
  breach corpora, common dictionaries, and obvious context words (e.g. the
  MUD's own name, "password", the username). Offline lists or a k-anonymity API
  both work.
- **No forced periodic rotation.** Require a change only on evidence of
  compromise.
- Allow all printable characters including spaces/Unicode, and support
  paste (do not break password managers).

### 2.4 Do not build a user-enumeration oracle

Login, registration, and any password-reset flow must return a **generic
result** so an attacker cannot distinguish "user does not exist" from "wrong
password"; this applies to the message text *and* to timing
([OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[OWASP Forgot Password Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html)).
Because MUDs prompt for a character name *first* and then a password, they are
especially prone to leaking which names exist ("That character does not
exist." vs. "Wrong password."). Two concrete measures:

- Use one message for all failures (e.g. "Login failed.").
- Defeat **timing** enumeration by performing a dummy KDF verification even when
  the account does not exist, so the response time is the same either way
  ([OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)).
  (Caveat: a MUD's account-creation flow inevitably reveals *taken* names when a
  player tries to create one; scope the enumeration defence to the *login* path
  and accept this residual, documented trade-off rather than overstating a
  guarantee.)

---

## 3. Online Brute-Force Defence

Weak or absent brute-force protection is squarely within OWASP Top 10
**A07:2021 – Identification and Authentication Failures**, which explicitly cites
permitting automated credential-stuffing and brute-force attempts
([OWASP A07](https://owasp.org/Top10/2021/A07_2021-Identification_and_Authentication_Failures/)).
OWASP's guidance combines several controls
([OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html),
[OWASP: Blocking Brute Force Attacks](https://owasp.org/www-community/controls/Blocking_Brute_Force_Attacks)):

- **Login throttling / backoff.** Cap attempts and add increasing delay between
  successive failures on the same account or connection. For a persistent telnet
  session this is trivial to enforce: sleep/backoff and eventually drop the
  connection after N failures.
- **Account lockout - carefully.** Typical thresholds are 3–5 failures with a
  timed auto-unlock. **Warning:** naive lockout is itself a denial-of-service
  vector - an attacker who knows valid names can lock every player out. Prefer
  temporary, exponentially-increasing lockouts and per-IP throttling over
  permanent per-account locks ([OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)).
- **Per-IP throttling** on both new connections and failed logins. This depends
  on seeing the *real* client IP - see the `stunnel` caveat in §1.2.
- **CAPTCHA / MFA** are the strongest web controls but map awkwardly onto a raw
  telnet MUD; treat them as options for the FastAPI admin surface (where MFA is
  strongly advised) rather than the game login.

Apply the same throttling to the FastAPI admin login - an admin brute-force is
far more damaging than a player one.

---

## 4. Input Handling

### 4.1 SQL injection - use the ORM / parameterized queries

OWASP's primary defence against SQL injection is **parameterized queries /
prepared statements**, with an ORM being an acceptable equivalent because it
builds parameterized queries for you; input validation is a *secondary*, not
substitute, defence
([OWASP SQL Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html),
[OWASP Query Parameterization Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html)).
CodeForge's use of SQLAlchemy is the right choice. The remaining risks are the
places developers *bypass* the ORM:

- Never build SQL by string concatenation or f-strings, even "just for an admin
  report." Use bound parameters (`text("... :name")` with a params dict, or the
  ORM expression language).
- Table/column *identifiers* cannot be parameterized - if any admin feature lets
  a user pick a column/table name, validate it against a hard-coded allowlist.

### 4.2 Command injection and never exposing `eval`/`exec`

Player commands are dispatched, not executed as shell/Python. Keep it that way:
map commands through an explicit dispatch table, never pass player text to
`os.system`, `subprocess(..., shell=True)`, `eval`, or `exec`. This connects
directly to the MUD-specific privilege problem in §5.

### 4.3 Path traversal in content / seed loading

MUDs load rooms, zones, help files, and seed data from disk. If any path is
influenced by user or client input (an area name, a `download`/`help` argument),
an attacker can attempt `../../etc/passwd`-style traversal. Mitigate per OWASP
Injection Prevention guidance
([OWASP Injection Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html)):
resolve the requested path, canonicalize it (`os.path.realpath` /
`Path.resolve()`), and verify it is contained within the intended base directory
before opening; prefer an allowlist of known content files over accepting
arbitrary paths.

### 4.4 Telnet IAC handling, length caps, and read timeouts

- **Parse telnet control bytes safely.** The telnet IAC (Interpret As Command,
  byte `0xFF`) escape and option negotiation (`DO`/`DONT`/`WILL`/`WONT`,
  RFC 854) appear in the byte stream. Handle or strip IAC sequences deliberately;
  do not feed raw negotiation bytes into game-command parsing, and bound the
  size of any subnegotiation buffer ([RFC 854](https://www.rfc-editor.org/rfc/rfc854.html)).
- **Cap input line length** and total buffered bytes per connection so a client
  cannot force unbounded memory growth by sending a line with no newline
  (see §6).
- **Impose read/idle timeouts** so half-open and stalled connections are reaped
  (see §6, Slowloris).

### 4.5 The MUD-specific risk: ANSI / terminal control-character injection

This is the input-handling issue most unique to MUDs and most often missed.
Player-supplied text - character names, `say`/`tell`/channel chat, descriptions,
titles, mail - is rendered into *other players'* terminals and into
*administrators'* consoles and logs. If that text can contain raw ANSI/VT escape
sequences (`ESC[`, `0x1B`), a malicious player can:

- Corrupt or spoof other players' displays (fake system messages, hidden text,
  cursor repositioning, screen clears).
- Attack the terminal emulator itself. Terminal-escape injection is a real,
  actively-exploited class: OSC sequences can rewrite window titles, and some
  emulators expose clipboard writes (OSC 52) or other dangerous operations,
  turning "display a message" into "stage a command in the victim's clipboard"
  ([CyberArk: Abusing Terminal Emulators with ANSI Escape Characters](https://www.cyberark.com/resources/threat-research-blog/dont-trust-this-title-abusing-terminal-emulators-with-ansi-escape-characters),
  [InfosecMatter: Terminal Escape Injection](https://www.infosecmatter.com/terminal-escape-injection/)).
- Attack **admins reading logs.** If raw player text is written to a log file
  that an admin later `cat`s in a terminal, the escape sequences execute in the
  admin's terminal. This exact pattern produced recent CVEs, e.g. Apache
  Tomcat's ANSI-escape-in-logs issue CVE-2025-55754
  ([SentinelOne: CVE-2025-55754](https://www.sentinelone.com/vulnerability-database/cve-2025-55754/)).

**Mitigations:**

- **Strip or reject raw control characters** (`0x00–0x1F` except intended
  whitespace, plus `0x7F` and `ESC`) from all player-supplied text at the input
  boundary. Then re-introduce colour on *output* through your own safe markup
  (e.g. a `{r`/`&R`-style tag scheme translated to ANSI by the server), so
  players never inject raw escapes.
- **Sanitize before logging.** Escape or strip control bytes before writing
  user data to logs, so reading a log file can never drive an admin's terminal.
- Enforce strict **allowlist validation on names** (letters, limited length, no
  control bytes, no impersonation of system strings).

---

## 5. Authorization and Privilege Separation

Broken access control is OWASP Top 10 **A01:2021**, the single most prevalent
category, covering any failure to enforce that users act only within their
intended permissions ([OWASP A01](https://owasp.org/Top10/2021/A01_2021-Broken_Access_Control/)).
In MUDs this manifests as the **wizard/immortal escalation** problem - the most
storied MUD vulnerability class.

- **Least privilege and default-deny.** Every privileged command must check the
  actor's level/role at execution time, server-side, on *every* invocation - not
  merely hide the command from a menu. Never rely on the client to withhold a
  command.
- **Tiered command tables.** Separate mortal, builder/wizard, and admin/implementor
  command sets, and gate each with an explicit authorization check. A frequent
  historical bug is a privileged command that fails to re-verify level, or that
  trusts a target/argument (e.g. "set my level," "goto/snoop any player,"
  "force another player") without an ownership/level check.
- **Never expose a live interpreter.** Many classic MUD codebases shipped
  "coder"/OLC features that could run arbitrary code or arbitrary shell commands;
  exposing `eval`/`exec`/shell to any online command is an immediate remote code
  execution path. Do not provide it. If builders need to script content, use a
  sandboxed, non-Turing-complete data format loaded offline.
- **Audit-log privileged actions.** Log who did what, when, and to whom for all
  admin/wizard commands (bans, level changes, item/currency creation, `force`,
  `snoop`, config edits). This supports A09 (*Security Logging and Monitoring
  Failures*) and gives you an incident trail. Ensure these logs are
  control-character-sanitized (§4.5).
- **Segregate the FastAPI admin surface.** Its authorization is separate from
  in-game roles: enforce authentication + role checks on every admin endpoint
  (default-deny), bind it to localhost/LAN, and strongly prefer MFA. An
  unauthenticated or IDOR-prone admin endpoint is a direct A01 finding.

---

## 6. Denial of Service and Resource Limits

CodeForge's threaded, thread-per-connection model is efficient to reason about
but is the textbook target for connection-exhaustion attacks.

- **Connection floods.** Cap concurrent connections globally and per IP; reject
  or queue beyond the cap rather than spawning unbounded threads.
- **Thread-per-connection exhaustion + Slowloris.** A "low and slow" attacker
  opens many connections and sends bytes just fast enough to avoid timing out,
  tying up one worker/thread each until the pool is exhausted - precisely the
  Slowloris pattern that devastates thread-per-connection servers
  ([Cloudflare: Slowloris](https://www.cloudflare.com/learning/ddos/ddos-attack-tools/slowloris/),
  [CMU SEI: Mitigating Slowloris](https://www.sei.cmu.edu/blog/mitigating-slowloris/)).
  Mitigations that transfer directly to a MUD:
  - **Aggressive read/idle timeouts** - drop a connection that has not completed
    login or sent input within a bounded window; do not let a header/line be fed
    one byte at a time forever ([CMU SEI](https://www.sei.cmu.edu/blog/mitigating-slowloris/)).
  - **Per-IP connection limits** and **maximum session lifetime for the
    pre-auth state**.
  - Consider an async/event-loop or a bounded thread pool with backpressure so
    that one slow client cannot consume a dedicated OS thread.
- **Unbounded allocation.** Cap input line length, per-connection buffer size,
  and any per-player collections (inventory, mail, channel history) so a client
  cannot exhaust memory. Reject oversized input early and loudly.
- **Backpressure on output.** A client that reads slowly can make the server's
  send buffers grow without limit; bound outbound queues and disconnect clients
  that cannot keep up.

Longer term, fronting the game (and especially the FastAPI admin surface) with a
reverse proxy that buffers complete requests is a recognised Slowloris defence
for the HTTP side ([Cloudflare: Slowloris](https://www.cloudflare.com/learning/ddos/ddos-attack-tools/slowloris/)).

---

## 7. Persistence and Data Integrity

- **Parameterized queries everywhere** - see §4.1. With SQLAlchemy this is the
  default; the discipline is never dropping to string-built SQL.
- **Treat all persisted and client state as untrusted.** Data loaded back from
  SQLite (or from any client-supplied "restore" of game state) must be
  re-validated on read, not trusted merely because "we wrote it." Corrupted or
  tampered rows, out-of-range values, and dangling references should fail loud,
  not crash or silently corrupt live state. This is the persistence-layer
  corollary of OWASP's input-validation guidance.
- **SQLite WAL mode.** Enabling Write-Ahead Logging (`PRAGMA journal_mode=WAL`)
  improves crash durability and concurrency - readers do not block the single
  writer and vice-versa, and a COMMIT is durable once its record is flushed to
  the WAL, even across a power loss ([SQLite: Write-Ahead Logging](https://sqlite.org/wal.html)).
  Two caveats from the SQLite docs: there is still only **one writer at a time**,
  and **WAL does not work over a network filesystem** - all processes must be on
  the same host ([SQLite: Write-Ahead Logging](https://sqlite.org/wal.html)).
  This suits a single-host LAN MUD well.
- **Backups.** Take regular, tested backups. Use SQLite's online backup API or
  `VACUUM INTO` rather than copying the file mid-write; verify restores. Store
  backups off the game host and treat them as sensitive (they contain password
  hashes).

---

## 8. Secrets Management and Supply Chain

- **Keep credentials out of version control.** Load the pepper (§2.2), FastAPI
  admin secrets, TLS private keys, and any session/signing keys from environment
  variables or a secrets manager, never from tracked source. Commit a
  `.env.example` documenting the *names* of required variables, and ensure
  `.env`, key files, and the SQLite database are `.gitignore`d. A committed
  secret must be treated as compromised and rotated - removing it in a later
  commit does not undo the exposure, since it remains in git history.
- **Audit dependencies.** Run **`pip-audit`** (maintained with contributors from
  Google's open-source security team and Trail of Bits; it sources advisories
  from the PyPA Advisory Database via PyPI) in CI to catch known-vulnerable
  packages before release ([pip-audit](https://pypi.org/project/pip-audit/)).
  Note its documented limitation: it flags *known* vulnerabilities and does not
  protect against *malicious* packages ([pip-audit](https://pypi.org/project/pip-audit/)),
  so pin/verify dependencies (hashes, a lockfile) as well.
- **Patch on a cadence.** Track and update SQLAlchemy, FastAPI, the KDF library,
  and the TLS stack; subscribe to advisories and re-run `pip-audit` regularly,
  not just once.
- **Verify against a standard.** For a portfolio-grade claim of security
  diligence, self-assess against the OWASP Application Security Verification
  Standard (ASVS), which provides a checklist across authentication, session
  management, access control, and validation.

---

## Summary Checklist

| Area | Minimum bar | Stretch goal |
|---|---|---|
| Transport | TLS listener available (even on LAN); no secrets over plaintext | TLS 1.3 only; real client IP preserved; admin over HTTPS |
| Credential storage | PBKDF2-HMAC-SHA256 ≥ 600k iters, per-user salt | Argon2id (19 MiB/t=2/p=1) + pepper; transparent re-hash on login |
| Password policy | ≥ 8 chars, length-based, no forced rotation | ≥ 15 chars, breached-password screening, passphrases |
| Auth hardening | Generic failure messages; login throttling | Timing-equalised login; per-IP throttle; admin MFA |
| Input | ORM/parameterized SQL; strip control chars from player text | Path allowlist; safe colour-markup layer; log sanitization |
| Authorization | Server-side level check on every privileged command | Tiered command tables; audit log; no `eval`/`exec` ever |
| DoS | Read/idle timeouts; per-IP + global connection caps | Bounded thread pool/async with backpressure; input size caps |
| Persistence | Parameterized queries; WAL; tested backups | Re-validate persisted state on load; off-host encrypted backups |
| Supply chain | Secrets out of VCS; `pip-audit` in CI | Hash-pinned lockfile; ASVS self-assessment |

---

## Notes on Certainty and Conflicting Guidance

- **PBKDF2 vs Argon2id.** These are not in conflict - both are OWASP-listed. The
  nuance is that PBKDF2 is *sufficient for compliance* (FIPS-140) but *weaker per
  unit of defender cost* because it is not memory-hard. Calling PBKDF2 "insecure"
  would be an overstatement; "acceptable but no longer preferred" is accurate.
- **Password minimum length.** SP 800-63B's absolute floor is 8 characters; the
  latest revision pushes recommended minimums higher (toward 15 for
  password-only auth). Sources vary on the exact number by revision, so this
  report cites both rather than asserting a single figure.
- **Historical MUD CVEs.** DikuMUD/Merc/ROM/LPMud lineages had numerous
  real-world security issues (buffer overflows in C string handling, wizard
  command escalation, OLC/coder RCE), but these were largely documented in mailing
  lists and code comments rather than the modern CVE database, and this report
  could not verify specific CVE identifiers for them from authoritative sources.
  The *vulnerability classes* (memory-safety in C - not applicable to CodeForge's
  Python - and privilege escalation, which very much is) are well established even
  where individual advisory citations are not. This is flagged rather than
  overstated.
- **ANSI-escape severity varies by terminal.** The impact of terminal-escape
  injection depends heavily on the victim's terminal emulator; consequences range
  from cosmetic corruption to (in specific emulators) clipboard or command
  staging. The defensive posture - strip control characters - is the same
  regardless, but claims of guaranteed RCE against arbitrary clients would be
  overstated.

---

## References

1. OWASP - Password Storage Cheat Sheet. <https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html>
2. OWASP - Authentication Cheat Sheet. <https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html>
3. OWASP - Forgot Password Cheat Sheet. <https://cheatsheetseries.owasp.org/cheatsheets/Forgot_Password_Cheat_Sheet.html>
4. OWASP - SQL Injection Prevention Cheat Sheet. <https://cheatsheetseries.owasp.org/cheatsheets/SQL_Injection_Prevention_Cheat_Sheet.html>
5. OWASP - Query Parameterization Cheat Sheet. <https://cheatsheetseries.owasp.org/cheatsheets/Query_Parameterization_Cheat_Sheet.html>
6. OWASP - Injection Prevention Cheat Sheet. <https://cheatsheetseries.owasp.org/cheatsheets/Injection_Prevention_Cheat_Sheet.html>
7. OWASP - Blocking Brute Force Attacks. <https://owasp.org/www-community/controls/Blocking_Brute_Force_Attacks>
8. OWASP Top 10:2021 - A01 Broken Access Control. <https://owasp.org/Top10/2021/A01_2021-Broken_Access_Control/>
9. OWASP Top 10:2021 - A07 Identification and Authentication Failures. <https://owasp.org/Top10/2021/A07_2021-Identification_and_Authentication_Failures/>
10. OWASP - Application Security Verification Standard (ASVS). <https://owasp.org/www-project-application-security-verification-standard/>
11. NIST SP 800-63B - Digital Identity Guidelines: Authentication and Lifecycle Management. <https://pages.nist.gov/800-63-3/sp800-63b.html>
12. NIST SP 800-63B-4 - Passwords (draft/revision). <https://pages.nist.gov/800-63-4/sp800-63b/passwords/>
13. IETF RFC 854 - Telnet Protocol Specification. <https://www.rfc-editor.org/rfc/rfc854.html>
14. IETF RFC 857 - Telnet Echo Option. <https://www.rfc-editor.org/rfc/rfc857>
15. P-H-C - Argon2, winner of the Password Hashing Competition (reference implementation). <https://github.com/P-H-C/phc-winner-argon2>
16. Argon2 - Wikipedia (PHC 2015 winner; Argon2i/d/id variants). <https://en.wikipedia.org/wiki/Argon2>
17. CyberArk - "Don't Trust This Title: Abusing Terminal Emulators with ANSI Escape Characters." <https://www.cyberark.com/resources/threat-research-blog/dont-trust-this-title-abusing-terminal-emulators-with-ansi-escape-characters>
18. InfosecMatter - Terminal Escape Injection. <https://www.infosecmatter.com/terminal-escape-injection/>
19. SentinelOne - CVE-2025-55754 (Apache Tomcat ANSI escape injection in logs). <https://www.sentinelone.com/vulnerability-database/cve-2025-55754/>
20. Discworld MUD Wiki - Stunnel (TLS wrapping for MUDs). <https://dwwiki.mooo.com/wiki/Stunnel>
21. LDMud Documentation - Transport Layer Security. <https://abathur.github.io/ldmud-doc/build/html/topics/tls.html>
22. Mudlet Wiki - Sample TLS Configuration. <https://wiki.mudlet.org/w/Sample_TLS_Configuration>
23. pip-audit - Python dependency vulnerability scanner (PyPI). <https://pypi.org/project/pip-audit/>
24. Cloudflare - Slowloris DDoS Attack. <https://www.cloudflare.com/learning/ddos/ddos-attack-tools/slowloris/>
25. CMU Software Engineering Institute - Mitigating Slowloris. <https://www.sei.cmu.edu/blog/mitigating-slowloris/>
26. SQLite - Write-Ahead Logging. <https://sqlite.org/wal.html>
27. Python Standard Library - `hmac.compare_digest` (constant-time comparison). <https://docs.python.org/3/library/hmac.html>

---

*Prepared as a portfolio reference document for the CodeForge MUD engine. All
recommendations are defence-in-depth; "LAN-only by design" reduces but does not
eliminate the applicable threat surface.*
