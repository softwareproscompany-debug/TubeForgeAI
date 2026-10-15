"""Auth phase 1 tests: registration, password reset, passkey/WebAuthn flows."""

import logging
from unittest import mock

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient

from core.models import User, WebAuthnCredential

REGISTER_URL = "/api/v1/auth/register"
RESET_REQUEST_URL = "/api/v1/auth/password-reset/request"
RESET_CONFIRM_URL = "/api/v1/auth/password-reset/confirm"
PK_REG_BEGIN = "/api/v1/auth/passkey/register/begin"
PK_REG_FINISH = "/api/v1/auth/passkey/register/finish"
PK_AUTH_BEGIN = "/api/v1/auth/passkey/authenticate/begin"
PK_AUTH_FINISH = "/api/v1/auth/passkey/authenticate/finish"


def _reset_pair(user):
    token = PasswordResetTokenGenerator().make_token(user)
    uidb64 = urlsafe_base64_encode(force_bytes(str(user.pk)))
    return uidb64, token


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_register_success():
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "supersecurepassword123",
        },
        format="json",
    )
    assert response.status_code == 201
    body = response.json()
    assert body.get("token")
    assert body["user"]["username"] == "newuser"
    assert body["user"]["id"] == str(User.objects.get(username="newuser").pk)
    assert "password" not in body["user"]


