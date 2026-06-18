"""
POST /v1/infer — public LLM dispatch endpoint.

Two pipelines, picked by the request shape:

  Single-prompt (Phase 1 callers — schema mapping, cleaning, summary):
    1. Resolve model         routing.resolve_model
    2. PII-redact for ext.   pii.redact (K-5; only when method=external)
    3. Dispatch              providers.invoke
    4. Audit                 audit.log_decision (K-6, best-effort)
    5. Return InferResponse  (tool_calls=None)

  Chat (Sprint 8 chat agent — when ``messages`` is non-empty):
    Same five steps, but pii.redact is applied per message, dispatch
    is providers.invoke_chat, and the response surfaces ``tool_calls``
    + ``finish_reason`` so the agent can loop.

Two non-fatal fallbacks:
  - external method requested but no API key configured → providers
    quietly downgrade to internal Ollama and surface that in
    ``model_used``.
  - audit.log_decision swallows its own DB errors so a downed audit
    table never breaks an LLM response.

Deliberately not in this PR (P-1 follow-ups):
  - Semantic cache lookup (cache_hit currently always False).
  - Per-tenant token budget enforcement.
"""
from __future__ import annotations

import json
import time

import structlog
from fastapi import APIRouter, HTTPException
from prometheus_client import Counter

from . import ai_governance, audit, pii, providers, routing, tenant_quotas
from .db import get_pool
from .models import (
    EmbedRequest,
    build_disclosure,
    EmbedResponse,
    InferRequest,
    InferResponse,
    OcrRequest,
    OcrResponse,
    OutputValidation,
    TokenUsage,
)
from .output_validator import StructuredOutputError, validate_or_repair

log = structlog.get_logger()

router = APIRouter()


# OBS-008 (P1-S5) — per-call + per-token metrics, scraped by Prometheus.
# Labels chosen for fan-out ratio: provider × model × tenant_id × status.
# tenant_id label cardinality bounded by tenant count (~hundreds Phase 1,
# scales to thousands Phase 2 — Prometheus handles fine; if we need to
# trim later, drop tenant_id from kaori_ai_tokens_total only and keep
# kaori_ai_calls_total per-tenant for budget alerts).
#
# Defensive registration — multi-worker uvicorn boots more than one
# process and the metrics module gets re-imported. Counter constructor
# raises ValueError("Duplicated timeseries") on second registration in
# the same process; the try/except hand-back makes the module idempotent
# under tests + reload.
def _register_counter(name: str, doc: str, labelnames):
    try:
        return Counter(name, doc, labelnames=labelnames)
    except ValueError:
        from prometheus_client import REGISTRY
        for collector in list(REGISTRY._names_to_collectors.values()):  # type: ignore[attr-defined]
            if getattr(collector, "_name", None) == name:
                return collector
        raise


AI_CALLS_TOTAL = _register_counter(
    "kaori_ai_calls_total",
    "P1-S5 OBS-008 — total LLM dispatch calls. Labels: provider (anthropic/"
    "openai/ollama), model (model_used returned by router), tenant_id, "
    "status (success/validation_failed/upstream_error).",
    labelnames=("provider", "model", "tenant_id", "status"),
)

AI_TOKENS_TOTAL = _register_counter(
    "kaori_ai_tokens_total",
    "P1-S5 OBS-008 — character count proxy for token usage (Phase 1 — real "
    "token counts come Phase 1.5 with provider-side billing API). "
    "Labels: provider, model, tenant_id, direction (input/output).",
    labelnames=("provider", "model", "tenant_id", "direction"),
)


def _emit_call_metric(*, provider: str, model: str, tenant_id: str, status: str) -> None:
    """Single point of metric increment so test fixtures can patch
    one function instead of every callsite."""
    AI_CALLS_TOTAL.labels(
        provider=provider, model=model, tenant_id=tenant_id, status=status,
    ).inc()


