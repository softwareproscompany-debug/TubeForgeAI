"""Root URL configuration: every app is mounted under /api/v1/."""

from django.urls import include, path

urlpatterns = [
    path("api/v1/", include("core.urls")),
    path("api/v1/", include("billing.urls")),
    path("api/v1/", include("channels.urls")),
    path("api/v1/", include("research.urls")),
    path("api/v1/", include("projects.urls")),
    path("api/v1/", include("providers.urls")),
    path("api/v1/", include("workflows.urls")),
    path("api/v1/", include("publishing.urls")),
    path("api/v1/", include("onboarding.urls")),
]
