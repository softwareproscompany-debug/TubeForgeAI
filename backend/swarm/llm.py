"""Text completion through the existing provider gateway.

Important context: ``providers/gateway.py`` is a *media generation* gateway —
its ``TASK_TYPES`` cover image/video/narration/music/captions/upscale and it
exposes no text LLM completion function. The audit already flagged that
``generate_plan`` is a heuristic that ignores the prompt.

To satisfy the swarm's need for agent text completions WITHOUT building a
second LLM client (no new SDK dependencies, no new credential plumbing), this
module reuses the gateway's own machinery:

- the ``Provider`` model and ``get_adapter(provider)`` — encrypted-secret
  auth headers, the SSRF host guard, retries, and timeouts all come along;
- only the OpenAI-compatible adapters (``local_inference`` / ``external_api``)
  are eligible, because they already speak the standard
  ``/v1/chat/completions`` endpoint;
- ``check_budget_hierarchy`` keeps text spend inside the server-side budgets.

Follow-up (no real LLM calls work until this lands): register a ``"text"``
task type in the media gateway and configure a local text provider
(e.g. self-hosted Ollama with the ``local_inference`` adapter) — then the
selector below will pick it up automatically. Until then ``complete_text``
raises a clear ``ProviderError`` and the orchestrator turns that into a
failed run with a readable error, never a hang or a silent stub.
"""

import asyncio
from decimal import Decimal

from providers.gateway import ProviderError, check_budget_hierarchy, get_adapter

#: Adapter types whose HTTP surface is OpenAI-compatible (chat completions).
TEXT_ADAPTER_TYPES = ("local_inference", "external_api")


def _select_text_provider():
    """Local-first provider selection, mirroring the media gateway policy."""
    from providers.models import Provider

    base = Provider.objects.filter(
        enabled=True, adapter_type__in=TEXT_ADAPTER_TYPES
    ).exclude(health_status="UNHEALTHY")
    provider = base.filter(deployment_type="local").first() or base.first()
    if provider is None:
        raise ProviderError(
            "No text-capable LLM provider is configured. Add a local "
            "inference provider (e.g. Ollama) with the 'local_inference' "
            "adapter to enable the agent swarm.",
            code="NO_TEXT_PROVIDER",
            retryable=False,
        )
    return provider


def _resolve_model_name(provider, agent):
    """Explicit agent model wins; otherwise the provider's first enabled
    model; otherwise the literal string the server expects (Ollama accepts
    arbitrary names on /v1/chat/completions)."""
    if agent.model and agent.model != "auto":
        return agent.model
    model = provider.models.filter(enabled=True).first()
    return model.model_identifier if model else "default"


def complete_text(
    *,
    agent,
    prompt,
    history=None,
    project=None,
    channel=None,
    temperature=0.7,
    max_tokens=1600,
):
    """Run one agent completion through the gateway's provider adapters.

    Returns the assistant message content as ``str``. Raises ``ProviderError``
    (including ``BudgetExceeded`` and ``NO_TEXT_PROVIDER``) on any failure —
    the orchestrator converts these into a failed ``SwarmRun``.
    """
    provider = _select_text_provider()
    model_name = _resolve_model_name(provider, agent)

    # Server-side budget gate, same as media jobs (cost 0 for local providers).
    channel = channel or (project.channel if project else None)
    estimated_cost = (
        Decimal(0) if provider.deployment_type == "local" else Decimal("0.01")
    )
    check_budget_hierarchy(channel, project, estimated_cost=estimated_cost)

    messages = [{"role": "system", "content": agent.system_prompt}]
    for turn in history or []:
        messages.append({"role": turn.get("role", "user"), "content": turn["content"]})
    messages.append({"role": "user", "content": prompt})

    adapter = get_adapter(provider)
    try:
        response = asyncio.run(
            adapter._request(
                "POST",
                "/v1/chat/completions",
                json={
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                },
            )
        )
    except ProviderError:
        raise
    except Exception as exc:
        raise ProviderError(
            f"Text completion request failed: {type(exc).__name__}",
            code="TEXT_COMPLETION_FAILED",
            retryable=True,
        ) from exc

    try:
        data = response.json()
        content = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError(
            "LLM provider returned an unparseable chat response.",
            code="BAD_TEXT_RESPONSE",
            retryable=True,
        ) from exc
    if not content:
        raise ProviderError(
            "LLM provider returned an empty completion.",
            code="EMPTY_TEXT_RESPONSE",
            retryable=True,
        )
    return content.strip()
