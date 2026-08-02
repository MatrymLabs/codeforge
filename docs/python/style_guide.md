# MATRYM LABS - PYTHON STYLE GUIDE
### The Signature Standard

> "It is a capital mistake to theorize before one has data."

This guide defines how Python is written across the Matrym Labs fleet - by the founder and by AI agents alike. It encodes two commitments that must never trade against each other:

1. **Professional first contact.** Anything a stranger touches first - README, public API, error message, commit history - reads as the work of a disciplined senior engineer. No inside jokes on the storefront.
2. **Signature underneath.** The structure, naming discipline, and evidence habits are distinctly ours. Someone who reads three Matrym repos should recognize the fourth without seeing the org name.

The boundary rule that resolves every conflict between the two:

**PUBLIC SURFACES ARE STRICTLY PROFESSIONAL. INTERNAL SURFACES CARRY THE VOICE.**

| Surface | Register |
|---|---|
| README, docs site, changelog, release notes | Professional. Clear, direct, zero whimsy. |
| Public API names, CLI flags, config keys, error messages | Professional. Boring names are correct names. |
| Commit messages, PR descriptions | Professional. Conventional Commits. |
| Module organization, internal naming, docstrings | Signature. Domain-appropriate flavor permitted. |
| Test fixtures, example data, internal tooling | Signature. This is where the goblins live. |

Domain-appropriate is the test: `heartbeat.py` as the tick scheduler *inside a MUD engine* passes - any senior engineer reads it as fitting the domain. The same name in a payroll API fails. When in doubt, the boring name wins.

---

## 1. THE METHOD - Data Before Theory

The house method is observational: gather evidence, deduce, then conclude - and never let a deduction masquerade as an observation. This is enforced in code, not just prose.

### 1.1 Evidence-tagged decisions

Every non-obvious choice in code cites its basis using the fleet's evidence vocabulary:

```python
# DECISION: 3-second tick resolution. See ADR-007.
# INFER: Evennia caches attribute reads per-request; not yet verified
#        under load. Revisit if profile shows attribute churn.
# UNVERIFIED: upstream claims thread-safety; treat as hostile until tested.
TICK_SECONDS = 3
```

Tags: `DECISION` (deliberate choice, cite the ADR), `INFER` (reasoned but unproven - must say what would verify it), `UNVERIFIED` (external claim taken on faith, flagged), `EVIDENCE` (link to benchmark/test that proves the claim). An `INFER` comment that never gets resolved is technical debt; sweep them quarterly.

### 1.2 Verdicts, not booleans

Validation and gate logic returns canonical outcomes, never bare `True`/`False`, so the result carries its reasoning:

```python
class Verdict(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    HUMAN_DECISION_REQUIRED = "human_decision_required"

@dataclass(frozen=True, slots=True)
class GateResult:
    verdict: Verdict
    evidence: tuple[str, ...]      # what was observed
    reasoning: str                 # the deduction
```

A function that decides something important returns *why* it decided. Eliminate the impossible; whatever remains must be logged.

### 1.3 Deduction has a Watson

The deduction instinct's failure mode is confident inference outrunning evidence. The counterweight is structural, not aspirational:

- No inference ships without a test that would falsify it.
- `INFER` in a comment obligates a matching test, benchmark, or explicit UNVERIFIED escalation.
- Agents (and the founder) may not upgrade `INFER` to `DECISION` without citing the evidence that resolved it.

---

## 2. STRUCTURE - Grammar Before Worlds

Every Matrym project shares one shape. Kernel first, adapters second, content last.

```
project/
  kernel/          # Pure logic. Zero framework imports. Fully typed. Fully tested.
  adapters/        # Framework/IO boundaries (Evennia, web, DB, filesystem).
  content/         # Data, world definitions, configuration-as-content.
  vocabulary.py    # The domain grammar. See §3.
```

Rules:

- `kernel/` imports nothing from `adapters/` or any framework. Ever. If the kernel needs IO, it declares a protocol; an adapter implements it.
- Dependency direction is one-way: content → adapters → kernel. A reversed import is a build failure, not a review comment (enforce with import-linter).
- The kernel of any project should be runnable and testable with nothing but the standard library and its declared pure dependencies.

This is the architectural signature. A stranger opening any Matrym repo finds the same skeleton and knows where everything lives.

---

## 3. VOCABULARY - One Grammar Per Project

