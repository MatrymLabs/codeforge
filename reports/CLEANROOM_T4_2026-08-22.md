# Clean Room Tier 4 — 2026-08-22

## Boundary

Fresh clone:

```text
git clone https://github.com/MatrymLabs/codeforge.git C:\Projects\MatrymLabs\cleanroom-t4b-20260822
```

Only `README.md` in that clone was read. No source file, Makefile, test, or second project
document was opened. No repair, package installation, PATH edit, or venv activation was added
beyond commands the README presented.

The clone URL came from the README's HTTPS command. The README also presents the repository as
`codeforge` after `cd codeforge`; the explicit destination above placed the fresh clone at that
directory, and all following commands ran from it.

## Attempts: 8/8

The first output line is the first line emitted by the command. For compound commands, the row is
the literal README line and the exit is the compound command's exit.

| # | README command | exit | first output line |
|---:|---|---:|---|
| 1 | `git clone https://github.com/MatrymLabs/codeforge` | 0 | `Cloning into 'C:\Projects\MatrymLabs\cleanroom-t4b-20260822'...` |
| 2 | `cd codeforge` | 0 | working directory entered as the fresh clone |
| 3 | `make env && make deploy-proof` | 0 | `git config core.hooksPath scripts/hooks` |
| 4 | `make env` | 0 | `git config core.hooksPath scripts/hooks` |
| 5 | `make check` | 2 | `ruff format --check .` |
| 6 | `spark` | 1 | `Traceback (most recent call last):` |
| 7 | `codeforge web` | 1 | `Traceback (most recent call last):` |
| 8 | `codeforge api` | 1 | `Traceback (most recent call last):` |

The successful deployment proof printed `boot verdict: BOOTED + SERVED`, with a 10,681-room
world at spawn `veridia`. `make check` passed formatting, Ruff, Rust, and two Go lanes before
`native/spine` reported missing generated `codeforge/spine/telemetrypb` and exited 2. The three
CLI failures came from the machine's global executables and ended with `ModuleNotFoundError:
No module named 'parts'`; no PATH or activation workaround was attempted.

## Hesitations

The first disbelief was the README's `~11s` two-command claim: this fresh Windows run had to
build and install the locked environment before the deployment proof, so the observed run was not
an eleven-second first run.

The first confusion was the README's POSIX activation example, `source .venv/Scripts/activate`,
inside a Windows procedure; the README does not state how a PowerShell reader should activate it.

## 2026-08-21 findings

### Fixed

- The SSH clone instruction is now HTTPS.
- `make env` no longer depended on `ensurepip` or a separately available `pip`; uv built the
  environment and installed the locked set.
- Ruff was available through the environment and passed in `make check`.
- `cd codeforge` succeeded in the fresh clone.
- The documented deployment proof now completed with `BOOTED + SERVED`.

### Survive

- `spark` still does not start from the README procedure. It resolved to a global executable and
  failed with `ModuleNotFoundError: No module named 'parts'`.
- `codeforge web` and `codeforge api` still do not start from the README procedure. Both resolved
  to the same global executable and failed with the same missing-module error.

### New

- The README now presents `make check` as Quick Start, and it reaches the native spine lane before
  failing because generated `codeforge/spine/telemetrypb` is absent. This is a new first-run
  finding for the current README surface.

No code changed in the fresh clone. The only repository change for this order is this report in
the codeforge bench.