def _emit_token_metric(
    *, provider: str, model: str, tenant_id: str,
    input_chars: int, output_chars: int,
) -> None:
    AI_TOKENS_TOTAL.labels(
        provider=provider, model=model, tenant_id=tenant_id, direction="input",
    ).inc(input_chars)
    AI_TOKENS_TOTAL.labels(
        provider=provider, model=model, tenant_id=tenant_id, direction="output",
    ).inc(output_chars)


def _provider_label(method: str, model_used: str) -> str:
    """Map (method, model_used) → metric provider label.

    method='internal' always = ollama. method='external' splits by model
    naming convention (claude-* → anthropic, gpt-* → openai, default
    'external' if we add a vendor we don't recognise yet).
    """
    if method == "internal":
        return "ollama"
    if model_used.startswith("claude"):
        return "anthropic"
    if model_used.startswith(("gpt", "o1", "o3")):
        return "openai"
    return "external"


@router.post("/v1/infer", response_model=InferResponse)
async def infer(req: InferRequest) -> InferResponse:
    pool = get_pool()
    started = time.monotonic()

    # Validate the request actually has text to send. Either prompt or
    # messages must be non-empty — Pydantic can't express "exactly one
    # of" cleanly without a discriminated union, so we check here.
    has_messages = bool(req.messages)
    if not has_messages and not (req.prompt or "").strip():
        raise HTTPException(status_code=422, detail="prompt or messages required")

    # K-20 (P1-LLM-004) — workflow-pinned model wins over task routing.
    # Validates pinned_model + pinned_version come together (not one without
    # the other) so the audit row always carries both. The router picks
    # method based on model name prefix (Phase 1 simple heuristic; Phase
    # 1.5 wires model→method explicit registry).
    if req.pinned_model is not None or req.pinned_version is not None:
        if req.pinned_model is None or req.pinned_version is None:
            raise HTTPException(
                status_code=422,
                detail="K-20: pinned_model and pinned_version must both be set, or both null.",
            )
        model_id = req.pinned_model
        # External vendors by prefix; everything else is internal Ollama.
        if model_id.startswith(("claude-", "gpt-", "o1-", "o3-")):
            method = "external"
        else:
            method = "internal"
    else:
        try:
            model_id, method = await routing.resolve_model(
                pool,
                task=req.task,
                consent_external=req.consent_external,
                model_hint=req.model_hint,
            )
        except Exception as exc:
            log.error("llm_gateway.routing_failed", task=req.task, error=str(exc))
            raise HTTPException(status_code=500, detail="routing failed") from exc

    # K-5: PII never crosses the public-internet boundary.
    if has_messages:
        # Redact only the user/assistant content; tool messages may
        # legitimately carry IDs that would otherwise be eaten by the
        # masker (and they came from us anyway, not the internet).
        scrubbed_messages = []
        for m in req.messages or []:
            md = m.model_dump()
            if method == "external" and md.get("role") in {"user", "system"} and md.get("content"):
                md["content"] = pii.redact(md["content"])
            scrubbed_messages.append(md)
        prompt_for_provider = ""  # unused on chat path
    else:
        scrubbed_messages = []
        prompt_for_provider = pii.redact(req.prompt) if method == "external" else req.prompt

    # Phase 2.7 P2 — quota pre-flight gate. Estimate amount = prompt
    # chars + max_tokens × 4 (rough char-per-token avg). Charges
    # llm_tokens_external when method='external', llm_tokens_local
    # otherwise. QuotaExceeded → 429 RFC 7807; infra failure on the
    # quota path fails OPEN so the primary call isn't blocked when
    # the quota table is unreachable.
    #
    # Defense-in-depth: tenant_quotas already absorbs infra errors via
    # fail_open_on_infra_error=True. We wrap again here so even a
    # contract bug (e.g. unexpected raise) can't 5xx the LLM dispatch.
    # Only QuotaExceeded — the INTENTIONAL rejection — propagates.
    quota_type = "llm_tokens_external" if method == "external" else "llm_tokens_local"
    estimated_chars = (
        sum(len(m.content or "") for m in (req.messages or []))
        if has_messages else len(req.prompt)
    ) + (req.max_tokens * 4)
    try:
        await tenant_quotas.check_and_consume(
            pool,
            enterprise_id=str(req.enterprise_id),
            quota_type=quota_type,
            amount=estimated_chars,
        )
    except tenant_quotas.QuotaExceeded as exc:
        log.warning(
            "llm_gateway.quota_exceeded",
            quota_type=exc.quota_type, period=exc.period,
            enterprise_id=str(req.enterprise_id),
            max_value=exc.max_value, current=exc.current,
        )
        # 429 — Problem Details (K-14). RFC 7807 surfaces quota_type +
        # period so the caller can tell the difference between
        # llm_tokens_external (paid, raise consent_external=False to
        # downgrade) vs llm_tokens_local (always free Qwen, retry next
        # window).
        raise HTTPException(
            status_code=429,
            detail=(
                f"quota '{exc.quota_type}' exceeded for window "
                f"'{exc.period}' (current={exc.current} > max={exc.max_value})"
            ),
        ) from exc
    except Exception:  # noqa: BLE001
        # Defense-in-depth: contract violation in tenant_quotas →
        # fail OPEN, let the call proceed.
        log.exception(
            "llm_gateway.quota_check_unexpected_failure",
            quota_type=quota_type,
            enterprise_id=str(req.enterprise_id),
        )

    # TODO(follow-up): Redis-backed semantic cache lookup keyed by
    # (task, sha256(prompt_for_provider)). Sets cache_hit=True and
    # skips the provider call.
    cache_hit = False

    try:
        if has_messages:
            completion, model_used, tool_calls, finish_reason = await providers.invoke_chat(
                model_id=model_id,
                method=method,
                messages=scrubbed_messages,
                tools=req.tools,
                tool_choice=req.tool_choice,
                max_tokens=req.max_tokens,
            )
        else:
            completion, model_used = await providers.invoke(
                model_id=model_id,
                method=method,
                prompt=prompt_for_provider,
                max_tokens=req.max_tokens,
            )
            tool_calls = None
            finish_reason = "stop"
    except Exception as exc:
        log.error(
            "llm_gateway.provider_failed",
            model=model_id,
            method=method,
            error=str(exc),
        )
        # OBS-008 — record upstream failure before raising so dashboards
        # see the call count even when no completion came back.
        _emit_call_metric(
            provider=_provider_label(method, model_id),
            model=model_id,
            tenant_id=str(req.enterprise_id),
            status="upstream_error",
        )
        raise HTTPException(status_code=502, detail="upstream LLM call failed") from exc

    # Issue #3 — when the caller supplied output_schema, validate the
    # completion. On failure we make ONE repair attempt with an
    # augmented prompt before giving up. The whole roundtrip happens
    # transparently to the caller — they get parsed_json + a flag in
    # output_validation, or a 502 if even the repair fails.
    output_validation_meta: OutputValidation | None = None
    if req.output_schema is not None:
        # Build the retry closure that captures original-call context.
        # Single-prompt path uses providers.invoke; chat path uses
        # invoke_chat with the augmented prompt as a fresh user
        # message so the repair instruction sits at the end of the
        # conversation history.
        if has_messages:
            base_messages = scrubbed_messages

            async def _retry(augmented: str) -> str:
                msgs = base_messages + [{"role": "user", "content": augmented}]
                comp, _, _, _ = await providers.invoke_chat(
                    model_id=model_id,
                    method=method,
                    messages=msgs,
                    tools=None,            # no tools on the repair round
                    tool_choice=None,
                    max_tokens=req.max_tokens,
                )
                return comp
        else:
            async def _retry(augmented: str) -> str:
                comp, _ = await providers.invoke(
                    model_id=model_id,
                    method=method,
                    prompt=augmented,
                    max_tokens=req.max_tokens,
                )
                return comp

        try:
            parsed, was_repaired = await validate_or_repair(
                completion=completion,
                schema=req.output_schema,
                original_prompt=(
                    prompt_for_provider if not has_messages
                    # Chat path: re-state the last user message as the
                    # "original" so the augmented prompt is grounded
                    # in the most recent user request.
                    else next(
                        (m["content"] for m in reversed(scrubbed_messages)
                         if m.get("role") == "user" and m.get("content")),
                        "",
                    )
                ),
                retry_fn=_retry,
            )
        except StructuredOutputError as exc:
            log.error(
                "llm_gateway.output_validation_failed",
                task=req.task,
                attempts=exc.attempts,
                last_error=exc.last_error,
            )
            # OBS-008 — distinct status so dashboards can chart
            # "schema validation failures" separately from upstream errors.
            _emit_call_metric(
                provider=_provider_label(method, model_id),
                model=model_id,
                tenant_id=str(req.enterprise_id),
                status="validation_failed",
            )
            # 502 — the upstream model produced a payload we can't use.
            # The audit row still gets written below with method='external'/
            # 'internal' as appropriate so ops can spot a model that
            # repeatedly fails validation on a particular task.
            raise HTTPException(
                status_code=502,
                detail=f"output validation failed after {exc.attempts} attempts: {exc.reason}",
            ) from exc

        # On the repair round we want the audit log to reflect what
        # the model finally said — not the bad first attempt. The
        # validator returns the parsed dict, so we re-serialise to
        # canonical JSON for the chosen_value column.
        if was_repaired:
            completion = json.dumps(parsed, separators=(",", ":"))

        output_validation_meta = OutputValidation(
            was_repaired=was_repaired,
            attempts=2 if was_repaired else 1,
            parsed_json=parsed,
        )

    latency_ms = int((time.monotonic() - started) * 1000)

    # Reasoning string captures the salient bits without bloating the
    # audit row; full prompt + tools live in structured logs.
    if has_messages:
        prompt_chars = sum(len(m.content or "") for m in (req.messages or []))
        tool_count = len(req.tools or [])
        reasoning = (
            f"chat msgs={len(req.messages or [])} prompt_chars={prompt_chars} "
            f"tools={tool_count} response_chars={len(completion)} "
            f"tool_calls={len(tool_calls or [])} finish={finish_reason} "
            f"latency_ms={latency_ms}"
        )
    else:
        reasoning = (
            f"prompt_chars={len(req.prompt)} response_chars={len(completion)} "
            f"latency_ms={latency_ms}"
        )

    # Issue #3 — annotate the audit row when validation kicked in.
    # ``schema_repaired=true`` is greppable in the audit feed when ops
    # want to spot tasks that disproportionately need a repair round
    # (signal of an undersized model OR a too-strict schema).
    if output_validation_meta is not None:
        reasoning += (
            f" schema_validated=true schema_repaired={str(output_validation_meta.was_repaired).lower()}"
        )

    # OBS-008 (P1-S5) — successful call + token usage. Counter increments
    # are O(1) and don't go through I/O, so emitting here (after the audit
    # block) is fine even on the hot path.
    input_chars = (
        sum(len(m.content or "") for m in (req.messages or []))
        if has_messages else len(req.prompt)
    )
    _emit_call_metric(
        provider=_provider_label(method, model_used),
        model=model_used,
        tenant_id=str(req.enterprise_id),
        status="success",
    )
    _emit_token_metric(
        provider=_provider_label(method, model_used),
        model=model_used,
        tenant_id=str(req.enterprise_id),
        input_chars=input_chars,
        output_chars=len(completion),
    )

    # K-6 + K-20: audit row carries pinned model+version when set so
    # downstream regression analysis can correlate output quality with
    # the exact model build that produced it.
    pinned_suffix = ""
    if req.pinned_model is not None:
        pinned_suffix = f" pinned={req.pinned_model}@{req.pinned_version}"

    # K-6: best-effort audit. log_decision logs DB errors and returns
    # without raising — primary path must not fail on audit miss.
    await audit.log_decision(
        pool,
        enterprise_id=str(req.enterprise_id),
        run_id=str(req.run_id) if req.run_id else None,
        decision_type="llm_call",
        subject=req.task,
        chosen_value=completion,
        method=method,
        llm_provider=model_used,
        reasoning=reasoning + pinned_suffix,
    )

    # Phase 2.7 P3 — AI governance audit (ai_decision_audit). Best-
    # effort parallel writer alongside decision_audit_log: governance
    # captures the CALL (model + prompt hash + refs + confidence);
    # decision_audit_log captures the resulting business decision.
    #
    # Defense-in-depth: ai_governance.record_ai_call already wraps DB
    # work in try/except. We wrap again so even a contract bug can't
    # 5xx the LLM dispatch — the user's response is already computed,
    # the audit gap is recoverable.
    governance_prompt = (
        prompt_for_provider if not has_messages
        else "\n\n".join(
            (m.get("content") or "")
            for m in scrubbed_messages
            if m.get("role") in {"system", "user"}
        )
    )
    try:
        await ai_governance.record_ai_call(
            pool,
            enterprise_id=req.enterprise_id,
            task_kind=req.task,
            model_version=model_used,
            model_provider=_provider_label(method, model_used),
            prompt=governance_prompt,
            output=completion,
            confidence=None,
            output_validated=output_validation_meta is not None,
            consent_external=(method == "external"),
            pii_redacted=(method == "external"),
            run_id=req.run_id,
            latency_ms=latency_ms,
            token_input_count=input_chars,
            token_output_count=len(completion),
        )
    except Exception:  # noqa: BLE001
        log.exception(
            "llm_gateway.governance_audit_unexpected_failure",
            task_kind=req.task,
            enterprise_id=str(req.enterprise_id),
        )

    return InferResponse(
        completion=completion,
        model_used=model_used,
        method=method,
        cache_hit=cache_hit,
        tokens=TokenUsage(
            prompt_chars=(
                sum(len(m.content or "") for m in (req.messages or []))
                if has_messages else len(req.prompt)
            ),
            completion_chars=len(completion),
        ),
        latency_ms=latency_ms,
        tool_calls=tool_calls,
        finish_reason=finish_reason,
        output_validation=output_validation_meta,
        disclosure=build_disclosure(model_used, method),
    )


