"""
F-038 Reports — orchestration layer.

Generates a report by:
  1. Resolving the template (built-in OR per-tenant).
  2. Building a context block for the LLM from the tenant's recent
     analysis_runs / gold_features (truncated for prompt size).
  3. Calling llm-gateway via the Issue #3 structured-output path
     (output_schema = the template's schema, gateway validates +
     repairs once on failure).
  4. Updating the report row to ``ready`` (or ``failed`` on
     irrecoverable error).
  5. Emitting ``kaori.reports.generated`` and enqueueing a
     ``report-ready`` notification for the owner.

The whole flow is launched as an asyncio.create_task from the router
so the HTTP request returns 202 immediately. Failures inside the task
are captured into the row's ``last_error`` and emitted with
``status='failed'`` — never lost silently.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from jinja2 import Template

from ..engine.llm_router import llm_router
from ..shared import kafka_topics
from ..shared.db import acquire_for_tenant, get_pool
from ..shared.kafka_producer import emit
from . import repository

log = structlog.get_logger()


# How many recent analysis_runs to summarise in the LLM context. The
# default (10) keeps the prompt under ~3 KB which fits comfortably in
# Qwen 2.5:7b's 32K window with room for the schema + retry prompt.
_CONTEXT_RUN_LIMIT = int(os.getenv("REPORTS_CONTEXT_RUN_LIMIT", "10"))


# ─── Public API ──────────────────────────────────────────────────

async def queue_report(
    *,
    enterprise_id: str,
    template_id: UUID,
    title: str,
    owner_email: str,
    params: dict,
) -> UUID:
    """Insert a queued report row and return its id. The router
    spawns ``run_report`` as a background task right after.

    Tenant-scoped via acquire_for_tenant — the INSERT only sees the
    caller's enterprise_id thanks to RLS."""
    async with acquire_for_tenant(enterprise_id) as conn:
        # Confirm template exists + is visible BEFORE inserting the
        # row, so a typo'd template_id doesn't leave a zombie queued
        # report no worker can resolve.
        template = await repository.fetch_template(conn, template_id)
        if template is None:
            raise TemplateNotFoundError(
                f"template {template_id} not found or not visible to this tenant"
            )

        report_id = await repository.create_report(
            conn,
            enterprise_id=UUID(enterprise_id),
            template_id=template_id,
            title=title,
            owner_email=owner_email,
            params=params,
        )
    return report_id


async def run_report(*, enterprise_id: str, report_id: UUID) -> None:
    """Execute the report end-to-end. Designed to be spawned via
    asyncio.create_task from the router. Captures every failure
    inside the function — never re-raises (no error path can rescue
    a fire-and-forget task)."""
    try:
        await _run_report_inner(enterprise_id=enterprise_id, report_id=report_id)
    except Exception as exc:
        log.exception(
            "reports.background_task_crashed",
            report_id=str(report_id), error=str(exc),
        )
        # Even the "mark failed" write is best-effort here — if the
        # DB is hard-down both writes lose. The earlier mark_running
        # commit means the row at least shows up in the FE as "stuck
        # running" which is recoverable.
        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                await repository.mark_failed(conn, report_id, str(exc))
        except Exception as inner:
            log.error(
                "reports.mark_failed_also_crashed",
                report_id=str(report_id), error=str(inner),
            )


