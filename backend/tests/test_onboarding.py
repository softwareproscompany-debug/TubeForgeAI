"""Onboarding progress API tests."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from onboarding.models import OnboardingProgress

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="onboarder", email="onboard@example.com", password="pass12345"
    )


@pytest.fixture
def client(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def test_progress_lazy_create(client, user):
    """First GET creates the progress row at the welcome step."""
    resp = client.get("/api/v1/onboarding/progress")
    assert resp.status_code == 200
    assert resp.data["current_step"] == "welcome"
    assert resp.data["completed_steps"] == []
    assert resp.data["is_complete"] is False
    assert OnboardingProgress.objects.filter(user=user).exists()


def test_complete_step_advances(client):
    resp = client.post(
        "/api/v1/onboarding/complete-step", {"step": "welcome"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["current_step"] == "youtube"
    assert resp.data["completed_steps"] == ["welcome"]

    resp = client.post(
        "/api/v1/onboarding/complete-step", {"step": "youtube"}, format="json"
    )
    assert resp.data["current_step"] == "channel_setup"


def test_complete_all_steps_marks_complete(client):
    for step in ("welcome", "youtube", "channel_setup", "first_project"):
        resp = client.post(
            "/api/v1/onboarding/complete-step", {"step": step}, format="json"
        )
        assert resp.status_code == 200
    assert resp.data["is_complete"] is True
    assert resp.data["completed_at"] is not None


def test_complete_step_idempotent(client):
    client.post("/api/v1/onboarding/complete-step", {"step": "welcome"}, format="json")
    resp = client.post(
        "/api/v1/onboarding/complete-step", {"step": "welcome"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.data["completed_steps"] == ["welcome"]
    assert resp.data["current_step"] == "youtube"


def test_complete_step_invalid_rejected(client):
    resp = client.post(
        "/api/v1/onboarding/complete-step", {"step": "bogus"}, format="json"
    )
    assert resp.status_code == 400


def test_skip_marks_complete(client):
    resp = client.post("/api/v1/onboarding/skip")
    assert resp.status_code == 200
    assert resp.data["skipped"] is True
    assert resp.data["is_complete"] is True


def test_reset_restarts_wizard(client):
    client.post("/api/v1/onboarding/complete-step", {"step": "welcome"}, format="json")
    resp = client.post("/api/v1/onboarding/reset")
    assert resp.status_code == 200
    assert resp.data["current_step"] == "welcome"
    assert resp.data["completed_steps"] == []
    assert resp.data["skipped"] is False
    assert resp.data["is_complete"] is False


def test_unauthenticated_rejected(db):
    c = APIClient()
    assert c.get("/api/v1/onboarding/progress").status_code in (401, 403)
    assert c.post(
        "/api/v1/onboarding/complete-step", {"step": "welcome"}
    ).status_code in (401, 403)
