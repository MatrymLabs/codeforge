"""Honest boundary for the portable WASI component experiment.

This module does not emulate WASI or treat a normal subprocess as a WASI proof.  It records the
runtime and capability conditions needed for the experiment, and refuses to report execution when
no approved runtime is installed.
"""

from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


class WasiExperimentError(ValueError):
    """The WASI experiment request is malformed or cannot be honestly executed."""


@dataclass(frozen=True)
class WasiExperimentReport:
    """Evidence for one bounded portable-command experiment."""

    command_id: str
    module_digest: str
    runtime: str
    status: str
    network: str
    filesystem: str
    host_capabilities: tuple[str, ...]
    denied_capabilities: tuple[str, ...]
    notes: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "experiment": "wasi-component/1",
            "command_id": self.command_id,
            "module_digest": self.module_digest,
            "runtime": self.runtime,
            "status": self.status,
            "network": self.network,
            "filesystem": self.filesystem,
            "host_capabilities": list(self.host_capabilities),
            "denied_capabilities": list(self.denied_capabilities),
            "notes": list(self.notes),
            "decision": "experiment-only",
        }


def inspect_wasi_experiment(
    command_id: str,
    module: Path,
    *,
    host_capabilities: tuple[str, ...] = (),
) -> WasiExperimentReport:
    """Inspect an exact WASM artifact without executing it.

    The report becomes ``ready`` only when a known runtime is present.  Even then, this function
    remains an inspection boundary; execution belongs to a future sandbox broker with limits and
    evidence capture.
    """
    if not command_id.strip():
        raise WasiExperimentError("command_id must not be empty")
    path = Path(module)
    if not path.is_file():
        raise WasiExperimentError("WASI module does not exist")
    data = path.read_bytes()
    if not data.startswith(b"\x00asm"):
        raise WasiExperimentError("module is not a WebAssembly binary")
    runtime = shutil.which("wasmtime") or shutil.which("wasmer") or ""
    denied = ("network", "filesystem", "process", "shell", "package_install", "database")
    return WasiExperimentReport(
        command_id=command_id,
        module_digest=f"sha256:{hashlib.sha256(data).hexdigest()}",
        runtime=runtime or "unavailable",
        status="ready" if runtime else "runtime-unavailable",
        network="deny",
        filesystem="deny",
        host_capabilities=tuple(sorted(set(host_capabilities))),
        denied_capabilities=denied,
        notes=(
            "inspection only; no module execution occurred",
            "portable behavior requires an approved WASI component runtime",
        ),
    )
