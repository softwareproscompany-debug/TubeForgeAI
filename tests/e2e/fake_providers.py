"""Deterministic fake provider adapters for end-to-end testing.

FakeComfyUIAdapter and FakeLLMAdapter implement the GenerationProvider
protocol surface (async health_check / capabilities / estimate / submit /
get_status / cancel / fetch_outputs) with fully deterministic, in-memory
behavior. No network access, no randomness, no disk writes outside /tmp.

These are test doubles, not stubs: they honor the contract shapes the real
adapters use so the e2e scenario exercises the real router, budget checks,
and workflow engine code paths.
"""

from __future__ import annotations

import hashlib
import itertools
import json

_JOB_IDS = itertools.count(1)


class _FakeJobStore:
    """Shared in-memory job registry: idempotency_key -> job record."""

    def __init__(self) -> None:
        self.by_idempotency: dict[str, dict] = {}
        self.by_id: dict[str, dict] = {}

    def reset(self) -> None:
        self.by_idempotency.clear()
        self.by_id.clear()


class _BaseFakeAdapter:
    name = "fake-base"
    is_local = True

    def __init__(self) -> None:
        self.store = _FakeJobStore()

    # -- contract ---------------------------------------------------------
    async def health_check(self) -> dict:
        return {"healthy": True, "name": self.name, "latency_ms": 1}

    async def capabilities(self) -> dict:
        return {
            "name": self.name,
            "local": self.is_local,
            "task_types": sorted(self.task_types),
            "resource_types": ["cpu_seconds", "ram_gb_seconds", "storage_gb"],
            "max_parallel_jobs": 8,
        }

    async def estimate(self, task_type: str, requirements: dict) -> dict:
        if task_type not in self.task_types:
            raise ValueError(f"{self.name} does not support task_type={task_type!r}")
        units = int(requirements.get("units", 1))
        return {
            "cpu_seconds": 2.0 * units,
            "ram_gb_seconds": 1.0 * units,
            "storage_gb": 0.05 * units,
            "api_spend_usd": 0.0,  # local-first: fake adapters never spend API budget
        }

    async def submit(self, task_type: str, payload: dict, idempotency_key: str) -> dict:
        if idempotency_key in self.store.by_idempotency:
            # Idempotent replay: same key -> same job, no duplicate work.
            return self.store.by_idempotency[idempotency_key]
        job_id = f"{self.name}-job-{next(_JOB_IDS):06d}"
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()
        ).hexdigest()[:16]
        job = {
            "job_id": job_id,
            "task_type": task_type,
            "status": "succeeded",  # fakes complete instantly and deterministically
            "progress": 1.0,
            "idempotency_key": idempotency_key,
            "payload_digest": digest,
            "outputs": self._build_outputs(job_id, task_type, payload, digest),
        }
        self.store.by_idempotency[idempotency_key] = job
        self.store.by_id[job_id] = job
        return job

    async def get_status(self, job_id: str) -> dict:
        job = self.store.by_id.get(job_id)
        if job is None:
            return {"job_id": job_id, "status": "not_found", "progress": 0.0}
        return {"job_id": job_id, "status": job["status"], "progress": job["progress"]}

    async def cancel(self, job_id: str) -> bool:
        job = self.store.by_id.get(job_id)
        if job is None:
            return False
        if job["status"] in ("succeeded", "failed", "canceled"):
            return False  # terminal jobs cannot be canceled
        job["status"] = "canceled"
        return True

    async def fetch_outputs(self, job_id: str) -> list:
        job = self.store.by_id.get(job_id)
        if job is None or job["status"] != "succeeded":
            return []
        return job["outputs"]

    # -- fake-specific ----------------------------------------------------
    def _build_outputs(self, job_id: str, task_type: str, payload: dict, digest: str) -> list:
        raise NotImplementedError


class FakeComfyUIAdapter(_BaseFakeAdapter):
    """Deterministic stand-in for the ComfyUI image/video adapter."""

    name = "fake-comfyui"
    task_types = {"image", "scene_frame", "thumbnail"}

    def _build_outputs(self, job_id: str, task_type: str, payload: dict, digest: str) -> list:
        # Deterministic fake PNG bytes derived from the payload digest.
        fake_png = b"\x89PNG\r\n\x1a\nFAKE-" + digest.encode() + b"-" + job_id.encode()
        return [
            {
                "kind": "image",
                "uri": f"memory://fake-comfyui/{job_id}.png",
                "bytes": fake_png,
                "width": 1024,
                "height": 576,
                "task_type": task_type,
                "prompt": payload.get("prompt", ""),
            }
        ]


class FakeLLMAdapter(_BaseFakeAdapter):
    """Deterministic stand-in for the local LLM adapter (scripts, plans)."""

    name = "fake-llm"
    task_types = {"script", "plan", "scene_breakdown", "narration_text", "captions"}

    def _build_outputs(self, job_id: str, task_type: str, payload: dict, digest: str) -> list:
        if task_type == "script":
            doc = {
                "title": "Deterministic Test Script",
                "sections": [
                    {"heading": "Hook", "lines": ["This is a deterministic test line."]},
                    {"heading": "Body", "lines": ["Nothing random lives here."]},
                    {"heading": "CTA", "lines": ["End of deterministic script."]},
                ],
            }
        elif task_type == "scene_breakdown":
            doc = {
                "scenes": [
                    {"index": 0, "prompt": "scene 0 deterministic", "duration_s": 5},
                    {"index": 1, "prompt": "scene 1 deterministic", "duration_s": 5},
                ]
            }
        elif task_type == "narration_text":
            doc = {"text": "Deterministic narration for testing.", "voice": "fake-voice"}
        elif task_type == "captions":
            doc = {
                "captions": [
                    {"start_s": 0.0, "end_s": 2.5, "text": "Deterministic caption one."},
                    {"start_s": 2.5, "end_s": 5.0, "text": "Deterministic caption two."},
                ]
            }
        else:  # plan and any other text task
            doc = {"plan": "deterministic plan", "steps": ["research", "script", "render"]}
        blob = json.dumps(doc, sort_keys=True).encode()
        return [
            {
                "kind": "document",
                "uri": f"memory://fake-llm/{job_id}.json",
                "bytes": blob,
                "json": doc,
                "task_type": task_type,
            }
        ]


def reset_all(*adapters: _BaseFakeAdapter) -> None:
    """Clear fake job stores between scenarios (keeps runs hermetic)."""
    for adapter in adapters:
        adapter.store.reset()
