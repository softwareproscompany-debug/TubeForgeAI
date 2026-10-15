"""Billing views: tier listing, subscription status, checkout, webhook, portal."""

import logging
from datetime import UTC, datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core.utils import record_audit

from . import stripe_client
from .limits import count_projects
from .models import SubscriptionTier, UserSubscription
from .serializers import (
    CheckoutRequestSerializer,
    SubscriptionTierSerializer,
    UserSubscriptionSerializer,
)

logger = logging.getLogger(__name__)
User = get_user_model()


# ---------------------------------------------------------------------------
# Tiers + subscription status
# ---------------------------------------------------------------------------
class TierListView(generics.ListAPIView):
    """Public pricing table.

    AllowAny (not just authenticated) so marketing/pricing pages can render
    plans without a login. No sensitive data is exposed.
    """

    permission_classes = (permissions.AllowAny,)
    queryset = SubscriptionTier.objects.all()
    serializer_class = SubscriptionTierSerializer


class SubscriptionView(APIView):
    """Current user's subscription, tier details, and usage summary."""

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        subscription = get_object_or_404(
            UserSubscription.objects.select_related("tier"), user=request.user
        )
        tier = subscription.tier
        usage = {
            "projects_used": count_projects(request.user),
            "projects_limit": tier.max_projects,
            # Placeholders until metering exists; kept in the contract now.
            "storage_gb_used": 0,
            "storage_gb_limit": tier.max_storage_gb,
            "api_calls_used": 0,
            "api_calls_limit": tier.max_api_calls_month,
        }
        return Response(
            {
                "subscription": UserSubscriptionSerializer(subscription).data,
                "usage": usage,
            }
        )


