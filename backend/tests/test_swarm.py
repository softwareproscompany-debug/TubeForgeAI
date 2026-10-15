"""Swarm tests: orchestrator sequencing, critic revision loop, API surface.

The LLM gateway is mocked — no real provider calls. We patch
``swarm.orchestrator.complete_text`` (the single seam between the
orchestrator and the provider gateway).
"""

import json
from unittest.mock import patch

import pytest
from django.urls import reverse

from providers.gateway import ProviderError
from swarm.models import Agent, AgentMessage, SwarmRun
from swarm.orchestrator import SwarmOrchestrator


def _ok(**kwargs):
    return json.dumps({"ok": True, **kwargs})


def _mock_all_ok(**kwargs):
    agent = kwargs["agent"]
    if agent.role == "critic":
        return json.dumps({"approved": True, "score": 9, "feedback": "solid"})
    return _ok(role=agent.role)


@pytest.fixture
def orchestrator(db):
    return SwarmOrchestrator()


def _run_stages(run):
    return [
        m.content.get("stage")
        for m in run.messages.filter(message_type="result").order_by("created_at")
    ]


# ---------------------------------------------------------------------------
# Orchestrator: happy path
# ---------------------------------------------------------------------------
def test_start_run_completes_and_persists_messages(db, project, orchestrator):
    with patch("swarm.orchestrator.complete_text", side_effect=_mock_all_ok):
        run = orchestrator.start_run(project.id, "how to brew pour-over coffee")

    run.refresh_from_db()
    assert run.status == "completed"
    assert run.current_stage == "done"
    assert run.completed_at is not None
    assert run.messages.count() > 0


def test_stage_sequencing_research_write_edit_publish(db, project, orchestrator):
    with patch("swarm.orchestrator.complete_text", side_effect=_mock_all_ok):
        run = orchestrator.start_run(project.id, "topic")

    assert _run_stages(run) == ["research", "writing", "editing", "publishing"]
    # Each stage opens with a system task message addressed to its producer.
    tasks = run.messages.filter(message_type="task").order_by("created_at")
    assert [m.to_agent.role for m in tasks] == [
        "researcher",
        "writer",
        "editor",
        "publisher",
    ]
    assert all(m.from_agent is None for m in tasks)  # system tasks


def test_result_messages_broadcast_from_producer(db, project, orchestrator):
    with patch("swarm.orchestrator.complete_text", side_effect=_mock_all_ok):
        run = orchestrator.start_run(project.id, "topic")

    results = run.messages.filter(message_type="result").order_by("created_at")
    assert results.count() == 4
    for message in results:
        assert message.from_agent is not None  # producer
        assert message.to_agent is None  # broadcast
        assert "output" in message.content


# ---------------------------------------------------------------------------
# Critic review loop
# ---------------------------------------------------------------------------
def test_critic_approves_first_try_no_revisions(db, project, orchestrator):
    with patch("swarm.orchestrator.complete_text", side_effect=_mock_all_ok):
        run = orchestrator.start_run(project.id, "topic")

    assert run.messages.filter(message_type="revision_request").count() == 0
    answers = run.messages.filter(message_type="answer").order_by("created_at")
    assert answers.count() == 2  # writer + editor reviewed
    assert all(m.content["verdict"]["approved"] for m in answers)


def test_critic_rejection_triggers_revision_then_approves(db, project, orchestrator):
    calls = {"critic": 0}

    def fake(**kwargs):
        agent = kwargs["agent"]
        if agent.role == "critic":
            calls["critic"] += 1
            approved = calls["critic"] % 2 == 0  # reject, then approve
            return json.dumps(
                {
                    "approved": approved,
                    "score": 4 if not approved else 8,
                    "feedback": "too generic" if not approved else "good",
                }
            )
        return _ok(role=agent.role, attempt=calls["critic"])

    with patch("swarm.orchestrator.complete_text", side_effect=fake):
        run = orchestrator.start_run(project.id, "topic")

    revisions = run.messages.filter(message_type="revision_request").order_by(
        "created_at"
    )
    assert revisions.count() == 2  # one per reviewed stage
    first = revisions[0]
    assert first.from_agent.role == "critic"
    assert first.to_agent.role == "writer"
    assert first.content["feedback"] == "too generic"
    run.refresh_from_db()
    assert run.status == "completed"


