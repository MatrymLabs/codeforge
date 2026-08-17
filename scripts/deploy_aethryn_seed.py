"""Real deployment proof: pour the Aethryn game Seed and prove it boots + serves for real.

The recentered thesis is that CodeForge can genuinely CREATE and DEPLOY a Seed, at the scale the
game demonstrates -- not narrate a deploy, perform one. This script drives the real cast pipeline
(plan -> generate -> validate) against the flagship `kindlands_saga` template, which pours the
Aethryn world, then boots the poured cast in a fresh subprocess and runs a play corpus against it.
A pass is honest evidence the game Seed's DEPLOYMENT is real; it boots the world once more to record
its room count -- the scale the platform is proven "capable of creating."

Heavy by design (it vendors the whole engine), so it runs via `make deploy-proof`, not the unit
suite; the subprocess boots are validate_cast's real machinery, no stub. PUBLIC deployment of the
poured cast is a separate, approval-gated step -- this proves the local cradle-to-grave build-and-
boot for the game target.
"""

from __future__ import annotations

import json
import os
import subprocess  # nosec B404
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_HERE = Path(__file__).resolve()
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))

from kernel.cast import (  # noqa: E402 -- after sys.path so the script runs from any cwd
    READY,
    CastError,
    _declared_deps,
    generate_cast,
    plan_cast,
    validate_cast,
)

FLAGSHIP_TEMPLATE = "kindlands_saga"  # the flagship template; its starter seed pack is Aethryn
AETHRYN_SEED = "aethryn"

# A play corpus that exercises the tick against the REAL world. Each command must return a string or
# validate_cast's probe fails loud: `look` renders the Aethryn cradle; the rest prove the character
# and help surfaces serve over the poured world, not just that the engine imports.
AETHRYN_CORPUS = ["look", "score", "inventory", "help"]

# A tiny probe that boots the poured cast's OWN world and reports its scale (room count + spawn),
# measured from the deployed artifact rather than asserted.
_SCALE_PROBE = (
    "import json; import kernel.world.world as w; "
    "print(json.dumps({'rooms': len(w.WORLD), 'start_room': w.START_ROOM}))"
)


@dataclass(frozen=True)
class DeployProof:
    """The verdict of one real game-Seed deployment: what was poured, whether it booted + served,
    and the scale of the world it stood up. `booted` is the load-bearing claim."""

    template: str
    seed_pack: str
    engine_modules: int
    declared_deps: int
    booted: bool
    corpus: list[str]
    detail: str
    rooms: int
    start_room: str
    cast_dir: str
    when: str

    @property
    def label(self) -> str:
        # DEPLOYABLE only when the poured cast booted AND served the corpus; otherwise a loud FAIL.
        return "DEPLOYABLE" if self.booted else "FAILED"


def _count_py(parts_dir: Path) -> int:
    """Count the Python modules vendored into a poured cast (0 if the tree is absent)."""
    return sum(1 for _ in parts_dir.rglob("*.py"))


