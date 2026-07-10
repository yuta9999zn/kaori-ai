"""
LLM Router — HTTP shim against services/llm-gateway (P-1 cutover).

Before this cutover, this module owned PII redaction (K-5), provider
dispatch (Ollama / Anthropic / OpenAI), and decision_audit_log writes
(K-6). All of that has moved into ``services/llm-gateway`` so there's
exactly one place where LLM calls happen.

This file remains for backward-compatibility with the existing
callers in this service (analytics/runner.py, routers/dashboard.py,
routers/strategy.py). They keep their import and call shape:

    from ..engine.llm_router import llm_router
    text = await llm_router.complete(prompt, task=..., enterprise_id=...)

Internally, ``complete`` makes an HTTP POST to ``${LLM_GATEWAY_URL}/v1/infer``
and returns the ``completion`` string. PII redaction and audit logging
happen inside the gateway — this shim is intentionally dumb.

K-3 invariant preserved: every LLM call still routes through this
module; nobody in ai-orchestrator imports an LLM SDK directly.

K-4 enforcement (F-016, Phase 1 close-out):
    Before forwarding ``consent_external=True`` to the gateway, the shim
    looks up ``tenant_settings.consent_external_ai`` for the calling
    tenant. If the tenant has not opted in, the call is refused with
    :class:`ConsentDeniedError` rather than letting the gateway invoke
    an external provider against the tenant's data. The lookup is cached
    per-enterprise for 60 seconds to keep hot LLM loops out of the DB.
"""
from __future__ import annotations

import os
import time
from typing import Optional

import httpx
import structlog

from ..shared.circuit_breaker import call_with_breaker
from ..shared.db import acquire_for_tenant

log = structlog.get_logger()

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")

# Phase 2 #7 (B3 PR #6) — bounded timeout. The previous 180-second value
# was self-DoS material: a flaky upstream stacked 100 concurrent requests
# that each held a connection for 3 minutes. Real Qwen 2.5 7B local runs
# finish in <10 seconds; external Anthropic/OpenAI in <30. Override via
# LLM_TIMEOUT_S env if you genuinely need longer.
LLM_TIMEOUT_S = float(os.getenv("LLM_TIMEOUT_S", "30.0"))

# Token ceiling for short freeform NARRATIVES (advisor summary, analysis
# overview/template blurbs — "2-4 sentences"). These prompts stop early on a
# fast model, but on the pilot box (Qwen 7B ≈ 6.7 tok/s) the default 2000-token
# ceiling lets a rambling generation blow past LLM_TIMEOUT_S → the narrative
# hangs/fails while the deterministic numbers are already done. Capping low
# guarantees the narrative finishes under the timeout on slow local models.
# Pilot .env sets ~128 (≈19s @ 6.7 tok/s); production (14B/GPU) leaves the
# default so summaries can run longer. Does NOT apply to structured analysis
# (complete_structured) — those need their full token budget for valid JSON.
NARRATIVE_MAX_TOKENS = int(os.getenv("KAORI_NARRATIVE_MAX_TOKENS", "400"))
_BREAKER_NAME = "llm_gateway"


def _llm_retry_attempts() -> Optional[int]:
    """LLM-specific retry budget (incident 2026-07-10, run d3d2e493).
    The global RETRY_MAX_ATTEMPTS=3 × LLM_TIMEOUT_S can mean 20+ minutes
    of silent waiting per LLM node on the pilot CPU box. Read per call so
    ops can tighten without a restart-order trap; unset/0 → None → keep
    the global default."""
    raw = os.getenv("KAORI_LLM_RETRY_MAX_ATTEMPTS", "").strip()
    if not raw:
        return None
    val = int(raw)
    return val if val > 0 else None