# ─── POST /v1/embed (P15-S11 — pgvector real impl) ──────────────────


EMBED_CALLS_TOTAL = _register_counter(
    "kaori_ai_embed_calls_total",
    "P15-S11 — total embedding dispatch calls. Labels: model, tenant_id, status.",
    labelnames=("model", "tenant_id", "status"),
)


@router.post("/v1/embed", response_model=EmbedResponse)
async def embed(req: EmbedRequest) -> EmbedResponse:
    """Embed `text` with the local BGE-M3 model and return the vector.

    K-4 invariant: embeddings ALWAYS run locally (Ollama). consent_external
    has no effect; tenant data does not leave the boundary for embedding
    work regardless of opt-in flags. Pinecone / managed-vector adapters
    Phase 2+ land as SEPARATE adapters; this endpoint stays local-only.
    """
    t0 = time.monotonic()
    try:
        vec = await providers.embed_text(req.text)
        status_label = "success"
    except Exception as exc:
        log.error("llm_gateway.embed.failed",
                  enterprise_id=req.enterprise_id, error=str(exc))
        EMBED_CALLS_TOTAL.labels(
            model=providers.EMBEDDING_MODEL,
            tenant_id=req.enterprise_id, status="error",
        ).inc()
        raise HTTPException(status_code=502, detail="embedding upstream failed") from exc

    EMBED_CALLS_TOTAL.labels(
        model=providers.EMBEDDING_MODEL,
        tenant_id=req.enterprise_id, status=status_label,
    ).inc()

    latency_ms = int((time.monotonic() - t0) * 1000)

    # Phase 2.7 P3 — governance audit for embedding calls. K-4 means
    # always local: consent_external=False, pii_redacted=False (nothing
    # crossed the boundary). Defense-in-depth try/except — audit gap
    # is recoverable, an embedding 5xx is not.
    try:
        await ai_governance.record_ai_call(
            get_pool(),
            enterprise_id=req.enterprise_id,
            task_kind="embedding",
            model_version=providers.EMBEDDING_MODEL,
            model_provider="ollama",
            prompt=req.text,
            output="",
            consent_external=False,
            pii_redacted=False,
            latency_ms=latency_ms,
            token_input_count=len(req.text),
            token_output_count=0,
        )
    except Exception:  # noqa: BLE001
        log.exception("llm_gateway.embed.governance_failed",
                       enterprise_id=req.enterprise_id)

    return EmbedResponse(
        vector=vec,
        dim=len(vec),
        model_used=providers.EMBEDDING_MODEL,
        latency_ms=latency_ms,
    )


