"""Swarm app config."""

from django.apps import AppConfig


class SwarmConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "swarm"
    verbose_name = "Agent Swarm"
