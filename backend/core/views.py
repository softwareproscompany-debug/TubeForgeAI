"""Core views: auth, health, audit, notifications, system settings."""
import asyncio

from django.conf import settings
from django.contrib.auth import authenticate
from django.db import connection
from django.utils import timezone
from rest_framework import generics, permissions, serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditEvent, Notification, SystemSetting
from .serializers import (
    AuditEventSerializer,
    LoginSerializer,
    NotificationSerializer,
    SystemSettingSerializer,
    UserSerializer,
)
from .utils import LoginRateThrottle, record_audit


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            record_audit(
                None, "auth.login", "user", serializer.validated_data["username"],
                outcome="failure", request=request,
            )
            raise AuthenticationFailed("Invalid username or password.")
        token, _ = Token.objects.get_or_create(user=user)
        record_audit(user, "auth.login", "user", str(user.id), request=request)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        record_audit(request.user, "auth.logout", "user", str(request.user.id), request=request)
        return Response({"detail": "Logged out."}, status=status.HTTP_200_OK)


class MeUpdateSerializer(serializers.Serializer):
    """Writable profile fields. ``display_name`` is stored on ``first_name``
    (the User model carries no separate display-name column)."""
    display_name = serializers.CharField(max_length=150, required=False)
    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = MeUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = request.user
        if "display_name" in data:
            user.first_name = data["display_name"]
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        user.save(update_fields=["first_name", "last_name"])
        record_audit(user, "user.update_profile", "user", str(user.id),
                     request=request)
        return Response(UserSerializer(user).data)


class ChangePasswordView(APIView):
    """Authenticated password change: verifies current password, sets a new one."""

    def post(self, request):
        current_password = request.data.get("current_password", "")
        new_password = request.data.get("new_password", "")
        if not request.user.check_password(current_password):
            return Response(
                {"error": {"code": "INVALID_CREDENTIALS",
                           "message": "Current password is incorrect.",
                           "retryable": False,
                           "correlation_id": getattr(request, "correlation_id", "")}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(new_password) < 12:
            return Response(
                {"error": {"code": "WEAK_PASSWORD",
                           "message": "New password must be at least 12 characters.",
                           "retryable": False,
                           "correlation_id": getattr(request, "correlation_id", "")}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        request.user.set_password(new_password)
        request.user.save(update_fields=["password"])
        record_audit(request.user, "user.change_password", "user", str(request.user.id),
                     request=request)
        return Response({"status": "password_changed"})


# ---------------------------------------------------------------------------
# Health (no secrets, no auth)
# ---------------------------------------------------------------------------
class HealthView(APIView):
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request):
        checks = {
            "database": self._check_database(),
            "redis": self._check_redis(),
            "temporal": self._check_temporal(),
        }
        degraded = any(v not in ("ok", "not_configured") for v in checks.values())
        return Response({"status": "degraded" if degraded else "ok", "checks": checks})

    def _check_database(self):
        try:
            connection.ensure_connection()
            return "ok"
        except Exception as exc:
            return f"error: {type(exc).__name__}"

    def _check_redis(self):
        if not settings.REDIS_URL:
            return "not_configured"
        try:
            import redis as redis_lib

            redis_lib.from_url(settings.REDIS_URL, socket_timeout=3).ping()
            return "ok"
        except Exception as exc:
            return f"error: {type(exc).__name__}"

    def _check_temporal(self):
        try:
            from temporalio.client import Client
        except ImportError:
            return "not_installed"

        async def _ping():
            await asyncio.wait_for(
                Client.connect(settings.TEMPORAL_HOST, namespace=settings.TEMPORAL_NAMESPACE),
                timeout=4,
            )

        try:
            asyncio.run(_ping())
            return "ok"
        except Exception:
            return "unreachable"


# ---------------------------------------------------------------------------
# Audit / notifications / settings
# ---------------------------------------------------------------------------
class AuditEventListView(generics.ListAPIView):
    serializer_class = AuditEventSerializer

    def get_queryset(self):
        return AuditEvent.objects.filter(actor=self.request.user).select_related("actor")


class NotificationListCreateView(generics.ListCreateAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        notification = serializer.save(user=self.request.user)
        record_audit(
            self.request.user, "notification.create", "notification", str(notification.id),
            request=self.request, metadata={"type": notification.type},
        )


class NotificationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = NotificationSerializer
    http_method_names = ["get", "patch"]

    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user)

    def perform_update(self, serializer):
        # PATCH marks the notification read; body fields are immutable.
        serializer.save(read_at=timezone.now())


class SystemSettingListView(generics.ListAPIView):
    serializer_class = SystemSettingSerializer
    queryset = SystemSetting.objects.all()


class SystemSettingDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = SystemSettingSerializer
    queryset = SystemSetting.objects.all()
    http_method_names = ["get", "put", "patch"]
    permission_classes = [permissions.IsAdminUser]

    def perform_update(self, serializer):
        setting = serializer.save(updated_by=self.request.user)
        record_audit(
            self.request.user, "system_setting.update", "system_setting", setting.key,
            request=self.request,
        )
