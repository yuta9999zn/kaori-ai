"""Embedding client for the knowledge base — calls llm-gateway /v1/embed
(BGE-M3, 1024-dim), the same endpoint memory L3 + pgvector RAG use.

K-3/K-4: embeddings go through the gateway, never a vendor SDK; the embed
endpoint is local-only by design.
"""
from __future__ import annotations

import os

import httpx
import structlog

log = structlog.get_logger()

LLM_GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")
EMBED_TIMEOUT_S = float(os.getenv("EMBED_TIMEOUT_S", "30"))


async def embed_text(text: str, *, enterprise_id: str) -> list[float]:
    """Return the BGE-M3 embedding for ``text``. Raises on transport/HTTP
    error so the caller can decide (ingest should surface; a bg re-embed
    should retry). Returns ``[]`` only when the gateway explicitly returns
    no vector."""
    async with httpx.AsyncClient(timeout=EMBED_TIMEOUT_S) as client:
        resp = await client.post(
            f"{LLM_GATEWAY_URL}/v1/embed",
            json={"text": text, "enterprise_id": enterprise_id},
        )
        resp.raise_for_status()
        return resp.json().get("vector") or []
