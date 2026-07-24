"""Test twin for parts/onboarding.py -- the practical adapter + the one-core-two-adapters proof."""

from parts.onboarding import ONBOARDING, available, drive, new_onboarding, run_demo
from parts.shelf.workflow import WorkflowEngine


def test_the_onboarding_flow_reaches_active():
    engine, run = new_onboarding()
    engine.advance(run, "submit_paperwork", actor="employee")
    engine.advance(run, "complete_orientation", actor="hr")
    engine.advance(run, "activate", actor="manager")
    assert run.state == "active"
    assert engine.is_done(run)


def test_roles_are_enforced_the_wrong_actor_is_refused():
    engine, run = new_onboarding()
    # submit_paperwork is a legal move from 'created', but only for the employee role.
    denied = engine.advance(run, "submit_paperwork", actor="manager")
    assert "may not" in denied.reason
    assert run.state == "created"  # unchanged


def test_run_demo_is_a_full_non_game_transcript():
    transcript = run_demo()
    assert transcript[0].startswith("start:")
    assert "Employee active." in transcript[-2]
    assert transcript[-1] == "done: True"


def test_one_core_powers_both_the_game_quest_and_the_practical_workflow():
    # The whole point of the vertical slice: the SAME engine class drives both adapters.
    from parts.world import quest

    game_engine = quest._QUESTS["coilward_contract"].engine  # the game quest (the built-in arc)
    assert isinstance(game_engine, WorkflowEngine)
    biz_engine, biz_run = new_onboarding()  # the practical workflow
    assert isinstance(biz_engine, WorkflowEngine)
    assert type(game_engine) is type(biz_engine)
    # And they are genuinely different workflows sharing one engine.
    assert game_engine.workflow.workflow_id == "coilward_contract"
    assert biz_engine.workflow.workflow_id == ONBOARDING.workflow_id == "employee_onboarding"


# --- the practical interface: `codeforge onboard` drives the same engine, no game ---------------


def _scripted(*answers: str):
    """A reader that returns the given answers in order (ignores the prompt)."""
    it = iter(answers)
    return lambda _prompt: next(it)


def test_available_lists_the_current_states_actions():
    engine, run = new_onboarding()
    assert available(engine, run) == [
        ("submit_paperwork", ["employee"])
    ]  # only this, from 'created'


def test_drive_completes_the_workflow_through_the_terminal():
    out: list[str] = []
    run = drive(
        reader=_scripted("submit_paperwork", "complete_orientation", "activate"),
        writer=out.append,
    )
    assert run.state == "active"
    assert [h["to"] for h in run.history] == ["paperwork", "oriented", "active"]
    assert any("DONE: Employee active." in line for line in out)
    assert any("role: hr" in line for line in out)  # role-gating is shown to the operator


def test_drive_rejects_an_unavailable_action_then_lets_you_quit():
    out: list[str] = []
    run = drive(reader=_scripted("nonsense", "quit"), writer=out.append)
    assert run.state == "created"  # never advanced
    assert any("not available" in line for line in out)
    assert any("before completion" in line for line in out)


def test_the_onboard_cli_subcommand_routes_to_drive(monkeypatch):
    import parts.onboarding as onboarding_mod
    from parts.cli import main

    called = {"n": 0}
    monkeypatch.setattr(onboarding_mod, "drive", lambda: called.__setitem__("n", called["n"] + 1))
    assert main(["onboard"]) == 0
    assert called["n"] == 1