# ---------------------------------------------------------------------------
# Checkout (stubbed Stripe)
# ---------------------------------------------------------------------------
class CheckoutView(APIView):
    """Start a Stripe Checkout session to upgrade to ``pro``/``enterprise``.

    The view only consumes ``stripe_client.create_checkout_session``'s
    ``{"id", "url"}`` contract — wiring real Stripe later is a one-function
    change inside ``stripe_client``.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        serializer = CheckoutRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tier = get_object_or_404(
            SubscriptionTier, name=serializer.validated_data["tier"]
        )
        base_url = (
            getattr(settings, "PUBLIC_APP_URL", "")
            or getattr(settings, "FRONTEND_URL", "")
            or "http://localhost:3000"
        ).rstrip("/")
        success_url = f"{base_url}/settings/billing?checkout=success"
        cancel_url = f"{base_url}/settings/billing?checkout=cancelled"
        session = stripe_client.create_checkout_session(
            request.user, tier, success_url, cancel_url
        )
        record_audit(
            request.user,
            "billing.checkout",
            "subscription_tier",
            tier.name,
            request=request,
            metadata={"session_id": session["id"], "stub": session.get("stub", False)},
        )
        return Response(
            {
                "checkout_url": session["url"],
                "session_id": session["id"],
                "stub": session.get("stub", False),
            },
            status=status.HTTP_201_CREATED,
        )


# ---------------------------------------------------------------------------
# Webhook (stubbed Stripe)
# ---------------------------------------------------------------------------
class StripeWebhookView(APIView):
    """Receive Stripe subscription events.

    AllowAny + no authentication: Stripe calls this with a signature, not a
    user token. Signature verification is delegated to
    ``stripe_client.verify_webhook_event`` (skipped with a warning when no
    Stripe keys are configured — dev only).
    """

    permission_classes = (permissions.AllowAny,)
    authentication_classes = ()

    def post(self, request):
        try:
            event = stripe_client.verify_webhook_event(
                request.body,
                request.headers.get("Stripe-Signature"),
            )
        except Exception as exc:  # noqa: BLE001 - verification failures are 400s
            logger.warning("billing.webhook rejected: %s", exc)
            return Response(
                {"detail": "Invalid webhook signature."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        event_type = event.get("type", "")
        logger.info("billing.webhook event=%s", event_type)
        handler = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.updated": self._handle_subscription_updated,
            "customer.subscription.deleted": self._handle_subscription_deleted,
        }.get(event_type)
        if handler is None:
            logger.info("billing.webhook unhandled event=%s", event_type)
        else:
            handler(event.get("data", {}).get("object", {}))
        return Response({"received": True})

    # -- handlers ---------------------------------------------------------
    def _handle_checkout_completed(self, session_obj: dict):
        """checkout.session.completed → upgrade the user to the paid tier."""
        metadata = session_obj.get("metadata", {}) or {}
        user_id = metadata.get("user_id") or session_obj.get("client_reference_id")
        tier_name = metadata.get("tier")
        logger.info(
            "billing.webhook checkout.session.completed user=%s tier=%s",
            user_id,
            tier_name,
        )
        if not user_id or not tier_name:
            logger.warning("billing.webhook checkout missing user_id/tier metadata")
            return
        try:
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError):
            logger.warning("billing.webhook checkout unknown user=%s", user_id)
            return
        try:
            tier = SubscriptionTier.objects.get(name=tier_name)
        except SubscriptionTier.DoesNotExist:
            logger.warning("billing.webhook checkout unknown tier=%s", tier_name)
            return
        subscription, _ = UserSubscription.objects.get_or_create(user=user)
        subscription.tier = tier
        subscription.status = UserSubscription.STATUS_ACTIVE
        subscription.stripe_customer_id = session_obj.get("customer", "") or ""
        subscription.stripe_subscription_id = session_obj.get("subscription", "") or ""
        subscription.save()
        record_audit(
            user,
            "billing.upgraded",
            "subscription",
            str(subscription.id),
            metadata={"tier": tier.name},
        )

    def _subscription_by_stripe_id(self, stripe_subscription_id: str):
        if not stripe_subscription_id:
            return None
        return UserSubscription.objects.filter(
            stripe_subscription_id=stripe_subscription_id
        ).first()

    def _handle_subscription_updated(self, subscription_obj: dict):
        """customer.subscription.updated → sync status + billing period."""
        sub = self._subscription_by_stripe_id(subscription_obj.get("id", ""))
        logger.info(
            "billing.webhook customer.subscription.updated stripe_id=%s found=%s",
            subscription_obj.get("id"),
            sub is not None,
        )
        if sub is None:
            return
        sub.status = subscription_obj.get("status", sub.status)
        sub.current_period_start = _ts(subscription_obj.get("current_period_start"))
        sub.current_period_end = _ts(subscription_obj.get("current_period_end"))
        sub.save()

    def _handle_subscription_deleted(self, subscription_obj: dict):
        """customer.subscription.deleted → mark canceled (keep the row)."""
        sub = self._subscription_by_stripe_id(subscription_obj.get("id", ""))
        logger.info(
            "billing.webhook customer.subscription.deleted stripe_id=%s found=%s",
            subscription_obj.get("id"),
            sub is not None,
        )
        if sub is None:
            return
        sub.status = UserSubscription.STATUS_CANCELED
        sub.save()
        record_audit(
            sub.user, "billing.canceled", "subscription", str(sub.id), metadata={}
        )


def _ts(value) -> datetime | None:
    if not value:
        return None
    return datetime.fromtimestamp(value, tz=UTC)


# ---------------------------------------------------------------------------
# Customer portal (stubbed Stripe)
# ---------------------------------------------------------------------------
class BillingPortalView(APIView):
    """Return a Stripe Customer Portal URL for managing the subscription."""

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request):
        base_url = (
            getattr(settings, "PUBLIC_APP_URL", "")
            or getattr(settings, "FRONTEND_URL", "")
            or "http://localhost:3000"
        ).rstrip("/")
        return_url = f"{base_url}/settings/billing"
        session = stripe_client.create_billing_portal_session(request.user, return_url)
        return Response(
            {
                "portal_url": session["url"],
                "stub": session.get("stub", False),
            }
        )
