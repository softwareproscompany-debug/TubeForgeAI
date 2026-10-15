"""Billing tests: tier seeding, free subscription auto-provisioning, checkout
stub, webhook handling, and project-create tier-limit enforcement."""

import importlib
import json

import pytest

from billing.limits import TierLimitExceededAPI, check_limit, require_tier
from billing.models import SubscriptionTier, UserSubscription
from billing.tier_data import TIER_SEEDS


@pytest.mark.django_db
def test_tiers_seeded():
    tiers = {t.name: t for t in SubscriptionTier.objects.all()}
    assert set(tiers) == {"free", "pro", "enterprise"}
    assert tiers["free"].price_monthly_cents == 0
    assert tiers["free"].max_projects == 3
    assert tiers["pro"].price_monthly_cents == 2900
    assert tiers["pro"].max_projects == 50
    assert tiers["enterprise"].price_monthly_cents == 29900
    assert tiers["free"].features  # non-empty feature list


@pytest.mark.django_db
def test_tier_seeding_idempotent():
    """Re-running the seed migration logic must not duplicate tiers."""
    module = importlib.import_module("billing.migrations.0001_initial")

    # Call the RunPython forward function twice against the real ORM state.
    from django.apps import apps

    module.seed_tiers(apps, None)
    module.seed_tiers(apps, None)
    assert SubscriptionTier.objects.count() == 3
    for seed in TIER_SEEDS:
        assert SubscriptionTier.objects.filter(name=seed["name"]).count() == 1


@pytest.mark.django_db
def test_free_subscription_auto_created(user):
    sub = UserSubscription.objects.get(user=user)
    assert sub.tier.name == "free"
    assert sub.status == UserSubscription.STATUS_ACTIVE


@pytest.mark.django_db
def test_subscription_not_duplicated_on_user_update(user):
    user.first_name = "Changed"
    user.save()
    assert UserSubscription.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_tiers_list_is_public():
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/billing/tiers")
    assert response.status_code == 200
    body = response.json()
    tiers = body["results"] if isinstance(body, dict) else body
    names = [t["name"] for t in tiers]
    assert names == ["free", "pro", "enterprise"]
    assert tiers[1]["price_monthly_usd"] == 29.0


@pytest.mark.django_db
def test_subscription_endpoint(auth_client):
    response = auth_client.get("/api/v1/billing/subscription")
    assert response.status_code == 200
    body = response.json()
    assert body["subscription"]["tier"]["name"] == "free"
    assert body["subscription"]["status"] == "active"
    assert body["usage"]["projects_used"] == 0
    assert body["usage"]["projects_limit"] == 3


@pytest.mark.django_db
def test_subscription_endpoint_requires_auth():
    from rest_framework.test import APIClient

    response = APIClient().get("/api/v1/billing/subscription")
    assert response.status_code == 401


@pytest.mark.django_db
def test_checkout_stub_returns_url_without_stripe_keys(auth_client, settings):
    settings.STRIPE_SECRET_KEY = ""
    response = auth_client.post(
        "/api/v1/billing/checkout", {"tier": "pro"}, format="json"
    )
    assert response.status_code == 201
    body = response.json()
    assert body["checkout_url"].startswith("http")
    assert "session_id=" in body["checkout_url"]
    assert body["stub"] is True


@pytest.mark.django_db
def test_checkout_rejects_invalid_tier(auth_client):
    assert (
        auth_client.post(
            "/api/v1/billing/checkout", {"tier": "free"}, format="json"
        ).status_code
        == 400
    )
    assert (
        auth_client.post(
            "/api/v1/billing/checkout", {"tier": "platinum"}, format="json"
        ).status_code
        == 400
    )


@pytest.mark.django_db
def test_portal_stub_returns_url(auth_client, settings):
    settings.STRIPE_SECRET_KEY = ""
    response = auth_client.post("/api/v1/billing/portal", {}, format="json")
    assert response.status_code == 200
    body = response.json()
    assert body["portal_url"].startswith("http")
    assert body["stub"] is True


