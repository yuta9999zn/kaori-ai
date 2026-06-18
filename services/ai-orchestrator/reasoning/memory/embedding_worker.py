"""
Background embedding worker for the Postgres+pgvector L3 tier.

Periodic scan: find memory_l3 rows where embedding IS NULL, call
llm-gateway /v1/embed for each, fill the column via
PostgresTierStore.set_embedding().

Run modes:
  * embed_pending_for_tenant — single batch, returns count processed.
                                Called by the Temporal workflow (Stage
                                12 follow-up commit) on a 1-minute cron.
  * run_forever               — convenience loop for dev (poll every
                                30s); not used in prod (Temporal owns
                                scheduling).

K-3: uses llm-gateway /v1/embed only — no direct Ollama HTTP.
K-4: embedding endpoint is local-only by design; no consent needed.
K-19: span attribute tenant_id + batch_size on every iteration.
"""
from __future__ import annotations

import asyncio
import os
from typing import Optional
from uuid import UUID

import httpx
import structlog

from .postgres_l3 import EMBEDDING_MODEL, PostgresTierStore

log = structlog.get_logger()


LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")
EMBED_TIMEOUT_S = 30.0
BATCH_SIZE = 50
POLL_INTERVAL_S = 30


async def embed_pending_for_tenant(
    store: PostgresTierStore, tenant_id: UUID, *,
    batch_size: int = BATCH_SIZE,
    gateway_url: Optional[str] = None,
) -> int:
    """Embed up to `batch_size` unembedded rows for one tenant.

    Returns count of rows successfully embedded (0 when nothing
    pending or all calls failed). Failures are logged + skipped;
    they get retried next tick.
    """
    pending = await store.list_unembedded(tenant_id, limit=batch_size)
    if not pending:
        return 0

    url = (gateway_url or LLM_GATEWAY_URL) + "/v1/embed"
    embedded = 0

    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_S) as client:
        for record in pending:
            text = record.content
            if not text or not text.strip():
                continue
            try:
                resp = await client.post(url, json={
                    "text": text[:8000],
                    "enterprise_id": str(tenant_id),
                })
                resp.raise_for_status()
                vec = resp.json().get("vector") or []
            except httpx.HTTPError as e:
                log.warning("memory.l3.embed_failed",
                            record_id=str(record.record_id),
                            tenant_id=str(tenant_id),
                            error=str(e))
                continue
            if not vec:
                continue
            ok = await store.set_embedding(tenant_id, record.record_id, vec,
                                            model_name=EMBEDDING_MODEL)
            if ok:
                embedded += 1

    log.info("memory.l3.embed_batch_done",
             tenant_id=str(tenant_id),
             pending=len(pending), embedded=embedded)
    return embedded


async def run_forever(
    store: PostgresTierStore,
    list_active_tenants: callable,   # async () -> list[UUID]
    *,
    poll_interval_s: int = POLL_INTERVAL_S,
    stop_event: Optional[asyncio.Event] = None,
) -> None:
    """Dev convenience loop. Production uses Temporal workflow."""
    while True:
        if stop_event is not None and stop_event.is_set():
            return
        try:
            tenants = await list_active_tenants()
            for t in tenants:
                await embed_pending_for_tenant(store, t)
        except Exception:
            log.exception("memory.l3.embed_loop_error")
        await asyncio.sleep(poll_interval_s)
