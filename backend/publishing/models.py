"""Publishing domain models: publication jobs and analytics snapshots."""

from django.db import models

from channels.models import Channel
from core.models import UUIDModel
from projects.models import Asset, Project


class PublicationJob(UUIDModel):
    VISIBILITY_CHOICES = (
        ("private", "Private"),
        ("unlisted", "Unlisted"),
        ("public", "Public"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="publications"
    )
    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="publications"
    )
    asset = models.ForeignKey(
        Asset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="publications",
    )
    youtube_video_id = models.CharField(max_length=32, null=True, blank=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    tags = models.JSONField(default=list)
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default="private"
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=32, default="DRAFT")
    upload_session_reference = models.CharField(max_length=500, null=True, blank=True)
    attempt_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True, default="")
    published_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)


class AnalyticsSnapshot(UUIDModel):
    SOURCE_CHOICES = (
        ("YOUTUBE_API", "YouTube API"),
        ("CALCULATED", "Calculated"),
        ("AI_INTERPRETATION", "AI interpretation"),
        ("FORECAST", "Forecast"),
    )

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="analytics"
    )
    youtube_video_id = models.CharField(max_length=32)
    captured_at = models.DateTimeField(auto_now_add=True)
    metrics = models.JSONField(default=dict)
    source = models.CharField(
        max_length=32, choices=SOURCE_CHOICES, default="YOUTUBE_API"
    )

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["channel", "youtube_video_id", "captured_at"],
                name="uniq_analytics_channel_video_captured",
            ),
        )
        ordering = ("-captured_at",)
