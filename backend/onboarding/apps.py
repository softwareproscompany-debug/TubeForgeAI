"""Onboarding app: tracks new-user setup wizard progress."""

from django.apps import AppConfig


class OnboardingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "onboarding"
