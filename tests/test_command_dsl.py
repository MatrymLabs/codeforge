"""CF-404: bounded command DSL experiment."""

from __future__ import annotations

import pytest

from kernel.command_dsl import (
    CommandDslError,
    compare_command_implementations,
    parse_command_dsl,
)

SOURCE = """
# A read-only command contract; this is not executable source.
command: command.inspect_component
verb: inspect
argument: component_id
requires: component.inspect
summary: Inspect the approved component and its evidence.
fallback: Component evidence is shown in text.
effects: read
"""


def test_dsl_compiles_to_a_bounded_accessible_command_contract() -> None:
    command = parse_command_dsl(SOURCE)
    contract = command.contract()
    assert contract["command_id"] == "command.inspect_component"
    assert contract["required_capabilities"] == ["component.inspect"]
    assert contract["side_effects"] == ["read"]
    assert contract["text_fallback"] == "Component evidence is shown in text."


def test_dsl_refuses_unknown_fields_duplicates_and_missing_contract_fields() -> None:
    with pytest.raises(CommandDslError, match="expected"):
        parse_command_dsl("shell: os.system('rm -rf /')")
    with pytest.raises(CommandDslError, match="duplicate"):
        parse_command_dsl(SOURCE + "verb: again\n")
    with pytest.raises(CommandDslError, match="missing fields"):
        parse_command_dsl("command: command.only")


def test_dsl_comparison_records_tradeoffs_without_selecting_a_runtime() -> None:
    report = compare_command_implementations(
        SOURCE,
        "emit('inspected'); return 1",
    )
    payload = report.to_dict()
    assert payload["decision"] == "experiment-only"
    assert payload["dsl_contract"]["required_capabilities"] == ["component.inspect"]
    assert payload["lua"]["source_digest"].startswith("sha256:")
    assert "accessibility" in payload["dimensions"]
