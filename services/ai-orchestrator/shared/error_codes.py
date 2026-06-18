"""
Canonical error_code registry — Phase 2 error-handling group #1.

Every error response (RFC 7807, K-14) carries:

    {
      "type":   "...",
      "title":  "...",
      "status": <int>,
      "detail": "...",
      "code":   "<DOMAIN>.<NAME>",      <-- this file
      "instance": "..."
    }

The ``code`` is the **machine-readable** key the FE maps to i18n strings
(``frontend/lib/i18n/error-messages.ts``). It must:

  * stay stable across releases — never rename a code that's already
    been observed by clients;
  * encode a single business meaning — different states get different
    codes even if the HTTP status is the same;
  * group by domain prefix — operators reading aggregated logs can grep
    one prefix to see all auth-related failures, etc.

Adding a new code:
  1. Append a constant in the matching domain section below.
  2. Mirror the same constant in services/ai-orchestrator + llm-gateway
     + notification-service + the Java enum (services/auth-service/
     .../common/ErrorCodes.java) — same string spelling.
  3. Document the user-facing text in the FE i18n table when the route
     starts emitting it.

Sampling: Phase 2 PR #4 (distributed tracing) will add a Prometheus
counter ``kaori_validation_errors_total{code, path}`` so high-frequency
codes can be sampled in logs without losing visibility on the rare ones.
"""
from __future__ import annotations


# ============================================================
# AUTH — login / session / token errors (auth-service domain)
# ============================================================
AUTH_INVALID_CREDENTIALS = "AUTH.INVALID_CREDENTIALS"
AUTH_LOCKED              = "AUTH.LOCKED"           # 423 — repeated failed attempts
AUTH_TOKEN_REVOKED       = "AUTH.TOKEN_REVOKED"
AUTH_TOKEN_INVALID       = "AUTH.TOKEN_INVALID"
AUTH_TOKEN_EXPIRED       = "AUTH.TOKEN_EXPIRED"
AUTH_WRONG_TOKEN_KIND    = "AUTH.WRONG_TOKEN_KIND" # platform endpoint hit with enterprise token
AUTH_FORBIDDEN_ROLE      = "AUTH.FORBIDDEN_ROLE"
AUTH_MISSING_BEARER      = "AUTH.MISSING_BEARER"
AUTH_MFA_REQUIRED        = "AUTH.MFA_REQUIRED"
AUTH_MFA_INVALID_CODE    = "AUTH.MFA_INVALID_CODE"
AUTH_SESSION_EXPIRED     = "AUTH.SESSION_EXPIRED"

# ============================================================
# VALIDATION — request shape, field types, business rules
# ============================================================
VALIDATION_GENERIC       = "VALIDATION.GENERIC"        # Pydantic / Bean Validation default
VALIDATION_MISSING_FIELD = "VALIDATION.MISSING_FIELD"
VALIDATION_INVALID_EMAIL = "VALIDATION.INVALID_EMAIL"
VALIDATION_INVALID_UUID  = "VALIDATION.INVALID_UUID"
VALIDATION_INVALID_DATE  = "VALIDATION.INVALID_DATE"
VALIDATION_INVALID_ENUM  = "VALIDATION.INVALID_ENUM"
VALIDATION_PAYLOAD_TOO_LARGE = "VALIDATION.PAYLOAD_TOO_LARGE"

# ============================================================
# BILLING — quota / plan / aggregation
# ============================================================
BILLING_QUOTA_EXCEEDED       = "BILLING.QUOTA_EXCEEDED"
BILLING_AGGREGATION_RUNNING  = "BILLING.AGGREGATION_RUNNING"   # PR #2 409
BILLING_NO_QUOTA             = "BILLING.NO_QUOTA"
BILLING_PLAN_NOT_FOUND       = "BILLING.PLAN_NOT_FOUND"

# ============================================================
# PIPELINE — upload / schema / cleaning / analysis
# ============================================================
PIPELINE_UPLOAD_REJECTED  = "PIPELINE.UPLOAD_REJECTED"
PIPELINE_DUPLICATE_FILE   = "PIPELINE.DUPLICATE_FILE"   # SHA-256 dedup
PIPELINE_SCHEMA_INVALID   = "PIPELINE.SCHEMA_INVALID"
PIPELINE_RUN_NOT_FOUND    = "PIPELINE.RUN_NOT_FOUND"
PIPELINE_INVALID_STATE    = "PIPELINE.INVALID_STATE"   # eg. confirming schema on already-cleaned run

# ============================================================
# LLM — gateway / consent / external AI
# ============================================================
LLM_CONSENT_DENIED      = "LLM.CONSENT_DENIED"        # K-4
LLM_GATEWAY_UNAVAILABLE = "LLM.GATEWAY_UNAVAILABLE"
LLM_TIMEOUT             = "LLM.TIMEOUT"
LLM_QUOTA_EXCEEDED      = "LLM.QUOTA_EXCEEDED"

# ============================================================
# COMPLIANCE — EU AI Act control framework (ADR-0041, K-22..K-26)
# ============================================================
COMPLIANCE_PROHIBITED_USE  = "COMPLIANCE.PROHIBITED_USE"   # 403 — Art 5 prohibited tier
COMPLIANCE_NOT_CLASSIFIED  = "COMPLIANCE.NOT_CLASSIFIED"   # 409 — high-risk action w/o classification

# ============================================================
# JOB — scheduled jobs / leases (PR #1 + #2 territory)
# ============================================================
JOB_ALREADY_RUNNING = "JOB.ALREADY_RUNNING"
JOB_LEASE_ORPHANED  = "JOB.LEASE_ORPHANED"

# ============================================================
# RATE / SYSTEM — gateway-side enforcement
# ============================================================
RATE_LIMIT_EXCEEDED      = "RATE.LIMIT_EXCEEDED"           # 429
RATE_IDEMPOTENCY_MISSING = "RATE.IDEMPOTENCY_MISSING"      # K-13 400
SYSTEM_INTERNAL_ERROR    = "SYSTEM.INTERNAL_ERROR"         # 500 catch-all
SYSTEM_UNAVAILABLE       = "SYSTEM.UNAVAILABLE"            # 503


# ============================================================
# Default mapping — used when a handler doesn't emit a specific code.
# ============================================================
_STATUS_DEFAULT_CODE = {
    400: VALIDATION_GENERIC,
    401: AUTH_TOKEN_INVALID,
    403: AUTH_FORBIDDEN_ROLE,
    404: "RESOURCE.NOT_FOUND",
    409: "RESOURCE.CONFLICT",
    422: VALIDATION_GENERIC,
    423: AUTH_LOCKED,
    429: RATE_LIMIT_EXCEEDED,
    500: SYSTEM_INTERNAL_ERROR,
    502: SYSTEM_UNAVAILABLE,
    503: SYSTEM_UNAVAILABLE,
    504: SYSTEM_UNAVAILABLE,
}


def default_code_for(status: int) -> str:
    """Fallback code when a route doesn't pass an explicit one — maps the
    HTTP status to the closest canonical code."""
    return _STATUS_DEFAULT_CODE.get(status, SYSTEM_INTERNAL_ERROR)
