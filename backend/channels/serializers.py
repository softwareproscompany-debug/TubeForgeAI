"""Channel serializers."""
from rest_framework import serializers

from .models import AutomationRule, Channel, ChannelCredential


class ChannelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Channel
        fields = [
            "id", "youtube_channel_id", "title", "description", "default_language",
            "timezone", "brand_config", "automation_config", "publishing_policy",
            "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "youtube_channel_id", "is_active", "created_at", "updated_at"]


class ChannelSettingsSerializer(serializers.Serializer):
    brand_config = serializers.DictField(required=False)
    automation_config = serializers.DictField(required=False)
    publishing_policy = serializers.DictField(required=False)


class ChannelCredentialSerializer(serializers.ModelSerializer):
    has_token = serializers.SerializerMethodField()

    class Meta:
        model = ChannelCredential
        fields = [
            "id", "provider", "has_token", "granted_scopes",
            "expires_at", "last_validated_at", "revoked_at",
        ]
        read_only_fields = fields

    def get_has_token(self, obj):
        token = bytes(obj.encrypted_refresh_token or b"")
        return bool(token)


class AutomationRuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = AutomationRule
        fields = [
            "id", "name", "trigger_type", "conditions", "actions",
            "enabled", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
