"""Build and install proof for the distributable CodeForge wheel."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_wheel_install_contains_migrations_and_boots(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parent.parent
    wheelhouse = tmp_path / "wheelhouse"
    install_root = tmp_path / "installed"
    wheelhouse.mkdir()
    install_root.mkdir()

    build = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            ".",
            "-w",
            str(wheelhouse),
        ],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, build.stderr
    wheels = sorted(wheelhouse.glob("codeforge-*.whl"))
    assert len(wheels) == 1

    install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--target",
            str(install_root),
            str(wheels[0]),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert install.returncode == 0, install.stderr

    console_root = tmp_path / "console-install"
    console_install = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--prefix",
            str(console_root),
            str(wheels[0]),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert console_install.returncode == 0, console_install.stderr
    console = console_root / "bin" / "codeforge-engine"
    server_console = console_root / "bin" / "codeforge-server"
    assert console.is_file()
    assert server_console.is_file()

    site_packages = console_root / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages"

    env = os.environ.copy()
    env.update(
        {
            "CODEFORGE_DB": str(tmp_path / "installed.db"),
            "CODEFORGE_SEED_REGISTRY": "file",
            "FORGE_SEED": "aethryn",
            "PYTHONPATH": str(site_packages),
            "SEEDLAB_HOME": str(tmp_path / ".seedlab"),
        }
    )

    doctor = subprocess.run(
        [str(console), "doctor", "--json"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert doctor.returncode == 0, doctor.stderr
    assert json.loads(doctor.stdout)["checks"][0]["state"] == "new"

    seeds = subprocess.run(
        [str(console), "seeds"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert seeds.returncode == 0, seeds.stderr
    assert "aethryn" in seeds.stdout

    help_result = subprocess.run(
        [str(console), "help"],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert help_result.returncode == 0, help_result.stderr
    assert "codeforge-engine doctor" in help_result.stdout

    script = """
from pathlib import Path

from alembic import command
from alembic.config import Config

import migrations
from kernel.persistence_doctor import inspect_persistence
from kernel.platform import bootstrap_platform

migration_root = Path(migrations.__file__).resolve().parent
assert (migration_root / "versions" / "d3e4f5a6b7c8_add_seedlab_persistence_tables.py").is_file()
config = Config()
config.set_main_option("script_location", str(migration_root))
command.upgrade(config, "head")

startup = bootstrap_platform(seed="aethryn", selection_source="default")
assert startup.status("engine").state == "initialized"
doctor = inspect_persistence()
assert doctor.exit_code == 0
assert {check.name: check.state for check in doctor.checks}["migrations"] == "ready"
assert {check.name: check.state for check in doctor.checks}["schema"] == "ready"
"""
    run = subprocess.run(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert run.returncode == 0, run.stderr
