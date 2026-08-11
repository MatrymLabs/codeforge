# DISPATCH CX-003

```yaml
packet_id:            CX-003
title:                Flight 2, the platform models a REAL repository
stream:               platform
owner:                Codex
reviewer:             Claude Code (re-runs every command independently)
merges:               founder
size:                 medium
flight:               M2 Engine Real
leg:                  2A

goal: >
  Point the platform at a genuine git working tree and prove the state it records corresponds to
  that tree as git itself reports it, and survives a process boundary. Every proof to date points
  at a fabricated .git written by the test itself, which proves the parser reads bytes it was
  handed, not that the platform can model a real codebase.

preconditions: >
  origin/main at or after the CX-002 merge. The platform proof runs green (driven this session).
  A Seed boots clean with kernel.world made unimportable (proven this session, not your job).
  tests/test_seed_backup.py covers backup/mutate/restore already; leave it alone.

verification_command: |
  cd /home/josh/Projects/MatrymLabs/codeforge
  export PATH="$PWD/.venv/bin:$PATH"
  make check

definition_of_done: >
  tests/test_repository_proof.py passes as given and unmodified; `seedlab repo-proof --source
  <path>` models a real tree and writes a JSON report artifact; the proof is DRIVEN against a real
  repository with the transcript pasted in the RETURN, showing the recorded branch and commit
  matching `git rev-parse`; make check green.

out_of_scope: >
  kernel/world/ anything. The no-game boundary gate (Claude Code, in flight).
  kernel/shelf/console.py, which is currently broken and is Claude Code's repair in flight.
  Backup and restore, already proven in tests/test_seed_backup.py.

approval_gates: >
  Founder merges. No self-certification. Claude Code re-runs every command independently before
  the verdict. Any change to the source_connector denylist or to the read-only constraint STOPS
  and returns the decision rather than proceeding.

rollback: >
  git revert the merge commit. The module is new and only the CLI verb references it.

file_allowlist:
  - kernel/seedlab/repository_proof.py      # NEW. the proof. yours to write
  - tests/test_repository_proof.py          # NEW. contract tests, verbatim from this packet
  - adapters/cli.py                         # to expose it as `seedlab repo-proof`, that verb only
  - registry/designations/modules.json      # the completeness gate WILL demand the new module
  - handoff/CX-003/RETURN.md                # NEW. you are explicitly authorised to create this

contract_tests:       tests/test_repository_proof.py
contract_test_policy: |
  ASSERTION-LOCKED. Given verbatim below. Create it exactly as written. You may ADD tests; you may
  NOT weaken, delete or rewrite an assertion. If an assertion is wrong, STOP and say so in the
  RETURN with your reasoning. Do not edit it into agreement with your implementation.

return_artifact:      handoff/CX-003/RETURN.md
return_authorisation: |
  EXPLICITLY AUTHORISED. Create it. Required, not optional. Its extraction block may not be blank
  ("none observed" is a valid answer; silence is not).
```

## What is already true, so you do not rebuild it

I drove all of this before writing the packet. **None of it is your job.**

`CMD` The platform proof runs green end to end today:

```
proof complete: seed-first-platform-proof-2479ee
Builds (1): run exit=0 (0.1s)     Tests (1): pytest exit=0 (0.9s)
Targets (1): first-proof-workload (cli, 6 files, manifest 8e31db47118d)
```

`CMD` A Seed boots clean with the game module made **unimportable** by an import hook, which is
Flight 2's second arrival criterion. Proven, and the hook was calibrated first (it raises on
`kernel.world`, passes `kernel.seedlab`). Do not redo this; I am turning it into a gate separately.

`CMD` Backup, mutate, restore is already covered properly in `tests/test_seed_backup.py`:
`test_restore_is_rollback_undoes_a_bad_change`, corrupt refused, non-owner refused, missing
refused. **Leave it alone.**

## The gap that is yours

Every proof the platform has ever run points at something **fabricated**. The platform proof's
source is a synthetic 4-file tree reported as `no-vcs`. `tests/test_source_connector.py` builds a
`.git/` by hand:

