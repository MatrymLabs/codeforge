from __future__ import annotations

from pathlib import Path

from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.reference_seed import ensure_reference_seed
from kernel.seedlab.workspace_contract import build_workspace_contract
from kernel.world import workshop_state


def _evidence(contract) -> dict[str, object]:
    for package in contract.packages:
        if package.package == "Engineering.Evidence":
            return package.payload
    raise AssertionError("workspace contract omitted Engineering.Evidence")


def test_seedlab_home_is_the_shared_authority_for_workshop_state_and_registry(
    monkeypatch, tmp_path: Path
) -> None:
    home = tmp_path / ".seedlab"
    monkeypatch.setenv("SEEDLAB_HOME", str(home))
    monkeypatch.delenv("CODEFORGE_WORKSHOP_STATE", raising=False)
    monkeypatch.delenv("CODEFORGE_WORKSHOP_DRAFTS", raising=False)

    workshop_state.save_changes(
        "aethryn",
        [
            {
                "kind": "create_item",
                "payload": {"label": "forge_lantern", "name": "Forge Lantern", "room": "veridia"},
            }
        ],
    )
    workshop_state.save_drafts(
        "aethryn",
        {
            "matrym": [
                {
                    "kind": "create_npc",
                    "summary": "draft",
                    "payload": {"label": "guide", "name": "Guide", "room": "veridia"},
                }
            ]
        },
    )

    assert (home / "workshop" / "aethryn.json").is_file()
    assert (home / "workshop" / "aethryn.drafts.json").is_file()

    kernel = SeedKernel(FileSeedStore(home / "seeds"))
    ensure_reference_seed(kernel)
    contract = build_workspace_contract("aethryn", root=home)
    evidence = _evidence(contract)
    lifecycle = evidence["lifecycle"]
    assert lifecycle["content"][0]["payload"]["label"] == "forge_lantern"
    assert lifecycle["drafts"][0]["owner_id"] == "matrym"