async def _run_report_inner(*, enterprise_id: str, report_id: UUID) -> None:
    # Phase 1: load template + flip status to running.
    async with acquire_for_tenant(enterprise_id) as conn:
        report = await repository.fetch_report(conn, report_id)
        if report is None:
            log.warning(
                "reports.run_report.row_missing",
                report_id=str(report_id),
            )
            return
        template = await repository.fetch_template(conn, report["template_id"])
        if template is None:
            await repository.mark_failed(
                conn, report_id, "template no longer visible"
            )
            return
        await repository.mark_running(conn, report_id)
        context_block = await _build_context_block(conn, report["title"])

    # Phase 2: call llm-gateway with output_schema. Outside the DB tx
    # so a slow LLM doesn't hold a connection for 10+ seconds.
    rendered_system = Template(template["system_prompt"]).render(
        enterprise_name="Kaori AI",  # FUTURE: look up from enterprises table
        period=_resolve_period(report.get("created_at") or _now()),
    )
    user_prompt = (
        f"{rendered_system}\n\n"
        f"--- Dữ liệu tham khảo ({_CONTEXT_RUN_LIMIT} phân tích gần nhất) ---\n"
        f"{context_block}\n\n"
        f"--- Yêu cầu người dùng ---\n"
        f"Tạo báo cáo \"{report['title']}\" theo schema."
    )

    try:
        parsed = await llm_router.complete_structured(
            prompt=user_prompt,
            task="reports.generate",
            output_schema=template["output_schema"],
            enterprise_id=enterprise_id,
            max_tokens=4000,
        )
    except Exception as exc:
        # Gateway failure (consent denied, structured output failed
        # after repair, network). Mark failed + emit failure event so
        # the FE can surface "regenerate?".
        async with acquire_for_tenant(enterprise_id) as conn:
            await repository.mark_failed(conn, report_id, str(exc))
        await _emit_terminal_event(
            report_id=report_id,
            enterprise_id=enterprise_id,
            template_id=report["template_id"],
            title=report["title"],
            owner_email=report["owner_email"],
            status="failed",
        )
        return

    # Phase 3: persist the validated content + a short narrative.
    narrative = _extract_narrative(parsed)
    async with acquire_for_tenant(enterprise_id) as conn:
        await repository.mark_ready(
            conn, report_id, content_json=parsed, narrative=narrative,
        )

    # Phase 4: best-effort downstream signals.
    await _emit_terminal_event(
        report_id=report_id,
        enterprise_id=enterprise_id,
        template_id=report["template_id"],
        title=report["title"],
        owner_email=report["owner_email"],
        status="ready",
    )
    await _enqueue_notification(
        enterprise_id=enterprise_id,
        report_id=report_id,
        title=report["title"],
        owner_email=report["owner_email"],
        narrative=narrative,
    )


# ─── Context building ────────────────────────────────────────────

async def _build_context_block(conn, report_title: str) -> str:
    """Dump the most recent analysis_runs (status='complete') for the
    tenant as a compact list the LLM can ground its narrative in.

    Intentionally narrow — we don't drag in raw silver_rows or
    bronze_files because those are huge and the LLM would either
    truncate or hallucinate around them. analysis_runs.overview JSON
    holds the compressed story already.
    """
    # K-1 isolation note for the tenant-filter lint:
    # This SELECT runs inside acquire_for_tenant(enterprise_id) — see the
    # call site in _run_report_inner — which sets app.enterprise_id on
    # the connection so RLS scopes the rows to this tenant. Adding a
    # SQL-level WHERE enterprise_id would be redundant + would hide a
    # future RLS regression behind belt-and-braces.
    rows = await conn.fetch(
        """
        SELECT id::text AS id, templates, status, completed_at, overview
          FROM analysis_runs                                       -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
         WHERE status = 'complete'
         ORDER BY completed_at DESC NULLS LAST
         LIMIT $1
        """,
        _CONTEXT_RUN_LIMIT,
    )
    if not rows:
        return "(Chưa có phân tích nào hoàn thành — báo cáo sẽ chỉ dựa trên schema mặc định.)"

    blocks = []
    for r in rows:
        overview = r["overview"]
        if isinstance(overview, str):
            try:
                overview = json.loads(overview)
            except json.JSONDecodeError:
                overview = None
        ov_str = (
            json.dumps(overview, ensure_ascii=False, separators=(",", ":"))
            if overview else "(no overview)"
        )
        blocks.append(
            f"- run {r['id']} (templates={r['templates']}, "
            f"completed={r['completed_at']}): {ov_str[:600]}"
        )
    return "\n".join(blocks)


# ─── Helpers ─────────────────────────────────────────────────────

def _resolve_period(created_at: datetime) -> str:
    """Format the report period as Vietnamese 'tháng MM/YYYY'."""
    return created_at.strftime("tháng %m/%Y")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_narrative(parsed: dict) -> Optional[str]:
    """Pull a short text summary from the structured payload to use as
    the email body / FE list-row preview. Looks at the typical fields
    the monthly_summary schema produces; falls back to None."""
    # Trends section is the most prose-heavy in monthly_summary —
    # join the first one's title + summary as the teaser.
    trends = parsed.get("trends") or []
    if trends:
        first = trends[0]
        title = first.get("title", "")
        summary = first.get("summary", "")
        joined = f"{title}: {summary}".strip(": ").strip()
        if joined:
            return joined[:500]
    # Fallback: first recommendation's action.
    recs = parsed.get("recommendations") or []
    if recs:
        action = recs[0].get("action")
        if action:
            return action[:500]
    return None


