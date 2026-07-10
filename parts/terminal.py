"""CARD: terminal -- the in-game computer: one console to run every diagnostic program.

The Diagnostic Console's terminal. It doesn't compute anything itself; it WIRES the read-only
diagnostic renderers the project already owns (the functions check, the frame-up, the career
board, Pioneer Mode, pm status, truth check, the QA board, the docs check) behind one
computer-terminal surface, framed like a real console. Composition, not duplication.

In the MUD: `terminal` shows the boot screen + program list; `terminal <name>` runs one.
"""

from __future__ import annotations

# (name, one-line description). The single source of truth for the menu; _run dispatches.
_PROGRAMS: list[tuple[str, str]] = [
    ("functions", "Hardware Store functions check - demo each reusable part"),
    ("inspect", "Frame-up: green/yellow/red health of every system"),
    ("career", "Career Evidence board - skills mapped to repo proof"),
    ("pioneer", "Pioneer Mode - doctrine, risk ladder, experiments"),
    ("pm", "Project status dashboard (computed live)"),
    ("truth", "VeritasGate - the project's claims vs reality"),
    ("qa", "QA board - every filed object graded"),
    ("docs", "Documentation gap check"),
]
_NAMES = {name for name, _ in _PROGRAMS}

_WIDTH = 54
_BAR = "+" + "=" * (_WIDTH - 2) + "+"


def _sticky_note() -> str:
    """A post-it stuck to the corner of the screen: the few commands to drive the terminal."""
    return "\n".join(
        [
            "        __________________________________",
            "       / STICKY NOTE  (how to drive me)   /|",
            "      /  1. get here: workshop -> north  / |",
            "     /   2. `terminal`      this menu   /  |",
            "    /    3. `terminal <name>` run one  /   |",
            "   /     4. `terminal help`   this note/    |",
            "  /______________________________ ___ /   /",
            "  |  e.g. `terminal functions`        |  /",
            "  |  read-only - nothing here bites   | /",
            "  |___________________________________|/",
        ]
    )


def _run(name: str) -> str:
    """Dispatch one program to its existing renderer (lazy imports avoid a load-time web)."""
    if name == "functions":
        from parts.functions import render_functions

        return render_functions()
    if name == "inspect":
        from parts.frameup import render_frameup

        return render_frameup()
    if name == "career":
        from parts.career import render_overview

        return render_overview()
    if name == "pioneer":
        from parts.pioneer import render_overview as pioneer_overview

        return pioneer_overview()
    if name == "pm":
        from parts.pm import pm_status

        return pm_status()
    if name == "truth":
        from parts.veritas import render_truth

        return render_truth()
    if name == "qa":
        from parts.qualitygate import render_gate_all

        return render_gate_all()
    if name == "docs":
        from parts.qualitygate import docs_check

        return docs_check()
    return f"no such program '{name}'"


def _boot_screen() -> str:
    lines = [
        _sticky_note(),
        "",
        _BAR,
        "|  F O R G E   T E R M I N A L".ljust(_WIDTH - 1) + "|",
        "|  diagnostic console  ·  read-only  ·  v1".ljust(_WIDTH - 1) + "|",
        _BAR,
        "",
        "  Programs  (run: `terminal <name>`)",
        "",
    ]
    for name, desc in _PROGRAMS:
        lines.append(f"    {name:<10} {desc}")
    lines += [
        "",
        "  Also on the workbench: `console` (run make gates), `registry`, `library`, `law`.",
        "  > _",
    ]
    return "\n".join(lines)


def terminal(arg: str = "") -> str:
    """The `terminal` command: bare -> boot screen + menu; `terminal <name>` -> run a program."""
    name = (arg or "").strip().lower()
    if name in ("", "help", "menu"):
        return _boot_screen()
    if name not in _NAMES:
        listing = ", ".join(n for n, _ in _PROGRAMS)
        return f"FORGE TERMINAL: no such program '{arg}'. Available: {listing}"
    body = _run(name)
    rule = "-" * _WIDTH
    return f"FORGE TERMINAL $ terminal {name}\n{rule}\n{body}\n{rule}\n> _"
