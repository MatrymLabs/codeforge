"""CF-305: keep generic Seed services independent of Aethryn game mechanics."""

from __future__ import annotations

import ast
from pathlib import Path

from kernel.seedlab.jobs import JobRunner
from kernel.seedlab.project_model import Provenance
from kernel.seedlab.source_connector import LocalSource

_ROOT = Path(__file__).resolve().parent.parent
_GENERIC_SEED_MODULES = (
    "kernel/seedlab/backup.py",
    "kernel/seedlab/form.py",
    "kernel/seedlab/jobs.py",
    "kernel/seedlab/kernel.py",
    "kernel/seedlab/model_store.py",
    "kernel/seedlab/operational_baseline.py",
    "kernel/seedlab/project_hub.py",
    "kernel/seedlab/project_model.py",
    "kernel/seedlab/provision.py",
    "kernel/seedlab/source_connector.py",
    "kernel/seedlab/source_modeler.py",
    "kernel/seedlab/tool_runner.py",
)


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_generic_seed_services_do_not_import_the_aethryn_world() -> None:
    for relative in _GENERIC_SEED_MODULES:
        imports = _imports(_ROOT / relative)
        assert not any(name.startswith("kernel.world") for name in imports), relative
        assert not any("aethryn" in name.lower() for name in imports), relative


def test_one_seed_contract_runs_unchanged_in_two_consumers(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    second_root = tmp_path / "second"
    first_root.mkdir()
    second_root.mkdir()
    first = JobRunner(
        LocalSource(first_root, Provenance("first-source", owner="alice", license="internal")),
        seed_id="first-forge",
        requested_by="alice",
        clock=lambda: "2026-08-05T00:00:00Z",
        id_minter=lambda kind: f"first-{kind}",
    ).test("python-version")
    second = JobRunner(
        LocalSource(second_root, Provenance("second-source", owner="bob", license="internal")),
        seed_id="non-game-seed",
        requested_by="bob",
        clock=lambda: "2026-08-05T00:00:00Z",
        id_minter=lambda kind: f"second-{kind}",
    ).test("python-version")
    assert first.ok and second.ok
    assert first.event().event_type == second.event().event_type == "test.completed"
    assert first.event().seed_id != second.event().seed_id
