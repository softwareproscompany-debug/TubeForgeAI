"""Provider serializers. Secrets are never exposed: secret_reference renders as a
masked id only, and accepts a write-only UUID on input."""

from rest_framework import serializers

from core.models import EncryptedSecret

from .models import (
    AIModel,
    Budget,
    GenerationJob,
    GenerationOutput,
    Provider,
    ResourceUsageEvent,
)


class ProviderSerializer(serializers.ModelSerializer):
    secret_reference = serializers.SerializerMethodField()
    secret_reference_id = serializers.UUIDField(
        write_only=True, required=False, allow_null=True
    )

    class Meta:
        model = Provider
        fields = (
            "id",
            "name",
            "adapter_type",
            "deployment_type",
            "base_url",
            "secret_reference",
            "secret_reference_id",
            "capabilities",
            "enabled",
            "priority",
            "health_status",
            "configuration",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "health_status", "created_at", "updated_at")

    def get_secret_reference(self, obj):
        if obj.secret_reference_id:
            return {"id": str(obj.secret_reference_id), "masked": True}
        return None

    def _resolve_secret(self, value, user):
        if value in (None, ""):
            return None
        try:
            return EncryptedSecret.objects.get(id=value, owner=user)
        except EncryptedSecret.DoesNotExist:
            raise serializers.ValidationError(
                {"secret_reference_id": "Secret not found or not owned by you."}
            )

    def create(self, validated_data):
        secret_id = validated_data.pop("secret_reference_id", None)
        provider = Provider.objects.create(
            **validated_data,
            secret_reference=self._resolve_secret(
                secret_id, self.context["request"].user
            ),
        )
        return provider

    def update(self, instance, validated_data):
        if "secret_reference_id" in validated_data:
            secret_id = validated_data.pop("secret_reference_id")
            instance.secret_reference = self._resolve_secret(
                secret_id, self.context["request"].user
            )
        return super().update(instance, validated_data)


class AIModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIModel
        fields = (
            "id",
            "provider",
            "model_identifier",
            "model_version",
            "task_type",
            "hardware_requirements",
            "quality_profile",
            "license_metadata",
            "enabled",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class GenerationJobSerializer(serializers.ModelSerializer):
    provider_name = serializers.CharField(source="provider.name", read_only=True)
    model_identifier = serializers.CharField(
        source="model.model_identifier", read_only=True
    )

    class Meta:
        model = GenerationJob
        fields = (
            "id",
            "project",
            "scene",
            "provider",
            "provider_name",
            "model",
            "model_identifier",
            "task_type",
            "request_hash",
            "request_metadata",
            "status",
            "external_job_id",
            "idempotency_key",
            "attempt_count",
            "estimated_cost",
            "actual_cost",
            "resource_usage",
            "error_code",
            "error_message",
            "started_at",
            "completed_at",
            "created_at",
        )
        read_only_fields = fields


class GenerationOutputSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenerationOutput
        fields = ("id", "job", "asset", "output_index", "metadata", "created_at")
        read_only_fields = fields


class ResourceUsageEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResourceUsageEvent
        fields = (
            "id",
            "provider",
            "job",
            "resource_type",
            "quantity",
            "unit",
            "estimated_cost",
            "actual_cost",
            "occurred_at",
            "metadata",
        )
        read_only_fields = fields


class BudgetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Budget
        fields = ("id", "scope_type", "scope_id", "limits", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")
