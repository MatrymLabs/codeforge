# RETURN CX-003

packet_id: CX-003
status: PARTIAL
branch: agent/codex/cx-003
pr_url: https://github.com/MatrymLabs/codeforge/pull/914

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

CMD initial `export PATH="$PWD/.venv/bin:$PATH" && make check` exited 2 before packet-author
amendment:

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

## Packet-author amendment

The packet author authorised exactly one assertion change: the missing-target assertion now catches
`SourceConnectorError`, the error emitted by the consumed `LocalSource` boundary. This is more
truthful than wrapping that error in a new proof exception. Ruff B017 then passed.

CMD amended `make check` was attempted repeatedly. It completed lint, import contracts, mypy, and
entered the 5,210-item coverage suite, but this execution host terminated foreground commands at
approximately 30 seconds before an exit marker. A detached retry wrote only `ruff format --check .`
then exited without an exit marker. No green full-gate claim is made.

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

dissent: The original assertion was unmergeable under B017 and was amended only with explicit
packet-author authority. Full-gate completion remains unverified because the execution host stopped
the coverage run before its exit status.
