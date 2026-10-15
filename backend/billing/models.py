"""Billing domain models: subscription tiers and per-user subscriptions."""

from django.conf import settings
from django.db import models

from core.models import UUIDModel


class SubscriptionTier(UUIDModel):
    """A billable plan. Limits are enforced by ``billing.limits``."""

    name = models.CharField(max_length=50, unique=True)  # free|pro|enterprise
    display_name = models.CharField(max_length=100)
    price_monthly_cents = models.IntegerField(default=0)
    stripe_price_id = models.CharField(max_length=255, blank=True, default="")
    max_projects = models.IntegerField(default=0)
    max_storage_gb = models.IntegerField(default=0)
    max_api_calls_month = models.IntegerField(default=0)
    features = models.JSONField(default=list)

    class Meta:
        ordering = ("price_monthly_cents",)

    def __str__(self):
        return self.name


class UserSubscription(UUIDModel):
    """One subscription row per user. Auto-created on the free tier."""

    STATUS_ACTIVE = "active"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELED = "canceled"
    STATUS_TRIALING = "trialing"
    STATUS_INCOMPLETE = "incomplete"

    STATUS_CHOICES = (
        (STATUS_ACTIVE, "Active"),
        (STATUS_PAST_DUE, "Past due"),
        (STATUS_CANCELED, "Canceled"),
        (STATUS_TRIALING, "Trialing"),
        (STATUS_INCOMPLETE, "Incomplete"),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    tier = models.ForeignKey(
        SubscriptionTier,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    stripe_customer_id = models.CharField(max_length=255, blank=True, default="")
    stripe_subscription_id = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_ACTIVE
    )
    current_period_start = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user}:{self.tier.name}:{self.status}"
