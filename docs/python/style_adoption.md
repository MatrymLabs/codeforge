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
| §2 kernel/adapters/content + import-linter | **HELD (keel junction)** | codeforge uses `parts/` (a flat, tested part catalog), not `kernel/adapters/content`. Restructuring is a core-architecture change under the human-keel replacement threshold. Not adopted; owner decision required. See below. |
| §3 `vocabulary.py` per project | STAGED | No `vocabulary.py` today; domain nouns live across `parts/`. A vocabulary module is a candidate build, not yet made. |
| §3 Deprecated-vocabulary ban | **HELD (owner call)** | `parts/evidence_gate.py` and the EvidenceGate naming (and the "assimilation" campaign language) predate this ban. The rename is reserved as the owner's decision (see the nomenclature work). New code introduces none of the deprecated terms. |
| §4 Professional baseline | MET | Ruff (line length 100), mypy, pytest (strict), branch coverage gate, per-module custom exceptions, Conventional Commits, Google-style docstrings. Evidenced in `standards.md`. |
| §4 Per-project exception root | PARTIAL | Exceptions are per-module (`BuildError`, `LibraryError`, ...) rather than one project root. Consistent and typed; a single root is a possible future consolidation, not required. |
| §5 Flourish budget | MET (by habit) | codeforge already carries one domain motif (the forge/spiral voice) in internal names; public surfaces stay professional. |
| §6 Agent addendum | ADOPTED | Agents read this guide and honor the kernel/adapter intent, tag surprising choices, return verdicts, and introduce no deprecated vocabulary. |

## The two held items (owner decisions, not agent-doable)

1. **Structure migration (§2).** Moving codeforge from `parts/` to `kernel/adapters/content`
   with import-linter enforcement is a core-architecture change. Per the human-keel doctrine it
   stops for the owner: it alters module boundaries fleet-wide, touches every import, and would
   be a multi-week program. The guide's *intent* (pure logic with no IO/framework imports,
   one-way dependencies) is already substantially honored by `parts/` and the engine-tick law;
   the *directory shape* is the open question. Not started.

2. **Deprecated-vocabulary rename (§3).** Retiring `Veritas`/EvidenceGate and the assimilation
   language touches ~28 files plus a persisted part name. It is reserved as the owner's call
   because it changes established identifiers. New code uses only canonical vocabulary.

## Go-forward, in effect now

- Public surfaces strictly professional; the signature voice only in internal code, within the
  existing motif.
- New non-obvious choices carry a DECISION/INFER/UNVERIFIED tag; an INFER ships with the test
  that would falsify it (or an explicit UNVERIFIED).
- New gate/adjudication logic returns a verdict carrying evidence and reasoning, not a bare bool.
- No deprecated vocabulary in any new code, tests, or fixtures.
