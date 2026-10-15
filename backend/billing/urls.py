"""Billing URL routes."""

from django.urls import path

from .views import (
    BillingPortalView,
    CheckoutView,
    StripeWebhookView,
    SubscriptionView,
    TierListView,
)

urlpatterns = [
    path("billing/tiers", TierListView.as_view(), name="billing-tiers"),
    path(
        "billing/subscription",
        SubscriptionView.as_view(),
        name="billing-subscription",
    ),
    path("billing/checkout", CheckoutView.as_view(), name="billing-checkout"),
    path(
        "billing/webhook",
        StripeWebhookView.as_view(),
        name="billing-webhook",
    ),
    path("billing/portal", BillingPortalView.as_view(), name="billing-portal"),
]
