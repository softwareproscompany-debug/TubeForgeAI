"""Billing app configuration."""

from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "billing"

    def ready(self):
        # Import signal handlers so the free-subscription auto-provisioning
        # is registered once the app registry is ready.
        from . import signals  # noqa: F401
