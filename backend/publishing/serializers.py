"""Publishing serializers."""
from rest_framework import serializers

from .models import AnalyticsSnapshot, PublicationJob


class PublicationJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationJob
        fields = [
            "id", "project", "channel", "asset", "youtube_video_id", "title",
            "description", "tags", "visibility", "scheduled_at", "status",
            "upload_session_reference", "attempt_count", "last_error",
            "published_at", "idempotency_key", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "status", "youtube_video_id", "upload_session_reference",
                            "attempt_count", "last_error", "published_at",
                            "created_at", "updated_at"]


class PublicationJobCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PublicationJob
        fields = ["project", "asset", "title", "description", "tags",
                  "visibility", "scheduled_at", "idempotency_key"]
        extra_kwargs = {"idempotency_key": {"required": True}}


class AnalyticsSnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AnalyticsSnapshot
        fields = ["id", "channel", "youtube_video_id", "captured_at", "metrics", "source"]
        read_only_fields = fields


class IntegrityIssueSerializer(serializers.Serializer):
    severity = serializers.CharField()
    code = serializers.CharField()
    message = serializers.CharField()
