"""FFmpeg render worker: claims QUEUED RenderJobs and runs the 10-stage
RenderWorker pipeline (media_engine.RenderWorker.run).

Usage: ``python manage.py render_worker [--once] [--poll-seconds 5]``
"""
import time

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Run the FFmpeg render worker loop."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true",
                            help="Process a single queued job, then exit.")
        parser.add_argument("--poll-seconds", type=int, default=5)

    def handle(self, *args, **options):
        from projects.media_engine import RenderWorker
        from projects.models import RenderJob

        worker = RenderWorker()
        self.stdout.write(self.style.SUCCESS("Render worker started."))
        while True:
            job = (
                RenderJob.objects.filter(status="QUEUED")
                .order_by("created_at")
                .select_related("timeline_version", "project")
                .first()
            )
            if job is None:
                if options["once"]:
                    break
                time.sleep(options["poll_seconds"])
                continue
            # Claim the job so a second worker cannot pick it up.
            claimed = RenderJob.objects.filter(
                id=job.id, status="QUEUED").update(status="RUNNING",
                                                  started_at=timezone.now())
            if not claimed:
                continue
            job.refresh_from_db()
            self.stdout.write(f"Rendering job {job.id} …")
            try:
                plan = None
                prev = RenderJob.objects.filter(
                    project=job.project, status="COMPLETED"
                ).exclude(id=job.id).order_by("-completed_at").first()
                if prev and prev.manifest:
                    from projects.media_engine import compute_incremental_plan
                    old = (prev.manifest.get("timeline") or {})
                    plan = compute_incremental_plan(
                        old, job.timeline_version.timeline_json)
                worker.run(job, plan=plan)
            except Exception as exc:  # never let one job kill the loop
                job.status = "FAILED"
                job.error = f"worker crashed: {exc}"[:2000]
                job.completed_at = timezone.now()
                job.save()
            self.stdout.write(f"Job {job.id}: {job.status}")
            if options["once"]:
                break
