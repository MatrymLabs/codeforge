"""CARD: foundry -- propose a change, gate it on human approval, then generate under guard.

Proving Ground phases 9-10 (the AI-touches-files phases), made safe. Two hard rails, straight from
docs/proving_ground/SAFETY.md:

  Phase 9  A PatchProposal is a DATA artifact -- what file, why, which part, the risk, how to
           test, how to revert. Creating one writes NOTHING. A human must APPROVE it first.
  Phase 10 Applying an APPROVED proposal generates a NEW file into a cordoned, git-ignored
           sandbox (workspace/). It refuses to escape the sandbox, refuses to overwrite, and
           files evidence. It NEVER edits existing source, config, git state, or main.

The result is a candidate for review, not a finished part: promoting it into parts/ stays a
human branch -> check -> PR action (the SAFETY rule: reversible + low-risk stays in the
Workshop; risky or outward-facing goes to PyCharm). This surface never runs a subprocess and
never calls the network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from pathlib import Path

_SANDBOX = "workspace"  # the only directory generation may write into (git-ignored)
_RISK = ("low", "medium", "high")
_LABEL = re.compile(r"^[a-z][a-z0-9_]*$")


class ProposalError(ValueError):
    """A malformed or unsafe proposal: fail loud, never write a byte."""


@dataclass(frozen=True)
class PatchProposal:
    """A proposed change as DATA (SAFETY.md fields). Creating one writes nothing; it must be
    approved by a human before it can be generated."""

    proposal_id: str
    target: str  # relative path to CREATE, inside the sandbox
    content: str  # what would be written
    rationale: str  # why
    risk: str = "low"  # low | medium | high
    affected_part: str = ""  # which reusable part this touches, if any
    test: str = ""  # how it would be tested
    rollback: str = ""  # how to undo (auto-filled: delete the generated file)
    approved: bool = False  # the human approval gate -- False until a person says so

    tags: list[str] = field(default_factory=list)


def _root() -> Path:
    return Path(__file__).resolve().parent.parent


def _resolve_in_sandbox(target: str, base: Path) -> Path:
    """Resolve a target strictly inside the sandbox, or refuse. Blocks absolute paths and
    `..` traversal -- generation can only ever land under workspace/."""
    if not target.strip():
        raise ProposalError("refused: empty target path")
    if target.startswith(("/", "~")) or Path(target).is_absolute():
        raise ProposalError(f"refused: target must be a relative path inside {_SANDBOX}/")
    dest = (base / target).resolve()
    if not dest.is_relative_to(base.resolve()):
        raise ProposalError(f"refused: '{target}' escapes the {_SANDBOX}/ sandbox")
    return dest


def propose(
    proposal_id: str,
    target: str,
    content: str,
    *,
    rationale: str,
    risk: str = "low",
    affected_part: str = "",
    test: str = "",
    rollback: str = "",
) -> PatchProposal:
    """Build a PatchProposal (UNAPPROVED). Validates and fails loud; writes NOTHING to disk."""
    if not _LABEL.match(proposal_id):
        raise ProposalError(f"proposal_id {proposal_id!r} must be lowercase_snake_case")
    if not content.strip():
        raise ProposalError(f"proposal {proposal_id!r}: 'content' is empty -- nothing to generate")
    if not rationale.strip():
        raise ProposalError(f"proposal {proposal_id!r}: 'rationale' (why) is required")
    if risk not in _RISK:
        raise ProposalError(f"proposal {proposal_id!r}: risk must be one of {_RISK}")
    # A basic path check now; the authoritative sandbox check happens again at apply time.
    _resolve_in_sandbox(target, _root() / _SANDBOX)
    return PatchProposal(
        proposal_id=proposal_id,
        target=target,
        content=content,
        rationale=rationale,
        risk=risk,
        affected_part=affected_part,
        test=test,
        rollback=rollback or f"delete the generated file: {_SANDBOX}/{target}",
        approved=False,
    )


def approve(proposal: PatchProposal) -> PatchProposal:
    """The human approval gate: return an APPROVED copy. Only a person should call this."""
    return replace(proposal, approved=True)


def apply_proposal(proposal: PatchProposal, root: Path | None = None) -> Path:
    """Generate an APPROVED proposal into the sandbox. Refuses unless approved; refuses to
    escape the sandbox; refuses to overwrite. Returns the path written. (Phase 10.)"""
    if not proposal.approved:
        raise ProposalError(
            "refused: not approved -- a human must approve before any byte is written"
        )
    base = (root if root is not None else _root()) / _SANDBOX
    dest = _resolve_in_sandbox(proposal.target, base)
    if dest.exists():
        raise ProposalError(
            f"refused: '{proposal.target}' already exists -- generation never overwrites"
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(proposal.content, encoding="utf-8")
    return dest


def render_proposal(proposal: PatchProposal) -> str:
    """A human-readable preview of a proposal (the review surface before approval)."""
    status = "APPROVED" if proposal.approved else "PENDING approval"
    lines = [
        f"PATCH PROPOSAL [{proposal.proposal_id}] - {status}",
        f"  target   : {_SANDBOX}/{proposal.target}  (a new candidate file, sandboxed)",
        f"  why      : {proposal.rationale}",
        f"  risk     : {proposal.risk}",
    ]
    if proposal.affected_part:
        lines.append(f"  part     : {proposal.affected_part}")
    if proposal.test:
        lines.append(f"  test     : {proposal.test}")
    lines += [
        f"  rollback : {proposal.rollback}",
        "",
        "  --- content preview (first lines) ---",
    ]
    preview = proposal.content.splitlines()[:8]
    lines += [f"  | {line}" for line in preview]
    if len(proposal.content.splitlines()) > 8:
        lines.append("  | ...")
    lines += [
        "",
        "  A human must approve before anything is written. Generation lands only in the",
        f"  {_SANDBOX}/ sandbox; promoting it into parts/ is a human branch -> check -> PR step.",
    ]
    return "\n".join(lines)


# --- the in-MUD `@forge` flow: owner-only, two-step (propose -> approve -> generate) --------
#
# Pending proposals live per-process until approved. `@forge` is an ADMIN verb (owner rank),
# so a demo visitor (always rank 'player') can never reach it, and it writes only to the
# git-ignored sandbox.

_PENDING: dict[str, PatchProposal] = {}


def scaffold_part(name: str) -> str:
    """A deterministic part-skeleton candidate (NOT a finished part) for the `@forge` flow."""
    return (
        f'"""CARD: {name} -- (draft) describe the one job this part does.\n\n'
        "Generated by the Foundry as a candidate skeleton. Review it, flesh it out, write its\n"
        "test twin, and promote it into parts/ via the normal branch -> check -> PR flow.\n"
        'It is NOT a finished part.\n"""\n\n\n'
        f"def {name}() -> str:\n"
        '    """One clear job. Replace this stub."""\n'
        f'    raise NotImplementedError("forge me: implement {name} and write '
        f'tests/test_{name}.py")\n'
    )


