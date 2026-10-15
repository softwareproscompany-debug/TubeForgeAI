"""Security tests: owner scoping, secret redaction, OAuth state integrity,
audit scrubbing."""

import time
from unittest import mock

import pytest

from channels.views import STATE_MAX_AGE_SECONDS, _signer
from core.models import AuditEvent
from core.secrets import encrypt_value
from core.utils import record_audit


@pytest.mark.django_db
def test_cross_owner_channel_access_denied(auth_client2, channel):
    response = auth_client2.get(f"/api/v1/channels/{channel.id}")
    assert response.status_code == 404


@pytest.mark.django_db
def test_cross_owner_project_access_denied(auth_client2, project):
    response = auth_client2.get(f"/api/v1/projects/{project.id}")
    assert response.status_code == 404


@pytest.mark.django_db
def test_cross_owner_idea_promotion_denied(auth_client, auth_client2, channel):
    from research.models import ContentIdea

    idea = ContentIdea.objects.create(channel=channel, title="Secret idea")
    response = auth_client2.post(f"/api/v1/ideas/{idea.id}/create-project")
    assert response.status_code == 404


@pytest.mark.django_db
def test_secrets_redacted_in_provider_responses(auth_client, user):
    from core.models import EncryptedSecret
    from providers.models import Provider

    plaintext = "super-secret-provider-key"
    secret = EncryptedSecret.objects.create(
        owner=user, name="render-api-key", encrypted_value=encrypt_value(plaintext)
    )
    provider = Provider.objects.create(
        name="secret-box",
        adapter_type="external_api",
        deployment_type="external",
        base_url="https://api.example.com",
        secret_reference=secret,
        capabilities={"task_types": ["image"]},
    )
    response = auth_client.get(f"/api/v1/providers/{provider.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["secret_reference"] == {"id": str(secret.id), "masked": True}
    assert plaintext not in response.content.decode()


@pytest.mark.django_db
def test_oauth_state_tampering_rejected(auth_client):
    connect = auth_client.post("/api/v1/channels/connect", {"title": "OAuth test"})
    assert connect.status_code == 201
    channel_id = connect.json()["channel_id"]
    state = connect.json()["state"]
    tampered = state[:-2] + ("ab" if not state.endswith("ab") else "cd")
    callback = auth_client.get(
        f"/api/v1/channels/{channel_id}/oauth/callback",
        {"code": "fake-code", "state": tampered},
    )
    assert callback.status_code == 400
    assert callback.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_oauth_state_expiry_rejected(auth_client):
    connect = auth_client.post("/api/v1/channels/connect", {"title": "OAuth expiry"})
    assert connect.status_code == 201
    channel_id = connect.json()["channel_id"]
    # Sign a state token in the past so it is genuinely older than the max
    # age; the callback must reject it as expired (not merely mismatched).
    past = time.time() - (STATE_MAX_AGE_SECONDS + 60)
    with mock.patch("django.core.signing.time") as mock_time:
        mock_time.time.return_value = past
        mock_time.return_value = past  # covers `from time import time` style too
        expired_state = _signer.sign(channel_id)
    callback = auth_client.get(
        f"/api/v1/channels/{channel_id}/oauth/callback",
        {"code": "fake-code", "state": expired_state},
    )
    assert callback.status_code == 400
    assert callback.json()["error"]["code"] == "validation_error"


@pytest.mark.django_db
def test_audit_written_without_secrets(user):
    record_audit(
        user,
        "test.action",
        "secret",
        "1",
        metadata={
            "api_password": "hunter2",
            "nested": {"access_token": "tok-abc", "note": "hello"},
            "items": [{"client_secret": "shh"}],
        },
    )
    event = AuditEvent.objects.get(action="test.action")
    assert event.metadata["api_password"] == "***REDACTED***"
    assert event.metadata["nested"]["access_token"] == "***REDACTED***"
    assert event.metadata["nested"]["note"] == "hello"
    assert event.metadata["items"][0]["client_secret"] == "***REDACTED***"
    blob = str(event.metadata)
    assert "hunter2" not in blob and "tok-abc" not in blob and "shh" not in blob


@pytest.mark.django_db
def test_error_envelope_shape(auth_client):
    response = auth_client.get("/api/v1/channels/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
    error = response.json()["error"]
    assert set(error) == {"code", "message", "retryable", "correlation_id"}
    assert error["code"] == "not_found"
    assert error["retryable"] is False
    assert response["X-Correlation-ID"] == error["correlation_id"]
