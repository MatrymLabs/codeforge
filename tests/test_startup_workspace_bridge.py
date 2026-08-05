"""The primary startup path bridges the bundled runtime package to SeedLab."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_clean_startup_registers_aethryn_and_makes_workspace_contract_available(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["FORGE_SEED"] = "aethryn"
    env["SEEDLAB_HOME"] = str(tmp_path / ".seedlab")
    env["CODEFORGE_DB"] = str(tmp_path / "codeforge.db")
    script = """
from pathlib import Path
import json
import os

from kernel.platform import bootstrap_platform
from kernel.seedlab.workspace_contract import build_workspace_contract

startup = bootstrap_platform(seed="aethryn", selection_source="default")
contract = build_workspace_contract("aethryn", root=Path(os.environ["SEEDLAB_HOME"]))
print(json.dumps({"startup": startup.to_dict(), "contract": contract.to_dict()}))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["startup"]["seed"] == "aethryn"
    assert payload["contract"]["seed"]["name"] == "Aethryn"
    assert payload["contract"]["contract_version"] == "seedlab.workspace/1"
    assert payload["contract"]["packages"][0]["package"] == "Project.Status"
