"""Test twin for parts/seedlab/source_modeler.py -- extract a ProjectModel from a registered source.

Acceptance: identity comes from a manifest (else the dir name); entities + interfaces are inferred
from the layout; provenance links the model to its source; unknowns state what was NOT determined;
`model_and_store` persists it, and the full flow lights up the Project Hub's `models` facet.

Refusal / honesty: the modeler never claims to have inferred behavior it did not (states/actions/
inputs/outputs stay empty and are named in `unknowns`).
"""

from __future__ import annotations

from pathlib import Path

from parts.seedlab.kernel import InMemorySeedStore, SeedKernel
from parts.seedlab.model_store import FileModelStore, InMemorySeedModels, model_labels
from parts.seedlab.project_hub import ProjectHub, ProjectState
from parts.seedlab.project_model import Provenance
from parts.seedlab.source_connector import LocalSource, SourceConnectorError
from parts.seedlab.source_modeler import model_and_store, model_from_source


def _cli_project(tmp_path: Path, *, with_pyproject: bool = True) -> LocalSource:
    """A tiny CLI-shaped source: a package, a runnable module, a test, and maybe a manifest."""
    root = tmp_path / "taskledger"
    (root / "taskledger").mkdir(parents=True)
    (root / "tests").mkdir()
    (root / "taskledger" / "__init__.py").write_text("", encoding="utf-8")
    (root / "taskledger" / "ledger.py").write_text("class Ledger:\n    pass\n", encoding="utf-8")
    (root / "taskledger" / "__main__.py").write_text("print('hi')\n", encoding="utf-8")
    (root / "tests" / "test_ledger.py").write_text(
        "def test_x():\n    assert True\n", encoding="utf-8"
    )
    if with_pyproject:
        (root / "pyproject.toml").write_text(
            "[project]\nname = 'task-ledger'\n[project.scripts]\ntl = 'taskledger.__main__:main'\n",
            encoding="utf-8",
        )
    return LocalSource(root, Provenance("demo-src", owner="josh", visibility="private"))


# --- acceptance --------------------------------------------------------------------------------
def test_identity_comes_from_the_manifest(tmp_path: Path) -> None:
    model = model_from_source(_cli_project(tmp_path))
    assert model.identity == "task-ledger"


def test_identity_falls_back_to_dir_name(tmp_path: Path) -> None:
    model = model_from_source(_cli_project(tmp_path, with_pyproject=False))
    assert model.identity == "taskledger"  # the directory name
    assert any("directory name" in u for u in model.unknowns)


def test_entities_inferred_from_layout(tmp_path: Path) -> None:
    ents = model_from_source(_cli_project(tmp_path)).entities
    assert "taskledger" in ents and "ledger" in ents  # top-level package + a module
    assert "test_ledger" not in ents  # tests are not entities


def test_interfaces_detect_entry_points(tmp_path: Path) -> None:
    ifaces = model_from_source(_cli_project(tmp_path)).interfaces
    assert "pyproject.toml" in ifaces
    assert any(i.endswith("__main__.py") for i in ifaces)
    assert "script:tl" in ifaces  # a declared console script


def test_provenance_links_to_source(tmp_path: Path) -> None:
    model = model_from_source(_cli_project(tmp_path))
    assert model.provenance.source_id == "demo-src" and model.provenance.owner == "josh"


def test_unknowns_mark_what_was_not_inferred(tmp_path: Path) -> None:
    model = model_from_source(_cli_project(tmp_path))
    # The directive's rule: never claim complete understanding. Behavior is not inferred.
    assert model.states == [] and model.actions == [] and model.inputs == [] and model.outputs == []
    assert any("not inferred" in u or "no behavioral analysis" in u for u in model.unknowns)


def test_model_and_store_persists_and_survives_restart(tmp_path: Path) -> None:
    source = _cli_project(tmp_path)
    store = FileModelStore(tmp_path / "models")
    model = model_and_store(store, "seed-1", source)
    assert model.identity == "task-ledger"
    # Restart: a new store over the same root recovers the model.
    recovered = FileModelStore(tmp_path / "models").all_for_seed("seed-1")
    assert len(recovered) == 1 and recovered[0].identity == "task-ledger"


def test_identity_supplied_explicitly_wins(tmp_path: Path) -> None:
    model = model_from_source(_cli_project(tmp_path), identity="My Chosen Name")
    assert model.identity == "My Chosen Name"
    assert any("explicitly" in u for u in model.unknowns)


def test_identity_from_package_json(tmp_path: Path) -> None:
    root = tmp_path / "jsproj"
    root.mkdir()
    (root / "index.js").write_text("console.log('hi')\n", encoding="utf-8")
    (root / "package.json").write_text('{"name": "js-widget"}\n', encoding="utf-8")
    model = model_from_source(LocalSource(root, Provenance("js-src")))
    assert model.identity == "js-widget"


def test_a_malformed_manifest_falls_back_to_dir_name(tmp_path: Path) -> None:
    root = tmp_path / "brokenproj"
    root.mkdir()
    (root / "a.py").write_text("x = 1\n", encoding="utf-8")
    (root / "pyproject.toml").write_text("this is : not [valid toml\n", encoding="utf-8")
    model = model_from_source(LocalSource(root, Provenance("b-src")))
    assert model.identity == "brokenproj"  # a malformed manifest is ignored; dir name wins


def test_a_manifest_that_cannot_be_read_falls_back(tmp_path: Path) -> None:
    class _Flaky(LocalSource):
        def read(self, relpath: str, **kw: object) -> str:
            if relpath == "pyproject.toml":
                raise SourceConnectorError("simulated unreadable manifest")
            return super().read(relpath, **kw)  # type: ignore[arg-type]

    src = _Flaky(_cli_project(tmp_path).root, Provenance("f-src"))
    assert model_from_source(src).identity == "taskledger"  # read failed -> dir name


def test_full_flow_lights_up_the_hub_models_facet(tmp_path: Path) -> None:
    # Stage 3 + 4 -> Stage 2: register a source, model it, and the Hub's `models` facet shows it.
    kernel = SeedKernel(InMemorySeedStore(), clock=lambda: "2026-08-01T00:00:00+00:00")
    kernel.create_seed("Demo", "josh", "a demo", seed_id="seed-1")
    store = InMemorySeedModels()
    model_and_store(store, "seed-1", _cli_project(tmp_path))

    hub = ProjectHub(kernel)
    state = ProjectState("seed-1", models=model_labels(store, "seed-1"))
    assert "task-ledger" in hub.command("seed-1", "list models", state)
    assert any("task-ledger" in m for m in hub.contract("seed-1", state)["project"]["models"])
