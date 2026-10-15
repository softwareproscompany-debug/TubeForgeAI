"""Core URL routes."""

from django.urls import path

from .passkey import (
    PasskeyAuthenticateBeginView,
    PasskeyAuthenticateFinishView,
    PasskeyRegisterBeginView,
    PasskeyRegisterFinishView,
)
from .views import (
    AuditEventListView,
    ChangePasswordView,
    HealthView,
    LoginView,
    LogoutView,
    MeView,
    NotificationDetailView,
    NotificationListCreateView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
    SystemSettingDetailView,
    SystemSettingListView,
)

urlpatterns = [
    path("auth/login", LoginView.as_view(), name="auth-login"),
    path("auth/logout", LogoutView.as_view(), name="auth-logout"),
    path("auth/me", MeView.as_view(), name="auth-me"),
    path("auth/register", RegisterView.as_view(), name="auth-register"),
    path(
        "auth/change-password",
        ChangePasswordView.as_view(),
        name="auth-change-password",
    ),
    path(
        "auth/password-reset/request",
        PasswordResetRequestView.as_view(),
        name="auth-password-reset-request",
    ),
    path(
        "auth/password-reset/confirm",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path(
        "auth/passkey/register/begin",
        PasskeyRegisterBeginView.as_view(),
        name="auth-passkey-register-begin",
    ),
    path(
        "auth/passkey/register/finish",
        PasskeyRegisterFinishView.as_view(),
        name="auth-passkey-register-finish",
    ),
    path(
        "auth/passkey/authenticate/begin",
        PasskeyAuthenticateBeginView.as_view(),
        name="auth-passkey-authenticate-begin",
    ),
    path(
        "auth/passkey/authenticate/finish",
        PasskeyAuthenticateFinishView.as_view(),
        name="auth-passkey-authenticate-finish",
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