@pytest.mark.django_db
def test_webhook_checkout_completed_upgrades_tier(user, settings):
    from rest_framework.test import APIClient

    settings.STRIPE_SECRET_KEY = ""
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "customer": "cus_test_123",
                "subscription": "sub_test_123",
                "client_reference_id": str(user.pk),
                "metadata": {"user_id": str(user.pk), "tier": "pro"},
            }
        },
    }
    response = APIClient().post(
        "/api/v1/billing/webhook",
        data=json.dumps(event),
        content_type="application/json",
    )
    assert response.status_code == 200
    sub = UserSubscription.objects.get(user=user)
    assert sub.tier.name == "pro"
    assert sub.status == "active"
    assert sub.stripe_customer_id == "cus_test_123"
    assert sub.stripe_subscription_id == "sub_test_123"


@pytest.mark.django_db
def test_webhook_subscription_deleted_marks_canceled(user, settings):
    from rest_framework.test import APIClient

    settings.STRIPE_SECRET_KEY = ""
    sub = UserSubscription.objects.get(user=user)
    sub.stripe_subscription_id = "sub_test_456"
    sub.save()
    event = {
        "type": "customer.subscription.deleted",
        "data": {"object": {"id": "sub_test_456"}},
    }
    response = APIClient().post(
        "/api/v1/billing/webhook",
        data=json.dumps(event),
        content_type="application/json",
    )
    assert response.status_code == 200
    sub.refresh_from_db()
    assert sub.status == UserSubscription.STATUS_CANCELED


@pytest.mark.django_db
def test_webhook_unknown_event_acknowledged(settings):
    from rest_framework.test import APIClient

    settings.STRIPE_SECRET_KEY = ""
    response = APIClient().post(
        "/api/v1/billing/webhook",
        data=json.dumps({"type": "invoice.paid", "data": {"object": {}}}),
        content_type="application/json",
    )
    assert response.status_code == 200
    assert response.json() == {"received": True}


@pytest.mark.django_db
def test_check_limit_allows_under_free_cap(user):
    assert check_limit(user, "projects") == 0


@pytest.mark.django_db
def test_project_create_blocked_at_free_limit(auth_client, user, channel):
    from projects.models import Project

    for i in range(3):
        Project.objects.create(channel=channel, title=f"Project {i}")
    response = auth_client.post(
        "/api/v1/projects",
        {"channel": str(channel.id), "title": "One too many"},
        format="json",
    )
    assert response.status_code == 402
    assert response.json()["error"]["code"] == "TIER_LIMIT_EXCEEDED"


@pytest.mark.django_db
def test_project_create_allowed_under_limit(auth_client, user, channel):
    response = auth_client.post(
        "/api/v1/projects",
        {"channel": str(channel.id), "title": "First project"},
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_pro_tier_raises_project_limit(auth_client, user, channel):
    from projects.models import Project

    sub = UserSubscription.objects.get(user=user)
    sub.tier = SubscriptionTier.objects.get(name="pro")
    sub.save()
    for i in range(3):
        Project.objects.create(channel=channel, title=f"Project {i}")
    response = auth_client.post(
        "/api/v1/projects",
        {"channel": str(channel.id), "title": "Fourth project"},
        format="json",
    )
    assert response.status_code == 201


@pytest.mark.django_db
def test_require_tier_decorator(user):
    class FakeRequest:
        pass

    request = FakeRequest()
    request.user = user

    @require_tier("pro")
    def pro_only(request):
        return "ok"

    from rest_framework.exceptions import APIException

    with pytest.raises(APIException):
        pro_only(request)
    sub = UserSubscription.objects.get(user=user)
    sub.tier = SubscriptionTier.objects.get(name="pro")
    sub.save()
    assert pro_only(request) == "ok"


@pytest.mark.django_db
def test_check_limit_unknown_resource(user):
    with pytest.raises(ValueError, match="Unknown billable resource"):
        check_limit(user, "warp_drives")


@pytest.mark.django_db
def test_check_limit_raises_unit(user, channel):
    from projects.models import Project

    for i in range(3):
        Project.objects.create(channel=channel, title=f"P{i}")
    with pytest.raises(TierLimitExceededAPI):
        check_limit(user, "projects")
