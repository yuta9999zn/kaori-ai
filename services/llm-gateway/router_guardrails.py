"""
P2-S23 SH-M56a router — public guardrails surface.

Endpoints
---------
POST   /guardrails/validate-input        run input rules on a prompt
POST   /guardrails/validate-output       run output rules on a completion
GET    /guardrails/violations            list per-tenant violations
GET    /guardrails/violations/top        top-pattern dashboard data
POST   /guardrails/retention/run         manual retention trigger
                                         (cron usually calls this)

The infer/chat endpoints in router.py call the engine internally before
+ after the LLM round-trip. These dedicated endpoints are for the FE
to preview rule outcomes (e.g., "would my prompt be blocked?") and for
the ops dashboard (SH-M56a-022).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from .guardrails import GuardrailEngine, GuardrailBlockedError, Layer, RuleContext
from .guardrails.input_rules import (
    InputLengthRule,
    PIIDetectRule,
    PromptInjectionRule,
    RateLimitRule,
    TopicRestrictionRule,
    ToxicLanguageInputRule,
)
from .guardrails.kaori_rules import (
    BusinessLanguageRule,
    CitationRequiredRule,
    HallucinationDetectorRule,
    NumericPrecisionCheckRule,
    TopFactorsMinLengthRule,
)
from .guardrails.output_rules import (
    CompetitorCheckRule,
    OutputLengthRule,
    ProfanityFreeRule,
    ToxicLanguageOutputRule,
    ValidJsonRule,
)
from .guardrails.violations import (
    list_violations,
    run_retention,
    top_patterns,
)

log = structlog.get_logger()

router = APIRouter(prefix="/guardrails", tags=["Guardrails"])


# ─── Default engine factory ──────────────────────────────────────────


def make_default_engine(persist: bool = True) -> GuardrailEngine:
    """Build an engine with the canonical Kaori rule set in order."""
    return GuardrailEngine(
        input_rules=[
            InputLengthRule(),
            PromptInjectionRule(),
            ToxicLanguageInputRule(),
            TopicRestrictionRule(),
            RateLimitRule(),
            PIIDetectRule(),       # last — FIX is applied to redacted prompt
        ],
        output_rules=[
            ValidJsonRule(),
            OutputLengthRule(),
            ToxicLanguageOutputRule(),
            ProfanityFreeRule(),
            CompetitorCheckRule(),
            TopFactorsMinLengthRule(),
            CitationRequiredRule(),
            BusinessLanguageRule(),
            NumericPrecisionCheckRule(),
            HallucinationDetectorRule(),
        ],
        persist_violations=persist,
    )


# Module-level singleton — cheap to construct, no I/O until invoked.
_default_engine = make_default_engine()


# ─── Schemas ─────────────────────────────────────────────────────────


class ValidateRequest(BaseModel):
    text:           str
    tenant_config:  dict[str, Any] = Field(default_factory=dict)
    request_id:     Optional[UUID] = None
    model_id:       Optional[str]  = None
    paired_input:   Optional[str]  = None
    parsed_output:  Optional[dict] = None


class ViolationOut(BaseModel):
    rule_name:         str
    severity:          str
    on_fail_action:    str
    rule_metadata:     dict[str, Any]
    offending_excerpt: Optional[str]


class ValidateResponse(BaseModel):
    passed:         bool
    layer:          str
    text:           str                  # possibly fixed
    violations:     list[ViolationOut]
    reask_feedback: list[str]


class ViolationRow(BaseModel):
    violation_id:      UUID
    enterprise_id:     UUID
    user_id:           Optional[UUID]
    rule_name:         str
    layer:             str
    severity:          str
    on_fail_action:    str
    request_id:        Optional[UUID]
    model_id:          Optional[str]
    offending_excerpt: Optional[str]
    rule_metadata:     dict[str, Any]
    created_at:        datetime


class TopPatternRow(BaseModel):
    rule_name: str
    layer:     str
    severity:  str
    n:         int


class RetentionRunOut(BaseModel):
    dropped_partitions: list[str]
    keep_days:          int


# ─── Endpoints ───────────────────────────────────────────────────────


@router.post("/validate-input", response_model=ValidateResponse)
async def validate_input(
    body: ValidateRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(None, alias="X-User-ID"),
):
    ctx = RuleContext(
        text=body.text,
        enterprise_id=x_enterprise_id,
        user_id=x_user_id,
        request_id=body.request_id,
        model_id=body.model_id,
        tenant_config=body.tenant_config or {},
    )
    try:
        report = await _default_engine.run_input(ctx)
    except GuardrailBlockedError as e:
        return ValidateResponse(
            passed=False,
            layer=Layer.INPUT.value,
            text=body.text,
            violations=[ViolationOut(
                rule_name=e.rule_name,
                severity="critical",
                on_fail_action="exception",
                rule_metadata={"reason": e.reason, "feedback": e.feedback},
                offending_excerpt=None,
            )],
            reask_feedback=[],
        )
    return _report_to_response(report, body.text)


@router.post("/validate-output", response_model=ValidateResponse)
async def validate_output(
    body: ValidateRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       Optional[UUID] = Header(None, alias="X-User-ID"),
):
    ctx = RuleContext(
        text=body.text,
        enterprise_id=x_enterprise_id,
        user_id=x_user_id,
        request_id=body.request_id,
        model_id=body.model_id,
        paired_input=body.paired_input,
        parsed_output=body.parsed_output,
        tenant_config=body.tenant_config or {},
    )
    try:
        report = await _default_engine.run_output(ctx)
    except GuardrailBlockedError as e:
        return ValidateResponse(
            passed=False,
            layer=Layer.OUTPUT.value,
            text=body.text,
            violations=[ViolationOut(
                rule_name=e.rule_name,
                severity="critical",
                on_fail_action="exception",
                rule_metadata={"reason": e.reason, "feedback": e.feedback},
                offending_excerpt=None,
            )],
            reask_feedback=[],
        )
    return _report_to_response(report, body.text)


def _report_to_response(report, original_text: str) -> ValidateResponse:
    return ValidateResponse(
        passed=len(report.violations) == 0,
        layer=report.layer.value if report.layer else "input",
        text=report.text,
        violations=[ViolationOut(
            rule_name=v.rule_name,
            severity=v.severity.value if hasattr(v.severity, "value") else str(v.severity),
            on_fail_action=v.rule_metadata.get("on_fail_action", "unknown"),
            rule_metadata=v.rule_metadata,
            offending_excerpt=v.offending_excerpt,
        ) for v in report.violations],
        reask_feedback=report.reask_feedback,
    )


@router.get("/violations", response_model=list[ViolationRow])
async def list_violations_endpoint(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    since:     Optional[datetime] = Query(default=None),
    layer:     Optional[str]      = Query(default=None),
    rule_name: Optional[str]      = Query(default=None),
    limit:     int                 = Query(default=100, ge=1, le=1000),
):
    rows = await list_violations(
        enterprise_id=x_enterprise_id,
        since=since, layer=layer, rule_name=rule_name, limit=limit,
    )
    return [ViolationRow(**r) for r in rows]


@router.get("/violations/top", response_model=list[TopPatternRow])
async def top_patterns_endpoint(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    since: Optional[datetime] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
):
    rows = await top_patterns(
        enterprise_id=x_enterprise_id, since=since, limit=limit,
    )
    return [TopPatternRow(**r) for r in rows]


@router.post("/retention/run", response_model=RetentionRunOut)
async def trigger_retention(
    keep_days: int = Query(default=180, ge=30, le=730),
):
    """SH-M56a-024 — manual retention. Cron hits this daily at 03:00."""
    dropped = await run_retention(keep_days=keep_days)
    return RetentionRunOut(dropped_partitions=dropped, keep_days=keep_days)
