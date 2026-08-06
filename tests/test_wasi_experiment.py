"""CF-405: the WASI experiment refuses to claim execution without a runtime."""

from pathlib import Path

import pytest

from kernel.wasi_experiment import WasiExperimentError, inspect_wasi_experiment


def test_wasi_experiment_records_exact_module_and_denies_host_capabilities(tmp_path: Path) -> None:
    module = tmp_path / "command.wasm"
    module.write_bytes(b"\x00asm\x01\x00\x00\x00")
    report = inspect_wasi_experiment(
        "command.inspect",
        module,
        host_capabilities=("event.publish",),
    )
    payload = report.to_dict()
    assert payload["module_digest"].startswith("sha256:")
    assert payload["network"] == "deny"
    assert payload["filesystem"] == "deny"
    assert "shell" in payload["denied_capabilities"]
    assert payload["status"] == "runtime-unavailable"


def test_wasi_experiment_rejects_non_wasm_and_missing_modules(tmp_path: Path) -> None:
    with pytest.raises(WasiExperimentError, match="does not exist"):
        inspect_wasi_experiment("command.inspect", tmp_path / "missing.wasm")
    source = tmp_path / "source.wasm"
    source.write_text("not wasm", encoding="utf-8")
    with pytest.raises(WasiExperimentError, match="WebAssembly"):
        inspect_wasi_experiment("command.inspect", source)