# ─── POST /v1/ocr (Phase 2.5 — Qwen2.5-VL local-only) ───────────────


OCR_CALLS_TOTAL = _register_counter(
    "kaori_ai_ocr_calls_total",
    "Phase 2.5 — total OCR dispatch calls. Labels: model, tenant_id, status.",
    labelnames=("model", "tenant_id", "status"),
)


@router.post("/v1/ocr", response_model=OcrResponse)
async def ocr(req: OcrRequest) -> OcrResponse:
    """Extract text from a base64-encoded image via the local Qwen2.5-VL.

    K-4 invariant: OCR is ALWAYS local in Phase 2.5. No consent_external
    opt-in path — image bytes carry PII that byte-level redaction can't
    strip before send (CCCD photos, contract scans, receipts). Vendor
    vision adapters are Phase 3 + require a separate ADR. The strict
    `data_residency_strict=true` tenants would refuse external OCR
    anyway; em surface a uniform behavior across tiers.

    Mirrors /v1/embed: timer + try/except + 502 on upstream failure,
    Prometheus counter labelled by model × tenant × status.
    """
    t0 = time.monotonic()
    try:
        text = await providers.ocr_image(
            image_b64=req.image_b64,
            prompt=req.prompt,
            max_tokens=req.max_tokens,
        )
        status_label = "success"
    except Exception as exc:
        log.error("llm_gateway.ocr.failed",
                  enterprise_id=req.enterprise_id, error=str(exc))
        OCR_CALLS_TOTAL.labels(
            model=providers.OCR_MODEL,
            tenant_id=req.enterprise_id, status="error",
        ).inc()
        raise HTTPException(status_code=502, detail="OCR upstream failed") from exc

    OCR_CALLS_TOTAL.labels(
        model=providers.OCR_MODEL,
        tenant_id=req.enterprise_id, status=status_label,
    ).inc()

    latency_ms = int((time.monotonic() - t0) * 1000)

    # Phase 2.7 P3 — governance audit for OCR calls. K-4 enforces local
    # only (image bytes can't be PII-redacted). prompt field captures
    # the override prompt if any; image bytes are NOT hashed into the
    # audit (15 MB cap on the input would blow up SHA hex string size
    # and we already cap prompts at 1 MB in hash_prompt). Defense-in-
    # depth try/except — audit gap is recoverable, an OCR 5xx is not.
    try:
        await ai_governance.record_ai_call(
            get_pool(),
            enterprise_id=req.enterprise_id,
            task_kind="ocr",
            model_version=providers.OCR_MODEL,
            model_provider="ollama",
            prompt=req.prompt or "<default-ocr-prompt>",
            output=text,
            consent_external=False,
            pii_redacted=False,
            latency_ms=latency_ms,
            token_input_count=0,
            token_output_count=len(text),
        )
    except Exception:  # noqa: BLE001
        log.exception("llm_gateway.ocr.governance_failed",
                       enterprise_id=req.enterprise_id)

    return OcrResponse(
        text=text,
        char_count=len(text),
        model_used=providers.OCR_MODEL,
        latency_ms=latency_ms,
    )
