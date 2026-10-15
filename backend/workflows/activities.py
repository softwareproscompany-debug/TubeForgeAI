"""Temporal activities: one durable, retryable activity per pipeline stage.

Each activity is idempotent w.r.t. its WorkflowRun: re-running a stage after a
worker crash resumes from recorded checkpoints (scene completion events).
Run directly as a Temporal worker via ``python -m workflows.activities``.
"""

import asyncio
import os

try:
    from temporalio import activity

    TEMPORAL_AVAILABLE = True
except ImportError:  # pragma: no cover
    TEMPORAL_AVAILABLE = False

    def _passthrough_decorator(*dargs, **dkwargs):
        def wrap(target):
            return target

        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]
        return wrap

    class _ActivityShim:
        defn = staticmethod(_passthrough_decorator)

        class _Info:
            workflow_id = ""
            activity_id = ""

        @staticmethod
        def info():
            return _ActivityShim._Info()

    activity = _ActivityShim()

from asgiref.sync import sync_to_async


def _load_run(run_id):
    from .models import WorkflowEvent, WorkflowRun

    run = WorkflowRun.objects.select_related("project__channel").get(id=run_id)
    return run, WorkflowEvent


@activity.defn(name="research_stage")
async def research_stage(run_id: str, project_id: str) -> dict:
    def _work():
        from research.models import ResearchRun

        run, WorkflowEvent = _load_run(run_id)
        project = run.project
        research = (
            ResearchRun.objects.filter(channel=project.channel, status="COMPLETED")
            .order_by("-created_at")
            .first()
        )
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="RESEARCHING",
            payload={"research_run_id": str(research.id) if research else None},
        )
        return {"research_run_id": str(research.id) if research else None}

    return await sync_to_async(_work)()


@activity.defn(name="script_stage")
async def script_stage(run_id: str, project_id: str) -> dict:
    def _work():
        run, WorkflowEvent = _load_run(run_id)
        script = run.project.script_versions.order_by("-version_number").first()
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="SCRIPTING",
            payload={"script_version": script.version_number if script else None},
        )
        return {"script_version": script.version_number if script else None}

    return await sync_to_async(_work)()


@activity.defn(name="storyboard_stage")
async def storyboard_stage(run_id: str, project_id: str) -> dict:
    def _work():
        run, WorkflowEvent = _load_run(run_id)
        scenes = list(
            run.project.scenes.order_by("position").values("id", "position", "status")
        )
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="STORYBOARDING",
            payload={"scene_count": len(scenes)},
        )
        return {"scene_count": len(scenes)}

    return await sync_to_async(_work)()


@activity.defn(name="generate_assets_stage")
async def generate_assets_stage(run_id: str, project_id: str) -> dict:
    """Scene-level checkpoint resume: scenes already marked READY are skipped."""

    def _work():
        from providers import gateway as provider_gateway

        run, WorkflowEvent = _load_run(run_id)
        project = run.project
        done, failed = [], []
        for scene in project.scenes.order_by("position"):
            if scene.status == "READY":
                done.append(str(scene.id))  # checkpoint hit: skip
                continue
            task_type = (
                "video" if scene.scene_type in ("CINEMATIC", "FACELESS") else "image"
            )
            job = provider_gateway.route_generation(
                task_type=task_type,
                requirements=scene.generation_settings or {},
                channel=project.channel,
                project=project,
                scene=scene,
                workflow_id=str(run.id),
                request_metadata={
                    "scene_id": str(scene.id),
                    "stage": "generate_assets",
                },
            )
            if job.status == "RUNNING":
                scene.status = "READY"
                scene.save(update_fields=["status", "updated_at"])
                done.append(str(scene.id))
                WorkflowEvent.objects.create(
                    run=run,
                    event_type="scene_completed",
                    stage="GENERATING_ASSETS",
                    payload={"scene_id": str(scene.id), "job_id": str(job.id)},
                )
            else:
                failed.append(str(scene.id))
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="GENERATING_ASSETS",
            payload={"scenes_done": done, "scenes_failed": failed},
        )
        return {"scenes_done": done, "scenes_failed": failed}

    return await sync_to_async(_work)()