@pytest.mark.django_db
def test_register_duplicate_username(user):
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {
            "username": user.username,
            "email": "other@example.com",
            "password": "supersecurepassword123",
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_duplicate_email(user):
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {
            "username": "someoneelse",
            "email": user.email,
            "password": "supersecurepassword123",
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_register_weak_password_rejected():
    client = APIClient()
    response = client.post(
        REGISTER_URL,
        {"username": "weakuser", "email": "weak@example.com", "password": "short"},
        format="json",
    )
    assert response.status_code == 400
    assert not User.objects.filter(username="weakuser").exists()


@pytest.mark.django_db
def test_registered_user_can_login():
    client = APIClient()
    client.post(
        REGISTER_URL,
        {
            "username": "loginme",
            "email": "loginme@example.com",
            "password": "supersecurepassword123",
        },
        format="json",
    )
    response = client.post(
        "/api/v1/auth/login",
        {"username": "loginme", "password": "supersecurepassword123"},
        format="json",
    )
    assert response.status_code == 200
    assert "token" in response.json()


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_password_reset_request_always_200(user, caplog):
    client = APIClient()
    with caplog.at_level(logging.INFO, logger="core.views"):
        response = client.post(RESET_REQUEST_URL, {"email": user.email}, format="json")
    assert response.status_code == 200
    assert "uidb64=" in caplog.text  # token logged for the real user


@pytest.mark.django_db
def test_password_reset_request_unknown_email_still_200():
    client = APIClient()
    response = client.post(
        RESET_REQUEST_URL, {"email": "nobody@example.com"}, format="json"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_password_reset_confirm_valid_token(user):
    client = APIClient()
    uidb64, token = _reset_pair(user)
    response = client.post(
        RESET_CONFIRM_URL,
        {
            "uidb64": uidb64,
            "token": token,
            "new_password": "brandnewsecurepassword123",
        },
        format="json",
    )
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.check_password("brandnewsecurepassword123")


@pytest.mark.django_db
def test_password_reset_confirm_invalid_token(user):
    client = APIClient()
    uidb64, _ = _reset_pair(user)
    response = client.post(
        RESET_CONFIRM_URL,
        {
            "uidb64": uidb64,
            "token": "bogus-token",
            "new_password": "brandnewsecurepassword123",
        },
        format="json",
    )
    assert response.status_code == 400
    user.refresh_from_db()
    assert not user.check_password("brandnewsecurepassword123")


@pytest.mark.django_db
def test_password_reset_confirm_weak_new_password_rejected(user):
    client = APIClient()
    uidb64, token = _reset_pair(user)
    response = client.post(
        RESET_CONFIRM_URL,
        {"uidb64": uidb64, "token": token, "new_password": "short"},
        format="json",
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Passkey registration
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_passkey_register_begin_returns_options(auth_client, user):
    response = auth_client.post(PK_REG_BEGIN, {}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["challenge"]
    assert body["rp"]["name"] == "TubeForge AI"
    assert body["user"]["name"] == user.username


@pytest.mark.django_db
def test_passkey_register_begin_requires_auth():
    client = APIClient()
    response = client.post(PK_REG_BEGIN, {}, format="json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_passkey_register_finish_invalid_attestation_rejected(auth_client):
    auth_client.post(PK_REG_BEGIN, {}, format="json")
    response = auth_client.post(
        PK_REG_FINISH,
        {"credential": {"id": "bogus", "type": "public-key"}, "name": "My key"},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_passkey_register_finish_without_begin_rejected(auth_client):
    response = auth_client.post(
        PK_REG_FINISH,
        {"credential": {"id": "bogus", "type": "public-key"}},
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_passkey_register_full_ceremony_mocked(auth_client, user):
    from webauthn.helpers import bytes_to_base64url

    begin = auth_client.post(PK_REG_BEGIN, {}, format="json")
    assert begin.status_code == 200

    fake_credential_id = b"fake-credential-id-123"
    fake_public_key = b"fake-cose-public-key-bytes"
    verification = mock.Mock()
    verification.credential_id = fake_credential_id
    verification.credential_public_key = fake_public_key
    verification.sign_count = 0

    with mock.patch(
        "core.passkey.verify_registration_response", return_value=verification
    ):
        response = auth_client.post(
            PK_REG_FINISH,
            {
                "credential": {
                    "id": bytes_to_base64url(fake_credential_id),
                    "rawId": bytes_to_base64url(fake_credential_id),
                    "type": "public-key",
                    "response": {},
                },
                "name": "My laptop key",
            },
            format="json",
        )
    assert response.status_code == 201
    body = response.json()
    assert body["credential_id"] == bytes_to_base64url(fake_credential_id)
    assert body["name"] == "My laptop key"

    stored = WebAuthnCredential.objects.get(user=user)
    assert stored.credential_id == bytes_to_base64url(fake_credential_id)
    assert bytes(stored.public_key) == fake_public_key
    assert stored.sign_count == 0


# ---------------------------------------------------------------------------
# Passkey authentication
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_passkey_authenticate_begin_unknown_user_404():
    client = APIClient()
    response = client.post(PK_AUTH_BEGIN, {"username": "ghost-user"}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_passkey_authenticate_begin_returns_options_and_ids(user):
    from webauthn.helpers import bytes_to_base64url

    WebAuthnCredential.objects.create(
        user=user,
        credential_id=bytes_to_base64url(b"stored-credential-id"),
        public_key=b"stored-public-key",
        sign_count=5,
        name="Phone",
    )
    client = APIClient()
    response = client.post(PK_AUTH_BEGIN, {"username": user.username}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["options"]["challenge"]
    assert body["username"] == user.username
    assert body["credential_ids"] == [bytes_to_base64url(b"stored-credential-id")]
    allow = body["options"]["allowCredentials"]
    assert len(allow) == 1
    assert allow[0]["id"] == bytes_to_base64url(b"stored-credential-id")


@pytest.mark.django_db
def test_passkey_authenticate_finish_full_ceremony_mocked(user):
    from webauthn.helpers import bytes_to_base64url

    credential_id_b64 = bytes_to_base64url(b"auth-credential-id")
    WebAuthnCredential.objects.create(
        user=user,
        credential_id=credential_id_b64,
        public_key=b"auth-public-key",
        sign_count=5,
        name="Phone",
    )
    client = APIClient()
    begin = client.post(PK_AUTH_BEGIN, {"username": user.username}, format="json")
    assert begin.status_code == 200

    verification = mock.Mock()
    verification.new_sign_count = 6

    with mock.patch(
        "core.passkey.verify_authentication_response", return_value=verification
    ):
        response = client.post(
            PK_AUTH_FINISH,
            {
                "username": user.username,
                "credential": {
                    "id": credential_id_b64,
                    "rawId": credential_id_b64,
                    "type": "public-key",
                    "response": {},
                },
            },
            format="json",
        )
    assert response.status_code == 200
    body = response.json()
    assert body.get("token")
    assert body["user"]["username"] == user.username

    stored = WebAuthnCredential.objects.get(user=user)
    assert stored.sign_count == 6


@pytest.mark.django_db
def test_passkey_authenticate_finish_unknown_credential_rejected(user):
    client = APIClient()
    client.post(PK_AUTH_BEGIN, {"username": user.username}, format="json")
    response = client.post(
        PK_AUTH_FINISH,
        {
            "username": user.username,
            "credential": {"id": "dW5rbm93bg", "type": "public-key"},
        },
        format="json",
    )
    assert response.status_code == 400


@pytest.mark.django_db
def test_passkey_authenticate_finish_without_begin_rejected(user):
    from webauthn.helpers import bytes_to_base64url

    WebAuthnCredential.objects.create(
        user=user,
        credential_id=bytes_to_base64url(b"auth-credential-id"),
        public_key=b"auth-public-key",
        sign_count=5,
    )
    client = APIClient()
    response = client.post(
        PK_AUTH_FINISH,
        {
            "username": user.username,
            "credential": {
                "id": bytes_to_base64url(b"auth-credential-id"),
                "type": "public-key",
            },
        },
        format="json",
    )
    assert response.status_code == 400
