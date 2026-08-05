"""Clean-checkout proof: migrations and the canonical CodeForge startup work together."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_clean_migrated_checkout_boots_the_product_platform(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parent.parent
    env = os.environ.copy()
    env.update(
        {
            "CODEFORGE_DB": str(tmp_path / "codeforge.db"),
            "CODEFORGE_SEED_REGISTRY": "file",
            "FORGE_SEED": "aethryn",
            "SEEDLAB_HOME": str(tmp_path / ".seedlab"),
        }
    )
    script = """
from pathlib import Path

from alembic import command
from alembic.config import Config

from kernel.persistence_doctor import inspect_persistence
from kernel.platform import bootstrap_platform

repo = Path.cwd()
config = Config(str(repo / "alembic.ini"))
config.set_main_option("script_location", str(repo / "migrations"))
command.upgrade(config, "head")

startup = bootstrap_platform(seed="aethryn", selection_source="default")
assert startup.status("engine").state == "initialized"
assert startup.status("seed-runtime").detail == "active Seed: aethryn"
assert startup.status("workspace").detail.endswith("available for Aethryn")

doctor = inspect_persistence()
assert doctor.exit_code == 0
assert doctor.overall == "warnings"  # no backup has been created in this clean environment
states = {check.name: check.state for check in doctor.checks}
assert states["schema"] == "ready"
assert states["migrations"] == "ready"
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "codeforge.db").is_file()
    assert (tmp_path / ".seedlab" / "seeds" / "aethryn.json").is_file()
