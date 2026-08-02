# CodeForge STRIDE threat models

*Lightweight, living threat models for the material trust boundaries. Each is a checklist, not a
diagram that retires in a folder: every High/Critical threat names a preventive control, a detective
control, a response, and a **real test that proves the control holds**. When a boundary changes, its
model is reviewed. Not a compliance claim.*

| Field | Value |
|-------|-------|
| **Owner** | Josh / MatrymLabs |
| **Last reviewed** | 2026-07-31 |
| **Method** | STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, Denial of service, Elevation of privilege) |
| **Reassess when** | a new privileged verb, a new endpoint, an auth change, a new economy path, a new parser, or a new import format lands |

Legend: **P** preventive control · **D** detective control · **R** response/recovery · **T** the test
that pins it. Controls and tests are cited by real path/name so this model cannot rot into fiction.

---

## Boundary 1 - Player-to-server command path (the tick)

**Asset:** world state (the canonical `Session` + `WORLD`/`ITEMS`/`NPCS`). **Actor:** any connected
player (untrusted). **Trust boundary:** the network socket into `handle_command`. **Preconditions:**
a connection (telnet `:4000`, WebSocket, or the API). **Doctrine:** every client input is hostile;
`handle_command` is the only door, and drivers only assemble tick commands.

| STRIDE | Threat | Controls + test |
|--------|--------|-----------------|
| **T**ampering | injected control chars / ANSI escapes corrupt another player's terminal | **P** output sanitized at the transport edge (`_sanitize`, `web_gateway._pump`); telnet IAC stripped (`strip_iac`). **T** `test_fuzz_telnet.py`, `test_web_gateway.py` |
| **D**oS | overlong line / command flood stalls the tick | **P** `MAX_LINE_BYTES` bounds each read; single `TICK_LOCK` serializes; idle timeout + seat cap on the public gate. **T** `test_gateway.py` |
| **E**levation | a crafted command reaches a privileged verb | **P** server-side rank gate before any handler runs (see Boundary 2). **T** `test_fuzz_commands.py::test_a_player_can_never_run_an_admin_command_however_phrased` |
| info-disclosure | a parser crash leaks a stack trace to the client | **P** the dispatcher never raises on hostile input; generic errors client-side. **T** `test_fuzz_commands.py::test_dispatch_never_crashes_on_hostile_input` |

**Residual risk:** low. The command parser is fuzzed and the output edge sanitized.

## Boundary 2 - Privilege boundary (player < wizard < owner)

**Asset:** administrative capability (`@`-verbs, grant, teleport, item generation). **Actor:** a
player or wizard attempting to act above their rank. **Trust boundary:** `kernel/world/ranks.has_rank`,
checked in the tick BEFORE any handler runs. This is the #1 OWASP risk (broken access control), so it
is deliberately tested from the deny side.

| STRIDE | Threat | Controls + test |
|--------|--------|-----------------|
| **E**levation | a player runs a wizard/owner verb | **P** deny-by-default rank gate; the `@` sigil is reserved for ADMIN by construction. **D** `[SS]`/`[SYSTEM]` security log lines on denials. **T** `test_ranks.py::test_players_are_refused_every_wizard_verb`, `test_commands.py::test_an_admin_command_denies_a_mere_player` |
| **E**levation | a verb is smuggled past the gate by casing/padding/aliasing | **P** longest-verb-first match on the normalized command; rank checked on the resolved command, not the raw text. **T** `test_fuzz_commands.py::test_case_and_padding_never_smuggle_an_admin_verb_past_the_gate` |
| **E**levation | a non-owner enters the Creator's Workshop | **P** the Workshop barrier is owner-only and sealed even to wizards; players cannot teleport, a wizard is turned back. **T** `test_ranks.py` (teleport), `kernel/world/workshop.py` |
| **T**ampering | rank is granted without authority | **P** `grant` is owner-only and persists; AI never assigns rank. **T** `test_ranks.py::test_grant_is_owner_only_and_persists_rank` |
| **R**epudiation | a privileged action leaves no trace | **D** privileged commands emit a security event (actor, action, outcome) - see `control-crosswalk.yaml` CF-SEC-006. |

