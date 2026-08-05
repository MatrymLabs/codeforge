import pytest

from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.reference_seed import ensure_reference_seed
from kernel.seedlab.runtime_bridge import RuntimeSeedError, bind_reference_seed, bind_runtime_seed


def test_reference_seed_binds_to_the_shipped_aethryn_package(tmp_path):
    kernel = SeedKernel(FileSeedStore(tmp_path / "records"))
    ensure_reference_seed(kernel)
    binding = bind_reference_seed(kernel)
    assert binding.seed_id == "aethryn"
    assert binding.manifest["title"] == "Aethryn"
    assert binding.manifest["start_room"] == "veridia"


def test_bridge_rejects_a_seed_without_a_matching_runtime_manifest(tmp_path):
    kernel = SeedKernel(FileSeedStore(tmp_path / "records"))
    kernel.create_seed("Prototype", "owner", "test", seed_id="prototype")
    package = tmp_path / "seeds" / "prototype"
    package.mkdir(parents=True)
    (package / "rooms.yaml").write_text(
        "spawn:\n  name: Spawn\n  desc: test\n  exits: {}\n", encoding="utf-8"
    )
    (package / "world.yaml").write_text("world_id: other\n", encoding="utf-8")
    with pytest.raises(RuntimeSeedError, match="declares"):
        bind_runtime_seed(kernel, "prototype", root=tmp_path / "seeds")
