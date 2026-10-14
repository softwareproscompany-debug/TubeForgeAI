"""Provider gateway: local-first routing, adapters, server-side budget enforcement.

Routing pipeline (10 steps):
  1. validate the task type
  2. match provider/model capabilities against requirements
  3. apply channel restrictions (allowed_models / prohibited_models)
  4. exclude unhealthy providers
  5. check GPU capacity + queue depth
  6. estimate resource use + monetary cost
  7. select per policy (local-first | quality-first | lowest-cost | hybrid-fallback | manual)
  8. persist the routing decision into GenerationJob.request_metadata
  9. submit via the adapter with a budget pre-check
  10. on completion, save outputs + ResourceUsageEvents (see complete_job)

Paid fallback is NEVER silent: selecting a paid provider without
``allow_paid_fallback=True`` raises PaidFallbackApprovalRequired.

Adapters never log secret material, and outbound HTTP is restricted by an SSRF
guard to the provider's own configured base_url host.
"""
import asyncio
import hashlib
import json
import uuid
from decimal import Decimal
from typing import Protocol
from urllib.parse import urlparse

from core.secrets import decrypt_value
from django.conf import settings
from django.db.models import DecimalField, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

TASK_TYPES = ("image", "video", "narration", "music", "captions", "upscale")
PAID_DEPLOYMENT_TYPES = ("cloud_gpu", "external")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
class ProviderError(Exception):
    code = "PROVIDER_ERROR"
    message = "Provider request failed."
    retryable = True

    def __init__(self, message=None, code=None, retryable=None):
        super().__init__(message or self.message)
        if code:
            self.code = code
        if retryable is not None:
            self.retryable = retryable


class BudgetExceeded(ProviderError):
    code = "BUDGET_EXCEEDED"
    message = "A budget limit was exceeded."
    retryable = False


class PaidFallbackApprovalRequired(ProviderError):
    code = "PAID_FALLBACK_APPROVAL_REQUIRED"
    message = "Routing to a paid provider requires explicit approval."
    retryable = False


# ---------------------------------------------------------------------------
# Adapter protocol + HTTP base
# ---------------------------------------------------------------------------
class GenerationProvider(Protocol):
    async def health_check(self) -> dict: ...
    async def capabilities(self) -> dict: ...
    async def estimate(self, task_type: str, requirements: dict) -> dict: ...
    async def submit(self, task_type: str, payload: dict) -> dict: ...
    async def get_status(self, external_job_id: str) -> dict: ...
    async def cancel(self, external_job_id: str) -> dict: ...
    async def fetch_outputs(self, external_job_id: str) -> list: ...


class HttpProviderAdapter:
    """Base adapter over requests. Sync I/O inside async methods keeps the
    gateway usable from synchronous Django views and the sqlite test suite."""

    timeout = 30
    max_retries = 3

    def __init__(self, provider, secret_value=None):
        self.provider = provider
        self._secret = secret_value  # never logged, never included in errors
        host = urlparse(provider.base_url or "").hostname or ""
        if not host:
            raise ProviderError("Provider base_url is not a valid URL.",
                                code="INVALID_PROVIDER_URL", retryable=False)
        self._allowed_host = host.lower()

    # -- SSRF guard ---------------------------------------------------------
    def _guard_url(self, url):
        if urlparse(url).hostname.lower() != self._allowed_host:
            raise ProviderError("Outbound request blocked by SSRF guard.",
                                code="SSRF_BLOCKED", retryable=False)

    def _auth_headers(self):
        return {}

    def _request(self, method, path, **kwargs):
        import requests

        url = self.provider.base_url.rstrip("/") + path
        self._guard_url(url)
        headers = dict(kwargs.pop("headers", {}) or {})
        headers.update(self._auth_headers())
        last_error = None
        for _ in range(self.max_retries):
            try:
                response = requests.request(method, url, headers=headers,
                                            timeout=self.timeout, **kwargs)
            except requests.RequestException as exc:
                last_error = ProviderError(
                    f"Provider connection failed: {type(exc).__name__}", retryable=True)
                continue
            if response.status_code == 429 or response.status_code >= 500:
                last_error = ProviderError(
                    f"Provider HTTP {response.status_code} (retryable)",
                    code=f"HTTP_{response.status_code}", retryable=True)
                continue
            if response.status_code >= 400:
                raise ProviderError(
                    f"Provider HTTP {response.status_code}",
                    code=f"HTTP_{response.status_code}", retryable=False)
            return response
        raise last_error or ProviderError("Provider request failed.")

    # -- protocol -------------------------------------------------------------
    async def health_check(self):
        raise NotImplementedError

    async def capabilities(self):
        return dict(self.provider.capabilities or {})

    async def estimate(self, task_type, requirements):
        return {"estimated_cost_usd": "0", "eta_seconds": 60}

    async def submit(self, task_type, payload):
        raise NotImplementedError

    async def get_status(self, external_job_id):
        raise NotImplementedError

    async def cancel(self, external_job_id):
        return {"canceled": True}

    async def fetch_outputs(self, external_job_id):
        return []


