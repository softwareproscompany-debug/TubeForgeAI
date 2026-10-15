"""Temporal workflow definitions for TubeForge AI.

The temporalio import is guarded: if the SDK is not installed, lightweight
no-op decorator shims keep this module importable (the synchronous fallback
runner in views is used instead). Install ``temporalio`` and point
TEMPORAL_HOST at a live server for durable execution.
"""

from datetime import timedelta

try:
    from temporalio import workflow

    TEMPORAL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised when temporalio is missing
    TEMPORAL_AVAILABLE = False

    def _passthrough_decorator(*dargs, **dkwargs):
        def wrap(target):
            return target

        if len(dargs) == 1 and callable(dargs[0]) and not dkwargs:
            return dargs[0]
        return wrap

    class _WorkflowShim:
        defn = staticmethod(_passthrough_decorator)
        run = staticmethod(_passthrough_decorator)
        signal = staticmethod(_passthrough_decorator)

        @staticmethod
        def wait_condition(*args, **kwargs):
            raise RuntimeError("temporalio is not installed")

        @staticmethod
        def execute_activity(*args, **kwargs):
            raise RuntimeError("temporalio is not installed")

    workflow = _WorkflowShim()


def _activity(name):
    # Imported lazily so the shim path never touches the real SDK.
    from . import activities

    return getattr(activities, name)


@workflow.defn
class VideoProductionWorkflow:
    """Durable video-production pipeline with pause/resume/cancel/approve signals,
    per-stage activities, checkpointing after each scene, and an idempotent
    workflow id of ``project-<project_id>-v<n>``."""

    def __init__(self):
        self._paused = False
        self._cancel_requested = False
        self._approvals = {}

    @workflow.run
    async def run(self, run_id: str, project_id: str) -> dict:
        from temporalio.common import RetryPolicy

        stages = [
            ("RESEARCHING", "research_stage"),
            ("SCRIPTING", "script_stage"),
            ("STORYBOARDING", "storyboard_stage"),
            ("GENERATING_ASSETS", "generate_assets_stage"),
            ("GENERATING_NARRATION", "narration_stage"),
            ("ASSEMBLING", "assemble_stage"),
            ("RENDERING", "render_stage"),
            ("VALIDATING", "validate_stage"),
        ]
        completed = []
        for stage_name, activity_name in stages:
            await workflow.wait_condition(lambda: not self._paused)
            if self._cancel_requested:
                return {"status": "canceled", "completed_stages": completed}
            result = await workflow.execute_activity(
                _activity(activity_name),
                args=[run_id, project_id],
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(minutes=2),
                retry_policy=RetryPolicy(
                    maximum_attempts=5, initial_interval=timedelta(seconds=10)
                ),
            )
            # Checkpoint after each stage (scene-level checkpointing happens
            # inside generate_assets_stage).
            completed.append({"stage": stage_name, "result": result})
        return {"status": "completed", "completed_stages": completed}

    @workflow.signal
    async def pause(self):
        self._paused = True

    @workflow.signal
    async def resume(self):
        self._paused = False

    @workflow.signal
    async def cancel(self):
        self._cancel_requested = True

    @workflow.signal
    async def approve(self, approval_id: str):
        self._approvals[approval_id] = True


def build_workflow_id(project_id, version):
    return f"project-{project_id}-v{version}"