def measure_scale(cast_dir: Path, *, timeout: float = 120.0) -> tuple[int, str]:
    """Boot the poured cast's world in a subprocess and read its room count + spawn room -- the
    honest scale number, measured from the deployed artifact. Returns (0, "") if the probe fails."""
    env = dict(os.environ, FORGE_SEED=AETHRYN_SEED)
    try:
        # Fixed argv, no shell; boots the poured cast to measure its world.
        result = subprocess.run(  # nosec B603  # noqa: S603
            [sys.executable, "-c", _SCALE_PROBE],
            cwd=cast_dir,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired:
        return 0, ""
    if result.returncode != 0 or not result.stdout.strip():
        return 0, ""
    try:
        data = json.loads(result.stdout.strip().splitlines()[-1])
        return int(data["rooms"]), str(data["start_room"])
    except (ValueError, KeyError, IndexError):
        return 0, ""


def deploy_aethryn_seed(
    dest: Path,
    *,
    when: str,
    root: Path | None = None,
    corpus: list[str] | None = None,
    plan=plan_cast,
    generate=generate_cast,
    validate=validate_cast,
    scale=measure_scale,
) -> DeployProof:
    """Pour the Aethryn game Seed and prove it boots + serves. The heavy seams
    (`generate`/`validate`/`scale`) default to the real cast machinery; a test injects fakes so the
    unit suite stays fast and offline. Fails loud if the flagship template no longer pours Aethryn.
    """
    corpus = corpus if corpus is not None else list(AETHRYN_CORPUS)
    the_plan = plan(FLAGSHIP_TEMPLATE, "AethrynDeployProof", root=root)
    if the_plan.verdict != READY:
        raise CastError(  # noqa: TRY003
            f"cannot pour the Aethryn Seed: plan is {the_plan.verdict.upper()} "
            f"({'; '.join(the_plan.warnings) or 'no detail'})"
        )
    if the_plan.manifest.starter_seed_pack != AETHRYN_SEED:
        raise CastError(  # noqa: TRY003
            f"flagship template must pour '{AETHRYN_SEED}', got "
            f"{the_plan.manifest.starter_seed_pack!r}"
        )
    cast_dir = Path(generate(the_plan, dest, root=root))
    booted, detail = validate(cast_dir, commands=corpus)
    rooms, start_room = scale(cast_dir) if booted else (0, "")
    return DeployProof(
        template=FLAGSHIP_TEMPLATE,
        seed_pack=the_plan.manifest.starter_seed_pack,
        engine_modules=_count_py(cast_dir / "parts"),
        declared_deps=len(_declared_deps(cast_dir / "pyproject.toml")),
        booted=booted,
        corpus=corpus,
        detail=detail,
        rooms=rooms,
        start_room=start_room,
        cast_dir=str(cast_dir),
        when=when,
    )


def render_proof(proof: DeployProof) -> str:
    """The human-readable deployment evidence: what was poured, the boot verdict, and the scale."""
    verdict = "BOOTED + SERVED" if proof.booted else f"FAILED: {proof.detail}"
    return "\n".join(
        [
            f"REAL GAME-SEED DEPLOYMENT PROOF -- {proof.when}",
            "",
            f"  template:         {proof.template}",
            f"  world (seed):     {proof.seed_pack}",
            f"  engine modules:   {proof.engine_modules} vendored (whole engine)",
            f"  declared deps:    {proof.declared_deps}",
            f"  boot corpus:      {', '.join(proof.corpus)}",
            f"  boot verdict:     {verdict}",
            f"  world at boot:    {proof.rooms} rooms  (spawn: {proof.start_room or '-'})",
            f"  cast path:        {proof.cast_dir}",
            f"  label:            {proof.label}",
            "",
            "  What this proves: the game Seed's DEPLOYMENT is real. CodeForge poured the whole",
            "  engine plus the Aethryn world into a standalone cast and booted it in a fresh",
            "  subprocess, where it served real play commands over its own world. That world's",
            "  room count is the scale the platform is proven capable of creating. Public",
            "  deployment of the poured cast is a separate, approval-gated step.",
        ]
    )


def write_evidence(proof: DeployProof, reports_dir: Path) -> Path:
    """File dated deployment evidence (reports/ is gitignored: reproducible from commit)."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"{proof.when}-aethryn-seed-deploy.md"
    body = [
        "# Aethryn game-Seed deployment proof",
        "",
        "Generated by `make deploy-proof` (scripts/deploy_aethryn_seed.py). Reproducible from the",
        "recorded commit; not a claim, a performed deployment.",
        "",
        "```",
        render_proof(proof),
        "```",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    """Pour + boot the Aethryn game Seed, print the proof, file evidence. Exit 0 iff it booted.

    Usage: python3 scripts/deploy_aethryn_seed.py [YYYY-MM-DD] [DEST]
    """
    args = argv if argv is not None else sys.argv[1:]
    when = args[0] if args else date.today().isoformat()  # noqa: DTZ011
    dest_arg = args[1] if len(args) > 1 else None
    with tempfile.TemporaryDirectory(prefix="aethryn-cast-") as tmp:
        dest = Path(dest_arg) if dest_arg else Path(tmp) / "aethryn-cast"
        try:
            proof = deploy_aethryn_seed(dest, when=when)
        except CastError as exc:
            print(f"deploy-proof: {exc}", file=sys.stderr)
            return 2
        print(render_proof(proof))
        evidence = write_evidence(proof, _ROOT / "reports" / "deploy")
        print(f"\nevidence: {evidence}")
        return 0 if proof.booted else 1


if __name__ == "__main__":
    raise SystemExit(main())
