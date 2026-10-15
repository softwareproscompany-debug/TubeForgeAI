"""Project domain models: projects, scripts, scenes, assets, timelines, renders."""

from django.db import models

from channels.models import Channel
from core.models import UUIDModel
from research.models import ContentIdea


class Project(UUIDModel):
    FORMAT_CHOICES = (
        ("LONG_FORM", "Long form"),
        ("SHORT", "Short"),
        ("DOCUMENTARY", "Documentary"),
        ("EXPLAINER", "Explainer"),
        ("CINEMATIC", "Cinematic"),
    )
    ASPECT_CHOICES = (("16:9", "16:9"), ("9:16", "9:16"), ("1:1", "1:1"))
    STATUS_CHOICES = (
        ("DRAFT", "Draft"),
        ("ACTIVE", "Active"),
        ("ARCHIVED", "Archived"),
    )

    channel = models.ForeignKey(
        Channel, on_delete=models.CASCADE, related_name="projects"
    )
    content_idea = models.ForeignKey(
        ContentIdea,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="projects",
    )
    title = models.CharField(max_length=500)
    brief = models.TextField(blank=True, default="")
    format = models.CharField(
        max_length=16, choices=FORMAT_CHOICES, default="LONG_FORM"
    )
    target_duration_seconds = models.IntegerField(default=600)
    aspect_ratio = models.CharField(
        max_length=8, choices=ASPECT_CHOICES, default="16:9"
    )
    language = models.CharField(max_length=16, default="en")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="DRAFT")
    current_workflow_id = models.CharField(max_length=100, null=True, blank=True)
    settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-updated_at",)


class ScriptVersion(UUIDModel):
    FACT_CHECK_CHOICES = (
        ("UNCHECKED", "Unchecked"),
        ("IN_REVIEW", "In review"),
        ("FLAGGED", "Flagged"),
        ("CLEARED", "Cleared"),
    )
    APPROVAL_CHOICES = (
        ("DRAFT", "Draft"),
        ("PENDING", "Pending"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="script_versions"
    )
    version_number = models.IntegerField()
    structured_script = models.JSONField(
        default=dict
    )  # blocks: [{id, kind, text, scene_refs}]
    rendered_text = models.TextField(blank=True, default="")
    fact_check_status = models.CharField(
        max_length=16, choices=FACT_CHECK_CHOICES, default="UNCHECKED"
    )
    approval_status = models.CharField(
        max_length=16, choices=APPROVAL_CHOICES, default="DRAFT"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["project", "version_number"], name="uniq_script_project_version"
            ),
        )
        ordering = ("-version_number",)


class Scene(UUIDModel):
    TYPE_CHOICES = (
        ("FACELESS", "Faceless"),
        ("CINEMATIC", "Cinematic"),
        ("STOCK", "Stock"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("GENERATING", "Generating"),
        ("READY", "Ready"),
        ("FAILED", "Failed"),
        ("APPROVED", "Approved"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="scenes"
    )
    position = models.IntegerField()
    script_segment = models.TextField(blank=True, default="")
    visual_prompt = models.TextField(blank=True, default="")
    negative_prompt = models.TextField(blank=True, default="")
    duration_seconds = models.FloatField(default=5.0)
    scene_type = models.CharField(
        max_length=16, choices=TYPE_CHOICES, default="FACELESS"
    )
    generation_settings = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["project", "position"], name="uniq_scene_project_position"
            ),
        )
        ordering = ("position",)


class Asset(UUIDModel):
    TYPE_CHOICES = (
        ("IMAGE", "Image"),
        ("VIDEO", "Video"),
        ("AUDIO", "Audio"),
        ("CAPTION", "Caption"),
        ("THUMBNAIL", "Thumbnail"),
        ("DOCUMENT", "Document"),
    )
    SOURCE_CHOICES = (
        ("GENERATED", "Generated"),
        ("UPLOADED", "Uploaded"),
        ("STOCK", "Stock"),
        ("BRAND", "Brand"),
    )
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("READY", "Ready"),
        ("FAILED", "Failed"),
        ("QUARANTINED", "Quarantined"),
    )

    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.CASCADE, related_name="assets"
    )
    scene = models.ForeignKey(
        Scene, null=True, blank=True, on_delete=models.SET_NULL, related_name="assets"
    )
    asset_type = models.CharField(max_length=16, choices=TYPE_CHOICES)
    object_key = models.CharField(max_length=1000)
    mime_type = models.CharField(max_length=128, blank=True, default="")
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True, default="")
    duration_seconds = models.FloatField(null=True, blank=True)
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    source_type = models.CharField(
        max_length=16, choices=SOURCE_CHOICES, default="GENERATED"
    )
    source_url = models.CharField(max_length=2000, null=True, blank=True)
    license_metadata = models.JSONField(default=dict)
    model_metadata = models.JSONField(
        default=dict
    )  # {provider, model, version, seed, settings}
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="PENDING")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)


class TimelineVersion(UUIDModel):
    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="timeline_versions"
    )
    version_number = models.IntegerField()
    timeline_json = models.JSONField(default=dict)
    render_settings = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=["project", "version_number"],
                name="uniq_timeline_project_version",
            ),
        )
        ordering = ("-version_number",)


class RenderJob(UUIDModel):
    STATUS_CHOICES = (
        ("QUEUED", "Queued"),
        ("RUNNING", "Running"),
        ("COMPLETED", "Completed"),
        ("FAILED", "Failed"),
        ("CANCELED", "Canceled"),
    )

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="render_jobs"
    )
    timeline_version = models.ForeignKey(
        TimelineVersion, on_delete=models.CASCADE, related_name="render_jobs"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="QUEUED")
    manifest = models.JSONField(null=True, blank=True)
    output_asset = models.ForeignKey(
        Asset,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="render_outputs",
    )
    error = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
