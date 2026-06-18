"""
P2-S21 D4 — startup hook for TraceDistillerWorker.

Long-running asyncio task that wraps `TraceDistillerWorker.run_once()`
in a poll loop. Env-gated so Phase 1.5 stays off-by-default; flip on
per deployment when MemoryService backend is wired to the production
Postgres adapter.

Env vars
--------
TRACE_DISTILLER_ENABLED       "true" / "1" → start the runner (default off)
TRACE_DISTILLER_POLL_SECONDS  poll interval (default 300 = 5 min)
TRACE_DISTILLER_BATCH_SIZE    rows per batch (default 20)
TRACE_DISTILLER_CONFIDENCE    confidence threshold (default 0.6)

LLM_GATEWAY_URL               base URL of llm-gateway service
                              (default http://llm-gateway:8095)
LLM_GATEWAY_TASK              task name forwarded to the gateway router
                              (default "trace_distillation")
LLM_GATEWAY_TIMEOUT_SECONDS   per-call HTTP timeout (default 60.0)
LLM_GATEWAY_USE_STUB          "true" → bypass HTTP, use in-process stub
                              (default off; useful for local dev / tests)

Side-effect class (K-17): the loop body is `write_idempotent` per
worker docstring. The runner itself is plumbing — no decisions, no
state ownership.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional

import structlog

log = structlog.get_logger()


def _env_truthy(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        log.warning("trace_distiller.env.invalid_int",
                    name=name, raw=raw, default=default)
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        log.warning("trace_distiller.env.invalid_float",
                    name=name, raw=raw, default=default)
        return default


def is_enabled() -> bool:
    """Public predicate so callers can fast-skip construction when off."""
    return _env_truthy("TRACE_DISTILLER_ENABLED")


async def run_distiller_loop(stop_event: asyncio.Event) -> None:
    """Poll loop. Builds worker once at startup, then calls run_once()
    every poll_interval seconds until stop_event is set.

    Designed for the standard FastAPI lifespan pattern::

        stop_event = asyncio.Event()
        task = asyncio.create_task(run_distiller_loop(stop_event))
        ...
        stop_event.set()
        await asyncio.wait_for(task, timeout=10.0)

    If the env gate is off, the function returns immediately — caller
    can always schedule the task; it's cheap when disabled.
    """
    if not is_enabled():
        log.info("trace_distiller.disabled")
        return

    poll_seconds = _env_int("TRACE_DISTILLER_POLL_SECONDS", 300)
    batch_size = _env_int("TRACE_DISTILLER_BATCH_SIZE", 20)
    confidence = _env_float("TRACE_DISTILLER_CONFIDENCE", 0.6)

    # Late imports keep this module cheap when disabled.
    from ...shared import db as db_module
    from ..memory.service import MemoryService
    from .transformer import TCubeTransformer
    from .worker import TraceDistillerWorker

    pool = db_module.get_pool()
    if pool is None:
        log.error("trace_distiller.no_pool")
        return

    # Phase 1.5: LLM client is a stub for now — wiring to the real
    # llm-gateway adapter is the follow-up. The worker still runs the
    # full DB → distill (stub) → mark cycle so we can verify end-to-end
    # plumbing under load testing.
    llm_client = _build_llm_client()
    transformer = TCubeTransformer(llm_client)
    memsvc = MemoryService()  # InMemory default — production swap is env-var
    worker = TraceDistillerWorker(
        db=pool,
        transformer=transformer,
        memory_service=memsvc,
        confidence_threshold=confidence,
    )

    log.info("trace_distiller.started",
             poll_seconds=poll_seconds,
             batch_size=batch_size,
             confidence=confidence)

    while not stop_event.is_set():
        try:
            stats = await worker.run_once(batch_size=batch_size)
            if stats.candidates_scanned:
                log.info("trace_distiller.cycle",
                         scanned=stats.candidates_scanned,
                         ok=stats.distilled_ok,
                         failed=stats.distilled_failed,
                         skipped_conf=stats.skipped_low_conf,
                         skipped_retry=stats.skipped_max_retry)
        except Exception:
            log.exception("trace_distiller.cycle_error")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=poll_seconds)
        except asyncio.TimeoutError:
            continue

    log.info("trace_distiller.stopped")


_DEFAULT_LLM_GATEWAY_URL      = "http://llm-gateway:8095"
_DEFAULT_LLM_GATEWAY_TIMEOUT  = 60.0  # seconds
_DEFAULT_LLM_GATEWAY_TASK     = "trace_distillation"


def _build_llm_client():
    """Build the LLM client used by TCubeTransformer.

    Production path: returns a thin httpx-based async client that calls
    POST /v1/infer on llm-gateway. Reads URL from env var
    LLM_GATEWAY_URL (default http://llm-gateway:8095).

    Fallback path: when env var LLM_GATEWAY_USE_STUB is truthy, returns
    a stub that emits canned per-form text. Used by unit tests + local
    dev when llm-gateway isn't running.

    K-3: every LLM call goes through llm-gateway (never direct provider SDK).
    K-4: consent_external=False in the body → Qwen-local by default.
    K-20: optional `model` arg becomes pinned_model in the request body.
    """
    if _env_truthy("LLM_GATEWAY_USE_STUB"):
        return _StubLLM()

    return _LLMGatewayClient(
        base_url=os.getenv("LLM_GATEWAY_URL", _DEFAULT_LLM_GATEWAY_URL),
        task=os.getenv("LLM_GATEWAY_TASK", _DEFAULT_LLM_GATEWAY_TASK),
        timeout=_env_float("LLM_GATEWAY_TIMEOUT_SECONDS",
                           _DEFAULT_LLM_GATEWAY_TIMEOUT),
    )


class _StubLLM:
    """Local-dev / test stub. Returns canned text per prompt marker so
    the distillation pipeline runs E2E without a live LLM."""

    async def complete(self, *, tenant_id, prompt, max_tokens, model=None):
        if "5 BƯỚC" in prompt or "5 BUOC" in prompt:
            return "1. Đọc data\n2. Xử lý\n3. Quyết định\n4. Hành động\n5. Đo lường"
        if "INSIGHT" in prompt:
            return "Khi tình huống X, làm Y để đạt Z."
        return "- BẪY: chưa có pattern nổi bật | TRÁNH: theo dõi step đầu."


class _LLMGatewayClient:
    """Async adapter satisfying trace_distiller._LLMClient Protocol.

    Wraps POST /v1/infer on llm-gateway. The endpoint enforces routing
    (Qwen-local default per K-4), token budget, and audit logging — all
    cross-cutting concerns we don't repeat here.
    """

    def __init__(self, *, base_url: str, task: str, timeout: float):
        self._base_url = base_url.rstrip("/")
        self._task     = task
        self._timeout  = timeout

    async def complete(self, *, tenant_id, prompt, max_tokens, model=None):
        import httpx
        body = {
            "task":             self._task,
            "prompt":           prompt,
            "enterprise_id":    str(tenant_id),
            "consent_external": False,        # K-4: distillation stays internal
            "max_tokens":       max_tokens,
        }
        if model is not None:
            body["pinned_model"]   = model    # K-20
            # pinned_model REQUIRES pinned_version per llm-gateway contract;
            # we ship a static date stamp matching the distiller's model pin.
            # When TCubeTransformer is given an explicit distiller_version,
            # callers should plumb it through here. For now, use the
            # current month as a coarse-grained stamp.
            from datetime import date
            body["pinned_version"] = date.today().strftime("%Y-%m")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            r = await client.post(f"{self._base_url}/v1/infer", json=body)
            r.raise_for_status()
            data = r.json()
            return data["completion"]
