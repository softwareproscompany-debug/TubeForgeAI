"""Provider domain models: providers, models, generation jobs, usage, budgets."""
from core.models import UUIDModel, EncryptedSecret
from django.db import models
from projects.models import Asset, Project, Scene


class Provider(UUIDModel):
    ADAPTER_CHOICES = [
        ("comfyui", "ComfyUI"),
        ("local_inference", "Local inference"),
        ("external_api", "External API"),
    ]
    DEPLOYMENT_CHOICES = [
        ("local", "Local"),
        ("cloud_gpu", "Cloud GPU"),
        ("external", "External"),
    ]
    HEALTH_CHOICES = [
        ("UNKNOWN", "Unknown"), ("HEALTHY", "Healthy"),
        ("DEGRADED", "Degraded"), ("UNHEALTHY", "Unhealthy"),
    ]

    name = models.CharField(max_length=255, unique=True)
    adapter_type = models.CharField(max_length=32, choices=ADAPTER_CHOICES)
    deployment_type = models.CharField(max_length=16, choices=DEPLOYMENT_CHOICES, default="local")
    base_url = models.CharField(max_length=2000)
    secret_reference = models.ForeignKey(
        EncryptedSecret, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="providers",
    )
    capabilities = models.JSONField(default=dict)  # {task_types[], max_resolution, max_duration_s}
    enabled = models.BooleanField(default=True)
    priority = models.IntegerField(default=0)
    health_status = models.CharField(max_length=16, choices=HEALTH_CHOICES, default="UNKNOWN")
    configuration = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "name"]


class AIModel(UUIDModel):
    provider = models.ForeignKey(Provider, on_delete=models.CASCADE, related_name="models")
    model_identifier = models.CharField(max_length=255)
    model_version = models.CharField(max_length=64, blank=True, default="")
    task_type = models.CharField(max_length=32)
    hardware_requirements = models.JSONField(default=dict)  # {vram_gb}
    quality_profile = models.JSONField(default=dict)  # {rank, notes}
    license_metadata = models.JSONField(default=dict)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "model_identifier"], name="uniq_model_provider_identifier"
            ),
        ]
        ordering = ["model_identifier"]


class GenerationJob(UUIDModel):
    STATUS_CHOICES = [
        ("QUEUED", "Queued"), ("RUNNING", "Running"), ("COMPLETED", "Completed"),
        ("FAILED", "Failed"), ("CANCELED", "Canceled"),
    ]

    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="generation_jobs"
    )
    scene = models.ForeignKey(
        Scene, null=True, blank=True, on_delete=models.SET_NULL, related_name="generation_jobs"
    )
    provider = models.ForeignKey(Provider, on_delete=models.PROTECT, related_name="generation_jobs")
    model = models.ForeignKey(
        AIModel, null=True, blank=True, on_delete=models.SET_NULL, related_name="generation_jobs"
    )
    task_type = models.CharField(max_length=32)
    request_hash = models.CharField(max_length=64)
    request_metadata = models.JSONField(default=dict)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="QUEUED")
    external_job_id = models.CharField(max_length=255, null=True, blank=True)
    idempotency_key = models.CharField(max_length=128, unique=True)
    attempt_count = models.IntegerField(default=0)
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    resource_usage = models.JSONField(default=dict)
    error_code = models.CharField(max_length=64, blank=True, default="")
    error_message = models.TextField(blank=True, default="")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["request_hash"])]


class GenerationOutput(UUIDModel):
    job = models.ForeignKey(GenerationJob, on_delete=models.CASCADE, related_name="outputs")
    asset = models.ForeignKey(Asset, on_delete=models.CASCADE, related_name="generation_outputs")
    output_index = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)


class ResourceUsageEvent(UUIDModel):
    RESOURCE_CHOICES = [
        ("local_gpu_seconds", "Local GPU seconds"),
        ("cloud_gpu_seconds", "Cloud GPU seconds"),
        ("cpu_seconds", "CPU seconds"),
        ("ram_gb_seconds", "RAM GB seconds"),
        ("storage_gb", "Storage GB"),
        ("api_spend_usd", "API spend USD"),
        ("youtube_quota_units", "YouTube quota units"),
        ("render_seconds", "Render seconds"),
    ]

    provider = models.ForeignKey(
        Provider, null=True, blank=True, on_delete=models.SET_NULL, related_name="usage_events"
    )
    job = models.ForeignKey(
        GenerationJob, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="usage_events",
    )
    resource_type = models.CharField(max_length=32, choices=RESOURCE_CHOICES)
    quantity = models.DecimalField(max_digits=18, decimal_places=4)
    unit = models.CharField(max_length=32, default="")
    estimated_cost = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    actual_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        ordering = ["-occurred_at"]
        indexes = [models.Index(fields=["resource_type", "occurred_at"])]


class Budget(UUIDModel):
    SCOPE_CHOICES = [
        ("global", "Global"), ("channel", "Channel"),
        ("project", "Project"), ("workflow", "Workflow"),
    ]

    scope_type = models.CharField(max_length=16, choices=SCOPE_CHOICES)
    scope_id = models.UUIDField(null=True, blank=True)
    limits = models.JSONField(default=dict)  # {max_api_spend_daily, max_api_spend_monthly,
    #  max_spend_per_video, max_concurrent_gpu_jobs, max_storage_gb_per_project,
    #  max_retries_per_task, max_render_minutes, require_approval_for_paid_fallback}
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["scope_type", "scope_id"], name="uniq_budget_scope"),
        ]