async def _emit_terminal_event(
    *,
    report_id: UUID,
    enterprise_id: str,
    template_id: UUID,
    title: str,
    owner_email: str,
    status: str,
) -> None:
    """Emit kaori.reports.generated. Best-effort: validation runs at
    the producer side (Issue #4 schema) and a downstream relay outage
    must not roll back the report row."""
    payload = {
        "report_id":     str(report_id),
        "enterprise_id": enterprise_id,
        "template_id":   str(template_id),
        "status":        status,
        "title":         title,
        "owner_email":   owner_email,
    }
    try:
        await emit(kafka_topics.REPORTS_GENERATED, payload)
    except Exception as exc:
        # Schema validation failure here would be a code bug (we
        # control the payload shape) — log loudly so it surfaces.
        log.error(
            "reports.kafka_emit_failed",
            report_id=str(report_id), error=str(exc),
        )


async def _enqueue_notification(
    *,
    enterprise_id: str,
    report_id: UUID,
    title: str,
    owner_email: str,
    narrative: Optional[str],
) -> None:
    """Insert a notification_outbox row so the notification-service
    poller picks it up + sends the email (Issue #6 / PR #110 pattern).
    Same best-effort contract — a downed outbox writer must not roll
    back the report row.
    """
    pool = get_pool()
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    context = {
        "report_title": title,
        "report_url":   f"{frontend_url}/p2/reports/{report_id}",
        "narrative":    narrative or "",
        "generated_at": _now().strftime("%H:%M %d/%m/%Y"),
    }
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notification_outbox
                    (enterprise_id, template, recipient_email, context, source_ref)
                VALUES ($1, $2, $3, $4::jsonb, $5)
                """,
                UUID(enterprise_id),
                "report-ready",
                owner_email,
                json.dumps(context),
                f"report:{report_id}",
            )
    except Exception as exc:
        log.error(
            "reports.notification_enqueue_failed",
            report_id=str(report_id), error=str(exc),
        )


# ─── Distribution (F-038 follow-up) ──────────────────────────────

# Cap on recipients per single distribute() call. 50 is well above
# the realistic "department head + leadership team" use case but low
# enough to keep an accidental "send to everyone" out of the outbox.
_MAX_RECIPIENTS = 50

# Custom message above the default copy. Trim to 500 chars before
# storing/rendering — long text belongs in the report itself.
_CUSTOM_MESSAGE_CHARS = 500


async def distribute_report(
    *,
    enterprise_id: str,
    report_id: UUID,
    recipients: list[str],
    custom_message: Optional[str] = None,
    triggered_by_user: Optional[UUID] = None,
) -> dict:
    """Manually distribute a ready report to additional recipients.

    Per recipient, this enqueues one notification_outbox row with the
    ``report-ready`` template + a report_distributions audit row. The
    poller in notification-service handles SMTP delivery with retries.

    Best-effort per recipient: if one enqueue raises, the row gets
    ``status='failed'`` and the loop continues. Total failure (report
    not ready, no recipients) raises a typed exception the router
    translates to 4xx.

    Returns a summary dict the router renders as JSON:

        {
            "report_id": ...,
            "recipient_count": int,
            "success_count": int,
            "failure_count": int,
            "distributions": [{ recipient, distribution_id, outbox_id, status }]
        }
    """
    deduped = _dedup_emails(recipients)
    if not deduped:
        raise InvalidDistributionError("at least one recipient is required")
    if len(deduped) > _MAX_RECIPIENTS:
        raise InvalidDistributionError(
            f"recipient list capped at {_MAX_RECIPIENTS} (got {len(deduped)})"
        )

    trimmed_message = (
        (custom_message or "").strip()[:_CUSTOM_MESSAGE_CHARS] or None
    )

    # Phase 1: load + validate report. Single tenant-scoped tx so RLS
    # confirms cross-tenant requests get the same 404 as missing rows.
    async with acquire_for_tenant(enterprise_id) as conn:
        report = await repository.fetch_report(conn, report_id)
        if report is None:
            raise ReportNotFoundError(f"report {report_id} not found")
        if report["status"] != "ready":
            raise ReportNotReadyError(
                f"report {report_id} is in status '{report['status']}', "
                f"only 'ready' reports can be distributed"
            )

    # Phase 2: per-recipient enqueue. Outside the load tx so a slow
    # outbox INSERT doesn't pin the read connection. Each enqueue +
    # audit row pair runs in its own short tx via the pool.
    pool = get_pool()
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

    distributions: list[dict] = []
    success_count = 0
    failure_count = 0

    for recipient in deduped:
        outbox_id: Optional[UUID] = None
        status = "pending"
        last_error: Optional[str] = None
        try:
            outbox_id = await _enqueue_distribution_outbox(
                pool=pool,
                enterprise_id=enterprise_id,
                report_id=report_id,
                report_title=report["title"],
                narrative=report.get("narrative"),
                recipient_email=recipient,
                custom_message=trimmed_message,
                frontend_url=frontend_url,
            )
            success_count += 1
        except Exception as exc:
            # Outbox enqueue can fail if e.g. notification_outbox is
            # full or DB connection is dead. Record the failure but
            # keep going — partial success is a useful state.
            log.error(
                "reports.distribute.enqueue_failed",
                report_id=str(report_id),
                recipient=recipient,
                error=str(exc),
            )
            status = "failed"
            last_error = str(exc)
            failure_count += 1

        try:
            async with acquire_for_tenant(enterprise_id) as conn:
                distribution_id = await repository.create_distribution(
                    conn,
                    enterprise_id=UUID(enterprise_id),
                    report_id=report_id,
                    recipient_email=recipient,
                    channel="email",
                    outbox_id=outbox_id,
                    status=status,
                    custom_message=trimmed_message,
                    triggered_by_user=triggered_by_user,
                    last_error=last_error,
                )
        except Exception as exc:
            # Audit row insertion failure is louder than enqueue
            # failure — losing the record means support can't trace
            # "why didn't user X get the email". Log + mark this
            # recipient as failed in the summary even if the outbox
            # row got through.
            log.error(
                "reports.distribute.audit_insert_failed",
                report_id=str(report_id),
                recipient=recipient,
                error=str(exc),
            )
            distribution_id = None
            if status != "failed":
                # Outbox went through but audit failed — surface the
                # uncertainty to the caller so they can manually verify.
                status = "failed"
                last_error = f"outbox enqueued but audit failed: {exc}"
                success_count -= 1
                failure_count += 1

        distributions.append({
            "recipient":       recipient,
            "distribution_id": distribution_id,
            "outbox_id":       outbox_id,
            "status":          status,
        })

    log.info(
        "reports.distribute.done",
        report_id=str(report_id),
        recipient_count=len(deduped),
        success=success_count,
        failure=failure_count,
    )

    return {
        "report_id":       report_id,
        "recipient_count": len(deduped),
        "success_count":   success_count,
        "failure_count":   failure_count,
        "distributions":   distributions,
    }


async def list_distributions(*, enterprise_id: str, report_id: UUID) -> list[dict]:
    """List distributions for a report. Validates the report itself is
    visible to the caller (RLS) before returning the audit rows."""
    async with acquire_for_tenant(enterprise_id) as conn:
        report = await repository.fetch_report(conn, report_id)
        if report is None:
            raise ReportNotFoundError(f"report {report_id} not found")
        return await repository.list_distributions(conn, report_id)


async def _enqueue_distribution_outbox(
    *,
    pool,
    enterprise_id: str,
    report_id: UUID,
    report_title: str,
    narrative: Optional[str],
    recipient_email: str,
    custom_message: Optional[str],
    frontend_url: str,
) -> UUID:
    """Insert a notification_outbox row + return the outbox_id.

    Same shape as ``_enqueue_notification`` for the auto-generate
    flow, with two extras: ``custom_message`` flows into the
    template context (rendered above the default copy when present),
    and ``source_ref`` carries ``dist:`` so support can grep the
    notification_outbox by distribution intent."""
    context = {
        "report_title":   report_title,
        "report_url":     f"{frontend_url}/p2/reports/{report_id}",
        "narrative":      narrative or "",
        "generated_at":   _now().strftime("%H:%M %d/%m/%Y"),
        "custom_message": custom_message or "",
    }
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO notification_outbox
                (enterprise_id, template, recipient_email, context, source_ref)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            RETURNING outbox_id
            """,
            UUID(enterprise_id),
            "report-ready",
            recipient_email,
            json.dumps(context),
            f"report:{report_id}:dist",
        )
    return row["outbox_id"]


def _dedup_emails(recipients: list[str]) -> list[str]:
    """Trim, lowercase-compare for dedup, drop empties. Preserves the
    first-seen casing for friendlier rendering in the FE list."""
    seen: set[str] = set()
    out: list[str] = []
    for raw in recipients or []:
        if not raw:
            continue
        cleaned = raw.strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


# ─── Errors ──────────────────────────────────────────────────────

class TemplateNotFoundError(Exception):
    """Raised when the requested template_id does not exist or is not
    visible to the calling tenant. Router translates to 404."""


class ReportNotFoundError(Exception):
    """Raised when distribute() / list_distributions() target a report
    that doesn't exist or isn't visible to the calling tenant."""


class ReportNotReadyError(Exception):
    """Raised when distribute() is called on a non-ready report.
    Router translates to 409."""


class InvalidDistributionError(Exception):
    """Raised on bad input — empty recipients, over-cap. Router
    translates to 400."""
