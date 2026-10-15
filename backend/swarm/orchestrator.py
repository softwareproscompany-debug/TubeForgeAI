"""Swarm orchestrator: researcher -> writer -> editor -> publisher, with a
critic reviewing the writer's and editor's outputs.

The pipeline currently runs synchronously inside ``start_run``. Each stage is
a separate method so it can be moved onto a Celery/Temporal task later; the
only shared state between stages is the ``SwarmRun`` row plus the persisted
``AgentMessage`` conversation, which is already queue-safe.
"""

import json
import logging
from typing import ClassVar

from django.utils import timezone

from providers.gateway import ProviderError

from .llm import complete_text
from .models import Agent, AgentMessage, SwarmRun

logger = logging.getLogger(__name__)


class SwarmOrchestrator:
    """Runs one full agent-swarm video planning pass for a project topic."""

    STAGES: ClassVar[tuple] = ("research", "writing", "editing", "publishing")
    #: Stage -> role that produces it.
    STAGE_AGENTS: ClassVar[dict] = {
        "research": "researcher",
        "writing": "writer",
        "editing": "editor",
        "publishing": "publisher",
    }
    #: Critic reviews these producer roles after their stage completes.
    CRITIC_REVIEWED_ROLES: ClassVar[tuple] = ("writer", "editor")
    MAX_REVISION_RETRIES: ClassVar[int] = 3

    def __init__(self):
        self.agents = {agent.role: agent for agent in Agent.objects.all()}

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def start_run(self, project_id, topic):
        """Create the run and execute the pipeline synchronously.

        Returns the ``SwarmRun``. Gateway failures mark the run ``failed``
        with the error stored on ``run.error`` — never raised to the caller.
        """
        from projects.models import Project

        project = Project.objects.select_related("channel").get(pk=project_id)
        run = SwarmRun.objects.create(
            project=project, topic=topic, status="running", current_stage="research"
        )
        try:
            research = self.run_research(run, topic)
            self._advance(run, "writing")
            script = self.run_writing(run, research)
            self._advance(run, "editing")
            package = self.run_editing(run, script)
            self._advance(run, "publishing")
            self.run_publishing(run, package)
            self._finish(run, "completed")
        except ProviderError as exc:
            logger.warning("Swarm run %s failed: %s", run.id, exc)
            self._fail(run, str(exc))
        except Exception as exc:
            logger.exception("Swarm run %s crashed", run.id)
            self._fail(run, f"Unexpected orchestrator error: {exc}")
        return run

    # ------------------------------------------------------------------
    # Stages (each queue-safe on its own)
    # ------------------------------------------------------------------
    def run_research(self, run, topic):
        """Researcher: trending angles, keywords, competitor notes."""
        agent = self._agent("researcher")
        prompt = (
            f"Topic: {topic}\n\n"
            "Research this YouTube video topic. Return ONLY valid JSON with "
            'these keys: "trending_angles" (list of strings), "keywords" '
            '(list of strings), "competitor_notes" (list of strings), '
            '"audience_hooks" (list of strings).'
        )
        self._send(run, None, agent, "task", {"stage": "research", "topic": topic})
        output = self._produce(run, agent, prompt)
        self._broadcast(run, agent, "research", output)
        return output

    def run_writing(self, run, research):
        """Writer: full script from the research, then the critic reviews."""
        agent = self._agent("writer")
        prompt = (
            "Write a YouTube video script from this research.\n\n"
            f"Research: {json.dumps(research)}\n\n"
            'Return ONLY valid JSON with these keys: "title_options" (list '
            'of strings), "hook" (string, first 15 seconds), "chapters" '
            '(list of {"title": str, "script": str}), "ctas" (list of '
            "strings)."
        )
        self._send(run, None, agent, "task", {"stage": "writing"})
        output = self._produce(run, agent, prompt)
        self._broadcast(run, agent, "writing", output)
        return self._critic_review(run, "writing", agent, output)

    def run_editing(self, run, script):
        """Editor: scene breakdown + visual directions, then the critic."""
        agent = self._agent("editor")
        prompt = (
            "Break this script into an edit plan.\n\n"
            f"Script: {json.dumps(script)}\n\n"
            'Return ONLY valid JSON with these keys: "scenes" (list of '
            '{"scene_number": int, "script_segment": str, '
            '"visual_direction": str, "broll_suggestions": list of str, '
            '"duration_seconds": number}), "pacing_notes" (string).'
        )
        self._send(run, None, agent, "task", {"stage": "editing"})
        output = self._produce(run, agent, prompt)
        self._broadcast(run, agent, "editing", output)
        return self._critic_review(run, "editing", agent, output)

    def run_publishing(self, run, package):
        """Publisher: title, description, tags, thumbnail prompt."""
        agent = self._agent("publisher")
        prompt = (
            "Create the publishing package for this video.\n\n"
            f"Edit plan: {json.dumps(package)}\n\n"
            'Return ONLY valid JSON with these keys: "title" (string, max '
            '70 chars), "description" (string with timestamps if long '
            'form), "tags" (list of strings), "thumbnail_prompt" '
            '(string, detailed image prompt), "publish_checklist" (list of '
            "strings)."
        )
        self._send(run, None, agent, "task", {"stage": "publishing"})
        output = self._produce(run, agent, prompt)
        self._broadcast(run, agent, "publishing", output)
        return output

    # ------------------------------------------------------------------
    # Critic loop
    # ------------------------------------------------------------------
    def _critic_review(self, run, stage, producer_agent, output):
        """Critic reviews ``output``; on rejection the producer revises.

        At most ``MAX_REVISION_RETRIES`` revision rounds, then the latest
        output is used regardless (proceed anyway, never stall).
        """
        critic = self._agent("critic")
        attempts = 0
        while True:
            self._send(
                run,
                critic,
                producer_agent,
                "question",
                {
                    "stage": stage,
                    "request": "Review this output for quality and accuracy.",
                    "output": output,
                },
            )
            verdict = self._review_verdict(run, critic, producer_agent, stage, output)
            if verdict.get("approved"):
                return output
            attempts += 1
            if attempts > self.MAX_REVISION_RETRIES:
                logger.warning(
                    "Swarm run %s: %s output rejected %d times; proceeding anyway.",
                    run.id,
                    stage,
                    self.MAX_REVISION_RETRIES,
                )
                return output
            self._send(
                run,
                critic,
                producer_agent,
                "revision_request",
                {
                    "stage": stage,
                    "attempt": attempts,
                    "max_attempts": self.MAX_REVISION_RETRIES,
                    "feedback": verdict.get("feedback", ""),
                },
            )
            prompt = (
                f"Revise your {stage} output based on this critique. Do not "
                f"repeat the same mistakes.\n\nCritique: {verdict.get('feedback', '')}\n\n"
                f"Your previous output: {json.dumps(output)}\n\n"
                "Return ONLY the revised valid JSON (same schema as before)."
            )
            output = self._produce(run, producer_agent, prompt)
            self._broadcast(
                run, producer_agent, stage, output, extra={"revision": attempts}
            )

    def _review_verdict(self, run, critic, producer_agent, stage, output):
        """Ask the critic for a JSON verdict; persist it as an answer."""
        prompt = (
            f"Review this {stage} output strictly, as a YouTube content "
            "quality critic. Score factual consistency, hook strength, and "
            "audience fit.\n\n"
            f"Output: {json.dumps(output)}\n\n"
            'Return ONLY valid JSON: {"approved": bool, "score": number '
            '0-10, "feedback": string}. Reject with specific, actionable '
            "feedback when the output is thin, generic, or inconsistent."
        )
        raw = self._produce(run, critic, prompt)
        verdict = raw if isinstance(raw, dict) else {"text": raw}
        if not isinstance(verdict.get("approved"), bool):
            # Unparseable verdict: fail open rather than stall the pipeline.
            verdict = {
                "approved": True,
                "score": 0,
                "feedback": "Critic verdict was not parseable; auto-approved.",
            }
        self._send(
            run,
            critic,
            producer_agent,
            "answer",
            {"stage": stage, "verdict": verdict},
        )
        return verdict

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------
    def _agent(self, role):
        try:
            return self.agents[role]
        except KeyError:
            raise ProviderError(
                f"Swarm agent with role '{role}' is not seeded.",
                code="AGENT_NOT_SEEDED",
                retryable=False,
            ) from None

    def _produce(self, run, agent, prompt):
        """Call one agent through the gateway, tracking its working state."""
        agent.status = "working"
        agent.save(update_fields=["status"])
        try:
            raw = complete_text(agent=agent, prompt=prompt, project=run.project)
        finally:
            agent.status = "idle"
            agent.save(update_fields=["status"])
        return _parse_json(raw)

    def _send(self, run, from_agent, to_agent, message_type, content):
        return AgentMessage.objects.create(
            swarm_run=run,
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            content=content or {},
        )

    def _broadcast(self, run, agent, stage, output, extra=None):
        content = {"stage": stage, "output": output}
        if extra:
            content.update(extra)
        return self._send(run, agent, None, "result", content)

    def _advance(self, run, stage):
        run.current_stage = stage
        run.save(update_fields=["current_stage"])

    def _finish(self, run, status):
        run.status = status
        run.current_stage = "done"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "current_stage", "completed_at"])

    def _fail(self, run, message):
        run.status = "failed"
        run.error = message[:1000]
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error", "completed_at"])
        for agent in self.agents.values():
            if agent.status != "idle":
                agent.status = "idle"
                agent.save(update_fields=["status"])


def _parse_json(raw):
    """Parse agent output; tolerate code fences, fall back to raw text."""
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"text": raw}
