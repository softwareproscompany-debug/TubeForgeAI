"""Signal handlers: auto-provision a free subscription for every new user."""

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import SubscriptionTier, UserSubscription
from .tier_data import TIER_SEEDS

User = get_user_model()

_FREE_DEFAULTS = {s["name"]: s for s in TIER_SEEDS}["free"]


@receiver(post_save, sender=User)
def ensure_free_subscription(sender, instance, created, **kwargs):
    """Give every newly registered user an active ``free`` subscription.

    Idempotent (``get_or_create``) so it is safe against double dispatch.
    """
    if not created:
        return
    tier, _ = SubscriptionTier.objects.get_or_create(
        name="free",
        defaults={
            "display_name": _FREE_DEFAULTS["display_name"],
            "price_monthly_cents": _FREE_DEFAULTS["price_monthly_cents"],
            "stripe_price_id": _FREE_DEFAULTS["stripe_price_id"],
            "max_projects": _FREE_DEFAULTS["max_projects"],
            "max_storage_gb": _FREE_DEFAULTS["max_storage_gb"],
            "max_api_calls_month": _FREE_DEFAULTS["max_api_calls_month"],
            "features": _FREE_DEFAULTS["features"],
        },
    )
    UserSubscription.objects.get_or_create(
        user=instance,
        defaults={"tier": tier, "status": UserSubscription.STATUS_ACTIVE},
    )
