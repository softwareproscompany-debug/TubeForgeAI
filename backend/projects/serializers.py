"""Project serializers."""
from rest_framework import serializers

from .models import Asset, Project, RenderJob, Scene, ScriptVersion, TimelineVersion


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "id", "channel", "content_idea", "title", "brief", "format",
            "target_duration_seconds", "aspect_ratio", "language", "status",
            "current_workflow_id", "settings", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ScriptVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScriptVersion
        fields = [
            "id", "project", "version_number", "structured_script", "rendered_text",
            "fact_check_status", "approval_status", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class SceneSerializer(serializers.ModelSerializer):
    class Meta:
        model = Scene
        fields = [
            "id", "project", "position", "script_segment", "visual_prompt",
            "negative_prompt", "duration_seconds", "scene_type",
            "generation_settings", "status", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "project", "created_at", "updated_at"]


class AssetSerializer(serializers.ModelSerializer):
    class Meta:
        model = Asset
        fields = [
            "id", "project", "scene", "asset_type", "object_key", "mime_type",
            "size_bytes", "sha256", "duration_seconds", "width", "height",
            "source_type", "source_url", "license_metadata", "model_metadata",
            "status", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TimelineVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimelineVersion
        fields = ["id", "project", "version_number", "timeline_json", "render_settings", "created_at"]
        read_only_fields = ["id", "version_number", "created_at"]


class RenderJobSerializer(serializers.ModelSerializer):
    class Meta:
        model = RenderJob
        fields = [
            "id", "project", "timeline_version", "status", "manifest",
            "output_asset", "error", "started_at", "completed_at", "created_at",
        ]
        read_only_fields = ["id", "status", "manifest", "output_asset", "error",
                            "started_at", "completed_at", "created_at"]
