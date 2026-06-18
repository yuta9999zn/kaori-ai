"""
F-034 Frameworks — orchestration layer.

Per generated framework run:

  1. Validate ``framework_code`` against the Python registry.
  2. Insert a ``queued`` row.
  3. Spawn ``run_framework`` as ``asyncio.create_task`` — return
     ``run_id`` to the caller (router returns 202).
  4. Background task: render the system_prompt, call
     ``llm_router.complete_structured(output_schema=template.schema)``
     (Issue #3 path), persist content + narrative, flip status='ready'.
  5. Failure modes (consent denied, structured-output gives up after
     repair, network) flip status='failed' with a captured error.

Same shape as F-038 reports/service.py; the divergences are:
  * No template DB lookup — registry is in-process Python.
  * No Kafka event yet (frameworks aren't a downstream-consumer
    surface in v0; can be added when a consumer materialises).
  * No notification_outbox — frameworks are a synchronous-feel
    feature with the FE polling, not a "we'll email you" feature.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from jinja2 import Template

from ..engine.llm_router import llm_router
from ..shared.db import acquire_for_tenant
from . import repository, templates

log = structlog.get_logger()


# ─── Public API ──────────────────────────────────────────────────

async def queue_framework(
    *,
    enterprise_id: str,
    framework_code: str,
    question: str,
    source_ref: Optional[str],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued framework_runs row and return its id. The
    router spawns ``run_framework`` as a background task right after.

    Validates framework_code against the in-process registry BEFORE
    inserting so a typo doesn't leave a zombie 'queued' row no worker
    can resolve. Same pattern as F-038 ``queue_report``."""
    if templates.get_template(framework_code) is None:
        raise UnknownFrameworkError(
            f"unknown framework_code '{framework_code}' "
            f"(allowed: {sorted(templates.ALLOWED_CODES)})"
        )

    if not question or not question.strip():
        raise InvalidFrameworkInputError("question is required")
    if len(question) > 2000:
        raise InvalidFrameworkInputError("question must be ≤ 2000 characters")

    async with acquire_for_tenant(enterprise_id) as conn:
        run_id = await repository.create_run(
            conn,
            enterprise_id=UUID(enterprise_id),
            framework_code=framework_code,
            question=question.strip(),
            source_ref=(source_ref or None),
            consent_external=consent_external,
            created_by_user=created_by_user,
        )
    return run_id


async def run_framework(*, enterprise_id: str, run_id: UUID) -> None:
    """Execute end-to-end. Designed to be spawned via
    ``asyncio.create_task`` from the router; captures every failure
    inside the function — never re-raises."""
    try:
        await _run_inner(enterprise_id=enterprise_id, run_id=run_id)
    except Exception as exc:
        log.exception(
            "frameworks.background_task_crashed",
            run_id=str(run_id), error=str(exc),
        )
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await repository.mark_failed(conn, run_id, str(exc))
        except Exception as inner:
            log.error(
                "frameworks.mark_failed_also_crashed",
                run_id=str(run_id), error=str(inner),
            )


async def _run_inner(*, enterprise_id: str, run_id: UUID) -> None:
    # Load + flip running.
    async with acquire_for_tenant(enterprise_id) as conn:
        run = await repository.fetch_run(conn, run_id)
        if run is None:
            log.warning("frameworks.run.row_missing", run_id=str(run_id))
            return
        await repository.mark_running(conn, run_id)

    template = templates.get_template(run["framework_code"])
    if template is None:
        # Should never happen — queue_framework validated already.
        # Defensive: framework_code might have been removed from the
        # registry between queue + run.
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_failed(
                conn, run_id, "framework code no longer registered",
            )
        return

    rendered_prompt = _render_prompt(template["system_prompt"], run)

    try:
        parsed = await llm_router.complete_structured(
            prompt=rendered_prompt,
            task=f"frameworks.{run['framework_code']}",
            output_schema=template["output_schema"],
            enterprise_id=enterprise_id,
            consent_external=bool(run["consent_external"]),
            max_tokens=2500,
        )
    except Exception as exc:
        # httpx timeout exceptions str() to '' — persisting that leaves the
        # UI showing "failed" with no reason (the pilot 7B box routinely
        # exceeds LLM_TIMEOUT_S on a 2500-token structured framework prompt).
        # Always record a clear, user-facing message so the FE can surface
        # *why* it failed and offer retry / external-AI.
        detail = str(exc).strip()
        exc_name = type(exc).__name__
        if not detail or "timeout" in exc_name.lower() or "timeout" in detail.lower():
            message = (
                "Qwen nội bộ không kịp hoàn tất phân tích trong thời gian cho phép "
                "(model 7B pilot quá tải cho khung này). Hãy thử lại, hoặc bật "
                "'AI ngoài' cho các phân tích nặng."
            )
        else:
            message = f"Phân tích thất bại ({exc_name}): {detail}"
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_failed(conn, run_id, message)
        log.warning(
            "frameworks.run.llm_failed",
            run_id=str(run_id), code=run["framework_code"],
            error=detail or exc_name,
        )
        return

    narrative = templates.extract_narrative(run["framework_code"], parsed)

    async with acquire_for_tenant(enterprise_id) as conn:
        await repository.mark_ready(
            conn, run_id, content_json=parsed, narrative=narrative,
        )

    log.info(
        "frameworks.run.ready",
        run_id=str(run_id), code=run["framework_code"],
    )


# ─── Helpers ─────────────────────────────────────────────────────

def _render_prompt(system_prompt: str, run: dict) -> str:
    """Substitute the run's ``question`` + ``source_ref`` into the
    framework's system_prompt. Jinja with autoescape off — the LLM
    sees plain text, not HTML."""
    return Template(system_prompt).render(
        question=run["question"],
        source_ref=run["source_ref"] or "(không xác định)",
    )


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ─── Errors ──────────────────────────────────────────────────────

class UnknownFrameworkError(Exception):
    """Raised when ``framework_code`` is not in the registry. Router
    converts to 400."""


class InvalidFrameworkInputError(Exception):
    """Raised on bad question length / empty input. Router converts
    to 400."""
