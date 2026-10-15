"""Stripe client stub.

All Stripe network access goes through this module. Nothing here performs a
real charge today.

Going live is a one-function change:
  1. ``pip install stripe`` and set ``STRIPE_SECRET_KEY`` (+ ``STRIPE_PRICE_*``
     ids on the tiers, ``STRIPE_WEBHOOK_SECRET`` for the webhook).
  2. Replace the stub bodies in ``create_checkout_session``,
     ``create_billing_portal_session`` and ``verify_webhook_event`` with the
     real ``stripe`` SDK calls sketched in the TODO comments below.

When ``STRIPE_SECRET_KEY`` is unset the functions log a warning and return
locally-generated stub payloads, so checkout/portal flows can be exercised
end-to-end in dev without network access or fake charges.
"""

import logging
import uuid

from django.conf import settings

logger = logging.getLogger(__name__)


def is_stripe_configured() -> bool:
    """True only when a real secret key is present."""
    return bool(getattr(settings, "STRIPE_SECRET_KEY", ""))


def _require_stripe_sdk():
    """Import the stripe SDK, or raise with a clear setup message."""
    try:
        import stripe  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - environment-dependent
        raise RuntimeError(
            "STRIPE_SECRET_KEY is set but the 'stripe' package is not installed. "
            "Run: pip install stripe"
        ) from exc
    return stripe


def create_checkout_session(user, tier, success_url: str, cancel_url: str) -> dict:
    """Create a Stripe Checkout session for upgrading to ``tier``.

    Returns a dict with at least ``{"id": ..., "url": ...}``. The caller
    (``billing.views.CheckoutView``) only consumes this contract, so swapping
    in real Stripe is a one-function change here.
    """
    if not is_stripe_configured():
        logger.warning(
            "billing.checkout_stub user=%s tier=%s — STRIPE_SECRET_KEY unset; "
            "returning a stub checkout session (no real charge possible).",
            user.pk,
            tier.name,
        )
        stub_id = f"cs_test_stub_{uuid.uuid4().hex[:16]}"
        return {
            "id": stub_id,
            "url": f"{success_url}?session_id={stub_id}&stub=1",
            "stub": True,
        }
    stripe = _require_stripe_sdk()
    stripe.api_key = settings.STRIPE_SECRET_KEY
    # TODO(live): uncomment when going live with real Stripe price IDs.
    # session = stripe.checkout.Session.create(
    #     mode="subscription",
    #     customer_email=user.email,
    #     client_reference_id=str(user.pk),
    #     metadata={"user_id": str(user.pk), "tier": tier.name},
    #     line_items=[{"price": tier.stripe_price_id, "quantity": 1}],
    #     success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
    #     cancel_url=cancel_url,
    # )
    # return {"id": session.id, "url": session.url, "stub": False}
    raise NotImplementedError(
        "Real Stripe checkout is not wired yet: STRIPE_SECRET_KEY is set but "
        "the live stripe.checkout.Session.create call is still a TODO in "
        "billing/stripe_client.py::create_checkout_session."
    )


def create_billing_portal_session(user, return_url: str) -> dict:
    """Create a Stripe Customer Portal session for managing the subscription."""
    if not is_stripe_configured():
        logger.warning(
            "billing.portal_stub user=%s — STRIPE_SECRET_KEY unset; "
            "returning a stub portal session.",
            user.pk,
        )
        stub_id = f"bps_test_stub_{uuid.uuid4().hex[:16]}"
        return {
            "id": stub_id,
            "url": f"{return_url}?portal_session={stub_id}&stub=1",
            "stub": True,
        }
    stripe = _require_stripe_sdk()
    stripe.api_key = settings.STRIPE_SECRET_KEY
    # TODO(live): uncomment when going live.
    # session = stripe.billing_portal.Session.create(
    #     customer=user.subscription.stripe_customer_id,
    #     return_url=return_url,
    # )
    # return {"id": session.id, "url": session.url, "stub": False}
    raise NotImplementedError(
        "Real Stripe portal is not wired yet: STRIPE_SECRET_KEY is set but "
        "the live stripe.billing_portal.Session.create call is still a TODO in "
        "billing/stripe_client.py::create_billing_portal_session."
    )


def verify_webhook_event(payload: bytes, sig_header: str | None) -> dict:
    """Verify the webhook signature and parse the event.

    With live keys this delegates to ``stripe.Webhook.construct_event``.
    Without keys the signature check is skipped (warning logged) and the
    JSON payload is returned as-is — dev convenience only.
    """
    import json

    if not is_stripe_configured():
        logger.warning(
            "billing.webhook_stub — STRIPE_SECRET_KEY unset; skipping "
            "signature verification (dev mode only, never in production)."
        )
        return json.loads(payload.decode("utf-8"))
    _require_stripe_sdk()  # fail fast with a clear message if the SDK is missing
    # TODO(live): uncomment when going live.
    # import stripe
    # stripe.api_key = settings.STRIPE_SECRET_KEY
    # return stripe.Webhook.construct_event(
    #     payload, sig_header or "", settings.STRIPE_WEBHOOK_SECRET
    # )
    raise NotImplementedError(
        "Real webhook verification is not wired yet: STRIPE_SECRET_KEY is set "
        "but stripe.Webhook.construct_event is still a TODO in "
        "billing/stripe_client.py::verify_webhook_event."
    )
