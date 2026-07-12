"""Test twin for parts/onboarding.py -- the practical adapter + the one-core-two-adapters proof."""

from parts.onboarding import ONBOARDING, new_onboarding, run_demo
from parts.workflow import WorkflowEngine


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
    from parts import quest

    assert isinstance(quest._ENGINE, WorkflowEngine)  # the game quest
    game_engine = quest._ENGINE
    biz_engine, biz_run = new_onboarding()  # the practical workflow
    assert isinstance(biz_engine, WorkflowEngine)
    assert type(game_engine) is type(biz_engine)
    # And they are genuinely different workflows sharing one engine.
    assert game_engine.workflow.workflow_id == "coilward_contract"
    assert biz_engine.workflow.workflow_id == ONBOARDING.workflow_id == "employee_onboarding"
