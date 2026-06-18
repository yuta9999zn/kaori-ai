"""Industry comparison — benchmark a tenant's Gold metrics against curated
domain (SME-retail) knowledge (reviewer item: "so sánh với RAG chuyên ngành").

Rule-first / grounded (K-3, same stance as the workflow advisor + doc analyzer):
the comparison surfaces the tenant's ACTUAL metrics (gold_features /
gold_aggregates) alongside the relevant industry heuristics RETRIEVED from
knowledge_documents (bge-m3 cosine) — every claim cites a KB doc, nothing is
invented. Gated by the ADR-0033 |OR| coverage gate: no industry knowledge
retrieved → decline ("chưa đủ tri thức ngành"), don't guess.

Fast: one embed call + two SQL reads, no LLM synthesis (the citations ARE the
grounding). An optional Qwen narrative is a later enrichment.
"""
from __future__ import annotations

import math
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from .knowledge.grounding import coverage_gate

log = structlog.get_logger()

_COVERAGE_K = 0.6


async def _load_metrics(conn, enterprise_id: UUID) -> dict:
    """Tenant's Gold rollup — customer count, at-risk count + value, AOV proxy."""
    agg = await conn.fetch(
        "SELECT metric_key, metric_value FROM gold_aggregates WHERE enterprise_id = $1",
        enterprise_id,
    )
    aggregates = {r["metric_key"]: float(r["metric_value"]) for r in agg}
    counts = await conn.fetchrow(
        """SELECT COUNT(*) AS customers,
                  COUNT(*) FILTER (WHERE revenue_at_risk > 0) AS at_risk,
                  COALESCE(AVG(NULLIF(revenue_at_risk, 0)), 0) AS avg_at_risk
           FROM gold_features WHERE enterprise_id = $1""",
        enterprise_id,
    )
    customers = int(counts["customers"] or 0)
    at_risk = int(counts["at_risk"] or 0)
    return {
        "customers": customers,
        "at_risk_customers": at_risk,
        "at_risk_pct": round(100.0 * at_risk / customers, 2) if customers else 0.0,
        "total_revenue_at_risk": aggregates.get("total_revenue_at_risk", 0.0),
        "avg_revenue_at_risk": round(float(counts["avg_at_risk"] or 0), 2),
    }


async def _load_industry_kb(conn, query_vec: list[float], *, top_k: int = 5) -> list[dict]:
    """Top-k industry knowledge docs by stored-embedding cosine (RLS: global + own)."""
    from .knowledge.store import EMBEDDING_MODEL, _vec_to_pg
    rows = await conn.fetch(
        """SELECT document_id::text AS id, tier, category, title, content,
                  embedding <=> $1 AS distance
           FROM knowledge_documents
           WHERE embedding IS NOT NULL AND embedding_model = $2 AND status = 'active'
           ORDER BY embedding <=> $1
           LIMIT $3""",
        _vec_to_pg(query_vec), EMBEDDING_MODEL, top_k,
    )
    return [{
        "id": r["id"], "tier": r["tier"], "category": r["category"],
        "title": r["title"], "content": r["content"],
        "similarity": round(1.0 - float(r["distance"]), 4),
    } for r in rows]


def _coverage(kb: list[dict]) -> float:
    """Saturating |OR| coverage from the retrieved KB similarities."""
    mass = sum(max(0.0, d["similarity"]) for d in kb)
    return round(1.0 - math.exp(-_COVERAGE_K * mass), 4)


def _build_findings(metrics: dict, kb: list[dict]) -> list[dict]:
    """Templated, CITED comparisons — tenant metric vs the relevant industry
    heuristic. Rule-based (no LLM): each finding points at a KB doc by category."""
    by_cat = {d["category"]: d for d in kb}
    out: list[dict] = []

    if "churn" in by_cat and metrics["customers"]:
        d = by_cat["churn"]
        out.append({
            "topic": "Rủi ro rời bỏ",
            "tenant": f"{metrics['at_risk_customers']}/{metrics['customers']} khách "
                      f"({metrics['at_risk_pct']}%) ở mức rủi ro; "
                      f"{metrics['total_revenue_at_risk']:,.0f}₫ doanh thu at-risk.",
            "industry": f"[{d['title']}] {(d['content'] or '')[:160]}",
            "cite": d["id"],
        })
    if "pareto" in by_cat:
        d = by_cat["pareto"]
        out.append({
            "topic": "Tập trung doanh thu (Pareto)",
            "tenant": f"{metrics['customers']} khách trong Gold — rà soát 20% top "
                      "đóng góp bao nhiêu % doanh thu.",
            "industry": f"[{d['title']}] {(d['content'] or '')[:160]}",
            "cite": d["id"],
        })
    if "retention" in by_cat:
        d = by_cat["retention"]
        out.append({
            "topic": "Chiến thuật giữ chân",
            "tenant": f"AOV at-risk trung bình ≈ {metrics['avg_revenue_at_risk']:,.0f}₫ — "
                      "chọn win-back theo giá trị + recency.",
            "industry": f"[{d['title']}] {(d['content'] or '')[:160]}",
            "cite": d["id"],
        })
    if "rfm" in by_cat:
        d = by_cat["rfm"]
        out.append({
            "topic": "Phân khúc RFM",
            "tenant": "Dùng recency/frequency/monetary từ Gold để phân khúc khách.",
            "industry": f"[{d['title']}] {(d['content'] or '')[:160]}",
            "cite": d["id"],
        })
    return out


async def compare_to_industry(conn, enterprise_id: UUID, *, embed_fn) -> dict:
    """Benchmark the tenant's Gold metrics against the SME-retail KB. embed_fn is
    an async (text, enterprise_id) -> vector (injected for testability)."""
    metrics = await _load_metrics(conn, enterprise_id)
    if metrics["customers"] == 0:
        return {"status": "no_data",
                "note": "Chưa có dữ liệu Gold — chạy phân tích dữ liệu trước."}

    query = ("phân tích bán lẻ SME: phân khúc RFM, quy tắc Pareto doanh thu, "
             "dấu hiệu khách rời bỏ và playbook giữ chân khách")
    try:
        qvec = await embed_fn(query, enterprise_id=str(enterprise_id))
    except Exception as e:  # pragma: no cover
        log.warning("industry_compare.embed_failed", error=str(e))
        qvec = []

    kb = await _load_industry_kb(conn, qvec) if qvec else []
    coverage = _coverage(kb)
    gate = coverage_gate(coverage)
    if not gate["can_generalize"]:
        return {"status": "insufficient_knowledge", "coverage": coverage,
                "metrics": metrics,
                "note": "Chưa đủ tri thức ngành để so sánh — cần bổ sung KB ngành."}

    return {
        "status": "done",
        "metrics": metrics,
        "coverage": coverage,
        "band": gate["band"],
        "findings": _build_findings(metrics, kb),
        "citations": [{"id": d["id"], "title": d["title"],
                       "category": d["category"], "similarity": d["similarity"]} for d in kb],
    }
