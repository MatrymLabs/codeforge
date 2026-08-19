# LANGUAGE LANE RECORDS v1 (DRAFT, derived)

**Not doctrine.** Extracted 2026-08-19 from the two products this factory has actually proven.

The ladder is `CANDIDATE -> INSTALLED -> GATED -> PROVEN`, and the last rung is the one that gets
overstated. **A lane is PROVEN only when a real Target Product has shipped through the factory in
it.** Gates existing is `GATED`. Gates being calibrated is still `GATED`. Having code in the tree
is not even that.

By that rule, after two dones, **exactly one lane is PROVEN.** Nine languages have gates. That gap
is the honest state of the Workshop and it is written down rather than rounded up.

---

## PROVEN: python

```yaml
lane_id:        python
status:         PROVEN
proven_by:
  - DONE-1 (M2 Engine Real): poured a standalone product that persists, restarts and survives
    database loss. Verified 2026-08-19: isolation, persist, restart, survive all PASS, and all
    four refuse when sabotaged.
  - DONE-2 (RF-001): decoded a cartridge image to a tile grid and a traceable manifest with the
    source bytes provably unchanged. Four stages, all refuse when sabotaged.
  - deploy-proof: poured the whole engine plus a 10,681-room world into a standalone cast that
    booted in a fresh subprocess and served real play commands. Label DEPLOYABLE.

gates:
  format:       ruff format --check .
  lint:         ruff check .
  typecheck:    mypy (strict, warn_unreachable)
  test:         pytest, via $(PY) so the repository interpreter is used
  sca:          pip-audit (make audit-runtime), blocking
  sast:         bandit (make sast)
  secrets:      gitleaks (make secrets)

calibration:    ruff x3, mypy x2 all green 2026-08-19.
                pytest x1 is currently UNCERTIFIABLE and that is not rounded to green:
                  [FAIL] pytest-filterwarnings-error
                         the benign probe is already red before planting (exit 4)
                Cause measured, not guessed: the case invokes bare `python`, which resolves to the
                system interpreter and collects nothing. `python -m pytest` exits 4 where
                `.venv/Scripts/python -m pytest` exits 0. WO-CAL-3 is dispatched.
                bandit x1 SKIPs on this bench for the same class: bare `bandit` is not on PATH.

known_limitation: two of eleven Python calibration cases cannot currently run, both for the same
                  reason, and both were found by the harness refusing rather than by anyone
                  noticing. The lane is PROVEN by shipped product; its gate coverage is not
                  complete and the record says so.
```

## GATED, not proven: kotlin

```yaml
lane_id:        kotlin
status:         GATED
why_not_proven: No Target Product has shipped in Kotlin. DONE-2's tile grid renders through
                `python -m kernel.retroforge.view`; the Kotlin is a plugin scaffold that compiles
                and packages (buildPlugin BUILD SUCCESSFUL, plugin.xml and the tool-window factory
                present inside the jar) but Rider LOADING it has never been observed.
                That is L1 with an L4 scaffold beside it, and calling it PROVEN would be the exact
                overstatement this ladder exists to prevent.

gates:
  lint:         ktlint 14.2.0
  static:       detekt 1.23.8, baseline 16
  build:        gradle 9.7.0, kotlin 2.4.0, daemon JVM pinned to 24

calibration:    detekt x1 green 2026-08-19 (green -> RED on TooGenericExceptionCaught -> green).
                ktlint shown to catch a planted indentation violation by file:line on 2026-08-18.
                Both gates were re-calibrated AFTER the Gradle/Kotlin/ktlint version bumps, because
                "it still runs" and "it still catches" are different claims.

what_would_prove_it: a product whose deliverable IS the Kotlin artifact, loaded and used.
```

## GATED, awaiting a product: go, rust, c, terraform, shell

```yaml
status:         GATED
why_not_proven: Each has code in the tree, a gate in `make lint`, and a calibration case that has
                been shown to redden. NONE has produced a Target Product.
calibrated:     go (errcheck), rust (clippy unwrap_used), c (unused-parameter),
                terraform (fmt drift), shellcheck (SC2086). All verified green 2026-08-19.
honest_note:    These lanes are in better shape than most projects' primary language, and they are
                still not PROVEN, because the ladder's top rung means shipped, not inspected.
```

## The count, stated plainly

| rung | lanes |
|---|---|
| PROVEN | **1** (python) |
| GATED | 6 (kotlin, go, rust, c, terraform, shell) |
| calibration cases total | 14, of which 13 currently pass and 1 is uncertifiable |

## Known limitation

**Both proving products are Python, and both were built by the factory describing itself.** A lane
reaches PROVEN through a product, and every product so far has been the same shape: an engine that
pours itself, and a tool that reads a file. The claim "any language can enter the factory" remains
an architectural claim, not a demonstrated one, until a second lane ships something. This record
exists so that gap is visible rather than implied away by nine green gates.
