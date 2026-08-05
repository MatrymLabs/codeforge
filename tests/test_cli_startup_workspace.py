"""The product CLI reaches the unified bootstrap before dispatching its server command."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_cli_api_path_bootstraps_aethryn_before_dispatch(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["FORGE_SEED"] = "unexpected"
    env["SEEDLAB_HOME"] = str(tmp_path / ".seedlab")
    env["CODEFORGE_DB"] = str(tmp_path / "codeforge.db")
    script = """
import json
import adapters.cli as cli

cli._DISPATCH["api"] = lambda args: 0
exit_code = cli.main(["--seed", "aethryn", "api"])
print(json.dumps({"exit_code": exit_code}))
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"exit_code": 0}
    assert (tmp_path / ".seedlab" / "seeds" / "aethryn.json").is_file()
