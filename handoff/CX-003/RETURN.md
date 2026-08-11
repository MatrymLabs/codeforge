# RETURN CX-003

packet_id: CX-003
status: BLOCKED
branch: agent/codex/cx-003
pr_url: not opened, assertion-locked contract blocks the required full gate

## Commands run

CMD `./.venv/bin/pytest -q tests/test_repository_proof.py` exited 0:

```text
8 passed in 0.66s
```

CMD real repository drive, using the configured adapter function because the local `codeforge`
entry-point script has a stale interpreter path, exited 0:

```text
repository proof complete: repository-0fb509b3f804607a
vcs: git, branch: agent/codex/cx-003, commit: d4dd75299a01
git branch: agent/codex/cx-003
git commit: d4dd7529
recorded branch: agent/codex/cx-003
recorded commit: d4dd75299a01
recorded vcs: git
```

CMD `export PATH="$PWD/.venv/bin:$PATH" && make check` exited 2:

```text
ruff format --check .
1056 files already formatted
ruff check .
B017 Do not assert blind exception: `Exception`
  --> tests/test_repository_proof.py:80:10
   |
79 | def test_a_missing_target_is_refused_loudly(tmp_path: Path) -> None:
80 |     with pytest.raises(Exception):
   |          ^^^^^^^^^^^^^^^^^^^^^^^^
81 |         model_repository(tmp_path / "nope")
   |

Found 1 error.
make: *** [Makefile:29: lint] Error 1
```

## Files touched

- `kernel/seedlab/repository_proof.py`
- `tests/test_repository_proof.py`
- `adapters/cli.py`
- `registry/designations/modules.json`
- `handoff/CX-003/RETURN.md`

All are in the packet allowlist.

## Blocker

The assertion-locked packet requires `with pytest.raises(Exception):`. The repository lint rule
rejects that exact assertion as B017. Editing the assertion or adding an inline suppression would
change the required contract test, so no workaround was attempted. Founder or packet-author ruling
is required.

## Consume-first log

- Certified Tier: searched `hardware-store/catalog/` for repository, provenance, source of truth,
  git metadata, and content addressing. `source-monitor` is a source-drift classifier, not a local
  repository snapshot or report, so it was not consumed.
- Working Shelf: searched `catalog/parts.yaml` with the same terms. Consumed the existing
  path-bounded reader and provenance-record surfaces through `LocalSource` and `Provenance`; no new
  file-boundary or provenance mechanism was introduced.

## Extraction signals

reimplemented: none. The source boundary and provenance fields are consumed from existing SeedLab
surfaces.

recurrence: external-tree provenance has the same source plus version shape as the
federal-guidance-library record pattern named in the packet. This is the second occurrence signal.

generalizable: a metadata-only, restart-recoverable repository provenance report would apply to any
source tree a Seed connects.

friction: `LocalSource` handles ordinary `.git` directories but not linked-worktree pointer files;
the proof adds that metadata interpretation without changing the connector boundary.

pattern_shapes: source identity + source location + branch/version + approved file metadata +
durable recovery. The nearest prior shape is external source provenance, not source content capture.

dissent: The packet's exact broad exception assertion conflicts with the repository's enforced B017
lint rule. I do not have authority to change either measuring instrument.
