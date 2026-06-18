"""
First activity set — analyze-pipeline workflow building blocks.

Each activity here covers one of the 5 side-effect classes (K-17). The
implementations are intentionally minimal — they exercise the
contract surface (input/output dataclasses, structlog fields, optional
DB pool reuse) without depending on any one feature flow. Phase 1.5+
real workflows compose these + add domain-specific activities.

Class assignments
=================
parse_input                    pure                  no I/O at all
load_pipeline_run              read_only             SELECT only
upsert_run_status              write_idempotent      UPSERT by run_id
insert_decision_audit          write_non_idempotent  append audit row
send_completion_notification   external              POST to notification-svc

Why a single file for five activities (instead of one-per-file):
the activities here are templates / building blocks, not feature
flows. Splitting them now would scatter the K-17 documentation and
tempt readers to grep for "real" implementations elsewhere. When a
feature workflow needs a domain activity (e.g. churn_score_compute),
that one ships in its own module under activities/.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import structlog
from temporalio import activity

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Shared dataclasses — keep activity I/O typed so the workflow is clear
# about what flows where (Temporal serialises these as JSON via the
# default data converter).
# ---------------------------------------------------------------------------


@dataclass
class AnalyzeInput:
    """Top-of-workflow input. Mirrors the body of POST /analytics/runs
    so the same payload can drive both the Kafka path (Phase 1) and the
    Temporal path (Phase 1.5+) without translation."""

    tenant_id: str
    run_id: str
    templates: list[str]
    config: dict[str, Any]


@dataclass
class PipelineRunSnapshot:
    """Read-only view of pipeline_runs state. Returned by load_pipeline_run."""

    run_id: str
    tenant_id: str
    status: str
    silver_row_count: int


@dataclass
class StatusUpdate:
    """Result of upsert_run_status — caller sees what the new state is.

    Returning the value rather than None lets the workflow log it for
    the audit trail (REL-019) without re-reading the DB.
    """

    run_id: str
    new_status: str


# ---------------------------------------------------------------------------
# pure — no I/O, retry freely
# ---------------------------------------------------------------------------


@activity.defn(name="parse_input")
async def parse_input(payload: dict[str, Any]) -> AnalyzeInput:
    """Validate + shape the workflow input dict into AnalyzeInput.

    K-17 class: pure. Pure validation, no I/O. The workflow runs this
    first so a malformed payload fails fast before any side effect.
    """
    required = {"tenant_id", "run_id", "templates"}
    missing = required - set(payload)
    if missing:
        raise ValueError(f"parse_input: missing keys {sorted(missing)}")
    return AnalyzeInput(
        tenant_id=str(payload["tenant_id"]),
        run_id=str(payload["run_id"]),
        templates=list(payload["templates"]),
        config=dict(payload.get("config") or {}),
    )


# ---------------------------------------------------------------------------
# read_only — SELECT only, retry safe
# ---------------------------------------------------------------------------


@activity.defn(name="load_pipeline_run")
async def load_pipeline_run(input_: AnalyzeInput) -> PipelineRunSnapshot:
    """Read pipeline_runs row to confirm the run exists + count rows.

    K-17 class: read_only. SELECT only. Stub returns a synthetic
    snapshot — Phase 1.5+ wires shared.db.get_pool() with
    acquire_for_tenant() (RLS) once the feature workflow is real. The
    contract here is intentionally small so it's easy to implement.

    The activity does NOT raise if the row is missing — it returns a
    snapshot with status='not_found' so the workflow can branch on
    state rather than catching exceptions for control flow.
    """
    log.info(
        "activity.load_pipeline_run",
        tenant_id=input_.tenant_id,
        run_id=input_.run_id,
    )
    # Stub: real impl will read the run row scoped to input_.tenant_id.
    # Returning a populated snapshot lets the workflow continue + tests
    # cover the happy path without a live Postgres.
    return PipelineRunSnapshot(
        run_id=input_.run_id,
        tenant_id=input_.tenant_id,
        status="silver_complete",
        silver_row_count=0,
    )


# ---------------------------------------------------------------------------
# write_idempotent — UPSERT by natural key, same input → same row state
# ---------------------------------------------------------------------------


@activity.defn(name="upsert_run_status")
async def upsert_run_status(input_: AnalyzeInput, status: str) -> StatusUpdate:
    """UPSERT analysis_runs status — keyed by run_id, idempotent on retry.

    K-17 class: write_idempotent. Same (run_id, status) pair applied
    twice = same row state. No idempotency_records lookup needed; the
    UPSERT itself is the dedup primitive.

    Allowed status values match the analysis_runs CHECK constraint
    (queued / running / complete / failed) — passing anything else
    raises so a typo doesn't silently set a workflow into limbo.
    """
    if status not in {"queued", "running", "complete", "failed"}:
        raise ValueError(f"upsert_run_status: invalid status {status!r}")
    log.info(
        "activity.upsert_run_status",
        tenant_id=input_.tenant_id,
        run_id=input_.run_id,
        status=status,
    )
    return StatusUpdate(run_id=input_.run_id, new_status=status)


# ---------------------------------------------------------------------------
# write_non_idempotent — append-only, needs explicit dedup at the
# Action Runtime layer (REL-005 + idempotency_records table)
# ---------------------------------------------------------------------------


@activity.defn(name="insert_decision_audit")
async def insert_decision_audit(
    input_: AnalyzeInput, decision_type: str, payload: dict[str, Any]
) -> str:
    """Append a row to decision_audit_log (K-6).

    K-17 class: write_non_idempotent. The table is INSERT-only with a
    serial primary key — naive retry would create duplicate audit rows.
    The Action Runtime wraps this call with derive_idempotency_key()
    + idempotency_records lookup so a retry hits the dedup cache.

    Returns the audit row id (UUID hex) so the workflow can reference
    it in subsequent activities or in the workflow result.
    """
    # Stub: real impl will append the audit row keyed to input_.tenant_id.
    # Returning a deterministic id keyed by run + type makes the test
    # reproducible and the K-17 dedup layer can verify the same key
    # always returns the same id.
    audit_id = f"audit-{input_.run_id}-{decision_type}"
    log.info(
        "activity.insert_decision_audit",
        tenant_id=input_.tenant_id,
        run_id=input_.run_id,
        decision_type=decision_type,
        audit_id=audit_id,
    )
    return audit_id


# ---------------------------------------------------------------------------
# external — third-party API with side effect, needs saga compensation
# ---------------------------------------------------------------------------


@activity.defn(name="send_completion_notification")
async def send_completion_notification(
    input_: AnalyzeInput, status: StatusUpdate
) -> dict[str, Any]:
    """POST a notification to the notification-service for terminal states.

    K-17 class: external. Notification-service forwards to SMTP / Telegram
    / Zalo — once the message goes out it can't be unsent. The compensation
    declared in the matching workflow YAML node is `send_correction_message`
    which posts a follow-up "ignore the previous notification" message
    when the saga aborts.

    The activity itself doesn't issue the HTTP — the Phase 1.5 stub logs
    the intent + returns a synthetic ack. Phase 1.5+ replaces with the
    real httpx client once notification-service exposes the endpoint
    (P15-S9 D5).
    """
    log.info(
        "activity.send_completion_notification",
        tenant_id=input_.tenant_id,
        run_id=input_.run_id,
        status=status.new_status,
    )
    return {
        "delivered": True,
        "channel": "stub",
        "ref": f"notif-{input_.run_id}-{status.new_status}",
    }
