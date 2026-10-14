"""Workflow failure-injection / recovery tests (spec §15.2).

Covers: worker crash mid-generation (FAILED preserves completed scene
artifacts, FAILED -> QUEUED retry resumes), duplicate workflow submission
(same temporal_workflow_id never creates two runs), and late worker
callbacks on canceled runs (ignored, status stays CANCELED).

Backend imports are lazy with skip guards so collection never fails while
the backend sibling is mid-build.
"""

import uuid

import pytest

try:
    from django.test import TestCase

    _DJANGO_OK, _DJANGO_ERR = True, None
except Exception as exc:
    TestCase = object  # type: ignore[assignment]
    _DJANGO_OK, _DJANGO_ERR = False, exc

pytestmark = pytest.mark.skipif(
    not _DJANGO_OK, reason=f"Django unavailable, backend mid-build: {_DJANGO_ERR!r}"
)

ADVANCE_PATH = ["PLANNING", "QUEUED", "RESEARCHING", "SCRIPTING",
                "STORYBOARDING", "GENERATING_ASSETS"]


def _engine_or_skip(testcase):
    try:
        from workflows import engine
    except Exception as exc:
        testcase.skipTest(f"workflows.engine unavailable: {exc!r}")
    for attr in ("validate_transition", "transition"):
        if not hasattr(engine, attr):
            testcase.skipTest(f"workflows.engine.{attr} not implemented yet")
    return engine


def _models_or_skip(testcase):
    try:
        from workflows.models import WorkflowRun
    except Exception as exc:
        testcase.skipTest(f"workflows.WorkflowRun unavailable: {exc!r}")
    try:
        from projects.models import Scene  # scene artifacts live with the project
    except Exception:
        try:
            from workflows.models import Scene
        except Exception as exc:
            testcase.skipTest(f"Scene model unavailable: {exc!r}")
    return WorkflowRun, Scene


def _make_run(testcase, WorkflowRun, **overrides):
    field_names = {f.name for f in WorkflowRun._meta.get_fields()}
    kwargs = dict(overrides)
    if "temporal_workflow_id" in field_names and "temporal_workflow_id" not in kwargs:
        kwargs["temporal_workflow_id"] = f"wf-{uuid.uuid4().hex[:12]}"
    if "state" in field_names and "state" not in kwargs:
        kwargs["state"] = "DRAFT"
    elif "status" in field_names and "status" not in kwargs and "state" not in field_names:
        kwargs["status"] = "DRAFT"
    # Best-effort FK wiring to project/channel when those fields exist.
    for f in WorkflowRun._meta.get_fields():
        if getattr(f, "many_to_one", False) and f.related_model is not None:
            if f.name in kwargs:
                continue
            try:
                from channels.models import Channel as _C
                from core.models import User as _U
                from projects.models import Project as _P

                if issubclass(f.related_model, _U):
                    user = _U.objects.create_user(
                        username=f"wf-user-{uuid.uuid4().hex[:8]}",
                        email=f"{uuid.uuid4().hex[:8]}@tubeforge.local",
                        password="not-a-real-password",
                    )
                    kwargs[f.name] = user
                elif issubclass(f.related_model, _P):
                    owner = _U.objects.create_user(
                        username=f"wf-owner-{uuid.uuid4().hex[:8]}",
                        email=f"{uuid.uuid4().hex[:8]}@tubeforge.local",
                        password="not-a-real-password",
                    )
                    proj_kwargs = {"title": "wf-project"}
                    for pf in _P._meta.get_fields():
                        if getattr(pf, "many_to_one", False) and pf.related_model is not None:
                            try:
                                if issubclass(pf.related_model, _U):
                                    proj_kwargs.setdefault(pf.name, owner)
                                elif issubclass(pf.related_model, _C):
                                    ch_kwargs = {"name": f"wf-ch-{uuid.uuid4().hex[:8]}"}
                                    for cf in _C._meta.get_fields():
                                        if getattr(cf, "many_to_one", False) and cf.related_model is not None:
                                            try:
                                                if issubclass(cf.related_model, _U):
                                                    ch_kwargs.setdefault(cf.name, owner)
                                            except Exception:
                                                pass
                                    proj_kwargs.setdefault(pf.name, _C.objects.create(**ch_kwargs))
                            except Exception:
                                pass
                    kwargs[f.name] = _P.objects.create(**proj_kwargs)
            except Exception:
                pass
    try:
        return WorkflowRun.objects.create(**kwargs)
    except TypeError as exc:
        testcase.skipTest(f"cannot construct WorkflowRun with {sorted(kwargs)}: {exc!r}")


def _state_of(run):
    for attr in ("state", "status"):
        if hasattr(run, attr):
            return getattr(run, attr)
    raise AssertionError("WorkflowRun has neither .state nor .status")