# Kept exported because routers/health.py reads it for the readiness
# check. After the cutover the orchestrator no longer talks to Ollama
# directly, so the readiness probe pings the gateway instead — but
# the constant stays here so the import path remains stable.
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Background callers without tenant context (rare — overview narrative
# generation in dev paths) historically pass enterprise_id="". The
# gateway requires a UUID; we substitute a well-known dev id so the
# audit row surfaces as a system-level entry. Kept identical to the
# pre-K-4 behaviour for the no-consent (default) path.
_DEV_ENTERPRISE_ID = "00000000-0000-0000-0000-000000000001"

# K-4 consent cache: {enterprise_id: (consent_external_ai, expires_monotonic)}.
# 60s TTL keeps a 100-template analysis run from hammering the DB while
# being short enough that a MANAGER's settings change takes effect almost
# immediately.
_CONSENT_TTL_S = 60.0
_consent_cache: dict[str, tuple[bool, float]] = {}


class ConsentDeniedError(PermissionError):
    """Raised when a caller requests an external LLM call but the tenant
    has not enabled ``consent_external_ai`` in tenant_settings (K-4).

    Callers should catch this and surface a user-facing message asking
    the MANAGER to opt in via the Settings page.
    """


async def _get_tenant_consent_external(enterprise_id: str) -> bool:
    """Read ``tenant_settings.consent_external_ai`` for the tenant, with
    a 60s in-process cache. Returns ``False`` (fail closed) on any DB
    error or missing row — K-4 says default to no external when uncertain.
    """
    now = time.monotonic()
    cached = _consent_cache.get(enterprise_id)
    if cached and cached[1] > now:
        return cached[0]

    consent = False
    try:
        async with acquire_for_tenant(enterprise_id) as conn:
            row = await conn.fetchrow(
                "SELECT consent_external_ai FROM tenant_settings "
                "WHERE enterprise_id = $1",
                enterprise_id,
            )
        if row is not None:
            consent = bool(row["consent_external_ai"])
    except Exception as exc:
        # Fail closed. K-4 is a privacy invariant — we'd rather refuse a
        # legitimate external call than leak data on a transient DB blip.
        log.error("llm_router.consent_lookup_failed",
                  enterprise_id=enterprise_id, error=str(exc))
        consent = False

    _consent_cache[enterprise_id] = (consent, now + _CONSENT_TTL_S)
    return consent


def _invalidate_consent_cache(enterprise_id: Optional[str] = None) -> None:
    """Test hook (and future PATCH-side hook) to drop cached consent."""
    if enterprise_id is None:
        _consent_cache.clear()
    else:
        _consent_cache.pop(enterprise_id, None)


class LLMRouter:
    """HTTP client for ``llm-gateway``. Same surface the rest of the
    service has been calling — drop-in replacement for the old
    in-process implementation.
    """

    async def complete(
        self,
        prompt: str,
        task: str,
        consent_external: bool = False,
        enterprise_id: str = "",
        max_tokens: int = 2000,
        run_id: Optional[str] = None,
    ) -> str:
        # K-4 enforcement runs BEFORE we substitute the dev enterprise id,
        # so a no-tenant background call cannot piggy-back on the dev row's
        # opt-in to reach an external provider.
        if consent_external:
            if not enterprise_id:
                raise ConsentDeniedError(
                    "External LLM call requires a tenant context "
                    "(enterprise_id is empty). K-4 refuses."
                )
            tenant_consent = await _get_tenant_consent_external(enterprise_id)
            if not tenant_consent:
                raise ConsentDeniedError(
                    f"Tenant {enterprise_id} has not enabled "
                    "consent_external_ai. Ask a MANAGER to opt in via "
                    "the Enterprise Settings page (K-4)."
                )

        body: dict = {
            "task": task,
            "prompt": prompt,
            # The gateway requires a UUID. Existing callers always
            # have one; the empty-string default is preserved for the
            # rare background path so the shim doesn't 422 on it —
            # we substitute the well-known dev enterprise id, which
            # makes the audit row surface as a system call.
            "enterprise_id": enterprise_id or _DEV_ENTERPRISE_ID,
            "consent_external": consent_external,
            "max_tokens": max_tokens,
        }
        if run_id:
            body["run_id"] = run_id

        # Phase 2 #7 — wrap the network hop in a circuit breaker +
        # bounded retry. The breaker opens after 5 failures in 30s and
        # blocks new calls for 60s; a flapping gateway stops cascading
        # into ai-orchestrator's own thread pool. The retry inside the
        # closed-state attempt absorbs single-packet drops with jittered
        # exponential backoff (max 3 attempts).
        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
                resp = await client.post(f"{LLM_GATEWAY_URL}/v1/infer", json=body)
                resp.raise_for_status()
                return resp.json()

        try:
            payload = await call_with_breaker(_BREAKER_NAME, _call, max_attempts=_llm_retry_attempts())
        except httpx.HTTPError as exc:
            log.error("llm_router.gateway_call_failed",
                      task=task, error=str(exc))
            raise

        # The gateway already wrote the K-6 audit row; the shim returns
        # only the completion text so existing call sites are unchanged.
        return payload.get("completion", "")

    async def complete_structured(
        self,
        prompt: str,
        task: str,
        output_schema: dict,
        consent_external: bool = False,
        enterprise_id: str = "",
        max_tokens: int = 2000,
        run_id: Optional[str] = None,
    ) -> dict:
        """Single-prompt completion with Issue #3 (PR #112) JSON Schema
        validation + one-shot repair on the gateway side.

        Returns the validated parsed dict (``output_validation.parsed_json``
        from the gateway response) — caller never has to ``json.loads`` or
        worry about ``` ``` `` fences.

        Behaviour:
          * On gateway 200 — returns the parsed dict.
          * On gateway 502 (LLM.OUTPUT_VALIDATION_FAILED) — re-raises the
            ``httpx.HTTPStatusError`` so the caller can decide whether to
            fall back to a heuristic or surface the failure to the user.

        Same K-4 consent gate as ``complete``. Designed for F-038 Reports
        (and any future caller that needs structured LLM output).
        """
        if consent_external:
            if not enterprise_id:
                raise ConsentDeniedError(
                    "External LLM call requires a tenant context. K-4 refuses."
                )
            tenant_consent = await _get_tenant_consent_external(enterprise_id)
            if not tenant_consent:
                raise ConsentDeniedError(
                    f"Tenant {enterprise_id} has not enabled consent_external_ai (K-4)."
                )

        body: dict = {
            "task":             task,
            "prompt":           prompt,
            "enterprise_id":    enterprise_id or _DEV_ENTERPRISE_ID,
            "consent_external": consent_external,
            "max_tokens":       max_tokens,
            "output_schema":    output_schema,
        }
        if run_id:
            body["run_id"] = run_id

        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
                resp = await client.post(f"{LLM_GATEWAY_URL}/v1/infer", json=body)
                resp.raise_for_status()
                return resp.json()

        try:
            payload = await call_with_breaker(_BREAKER_NAME, _call, max_attempts=_llm_retry_attempts())
        except httpx.HTTPError as exc:
            log.error("llm_router.structured_call_failed",
                      task=task, error=str(exc))
            raise

        # The gateway response shape is pinned by Issue #3 — when
        # output_schema is set, output_validation.parsed_json is always
        # present on a 200. If it's not we raise so the caller doesn't
        # silently get an empty dict.
        validation = payload.get("output_validation") or {}
        parsed = validation.get("parsed_json")
        if parsed is None:
            raise RuntimeError(
                "llm-gateway returned 200 with output_schema set but no "
                "parsed_json in output_validation — gateway contract drift."
            )
        return parsed

    async def chat(
        self,
        messages: list[dict],
        task: str,
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[str] = None,
        consent_external: bool = False,
        enterprise_id: str = "",
        max_tokens: int = 1500,
    ) -> dict:
        """Multi-message chat with optional tool calling — Sprint 8.

        Returns the raw gateway response dict (``completion``,
        ``tool_calls``, ``finish_reason``, ``model_used``, ``method``,
        ``latency_ms``). Callers — currently just chat/agent.py — pick
        the fields they need; we don't narrow the return type so the
        agent has access to ``finish_reason`` for loop control.

        Same K-4 consent gate as ``complete``: external chat is
        refused unless the tenant has explicitly opted in. The
        Sprint 8 chat agent always passes ``consent_external=False``,
        so this guard mostly protects future callers.
        """
        if consent_external:
            if not enterprise_id:
                raise ConsentDeniedError(
                    "External chat call requires a tenant context. K-4 refuses."
                )
            tenant_consent = await _get_tenant_consent_external(enterprise_id)
            if not tenant_consent:
                raise ConsentDeniedError(
                    f"Tenant {enterprise_id} has not enabled consent_external_ai (K-4)."
                )

        body: dict = {
            "task": task,
            "prompt": "",  # required field on the gateway, ignored on chat path
            "messages": messages,
            "enterprise_id": enterprise_id or _DEV_ENTERPRISE_ID,
            "consent_external": consent_external,
            "max_tokens": max_tokens,
        }
        if tools:
            body["tools"] = tools
        if tool_choice:
            body["tool_choice"] = tool_choice

        # Phase 2 #7 — same breaker name as ``complete``: gateway down
        # affects both paths the same way, and a single failure budget
        # is what we want.
        async def _call() -> dict:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT_S) as client:
                resp = await client.post(f"{LLM_GATEWAY_URL}/v1/infer", json=body)
                resp.raise_for_status()
                return resp.json()

        try:
            return await call_with_breaker(_BREAKER_NAME, _call, max_attempts=_llm_retry_attempts())
        except httpx.HTTPError as exc:
            log.error("llm_router.chat_call_failed",
                      task=task, error=str(exc))
            raise


# Singleton — preserved so existing callers keep working untouched:
#   from ..engine.llm_router import llm_router
#   await llm_router.complete(...)
llm_router = LLMRouter()