Each project maintains a `vocabulary.py` (or `vocabulary/` package): the single home of domain nouns. Enums, type aliases, frozen dataclasses. Everything else imports its language from here.

```python
# vocabulary.py - the canonical grammar of this project.
class Calling(StrEnum): ...        # combat identity - never "class" or "job"
class Profession(StrEnum): ...     # crafting/gathering - never "trade"
SeedId = NewType("SeedId", str)
```

Rules:

- Canonical terms only. Deprecated fleet vocabulary (Borg, Assimilation, Collective, Drone, Hive, Cube, Veritas) never appears in new code, including tests.
- A domain concept named two ways is a defect. Rename toward the vocabulary module.
- Public API surfaces use plain-industry terms where the domain term would confuse an outsider; the mapping between the two lives in `vocabulary.py` docstrings.

---

## 4. PROFESSIONAL BASELINE - The Non-Negotiables

The signature earns its place only on top of unimpeachable fundamentals.

**Tooling (enforced in CI, not by memory):**
- Ruff - lint + format, line length 100. The repo ships `ruff.toml`; agents and humans run it pre-commit.
- Full type annotations on all public functions and all kernel code. `mypy --strict` (or pyright strict) on `kernel/`.
- pytest, test pyramid: kernel logic unit-tested exhaustively; adapters integration-tested; a thin E2E layer.
- Import-linter enforcing §2's dependency direction.
- Docstrings: Google style, on every public callable. First line states what it does; body states contracts, not implementation.

**Naming:**
- `snake_case` functions/modules, `PascalCase` classes, `SCREAMING_SNAKE` constants. No abbreviations that save fewer than four characters. No single-letter names outside comprehensions and math.
- Functions are verbs (`resolve_tick`, `assemble_packet`); classes are nouns; booleans read as predicates (`is_authoritative`, `has_consumer`).

**Error handling:**
- Custom exception hierarchy rooted per-project (`HavenError`, `ForgeError`). Never raise bare `Exception`.
- Error messages are professional surfaces: state what failed, what was expected, and what the caller can do. No flavor text in exceptions.
- Fail loudly at boundaries, never silently in the kernel. Swallowed exceptions require a `DECISION` comment.

**Commits & PRs:**
- Conventional Commits (`feat:`, `fix:`, `refactor:`, `docs:`, `test:`).
- Subject ≤ 72 chars, imperative mood. Body explains *why*, links the ADR or issue.
- No commit named `wip`, `stuff`, or `fixes` reaches a shared branch.

**Server authority (fleet law, restated for code):**
- Nothing client-side decides an authoritative outcome. Kernel functions that adjudicate state changes take evidence in and return verdicts out; presentation happens elsewhere.

---

## 5. THE FLOURISH BUDGET - Rationed Personality

Personality is a spice, measured in pinches:

- **One thematic naming motif per project**, and only where it's domain-appropriate (a MUD's scheduler may be `heartbeat.py`; its bootstrap may be `awaken()`). It must be *more* descriptive than the generic name, or it doesn't ship.
- **Test fixtures wear the domain.** D&D-flavored fixtures (`goblin`, `longsword`, `tavern_room`) beat `foo`/`bar` in game projects - they make tests readable. In non-game projects, fixtures use realistic domain data instead.
- **Docstrings may be dry, never cute.** A single well-placed epigraph at the top of a module is the ceiling.
- If a reviewer (human or agent) can't tell whether a name is flavor or function, it's renamed.

---

## 6. AGENT ADDENDUM - Writing In This Voice

Most fleet code volume is agent-generated. Agents operating in Matrym repos:

1. Read this file and the repo's `vocabulary.py` before writing code.
2. Follow the kernel/adapter boundary absolutely; when unsure where code belongs, put it in the kernel *only if* it needs no IO and no framework.
3. Tag every non-obvious choice with `DECISION`/`INFER`/`UNVERIFIED` - an untagged surprising choice is a review rejection.
4. Return verdicts, not booleans, from gate logic.
5. Never introduce deprecated vocabulary, even in comments or fixtures.
6. Keep public surfaces strictly professional; spend the flourish budget only in internal code and only within the project's declared motif.
7. When generated code embeds an inference about how a library behaves, mark it `INFER` and generate the test that would verify it in the same change.

---

*The observation is free. The deduction must be earned. The verdict must be evidenced.*
