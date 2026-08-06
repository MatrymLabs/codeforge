"""CARD: tool_runner -- run an ALLOWLISTED build/test command inside an approved source, under a
working-directory boundary, a timeout, an output cap, and secret redaction; record the result as
persistent evidence the Project Hub can surface.

Stage 5 of the Seed Platform directive: controlled tool execution. The Seed is a control plane, so
every run is fenced:

  * Approved command profile -- only a NAMED entry in an allowlist runs, as a fixed shell-free argv
    list (never user-interpolated). An unknown profile is refused; it never executes.
  * Working-directory boundary -- the command runs with cwd = the connected source's resolved root.
  * Timeout + output cap -- a hung or noisy command is bounded, not unbounded.
  * Secret redaction -- captured output is scrubbed of key blocks and `token=`/`password=` values.
  * Evidence -- each run is a `ToolRunResult` (profile, argv, exit, duration, when); a `RunLog`
    persists them per Seed (survives restart) and labels them for the Hub's `builds`/`tests` facets.

HONEST SCOPE / SECURITY: running a build/test executes code from the approved source (its conftest,
its build). The controls above fence it; stronger isolation (containers, namespaces) is future
hardening the directive names as "sandboxing where practical". Tests here only ever run fixed,
harmless argv (e.g. `python --version`). Reuses the FailsafeRunner pattern, binding cwd to the
source. No `kernel/world/` coupling. Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess  # nosec B404
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Thread
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session as SqlSession

from kernel.permission_policy import PermissionDenied, PermissionPolicy
from kernel.platform_db import SeedRunRow, open_archive_session
from kernel.seedlab.audit_registry import AuditStore
from kernel.seedlab.source_connector import LocalSource
from kernel.session_identity import SessionIdentity, SessionIdentityError
from kernel.session_registry import SessionRegistry

DEFAULT_TIMEOUT = 120.0
OUTPUT_CAP = 20_000


def _default_resource_limits(timeout: float, cap: int) -> dict[str, object]:
    return {
        "wall_seconds": timeout,
        "output_bytes": cap,
        "cpu_seconds": None,
        "memory_bytes": None,
        "processes": 1,
        "artifact_bytes": None,
        "filesystem": "cwd-bounded",
        "network": "policy-declared-not-enforced",
        "enforced": ["wall_seconds", "output_bytes"],
    }


def _normalize_resource_limits(
    timeout: float, cap: int, supplied: dict[str, object] | None
) -> dict[str, object]:
    limits = _default_resource_limits(timeout, cap)
    if supplied:
        limits.update(supplied)
    if float(limits["wall_seconds"]) <= 0 or int(limits["output_bytes"]) <= 0:
        raise ValueError("wall_seconds and output_bytes must be positive")
    for field_name in ("cpu_seconds", "memory_bytes", "processes", "artifact_bytes"):
        value = limits.get(field_name)
        if value is not None and float(value) <= 0:
            raise ValueError(f"{field_name} must be positive when supplied")
    enforced = ["wall_seconds", "output_bytes"]
    if limits.get("cpu_seconds") is not None and _resource_preexec(limits) is not None:
        enforced.append("cpu_seconds")
    if limits.get("memory_bytes") is not None and _resource_preexec(limits) is not None:
        enforced.append("memory_bytes")
    limits["enforced"] = enforced
    return limits


def _resource_preexec(limits: dict[str, object]) -> Callable[[], None] | None:
    """Return Unix rlimits only when an explicit resource cap was requested."""
    cpu_seconds = limits.get("cpu_seconds")
    memory_bytes = limits.get("memory_bytes")
    if cpu_seconds is None and memory_bytes is None:
        return None
    try:
        import resource
    except ImportError:
        return None

    def apply() -> None:
        if cpu_seconds is not None:
            seconds = max(1, int(float(cpu_seconds)))
            resource.setrlimit(resource.RLIMIT_CPU, (seconds, seconds))
        if memory_bytes is not None:
            bytes_limit = int(memory_bytes)
            resource.setrlimit(resource.RLIMIT_AS, (bytes_limit, bytes_limit))

    return apply

# The default approved command profile: build/test tools as fixed, shell-free argv. Only a NAMED
# entry here can run; a caller may pass its own allowlist. NEVER built from user input.
DEFAULT_PROFILE: dict[str, list[str]] = {
    "pytest": ["python", "-m", "pytest", "-q"],
    "python-build": ["python", "-m", "build"],
    "ruff": ["ruff", "check", "."],
    "python-version": ["python", "--version"],
}

# Patterns scrubbed from captured output before it is stored or shown.
_REDACTIONS = (
    re.compile(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", re.S),
    re.compile(r"(?i)\b(token|secret|password|passwd|api[_-]?key)\b\s*[=:]\s*\S+"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)


def redact(text: str) -> str:
    """Scrub key blocks and secret-shaped assignments from captured output."""
    for pattern in _REDACTIONS:
        text = pattern.sub("[REDACTED]", text)
    return text


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


class CommandRefused(ValueError):
    """The requested profile is not on the approved allowlist -- it never ran."""


def authorize_tool_run(
    identity: SessionIdentity,
    policy: PermissionPolicy,
    *,
    seed_id: str,
    kind: str,
    now: datetime | None = None,
    session_registry: SessionRegistry | None = None,
) -> None:
    """Enforce identity scope, expiry, and capability before a subprocess can start."""
    try:
        identity.require_seed(seed_id)
    except SessionIdentityError as exc:
        raise PermissionDenied(str(exc)) from exc
    if not identity.is_active(now):
        raise PermissionDenied(f"session {identity.session_id!r} is expired or not yet active")
    if session_registry is not None:
        session_registry.require_active(identity, now=now)
    policy.require(
        identity.permission_context(),
        capability=f"tool.{kind}",
        scope=seed_id,
    )


class RunLogError(Exception):
    """A persisted run record is corrupt. Fails loud."""


@dataclass(frozen=True)
class ToolRunResult:
    """The evidence of one controlled run: what ran, where, its exit, timing, and output."""

    seed_id: str
    kind: str  # "build" | "test" | "run" -- the caller's declared intent, for the Hub facet
    profile: str
    argv: list[str]
    exit_code: int
    output: str  # captured, redacted, capped
    duration: float
    timed_out: bool
    cwd: str
    when: str
    correlation_id: str = ""
    cancelled: bool = False
    revoked: bool = False
    source_id: str = ""
    connector_id: str = ""
    input_digest: str = ""
    output_digest: str = ""
    resource_limits: dict[str, object] = field(default_factory=dict)
    resource_usage: dict[str, object] = field(default_factory=dict)
    audit_id: str = ""
    principal_id: str = ""
    principal_kind: str = ""
    session_id: str = ""
    worker_id: str = ""

    @property
    def ok(self) -> bool:
        return (
            self.exit_code == 0
            and not self.timed_out
            and not self.cancelled
            and not self.revoked
        )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> ToolRunResult:
        try:
            return cls(
                seed_id=data["seed_id"],
                kind=data["kind"],
                profile=data["profile"],
                argv=list(data["argv"]),
                exit_code=int(data["exit_code"]),
                output=data.get("output", ""),
                duration=float(data.get("duration", 0.0)),
                timed_out=bool(data.get("timed_out", False)),
                cwd=data.get("cwd", ""),
                when=data.get("when", ""),
                correlation_id=data.get("correlation_id", ""),
                cancelled=bool(data.get("cancelled", False)),
                revoked=bool(data.get("revoked", False)),
                source_id=str(data.get("source_id", "")),
                connector_id=str(data.get("connector_id", "")),
                input_digest=str(data.get("input_digest", "")),
                output_digest=str(data.get("output_digest", "")),
                resource_limits=dict(data.get("resource_limits", {})),
                resource_usage=dict(data.get("resource_usage", {})),
                audit_id=str(data.get("audit_id", "")),
                principal_id=str(data.get("principal_id", "")),
                principal_kind=str(data.get("principal_kind", "")),
                session_id=str(data.get("session_id", "")),
                worker_id=str(data.get("worker_id", "")),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RunLogError(f"malformed run record: {exc}") from exc


def run_tool(
    source: LocalSource,
    profile: str,
    *,
    seed_id: str,
    kind: str = "run",
    allowlist: dict[str, list[str]] | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    cap: int = OUTPUT_CAP,
    clock: Callable[[], str] = _utcnow,
    identity: SessionIdentity | None = None,
    policy: PermissionPolicy | None = None,
    correlation_id: str = "",
    cancel_check: Callable[[], bool] | None = None,
    log_sink: Callable[[dict[str, object]], None] | None = None,
    worker_id: str = "codeforge-tool-runner",
    resource_limits: dict[str, object] | None = None,
    session_registry: SessionRegistry | None = None,
) -> ToolRunResult:
    """Run one approved command inside `source`, bounded and captured. Refuses an unlisted profile;
    returns a ToolRunResult (never raises on a failing command -- a non-zero exit IS the result)."""
    if (identity is None) != (policy is None):
        raise PermissionDenied("identity and policy must be supplied together")
    if identity is not None and policy is not None:
        auth_now = datetime.fromisoformat(clock().replace("Z", "+00:00"))
        authorize_tool_run(
            identity,
            policy,
            seed_id=seed_id,
            kind=kind,
            now=auth_now,
            session_registry=session_registry,
        )
    cancel_check = cancel_check or (lambda: False)
    table = allowlist if allowlist is not None else DEFAULT_PROFILE
    configured_argv = table.get(profile)
    if configured_argv is None:
        raise CommandRefused(f"{profile!r} is not an approved command profile")
    # The profile is portable by contract, but `python` may resolve to a system interpreter that
    # lacks CodeForge's installed test tools. Keep the allowlist fixed while binding its interpreter
    # to the current runtime environment.
    argv = list(configured_argv)
    if argv and argv[0] == "python":
        argv[0] = sys.executable
    root = Path(source.root)  # the connector already resolved + bounded this
    correlation_id = correlation_id.strip()
    limits = _normalize_resource_limits(timeout, cap, resource_limits)
    input_digest = source.digest()
    principal_id = identity.principal_id if identity is not None else ""
    principal_kind = identity.principal_kind if identity is not None else ""
    session_id = identity.session_id if identity is not None else ""

    def emit_log(event: str, **fields: object) -> None:
        if log_sink is None:
            return
        log_sink(
            {
                "event": event,
                "seed_id": seed_id,
                "correlation_id": correlation_id,
                "worker_id": worker_id,
                **fields,
            }
        )

    started = time.monotonic()
    emit_log(
        "tool.started",
        kind=kind,
        profile=profile,
        source_id=source.provenance.source_id,
        connector_id="connector.local-source",
        input_digest=input_digest,
        resource_limits=limits,
    )
    cancelled = False
    try:
        # Fixed allowlisted argv, shell=False, cwd-bounded.  Popen gives the control plane a
        # cancellation observation point while the command is running; subprocess.run cannot.
        proc = subprocess.Popen(  # nosec B603
            argv,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            preexec_fn=_resource_preexec(limits),  # nosec B603
        )
        captured: dict[str, str] = {}

        def drain() -> None:
            stdout, stderr = proc.communicate()
            captured["output"] = (stdout or "") + (stderr or "")

        # Drain continuously in a small helper so a verbose build cannot fill the OS pipe while
        # the control thread watches for cancellation and wall-time expiry.
        collector = Thread(target=drain, name="codeforge-tool-output", daemon=True)
        collector.start()
        while True:
            if cancel_check():
                cancelled = True
                proc.terminate()
                break
            if time.monotonic() - started >= timeout:
                break
            if proc.poll() is not None:
                break
            time.sleep(min(0.05, max(0.001, timeout - (time.monotonic() - started))))
        if cancelled:
            collector.join(timeout=1.0)
            if collector.is_alive():
                proc.kill()
                collector.join(timeout=1.0)
            output = captured.get("output", "")
            exit_code, timed_out = 125, False
        elif proc.poll() is None:
            timed_out = True
            proc.terminate()
            collector.join(timeout=1.0)
            if collector.is_alive():
                proc.kill()
                collector.join(timeout=1.0)
            output = captured.get("output", "")
            exit_code = 124
        else:
            collector.join(timeout=1.0)
            output = captured.get("output", "")
            exit_code, timed_out = proc.returncode, False
    except subprocess.TimeoutExpired:
        output, exit_code, timed_out = "", 124, True
    except FileNotFoundError:
        output, exit_code, timed_out = f"command not found: {argv[0]}", 127, False
    duration = time.monotonic() - started
    output = redact(output)
    if len(output) > cap:
        output = output[:cap] + f"\n... (truncated at {cap} chars)"
    revoked = False
    if identity is not None and policy is not None:
        revoked = policy.is_revoked(
            identity.permission_context(), capability=f"tool.{kind}", scope=seed_id
        )
    output_digest = "sha256:" + hashlib.sha256(output.encode("utf-8")).hexdigest()
    when = clock()
    audit_id = "audit:tool-" + hashlib.sha256(
        f"{seed_id}:{correlation_id}:{profile}:{when}:{output_digest}".encode()
    ).hexdigest()[:32]
    result = ToolRunResult(
        seed_id=seed_id,
        kind=kind,
        profile=profile,
        argv=list(argv),
        exit_code=exit_code,
        output=output.strip(),
        duration=duration,
        timed_out=timed_out,
        cwd=str(root),
        when=when,
        correlation_id=correlation_id,
        cancelled=cancelled,
        revoked=revoked,
        source_id=source.provenance.source_id,
        connector_id="connector.local-source",
        input_digest=input_digest,
        output_digest=output_digest,
        resource_limits=limits,
        resource_usage={"wall_seconds": duration},
        audit_id=audit_id,
        principal_id=principal_id,
        principal_kind=principal_kind,
        session_id=session_id,
        worker_id=worker_id,
    )
    outcome = (
        "passed"
        if result.ok
        else "cancelled"
        if cancelled
        else "revoked"
        if revoked
        else "failed"
    )
    emit_log(
        "tool.completed",
        kind=kind,
        profile=profile,
        status=outcome,
        exit_code=exit_code,
        timed_out=timed_out,
        output_digest=output_digest,
        input_digest=input_digest,
        audit_id=audit_id,
        resource_limits=limits,
    )
    return result


def render_run(result: ToolRunResult) -> str:
    """A human view of a run (the output visible in the Seed)."""
    verdict = (
        "OK"
        if result.ok
        else (
            "CANCELLED"
            if result.cancelled
            else "REVOKED"
            if result.revoked
            else (
            f"TIMED OUT ({int(result.duration)}s)"
            if result.timed_out
            else f"FAILED (exit {result.exit_code})"
            )
        )
    )
    return "\n".join(
        [
            f"== {result.kind}:{result.profile} -- {verdict} ==",
            f"argv: {' '.join(result.argv)}",
            f"cwd:  {result.cwd}",
            f"when: {result.when}  ({result.duration:.2f}s)",
            "--- output ---",
            result.output or "(no output)",
        ]
    )


@dataclass
class InMemoryRunLog:
    """A volatile run log for tests. Does not survive restart, by design."""

    _runs: list[ToolRunResult] = field(default_factory=list)

    def append(self, result: ToolRunResult) -> None:
        self._runs.append(result)

    def for_seed(self, seed_id: str) -> list[ToolRunResult]:
        return [r for r in self._runs if r.seed_id == seed_id]


@dataclass
class FileRunLog:
    """A durable, append-only run log: one JSONL file per Seed under `root`. Survives restart."""

    root: Path

    def __post_init__(self) -> None:
        self.root = Path(self.root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, seed_id: str) -> Path:
        return self.root / f"{seed_id}.jsonl"

    def append(self, result: ToolRunResult) -> None:
        with self._path(result.seed_id).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(result.to_dict()) + "\n")

    def for_seed(self, seed_id: str) -> list[ToolRunResult]:
        path = self._path(seed_id)
        if not path.is_file():
            return []
        out: list[ToolRunResult] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(ToolRunResult.from_dict(json.loads(line)))
                except json.JSONDecodeError as exc:
                    raise RunLogError(f"corrupt run log line in {path}: {exc}") from exc
        return out


@runtime_checkable
class RunLog(Protocol):
    """The append-only persistence seam for controlled run evidence."""

    def append(self, result: ToolRunResult) -> None: ...

    def for_seed(self, seed_id: str) -> list[ToolRunResult]: ...


@dataclass
class SqlRunLog:
    """Durable append-only run evidence using the platform SQL persistence boundary."""

    session_factory: Callable[[], SqlSession] = open_archive_session

    def append(self, result: ToolRunResult) -> None:
        with self.session_factory() as session, session.begin():
            session.add(
                SeedRunRow(
                    seed_id=result.seed_id,
                    kind=result.kind,
                    run_json=json.dumps(
                        result.to_dict(), sort_keys=True, separators=(",", ":")
                    ),
                )
            )

    def for_seed(self, seed_id: str) -> list[ToolRunResult]:
        with self.session_factory() as session:
            rows = (
                session.query(SeedRunRow)
                .filter(SeedRunRow.seed_id == seed_id)
                .order_by(SeedRunRow.id)
                .all()
            )
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row: SeedRunRow) -> ToolRunResult:
        try:
            return ToolRunResult.from_dict(json.loads(row.run_json))
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            raise RunLogError(f"corrupt SQL run record {row.id}: {exc}") from exc


@dataclass
class DualReadRunLog:
    """Read legacy JSONL evidence while appending new records to SQL."""

    primary: RunLog
    legacy: RunLog

    def append(self, result: ToolRunResult) -> None:
        self.primary.append(result)

    def for_seed(self, seed_id: str) -> list[ToolRunResult]:
        seen: set[str] = set()
        records: list[ToolRunResult] = []
        for result in [*self.primary.for_seed(seed_id), *self.legacy.for_seed(seed_id)]:
            key = json.dumps(result.to_dict(), sort_keys=True, separators=(",", ":"))
            if key not in seen:
                seen.add(key)
                records.append(result)
        return records


def run_log(backend: str, home: Path) -> RunLog:
    """Build the run-evidence store selected by the shared SeedLab backend setting."""
    if backend == "file":
        return FileRunLog(Path(home) / "runs")
    primary = SqlRunLog()
    if backend == "sql":
        return primary
    if backend == "sql-dual-read":
        return DualReadRunLog(primary, FileRunLog(Path(home) / "runs"))
    raise RunLogError(
        f"unknown run log backend {backend!r}; expected file, sql, or sql-dual-read"
    )


def configured_run_log(home: Path) -> RunLog:
    """Open run evidence through the shared SeedLab registry configuration."""
    import os

    backend = os.environ.get("CODEFORGE_SEED_REGISTRY", "file").strip() or "file"
    return run_log(backend, home)


def run_and_record(
    log: RunLog,
    source: LocalSource,
    profile: str,
    *,
    seed_id: str,
    kind: str = "run",
    audit_store: AuditStore | None = None,
    audit_actor: str = "",
    **kw: object,
) -> ToolRunResult:
    """Run a command and persist its evidence in one call. Returns the result."""
    result = run_tool(source, profile, seed_id=seed_id, kind=kind, **kw)  # type: ignore[arg-type]
    log.append(result)
    if audit_store is not None:
        audit_store.append(
            {
                "ts": result.when,
                "actor": audit_actor or result.session_id or "system",
                "action": "tool.completed",
                "detail": json.dumps(
                    {
                        "audit_id": result.audit_id,
                        "correlation_id": result.correlation_id,
                        "seed_id": result.seed_id,
                        "source_id": result.source_id,
                        "connector_id": result.connector_id,
                        "principal_kind": result.principal_kind,
                        "input_digest": result.input_digest,
                        "output_digest": result.output_digest,
                        "status": "passed" if result.ok else "failed",
                    },
                    sort_keys=True,
                ),
            }
        )
    return result


def run_labels(log: RunLog, seed_id: str, kind: str) -> tuple[str, ...]:
    """The `builds`/`tests` facet the Hub renders: one label per persisted run of `kind`."""
    return tuple(
        f"{r.profile} exit={r.exit_code} ({r.duration:.1f}s) @ {r.when}"
        for r in log.for_seed(seed_id)
        if r.kind == kind
    )
