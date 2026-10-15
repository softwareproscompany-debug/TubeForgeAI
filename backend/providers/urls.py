"""Provider URL routes."""

from django.urls import path

from .views import (
    AIModelViewSet,
    BudgetViewSet,
    GenerationJobViewSet,
    ProviderViewSet,
    ResourceUsageListView,
)

provider_list = ProviderViewSet.as_view({"get": "list", "post": "create"})
provider_detail = ProviderViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)
provider_health = ProviderViewSet.as_view({"post": "health_check"})
provider_test = ProviderViewSet.as_view({"post": "test_generation"})
model_list = AIModelViewSet.as_view({"get": "list", "post": "create"})
model_detail = AIModelViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)
job_list = GenerationJobViewSet.as_view({"get": "list", "post": "create"})
job_detail = GenerationJobViewSet.as_view({"get": "retrieve"})
job_cancel = GenerationJobViewSet.as_view({"post": "cancel"})
job_complete = GenerationJobViewSet.as_view({"post": "complete"})
budget_list = BudgetViewSet.as_view({"get": "list", "post": "create"})
budget_detail = BudgetViewSet.as_view(
    {"get": "retrieve", "patch": "partial_update", "put": "update", "delete": "destroy"}
)

urlpatterns = [
    path("providers", provider_list, name="provider-list"),
    path("providers/<uuid:pk>", provider_detail, name="provider-detail"),
    path(
        "providers/<uuid:pk>/health-check",
        provider_health,
        name="provider-health-check",
    ),
    path(
        "providers/<uuid:pk>/test-generation",
        provider_test,
        name="provider-test-generation",
    ),
    path("models", model_list, name="aimodel-list"),
    path("models/<uuid:pk>", model_detail, name="aimodel-detail"),
    path("generations", job_list, name="generation-list"),
    path("generations/<uuid:pk>", job_detail, name="generation-detail"),
    path("generations/<uuid:pk>/cancel", job_cancel, name="generation-cancel"),
    path("generations/<uuid:pk>/complete", job_complete, name="generation-complete"),
    # Spec §9 canonical names (aliases of /generations/*).
    path("generation-jobs", job_list, name="generation-job-list"),
    path("generation-jobs/<uuid:pk>", job_detail, name="generation-job-detail"),
    path("generation-jobs/<uuid:pk>/cancel", job_cancel, name="generation-job-cancel"),
    path(
        "generation-jobs/<uuid:pk>/complete",
        job_complete,
        name="generation-job-complete",
    ),
    path("resource-usage", ResourceUsageListView.as_view(), name="resource-usage"),
    path("budgets", budget_list, name="budget-list"),
    path("budgets/<uuid:pk>", budget_detail, name="budget-detail"),
]
