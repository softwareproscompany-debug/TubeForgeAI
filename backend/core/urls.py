"""Core URL routes."""

from django.urls import path

from .views import (
    AuditEventListView,
    ChangePasswordView,
    HealthView,
    LoginView,
    LogoutView,
    MeView,
    NotificationDetailView,
    NotificationListCreateView,
    SystemSettingDetailView,
    SystemSettingListView,
)

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/me", MeView.as_view(), name="auth-me"),
    path(
        "auth/change-password",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
    path("health", HealthView.as_view(), name="health"),
    path("audit-events", AuditEventListView.as_view(), name="audit-events"),
    path("notifications", NotificationListCreateView.as_view(), name="notifications"),
    path(
        "notifications/<uuid:pk>",
        NotificationDetailView.as_view(),
        name="notification-detail",
    ),
    path("system-settings", SystemSettingListView.as_view(), name="system-settings"),
    path(
        "system-settings/<uuid:pk>",
        SystemSettingDetailView.as_view(),
        name="system-setting-detail",
    ),
]
