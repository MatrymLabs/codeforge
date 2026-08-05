"""The unified platform bootstrap coordinates existing services without a second Engine."""

import os
import subprocess
import sys
from pathlib import Path


def test_platform_bootstrap_initializes_existing_runtime(monkeypatch, tmp_path):
    env = os.environ.copy()
    env["FORGE_SEED"] = "aethryn"
    env["CODEFORGE_DB"] = str(tmp_path / "codeforge.db")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from kernel.platform import bootstrap_platform; "
                "s=bootstrap_platform(seed='aethryn', selection_source='default'); "
                "assert s.status('engine').state == 'initialized'; "
                "assert s.status('seed-runtime').detail == 'active Seed: aethryn'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert Path(tmp_path / "codeforge.db").exists()


def test_platform_status_is_structured():
    from kernel.platform import ComponentStatus, PlatformStartup
    from kernel.seed_selection import SeedSelection

    startup = PlatformStartup(
        SeedSelection("aethryn", "default"),
        (ComponentStatus("engine", "initialized", "ready"),),
    )
    assert startup.to_dict() == {
        "seed": "aethryn",
        "selection_source": "default",
        "components": [{"name": "engine", "state": "initialized", "detail": "ready"}],
    }
