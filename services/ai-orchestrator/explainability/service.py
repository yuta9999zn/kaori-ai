"""
F-041 Explainability — service layer.

Single public entry: ``explain(decision_id, enterprise_id)``. Reads the
decision_audit_log row via RLS (acquire_for_tenant), formats the prompt
with the audit fields, calls llm_router.complete_structured (Issue #3
path), writes a K-6 audit row for the explain call itself, returns the
parsed dict to the caller.

Stateless — explanations are not persisted. If the same decision is
re-explained, we regenerate (LLM cost is small; consistency between
re-runs depends on Qwen temperature, which is acceptable for a "second
opinion" feature).
"""
from __future__ import annotations

import json
from typing import Optional
from uuid import UUID

import structlog
from jinja2 import Template

from ..engine.llm_router import llm_router
from ..shared.audit import log_decision
from ..shared.db import acquire_for_tenant
from . import templates as expl_templates

log = structlog.get_logger()


# ─── Errors ──────────────────────────────────────────────────────


class DecisionNotFoundError(Exception):
    """Raised when the decision_id doesn't resolve under the tenant's
    RLS scope. Router translates to 404 (don't leak existence)."""


class ExplanationFailedError(Exception):
    """LLM gave up after the gateway's one-shot repair. Router
    translates to 502 with a friendly message."""


# ─── Public API ──────────────────────────────────────────────────


async def explain(
    *,
    decision_id: UUID,
    enterprise_id: str,
    consent_external: bool = False,
) -> dict:
    """Generate top_factors + narrative for a decision row.

    Returns the parsed dict (schema in templates.OUTPUT_SCHEMA). Logs
    a K-6 audit row tagging this call so an explainability run is
    itself auditable — explainable explainability."""
    async with acquire_for_tenant(enterprise_id) as conn:
        row = await conn.fetchrow(
            """
            SELECT decision_id, decision_type, subject, chosen_value,
                   confidence, method, llm_provider, reasoning,
                   alternatives, uncertainty_flags
              FROM decision_audit_log                    -- tenant-filter-lint: allow (RLS via acquire_for_tenant)
             WHERE decision_id = $1
            """,
            decision_id,
        )
    if row is None:
        raise DecisionNotFoundError(str(decision_id))

    rendered = _render_prompt(row)

    try:
        parsed = await llm_router.complete_structured(
            prompt=rendered,
            task="explainability.explain",
            output_schema=expl_templates.OUTPUT_SCHEMA,
            enterprise_id=enterprise_id,
            consent_external=consent_external,
            max_tokens=1500,
        )
    except Exception as exc:
        log.warning(
            "explainability.llm_failed",
            decision_id=str(decision_id), error=str(exc),
        )
        raise ExplanationFailedError(str(exc)) from exc

    # K-6 audit — explanation is itself a decision step.
    await log_decision(
        decision_type="explainability.explain",
        enterprise_id=enterprise_id,
        subject=str(decision_id),
        chosen_value=str(len(parsed.get("top_factors", []))),
        method="llm",
        llm_provider=("external" if consent_external else "qwen-internal"),
        reasoning=(
            f"explained decision_id={decision_id} "
            f"original_type={row['decision_type']} "
            f"factors={len(parsed.get('top_factors', []))}"
        ),
    )

    return parsed


# ─── Helpers ─────────────────────────────────────────────────────


def _render_prompt(row) -> str:
    alternatives = row["alternatives"]
    if isinstance(alternatives, str):
        try:
            alternatives = json.loads(alternatives)
        except (TypeError, ValueError):
            alternatives = []
    flags = list(row["uncertainty_flags"] or [])

    return Template(expl_templates.SYSTEM_PROMPT).render(
        decision_type=row["decision_type"] or "—",
        subject=row["subject"] or "—",
        chosen_value=row["chosen_value"] or "—",
        confidence=str(row["confidence"]) if row["confidence"] is not None else "—",
        method=row["method"] or "—",
        llm_provider=row["llm_provider"] or "—",
        reasoning=(row["reasoning"] or "")[:2000],
        alternatives=json.dumps(alternatives, ensure_ascii=False)[:1500],
        uncertainty_flags=", ".join(flags) if flags else "—",
    )
