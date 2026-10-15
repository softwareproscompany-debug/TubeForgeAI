"""AI gateway worker: polls provider job status for RUNNING GenerationJobs and
finalizes them (fetch outputs → create assets → record usage) via the provider
gateway. Submitted jobs are created through route_generation(); this loop only
reconciles in-flight external jobs so a lost response never double-submits.

Usage: ``python manage.py ai_gateway [--once] [--poll-seconds 10]``
"""

import asyncio
import time

from django.core.management.base import BaseCommand
from django.utils import timezone


async def _reconcile_job(job):
    from providers import gateway

    adapter = gateway.get_adapter(job.provider)
    try:
        state = await adapter.get_status(job.external_job_id or str(job.id))
    except gateway.ProviderError as exc:
        job.attempt_count = (job.attempt_count or 0) + 1
        job.error_code = exc.code if hasattr(exc, "code") else "PROVIDER_ERROR"
        job.error_message = str(exc)[:2000]
        job.save(update_fields=["attempt_count", "error_code", "error_message"])
        return
    status = (state.get("status") or "").upper()
    if status in ("COMPLETED", "SUCCEEDED", "DONE"):
        outputs = await adapter.fetch_outputs(job.external_job_id or str(job.id))
        assets = []
        for idx, out in enumerate(outputs):
            assets.append(out)
        gateway.complete_job(job, assets)
    elif status in ("FAILED", "ERROR", "CANCELED"):
        job.status = "FAILED"
        job.error_code = state.get("error_code", "PROVIDER_FAILED")
        job.error_message = str(state.get("error", "provider reported failure"))[:2000]
        job.completed_at = timezone.now()
        job.save()
    # else: still running — leave for the next poll.


class Command(BaseCommand):
    help = "Run the AI provider gateway reconciliation loop."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once", action="store_true", help="Reconcile once, then exit."
        )
        parser.add_argument("--poll-seconds", type=int, default=10)

    def handle(self, *args, **options):
        from providers.models import GenerationJob

        self.stdout.write(self.style.SUCCESS("AI gateway worker started."))
        while True:
            jobs = list(
                GenerationJob.objects.filter(status="RUNNING").select_related(
                    "provider"
                )[:25]
            )
            for job in jobs:
                try:
                    asyncio.run(_reconcile_job(job))
                except Exception as exc:  # noqa: BLE001 - never let one job kill the loop
                    self.stderr.write(f"job {job.id}: reconcile error: {exc}")
            if options["once"]:
                break
            time.sleep(options["poll_seconds"])