class ComfyUIAdapter(HttpProviderAdapter):
    async def health_check(self):
        try:
            response = self._request("GET", "/system_stats")
            detail = response.json() if response.content else {}
            return {"status": "HEALTHY", "detail": detail}
        except ProviderError as exc:
            return {"status": "UNHEALTHY", "detail": {"code": exc.code, "message": str(exc)}}

    async def estimate(self, task_type, requirements):
        price = (self.provider.capabilities or {}).get("price_per_task_usd", 0)
        if self.provider.deployment_type == "local":
            price = 0
        return {"estimated_cost_usd": str(price), "eta_seconds": 120}

    async def submit(self, task_type, payload):
        response = self._request("POST", "/prompt", json={"prompt": payload.get("workflow", {})})
        prompt_id = (response.json() or {}).get("prompt_id")
        if not prompt_id:
            raise ProviderError("ComfyUI did not return a prompt_id.", code="NO_PROMPT_ID")
        return {"external_job_id": prompt_id}

    async def get_status(self, external_job_id):
        response = self._request("GET", f"/history/{external_job_id}")
        data = response.json() or {}
        if external_job_id in data:
            return {"status": "COMPLETED", "detail": {"outputs": len(data[external_job_id].get("outputs", {}))}}
        return {"status": "RUNNING"}

    async def fetch_outputs(self, external_job_id):
        response = self._request("GET", f"/history/{external_job_id}")
        outputs = ((response.json() or {}).get(external_job_id) or {}).get("outputs", {})
        results = []
        for node_outputs in outputs.values():
            for item in node_outputs.get("images", []) + node_outputs.get("gifs", []):
                view = self._request(
                    "GET",
                    f"/view?filename={item['filename']}&subfolder={item.get('subfolder', '')}&type={item.get('type', 'output')}",
                )
                results.append({
                    "filename": item["filename"],
                    "mime_type": view.headers.get("Content-Type", "application/octet-stream"),
                    "content": view.content,
                })
        return results


class OpenAICompatibleAdapter(HttpProviderAdapter):
    _ENDPOINTS = {
        "image": "/v1/images/generations",
        "video": "/v1/videos",
        "narration": "/v1/audio/speech",
    }

    def _auth_headers(self):
        if self._secret:
            return {"Authorization": f"Bearer {self._secret}"}
        return {}

    async def health_check(self):
        try:
            self._request("GET", "/v1/models")
            return {"status": "HEALTHY", "detail": {}}
        except ProviderError as exc:
            return {"status": "UNHEALTHY", "detail": {"code": exc.code, "message": str(exc)}}

    async def estimate(self, task_type, requirements):
        price = (self.provider.capabilities or {}).get("price_per_task_usd", "0.05")
        return {"estimated_cost_usd": str(price), "eta_seconds": 90}

    async def submit(self, task_type, payload):
        endpoint = self._ENDPOINTS.get(task_type, "/v1/generations")
        response = self._request("POST", endpoint, json=payload.get("params", {}))
        data = response.json() or {}
        job_id = data.get("id") or data.get("job_id")
        if not job_id:
            raise ProviderError("Provider did not return a job id.", code="NO_JOB_ID")
        return {"external_job_id": str(job_id), "response": data}

    async def get_status(self, external_job_id):
        response = self._request("GET", f"/v1/jobs/{external_job_id}")
        data = response.json() or {}
        return {"status": str(data.get("status", "running")).upper(), "detail": data}


