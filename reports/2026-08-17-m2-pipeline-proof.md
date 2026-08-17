# M2 pipeline proof: produce -> persist -> restart -> survive

**Date:** 2026-08-17
**Bench:** Claude Code
**Engine commit:** `48aec856`
**Instrument:** `scripts/m2_pipeline_proof.py` (new)
**Verdict:** the pipeline is PROVEN on two Blueprints. Four defects found, one of them severe.

---

## Why this existed to do

Every leg of M2 already had a test twin: `cast-plan`, `cast`, `shelf-pour`, `backup`, `restore`.
The seam BETWEEN the legs had nothing. Nothing had ever run one artifact through the whole chain,
so "M2 works" was an inference across five separately-green parts, never a measurement.

D11 closed the *seam* question at five world-facing probes. That is a different question and it
stays closed. This is the *pipeline* question.

## What the instrument does

Four stages, each in **its own subprocess**, because a restart that reuses the parent interpreter
proves only that the object is still in memory.

| stage | what it proves |
|---|---|
| ISOLATION | the poured product imports its OWN engine, not the checkout that poured it |
| PERSIST | a hero is written to the product's own database |
| RESTART | a FRESH interpreter reads that hero back and every field still matches |
| SURVIVE | the database is DELETED outright, restored from backup, hero intact |

SURVIVE additionally asserts the hero was **unreachable while the database was gone**. Without
that, a restore that silently read a second store would pass.

### Calibration (canon 13: a gate is trusted only when shown to fail)

`--sabotage <stage>` breaks one stage on purpose. All four fail at exactly their own stage and
nowhere else:

```
  none       VERDICT: PASS
  isolation  VERDICT: FAIL
  persist    VERDICT: FAIL (nothing was persisted, the remaining stages cannot mean anything)
  restart    VERDICT: FAIL
  survive    VERDICT: FAIL
```

The `restart` sabotage output is the useful one, because it shows the comparison has real teeth:

```
  [FAIL] restart    level: wrote 7, read back 1; xp: wrote 1234, read back 0; coins: wrote 99,
                    read back 0; account: wrote 'm2proof', read back ''; job: wrote 'artificer',
                    read back ''; location: wrote 'arc_chamber', read back 'forge'
```

## Proof runs

Poured from the engine at `48aec856`, then driven end to end.

**`blank_mud` -> first-forge**

```
  [PASS] isolation  engine imported from ...\workspace\m2-proof\P_blank_mud
  [PASS] persist    hero 'm2probe' saved at 'arc_chamber' as 'artificer'
  [PASS] restart    fresh interpreter read back level 7, xp 1234, at 'arc_chamber'
  [PASS] survive    database deleted and restored from backup, hero intact
VERDICT: PASS
```

**`kindlands_saga` -> aethryn** (with `FORGE_BLUEPRINT` pinned, see F1)

```
  [PASS] isolation  engine imported from ...\workspace\m2-proof\P_kindlands_saga
  [PASS] persist    hero 'm2probe' saved at 'ancient_overlook' as 'arcanist'
  [PASS] restart    fresh interpreter read back level 7, xp 1234, at 'ancient_overlook'
  [PASS] survive    database deleted and restored from backup, hero intact
VERDICT: PASS
```

Two independent worlds, different start rooms, different callings. **M2's pipeline is proven.**

---

## Findings

### F1 (HIGH) - a poured cast cannot boot its own world

`kernel/world/seed.py:53-54`:

```python
DEFAULT_SEED = "first-forge"
SEED_NAME: str = os.environ.get("FORGE_BLUEPRINT") or os.environ.get("FORGE_SEED") or DEFAULT_SEED
```

A cast poured from `kindlands_saga` ships `aethryn`, declares `seed_pack = "aethryn"` in its
`seed.toml`, stamps `"status": "validated"`, and then dies at import in a fresh process:

```
BlueprintError: Seed file not found: ...\P_kindlands_saga\content\blueprints\first-forge\jobs.yaml
```

Only a cast whose pack happens to be `first-forge` runs unaided. The pour is not at fault: the
right pack is copied and correctly declared. **`seed.toml` is write-only.** `kernel/cast.py:251`
and `:368` write it; nothing in the engine reads it.

