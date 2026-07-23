# Publishing `codeforge-shelf`

The Hardware Store shelf (`parts/shelf/`) is poured into a standalone, release-ready package by
`parts/shelf_pour.py`. Everything up to the irreversible publish is automated and gated; the final
publish is a human trigger (it claims a public name and exposes a public artifact).

## What the tooling already does

```
make shelf-pour                 # pour codeforge_shelf/ + tests + pyproject + LICENSE + README
make shelf-build                # pour, then BUILD the wheel and install it into a fresh venv
```

`make shelf-build` is the release-grade proof: it builds `codeforge_shelf-<v>-py3-none-any.whl`
and imports it from a clean venv, proving `pip install codeforge-shelf` works for a stranger with
no CodeForge engine present. The poured `pyproject.toml` already carries the release metadata
(SPDX `license = "MIT"`, `authors`, `classifiers`, `[project.urls]`, `readme`) and the bundled
`LICENSE`. Runtime deps are auto-detected (`fastapi`, `pydantic`, `structlog`); test deps are a
`[test]` extra.

## The final step (human trigger, irreversible)

Pick one. Both claim a public name that cannot be un-claimed, so this is Josh's call:

1. **Its own GitHub repo** (installable immediately, no index):
   - Create `MatrymLabs/codeforge-shelf` (public), push the poured tree.
   - Consumers: `pip install git+https://github.com/MatrymLabs/codeforge-shelf`.

2. **PyPI** (a real `pip install codeforge-shelf`) -- **Trusted Publishing, no token stored.**
   The poured repo already ships `.github/workflows/release.yml` (OIDC publish on a GitHub
   Release) and `test.yml` (runs the poured tests). Two one-time human steps:
   1. On PyPI: add a **pending publisher** for the project `codeforge-shelf` -- repository
      `MatrymLabs/codeforge-shelf`, workflow `release.yml`, environment `pypi`. (This reserves the
      name; once claimed it is permanently yours.)
   2. On GitHub: create the `pypi` environment (Settings -> Environments), then cut a
      **Release** tagged `v0.1.0`. The release workflow builds sdist + wheel and publishes.
   - Manual fallback: `python -m build` then `twine upload dist/*` with an API token.

## Honesty notes

- Version is `0.1.0`; bump it in `shelf_pour._pyproject` before each release.
- `requires-python = ">=3.11"` is the declared floor; the cores are developed and tested on 3.13.
  If you publish, run the suite on the lowest supported version first, or raise the floor to `3.13`.
- The 2 engine-coupled twins (`console`, `observability`) keep their integration tests in this repo;
  the poured package ships the 25 standalone twins and passes them with no engine present.
