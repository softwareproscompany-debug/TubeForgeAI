"""Channel views: CRUD, YouTube OAuth connect/callback/disconnect/validate, settings, rules."""
from datetime import timedelta

from core.secrets import decrypt_value, encrypt_value
from core.utils import IsOwner, UpstreamError, record_audit
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db import IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from publishing import youtube as yt
from rest_framework import generics, permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AutomationRule, Channel, ChannelCredential
from .serializers import (
    AutomationRuleSerializer,
    ChannelCredentialSerializer,
    ChannelSerializer,
    ChannelSettingsSerializer,
)

_signer = TimestampSigner(salt="tubeforge-channel-oauth")
STATE_MAX_AGE_SECONDS = 900  # OAuth state tokens expire after 15 minutes.


def _get_owned_channel(user, pk):
    return get_object_or_404(Channel.objects.select_related("owner"), pk=pk, owner=user)


class ChannelViewSet(viewsets.ModelViewSet):
    serializer_class = ChannelSerializer
    permission_classes = [permissions.IsAuthenticated, IsOwner]

    def get_queryset(self):
        return Channel.objects.filter(owner=self.request.user).select_related("owner")

    def perform_create(self, serializer):
        channel = serializer.save(owner=self.request.user)
        record_audit(
            self.request.user, "channel.create", "channel", str(channel.id),
            request=self.request,
        )

    def perform_update(self, serializer):
        channel = serializer.save()
        record_audit(
            self.request.user, "channel.update", "channel", str(channel.id),
            request=self.request,
        )

    def perform_destroy(self, instance):
        record_audit(
            self.request.user, "channel.delete", "channel", str(instance.id),
            request=self.request,
        )
        instance.delete()


class ChannelConnectView(APIView):
    """Start YouTube OAuth: create a draft channel row, return the authorization URL."""

    def post(self, request):
        channel = Channel.objects.create(
            owner=request.user,
            title=request.data.get("title", "Untitled channel"),
            description=request.data.get("description", ""),
            default_language=request.data.get("default_language", "en"),
            timezone=request.data.get("timezone", "UTC"),
            youtube_channel_id=None,
            is_active=False,
        )
        state = _signer.sign(str(channel.id))
        authorization_url = yt.build_authorization_url(state)
        record_audit(
            request.user, "channel.oauth_start", "channel", str(channel.id), request=request,
        )
        return Response(
            {
                "channel_id": str(channel.id),
                "authorization_url": authorization_url,
                "state": state,
            },
            status=status.HTTP_201_CREATED,
        )


