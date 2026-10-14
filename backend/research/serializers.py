"""Research serializers."""
from rest_framework import serializers

from .models import ContentIdea, ResearchRun, ResearchSource


class ResearchSourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchSource
        fields = [
            "id", "source_type", "source_url", "title", "retrieved_at",
            "published_at", "evidence", "content_hash", "license_metadata",
        ]
        read_only_fields = fields


class ResearchRunSerializer(serializers.ModelSerializer):
    sources = ResearchSourceSerializer(many=True, read_only=True)

    class Meta:
        model = ResearchRun
        fields = [
            "id", "channel", "query", "parameters", "status",
            "started_at", "completed_at", "error_summary", "created_at", "sources",
        ]
        read_only_fields = ["id", "status", "started_at", "completed_at", "error_summary", "created_at", "sources"]


class ResearchRunCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ResearchRun
        fields = ["channel", "query", "parameters"]


class ContentIdeaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ContentIdea
        fields = [
            "id", "channel", "title", "topic", "format", "priority",
            "confidence_score", "supporting_evidence", "status", "created_at",
        ]
        read_only_fields = ["id", "created_at"]