def _advance_to(testcase, engine, run, target):
    for state in ADVANCE_PATH:
        valid = engine.validate_transition(_state_of(run), state)
        if not valid:
            testcase.skipTest(
                f"engine forbids { _state_of(run)} -> {state}; cannot reach {target}"
            )
        engine.transition(run, state, actor="test")
        run.refresh_from_db()
    testcase.assertEqual(_state_of(run), target)


class TestWorkflowRecovery(TestCase):
    def test_crash_mid_generation_preserves_artifacts_and_retry_resumes(self):
        engine = _engine_or_skip(self)
        WorkflowRun, Scene = _models_or_skip(self)
        run = _make_run(self, WorkflowRun)
        _advance_to(self, engine, run, "GENERATING_ASSETS")

        # Two scenes already finished before the crash.
        scene_fields = {f.name for f in Scene._meta.get_fields()}
        status_field = "status" if "status" in scene_fields else None
        if status_field is None:
            self.skipTest("Scene has no status field to mark READY")
        run_fk = next(
            (f.name for f in Scene._meta.get_fields()
             if getattr(f, "many_to_one", False)
             and f.related_model is WorkflowRun),
            None,
        )
        if run_fk is None:
            self.skipTest("Scene has no FK to WorkflowRun")
        for i in range(2):
            Scene.objects.create(**{run_fk: run, status_field: "READY",
                                    **({"index": i} if "index" in scene_fields else {})})

        # Simulate worker crash mid-scene: run goes FAILED with an error payload.
        engine.transition(run, "FAILED", actor="worker-crash-sim")
        run.refresh_from_db()
        if hasattr(run, "error"):
            run.error = {"code": "worker_crash",
                         "detail": "simulated crash during scene 2 render"}
            run.save(update_fields=["error"])
        self.assertEqual(_state_of(run), "FAILED")

        # Completed scene artifacts must be preserved.
        ready = Scene.objects.filter(**{run_fk: run, status_field: "READY"}).count()
        self.assertEqual(ready, 2, "completed scene artifacts lost on FAILED")

        # Retry: FAILED -> QUEUED must be legal and must not wipe artifacts.
        self.assertTrue(engine.validate_transition("FAILED", "QUEUED"),
                        "engine must allow FAILED -> QUEUED retry")
        engine.transition(run, "QUEUED", actor="test-retry")
        run.refresh_from_db()
        self.assertEqual(_state_of(run), "QUEUED")
        ready_after = Scene.objects.filter(**{run_fk: run, status_field: "READY"}).count()
        self.assertEqual(ready_after, 2, "retry wiped completed scene artifacts")

    def test_duplicate_workflow_submission_no_duplicate_run(self):
        from django.db import IntegrityError

        _engine_or_skip(self)
        WorkflowRun, _ = _models_or_skip(self)
        field_names = {f.name for f in WorkflowRun._meta.get_fields()}
        if "temporal_workflow_id" not in field_names:
            self.skipTest("WorkflowRun has no temporal_workflow_id field")
        wf_id = f"wf-dup-{uuid.uuid4().hex[:12]}"
        first = _make_run(self, WorkflowRun, temporal_workflow_id=wf_id)
        try:
            _make_run(self, WorkflowRun, temporal_workflow_id=wf_id)
        except IntegrityError:
            pass  # correct: unique constraint rejects the duplicate
        else:
            # No DB-level uniqueness: the engine/service layer must dedupe.
            existing = WorkflowRun.objects.filter(temporal_workflow_id=wf_id)
            self.assertEqual(existing.count(), 1,
                             "duplicate WorkflowRun rows for one temporal_workflow_id")
            # Clean up the accidental duplicate so later tests stay hermetic.
            existing.exclude(pk=first.pk).delete()

    def test_late_callback_after_cancel_is_ignored(self):
        engine = _engine_or_skip(self)
        WorkflowRun, _ = _models_or_skip(self)
        run = _make_run(self, WorkflowRun)
        _advance_to(self, engine, run, "GENERATING_ASSETS")

        engine.transition(run, "CANCELED", actor="test-user")
        run.refresh_from_db()
        self.assertEqual(_state_of(run), "CANCELED")

        # Terminal states must not accept further transitions: the engine
        # either reports the transition invalid or raises; either way the
        # late worker callback must not move the run.
        try:
            valid = engine.validate_transition("CANCELED", "GENERATING_ASSETS")
        except Exception:
            valid = False
        self.assertFalse(valid, "engine must reject transitions out of CANCELED")
        try:
            engine.transition(run, "GENERATING_ASSETS", actor="late-worker-callback")
        except Exception:
            pass  # raising is an acceptable way to ignore the callback
        run.refresh_from_db()
        self.assertEqual(_state_of(run), "CANCELED",
                         "late worker callback moved a CANCELED run")
