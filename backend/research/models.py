"""Research domain models: runs, evidence sources, content ideas."""
from channels.models import Channel
from core.models import UUIDModel
from django.db import models
from django.utils import timezone


class ResearchRun(UUIDModel):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("RUNNING", "Running"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELED", "Canceled"),
    ]

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="research_runs")
    query = models.CharField(max_length=500)
    parameters = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class ResearchSource(UUIDModel):
    run = models.ForeignKey(ResearchRun, on_delete=models.CASCADE, related_name="sources")
    source_type = models.CharField(max_length=64)
    source_url = models.CharField(max_length=2000, blank=True, default="")
    title = models.CharField(max_length=500)
    retrieved_at = models.DateTimeField(default=timezone.now)
    published_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, blank=True, default="")
    license_metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["title"]


class ContentIdea(UUIDModel):
    STATUS_CHOICES = [
        ("NEW", "New"),
        ("QUEUED", "Queued"),
        ("IN_PROJECT", "In project"),
        ("DISMISSED", "Dismissed"),
    ]

    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="ideas")
    title = models.CharField(max_length=500)
    topic = models.CharField(max_length=500, blank=True, default="")
    format = models.CharField(max_length=32, default="LONG_FORM")
    priority = models.IntegerField(default=0)
    confidence_score = models.FloatField(default=0.5)
    supporting_evidence = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="NEW")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["channel", "title"], name="uniq_idea_channel_title"),
        ]
        ordering = ["-priority", "-created_at"]
