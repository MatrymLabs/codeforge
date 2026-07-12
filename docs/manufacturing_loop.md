# The Manufacturing Loop (the connected spine)

*The vision's highest architectural risk -- "no connected manufacturing spine end-to-end"
-- closed for one part on 2026-07-12. This documents the three modules that connect it
and the command that proves it.*

## Run it

```
loop trace workflow-engine     # in-game, from the Workshop
make loop                      # from the shell (PART=<id> to trace another part)
python -m parts.loop trace workflow-engine
```

Exit 0 on a PASS verdict, 1 on FAIL. Every run files dated evidence under
`reports/loop/` (git-ignored, reproducible from the commit).

## The three parts

| Module | Responsibility |
|---|---|
| `parts/manifest.py` | **PartManifest** -- the typed, machine-readable contract for a reusable part. Loaded from `docs/hardware/<part_id>.yaml`, validated fail-loud (`ManifestError`), round-trips (`from_dict(to_dict(m)) == m` is a tested law). |
| `parts/assembly.py` | **Assembly** -- discovers what composes a part by walking its source's AST for `parts.*` imports (static imports only, stated honestly), resolves them against the Hardware Store catalog, verifies sources and tests exist, and files evidence under `reports/assembly/`. |
| `parts/loop.py` | **The tracer** -- walks one part through seven stages: manifest, catalog, blueprint (optional), registry, assembly, tests, docs. Each stage returns pass/fail/skip with a reason; the verdict is the conjunction. |

## The seven stages

1. **manifest** -- the YAML manifest loads and validates
2. **catalog** -- the part is stocked in `catalog/parts.yaml`
3. **blueprint** -- a filed Blueprint exists (skip if none; not required)
4. **registry** -- the part's source file has a filed designation
5. **assembly** -- imports discovered, dependencies resolved, files verified
6. **tests** -- declared test files exist and are non-empty
7. **docs** -- Markdown and/or YAML documentation present

## Design rules it honors

- **Fail loud at gates**: `ManifestError` / `AssemblyError` are `ValueError`s with names.
- **Pure data objects**: `PartManifest`, `Assembly`, `StageResult`, `TraceReport` are
  frozen dataclasses.
- **Evidence, not claims**: a trace is filed, dated, and reproducible; the verdict is
  computed, never stored.
- **Trust-boundary hardening**: the manifest gate is fuzz-tested (`make fuzz`) -- it
  refuses junk with its own error type, never crashes (two real defects found and fixed
  by that harness on day one).

## What it does not do yet (honest labels)

Stages 8+ of the full engineering loop (generate, simulate, repair, package, deploy,
monitor) are not traced; the Foundry and Cast cover generation and packaging as separate,
human-gated flows. Import discovery is static-only. One part (workflow-engine) is proven;
tracing every cataloged part is a later slice.
