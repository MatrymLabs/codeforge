"""Test twin for scripts/deploy_aethryn_seed.py -- the real game-Seed deployment proof.

Acceptance: a booting cast yields a DEPLOYABLE proof carrying the world's scale, renders it, and
files dated evidence. Refusal (fail loud, never fake a deploy): a cast that will not boot yields a
FAILED proof with zero scale and a non-zero exit; a flagship template that no longer pours Aethryn
is refused before anything is poured.

The heavy seams (`generate`/`validate`/`scale`) are faked so the suite stays fast and offline; the
REAL machinery is exercised by `make deploy-proof`. `plan_cast` itself is cheap (reads a template,
checks a seed dir) so the real guard logic runs unfaked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from parts.cast import CastError, plan_cast
from scripts.deploy_aethryn_seed import (
    AETHRYN_SEED,
    FLAGSHIP_TEMPLATE,
    DeployProof,
    deploy_aethryn_seed,
    render_proof,
    write_evidence,
)


def _fake_generate(booted_parts: int = 3):
    """A generate seam that makes the dest dir (and a few module files for the counter)."""

    def _gen(plan, dest, root=None):
        dest = Path(dest)
        parts = dest / "parts"
        parts.mkdir(parents=True, exist_ok=True)
        for i in range(booted_parts):
            (parts / f"mod_{i}.py").write_text("x = 1\n", encoding="utf-8")
        return dest

    return _gen


def _deploy(tmp_path: Path, *, booted: bool, rooms: int = 0) -> DeployProof:
    return deploy_aethryn_seed(
        tmp_path / "cast",
        when="2026-08-01",
        generate=_fake_generate(),
        validate=lambda cast, commands=None: (booted, "ran clean" if booted else "boot blew up"),
        scale=lambda cast: (rooms, "aethryn_cradle") if booted else (0, ""),
    )


# --- acceptance --------------------------------------------------------------------------------
def test_a_booting_cast_is_deployable_with_scale(tmp_path: Path) -> None:
    proof = _deploy(tmp_path, booted=True, rooms=1200)
    assert proof.booted is True and proof.label == "DEPLOYABLE"
    assert proof.seed_pack == AETHRYN_SEED and proof.template == FLAGSHIP_TEMPLATE
    assert proof.rooms == 1200 and proof.start_room == "aethryn_cradle"
    assert proof.engine_modules == 3  # counted from the poured tree


def test_render_shows_verdict_and_scale(tmp_path: Path) -> None:
    out = render_proof(_deploy(tmp_path, booted=True, rooms=999))
    assert "BOOTED + SERVED" in out and "999 rooms" in out
    assert "aethryn" in out and "DEPLOYABLE" in out


def test_evidence_is_filed_dated(tmp_path: Path) -> None:
    proof = _deploy(tmp_path, booted=True, rooms=10)
    path = write_evidence(proof, tmp_path / "reports" / "deploy")
    assert path.name == "2026-08-01-aethryn-seed-deploy.md"
    assert "deployment proof" in path.read_text(encoding="utf-8").lower()


# --- refusal: a deploy that does not boot must fail loud, never fake success --------------------
def test_a_cast_that_will_not_boot_is_failed_with_zero_scale(tmp_path: Path) -> None:
    proof = _deploy(tmp_path, booted=False, rooms=1200)
    assert proof.booted is False and proof.label == "FAILED"
    assert proof.rooms == 0 and proof.start_room == ""  # scale is not measured on a dead cast
    assert "boot blew up" in proof.detail


def test_render_marks_a_failed_deploy(tmp_path: Path) -> None:
    assert "FAILED: boot blew up" in render_proof(_deploy(tmp_path, booted=False))


def test_flagship_template_that_stops_pouring_aethryn_is_refused(tmp_path: Path) -> None:
    class _Manifest:
        starter_seed_pack = "some-other-world"

    class _Plan:
        verdict = "ready"
        warnings: list[str] = []
        manifest = _Manifest()

    with pytest.raises(CastError, match="must pour 'aethryn'"):
        deploy_aethryn_seed(
            tmp_path / "cast",
            when="2026-08-01",
            plan=lambda *a, **k: _Plan(),
            generate=_fake_generate(),
            validate=lambda cast, commands=None: (True, "ok"),
        )


def test_a_blocked_plan_is_refused_before_pouring(tmp_path: Path) -> None:
    class _Plan:
        verdict = "blocked"
        warnings = ["seed pack not installed"]
        manifest = type("M", (), {"starter_seed_pack": AETHRYN_SEED})()

    with pytest.raises(CastError, match="BLOCKED"):
        deploy_aethryn_seed(tmp_path / "cast", when="2026-08-01", plan=lambda *a, **k: _Plan())


def test_the_real_flagship_plan_still_points_at_aethryn() -> None:
    # The one unfaked real call: the flagship template must still pour the Aethryn world, or the
    # whole deploy proof is aimed at the wrong seed. Cheap (reads a template + checks a dir).
    plan = plan_cast(FLAGSHIP_TEMPLATE, "AethrynDeployProof")
    assert plan.manifest.starter_seed_pack == AETHRYN_SEED
