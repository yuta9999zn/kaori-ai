"""
F-033 Multi-tier Analysis — orchestration layer (PR A).

Two tiers ship in PR A:

    basic        → 1 pipeline_run + N templates  (delegate to wizard runner)
    intermediate → 2-5 silver/gold sources + 1 framework  (LLM with multi-source context)

Advanced tier + cross-workspace + approval queue land in PR B.

Pattern mirrors F-034 frameworks/service.py:
  * router calls ``queue_run_*`` (sync, transactional INSERT).
  * router schedules ``run_basic`` / ``run_intermediate`` as
    asyncio.create_task and returns 202.
  * background task captures all failures inside the function — never
    re-raises so a bug doesn't crash the FastAPI loop.

Why intermediate doesn't actually JOIN data
============================================
PR A's intermediate engine prompts the LLM with ``source_ids`` as
human-readable labels — e.g. "silver dataset rfm_q3_2026 (12k rows)".
The LLM produces a framework analysis grounded in those labels.

A "real" multi-source JOIN (load N silver/gold dataframes, run
correlation across them, feed numeric findings into the LLM) is a
heavier engine — it's the right home for F-035 Cohort Retention which
ships next. PR A keeps the surface honest by labelling output as
"intermediate" and not faking quantitative findings; pilots see SWOT
across multiple datasets, not made-up correlation coefficients.
"""
from __future__ import annotations

from typing import Optional
from uuid import UUID

import structlog
from jinja2 import Template

from ..reasoning.legacy_analytics.runner import run_analysis_for_run
from ..engine.llm_router import llm_router
from ..frameworks import templates as framework_templates
from ..shared.audit import log_decision
from ..shared.db import acquire_for_tenant
from ..shared.kafka_producer import emit
from ..shared import kafka_topics
from . import repository

log = structlog.get_logger()


# ─── Errors ──────────────────────────────────────────────────────


class InvalidRequestError(Exception):
    """Service-layer validation failure — router converts to 400."""


class TierNotImplementedError(Exception):
    """Tier is recognised in the schema but not wired in this PR.
    Router converts to 501. Used to gate `advanced` until PR B ships."""


# ─── Public API ──────────────────────────────────────────────────


