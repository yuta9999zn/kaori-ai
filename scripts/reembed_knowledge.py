#!/usr/bin/env python3
"""Re-embed knowledge_documents rows that landed without an embedding (CR-0017).

Seed migrations (e.g. 107_knowledge_seed_retail_sme.sql) insert GLOBAL knowledge
with `embedding = NULL` because SQL can't call the embed service. This ops
script fills those vectors via llm-gateway /v1/embed (BGE-M3) so the RAG engine
can retrieve them. Run ONCE after a knowledge seed migration, with the
llm-gateway reachable.

It is admin-scoped (`SET app.is_admin = 'true'`) so it can UPDATE global
(tenant_id NULL) rows past the tenant-pin RLS policy — mirrors RlsBypassHelper.
Idempotent: only touches rows where embedding IS NULL.

Usage:
    DATABASE_URL=postgres://... \
    LLM_GATEWAY_URL=http://llm-gateway:8095 \
    python scripts/reembed_knowledge.py [--limit N] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg
import httpx

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "bge-m3")
GATEWAY_URL = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8095")
# Embeddings are tenant-agnostic (K-4 local); the gateway still wants an
# enterprise_id for quota/tracing. Use a system id for global-knowledge embeds.
SYSTEM_ENTERPRISE_ID = os.getenv(
    "KAORI_SYSTEM_ENTERPRISE_ID", "00000000-0000-0000-0000-000000000000"
)


def _vec_to_pg(v: list[float]) -> str:
    return "[" + ",".join(repr(float(x)) for x in v) + "]"


async def _embed(client: httpx.AsyncClient, text: str) -> list[float]:
    resp = await client.post(
        f"{GATEWAY_URL}/v1/embed",
        json={"text": text, "enterprise_id": SYSTEM_ENTERPRISE_ID},
    )
    resp.raise_for_status()
    return resp.json().get("vector") or []


async def main(limit: int, dry_run: bool) -> int:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL not set", file=sys.stderr)
        return 2

    conn = await asyncpg.connect(db_url)
    try:
        await conn.execute("SET app.is_admin = 'true'")
        rows = await conn.fetch(
            """SELECT document_id::text AS id, title, content
               FROM knowledge_documents
               WHERE embedding IS NULL AND status = 'active'
               ORDER BY created_at ASC
               LIMIT $1""",
            limit,
        )
        print(f"{len(rows)} knowledge row(s) need an embedding "
              f"(model={EMBEDDING_MODEL}, dry_run={dry_run})")
        if not rows:
            return 0

        done = skipped = 0
        async with httpx.AsyncClient(timeout=60.0) as client:
            for r in rows:
                text = f"{r['title']}\n\n{r['content']}"
                try:
                    vec = await _embed(client, text)
                except Exception as e:  # noqa: BLE001 — report + continue
                    print(f"  ! embed failed {r['id']}: {e}", file=sys.stderr)
                    skipped += 1
                    continue
                if not vec:
                    print(f"  ! empty vector {r['id']} — skipped", file=sys.stderr)
                    skipped += 1
                    continue
                if dry_run:
                    print(f"  ~ would embed {r['id']} ({r['title'][:48]}…)")
                    done += 1
                    continue
                await conn.execute(
                    """UPDATE knowledge_documents
                       SET embedding = $1, embedding_model = $2, updated_at = NOW()
                       WHERE document_id = $3::uuid""",
                    _vec_to_pg(vec), EMBEDDING_MODEL, r["id"],
                )
                print(f"  ✓ embedded {r['id']} ({r['title'][:48]}…)")
                done += 1

        print(f"done: {done} embedded, {skipped} skipped")
        return 0 if skipped == 0 else 1
    finally:
        await conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    raise SystemExit(asyncio.run(main(args.limit, args.dry_run)))
