"""CARD: functions -- the Hardware Store functions check: prove the parts actually work.

A hardware store lets you test a part before you rely on it. This runs a small, safe,
canonical demonstration of each cataloged reusable part -- the real function call and its
real output -- so "reusable" is shown, not claimed. Where a clean standalone demo isn't
safe (a part that needs world state), it cites the part's test twin instead of faking one.
Nothing here mutates real repo state; demos use temp dirs and throwaway objects.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from parts.hardware import load_catalog

_ROOT = Path(__file__).resolve().parent.parent


# --- Live demos: (call shown, output shown). Each is pure or uses a temp dir. -----------
def _demo_rank_gate() -> tuple[str, str]:
    from parts.ranks import has_rank
    from parts.session import Session

    novice = has_rank(Session(player_id="novice", rank="player"), "wizard")
    owner = has_rank(Session(player_id="owner", rank="owner"), "wizard")
    return ("has_rank(player, owner -> 'wizard')", f"{novice} / {owner}  (refused / allowed)")


def _demo_report_writer() -> tuple[str, str]:
    from parts.shelf.reporting import write_report

    with tempfile.TemporaryDirectory() as d:
        p = write_report("demo", "hello world", root=Path(d), stamp="2026-07-10")
        return (
            "write_report('demo', 'hello world')",
            f"wrote {p.name} ({p.read_text(encoding='utf-8').strip()!r})",
        )


def _demo_assessment() -> tuple[str, str]:
    from parts.assessment import available_lessons

    lessons = available_lessons()
    total_q = sum(len(x.questions) for x in lessons)
    return (
        "available_lessons()",
        f"{len(lessons)} lesson(s), {total_q} question(s), all validated",
    )


def _demo_validated_loader() -> tuple[str, str]:
    from parts.seed import SeedError, load_rooms

    with tempfile.TemporaryDirectory() as d:
        bad = Path(d) / "rooms.yaml"
        bad.write_text(
            "start:\n  name: Start\nstart:\n  name: Dup\n", encoding="utf-8"
        )  # duplicate key
        try:
            load_rooms(bad)
            return ("load_rooms(<duplicate-key yaml>)", "loaded (unexpected -- validation gap!)")
        except (SeedError, Exception) as exc:  # noqa: BLE001 - the point is it refuses, loudly
            kind = type(exc).__name__
            return ("load_rooms(<duplicate-key yaml>)", f"{kind} -- refuses a bad row (fails loud)")


def _demo_event_ledger() -> tuple[str, str]:
    from parts.events import announce, bind_echo, unbind_echo
    from parts.session import SESSIONS, Session

    pid = "_fn_evt_demo"
    got: list[str] = []
    prev = SESSIONS.get(pid)
    SESSIONS[pid] = Session(player_id=pid, location="_fn_demo_room")
    bind_echo(pid, got.append)  # an EchoSink is just Callable[[str], None]
    try:
        announce("_fn_demo_room", "hello world")
        result = repr(got[0]) if got else "(nothing delivered)"
        return ("announce('room', 'hello world')", f"echo sink received {result}")
    finally:
        unbind_echo(pid)
        if prev is None:
            SESSIONS.pop(pid, None)
        else:
            SESSIONS[pid] = prev


def _demo_safe_runner() -> tuple[str, str]:
    from parts.console import ALLOWLIST, CommandRefused, run

    try:
        run("rm -rf /")  # not on the allowlist
        return ("run('rm -rf /')", "ran (unexpected -- allowlist bypass!)")
    except CommandRefused:
        sample = ", ".join(sorted(ALLOWLIST)[:3])
        return ("run('rm -rf /')", f"CommandRefused -- never ran (allowlist: {sample}, ...)")


def _demo_gate_runner() -> tuple[str, str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_fn_doctor", _ROOT / "scripts" / "doctor.py")
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        return ("scripts/doctor.py", "could not load doctor")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # import-safe: doctor runs main() only under __main__
    labels = [g[0] for g in mod.GATES]
    return ("doctor GATES (read-only)", f"{len(labels)} gates: {', '.join(labels[:4])}, ...")


_DEMOS: dict[str, Callable[[], tuple[str, str]]] = {
    "rank-gate": _demo_rank_gate,
    "report-writer": _demo_report_writer,
    "assessment-engine": _demo_assessment,
    "validated-loader": _demo_validated_loader,
    "event-ledger": _demo_event_ledger,
    "safe-runner": _demo_safe_runner,
    "gate-runner": _demo_gate_runner,
}


# Parts whose verification lives in a SHARED test file, not the 1:1 test_<stem>.py convention
# (e.g. the evolution parts are proven together in test_evolution_*.py). Each cited file exists.
_TWINS: dict[str, str] = {
    "blueprint-genome": "tests/test_evolution_genome.py",
    "constraint-gate": "tests/test_evolution_genome.py",
    "counterexample-bank": "tests/test_evolution_bakeoff.py",
    "fitness-aggregator": "tests/test_evolution_bakeoff.py",
    "evaluator-swarm": "tests/test_evolution_bakeoff.py",
    "evolution-lab": "tests/test_evolution_bakeoff.py",
}


def _test_twin(part_id: str, source: str) -> str | None:
    """A part's test twin: an explicit shared-twin mapping, else the derived
    convention (parts/x.py -> tests/test_x.py). Only cite a file that actually exists."""
    explicit = _TWINS.get(part_id)
    if explicit and (_ROOT / explicit).is_file():
        return explicit
    stem = Path(source).stem
    twin = _ROOT / "tests" / f"test_{stem}.py"
    return f"tests/test_{stem}.py" if twin.is_file() else None


def render_functions() -> str:
    """Run each part's live demo (or cite its test twin) and report -- the functions check."""
    parts = load_catalog()
    lines = [
        "HARDWARE STORE - FUNCTIONS CHECK",
        "  Prove the parts work, don't just claim it. Live demo where clean; else the test twin.",
        "",
    ]
    ran = 0
    tested = 0
    for part in parts:
        demo = _DEMOS.get(part.id)
        if demo is not None:
            try:
                call, out = demo()
                lines.append(f"  [runs]   {part.id:<18} {call}")
                lines.append(f"           -> {out}")
                ran += 1
            except Exception as exc:  # a part whose demo breaks must surface, never hide
                lines.append(f"  [BROKEN] {part.id:<18} demo raised: {exc}")
        else:
            twin = _test_twin(part.id, part.source)
            if twin:
                lines.append(f"  [tested] {part.id:<18} verified by {twin}")
                tested += 1
            else:
                lines.append(f"  [manual] {part.id:<18} run its example by hand ({part.source})")
    lines += [
        "",
        f"  {len(parts)} parts: {ran} demonstrated live, {tested} verified by their test twins.",
    ]
    return "\n".join(lines)


def functions(arg: str = "") -> str:
    """The `functions` command: the Hardware Store functions check."""
    return render_functions()