def forge_command(session: object, arg: str = "", root: Path | None = None) -> str:
    """The owner-only `@forge` verb: propose a part skeleton, then approve to generate it into
    the sandbox. Rank is enforced by the command spine (ADMIN verb, min_rank owner)."""
    parts = arg.split(maxsplit=1)
    sub = parts[0].strip().lower() if parts else ""
    rest = parts[1].strip() if len(parts) > 1 else ""

    if sub in ("", "list"):
        if not _PENDING:
            return "No pending proposals. Draft one: @forge <part_name>"
        lines = ["PENDING PROPOSALS (approve with: @forge approve <id>)", ""]
        lines += [f"  {pid:20} -> {_SANDBOX}/{p.target}" for pid, p in sorted(_PENDING.items())]
        return "\n".join(lines)

    if sub == "approve":
        proposal = _PENDING.get(rest)
        if proposal is None:
            return f"No pending proposal '{rest}'. List them: @forge list"
        try:
            written = apply_proposal(approve(proposal), root=root)
        except ProposalError as exc:
            return str(exc)
        _PENDING.pop(rest, None)
        return (
            f"Generated {written} (a sandboxed candidate).\n"
            f"  Review it, then promote it into parts/ via branch -> check -> PR.\n"
            f"  Rollback: {proposal.rollback}"
        )

    # Otherwise: draft a proposal to scaffold a new part named `sub`.
    name = sub
    if not _LABEL.match(name):
        return f"'{name}' must be lowercase_snake_case (a part name). Try: @forge my_part"
    try:
        proposal = propose(
            proposal_id=name,
            target=f"generated/{name}.py",
            content=scaffold_part(name),
            rationale=f"scaffold a new '{name}' part skeleton for review",
            risk="low",
            affected_part=name,
            test=f"tests/test_{name}.py (to be written when promoted)",
        )
    except ProposalError as exc:
        return str(exc)
    _PENDING[name] = proposal
    return render_proposal(proposal) + f"\n\n  Approve to generate: @forge approve {name}"