def test_revision_loop_caps_at_three_retries_then_proceeds(db, project, orchestrator):
    def fake(**kwargs):
        agent = kwargs["agent"]
        if agent.role == "critic":
            return json.dumps({"approved": False, "score": 2, "feedback": "still bad"})
        return _ok(role=agent.role)

    with patch("swarm.orchestrator.complete_text", side_effect=fake):
        run = orchestrator.start_run(project.id, "topic")

    revisions = run.messages.filter(message_type="revision_request").order_by(
        "created_at"
    )
    # 3 retries per reviewed stage (writer + editor) = 6 total.
    assert revisions.count() == 6
    assert revisions[0].content["attempt"] == 1
    assert revisions[2].content["attempt"] == 3
    assert revisions[2].content["max_attempts"] == 3
    run.refresh_from_db()
    assert run.status == "completed"  # proceeds anyway after cap


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------
def test_gateway_failure_marks_run_failed_with_error(db, project, orchestrator):
    def boom(**kwargs):
        raise ProviderError("No text-capable LLM provider", code="NO_TEXT_PROVIDER")

    with patch("swarm.orchestrator.complete_text", side_effect=boom):
        run = orchestrator.start_run(project.id, "topic")

    run.refresh_from_db()
    assert run.status == "failed"
    assert "No text-capable LLM provider" in run.error
    assert run.completed_at is not None
    # Agents are released back to idle even on failure.
    assert all(a.status == "idle" for a in Agent.objects.all())


def test_seed_migration_creates_five_agents(db):
    roles = set(Agent.objects.values_list("role", flat=True))
    assert roles == {"researcher", "writer", "editor", "publisher", "critic"}
    assert all(a.system_prompt for a in Agent.objects.all())


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------
def test_create_run_returns_201_and_completes(db, project, auth_client):
    with patch("swarm.orchestrator.complete_text", side_effect=_mock_all_ok):
        response = auth_client.post(
            reverse("swarm-runs"),
            {"project_id": str(project.id), "topic": "espresso basics"},
            format="json",
        )
    assert response.status_code == 201, response.content
    body = response.json()
    assert body["status"] == "completed"
    assert body["topic"] == "espresso basics"
    assert body["project_title"] == project.title
    assert [a["role"] for a in body["agents"]] == [
        "researcher",
        "writer",
        "editor",
        "publisher",
        "critic",
    ]


def test_run_detail_and_messages_scoped_to_owner(
    db, project, auth_client, auth_client2
):
    run = SwarmRun.objects.create(project=project, topic="t", status="completed")
    detail = auth_client.get(reverse("swarm-run-detail", args=[run.id]))
    assert detail.status_code == 200
    messages = auth_client.get(reverse("swarm-run-messages", args=[run.id]))
    assert messages.status_code == 200
    assert messages.json() == []
    # Another user's token cannot see it.
    assert (
        auth_client2.get(reverse("swarm-run-detail", args=[run.id])).status_code == 404
    )
    assert (
        auth_client2.get(reverse("swarm-run-messages", args=[run.id])).status_code
        == 404
    )


def test_create_run_rejects_other_users_project(db, project, auth_client2):
    response = auth_client2.post(
        reverse("swarm-runs"),
        {"project_id": str(project.id), "topic": "hijack"},
        format="json",
    )
    assert response.status_code == 404
    assert SwarmRun.objects.count() == 0


def test_cancel_running_run(db, project, auth_client):
    run = SwarmRun.objects.create(project=project, topic="t", status="running")
    response = auth_client.post(reverse("swarm-run-cancel", args=[run.id]))
    assert response.status_code == 200
    run.refresh_from_db()
    assert run.status == "cancelled"
    assert run.completed_at is not None


def test_cancel_completed_run_is_noop(db, project, auth_client):
    run = SwarmRun.objects.create(project=project, topic="t", status="completed")
    response = auth_client.post(reverse("swarm-run-cancel", args=[run.id]))
    assert response.status_code == 200
    run.refresh_from_db()
    assert run.status == "completed"


def test_messages_ordered_chronologically(db, project, auth_client, orchestrator):
    with patch("swarm.orchestrator.complete_text", side_effect=_mock_all_ok):
        run = orchestrator.start_run(project.id, "topic")

    response = auth_client.get(reverse("swarm-run-messages", args=[run.id]))
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == AgentMessage.objects.filter(swarm_run=run).count()
    created = [m["created_at"] for m in payload]
    assert created == sorted(created)
    first = payload[0]
    assert first["message_type"] == "task"
    assert first["from_agent"] is None  # system
    assert first["to_agent"]["role"] == "researcher"
