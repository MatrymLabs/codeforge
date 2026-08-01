"""CARD: workspace_verb -- the in-MUD `workspace` verb: an owner lists, creates, and inspects
engineering Seeds (workspaces) from inside the running MUD.

This is the TEXT half of the workspace surface -- the same engineering Seeds the Master Client
renders over GMCP (parts/seedlab/workspace_gmcp.py), reachable as a plain owner command in the
running world. "THE SEED IS THE MUD" made walkable: `workspace list`, `workspace create <name>
[purpose]`, `workspace status <id>`, `workspace start|stop <id>`, `workspace model <id>`.

Owner-gated at the command spine; the Kernel re-checks ownership on every mutation, so an owner can
only start/stop a workspace they own. Persistence is file-backed under $SEEDLAB_HOME. The Kernel and
model store are injectable, so the dispatch tests without touching disk. No game-world coupling
beyond reading the caller's identity. Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from parts.seedlab.kernel import FileSeedStore, SeedKernel, SeedKernelError, render_status
from parts.seedlab.model_store import FileModelStore, ModelStore, model_labels

_USAGE = (
    "workspace commands: list | create <name> [purpose] | status <id> | "
    "start <id> | stop <id> | model <id>"
)


def _home() -> Path:
    return Path(os.environ.get("SEEDLAB_HOME", ".seedlab"))


def _default_kernel() -> SeedKernel:
    return SeedKernel(FileSeedStore(_home() / "seeds"))


def _actor(session: Any) -> str:
    """The owner identity for a workspace: the caller's account, else their player id."""
    return getattr(session, "account", "") or getattr(session, "player_id", "owner")


def workspace_command(
    session: Any,
    arg: str,
    *,
    kernel: SeedKernel | None = None,
    model_store: ModelStore | None = None,
) -> str:
    """Dispatch a `workspace` subcommand over the Seed Kernel; returns a text projection for the
    tick. Owner-gated at the spine; the Kernel authorizes each mutation by the acting owner."""
    kernel = kernel or _default_kernel()
    actor = _actor(session)
    parts = (arg or "").split()
    sub = parts[0].lower() if parts else "list"
    rest = parts[1:]

    if sub in ("list", "ls"):
        from parts.seedlab.reference_seed import ensure_reference_seed, is_reference_seed

        ensure_reference_seed(kernel)  # the flagship game is one kind of Seed; it always appears
        lines = ["== Workspaces (engineering Seeds; the game is the reference Seed) =="]
        lines += [
            f"  {r.identity.seed_id}  {r.status.upper():8}  {r.identity.name}"
            f"{'  [reference game]' if is_reference_seed(r) else ''}  (owner: {r.identity.owner})"
            for r in kernel.list_seeds()
        ]
        return "\n".join(lines)

    if sub == "create":
        if not rest:
            return "usage: workspace create <name> [purpose]"
        name, purpose = rest[0], " ".join(rest[1:])
        try:
            record = kernel.create_seed(name, actor, purpose)
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        return f"Created workspace {record.identity.seed_id} (owner: {actor}, status: CREATED)."

    if sub in ("status", "show", "enter"):
        if not rest:
            return f"usage: workspace {sub} <seed_id>"
        try:
            return render_status(kernel.get(rest[0]))
        except SeedKernelError as exc:
            return f"workspace: {exc}"

    if sub in ("start", "stop", "archive"):
        if not rest:
            return f"usage: workspace {sub} <seed_id>"
        try:
            record = getattr(kernel, sub)(rest[0], actor)
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        return f"{rest[0]} -> {record.status.upper()}"

    if sub == "model":
        if not rest:
            return "usage: workspace model <seed_id>"
        try:
            kernel.get(rest[0])  # confirm the workspace exists first
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        store = model_store or FileModelStore(_home() / "models")
        labels = model_labels(store, rest[0])
        if not labels:
            return f"No models for {rest[0]} yet (connect a source and model it)."
        return "Models:\n" + "\n".join(f"  - {label}" for label in labels)

    return _USAGE
