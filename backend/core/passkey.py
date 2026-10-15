"""Passkey (WebAuthn) registration and authentication views.

Challenges are stored server-side in Django's cache keyed by user id with a
5-minute TTL, so a client cannot replay or substitute its own challenge.
"""

import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from webauthn import (
    base64url_to_bytes,
    generate_authentication_options,
    generate_registration_options,
    options_to_json,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import PublicKeyCredentialDescriptor

from .models import User, WebAuthnCredential
from .serializers import UserSerializer, WebAuthnCredentialSerializer
from .utils import record_audit

logger = logging.getLogger(__name__)

_CHALLENGE_TTL_SECONDS = 300


def _rp_id():
    return settings.WEBAUTHN_RP_ID


def _rp_name():
    return settings.WEBAUTHN_RP_NAME


def _origin(request):
    """Expected WebAuthn origin: explicit env override, else request scheme+host."""
    configured = (getattr(settings, "WEBAUTHN_ORIGIN", "") or "").strip().rstrip("/")
    if configured:
        return configured
    scheme = "https" if request.is_secure() else "http"
    return f"{scheme}://{request.get_host()}"


def _register_challenge_key(user):
    return f"webauthn:register-challenge:{user.pk}"


def _auth_challenge_key(user):
    return f"webauthn:auth-challenge:{user.pk}"


def _take_challenge(cache_key):
    """Pop the stored challenge; ``None`` when missing/expired."""
    challenge = cache.get(cache_key)
    if challenge is not None:
        cache.delete(cache_key)
    return challenge


def _options_response(options):
    return Response(json.loads(options_to_json(options)))


def _credential_id_from_response(credential_data):
    """Normalize the raw credential id in an assertion response to base64url."""
    raw_id = credential_data.get("id", "") if isinstance(credential_data, dict) else ""
    try:
        return bytes_to_base64url(base64url_to_bytes(raw_id))
    except Exception as exc:
        raise ValidationError("Malformed credential id.") from exc


def _stored_descriptors(user):
    return [
        PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id))
        for cred in user.webauthn_credentials.all()
    ]


# ---------------------------------------------------------------------------
# Registration (authenticated)
# ---------------------------------------------------------------------------
class PasskeyRegisterBeginView(APIView):
    """Return PublicKeyCredentialCreationOptions for registering a new passkey."""

    def post(self, request):
        options = generate_registration_options(
            rp_id=_rp_id(),
            rp_name=_rp_name(),
            user_id=str(request.user.pk).encode("utf-8"),
            user_name=request.user.username,
            user_display_name=request.user.get_full_name() or request.user.username,
            exclude_credentials=_stored_descriptors(request.user),
        )
        cache.set(
            _register_challenge_key(request.user),
            options.challenge,
            timeout=_CHALLENGE_TTL_SECONDS,
        )
        return _options_response(options)


class PasskeyRegisterFinishView(APIView):
    """Verify the attestation response and store the new credential.

    Body: ``{"credential": <registration response JSON>, "name": "optional label"}``.
    """

    def post(self, request):
        credential_data = request.data.get("credential")
        if not credential_data:
            raise ValidationError({"credential": "This field is required."})
        challenge = _take_challenge(_register_challenge_key(request.user))
        if challenge is None:
            raise ValidationError(
                "Registration session expired. Start again with register/begin."
            )
        try:
            verification = verify_registration_response(
                credential=credential_data,
                expected_challenge=challenge,
                expected_rp_id=_rp_id(),
                expected_origin=_origin(request),
            )
        except Exception as exc:  # noqa: BLE001 - webauthn raises many error types
            logger.warning("Passkey registration failed for %s: %s", request.user, exc)
            raise ValidationError("Passkey registration failed verification.")
        credential = WebAuthnCredential.objects.create(
            user=request.user,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes(verification.credential_public_key),
            sign_count=verification.sign_count,
            name=str(request.data.get("name") or "Passkey")[:255],
        )
        record_audit(
            request.user,
            "auth.passkey_register",
            "webauthn_credential",
            str(credential.id),
            request=request,
        )
        return Response(
            WebAuthnCredentialSerializer(credential).data,
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Authentication (unauthenticated)
# ---------------------------------------------------------------------------
class PasskeyAuthenticateBeginView(APIView):
    """Return PublicKeyCredentialRequestOptions for a passkey login.

    Body: ``{"username": "<username>"}``.
    """

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        username = request.data.get("username", "")
        user = get_object_or_404(User, username=username)
        credentials = list(user.webauthn_credentials.all())
        options = generate_authentication_options(
            rp_id=_rp_id(),
            allow_credentials=[
                PublicKeyCredentialDescriptor(id=base64url_to_bytes(cred.credential_id))
                for cred in credentials
            ],
        )
        cache.set(
            _auth_challenge_key(user), options.challenge, timeout=_CHALLENGE_TTL_SECONDS
        )
        body = _options_response(options).data
        return Response(
            {
                "options": body,
                "username": user.username,
                "credential_ids": [cred.credential_id for cred in credentials],
            }
        )


class PasskeyAuthenticateFinishView(APIView):
    """Verify the assertion response and return an auth token.

    Body: ``{"username": "<username>", "credential": <assertion response JSON>}``.
    """

    permission_classes = (permissions.AllowAny,)

    def post(self, request):
        username = request.data.get("username", "")
        credential_data = request.data.get("credential")
        if not credential_data:
            raise ValidationError({"credential": "This field is required."})
        user = get_object_or_404(User, username=username)
        challenge = _take_challenge(_auth_challenge_key(user))
        if challenge is None:
            raise ValidationError(
                "Authentication session expired. Start again with authenticate/begin."
            )
        credential_id = _credential_id_from_response(credential_data)
        stored = WebAuthnCredential.objects.filter(
            user=user, credential_id=credential_id
        ).first()
        if stored is None:
            raise ValidationError("Unknown credential for this user.")
        try:
            verification = verify_authentication_response(
                credential=credential_data,
                expected_challenge=challenge,
                expected_rp_id=_rp_id(),
                expected_origin=_origin(request),
                credential_public_key=bytes(stored.public_key),
                credential_current_sign_count=stored.sign_count,
            )
        except Exception as exc:  # noqa: BLE001 - webauthn raises many error types
            logger.warning("Passkey authentication failed for %s: %s", username, exc)
            record_audit(
                None,
                "auth.passkey_login",
                "user",
                username,
                outcome="failure",
                request=request,
            )
            raise ValidationError("Passkey authentication failed verification.")
        stored.sign_count = verification.new_sign_count
        stored.save(update_fields=["sign_count"])
        token, _ = Token.objects.get_or_create(user=user)
        record_audit(user, "auth.passkey_login", "user", str(user.id), request=request)
        return Response({"token": token.key, "user": UserSerializer(user).data})
