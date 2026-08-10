"""CARD: workspace_verb -- the in-MUD `workspace` verb: an owner lists, creates, and inspects
engineering Seeds (workspaces) from inside the running MUD.

This is the TEXT half of the workspace surface -- the same engineering Seeds the Master Client
renders over GMCP (kernel/seedlab/workspace_gmcp.py), reachable as a plain owner command in the
running world. "THE SEED IS THE MUD" made walkable: `workspace list`, `workspace create <name>
[purpose]`, `workspace status <id>`, `workspace start|stop <id>`, `workspace model <id>`,
`workspace run <id> <path> <profile>` (an allowlisted, bounded tool run whose evidence feeds the
Build Report), and `workspace report <id>`.

Owner-gated at the command spine; the Kernel re-checks ownership on every mutation, so an owner can
only start/stop a workspace they own. Persistence is file-backed under $SEEDLAB_HOME. The Kernel and
model store are injectable, so the dispatch tests without touching disk. Grammar before worlds: this
platform verb imports NO game module. Live workspace GMCP frames ride an INJECTED transport
(`gmcp_push`); the game tick wires the real `kernel.world.events.push_gmcp` when it dispatches this
verb, and with no transport injected (plain text, tests) a frame is simply dropped. Frames fire
whenever a subcommand resolves that state: `Project.Status` when a workspace is inspected or its
lifecycle changes,
`Source.Tree` + `Source.Connection` + `Model.Schema` when a source is connected and modeled, and
`Model.Schema` when models are inspected, and `Build.Report` when `run` records an allowlisted
tool run (or `report` replays the recorded runs). So a Native-Seed client's WHOLE Engineering
Workspace - Project Hub,
Source Explorer, Model view, Build Report - updates the instant an owner acts; the last dark panel
lit when the run verb landed. Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from kernel.seedlab.kernel import (
    FileSeedStore,
    SeedKernel,
    SeedKernelError,
    SeedRecord,
    render_status,
)
from kernel.seedlab.model_store import FileModelStore, ModelStore, model_label
from kernel.seedlab.workspace_gmcp import (
    BUILD_REPORT_PACKAGE,
    MODEL_SCHEMA_PACKAGE,
    PROJECT_STATUS_PACKAGE,
    SOURCE_CONNECTION_PACKAGE,
    SOURCE_TREE_PACKAGE,
    build_report,
    model_schema,
    project_status,
    source_connection_package,
    source_tree,
)

_USAGE = (
    "workspace commands: list | create <name> [purpose] | status <id> | "
    "start <id> | stop <id> | connect <id> <path> | model <id> | "
    "run <id> <path> <profile> | report <id> | "
    "backup <id> | backups <id> | restore <id> <backup_id>"
)

#: How the verb pushes a live GMCP frame to the acting owner: (player_id, package, data). The Seed
#: Kernel is domain-neutral (grammar before worlds), so it owns no game bus and imports no game
#: module: the game tick injects the real transport (kernel.world.events.push_gmcp) when it wires
#: this verb. Tests inject a fake to capture the pushes; a caller with no transport drops the frame.
GmcpPush = Callable[[str, str, object], None]


def _drop_frame(player_id: str, package: str, data: object) -> None:
    """Default transport: drop the frame. A domain-neutral platform verb cannot reach into the game
    world for a bus, so with no transport injected (plain-text caller, tests) the frame is a no-op;
    a text client has no GMCP sink anyway. The game tick supplies the real push at dispatch."""
    return None


def _push_frame(session: Any, push: GmcpPush, package: str, payload: dict[str, object]) -> None:
    """Push one workspace GMCP frame to the acting owner, if they have a player id. A session with
    no player id (a bare test session, a plain-text caller) is a no-op; `push_gmcp` itself already
    skips a player with no GMCP sink, so a text client never sees one."""
    player_id = getattr(session, "player_id", "")
    if not player_id:
        return
    push(player_id, package, payload)


def _emit_project_status(session: Any, record: SeedRecord, push: GmcpPush) -> None:
    """Project one workspace's status into a live `Project.Status` frame for the acting owner, so
    the client's Project Hub reflects a workspace the instant it is inspected or its lifecycle
    changes."""
    _push_frame(session, push, PROJECT_STATUS_PACKAGE, project_status(record))


def _home() -> Path:
    return Path(os.environ.get("SEEDLAB_HOME", ".seedlab"))


def _allowed_root() -> Path | None:
    """The base dir `workspace connect` is confined to, if $SEEDLAB_SOURCES is set. When unset,
    connect is owner-trusted (any path); when set, a path outside the base is refused."""
    base = os.environ.get("SEEDLAB_SOURCES")
    return Path(base).resolve() if base else None


def _default_kernel() -> SeedKernel:
    return SeedKernel(FileSeedStore(_home() / "seeds"))


def _default_backups() -> Any:
    """The Seed backup store under $SEEDLAB_HOME/backups (lazy import keeps backup off the load
    path until a caller actually snapshots or restores)."""
    from kernel.seedlab.backup import SeedBackups

    return SeedBackups(_home() / "backups")


def _actor(session: Any) -> str:
    """The owner identity for a workspace: the caller's account, else their player id."""
    return getattr(session, "account", "") or getattr(session, "player_id", "owner")