**Residual risk:** low. Authorization is server-side, deny-by-default, and tested from the deny side
across every wizard verb plus under fuzzing.

## Boundary 3 - Authentication and session

**Asset:** account credentials + the character behind them. **Actor:** an attacker guessing,
stuffing, or replaying at the login front desk. **Trust boundary:** `kernel/world/accounts` + the
gateway login dialogue.

| STRIDE | Threat | Controls + test |
|--------|--------|-----------------|
| **S**poofing | brute-force / credential stuffing | **P** salted pbkdf2-sha256 (600k), constant-time compare, per-connection 3-strikes-then-close, generic non-enumerating refusals. **T** `test_accounts.py`, `test_account_store.py` |
| **T**ampering | a mixed-case password is silently mangled at login | **P** the tick routes on lowercased text but parses the password from the ORIGINAL input (a historic `raw.lower()` bug is pinned closed). **T** `test_accounts.py::test_passwd_preserves_mixed_case_roundtrip` |
| info-disclosure | a password appears in logs / history | **P** ECHO blackout masks the prompt; the secret is never logged in plaintext; log fields sanitized. **T** `test_field_sanitizer.py` |

**Residual risk:** low. Argon2id migration is a noted future hardening (`security-roadmap.md`).

## Boundary 4 - Economy (item + currency transfer)

**Asset:** items and coin. **Actor:** a player attempting to duplicate, mint, or destroy value.
**Trust boundary:** the transfer primitives (`trade._execute`, auction, guild store).

| STRIDE | Threat | Controls + test |
|--------|--------|-----------------|
| **T**ampering | coin/item duplication or minting via a transfer | **P** validate-all-then-apply atomicity; offers refused if over-balance or negative. **T** `test_trade_properties.py` (currency conserved, single owner, no partial state - across hundreds of Hypothesis cases) |
| **T**ampering | a disconnect/abort mid-trade leaves partial state | **P** nothing moves until the atomic seal; a missing item aborts the whole trade. **T** `test_trade_properties.py::test_an_aborted_trade_leaves_no_partial_state` |

**Residual risk:** low for the player trade. Auction/guild-store paths carry example-based tests;
extending property coverage to them is a candidate follow-up.

## Boundary 5 - World-input / import (seed YAML, AI-provider, deploy artifact)

**Asset:** the engine process + the build/release. **Actor:** a malicious seed file, a compromised
dependency, or a substituted image. **Trust boundary:** the seed loaders, the dependency tree, the
publish pipeline.

| STRIDE | Threat | Controls + test |
|--------|--------|-----------------|
| **E**levation (RCE) | a malicious seed executes code via deserialization | **P** one shared safe YAML loader (SafeConstructor) refuses `!!python/...` tags. **T** `test_seed_security.py::test_the_world_yaml_loader_refuses_code_execution_tags` |
| **T**ampering | a substituted image is deployed | **P** signed SLSA provenance on the GHCR image; verify before deploy. **T** the publish workflow's attest step; `gh attestation verify` (runbook: `render-iac-deploy.md`) |
| supply-chain | a vulnerable/malicious dependency | **P** pip-audit CVE gate, SHA-pinned actions, least-priv workflow perms, CycloneDX SBOM. **T** CI (`make audit`, `make sbom`) |

**Residual risk:** low. AI-provider input rides an authenticated seam off the gameplay transport; no
archive/upload import exists (zip-slip is not applicable).

---

## What this model deliberately does NOT claim

- It is **not** a compliance statement. It records engineering controls and the tests that prove
  them; framework satisfaction requires independent assessment.
- **Not applicable** to CodeForge today: student/child data (FERPA/COPPA), payment data (PCI), SSRF
  (no user-influenced outbound requests), archive import (no zip-slip surface). Recorded so scope is
  explicit, per `authorized-targets.yaml`.

## Related

- [`control-crosswalk.yaml`](control-crosswalk.yaml) - the controls, mapped to framework families.
- [`authorized-targets.yaml`](authorized-targets.yaml) - the boundary for active self-testing.
- [`../../runbooks/incident-response.md`](../../runbooks/incident-response.md) - the response side.
- [`security-roadmap.md`](security-roadmap.md) - status of ongoing hardening.
