"""Temporal worker: runs the durable VideoProductionWorkflow + stage activities.

Usage: ``python manage.py temporal_worker``
Requires a reachable Temporal server at settings.TEMPORAL_HOST.
"""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Run the Temporal worker for TubeForge durable workflows."

    def handle(self, *args, **options):
        from workflows.activities import main

        self.stdout.write(self.style.SUCCESS("Starting Temporal worker…"))
        main()
