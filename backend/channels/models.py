"""Channel domain models: YouTube channel linkage, OAuth credentials, automation rules."""

from django.db import models

from core.models import User, UUIDModel


class Channel(UUIDModel):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="channels")
    youtube_channel_id = models.CharField(
        max_length=64, null=True, blank=True, default=None
    )
    title = models.CharField(max_length=255, default="")
    description = models.TextField(blank=True, default="")
    default_language = models.CharField(max_length=16, default="en")
    timezone = models.CharField(max_length=64, default="UTC")
    brand_config = models.JSONField(default=dict)
    automation_config = models.JSONField(default=dict)
    publishing_policy = models.JSONField(default=dict)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["owner", "youtube_channel_id"],
                name="uniq_channel_owner_youtube",
            ),
        )
        ordering = ("-created_at",)

    def __str__(self):
        return self.title or str(self.id)


class ChannelCredential(UUIDModel):
    """OAuth credential for a channel. Only the refresh token is stored, encrypted."""

    channel = models.OneToOneField(
        Channel, on_delete=models.CASCADE, related_name="credential"
    )
    provider = models.CharField(max_length=32, default="google")
    encrypted_refresh_token = models.BinaryField()
    granted_scopes = models.JSONField(default=list)
    expires_at = models.DateTimeField(null=True, blank=True)
    last_validated_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class AutomationRule(UUIDModel):
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="automation_rules"
    )
    name = models.CharField(max_length=255)
    trigger_type = models.CharField(max_length=64)
    conditions = models.JSONField(default=dict)
    actions = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name",)
