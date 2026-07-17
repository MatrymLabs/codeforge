"""Test twin for parts/foundry.py -- the propose/approve/generate safety pipeline.

The refusal cases are the point: a file-writing feature is only safe if it refuses loudly.
Acceptance: propose writes nothing; an approved proposal generates ONE new sandbox file with
the right content. Refusal: apply without approval, overwrite, sandbox escape (absolute or
`..`), and malformed proposals all fail loud and write NOTHING. The `@forge` verb is owner-
gated (a player is denied at the tick).
"""

import pytest

from forge import handle_command
from parts.foundry import (
    _PENDING,
    PatchProposal,
    ProposalError,
    apply_proposal,
    approve,
    forge_command,
    preview_seed,
    propose,
    render_proposal,
    render_proving_ground,
    scaffold_part,
)
from parts.session import Session


@pytest.fixture(autouse=True)
def _clear_pending():
    _PENDING.clear()
    yield
    _PENDING.clear()


def _good(**over):
    kw = dict(
        proposal_id="my_part",
        target="generated/my_part.py",
        content="print('hi')\n",
        rationale="scaffold a part",
    )
    kw.update(over)
    return propose(**kw)


# --- Phase 9: propose writes nothing; approval is a separate, human step -----


def test_propose_writes_nothing(tmp_path):
    p = _good()
    assert p.approved is False
    assert list(tmp_path.iterdir()) == []  # no side effects on disk anywhere we control


def test_render_shows_pending_then_approved():
    p = _good()
    assert "PENDING approval" in render_proposal(p)
    assert "APPROVED" in render_proposal(approve(p))


@pytest.mark.parametrize(
    "over, needle",
    [
        ({"proposal_id": "Bad-Id"}, "snake_case"),
        ({"content": "   "}, "nothing to generate"),
        ({"rationale": ""}, "rationale"),
        ({"risk": "spicy"}, "risk must be one of"),
        ({"target": "/etc/passwd"}, "relative path"),
        ({"target": "../secrets.py"}, "escapes"),
    ],
)
def test_bad_proposals_fail_loud(over, needle):
    with pytest.raises(ProposalError) as err:
        _good(**over)
    assert needle in str(err.value)


# --- Phase 10: generation is approved-only, sandboxed, no-overwrite ----------


def test_apply_without_approval_is_refused_and_writes_nothing(tmp_path):
    with pytest.raises(ProposalError) as err:
        apply_proposal(_good(), root=tmp_path)
    assert "not approved" in str(err.value)
    assert not (tmp_path / "workspace").exists()  # nothing was written


def test_approved_proposal_generates_one_sandboxed_file(tmp_path):
    written = apply_proposal(approve(_good()), root=tmp_path)
    assert written == (tmp_path / "workspace" / "generated" / "my_part.py")
    assert written.read_text() == "print('hi')\n"


def test_generation_never_overwrites(tmp_path):
    apply_proposal(approve(_good()), root=tmp_path)
    with pytest.raises(ProposalError) as err:
        apply_proposal(approve(_good()), root=tmp_path)
    assert "never overwrites" in str(err.value)


def test_generation_cannot_escape_the_sandbox(tmp_path):
    # A proposal that slipped a traversal target past propose() is still refused at apply.
    evil = PatchProposal(
        proposal_id="evil",
        target="../../etc/pwned.py",
        content="x",
        rationale="attack",
        approved=True,
    )
    with pytest.raises(ProposalError) as err:
        apply_proposal(evil, root=tmp_path)
    assert "escapes" in str(err.value)
    assert not (tmp_path.parent / "etc" / "pwned.py").exists()


# --- the @forge flow: propose -> approve -> generate -------------------------


def test_forge_proposes_then_generates(tmp_path):
    out = forge_command(Session(player_id="o", rank="owner"), "my_part", root=tmp_path)
    assert "PATCH PROPOSAL" in out and "@forge approve my_part" in out
    assert not (tmp_path / "workspace").exists()  # proposing wrote nothing

    done = forge_command(Session(player_id="o", rank="owner"), "approve my_part", root=tmp_path)
    assert "Generated" in done
    assert (tmp_path / "workspace" / "generated" / "my_part.py").exists()


def test_forge_approve_unknown_is_honest(tmp_path):
    assert "No pending proposal" in forge_command(
        Session(player_id="o", rank="owner"), "approve ghost", root=tmp_path
    )


def test_forge_rejects_a_bad_part_name(tmp_path):
    assert "snake_case" in forge_command(
        Session(player_id="o", rank="owner"), "Bad-Name", root=tmp_path
    )


def test_scaffold_is_a_draft_skeleton_not_a_finished_part():
    body = scaffold_part("widget")
    assert "CARD: widget" in body
    assert "NotImplementedError" in body  # a stub, never a claim of function


# --- owner-gated at the engine tick ------------------------------------------


def test_forge_is_owner_gated_at_the_tick():
    denied = handle_command(Session(player_id="p", rank="player"), "@forge my_part")
    assert "authority" in denied.lower() or "denied" in denied.lower()
    # An owner reaches it (proposing writes nothing to the real repo).
    allowed = handle_command(Session(player_id="o", rank="owner"), "@forge list")
    assert "proposal" in allowed.lower()


# --- the arch: read-only Proving Ground review ------------------------------


def test_proving_ground_is_empty_by_default(tmp_path):
    out = render_proving_ground(root=tmp_path)
    assert "Nothing forged yet" in out


def test_proving_ground_lists_forged_candidates(tmp_path):
    apply_proposal(approve(_good()), root=tmp_path)  # forge one candidate
    out = render_proving_ground(root=tmp_path)
    assert "generated/my_part.py" in out
    assert "nothing here is wired into the engine" in out


def test_arch_is_owner_gated_and_read_only_at_the_tick():
    denied = handle_command(Session(player_id="p", rank="player"), "@arch")
    assert "authority" in denied.lower() or "denied" in denied.lower()
    allowed = handle_command(Session(player_id="o", rank="owner"), "@arch")
    assert "PROVING GROUND" in allowed


# --- the arch: read-only preview of a built game ----------------------------


def test_arch_preview_shows_the_room_you_would_wake_in():
    out = preview_seed("first-forge")  # a real installed seed
    assert "THROUGH THE ARCH: first-forge" in out
    assert "You would wake in: The Cold Forge" in out  # first-forge's START_ROOM
    assert "training_dummy" in out  # a known inhabitant, listed read-only
    assert "does not enter it" in out  # honest: a preview, not a boot


def test_arch_preview_without_a_name_lists_installed_games():
    out = preview_seed("")
    assert "Name a game to preview" in out
    assert "first-forge" in out  # a real installed game appears in the listing


def test_arch_preview_of_an_unknown_game_is_refused():
    out = preview_seed("no_such_game")
    assert "No game named 'no_such_game'" in out


def test_arch_preview_does_not_swap_the_running_world():
    # A projection, never a boot: previewing another seed leaves the live world untouched.
    from parts import world

    before = world.START_ROOM
    preview_seed("first-forge")
    assert before == world.START_ROOM


def test_arch_preview_is_owner_gated_at_the_tick():
    denied = handle_command(Session(player_id="p", rank="player"), "@arch preview first-forge")
    assert "authority" in denied.lower() or "denied" in denied.lower()
    allowed = handle_command(Session(player_id="o", rank="owner"), "@arch preview first-forge")
    assert "THROUGH THE ARCH" in allowed
