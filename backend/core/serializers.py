"""Core serializers."""

from django.contrib.auth import password_validation
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import AuditEvent, Notification, SystemSetting, User, WebAuthnCredential


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "first_name", "last_name", "date_joined")
        read_only_fields = fields


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(
        max_length=150,
        validators=[UniqueValidator(queryset=User.objects.all())],
    )
    email = serializers.EmailField(
        validators=[UniqueValidator(queryset=User.objects.all())],
    )
    password = serializers.CharField(write_only=True)

    def validate_password(self, value):
        # Run Django's configured password validators against a throwaway user
        # so validators that need a user (e.g. similarity) still work.
        user = User(username=self.initial_data.get("username", ""))
        password_validation.validate_password(value, user=user)
        return value

    def create(self, validated_data):
        return User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
        )


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uidb64 = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)

    def validate_new_password(self, value):
        password_validation.validate_password(value)
        return value


class WebAuthnCredentialSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebAuthnCredential
        fields = ("id", "credential_id", "name", "sign_count", "created_at")
        read_only_fields = fields


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.StringRelatedField()

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "actor",
            "action",
            "resource_type",
            "resource_id",
            "outcome",
            "correlation_id",
            "metadata",
            "occurred_at",
        )
        read_only_fields = fields


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "type",
            "title",
            "body",
            "resource_type",
            "resource_id",
            "read_at",
            "created_at",
        )
        read_only_fields = ("id", "read_at", "created_at")


class SystemSettingSerializer(serializers.ModelSerializer):
    updated_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = SystemSetting
        fields = ("id", "key", "value", "updated_at", "updated_by")
        read_only_fields = ("id", "key", "updated_at", "updated_by")