@activity.defn(name="narration_stage")
async def narration_stage(run_id: str, project_id: str) -> dict:
    def _work():
        from providers import gateway as provider_gateway

        run, WorkflowEvent = _load_run(run_id)
        project = run.project
        job = provider_gateway.route_generation(
            task_type="narration",
            requirements={"language": project.language},
            channel=project.channel,
            project=project,
            workflow_id=str(run.id),
            request_metadata={"stage": "narration"},
        )
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="GENERATING_NARRATION",
            payload={"job_id": str(job.id), "job_status": job.status},
        )
        return {"job_id": str(job.id), "job_status": job.status}

    return await sync_to_async(_work)()


@activity.defn(name="assemble_stage")
async def assemble_stage(run_id: str, project_id: str) -> dict:
    def _work():
        from projects import media_engine

        run, WorkflowEvent = _load_run(run_id)
        timeline = run.project.timeline_versions.first()
        if timeline is None:
            raise RuntimeError("No timeline version to assemble.")
        media_engine.validate_timeline(timeline.timeline_json)
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="ASSEMBLING",
            payload={"timeline_version": timeline.version_number},
        )
        return {"timeline_version": timeline.version_number}

    return await sync_to_async(_work)()


@activity.defn(name="render_stage")
async def render_stage(run_id: str, project_id: str) -> dict:
    def _work():
        from projects import media_engine
        from projects.models import RenderJob

        run, WorkflowEvent = _load_run(run_id)
        project = run.project
        timeline = project.timeline_versions.first()
        if timeline is None:
            raise RuntimeError("No timeline version to render.")
        job = RenderJob.objects.create(
            project=project,
            timeline_version=timeline,
            status="QUEUED",
            manifest=media_engine.build_render_manifest(
                {}, timeline.id, {}, {"timeline_valid": True}
            ),
        )
        media_engine.RenderWorker().run(job)
        job.refresh_from_db()
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="RENDERING",
            payload={"render_job_id": str(job.id), "status": job.status},
        )
        if job.status != "COMPLETED":
            raise RuntimeError(f"Render failed: {job.error[:500]}")
        return {"render_job_id": str(job.id)}

    return await sync_to_async(_work)()


@activity.defn(name="validate_stage")
async def validate_stage(run_id: str, project_id: str) -> dict:
    def _work():
        run, WorkflowEvent = _load_run(run_id)
        render_job = run.project.render_jobs.order_by("-created_at").first()
        ok = render_job is not None and render_job.status == "COMPLETED"
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="VALIDATING",
            payload={"render_ok": ok},
        )
        if not ok:
            raise RuntimeError("No completed render to validate.")
        return {"render_ok": ok}

    return await sync_to_async(_work)()


@activity.defn(name="publish_stage")
async def publish_stage(run_id: str, project_id: str, publication_id: str = "") -> dict:
    def _work():
        from publishing import youtube as yt
        from publishing.models import PublicationJob

        run, WorkflowEvent = _load_run(run_id)
        publication = PublicationJob.objects.select_related("channel").get(
            id=publication_id
        )
        issues = yt.ContentIntegrityChecker.run(publication.project, publication)
        blocking = [i for i in issues if i["severity"] == "blocking"]
        if blocking:
            raise RuntimeError(f"Publication blocked: {blocking[0]['code']}")
        yt.UploadStateMachine.transition(publication, "UPLOAD_PENDING")
        WorkflowEvent.objects.create(
            run=run,
            event_type="stage_completed",
            stage="UPLOADING",
            payload={"publication_id": str(publication.id)},
        )
        return {"publication_id": str(publication.id)}

    return await sync_to_async(_work)()


ALL_ACTIVITIES = [
    research_stage,
    script_stage,
    storyboard_stage,
    generate_assets_stage,
    narration_stage,
    assemble_stage,
    render_stage,
    validate_stage,
    publish_stage,
]


def main():
    """Temporal worker entry point: ``python -m workflows.activities``."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django

    django.setup()

    async def _run():
        from django.conf import settings as dj_settings
        from temporalio.client import Client
        from temporalio.worker import Worker

        from .temporal_workflows import VideoProductionWorkflow

        client = await Client.connect(
            dj_settings.TEMPORAL_HOST, namespace=dj_settings.TEMPORAL_NAMESPACE
        )
        worker = Worker(
            client,
            task_queue=dj_settings.TEMPORAL_TASK_QUEUE,
            workflows=[VideoProductionWorkflow],
            activities=ALL_ACTIVITIES,
        )
        await worker.run()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