```python
(root / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
(root / ".git" / "refs" / "heads" / "main").write_text(_FAKE_COMMIT + "\n")
```

That is a fixture shaped like a repository, not a repository. It proves the parser reads the bytes
it was handed. It does not prove the platform can model a real codebase, which is the entire
Flight 2 claim: *"project state that reflects a real repository."*

**Your job: point the platform at a genuine git working tree and prove the state it records
corresponds to that tree, and survives a process boundary.**

## Invariant

**The recorded provenance corresponds to the repository as git itself reports it, and that
correspondence outlives the process.**

Not "a branch string was stored". The branch and commit the Seed records must equal what `git` says
about that tree, and a fresh process must recover the same facts from disk.

## Constraints, non-negotiable

1. **Read-only.** The proof never writes to, mutates, or runs anything inside the target
   repository. It reads. A proof that can modify the codebase it is inspecting is a liability.
2. **No secret leakage.** The connector's existing denylist (`.env`, keys, `.git`, `secrets*`)
   already refuses to list protected paths. Your proof must not defeat it, and the report artifact
   must not contain file CONTENTS, only metadata. Assert this in a test.
3. **No subprocess in production code.** `source_connector` reads git facts from `.git/` files on
   purpose. Keep that. Your TESTS may shell out to real `git` to build a real tree; the module may
   not.
4. **A non-git directory is not an error.** It is honestly recorded as `no-vcs`, exactly as today.
   Refusing it would make the platform less useful, not safer.

## The contract tests, verbatim

Create `tests/test_repository_proof.py` with exactly this content.

```python
"""Test twin for kernel/seedlab/repository_proof.py -- the platform models a REAL repository.

Acceptance: a genuine git working tree is modeled, and the branch and commit recorded match what
git itself reports; a fresh process recovers the same facts; a non-git directory is honestly
recorded as no-vcs rather than refused.

Refusal (fail loud): the report never carries file CONTENTS, only metadata; a protected path is
never listed; a path outside the target tree is refused.

Why this file exists: every prior proof pointed at a fabricated .git written by the test itself,
which proves the parser reads bytes it was handed, not that the platform can model a real codebase.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from kernel.seedlab.repository_proof import model_repository


def _real_repo(root: Path) -> tuple[str, str]:
    """A REAL git repository, built by git itself. Returns (branch, short_commit)."""
    root.mkdir(parents=True, exist_ok=True)
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run([*git[:3], "init", "-q", "-b", "main"], check=True, capture_output=True)
    (root / "app.py").write_text("def main():\n    return 0\n", encoding="utf-8")
    (root / "README.md").write_text("# real\n", encoding="utf-8")
    (root / ".env").write_text("SECRET_TOKEN=hunter2\n", encoding="utf-8")  # must never be listed
    subprocess.run([*git, "add", "-A"], check=True, capture_output=True)
    subprocess.run([*git, "commit", "-qm", "first"], check=True, capture_output=True)
    branch = subprocess.run(
        [*git[:3], "rev-parse", "--abbrev-ref", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    commit = subprocess.run(
        [*git[:3], "rev-parse", "--short", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    return branch, commit


def test_the_recorded_branch_and_commit_are_what_git_reports(tmp_path: Path) -> None:
    """The whole point. Not 'a string was stored' -- the SAME string git itself reports."""
    branch, commit = _real_repo(tmp_path / "repo")
    modeled = model_repository(tmp_path / "repo")
    assert modeled.branch == branch
    assert modeled.commit.startswith(commit[:7])


def test_a_real_repository_is_not_reported_as_no_vcs(tmp_path: Path) -> None:
    _real_repo(tmp_path / "repo")
    assert model_repository(tmp_path / "repo").vcs != "no-vcs"


def test_a_plain_directory_is_honestly_no_vcs_not_an_error(tmp_path: Path) -> None:
    """Refusing it would make the platform less useful, not safer."""
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "notes.txt").write_text("hello\n", encoding="utf-8")
    assert model_repository(plain).vcs == "no-vcs"


def test_a_protected_path_is_never_listed(tmp_path: Path) -> None:
    _real_repo(tmp_path / "repo")
    listed = " ".join(model_repository(tmp_path / "repo").files)
    assert ".env" not in listed
    assert ".git" not in listed


def test_the_report_carries_metadata_and_never_file_contents(tmp_path: Path) -> None:
    """A report that embeds source is an exfiltration path, not an artifact."""
    _real_repo(tmp_path / "repo")
    blob = str(model_repository(tmp_path / "repo").to_dict())
    assert "hunter2" not in blob  # the .env secret
    assert "def main" not in blob  # the source itself


def test_a_missing_target_is_refused_loudly(tmp_path: Path) -> None:
    with pytest.raises(Exception):
        model_repository(tmp_path / "nope")


def test_the_recorded_facts_outlive_the_process(tmp_path: Path) -> None:
    """A fresh process must recover the same correspondence from disk, not recompute it."""
    import importlib

    from kernel.seedlab import repository_proof

    branch, commit = _real_repo(tmp_path / "repo")
    first = model_repository(tmp_path / "repo")
    store = tmp_path / "store"
    repository_proof.persist(first, store)

    importlib.reload(repository_proof)
    recovered = repository_proof.recover(store, first.source_id)

    assert recovered.branch == branch
    assert recovered.commit == first.commit
    assert recovered.source_id == first.source_id
```

