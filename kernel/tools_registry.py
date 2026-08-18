"""CARD: tools_registry -- refuse a tool record that cannot prove the tool works.

Road v3 section 11 puts tools on the same ladder as language lanes:

    LISTED -> INSTALLED -> INVOCABLE (a proof command is captured) -> REGISTERED (a record exists)

Before `tools_registry.toml` existed, seven tools sat at INVOCABLE and none was REGISTERED,
because there was nowhere for a record to live. This module is what makes the last rung mean
something: a registry nothing validates is a list, and a list is what we already had.

THE ONE RULE THAT MATTERS: `proof_command` may not be a version check. A tool that answers
`--version` has proven it is installed and nothing else, and this ship has been caught by that
distinction three times in a week -- trivy and gitleaks installed and off PATH, the suite runner
resolving to the system interpreter, detekt configured with a burn-down ledger and invoked by
nothing. The proof command must be one that FAILS when the tool is broken for this repository.

`known_faults` may never be blank. "none observed" is an answer; silence is not. Every record on
file today carries a real fault, because every one of these tools has already surprised us.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

REGISTRY = Path(__file__).resolve().parent.parent / "tools_registry.toml"

#: Every field a record must carry. A record missing one is not a record.
REQUIRED_FIELDS = (
    "tool_id",
    "executable",
    "version_command",
    "proof_command",
    "supported_inputs",
    "supported_outputs",
    "language_lanes",
    "known_faults",
)

#: A proof command containing only these is a version check wearing a proof's name.
_VERSION_ONLY = ("--version", "-version", "version", "-V")


@dataclass(frozen=True)
class RegistryVerdict:
    """What the registry says about itself."""

    findings: list[str]
    registered: list[str]

    @property
    def clean(self) -> bool:
        return not self.findings

    def render(self) -> str:
        lines = ["Tool registry :: every record proves its tool works"]
        for finding in self.findings:
            lines.append(f"  FINDING  {finding}")
        if not self.findings:
            lines.append(
                f"  {len(self.registered)} tool(s) REGISTERED, each with a proof command that is "
                f"not a version check"
            )
        lines.append(
            f"VERDICT: {'PASS' if self.clean else 'FAIL'} "
            f"({len(self.findings)} finding(s), {len(self.registered)} registered)"
        )
        return "\n".join(lines)


def _is_version_only(command: str) -> bool:
    """Is this proof command nothing but a version check?

    Split on the shell operators a real proof tends to use, then ask whether EVERY part is a
    version probe. `go version && golangci-lint --version` is still version-only; `make lint-go`
    is not; and `./gradlew --version && make lint-kotlin` is not, because one part does work.
    """
    parts = [p.strip() for p in command.replace("&&", ";").replace("||", ";").split(";")]
    parts = [p for p in parts if p]
    if not parts:
        return True
    return all(any(flag in part for flag in _VERSION_ONLY) for part in parts)


def inspect(path: Path = REGISTRY) -> RegistryVerdict:
    """Read the registry and report every record that cannot stand up. Reads only."""
    findings: list[str] = []
    registered: list[str] = []

    if not path.is_file():
        return RegistryVerdict(
            findings=[f"{path.name} does not exist, so no tool is REGISTERED"], registered=[]
        )

    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        return RegistryVerdict(findings=[f"{path.name} is not valid TOML: {exc}"], registered=[])

    records = raw.get("tool", [])
    if not records:
        return RegistryVerdict(findings=[f"{path.name} declares no tools"], registered=[])

    seen: set[str] = set()
    for index, record in enumerate(records):
        name = str(record.get("tool_id") or f"<record {index}>")
        for field in REQUIRED_FIELDS:
            value = record.get(field)
            if value is None or (isinstance(value, str) and not value.strip()) or value == []:
                findings.append(f"{name}: missing or empty `{field}`")
        if name in seen:
            findings.append(f"{name}: duplicate tool_id")
        seen.add(name)

        proof = str(record.get("proof_command") or "")
        if proof and _is_version_only(proof):
            findings.append(
                f"{name}: proof_command `{proof}` is a VERSION CHECK, not a proof. It shows the "
                f"tool is installed and nothing about whether it works on this repository"
            )
        if not any(f"{name}: missing or empty" in f for f in findings):
            registered.append(name)

    return RegistryVerdict(findings=findings, registered=registered)


def main() -> int:
    verdict = inspect()
    print(verdict.render())
    return 0 if verdict.clean else 1


if __name__ == "__main__":
    raise SystemExit(main())
