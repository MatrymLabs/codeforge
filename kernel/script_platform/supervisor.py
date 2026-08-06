"""External worker supervisor for untrusted or semi-trusted script runners."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import ScriptManifest


class WorkerError(RuntimeError):
    """A worker failed, timed out, or returned an invalid bounded response."""


@dataclass(frozen=True)
class WorkerPolicy:
    wall_ms: int = 100
    output_bytes: int = 8192
    error_bytes: int = 8192

    def __post_init__(self) -> None:
        if self.wall_ms < 1 or self.output_bytes < 1 or self.error_bytes < 1:
            raise ValueError("worker limits must be positive")


@dataclass(frozen=True)
class WorkerResult:
    payload: dict[str, Any]
    returncode: int
    stdout_bytes: int
    stderr: str


class ScriptRunnerSupervisor:
    """Run a runner executable with no shell, no ambient environment, and kill-on-timeout.

    The executable is intentionally supplied by deployment configuration.  This class provides
    process/protocol containment; container, UID, seccomp, cgroup, and LSM policy belong to the
    deployment profile and must not be inferred from this Python helper.
    """

    def run(
        self,
        manifest: ScriptManifest,
        request: dict[str, Any],
        *,
        executable: Path,
        arguments: tuple[str, ...] = (),
        policy: WorkerPolicy | None = None,
    ) -> WorkerResult:
        selected = policy or WorkerPolicy(
            wall_ms=manifest.resource_policy.wall_ms,
            output_bytes=manifest.resource_policy.output_bytes,
        )
        if not executable.is_file():
            raise WorkerError(f"worker executable does not exist: {executable}")
        envelope = {"manifest": manifest.to_dict(), "request": request}
        environment = {
            "PATH": "/usr/bin:/bin",
            "LANG": "C.UTF-8",
            "PYTHONHASHSEED": "0",
        }
        with tempfile.TemporaryDirectory(prefix="codeforge-script-") as directory:
            process = subprocess.Popen(
                [str(executable), *arguments],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=directory,
                env=environment,
                shell=False,
                start_new_session=(os.name == "posix"),
            )
            try:
                stdout, stderr = process.communicate(
                    json.dumps(envelope, separators=(",", ":")).encode("utf-8"),
                    timeout=selected.wall_ms / 1000,
                )
            except subprocess.TimeoutExpired as exc:
                self._terminate(process)
                raise WorkerError("script worker wall-clock quota exceeded") from exc
        bounded_stdout = stdout[: selected.output_bytes]
        bounded_stderr = stderr[: selected.error_bytes].decode("utf-8", errors="replace")
        if len(stdout) > selected.output_bytes:
            raise WorkerError("script worker output quota exceeded")
        if process.returncode != 0:
            raise WorkerError(
                f"script worker exited with code {process.returncode}: {bounded_stderr}"
            )
        try:
            payload = json.loads(bounded_stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WorkerError("script worker returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise WorkerError("script worker response must be a JSON object")
        return WorkerResult(payload, process.returncode, len(stdout), bounded_stderr)

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is not None:
            return
        if os.name == "posix":
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
        process.communicate()
