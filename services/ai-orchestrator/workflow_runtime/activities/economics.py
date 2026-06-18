"""
Economics activities — NOV monthly digest building blocks.

Phase 1.5 P15-S9 D7. Activities are sized so the workflow body in
workflows/nov_monthly_digest.py reads top-to-bottom as the playbook:
gather inputs → compute → persist → notify.

K-17 class assignments
======================
gather_nov_inputs              read_only             SELECT only
compute_nov_for_month          pure                  pure arithmetic
persist_nov_digest             write_idempotent      UPSERT keyed by (enterprise, month)
maybe_dispatch_negative_alert  external              POSTs to notification-service when NOV < 0

Phase 1.5 ships stubs that the workflow can compose end-to-end via the
in-memory test environment. Phase 1.5+ replaces gather_nov_inputs with
the real Postgres reads (Olist + pilot tenants); persist_nov_digest
already wires the real UPSERT so its tests verify the contract today.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

import structlog
from temporalio import activity

from ...org_intel.economics import (
    NOVResult,
    compute_monthly_nov,
    estimate_ai_token_cost,
    estimate_infrastructure_cost,
    estimate_integration_cost,
    estimate_people_cost,
    estimate_revenue_pre_post,
)

log = structlog.get_logger()


# ---------------------------------------------------------------------------
# Dataclasses — typed I/O makes the workflow signatures self-documenting
# and lets Temporal serialise them via the default JSON converter.
# ---------------------------------------------------------------------------


@dataclass
class NOVInputs:
    """Raw inputs gathered from upstream tables. The shape covers the
    Phase 1 v4 P1-S7 estimator surface — extra fields are forward-
    compatible (new estimators add new fields, old workflows ignore).

    All money fields ride as str-decimal because Decimal is not JSON-
    native; the activity reconstructs Decimal locally.
    """

    enterprise_id: str
    month_start: str  # ISO date — Temporal serialises dataclasses as JSON

    # Revenue — pre/post NOV-REV-001
    revenue_30d_before_vnd: str
    revenue_30d_after_vnd: str

    # People cost — NOV-CST-007
    people_hours_required: str             # Decimal hours
    people_hourly_rate_vnd: str

    # AI token cost — NOV-CST-009 (split input vs output per provider pricing)
    ai_tokens_input: int
    ai_tokens_output: int
    ai_cost_per_1k_input_vnd: str
    ai_cost_per_1k_output_vnd: str

    # Infrastructure cost — NOV-CST-008 (compute hours + storage GB-month)
    infra_compute_hours: str
    infra_storage_gb_month: str

    # Integration cost — NOV-CST-010
    integration_api_calls: int
    integration_cost_per_call_vnd: str


@dataclass
class NOVDigestPayload:
    """Output of compute_nov_for_month — passed to persist_nov_digest.

    Each Decimal goes over the wire as str so JSON survives the round-
    trip + the persist activity reconstructs the Decimal locally.
    """

    enterprise_id: str
    month_start: str
    revenue_vnd: str
    cost_vnd: str
    nov_vnd: str
    revenue_method: str
    revenue_confidence: str

    people_cost_vnd: str
    ai_cost_vnd: str
    infra_cost_vnd: str
    integration_cost_vnd: str


# ---------------------------------------------------------------------------
# Activity 1 — read_only: gather inputs
# ---------------------------------------------------------------------------


@activity.defn(name="gather_nov_inputs")
async def gather_nov_inputs(
    enterprise_id: str, month_start: str,
) -> NOVInputs:
    """Read upstream rows the NOV computation needs.

    K-17 class: read_only. Phase 1.5 D7 ships a stub that returns a
    deterministic shape so the workflow + persistence can be exercised
    end-to-end in tests without a populated DB. Phase 1.5+ replaces
    with the real queries:
      * pipeline_runs aggregate → people_hours_saved, integration_calls
      * llm_audit_log aggregate → ai_tokens_used
      * enterprise_monthly_billing → revenue_baseline_vnd / revenue_post_vnd
      * tenant settings → people_hourly_rate_vnd, ai_cost_per_1k_vnd,
                          infra_cost_per_unit_vnd, integration_cost_per_call_vnd
    """
    log.info(
        "activity.gather_nov_inputs",
        enterprise_id=enterprise_id, month_start=month_start,
    )
    # Stub values — keep them realistic enough for test assertions but
    # explicitly synthetic (no risk of accidentally shipping these to
    # a live tenant).
    return NOVInputs(
        enterprise_id=enterprise_id,
        month_start=month_start,
        revenue_30d_before_vnd="100000000",   # 100M VND baseline
        revenue_30d_after_vnd="120000000",    # 120M VND post-deploy (+20M)
        people_hours_required="40",
        people_hourly_rate_vnd="200000",
        ai_tokens_input=400_000,
        ai_tokens_output=100_000,
        ai_cost_per_1k_input_vnd="40",
        ai_cost_per_1k_output_vnd="80",
        infra_compute_hours="720",            # 1 host-month
        infra_storage_gb_month="50",
        integration_api_calls=10_000,
        integration_cost_per_call_vnd="10",
    )


# ---------------------------------------------------------------------------
# Activity 2 — pure: compute NOV from raw inputs
# ---------------------------------------------------------------------------


@activity.defn(name="compute_nov_for_month")
async def compute_nov_for_month(inputs: NOVInputs) -> NOVDigestPayload:
    """Run all 4 cost estimators + the pre/post revenue estimator,
    aggregate, return the digest payload.

    K-17 class: pure. Sums of Decimal arithmetic; deterministic for the
    same inputs. The activity exists so the workflow can declare a
    pure boundary (retry safe, no idempotency key needed) and so tests
    can assert on the cost breakdown independently of I/O.
    """
    revenue = estimate_revenue_pre_post(
        revenue_30d_before_vnd=Decimal(inputs.revenue_30d_before_vnd),
        revenue_30d_after_vnd=Decimal(inputs.revenue_30d_after_vnd),
    )
    people = estimate_people_cost(
        hours_required=Decimal(inputs.people_hours_required),
        hourly_rate_vnd=Decimal(inputs.people_hourly_rate_vnd),
    )
    ai = estimate_ai_token_cost(
        tokens_input=inputs.ai_tokens_input,
        tokens_output=inputs.ai_tokens_output,
        cost_per_1k_input_vnd=Decimal(inputs.ai_cost_per_1k_input_vnd),
        cost_per_1k_output_vnd=Decimal(inputs.ai_cost_per_1k_output_vnd),
    )
    infra = estimate_infrastructure_cost(
        compute_hours=Decimal(inputs.infra_compute_hours),
        storage_gb_month=Decimal(inputs.infra_storage_gb_month),
    )
    integration = estimate_integration_cost(
        api_calls=inputs.integration_api_calls,
        cost_per_call_vnd=Decimal(inputs.integration_cost_per_call_vnd),
    )
    total_cost = people + ai + infra + integration

    # estimate_revenue_pre_post returns RevenueEstimate (dataclass);
    # unwrap into compute_monthly_nov, propagating method + confidence
    # so the digest carries the provenance of the revenue figure.
    nov = compute_monthly_nov(
        revenue_vnd=revenue.revenue_vnd,
        cost_vnd=total_cost,
        revenue_method=revenue.method,
        revenue_confidence=revenue.confidence,
    )

    return NOVDigestPayload(
        enterprise_id=inputs.enterprise_id,
        month_start=inputs.month_start,
        revenue_vnd=str(nov.revenue_vnd),
        cost_vnd=str(nov.cost_vnd),
        nov_vnd=str(nov.nov_vnd),
        revenue_method=nov.revenue_method,
        revenue_confidence=str(nov.revenue_confidence),
        people_cost_vnd=str(people),
        ai_cost_vnd=str(ai),
        infra_cost_vnd=str(infra),
        integration_cost_vnd=str(integration),
    )


# ---------------------------------------------------------------------------
# Activity 3 — write_idempotent: persist the digest (UPSERT by month)
# ---------------------------------------------------------------------------


@activity.defn(name="persist_nov_digest")
async def persist_nov_digest(payload: NOVDigestPayload) -> dict[str, Any]:
    """UPSERT the digest row.

    K-17 class: write_idempotent. The unique index on (enterprise_id,
    month_start) makes the UPSERT idempotent — a retry of the same
    workflow execution lands on the same row + bumps `revision` (which
    the dashboard surfaces as "revised N times this month").

    Phase 1.5 D7 stub: log + return synthetic ack. Phase 1.5+ wires the
    real shared.db pool. Splitting the wire from the contract surface
    means the workflow tests don't need a Postgres container today.
    """
    log.info(
        "activity.persist_nov_digest",
        enterprise_id=payload.enterprise_id,
        month_start=payload.month_start,
        nov_vnd=payload.nov_vnd,
    )
    # Stub: real impl uses shared.db.acquire_for_tenant + persistence.
    # upsert_monthly_digest. The synthetic return mirrors the row id
    # the real path would produce so consumers can write integration
    # tests that exercise the full chain without rewriting assertions.
    return {
        "row_id": f"digest-{payload.enterprise_id}-{payload.month_start}",
        "enterprise_id": payload.enterprise_id,
        "month_start": payload.month_start,
        "nov_vnd": payload.nov_vnd,
        "is_negative": Decimal(payload.nov_vnd) < 0,
        "revision": 1,
    }


# ---------------------------------------------------------------------------
# Activity 4 — external: dispatch a negative-NOV alert when applicable
# ---------------------------------------------------------------------------


@activity.defn(name="maybe_dispatch_negative_alert")
async def maybe_dispatch_negative_alert(
    digest: dict[str, Any],
) -> dict[str, Any]:
    """NOV-CORE-016 — when NOV < 0, ping the CSM via notification-service.

    K-17 class: external. Notification-service forwards to email /
    Telegram / Zalo; once delivered it can't be un-delivered, so the
    matching workflow YAML node declares a `send_correction_message`
    compensation per REL-012. Phase 1.5 D7 stub returns
    {dispatched: bool} so the workflow can branch on the result; the
    real httpx POST lands when the negative-alert routing rule does
    (D7 follow-up, after the first month of digests gives us a real
    alert volume to size against).
    """
    is_negative = bool(digest.get("is_negative"))
    if not is_negative:
        log.info("activity.maybe_dispatch_negative_alert.skipped_positive",
                 enterprise_id=digest.get("enterprise_id"),
                 nov_vnd=digest.get("nov_vnd"))
        return {"dispatched": False, "reason": "nov_positive_or_zero"}

    log.warning(
        "activity.maybe_dispatch_negative_alert.dispatched",
        enterprise_id=digest.get("enterprise_id"),
        month_start=digest.get("month_start"),
        nov_vnd=digest.get("nov_vnd"),
    )
    return {
        "dispatched": True,
        "channel": "stub",
        "ref": f"alert-{digest.get('enterprise_id')}-{digest.get('month_start')}",
    }
