# Template: Data science / research repo

**Use when:** a repo's job is analysis - datasets, notebooks, and reproducible experiments -
rather than a shipped service. **Status for CodeForge:** reference only. CodeForge is an engine,
not an analysis repo; its "research" already lives as prose under `docs/research/` and its
experiments as `docs/pioneer_experiments/`. This template is here for a sibling repo that is
genuinely data-first (e.g. a future portfolio analysis project).

## Layout

```text
README.md                     # project goal, data sources, how to run analyses
data/                         # raw + processed datasets (large files gitignored)
notebooks/                    # Jupyter notebooks - prototype/exploratory analyses
src/ or scripts/              # reusable Python/R for data processing
env/ or requirements.txt      # environment spec for reproducibility
outputs/                      # charts, models, tables (usually gitignored)
.github/workflows/ci.yml      # lint + test the src/, optionally execute notebooks
```

## Boundaries

- **Data is not code.** Raw and processed datasets live under `data/`, large ones gitignored
  (tracked via a manifest or DVC, not committed blobs). CodeForge already uses `data/` for
  career/pioneer records - a data-science repo uses it for datasets; same principle, different
  payload.
- **Notebooks prototype; `src/` productionizes.** Exploratory work lives in `notebooks/`; once a
  transform is worth keeping, it moves into importable, tested code under `src/`/`scripts/`. A
  notebook is never the source of truth for a pipeline.
- **Reproducibility is the gate.** The environment spec is pinned; `outputs/` is regenerable, not
  hand-curated. Same generated-vs-maintained discipline as ADR-0007.

## Note for CodeForge

CodeForge does not adopt this shape. Its analysis output (benchmarks, performance research,
evidence) is already structured under `benchmarks/`, `security-evidence/`, and `docs/research/`.
This template documents the archetype for completeness and for a future sibling, honoring the
prompt's request for a template library without importing an unused structure into the flagship.
