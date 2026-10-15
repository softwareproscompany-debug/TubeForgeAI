"""Workflow domain models: runs, events, approvals."""

from django.db import models

from core.models import User, UUIDModel
from projects.models import Project


class WorkflowRun(UUIDModel):
    TYPE_CHOICES = (
        ("VIDEO_PRODUCTION", "Video production"),
        ("SHORTS_BATCH", "Shorts batch"),
        ("PUBLISH_ONLY", "Publish only"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="workflow_runs"
    )
    workflow_type = models.CharField(
        max_length=32, choices=TYPE_CHOICES, default="VIDEO_PRODUCTION"
    )
    temporal_workflow_id = models.CharField(max_length=200, unique=True)
    status = models.CharField(max_length=32, default="DRAFT")
    current_stage = models.CharField(max_length=32, blank=True, default="")
    input_snapshot = models.JSONField(default=dict)
    output_summary = models.JSONField(default=dict)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class WorkflowEvent(UUIDModel):
    run = models.ForeignKey(
        WorkflowRun, on_delete=models.CASCADE, related_name="events"
    )
    event_type = models.CharField(max_length=64)
    stage = models.CharField(max_length=32, blank=True, default="")
    payload = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("occurred_at",)


class Approval(UUIDModel):
    TYPE_CHOICES = (
        ("SCRIPT", "Script"),
        ("VIDEO", "Video"),
        ("PUBLISH", "Publish"),
        ("PAID_FALLBACK", "Paid fallback"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
        ("EXPIRED", "Expired"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="approvals"
    )
    workflow_run = models.ForeignKey(
        WorkflowRun,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approvals",
    )
    approval_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    requested_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="requested_approvals"
    )
    decided_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_approvals",
    )
    decision_reason = models.TextField(blank=True, default="")
    requested_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-requested_at",)
