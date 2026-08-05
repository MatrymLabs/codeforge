"""The unified platform bootstrap coordinates existing services without a second Engine."""

import os
import subprocess
import sys
from pathlib import Path


def test_platform_bootstrap_initializes_existing_runtime(monkeypatch, tmp_path):
    env = os.environ.copy()
    env["FORGE_SEED"] = "aethryn"
    env["CODEFORGE_DB"] = str(tmp_path / "codeforge.db")
    env["SEEDLAB_HOME"] = str(tmp_path / ".seedlab")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from kernel.platform import bootstrap_platform; "
                "s=bootstrap_platform(seed='aethryn', selection_source='default'); "
                "assert s.status('engine').state == 'initialized'; "
                "assert s.status('seed-runtime').detail == 'active Seed: aethryn'; "
                "assert s.status('seed-registry').state == 'initialized'; "
                "assert s.status('workspace').detail.endswith('available for Aethryn')"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert Path(tmp_path / "codeforge.db").exists()
    assert Path(tmp_path / ".seedlab" / "seeds" / "aethryn.json").exists()


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


def test_platform_bootstrap_can_use_sql_seed_registry(monkeypatch, tmp_path):
    env = os.environ.copy()
    env["FORGE_SEED"] = "aethryn"
    env["CODEFORGE_SEED_REGISTRY"] = "sql"
    env["CODEFORGE_DB"] = str(tmp_path / "codeforge.db")
    env["SEEDLAB_HOME"] = str(tmp_path / ".seedlab")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "from kernel.platform import bootstrap_platform; "
                "s=bootstrap_platform(seed='aethryn', selection_source='default'); "
                "assert s.status('seed-registry').detail.startswith('sql:'); "
                "assert s.status('workspace').state == 'initialized'"
            ),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".seedlab" / "seeds" / "aethryn.json").exists()
