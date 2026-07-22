# Pattern family: Validation

*Fifth family doc for the Hardware Store's pattern shelf. Research basis: "Full-Stack Design Patterns
for CodeForge" (section 13, Schema Validation), which notes a schema "specifies which fields must be
present, what types they have, and constraints."*

## Provenance

- **Origin:** `independently_implemented_pattern`. Accumulate-all-errors input validation is a
  standard pattern (Pydantic, Zod, JSON Schema all return the full issue list). **No code was
  copied**; the behavior was reimplemented from first principles with the stdlib only.
- **Independently implemented:** the `ValidationResult`, the composable `Rule`/`Validator`, the rule
  builders, the "required is separate from format" policy, and both adapters.
- **License:** MIT · **owner:** MatrymLabs · **human review:** built and reviewed this session.

## The part: `validator`

`parts/shelf/validation.py` -- validate a mapping against a `Validator` (a bundle of small `Rule`
callables) and get a `ValidationResult`: `is_valid`, and every `Issue` at once (each tagged with its
`field` and a readable message). `raise_if_invalid()` is the one loud exit (`ValidationFailed`
carries the result). Rule builders cover the common cases: `required`, `matches`, `of_type`,
`in_range`, `one_of`, `max_length`.

**Design rule:** `required` is separate from format, so a required-and-empty field reports
`is required` **once**, not twice. Rules **never mutate** the input.

**Invariants (tested, incl. property-based):** a value satisfying every rule is valid; all issues are
collected in one pass; the issue count never exceeds the rule count; `raise_if_invalid` raises only
when invalid, carrying the result.

## GAME-TO-PRACTICAL TRANSLATION

- **Game component:** a character-name preview (`parts/name_check.py`).
- **Core behavior:** check a value against rules; return valid, or a clear list of problems.
- **Game-specific presentation:** "'admin' won't work: is a reserved name."
- **Reusable domain logic:** the whole `Validator` + rules (game-free).
- **Practical applications:** API payload validation, forms, config, data-import checks.
- **Required abstraction:** rules as callables over a mapping; already in the core.
- **Adapters required:** a game verb; a practical payload validator.
- **Security implications:** reject malformed input at the boundary with non-leaky messages.
- **Testing implications:** every-issue-at-once; required-vs-format separation.
- **Hardware Store candidate:** YES (stocked as `validator`).

## Adapters (one core, two lives)

- **Game:** `parts/name_check.py` -- the `namecheck` verb previews whether a proposed character name
  is valid (required, the name pattern, not a reserved word) and lists why not. Tick-reachable.
- **Practical:** `parts/payload_check.py` -- `validate_signup(payload)` checks a signup body
  (username, email, age) with the same core, returning every problem at once.

## Evidence

- Tests: `tests/test_validation.py` (unit + property), `tests/test_name_check.py` (game + tick),
  `tests/test_payload_check.py` (practical + a one-core proof).
- Manifest: `docs/hardware/validator.yaml`. Trace it: `make loop PART=validator`.
- **Maturity: `beta`** -- demonstrated in two contexts and tested, but not `stable` (no nested
  schemas or coercion yet).

## The companion part: `sanitizer`

`parts/shelf/sanitizer.py` -- where the validator *checks*, the sanitizer *normalizes*. `sanitize(text,
rule)` drops control characters, folds every run of whitespace to one space, trims, optionally
lowercases, and caps the length. It is **deterministic and idempotent** (sanitizing twice equals
once, a property-tested invariant), and honest about its scope: it normalizes, it is **not** a
security control (not output-escaping, not crypto). It does neutralize control chars and
log-injection newlines. Adapters: a sanitized player title in the game (`parts/titles.py`, the
`title` verb) and a stored/logged field cleaner in a practical app (`parts/field_sanitizer.py`,
`clean_field` / `clean_record`). Trace it: `make loop PART=sanitizer`. Maturity `beta`.

## Deferred (needs Josh's approval)

Nested/recursive schemas, type coercion, and a Pydantic or JSON-Schema-backed validator are later
slices; for the sanitizer, unicode NFC normalization and script allowlists. Consolidating the
existing seed/manifest loader checks onto these parts is a follow-up, not part of this slice.
