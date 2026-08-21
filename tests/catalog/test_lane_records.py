"""Contract tests for the ecosystem provisioning reference records."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

import yaml

LANE_DIR = Path(__file__).resolve().parents[2] / "catalog" / "lanes"
LANE_ALIASES = {"kotlin": "kotlin-jvm", "typescript": "typescript-node"}


def _mapping(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), path
    return loaded


def _governance_register() -> dict[str, Any]:
    workshop_root = Path(
        os.environ.get("MATRYM_WORKSHOP_ROOT", str(Path(__file__).resolve().parents[3]))
    )
    candidates = [
        workshop_root / "hardware-store" / "LANGUAGE_LANES.yaml",
        workshop_root / "hardware-store-codex" / "LANGUAGE_LANES.yaml",
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            return _mapping(candidate)
        except yaml.YAMLError:
            continue
    raise AssertionError(f"no readable governance register found in {candidates}")


def _records() -> dict[str, dict[str, Any]]:
    return {
        path.stem: _mapping(path)
        for path in sorted(LANE_DIR.glob("*.yaml"))
        if not path.name.startswith("_")
    }


def test_every_governed_language_has_a_provisioning_record() -> None:
    governance = _governance_register()
    records = _records()
    languages = {
        row["language"]
        for row in governance["lanes"]
        if isinstance(row, dict) and isinstance(row.get("language"), str)
    }
    expected_records = {LANE_ALIASES.get(language, language) for language in languages}
    assert expected_records <= records.keys()


def test_candidate_sql_engines_are_recorded_without_reverse_governance_claim() -> None:
    records = _records()
    assert records["sql-sqlserver"]["provisioning_status"] == "CANDIDATE"
    assert records["sql-mysql"]["provisioning_status"] == "CANDIDATE"
    assert records["sql-sqlserver"]["verified_on"] is None
    assert records["sql-mysql"]["verified_on"] is None


def test_each_record_matches_the_schema() -> None:
    schema = _mapping(LANE_DIR / "_schema.yaml")
    allowed_statuses = set(schema["provisioning_status_values"])
    required_fields = set(schema["required_fields"])
    command_fields = set(schema["command_required_fields"])

    for lane, record in _records().items():
        assert required_fields <= record.keys(), lane
        assert record["lane"] == lane
        assert record["ecosystem"], lane
        assert record["provisioning_status"] in allowed_statuses, lane
        assert "status" not in record, lane

        commands = record["commands"]
        assert isinstance(commands, list) and commands, lane
        for command in commands:
            assert isinstance(command, dict), lane
            assert command_fields <= command.keys(), lane
            assert command["command"] and command["purpose"], lane

        verified_on = record["verified_on"]
        output = record["verification_output"]
        if verified_on is None:
            assert output is None, lane
        else:
            assert isinstance(verified_on, date), lane
            assert record["provisioning_status"] == "INSTALLED", lane
            assert isinstance(output, str) and output.strip(), lane


def test_verified_date_cannot_be_claimed_without_installed_evidence() -> None:
    records = _records()
    for lane, record in records.items():
        if record["verified_on"] is not None:
            assert record["provisioning_status"] == "INSTALLED", lane
            assert record["verification_output"], lane