async def queue_basic(
    *,
    enterprise_id: str,
    pipeline_run_id: UUID,
    templates_: list[str],
    question: Optional[str],
    config: Optional[dict],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued basic-tier row + emit `tier.started` event.
    Caller schedules ``run_basic`` next as a background task."""
    if not templates_:
        raise InvalidRequestError("templates is required for tier=basic")
    if len(templates_) > 10:
        raise InvalidRequestError("at most 10 templates per basic run")

    async with acquire_for_tenant(enterprise_id) as conn:
        run_id = await repository.create_basic_run(
            conn,
            enterprise_id=UUID(enterprise_id),
            pipeline_run_id=pipeline_run_id,
            templates_=templates_,
            question=(question or None),
            config=config,
            consent_external=consent_external,
            created_by_user=created_by_user,
        )

    await _emit_started(
        run_id=run_id, enterprise_id=enterprise_id,
        tier="basic", scope="single", framework=None,
    )
    return run_id


async def queue_advanced(
    *,
    enterprise_id: str,
    framework: str,
    question: str,
    source_ids: list[dict],
    workspace_ids: Optional[list[str]],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> dict:
    """Insert a queued advanced-tier row + decide approval gate.

    K-4 invariant — refuse if consent_external is false. The DB CHECK
    catches it too, but the service layer surfaces the friendly 400
    instead of letting Postgres raise a generic constraint error.

    Approval policy (PR B "lite"):
      requires_approval = NOT tenant_settings.consent_external_ai

    Workspaces: PR B today only honours the calling workspace
    (Phase 1 model is one user = one enterprise). The list is stored
    so PR D — when multi-workspace memberships ship — can flip the
    cross-cohort engine on without a migration.

    Returns ``{run_id, requires_approval}`` so the router can shape
    the 202 response with the actual approval state.
    """
    if not consent_external:
        raise InvalidRequestError(
            "tier='advanced' requires consent_external=true (K-4)"
        )
    if framework not in framework_templates.ALLOWED_CODES:
        raise InvalidRequestError(
            f"unknown framework '{framework}' "
            f"(allowed: {sorted(framework_templates.ALLOWED_CODES)})"
        )
    if not question or not question.strip():
        raise InvalidRequestError("question is required for tier=advanced")
    if len(question) > 2000:
        raise InvalidRequestError("question must be ≤ 2000 characters")
    if not isinstance(source_ids, list) or not (2 <= len(source_ids) <= 5):
        raise InvalidRequestError("source_ids must contain 2 to 5 items")

    cleaned: list[dict] = []
    for s in source_ids:
        if not isinstance(s, dict):
            raise InvalidRequestError("source_ids items must be objects")
        layer = s.get("layer")
        ident = s.get("id") or s.get("feature")
        if layer not in {"silver", "gold"}:
            raise InvalidRequestError("source_ids[].layer must be 'silver' or 'gold'")
        if not ident:
            raise InvalidRequestError("source_ids[] missing id/feature")
        cleaned.append({"layer": layer, "id": str(ident), "label": s.get("label")})

    # Workspace ids — PR B accepts the list but degenerates to the
    # current workspace. UUID parse is best-effort; non-UUIDs (the
    # FE placeholder "ws_current") are dropped silently.
    parsed_workspaces: list[UUID] = []
    for w in (workspace_ids or []):
        try:
            parsed_workspaces.append(UUID(str(w)))
        except (ValueError, TypeError):
            continue

    async with acquire_for_tenant(enterprise_id) as conn:
        tenant_consent = await repository.fetch_tenant_consent(
            conn, UUID(enterprise_id),
        )
        # Strict mode = tenant has NOT opted in to external AI at the
        # tenant-settings level. Each advanced run still needs MANAGER
        # blessing in that case. When the tenant has opted in,
        # individual advanced runs go straight to the dispatcher.
        requires_approval = not tenant_consent

        run_id = await repository.create_advanced_run(
            conn,
            enterprise_id=UUID(enterprise_id),
            framework=framework,
            question=question.strip(),
            source_ids=cleaned,
            workspace_ids=parsed_workspaces,
            requires_approval=requires_approval,
            created_by_user=created_by_user,
        )

    await _emit_started(
        run_id=run_id, enterprise_id=enterprise_id,
        tier="advanced", scope="cross", framework=framework,
    )
    return {"run_id": run_id, "requires_approval": requires_approval}


async def approve(
    *,
    enterprise_id: str,
    run_id: UUID,
    approver_user_id: UUID,
) -> bool:
    """Flip approved_by + approved_at on a pending advanced run, then
    spawn the background dispatcher. Returns True on success, False
    when the row didn't exist OR wasn't pending. K-15 audit row
    written by log_decision."""
    async with acquire_for_tenant(enterprise_id) as conn:
        result = await repository.approve_run(
            conn, run_id, approver_user_id=approver_user_id,
        )
    if result is None:
        return False

    await log_decision(
        decision_type="analysis.advanced.approved",
        enterprise_id=enterprise_id,
        subject=str(run_id),
        chosen_value="approved",
        method="manual",
        reasoning=f"approved_by={approver_user_id}",
        run_id=str(run_id),
    )
    return True


async def queue_intermediate(
    *,
    enterprise_id: str,
    framework: str,
    question: str,
    source_ids: list[dict],
    consent_external: bool,
    created_by_user: Optional[UUID],
) -> UUID:
    """Insert a queued intermediate-tier row + emit `tier.started`."""
    if framework not in framework_templates.ALLOWED_CODES:
        raise InvalidRequestError(
            f"unknown framework '{framework}' "
            f"(allowed: {sorted(framework_templates.ALLOWED_CODES)})"
        )
    if not question or not question.strip():
        raise InvalidRequestError("question is required for tier=intermediate")
    if len(question) > 2000:
        raise InvalidRequestError("question must be ≤ 2000 characters")

    if not isinstance(source_ids, list) or not (2 <= len(source_ids) <= 5):
        raise InvalidRequestError("source_ids must contain 2 to 5 items")

    cleaned: list[dict] = []
    for s in source_ids:
        if not isinstance(s, dict):
            raise InvalidRequestError("source_ids items must be objects")
        layer = s.get("layer")
        ident = s.get("id") or s.get("feature")
        if layer not in {"silver", "gold"}:
            raise InvalidRequestError("source_ids[].layer must be 'silver' or 'gold'")
        if not ident:
            raise InvalidRequestError("source_ids[] missing id/feature")
        cleaned.append({"layer": layer, "id": str(ident), "label": s.get("label")})

    async with acquire_for_tenant(enterprise_id) as conn:
        run_id = await repository.create_intermediate_run(
            conn,
            enterprise_id=UUID(enterprise_id),
            framework=framework,
            question=question.strip(),
            source_ids=cleaned,
            consent_external=consent_external,
            created_by_user=created_by_user,
        )

    await _emit_started(
        run_id=run_id, enterprise_id=enterprise_id,
        tier="intermediate", scope="multi", framework=framework,
    )
    return run_id


async def run_basic(*, enterprise_id: str, run_id: UUID) -> None:
    """Background dispatcher for basic tier — delegates to the wizard
    runner. Captures every failure inside; never re-raises."""
    try:
        async with acquire_for_tenant(enterprise_id) as conn:
            run = await repository.fetch_run(conn, run_id)
        if run is None:
            log.warning("multi_tier.basic.row_missing", run_id=str(run_id))
            return

        # The wizard runner owns its own status transitions (queued →
        # running → done|error) on the same analysis_runs row, so we
        # just hand off — no double mark_running here.
        await run_analysis_for_run(
            analysis_run_id=str(run_id),
            run_id=str(run["pipeline_run_id"]),
            enterprise_id=enterprise_id,
            templates=run["templates"],
            config=run["config"] or {},
        )

        # Wizard runner already set completed_at + overview. Re-fetch
        # to grab the final status for the Kafka event.
        async with acquire_for_tenant(enterprise_id) as conn:
            run = await repository.fetch_run(conn, run_id)
        await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status=run["status"])

    except Exception as exc:
        log.exception(
            "multi_tier.basic.crashed",
            run_id=str(run_id), error=str(exc),
        )
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await repository.mark_error(conn, run_id, str(exc))
            await _emit_completed(
                run_id=run_id, enterprise_id=enterprise_id, status="error",
            )
        except Exception as inner:
            log.error(
                "multi_tier.basic.mark_error_crashed",
                run_id=str(run_id), error=str(inner),
            )


async def run_intermediate(*, enterprise_id: str, run_id: UUID) -> None:
    """Background dispatcher for intermediate tier. Wraps the framework
    template + multi-source label context in a single LLM call (Issue
    #3 path: structured output, gateway repairs once on validation
    failure)."""
    try:
        await _run_intermediate_inner(enterprise_id=enterprise_id, run_id=run_id)
    except Exception as exc:
        log.exception(
            "multi_tier.intermediate.crashed",
            run_id=str(run_id), error=str(exc),
        )
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await repository.mark_error(conn, run_id, str(exc))
            await _emit_completed(
                run_id=run_id, enterprise_id=enterprise_id, status="error",
            )
        except Exception as inner:
            log.error(
                "multi_tier.intermediate.mark_error_crashed",
                run_id=str(run_id), error=str(inner),
            )


async def _run_intermediate_inner(*, enterprise_id: str, run_id: UUID) -> None:
    async with acquire_for_tenant(enterprise_id) as conn:
        run = await repository.fetch_run(conn, run_id)
        if run is None:
            log.warning("multi_tier.intermediate.row_missing", run_id=str(run_id))
            return
        await repository.mark_running(conn, run_id)

    framework = run["framework"]
    template = framework_templates.get_template(framework)
    if template is None:
        # Defensive — queue_intermediate validated, but the registry
        # could conceivably drop a code between queue + dispatch.
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_error(conn, run_id, "framework code no longer registered")
        await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status="error")
        return

    source_ref = _format_sources(run["source_ids"] or [])
    rendered = Template(template["system_prompt"]).render(
        question=run["question"],
        source_ref=source_ref,
    )

    parsed: dict
    # Issue #3 was_repaired flag isn't surfaced through llm_router's
    # `complete_structured` return today — the gateway logs it, the
    # router returns just the parsed dict. PR B can promote the flag
    # through the router signature if pilot needs the audit channel;
    # for PR A we leave the column NULL (different from False — None
    # means "not captured" rather than "no repair occurred").
    repaired: Optional[bool] = None
    try:
        parsed = await llm_router.complete_structured(
            prompt=rendered,
            task=f"multi_tier.intermediate.{framework}",
            output_schema=template["output_schema"],
            enterprise_id=enterprise_id,
            consent_external=bool(run["consent_external"]),
            max_tokens=2500,
        )
    except Exception as exc:
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_error(conn, run_id, str(exc))
        await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status="error")
        return

    narrative = framework_templates.extract_narrative(framework, parsed)

    async with acquire_for_tenant(enterprise_id) as conn:
        await repository.mark_done(
            conn, run_id,
            overview=parsed,
            narrative=narrative,
            output_schema_repaired=repaired,
        )

    # K-6 audit — log_decision is best-effort by contract (never raises)
    await log_decision(
        decision_type="analysis.intermediate",
        enterprise_id=enterprise_id,
        subject=str(run_id),
        chosen_value=framework,
        method="llm",
        llm_provider=("external" if run["consent_external"] else "qwen-internal"),
        reasoning=(
            f"framework={framework} "
            f"source_count={len(run['source_ids'] or [])} "
            f"schema_repaired={repaired}"
        ),
        run_id=str(run_id),
    )

    await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status="done")


async def run_advanced(*, enterprise_id: str, run_id: UUID) -> None:
    """Background dispatcher for advanced tier. Same shape as
    run_intermediate but flips ``consent_external=true`` so the
    llm-gateway uses the external provider path (Claude / GPT-4o)
    after PII masking (K-5).

    If ``requires_approval=true`` and ``approved_at IS NULL`` we
    short-circuit — the row stays in 'queued' until the approve
    endpoint flips it. Re-call this function after approval.
    """
    try:
        await _run_advanced_inner(enterprise_id=enterprise_id, run_id=run_id)
    except Exception as exc:
        log.exception(
            "multi_tier.advanced.crashed",
            run_id=str(run_id), error=str(exc),
        )
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await repository.mark_error(conn, run_id, str(exc))
            await _emit_completed(
                run_id=run_id, enterprise_id=enterprise_id, status="error",
            )
        except Exception as inner:
            log.error(
                "multi_tier.advanced.mark_error_crashed",
                run_id=str(run_id), error=str(inner),
            )


async def _run_advanced_inner(*, enterprise_id: str, run_id: UUID) -> None:
    async with acquire_for_tenant(enterprise_id) as conn:
        run = await repository.fetch_run(conn, run_id)
        if run is None:
            log.warning("multi_tier.advanced.row_missing", run_id=str(run_id))
            return

        # Approval gate — short-circuit when the row is awaiting blessing.
        if run["requires_approval"] and run["approved_at"] is None:
            log.info(
                "multi_tier.advanced.awaiting_approval",
                run_id=str(run_id),
            )
            return

        await repository.mark_running(conn, run_id)

    framework = run["framework"]
    template = framework_templates.get_template(framework)
    if template is None:
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_error(conn, run_id, "framework code no longer registered")
        await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status="error")
        return

    source_ref = _format_sources(run["source_ids"] or [])
    rendered = Template(template["system_prompt"]).render(
        question=run["question"],
        source_ref=source_ref,
    )

    parsed: dict
    try:
        parsed = await llm_router.complete_structured(
            prompt=rendered,
            task=f"multi_tier.advanced.{framework}",
            output_schema=template["output_schema"],
            enterprise_id=enterprise_id,
            consent_external=True,  # advanced ALWAYS goes external (K-4 already enforced at queue)
            max_tokens=2500,
        )
    except Exception as exc:
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_error(conn, run_id, str(exc))
        await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status="error")
        return

    narrative = framework_templates.extract_narrative(framework, parsed)

    async with acquire_for_tenant(enterprise_id) as conn:
        await repository.mark_done(
            conn, run_id,
            overview=parsed,
            narrative=narrative,
            output_schema_repaired=None,
        )

    # K-6 audit — explicit `external` provider so cost rollups + the
    # quota counter pick this row up.
    await log_decision(
        decision_type="analysis.advanced",
        enterprise_id=enterprise_id,
        subject=str(run_id),
        chosen_value=framework,
        method="llm",
        llm_provider="external",
        reasoning=(
            f"framework={framework} "
            f"workspace_count={len(run['workspace_ids'] or [])} "
            f"source_count={len(run['source_ids'] or [])}"
        ),
        run_id=str(run_id),
    )

    await _emit_completed(run_id=run_id, enterprise_id=enterprise_id, status="done")


# ─── Helpers ─────────────────────────────────────────────────────


def _format_sources(source_ids: list[dict]) -> str:
    """Render the source list as a Vietnamese label string the LLM
    can ground its analysis on. Two layers handled:

      silver → "Silver dataset <id> (<label>)"
      gold   → "Gold feature <id>"
    """
    if not source_ids:
        return "(không có nguồn)"
    parts: list[str] = []
    for s in source_ids:
        layer = s.get("layer")
        ident = s.get("id")
        label = s.get("label")
        if layer == "silver":
            parts.append(f"Silver dataset {label or ident}")
        elif layer == "gold":
            parts.append(f"Gold feature {ident}")
        else:
            parts.append(str(ident))
    return "; ".join(parts)


async def _emit_started(
    *,
    run_id: UUID,
    enterprise_id: str,
    tier: str,
    scope: str,
    framework: Optional[str],
) -> None:
    try:
        await emit(kafka_topics.ANALYSIS_TIER_STARTED, {
            "analysis_run_id": str(run_id),
            "enterprise_id":   enterprise_id,
            "tier":            tier,
            "scope":           scope,
            "framework":       framework,
        })
    except Exception as exc:  # Kafka outage shouldn't block the run
        log.warning(
            "multi_tier.kafka.started_failed",
            run_id=str(run_id), error=str(exc),
        )


async def _emit_completed(
    *,
    run_id: UUID,
    enterprise_id: str,
    status: str,
) -> None:
    try:
        await emit(kafka_topics.ANALYSIS_TIER_COMPLETED, {
            "analysis_run_id": str(run_id),
            "enterprise_id":   enterprise_id,
            "status":          status,
        })
    except Exception as exc:
        log.warning(
            "multi_tier.kafka.completed_failed",
            run_id=str(run_id), error=str(exc),
        )