class LocalInferenceAdapter(OpenAICompatibleAdapter):
    async def estimate(self, task_type, requirements):
        return {"estimated_cost_usd": "0", "eta_seconds": 60}


class ExternalAPIAdapter(OpenAICompatibleAdapter):
    pass


ADAPTERS = {
    "comfyui": ComfyUIAdapter,
    "local_inference": LocalInferenceAdapter,
    "external_api": ExternalAPIAdapter,
}


def get_adapter(provider):
    secret_value = None
    if provider.secret_reference_id:
        raw = bytes(provider.secret_reference.encrypted_value or b"")
        if raw:
            secret_value = decrypt_value(raw)
    adapter_cls = ADAPTERS.get(provider.adapter_type)
    if adapter_cls is None:
        raise ProviderError(f"Unknown adapter type: {provider.adapter_type}",
                            code="UNKNOWN_ADAPTER", retryable=False)
    return adapter_cls(provider, secret_value)


# ---------------------------------------------------------------------------
# Budget enforcement (server-side, evaluated global -> channel -> project -> workflow)
# ---------------------------------------------------------------------------
def _spend_total(queryset):
    return queryset.aggregate(
        total=Coalesce(Sum(Coalesce("actual_cost", "estimated_cost")),
                       Value(Decimal("0")), output_field=DecimalField())
    )["total"] or Decimal("0")


def check_budget_hierarchy(channel, project=None, workflow_id=None, estimated_cost=Decimal("0")):
    """Raise BudgetExceeded when any applicable budget limit would be breached."""
    from .models import Budget, ResourceUsageEvent

    estimated_cost = Decimal(str(estimated_cost))
    today = timezone.now().date()
    month_start = today.replace(day=1)

    scopes = [("global", None)]
    if channel is not None:
        scopes.append(("channel", channel.id))
    if project is not None:
        scopes.append(("project", project.id))
    if workflow_id:
        scopes.append(("workflow", workflow_id))

    for scope_type, scope_id in scopes:
        try:
            budget = Budget.objects.get(scope_type=scope_type, scope_id=scope_id)
        except Budget.DoesNotExist:
            continue
        limits = budget.limits or {}
        events = ResourceUsageEvent.objects.filter(resource_type="api_spend_usd")
        if scope_type == "channel":
            events = events.filter(job__project__channel_id=scope_id)
        elif scope_type == "project":
            events = events.filter(job__project_id=scope_id)
        elif scope_type == "workflow":
            events = events.filter(metadata__workflow_id=str(scope_id))

        daily_limit = limits.get("max_api_spend_daily")
        if daily_limit is not None:
            spent = _spend_total(events.filter(occurred_at__date=today))
            if spent + estimated_cost > Decimal(str(daily_limit)):
                raise BudgetExceeded(
                    f"Daily API spend limit exceeded for {scope_type} scope "
                    f"(spent {spent}, limit {daily_limit}).")

        monthly_limit = limits.get("max_api_spend_monthly")
        if monthly_limit is not None:
            spent = _spend_total(events.filter(occurred_at__date__gte=month_start))
            if spent + estimated_cost > Decimal(str(monthly_limit)):
                raise BudgetExceeded(
                    f"Monthly API spend limit exceeded for {scope_type} scope "
                    f"(spent {spent}, limit {monthly_limit}).")

        per_video_limit = limits.get("max_spend_per_video")
        if per_video_limit is not None and project is not None:
            spent = _spend_total(events.filter(job__project_id=project.id))
            if spent + estimated_cost > Decimal(str(per_video_limit)):
                raise BudgetExceeded(
                    f"Per-video spend limit exceeded (spent {spent}, limit {per_video_limit}).")
    return True


def _has_capacity(provider):
    """GPU capacity + queue depth from the global budget (fallback: settings)."""
    from .models import Budget, GenerationJob

    limit = settings.AI_WORKER_CONCURRENCY
    try:
        budget = Budget.objects.get(scope_type="global", scope_id=None)
        limit = int((budget.limits or {}).get("max_concurrent_gpu_jobs", limit))
    except (Budget.DoesNotExist, ValueError, TypeError):
        pass
    running = GenerationJob.objects.filter(provider=provider, status="RUNNING").count()
    return running < max(limit, 1)


