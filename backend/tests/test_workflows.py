"""Workflow state-machine tests: legal/illegal transitions, terminal states,
late worker callbacks on canceled runs."""

import pytest

from workflows import engine
from workflows.models import WorkflowRun


@pytest.fixture
def run(db, project):
    return WorkflowRun.objects.create(
        project=project,
        workflow_type="VIDEO_PRODUCTION",
        temporal_workflow_id="project-x-v1",
        status="DRAFT",
    )


@pytest.mark.django_db
def test_legal_forward_chain(run):
    chain = [
        "PLANNING",
        "AWAITING_APPROVAL",
        "QUEUED",
        "RESEARCHING",
        "SCRIPTING",
        "STORYBOARDING",
        "GENERATING_ASSETS",
        "GENERATING_NARRATION",
        "ASSEMBLING",
        "RENDERING",
        "VALIDATING",
        "FINAL_REVIEW",
        "READY_TO_PUBLISH",
        "UPLOADING",
        "SCHEDULED",
        "PUBLISHED",
    ]
    for state in chain:
        engine.transition(run, state)
        assert run.status == state
    assert run.events.count() == len(chain)


@pytest.mark.django_db
def test_illegal_transition_raises(run):
    engine.transition(run, "PLANNING")
    with pytest.raises(engine.InvalidTransition):
        engine.transition(run, "PUBLISHED")  # skipping the chain is illegal
    with pytest.raises(engine.InvalidTransition):
        engine.transition(run, "NOPE")  # unknown state


@pytest.mark.django_db
def test_terminal_states_have_no_outgoing_edges(run):
    assert engine.TERMINAL_STATES == frozenset({"PUBLISHED", "FAILED", "CANCELED"})
    engine.transition(run, "CANCELED")
    with pytest.raises(engine.InvalidTransition):
        engine.transition(run, "QUEUED")
    with pytest.raises(engine.InvalidTransition):
        engine.transition(run, "DRAFT")


@pytest.mark.django_db
def test_failed_retry_edge_allowed(run):
    engine.transition(run, "PLANNING")
    engine.transition(run, "FAILED")
    engine.transition(run, "QUEUED")  # retry edge out of FAILED
    assert run.status == "QUEUED"


@pytest.mark.django_db
def test_parked_state_recovery(run):
    engine.transition(run, "PLANNING")
    engine.transition(run, "PAUSED")
    engine.transition(run, "QUEUED")
    engine.transition(run, "BLOCKED_ON_RESOURCES")
    engine.transition(run, "QUEUED")
    engine.transition(run, "BLOCKED_ON_APPROVAL")
    engine.transition(run, "AWAITING_APPROVAL")
    assert run.status == "AWAITING_APPROVAL"


@pytest.mark.django_db
def test_canceled_run_ignores_late_worker_callback(run):
    engine.transition(run, "PLANNING")
    engine.transition(run, "CANCELED")
    applied = engine.apply_worker_event(run, "QUEUED", event_type="worker_callback")
    assert applied is False
    run.refresh_from_db()
    assert run.status == "CANCELED"  # late callback did not resurrect the run
    assert run.events.filter(event_type="late_callback_ignored").exists()


@pytest.mark.django_db
def test_workflow_states_match_spec():
    assert engine.WORKFLOW_STATES == [
        "DRAFT",
        "PLANNING",
        "AWAITING_APPROVAL",
        "QUEUED",
        "RESEARCHING",
        "SCRIPTING",
        "STORYBOARDING",
        "GENERATING_ASSETS",
        "GENERATING_NARRATION",
        "ASSEMBLING",
        "RENDERING",
        "VALIDATING",
        "FINAL_REVIEW",
        "READY_TO_PUBLISH",
        "UPLOADING",
        "SCHEDULED",
        "PUBLISHED",
        "FAILED",
        "CANCELED",
        "PAUSED",
        "BLOCKED_ON_RESOURCES",
        "BLOCKED_ON_APPROVAL",
    ]