This is the same law the repo already states for rooms ("never hardcode a room label as the
start"), applied one level up and currently violated for the pack itself.

**Recommendation (Principal Engineer call, not taken unilaterally).** Let `seed.py` fall back to
the product's own `seed.toml` *below* both env vars and *above* `DEFAULT_SEED`. That is additive
and backwards-compatible: every currently-working configuration is unchanged, and only the case
that crashes today gains an answer. It does change the engine's world-selection contract and make
a currently-inert file load-bearing, which is a public-interface change, so it wants a ruling.

### F2 (HIGH) - the pour certifies a configuration the product cannot reproduce

`kernel/cast.py:429-434` reads the manifest and pins `FORGE_SEED` for the validation subprocess,
with a comment acknowledging the `first-forge` default. It then stamps `validated`.

The shipped product carries no such pin. So `validated` means "boots when someone else supplies a
missing environment variable", not "boots". `P_kindlands_saga` is stamped `validated` and cannot
start. This is the brief-#330 pattern exactly: the instrument constructs an environment the
subject cannot reproduce, then certifies the subject.

### F3 (HIGH) - `spiral-ascent` cannot boot at all, on main, today

Pre-existing on `origin/main`, unrelated to the pour (confirmed by running the gate directly in
the engine checkout):

```
  first-forge    job ladder loaded OK
  spiral-ascent  BlueprintError: job system: callings shipped with no ability kit:
                 ['forgewright', 'pathfinder', 'vanguard'].
  aethryn        job ladder loaded OK
```

`spiral-ascent` ships no `abilities.yaml` and three callings that require one. `CLAUDE.md`
advertises it as a shipped game ("Seeds-are-games (`first-forge`, `spiral-ascent`)"). It is not
one; it cannot start.

### F4 (MEDIUM) - the suite never boots a shipped Blueprint

`tests/test_seed_selection.py` is titled *"a seed is a game. Codeforge boots first-forge or
spiral-ascent"* and asserts the pack **directory exists**. Other tests read `spiral-ascent`'s YAML
files directly. Nothing imports the engine under each shipped pack, which is why F3 sat on a green
main. A parametrized boot-every-Blueprint test would have caught F3 and F1 both.

### F5 (LOW) - excluded caches are emitted anyway

The manifest lists `environment + caches (.venv/ · __pycache__/)` as excluded. The poured product
contains **4 `__pycache__` directories and 170 `.pyc` files**. Because the copy preserves mtime and
size, that bytecode can be treated as valid rather than recompiled. Runtime state (`codeforge.db`,
`save.json`, `characters.json`, `accounts.json`) is correctly excluded.

### F6 (LOW) - a blind character slice mangles the failure message

`kernel/cast.py:447-450` builds the failure detail as `(stdout + " " + stderr)[-200:]`. It cuts
mid-token and pulls in the traceback's source echo, so a real failure renders as:

```
  NOT validated: b system: callings shipped with no ability kit: {sorted(unarmed)}."
```

`job` became `b`, and `{sorted(unarmed)}` is the unrendered f-string source, not a value. On a
longer traceback the actual exception line would be cut out entirely.

---

## Two corrections to my own measurements, recorded because they are the pattern

1. I first reported `restore_character` as dropping the job. It does not. My probe planted a
   hardcoded `"smith"`, which is not a calling in the Blueprint under test, and
   `restore_character:317-321` deliberately restores a jobless sheet for a calling absent from the
   current world ("seeds are games"). **The instrument was wrong, not the engine.** The probe now
   takes its calling from the Blueprint under test, which is also what makes the aethryn run above
   meaningful.

2. I reported `cast generate` as exiting 0 on a failed validation. It exits **1** and stamps
   `not_validated`, correctly. My measurement read `$?` through a `sed` pipeline.

Third near-miss: I briefly concluded F3 was pour-specific because `spiral-ascent` loaded 16 rooms
in the engine checkout. `kernel.world.world` never imports `job_ladder`, so that check never ran
the gate that was failing.

---

## Environment gaps found on the PC (not code defects)

- **`codeforge-claude` has no `.venv`.** The Makefile calls `python3` directly and assumes an
  activated venv, so `make` in this worktree silently ran every gate against a bare system
  Python 3.14. Gate results from an agent worktree without a venv are not trustworthy. Also
  `make env` uses `.venv/bin/pip`, a POSIX path that does not exist on Windows.
- **Go is not installed.** `make check` stops at `lint-go` before reaching any Python gate. A
  `winget install GoLang.Go` is pending on a UAC prompt and needs a click.

## Proof Run, this session

```
lint-python      1124 files already formatted / ruff: All checks passed!
typecheck-python Success: no issues found in 827 source files
test             5281 passed, 56 skipped in 23.66s
```

Run with the project venv on PATH. `make check` in full is blocked on `lint-go` (Go absent).

## Reusable Part signals

- **reimplemented:** none observed.
- **recurrence:** yes, and it is the theme. Three separate proofs this week failed because the
  harness measured a context the subject does not have: the contract gate's `sys.path[0]`, the
  Source.Connection hardcoded `"josh"`, and now F2's pinned `FORGE_SEED`. Same shape each time.
- **generalizable:** the subprocess-per-stage + JSON-handshake + `--sabotage` structure is a
  general instrument for any "does the artifact survive leaving this process" question. Candidate
  Working Shelf part once a second consumer appears.
- **friction:** an agent worktree with no venv gives green-looking gate output from the wrong
  interpreter, with no warning. Worth a guard.
