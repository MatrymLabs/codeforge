# The CodeForge Python Engineering Standard

*What this repository already practices, now written down -- with the research that backs
each choice. Derived from an audit against "Python Coding Practices: A Scholarly Survey
(2021-2026)" on 2026-07-12. This documents the standard; it does not invent one.*

## The doctrine

Readable before clever. Explicit before magical. Simple before abstract. Measured before
optimized. Tested before trusted. Typed where boundaries matter. Automated where
repetition is stable. Documented where future maintainers need context.

**AI drafts. Static tools inspect. Tests challenge. Benchmarks measure. Josh decides.**

## Toolchain (deliberately minimal)

| Concern | Tool | Why this one |
|---|---|---|
| Lint + imports + modernize | Ruff (`E,F,I,UP,B,SIM`) | One tool replaces flake8+isort+pyupgrade; no rule overlap |
| Types | mypy (sole checker) | One checker, one truth; scoped to `parts`, `tests`, `forge.py` |
| Tests | pytest (strict markers/config) | Fail loud on typos, importlib mode |
| Property tests | Hypothesis (`@pytest.mark.property`) | See "Testing in layers" below |
| Fuzz | Hypothesis-driven (`@pytest.mark.fuzz`) | Zero new dependency; Atheris deferred until cross-platform need is proven |
| Security | bandit + pip-audit + detect-secrets + CodeQL + Scorecard | Layered; suppressions documented in pyproject with reasons |
| Coverage | branch coverage, gate >= 85% | Line coverage proves a line ran; branch coverage proves both sides |
| Env | uv-first (`make env`), pip fallback | Measured ~20x faster on this host |

The survey's tool-comparison tables (pp. 5, 8) list Black+isort+flake8 as the common
stack; Ruff subsumes all three here. Fewer tools enforcing the same rules is the
standard's own advice.

## Testing in layers

1. **Unit tests** -- 1:1 test-twin per module (`parts/x.py` <-> `tests/test_x.py`).
2. **Property tests** -- for invariant-heavy components: progression curves,
   state-machine laws, manifest round-trips, registry minting. Ravi and Coblenz (2025)
   found Python property-based tests detect ~50x more injected faults than the average
   unit test -- the strongest testing evidence in the survey, and why invariants get
   properties here, not just examples.
3. **Fuzz tests** -- for trust-boundary gates only (YAML seeds, catalogs, manifests,
   command input). The law: a gate returns a valid object or raises its OWN error type;
   an unexpected TypeError at a boundary is a crash, not a refusal.
4. **Benchmarks** -- frameless (`time.perf_counter` + `statistics`), warmup, median +
   distribution, dated evidence under `reports/performance/`.

### What the first fuzz run found (evidence this layer earns its place)

Two real defects on day one, both fixed and pinned by tests:

- **Platform-default file encoding** at nine gate call sites: `read_text()` without
  `encoding="utf-8"` crashes on Windows (cp1252) for any seed/catalog with non-Latin
  text. Also explained a pre-existing Windows test failure.
- **`interfaces:` with no value** in a manifest YAML parses to `None` and crashed the
  gate with `TypeError` instead of `ManifestError` -- a realistic authoring mistake.

## Typing strategy (gradual, boundary-first)

Magalhaes and Montandon (2026) found 91% of popular libraries use type hints but cover
only ~13.6% of their code -- adoption is boundary-first everywhere, and that is the
policy here, made explicit:

- **Always typed:** public APIs, Hardware Store part interfaces, data models (frozen
  dataclasses), adapters, persistence and protocol boundaries.
- **Typed where stable:** internal functions once their shape has settled.
- **Not required:** test bodies, one-off scripts, exploratory code.
- **Never:** `Any` spreading through a public interface; `object` where a real union is
  known (fixed in `parts/loop.py` -- `PartManifest | None` behind `TYPE_CHECKING`).

## Idioms policy

Idiomatic constructs (comprehensions, f-strings, context managers, pathlib, unpacking)
are the default -- research links them to readability and maintainability (Midolo and
Di Penta, 2025). Two guardrails the survey itself supports:

- **Performance claims require measurement.** Zhang et al.-style results show idiom
  performance is context-dependent; nothing here is "optimized" by being made Pythonic.
  Real gains came from measured experiments (EXP-001 catalog cache ~426x, EXP-002 stat
  cache ~3.2x, EXP-003 lazy import ~3.4x) -- caching and I/O removal, not syntax.
- **No structural pattern matching for fashion.** `match/case` enters only where it
  beats the existing dispatch for clarity; the command spine and `Fired`/`Refusal`
  handling are readable as-is.

## Security posture

Aligned with the OpenSSF Python Secure Coding Guide v1.0 (2026): no `eval`/`exec`,
subprocess as argument lists with no shell (FailsafeRunner allowlist), parameterized
queries via the ORM, salted-pbkdf2 (600k iterations in production), secrets never
rendered (config redaction), explicit UTF-8 at file boundaries. The six
`except Exception` sites are each justified in a comment (a dashboard must not 500; a
broken guard must refuse, not crash the tick) -- broad catches are boundary decisions,
never habits.

## Reproducibility

`make env` builds the venv (uv-first); SQLite is the zero-config dev backend, PostgreSQL
the production one, behind one seam. Per survey guidance (p. 8), the dependency graph is
pinned in `uv.lock` (committed): with uv, `make env` installs the exact resolved versions
(`uv sync`), so two machines building the project get identical dependency trees. The pip
fallback still resolves fresh -- reproducibility is best-effort without the resolver.
Refresh the pin deliberately with `uv lock`; `uv lock --check` verifies it is current.

## References (APA 7)

Magalhaes, T. R., & Montandon, J. E. (2026). *Understanding type hints in Python
libraries and frameworks: Early insights*. Proceedings of ICPC 2026.

Midolo, A., & Di Penta, M. (2025). *Automated refactoring of non-idiomatic Python code:
A replication with LLMs*. arXiv:2501.17024.

OpenSSF. (2026). *Python secure coding guide v1.0*. Open Source Security Foundation.

Ravi, S., & Coblenz, M. (2025). *An empirical evaluation of property-based testing in
Python*. Proceedings of OOPSLA 2025.
