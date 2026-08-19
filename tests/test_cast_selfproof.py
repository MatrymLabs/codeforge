"""Contract tests for the detached Target Product persistence proof."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def _write_product(root: Path) -> Path:
    package = root / "kernel" / "world"
    package.mkdir(parents=True)
    (root / "kernel" / "__init__.py").write_text("\n")
    (package / "__init__.py").write_text("\n")
    (package / "jobs.py").write_text("JOBS = {'scout': object()}\n")
    (package / "world.py").write_text("WORLD = {'forge': {}, 'yard': {}}\n")
    (package / "session.py").write_text(
        "class Session:\n"
        "    def __init__(self, player_id, location='forge'):\n"
        "        self.player_id = player_id\n"
        "        self.location = location\n"
        "        self.named = False\n"
        "        self.job = ''\n"
        "        self.level = 1\n"
        "        self.xp = 0\n"
        "        self.coins = 0\n"
        "        self.rank = 'player'\n"
        "        self.account = ''\n"
    )
    (package / "characters.py").write_text(
        """import json, os
from pathlib import Path

def _path(): return Path(os.environ['CODEFORGE_DB'])

def save_character(session):
    _path().write_text(json.dumps({'name': session.player_id, 'job': session.job,
        'level': session.level, 'xp': session.xp, 'coins': session.coins,
        'rank': session.rank, 'account': session.account, 'location': session.location}))

def load_character(name):
    if not _path().exists(): return None
    data = json.loads(_path().read_text())
    return data if data.get('name') == name else None
"""
    )
    (package / "db.py").write_text(
        "import os, shutil\n"
        "from pathlib import Path\n"
        "DB_PATH = Path(os.environ['CODEFORGE_DB'])\n"
        "def backup_db(dest_dir=None):\n"
        "    dest = Path(dest_dir or DB_PATH.parent / 'backups')\n"
        "    dest.mkdir(parents=True, exist_ok=True)\n"
        "    out = dest / 'proof.db'\n"
        "    shutil.copy2(DB_PATH, out)\n"
        "    return out\n"
        "def restore_db(source, dest=None):\n"
        "    target = Path(dest or DB_PATH)\n"
        "    shutil.copy2(source, target)\n"
        "    return target\n"
    )
    scripts = root / "scripts"
    scripts.mkdir()
    shutil.copy2(Path(__file__).parents[1] / "scripts" / "cast_selfproof.py", scripts)
    return scripts / "cast_selfproof.py"


def _run(product: Path) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    env["CODEFORGE_DB"] = str(product / "codeforge.db")
    return subprocess.run(
        [sys.executable, "scripts/cast_selfproof.py"],
        cwd=product,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_selfproof_covers_persist_restart_and_survive(tmp_path: Path) -> None:
    _write_product(tmp_path)
    result = _run(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "[PASS] persist" in result.stdout
    assert "[PASS] restart" in result.stdout
    assert "[PASS] survive" in result.stdout
    assert "VERDICT: PASS" in result.stdout


def test_selfproof_refuses_when_persisted_database_is_deleted(tmp_path: Path) -> None:
    _write_product(tmp_path)
    first = _run(tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    (tmp_path / "codeforge.db").unlink()
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "REFUSED: persisted database is missing" in result.stdout


def test_selfproof_refuses_a_corrupt_persisted_field_differently(tmp_path: Path) -> None:
    _write_product(tmp_path)
    first = _run(tmp_path)
    assert first.returncode == 0, first.stdout + first.stderr
    database = tmp_path / "codeforge.db"
    saved = json.loads(database.read_text())
    saved["level"] = 99
    database.write_text(json.dumps(saved))
    result = _run(tmp_path)
    assert result.returncode == 1
    assert "REFUSED: persisted field mismatch" in result.stdout
    assert "level" in result.stdout