def _parse_resolution(value):
    try:
        width, height = str(value).lower().split("x")
        return int(width), int(height)
    except (ValueError, AttributeError):
        return None


def _meets_requirements(capabilities, model, requirements):
    caps = capabilities or {}
    required_res = _parse_resolution(requirements.get("max_resolution") or requirements.get("resolution"))
    max_res = _parse_resolution(caps.get("max_resolution"))
    if required_res and max_res:
        if required_res[0] > max_res[0] or required_res[1] > max_res[1]:
            return False
    max_duration = caps.get("max_duration_s")
    wanted = requirements.get("duration_seconds") or requirements.get("max_duration_s")
    if max_duration is not None and wanted is not None:
        try:
            if float(wanted) > float(max_duration):
                return False
        except (TypeError, ValueError):
            return False
    return True


def _select_candidate(estimates, policy):
    if policy == "quality-first":
        return max(estimates, key=lambda e: (e["quality"], -e["cost"]))
    if policy == "lowest-cost":
        return min(estimates, key=lambda e: (e["cost"], -e["quality"]))
    if policy == "manual":
        return estimates[0]
    # local-first and hybrid-fallback: prefer local, then cheapest
    return min(estimates, key=lambda e: (0 if e["provider"].deployment_type == "local" else 1, e["cost"]))


# ---------------------------------------------------------------------------
# Routing entry point
# ---------------------------------------------------------------------------
def route_generation(task_type, requirements, channel, project=None, scene=None,
                     workflow_id=None, policy=None, idempotency_key=None,
                     allow_paid_fallback=False, requested_model_id=None,
                     request_metadata=None):
    """Route a generation task to a provider and submit it. Returns GenerationJob."""
    from .models import AIModel, GenerationJob, Provider

    # 1. validate task
    if task_type not in TASK_TYPES:
        raise ProviderError(f"Unsupported task type: {task_type}",
                            code="INVALID_TASK_TYPE", retryable=False)

    # idempotency: identical request_hash + idempotency_key returns the existing job
    if idempotency_key:
        existing = GenerationJob.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

    policy = policy or (channel.automation_config or {}).get("routing_policy", "local-first")
    requirements = dict(requirements or {})

    # 2-5. match capabilities, apply channel restrictions, exclude unhealthy, capacity
    automation = channel.automation_config or {}
    allowed_models = automation.get("allowed_models")
    prohibited_models = set(automation.get("prohibited_models") or [])
    candidates = []
    for provider in Provider.objects.filter(enabled=True).prefetch_related("models"):
        if provider.health_status == "UNHEALTHY":
            continue
        caps = provider.capabilities or {}
        if task_type not in (caps.get("task_types") or []):
            continue
        for model in provider.models.filter(enabled=True, task_type=task_type):
            ident = model.model_identifier
            if allowed_models is not None and ident not in allowed_models:
                continue
            if ident in prohibited_models:
                continue
            if not _meets_requirements(caps, model, requirements):
                continue
            if not _has_capacity(provider):
                continue
            candidates.append((provider, model))

    if policy == "manual":
        if not requested_model_id:
            raise ProviderError("Manual policy requires an explicit model_id.",
                                code="MODEL_REQUIRED", retryable=False)
        candidates = [c for c in candidates
                      if str(c[1].id) == str(requested_model_id)
                      or c[1].model_identifier == requested_model_id]
        if not candidates:
            raise ProviderError("Requested model is not available.",
                                code="MODEL_UNAVAILABLE", retryable=False)
    if not candidates:
        raise ProviderError("No capable provider is currently available.",
                            code="NO_CAPABLE_PROVIDER", retryable=False)

    # 6. estimate cost for every candidate
    estimates = []
    for provider, model in candidates:
        adapter = get_adapter(provider)
        estimate = asyncio.run(adapter.estimate(task_type, requirements))
        cost = Decimal(str(estimate.get("estimated_cost_usd", "0")))
        quality = ((model.quality_profile or {}).get("rank") or 0)
        estimates.append({"provider": provider, "model": model, "adapter": adapter,
                          "cost": cost, "quality": quality})

    # 7. select per policy
    chosen = _select_candidate(estimates, policy)
    provider, model, adapter, cost = (chosen["provider"], chosen["model"],
                                     chosen["adapter"], chosen["cost"])

    # paid fallback is never silent
    is_paid = provider.deployment_type in PAID_DEPLOYMENT_TYPES or cost > 0
    if is_paid and not allow_paid_fallback:
        raise PaidFallbackApprovalRequired(
            f"Selected provider '{provider.name}' is a paid fallback; "
            "re-submit with allow_paid_fallback=true or approve the paid fallback.")

    # 9. budget pre-check (server-side, before any spend)
    check_budget_hierarchy(channel, project, workflow_id, estimated_cost=cost)

    # 8. persist the routing decision
    request_hash = hashlib.sha256(
        json.dumps({"task": task_type, "req": requirements,
                    "channel": str(channel.id)}, sort_keys=True).encode()
    ).hexdigest()
    routing = {
        "policy": policy,
        "task_type": task_type,
        "requirements": requirements,
        "selected": {"provider": provider.name, "provider_id": str(provider.id),
                     "model": model.model_identifier, "estimated_cost_usd": str(cost)},
        "candidates": [{"provider": e["provider"].name, "model": e["model"].model_identifier,
                        "estimated_cost_usd": str(e["cost"])} for e in estimates],
        "paid_fallback": is_paid,
    }
    job = GenerationJob.objects.create(
        project=project, scene=scene, provider=provider, model=model,
        task_type=task_type, request_hash=request_hash,
        request_metadata={**(request_metadata or {}), "routing": routing},
        status="QUEUED", idempotency_key=idempotency_key or uuid.uuid4().hex,
        estimated_cost=cost,
    )
    try:
        result = asyncio.run(adapter.submit(task_type, {"params": requirements,
                                                        "workflow_id": workflow_id}))
        job.external_job_id = result.get("external_job_id")
        job.status = "RUNNING"
        job.started_at = timezone.now()
        job.attempt_count += 1
    except ProviderError as exc:
        job.status = "FAILED"
        job.error_code = exc.code
        job.error_message = str(exc)[:500]
    job.save()
    return job


