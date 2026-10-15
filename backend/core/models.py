"""Core domain models: identity, encrypted secrets, audit, notifications, settings."""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class UUIDModel(models.Model):
    """Shared abstract base: UUID primary key on every model."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class User(AbstractUser, UUIDModel):
    email = models.EmailField(unique=True)

    class Meta:
        pass

    def __str__(self):
        return self.username


class EncryptedSecret(UUIDModel):
    """A named secret owned by a user. The value is Fernet-encrypted bytes."""

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="secrets")
    name = models.CharField(max_length=255)
    encrypted_value = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["owner", "name"], name="uniq_secret_owner_name"
            ),
        )

    def __str__(self):
        return f"{self.owner}:{self.name}"


class AuditEvent(UUIDModel):
    """Immutable audit trail row. Metadata is scrubbed of secrets before write."""

    actor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100)
    resource_id = models.CharField(max_length=100)
    outcome = models.CharField(
        max_length=20, default="success"
    )  # success|failure|denied
    correlation_id = models.CharField(max_length=64, blank=True, default="")
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ("-occurred_at",)
        indexes = (
            models.Index(fields=["actor", "occurred_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        )


class Notification(UUIDModel):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=100)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True, default="")
    resource_type = models.CharField(max_length=100, blank=True, default="")
    resource_id = models.CharField(max_length=100, blank=True, default="")
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class SystemSetting(UUIDModel):
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_settings",
    )

    class Meta:
        ordering = ("key",)

    def __str__(self):
        return self.key