## A warning about that reload, learned the hard way

`importlib.reload` replaces the module's classes with NEW objects. Any test you ADD after
`test_the_recorded_facts_outlive_the_process` that catches an exception type imported at the top of
the file will silently stop matching the error it just provoked. If you add refusal tests, resolve
the exception through the module (`repository_proof.SomeError`), not through a top-level import.
This cost real time in CX-002; you are being told so it does not cost you any.

## Definition of done

```bash
cd /home/josh/Projects/MatrymLabs/codeforge
export PATH="$PWD/.venv/bin:$PATH"
make check
```

- `tests/test_repository_proof.py` passes as given, unmodified.
- `seedlab repo-proof --source <path>` models a real tree and writes a JSON report artifact.
- **Drive it against a real repository and paste the transcript in the RETURN.** Point it at this
  repo itself (read-only) and show the branch and commit it recorded matching `git rev-parse`.
- `make check` green.

## Out of scope

- `kernel/world/` anything. This packet does not touch the game.
- The no-game boundary gate. Mine, in flight.
- `kernel/shelf/console.py`. Mine, in flight, and it is currently broken (three allowlist entries
  point at the retired `parts/` and `REPO_ROOT` resolves to `kernel/`). Do not fix it here.
- Backup and restore. Already proven in `tests/test_seed_backup.py`.

## Rollback

`git revert` the merge commit. The module is new and only the CLI verb references it.

## EXTRACTION CONTEXT

```yaml
store_search_result: |
  NOT YET SEARCHED. Run the consume-first search BEFORE writing, for "repository", "provenance",
  "source of truth", "git metadata", "content addressing".

  SEARCH BOTH TIERS, per ADR-0005, and log both:
    Certified Tier  hardware-store/catalog/   (6 parts)
    Working Shelf   codeforge/catalog/parts.yaml   (104 parts)

  This instruction is emphatic because I got it wrong myself. CX-002's extraction context asserted
  "none of them an idempotency record" after searching only the Certified Tier; the Working Shelf
  held a direct hit. A one-tier search that finds nothing is an INCOMPLETE search, not a clean one.

parts_to_consume: |
  UNKNOWN until you search. `Content Address` (Working Shelf) is a plausible neighbour for
  identifying a tree by its contents; judge it on its card, and record the reason either way.
  Not consuming a part is a fine answer when the card says why.

watch_for: |
  "Provenance of an external tree" is a shape the fleet has met before: federal-guidance-library
  records source + date + version + owner for every registry row, and this packet records
  source + branch + commit + owner for a repository. If the two want the same fields, that is the
  pull rule's second occurrence and belongs in the RETURN as an extraction signal, not as a
  refactor you perform here.
```