def complete_job(job, outputs, actual_cost=None):
    """Persist adapter outputs as Assets + GenerationOutputs and record usage.

    Called when a generation finishes (polling loop or webhook).
    """
    import hashlib as _hashlib

    from projects.models import Asset

    from .models import GenerationOutput, ResourceUsageEvent

    assets = []
    for index, output in enumerate(outputs or []):
        content = output.get("content", b"")
        asset = Asset.objects.create(
            project=job.project, scene=job.scene,
            asset_type="VIDEO" if job.task_type == "video" else "IMAGE",
            object_key=output.get("object_key") or
            f"generated/{job.id}/{index}-{output.get('filename', 'output.bin')}",
            mime_type=output.get("mime_type", "application/octet-stream"),
            size_bytes=len(content),
            sha256=_hashlib.sha256(content).hexdigest() if content else "",
            source_type="GENERATED", status="READY",
            license_metadata=(job.model.license_metadata if job.model else {}),
            model_metadata={
                "provider": job.provider.name,
                "model": job.model.model_identifier if job.model else "",
                "external_job_id": job.external_job_id,
            },
        )
        GenerationOutput.objects.create(job=job, asset=asset, output_index=index,
                                        metadata=output.get("metadata", {}))
        assets.append(asset)
    if actual_cost is not None:
        job.actual_cost = Decimal(str(actual_cost))
    job.status = "COMPLETED"
    job.completed_at = timezone.now()
    job.save()
    ResourceUsageEvent.objects.create(
        provider=job.provider, job=job,
        resource_type="api_spend_usd" if job.provider.deployment_type in PAID_DEPLOYMENT_TYPES else "local_gpu_seconds",
        quantity=Decimal("1"), unit="job",
        estimated_cost=job.estimated_cost,
        actual_cost=job.actual_cost,
        metadata={"task_type": job.task_type},
    )
    return assets