def workspace_command(
    session: Any,
    arg: str,
    *,
    kernel: SeedKernel | None = None,
    model_store: ModelStore | None = None,
    gmcp_push: GmcpPush | None = None,
    run_log: Any | None = None,
    allowlist: dict[str, list[str]] | None = None,
    backups: Any | None = None,
) -> str:
    """Dispatch a `workspace` subcommand over the Seed Kernel; returns a text projection for the
    tick. Owner-gated at the spine; the Kernel authorizes each mutation by the acting owner. When a
    subcommand resolves workspace state, it also pushes the matching live GMCP frame(s) to the
    caller so a Native-Seed client's Engineering Workspace stays fresh: `Project.Status` on
    inspect/lifecycle, `Source.Tree` + `Model.Schema` on connect, `Model.Schema` on model, and
    `Build.Report` on run/report (the tool-run state the 4th client panel renders). `run_log` and
    `allowlist` are injectable seams (tests never shell a real tool or touch the real log)."""
    kernel = kernel or _default_kernel()
    push = gmcp_push or _drop_frame
    actor = _actor(session)
    parts = (arg or "").split()
    sub = parts[0].lower() if parts else "list"
    rest = parts[1:]

    if sub in ("list", "ls"):
        from kernel.seedlab.reference_seed import ensure_reference_seed, is_reference_seed

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
        _emit_project_status(session, record, push)
        return f"Created workspace {record.identity.seed_id} (owner: {actor}, status: CREATED)."

    if sub in ("status", "show", "enter"):
        if not rest:
            return f"usage: workspace {sub} <seed_id>"
        try:
            record = kernel.get(rest[0])
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        _emit_project_status(session, record, push)
        return render_status(record)

    if sub in ("start", "stop", "archive"):
        if not rest:
            return f"usage: workspace {sub} <seed_id>"
        try:
            record = getattr(kernel, sub)(rest[0], actor)
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        _emit_project_status(session, record, push)
        return f"{rest[0]} -> {record.status.upper()}"

    if sub == "model":
        if not rest:
            return "usage: workspace model <seed_id>"
        try:
            record = kernel.get(rest[0])  # confirm the workspace exists first
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        store = model_store or FileModelStore(_home() / "models")
        models = store.all_for_seed(rest[0])
        if not models:
            return f"No models for {rest[0]} yet (connect a source and model it)."
        # Inspecting the model resolves real extracted state, so push a live `Model.Schema` frame
        # (the latest model) to refresh the client's Model view, mirroring how `status` refreshes
        # the Project Hub.
        _push_frame(
            session, push, MODEL_SCHEMA_PACKAGE, model_schema(models[-1], seed=record.identity.name)
        )
        return "Models:\n" + "\n".join(f"  - {model_label(m)}" for m in models)

    if sub == "connect":
        if len(rest) < 2:
            return "usage: workspace connect <seed_id> <path>"
        seed_id, path = rest[0], " ".join(rest[1:])
        try:
            record = kernel.get(seed_id)  # the workspace must exist
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        # If an operator set an allowed-sources base, refuse a path outside it (defence in depth on
        # top of owner-gating; the connector still bounds reads WITHIN the chosen root).
        allowed = _allowed_root()
        resolved = Path(path).resolve()
        if allowed is not None:
            try:
                resolved.relative_to(allowed)
            except ValueError:
                return f"workspace: {path!r} is outside the allowed sources root ({allowed})"
        # Lazy imports: the connect flow pulls in the connector + modeler only when used.
        from kernel.seedlab.project_model import Provenance, SeedLabError
        from kernel.seedlab.source_connector import LocalSource, SourceConnectorError
        from kernel.seedlab.source_modeler import model_and_store

        store = model_store or FileModelStore(_home() / "models")
        source_id = resolved.name or "source"
        try:
            source = LocalSource(resolved, Provenance(source_id, owner=actor))
            model = model_and_store(store, seed_id, source)
        except (SourceConnectorError, SeedLabError) as exc:
            return f"workspace: {exc}"
        # Connecting resolves a real source AND a fresh model, so push both live frames: the
        # client's Source Explorer and Model view light up the instant an owner connects a
        # project. `register` snapshots the source's git head + approved-file count; the file
        # list is the connector's already-approved relpaths.
        seed_name = record.identity.name
        _push_frame(
            session,
            push,
            SOURCE_TREE_PACKAGE,
            source_tree(source.register(), source.list_files(), seed=seed_name),
        )
        _push_frame(
            session,
            push,
            SOURCE_CONNECTION_PACKAGE,
            source_connection_package(source.register(), seed=seed_name),
        )
        _push_frame(session, push, MODEL_SCHEMA_PACKAGE, model_schema(model, seed=seed_name))
        return (
            f"Connected {path} to {seed_id} and modeled it: {model.identity} "
            f"({len(model.entities)} entities, {len(model.unknowns)} unknowns). "
            f"See: workspace model {seed_id}"
        )

    if sub == "run":
        if len(rest) < 3:
            return "usage: workspace run <seed_id> <path> <profile>"
        seed_id, path, profile = rest[0], rest[1], rest[2]
        try:
            record = kernel.get(seed_id)  # the workspace must exist
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        allowed = _allowed_root()  # same defence-in-depth as connect
        resolved = Path(path).resolve()
        if allowed is not None:
            try:
                resolved.relative_to(allowed)
            except ValueError:
                return f"workspace: {path!r} is outside the allowed sources root ({allowed})"
        from kernel.seedlab.project_model import Provenance
        from kernel.seedlab.source_connector import LocalSource, SourceConnectorError
        from kernel.seedlab.tool_runner import (
            CommandRefused,
            FileRunLog,
            render_run,
            run_and_record,
        )

        log = run_log if run_log is not None else FileRunLog(_home() / "runs")
        try:
            source = LocalSource(resolved, Provenance(resolved.name or "source", owner=actor))
            result = run_and_record(log, source, profile, seed_id=seed_id, allowlist=allowlist)
        except (SourceConnectorError, CommandRefused) as exc:
            return f"workspace: {exc}"
        # A run resolves real tool-run state, so the 4th panel lights up: push the full
        # Build.Report (every recorded run for this Seed, not just the newest).
        _push_frame(
            session,
            push,
            BUILD_REPORT_PACKAGE,
            build_report(
                log.for_seed(seed_id),
                seed=record.identity.name,
                tests={
                    "passed": sum(1 for r in log.for_seed(seed_id) if r.kind == "test" and r.ok),
                    "failed": sum(
                        1 for r in log.for_seed(seed_id) if r.kind == "test" and not r.ok
                    ),
                    "skipped": 0,
                },
            ),
        )
        return render_run(result)

    if sub == "report":
        if not rest:
            return "usage: workspace report <seed_id>"
        try:
            record = kernel.get(rest[0])
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        from kernel.seedlab.tool_runner import FileRunLog, render_run

        log = run_log if run_log is not None else FileRunLog(_home() / "runs")
        runs = log.for_seed(rest[0])
        if not runs:
            return f"No tool runs for {rest[0]} yet (workspace run <id> <path> <profile>)."
        # Inspecting the report resolves recorded run state: re-push it so the client's Build
        # Report panel refreshes, mirroring how `model` refreshes the Model view.
        _push_frame(
            session,
            push,
            BUILD_REPORT_PACKAGE,
            build_report(
                runs,
                seed=record.identity.name,
                tests={
                    "passed": sum(1 for r in runs if r.kind == "test" and r.ok),
                    "failed": sum(1 for r in runs if r.kind == "test" and not r.ok),
                    "skipped": 0,
                },
            ),
        )
        ok = sum(1 for r in runs if r.ok)
        return f"{len(runs)} run(s), {ok} ok. Latest:\n" + render_run(runs[-1])

    if sub == "backup":
        if not rest:
            return "usage: workspace backup <seed_id>"
        try:
            record = kernel.get(rest[0])  # the workspace must exist to snapshot it
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        store = backups if backups is not None else _default_backups()
        ref = store.backup(record)
        return (
            f"Backed up {rest[0]} -> {ref.backup_id} (sha256 {ref.sha256[:8]}). "
            f"Restore with: workspace restore {rest[0]} {ref.backup_id}"
        )

    if sub in ("backups", "snapshots"):
        if not rest:
            return f"usage: workspace {sub} <seed_id>"
        try:
            kernel.get(rest[0])  # confirm the workspace exists before listing its snapshots
        except SeedKernelError as exc:
            return f"workspace: {exc}"
        store = backups if backups is not None else _default_backups()
        refs = store.list_backups(rest[0])
        if not refs:
            return f"No backups for {rest[0]} yet (workspace backup {rest[0]})."
        lines = [f"== Backups for {rest[0]} (oldest first) =="]
        lines += [
            f"  {r.backup_id}  {store.verify(rest[0], r.backup_id).upper():7}  {r.when}"
            for r in refs
        ]
        return "\n".join(lines)

    if sub == "restore":
        if len(rest) < 2:
            return "usage: workspace restore <seed_id> <backup_id>"
        from kernel.seedlab.backup import BackupError, restore

        store = backups if backups is not None else _default_backups()
        try:
            record = restore(kernel, store, rest[0], rest[1], actor)
        except (SeedKernelError, BackupError) as exc:
            return f"workspace: {exc}"
        # A restore rewrites live state (it is rollback), so refresh the client's Project Hub.
        _emit_project_status(session, record, push)
        return f"Restored {rest[0]} from {rest[1]} -> {record.status.upper()}."

    return _USAGE
