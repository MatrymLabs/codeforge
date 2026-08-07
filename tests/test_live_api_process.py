"""A real loopback Forge API process serves the same Seed contract as in-process tests."""

from __future__ import annotations

import base64
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from kernel.seedlab.kernel import FileSeedStore, SeedKernel
from kernel.seedlab.platform_proof import run_first_platform_proof


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _get(url: str) -> dict[str, object]:
    with urllib.request.urlopen(url, timeout=3) as response:  # nosec B310 - fixed loopback URL
        payload = json.loads(response.read().decode("utf-8"))
    assert isinstance(payload, dict)
    return payload


def _get_authenticated(url: str, account: str, password: str) -> dict[str, object]:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": "Basic " + base64.b64encode(f"{account}:{password}".encode()).decode()
        },
    )
    with urllib.request.urlopen(request, timeout=3) as response:  # nosec B310 - fixed loopback URL
        payload = json.loads(response.read().decode("utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_live_uvicorn_process_serves_authoritative_workspace_contract(tmp_path: Path) -> None:
    home = tmp_path / ".seedlab"
    SeedKernel(FileSeedStore(home / "seeds")).create_seed(
        "Live API Seed", "owner", "loopback process proof", seed_id="seed-live-process"
    )
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "SEEDLAB_HOME": str(home),
            "CODEFORGE_DB": str(tmp_path / "codeforge.db"),
            "CODEFORGE_SEED_REGISTRY": "file",
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "adapters.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        health: dict[str, object] | None = None
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise AssertionError(f"live Forge API exited early: {stderr}")
            try:
                health = _get(f"http://127.0.0.1:{port}/health")
                break
            except (OSError, TimeoutError):
                time.sleep(0.1)
        assert health == {"status": "alive", "engine": "codeforge"}

        contract = _get(f"http://127.0.0.1:{port}/api/seedlab/workspaces/seed-live-process")
        assert contract["contract_version"] == "seedlab.workspace/1"
        seed = contract["seed"]
        assert isinstance(seed, dict) and seed["name"] == "Live API Seed"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_live_uvicorn_process_replays_authenticated_platform_proof_and_recovery(
    tmp_path: Path, monkeypatch
) -> None:
    """CF-110: a real API process serves the exact recovered proof to an owner."""
    home = tmp_path / ".seedlab"
    from kernel.world import accounts
    from kernel.world import db as world_db

    db = Path(world_db.DB_PATH)
    from kernel.world.accounts import account_has_owner, account_password_ok, adopt, register
    from kernel.world.characters import save_character, set_rank
    from kernel.world.session import Session

    monkeypatch.setattr(accounts, "_ITERATIONS", 600_000)
    register("live-proof-seed", "live-proof-account", "proof-password")
    owner = Session(
        player_id="live-proof-owner",
        location="courtyard",
        named=True,
        account="live-proof-account",
    )
    save_character(owner)
    adopt("live-proof-owner", "live-proof-account")
    set_rank("live-proof-owner", "owner")
    assert account_password_ok("live-proof-account", "proof-password")
    assert account_has_owner("live-proof-account")
    proof = run_first_platform_proof(
        home / "proof",
        owner="live-proof-account",
        id_minter=lambda _name: "seed-live-proof",
    )
    port = _free_port()
    env = os.environ.copy()
    env.update(
        {
            "SEEDLAB_HOME": str(home),
            "CODEFORGE_DB": str(db),
            "CODEFORGE_SEED_REGISTRY": "file",
            "PYTHONUNBUFFERED": "1",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "adapters.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if process.poll() is not None:
                stderr = process.stderr.read() if process.stderr else ""
                raise AssertionError(f"live Forge API exited early: {stderr}")
            try:
                if _get(f"http://127.0.0.1:{port}/health")["status"] == "alive":
                    break
            except (OSError, TimeoutError):
                time.sleep(0.1)
        payload = _get_authenticated(
            f"http://127.0.0.1:{port}/api/seedlab/proofs/{proof.seed_id}",
            "live-proof-account",
            "proof-password",
        )
        assert payload["seed_id"] == "seed-live-proof"
        assert payload["deployment"]["status"] == "deployed"
        assert payload["failed_deployment"]["status"] == "failed"
        assert payload["recovered_deployment"]["status"] == "deployed"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
