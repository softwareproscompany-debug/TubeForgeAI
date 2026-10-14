"""Core serializers."""
from rest_framework import serializers

from .models import AuditEvent, Notification, SystemSetting, User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "date_joined"]
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = AuditEvent
        fields = [
            "id", "actor", "action", "resource_type", "resource_id",
            "outcome", "correlation_id", "metadata", "occurred_at",
        ]
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = [
            "id", "type", "title", "body", "resource_type", "resource_id",
            "read_at", "created_at",
        ]
        read_only_fields = ["id", "read_at", "created_at"]


class SystemSettingSerializer(serializers.ModelSerializer):
    updated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SystemSetting
        fields = ["id", "key", "value", "updated_at", "updated_by"]
        read_only_fields = ["id", "key", "updated_at", "updated_by"]
