"""Provider gateway tests: routing policies, budget enforcement, idempotency,
paid-fallback approval."""
from decimal import Decimal

import pytest

from providers import gateway
from providers.models import AIModel, Budget, GenerationJob, Provider, ResourceUsageEvent


@pytest.fixture
def local_provider(db):
    provider = Provider.objects.create(
        name="local-comfy", adapter_type="comfyui", deployment_type="local",
        base_url="http://127.0.0.1:9",  # unreachable on purpose; submit fails, routing is real
        capabilities={"task_types": ["image", "video"], "max_resolution": "2048x2048",
                      "max_duration_s": 60},
        health_status="UNKNOWN",
    )
    AIModel.objects.create(
        provider=provider, model_identifier="sdxl-turbo", task_type="image",
        quality_profile={"rank": 1},
    )
    return provider


@pytest.fixture
def cloud_provider(db):
    provider = Provider.objects.create(
        name="cloud-render", adapter_type="external_api", deployment_type="external",
        base_url="https://api.example.com",
        capabilities={"task_types": ["image", "video"], "max_resolution": "4096x4096",
                      "max_duration_s": 300, "price_per_task_usd": "0.50"},
        health_status="HEALTHY",
    )
    AIModel.objects.create(
        provider=provider, model_identifier="pro-image-2", task_type="image",
        quality_profile={"rank": 5},
    )
    return provider


def _route(channel, project, **kwargs):
    params = dict(task_type="image", requirements={"resolution": "1024x1024"},
                  channel=channel, project=project,
                  idempotency_key=kwargs.pop("idempotency_key", None) or
                  f"key-{channel.id}-{len(kwargs)}")
    params.update(kwargs)
    return gateway.route_generation(**params)


@pytest.mark.django_db
def test_local_first_routing_picks_local_capable_model(channel, project, local_provider, cloud_provider):
    job = _route(channel, project, idempotency_key="t1")
    assert job.provider_id == local_provider.id
    assert job.model.model_identifier == "sdxl-turbo"
    assert job.request_metadata["routing"]["policy"] == "local-first"
    assert job.request_metadata["routing"]["selected"]["provider"] == "local-comfy"


@pytest.mark.django_db
def test_unhealthy_providers_excluded(channel, project, local_provider, cloud_provider):
    local_provider.health_status = "UNHEALTHY"
    local_provider.save()
    job = _route(channel, project, idempotency_key="t2", allow_paid_fallback=True)
    assert job.provider_id == cloud_provider.id


@pytest.mark.django_db
def test_quality_first_policy_within_budget(channel, project, local_provider, cloud_provider):
    job = _route(channel, project, idempotency_key="t3", policy="quality-first",
                 allow_paid_fallback=True)
    assert job.provider_id == cloud_provider.id
    assert job.model.quality_profile["rank"] == 5


@pytest.mark.django_db
def test_budget_enforcement_blocks_overspend_at_channel_level(
        channel, project, local_provider, cloud_provider):
    seed_job = GenerationJob.objects.create(
        project=project, provider=local_provider, task_type="image",
        request_hash="seed", idempotency_key="seed-1", estimated_cost=Decimal("50"),
        status="COMPLETED",
    )
    ResourceUsageEvent.objects.create(
        provider=local_provider, job=seed_job, resource_type="api_spend_usd",
        quantity=Decimal("50"), unit="usd",
        estimated_cost=Decimal("50"), actual_cost=Decimal("50"),
    )
    Budget.objects.create(
        scope_type="channel", scope_id=channel.id,
        limits={"max_api_spend_daily": "10.00"},
    )
    with pytest.raises(gateway.BudgetExceeded) as exc_info:
        _route(channel, project, idempotency_key="t4")
    assert exc_info.value.code == "BUDGET_EXCEEDED"
    assert exc_info.value.retryable is False


@pytest.mark.django_db
def test_idempotent_submit_dedupes_by_idempotency_key(channel, project, local_provider):
    first = _route(channel, project, idempotency_key="dupe-key-1")
    second = _route(channel, project, idempotency_key="dupe-key-1")
    assert first.id == second.id
    assert GenerationJob.objects.filter(idempotency_key="dupe-key-1").count() == 1


@pytest.mark.django_db
def test_paid_fallback_requires_approval(channel, project, local_provider, cloud_provider):
    local_provider.health_status = "UNHEALTHY"
    local_provider.save()
    with pytest.raises(gateway.PaidFallbackApprovalRequired) as exc_info:
        _route(channel, project, idempotency_key="t5", allow_paid_fallback=False)
    assert exc_info.value.code == "PAID_FALLBACK_APPROVAL_REQUIRED"
    # ...but succeeds once explicitly allowed
    job = _route(channel, project, idempotency_key="t6", allow_paid_fallback=True)
    assert job.provider_id == cloud_provider.id