class ChannelOAuthCallbackView(APIView):
    """OAuth callback: validate signed state, exchange code, store encrypted token.

    Never accepts or stores a Google password — only the OAuth authorization code.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, pk):
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            raise ValidationError({"detail": "Missing 'code' or 'state' query parameter."})
        try:
            channel_id = _signer.unsign(state, max_age=STATE_MAX_AGE_SECONDS)
        except SignatureExpired:
            raise ValidationError({"state": "OAuth state expired. Restart the connect flow."})
        except BadSignature:
            raise ValidationError({"state": "OAuth state signature invalid."})
        if str(pk) != str(channel_id):
            raise ValidationError({"state": "OAuth state does not match this channel."})

        channel = get_object_or_404(Channel, pk=channel_id)
        try:
            tokens = yt.exchange_code(code)
        except yt.YouTubeError as exc:
            raise UpstreamError(f"Google token exchange failed: {exc}") from exc

        refresh_token = tokens.get("refresh_token")
        if not refresh_token:
            raise ValidationError(
                {"detail": "Google did not return a refresh token. Reconnect with consent."}
            )
        expires_in = int(tokens.get("expires_in") or 3600)
        try:
            info = yt.get_channel_info(tokens["access_token"])
        except yt.YouTubeError as exc:
            raise UpstreamError(f"Could not read YouTube channel info: {exc}") from exc

        ChannelCredential.objects.update_or_create(
            channel=channel,
            defaults={
                "provider": "google",
                "encrypted_refresh_token": encrypt_value(refresh_token),
                "granted_scopes": (tokens.get("scope") or "").split(),
                "expires_at": timezone.now() + timedelta(seconds=expires_in),
                "last_validated_at": timezone.now(),
                "revoked_at": None,
            },
        )
        channel.youtube_channel_id = info.get("id")
        channel.title = info.get("title") or channel.title
        channel.is_active = True
        try:
            channel.save()
        except IntegrityError as exc:
            raise ValidationError(
                {"detail": "This YouTube channel is already connected to your account."}
            ) from exc
        record_audit(
            channel.owner, "channel.oauth_complete", "channel", str(channel.id),
            metadata={"youtube_channel_id": channel.youtube_channel_id},
        )
        return Response(ChannelSerializer(channel).data)


class ChannelDisconnectView(APIView):
    """Revoke the Google token, clear stored ciphertext, mark revoked."""

    def post(self, request, pk):
        channel = _get_owned_channel(request.user, pk)
        credential = getattr(channel, "credential", None)
        if credential is not None:
            try:
                raw = bytes(credential.encrypted_refresh_token or b"")
                if raw:
                    yt.revoke(decrypt_value(raw))
            except yt.YouTubeError:
                pass  # revocation best-effort; local state is still cleared
            credential.encrypted_refresh_token = b""
            credential.revoked_at = timezone.now()
            credential.save(update_fields=["encrypted_refresh_token", "revoked_at", "updated_at"])
        channel.is_active = False
        channel.save(update_fields=["is_active", "updated_at"])
        record_audit(
            request.user, "channel.disconnect", "channel", str(channel.id), request=request,
        )
        return Response({"detail": "Channel disconnected."})


class ChannelValidateView(APIView):
    """Validate the stored credential by refreshing the access token."""

    def post(self, request, pk):
        channel = _get_owned_channel(request.user, pk)
        credential = getattr(channel, "credential", None)
        raw = bytes(getattr(credential, "encrypted_refresh_token", None) or b"")
        if credential is None or not raw or credential.revoked_at:
            return Response({"valid": False, "reason": "no_active_credential"})
        try:
            tokens = yt.refresh_access_token(decrypt_value(raw))
        except yt.YouTubeError as exc:
            return Response({"valid": False, "reason": str(exc)[:200]})
        credential.expires_at = timezone.now() + timedelta(seconds=int(tokens.get("expires_in") or 3600))
        credential.last_validated_at = timezone.now()
        credential.save(update_fields=["expires_at", "last_validated_at", "updated_at"])
        return Response(
            {
                "valid": True,
                "credential": ChannelCredentialSerializer(credential).data,
            }
        )


class ChannelSettingsView(APIView):
    """Brand / automation / publishing sub-resources of a channel."""

    def get(self, request, pk):
        channel = _get_owned_channel(request.user, pk)
        return Response(
            {
                "brand_config": channel.brand_config,
                "automation_config": channel.automation_config,
                "publishing_policy": channel.publishing_policy,
            }
        )

    def patch(self, request, pk):
        channel = _get_owned_channel(request.user, pk)
        serializer = ChannelSettingsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(channel, field, value)
        channel.save()
        record_audit(
            request.user, "channel.settings_update", "channel", str(channel.id),
            request=request, metadata={"fields": list(serializer.validated_data)},
        )
        return Response(ChannelSerializer(channel).data)


class AutomationRuleViewSet(viewsets.ModelViewSet):
    serializer_class = AutomationRuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def _channel(self):
        return _get_owned_channel(self.request.user, self.kwargs["channel_pk"])

    def get_queryset(self):
        return AutomationRule.objects.filter(channel=self._channel()).select_related("channel")

    def perform_create(self, serializer):
        rule = serializer.save(channel=self._channel())
        record_audit(
            self.request.user, "automation_rule.create", "automation_rule", str(rule.id),
            request=self.request,
        )

    def perform_update(self, serializer):
        rule = serializer.save()
        record_audit(
            self.request.user, "automation_rule.update", "automation_rule", str(rule.id),
            request=self.request,
        )

    def perform_destroy(self, instance):
        record_audit(
            self.request.user, "automation_rule.delete", "automation_rule", str(instance.id),
            request=self.request,
        )
        instance.delete()
