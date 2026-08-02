# Matrym Python Style Guide - Adoption Ledger (codeforge)

The canonical standard is [`style_guide.md`](style_guide.md) (the Matrym Labs Python Style
Guide, the fleet signature standard). This file records how codeforge stands against it:
what is already met, what is staged for go-forward code, and what is deliberately HELD
pending an owner decision. It exists so the guide can be canonical without any doc claiming
compliance the code does not have.

**Rule of adoption:** the guide is the standard for **new** code from its adoption date. No
retro-migration is implied by adopting it; existing code is brought toward it opportunistically,
not in a big-bang rewrite. Where the guide describes a target codeforge has not reached, this
ledger says so plainly.

Adopted: 2026-08-02. Companion doc: [`standards.md`](standards.md) is codeforge's evidenced
engineering baseline (toolchain, testing layers) and sits *under* this guide.

## Section-by-section

| Guide section | codeforge status | Note |
|---|---|---|
| §1.1 Evidence tags (DECISION/INFER/UNVERIFIED) | STAGED (go-forward) | New non-obvious choices tag their basis; existing code is not back-annotated. |
| §1.2 Verdicts not booleans | PARTIAL | The QA/Safety spine already returns verdicts; some gates still return bare booleans. New gate logic returns a verdict. |
| §1.3 Deduction has a Watson | STAGED (go-forward) | An `INFER` obligates a falsifying test or an explicit `UNVERIFIED` escalation in the same change. |
| §2 kernel/adapters/content + import-linter | **DONE (2026-08-02)** | Owner approved the literal restructure (2026-08-02). Completed in 10 gate-green batches (codeforge #760-#769): 328 modules relocated into `kernel/` (pure logic incl. `kernel/world`, the game) + `adapters/` (gateway, api, cli, AI seams, web assets) + `content/` (the seed worlds); `parts/` retired; import-linter enforces the one-way direction (kernel imports no adapters/content; content imports nothing). Residual refinement recorded: the sql persistence-port implementations ride inside `kernel/world` behind ports. |
| §3 `vocabulary.py` per project | STAGED | No `vocabulary.py` today; domain nouns live across `parts/`. A vocabulary module is a candidate build, not yet made. |
| §3 Deprecated-vocabulary ban | **IN PROGRESS** | `VeritasGate` renamed to `EvidenceGate` (`kernel/evidence_gate.py`, registry designation, seed-template flags, dev-tool list, `make truth`) - DONE. Remaining: the "assimilation" pattern language (prose/comments in ~10 files) to adoption/intake, and a broad doc-prose sweep of lingering `veritas` mentions in active docs. Historical logs/reports left as records. New code introduces none of the deprecated terms. |
| §4 Professional baseline | MET | Ruff (line length 100), mypy, pytest (strict), branch coverage gate, per-module custom exceptions, Conventional Commits, Google-style docstrings. Evidenced in `standards.md`. |
| §4 Per-project exception root | PARTIAL | Exceptions are per-module (`BuildError`, `LibraryError`, ...) rather than one project root. Consistent and typed; a single root is a possible future consolidation, not required. |
| §5 Flourish budget | MET (by habit) | codeforge already carries one domain motif (the forge/spiral voice) in internal names; public surfaces stay professional. |
| §6 Agent addendum | ADOPTED | Agents read this guide and honor the kernel/adapter intent, tag surprising choices, return verdicts, and introduce no deprecated vocabulary. |

## The two formerly-held items (owner approved both 2026-08-02)

1. **Structure migration (§2) - APPROVED, staged migration.** The owner chose the literal
   `kernel/adapters/content` restructure over enforce-in-place. It is a core-architecture change,
   so it ships as small verifiable slices, not a big-bang: scaffold the three packages + install
   import-linter with the target contracts; move modules in cohesive batches (each PR green and
   the registry re-filed); flip `parts/` imports batch by batch; retire the empty `parts/` shell
   last. Note: a repo-wide import rewrite conflicts with concurrent work, so it wants a clear
   runway (no other active codeforge sessions) per batch.

2. **Deprecated-vocabulary rename (§3) - IN PROGRESS.** `VeritasGate -> EvidenceGate` shipped
   (module, class, CARD name, registry designation MOD-10.006, seed-template flags, dev-tool
   classification, `make truth`, ~50 call sites; not a public break - nothing tick-dispatched or
   save-bearing used the name). Remaining: the "assimilation" pattern language (prose/comments)
   to adoption/intake, and a doc-prose sweep of lingering `veritas` mentions. Historical logs are
   left as records.

## Go-forward, in effect now

- Public surfaces strictly professional; the signature voice only in internal code, within the
  existing motif.
- New non-obvious choices carry a DECISION/INFER/UNVERIFIED tag; an INFER ships with the test
  that would falsify it (or an explicit UNVERIFIED).
- New gate/adjudication logic returns a verdict carrying evidence and reasoning, not a bare bool.
- No deprecated vocabulary in any new code, tests, or fixtures.
