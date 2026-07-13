# AI Workflow: how AI is used here, and how it stays honest

CodeForge is built with heavy AI assistance. This page states, plainly, how that works and
what keeps it trustworthy, so a reader never has to guess. The short version: **AI proposes,
the system measures, the tests verify, and Josh decides.** AI is a force multiplier for
creativity; it is never the authority, and its output is never accepted on faith.

## The keel stays human

The governing rule is the Human Keel Doctrine ([human_keel_doctrine.md](human_keel_doctrine.md)):
if AI replaces every plank, the **keel stays human**. Purpose, architecture, constraints,
acceptance criteria, risk decisions, and interpretation are Josh's; AI builds planks under
that direction. Every AI contribution is a **draft** until a human reviews, tests, and can
defend it.

**Ownership Gate (0-5):** `0 ai_output -> 1 reviewed -> 2 verified -> 3 modified -> 4
defendable -> 5 extended`. Level 4+ is a portfolio claim and requires a written **Human Keel
Record** on disk ([keel_records/](keel_records/)); the machine-enforced **KeelGate**
(`parts/career.py`) refuses any level >= 4 claim without one. AI never assigns ownership on
Josh's behalf.

## Every AI-drafted change passes the same gates as any other

AI authorship earns no shortcut. All code, AI-drafted or not, goes through
**branch -> `make check` -> PR -> CI green -> merge**, and `make check` is lint + mypy + the
full test suite with a coverage floor. Beyond that, the security surface is authorship-blind
and always on:

- **SAST** (`bandit`) and **CodeQL** gate CI: they flag exactly the patterns AI tends to
  leave (`shell=True`, `eval`/`exec`, `pickle`, unsafe `yaml.load`).
- **Secret scanning** (`detect-secrets`) gates CI.
- **Dependency discipline:** a new package an AI suggests cannot land without a justification
  row in `dependency_ledger.toml` (`make deps`), plus the blocking runtime CVE gate
  (`make audit-runtime`). This closes the "AI recommended an unsafe or hallucinated package"
  failure mode.
- **Truth discipline:** VeritasGate (`make truth`) refuses claims that do not correspond to
  reality, so AI-written docs cannot drift from the code unwatched.

## AI code is draft: the security review checklist

Peer-reviewed research is blunt about it: LLMs routinely solve the functional task while
missing the security issue unless asked explicitly, leaving disabled TLS, unsafe
deserialization, dangerous subprocess calls, or insecure package suggestions in place
("automated technical debt with extra confidence"). So when AI generates, debugs, or
refactors code here, it is reviewed like a draft from a talented but overconfident intern.
Inspect explicitly for:

- **Insecure defaults / disabled TLS** (`verify=False`, unverified SSL contexts).
- **Dangerous subprocess** (shell strings, unallowlisted commands; the ship uses the
  allowlisted `parts/console.py` runner, never raw shell).
- **Insecure deserialization** (`pickle`, `yaml.load` without `SafeLoader`, `eval`/`exec`).
- **Weak authentication / authorization gaps** (a capability reachable before its rank check).
- **Unsafe package recommendations** (unpinned, low-reputation, or hallucinated dependencies).

Ask the assistant for security review **explicitly** ("check this for insecure defaults"),
then run the static analysis, then read the diff. Passive trust is not the workflow. This
mirrors the ship's Secure Software Engineering posture (see the security roadmap under
[reports/](reports/)).

## Learning is protected

AI must not erase the learning. Every significant AI-assisted feature requires at least one
human act: explain it, trace a path, modify a behavior, write or repair a test, name a
failure mode, or teach it. The loop is **Ask -> Predict -> Generate -> Inspect -> Explain ->
Modify -> Test -> Reflect**, never generate-straight-to-accept.

## Honest labeling

Claims about AI use are stated truthfully: "AI-assisted implementation," "human-reviewed and
tested," "architecture directed by Josh." The project avoids "built by hand" when false,
"mastered" when the evidence is incomplete, and "fully autonomous" when review is required.

## The AI seam is testable and offline

AI features (the Architect NPC's Claude brain, the Blueprint drafter) sit behind an
**injected client** ([architect_brain.md](architect_brain.md)): tests drive a fake, CI needs
no API key, and the core never imports the SDK. The feature is one key away and dormant by
default, which is also why it is safe to run the whole suite without touching the network.

## Known failure patterns AI must watch

The ship keeps an honest list of real incidents (in the root operating contract and
[DEBUGGING.md](DEBUGGING.md)): a blanket `raw.lower()` that once destroyed mixed-case
passwords, "deploy != restart" ghost servers, wrong-address file drops that silently rewrote
imports, `endswith(b"")` always true. AI-assisted work checks these first, because they are
exactly the confident-but-wrong mistakes an assistant reproduces.
