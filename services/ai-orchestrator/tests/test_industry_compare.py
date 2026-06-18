"""Tests for industry compare (RAG chuyên ngành) — pure parts + flow."""
from __future__ import annotations

from uuid import uuid4

import pytest

from ai_orchestrator.reasoning import industry_compare as ic

ENT = uuid4()


def test_coverage_monotonic():
    assert ic._coverage([]) == 0.0
    c1 = ic._coverage([{"similarity": 0.5}])
    c2 = ic._coverage([{"similarity": 0.5}, {"similarity": 0.5}])
    assert 0 < c1 < c2 < 1


def test_build_findings_cite_kb_by_category():
    metrics = {"customers": 8222, "at_risk_customers": 1, "at_risk_pct": 0.01,
               "total_revenue_at_risk": 320000.0, "avg_revenue_at_risk": 320000.0}
    kb = [
        {"id": "k1", "category": "churn", "title": "Churn", "content": "cửa sổ 90 ngày", "similarity": 0.6},
        {"id": "k2", "category": "pareto", "title": "Pareto", "content": "20/80", "similarity": 0.5},
    ]
    findings = ic._build_findings(metrics, kb)
    topics = {f["topic"] for f in findings}
    assert "Rủi ro rời bỏ" in topics and "Tập trung doanh thu (Pareto)" in topics
    assert all(f["cite"] in ("k1", "k2") for f in findings)


class _FakeConn:
    """Returns gold_aggregates rows, gold counts row, then KB rows in order."""
    def __init__(self, agg, counts, kb):
        self._agg, self._counts, self._kb = agg, counts, kb
        self._fetch_calls = 0

    async def fetch(self, sql, *args):
        self._fetch_calls += 1
        return self._agg if self._fetch_calls == 1 else self._kb

    async def fetchrow(self, sql, *args):
        return self._counts


async def _embed(text, *, enterprise_id):
    return [0.1] * 8


@pytest.mark.asyncio
async def test_compare_done_when_grounded():
    agg = [{"metric_key": "total_revenue_at_risk", "metric_value": 320000.0}]
    counts = {"customers": 8222, "at_risk": 1, "avg_at_risk": 320000.0}
    kb = [{"id": "k1", "tier": 2, "category": "churn", "title": "Churn", "content": "90 ngày",
           "distance": 0.4}, {"id": "k2", "tier": 2, "category": "pareto", "title": "Pareto",
           "content": "20/80", "distance": 0.4}]
    conn = _FakeConn(agg, counts, kb)
    res = await ic.compare_to_industry(conn, ENT, embed_fn=_embed)
    assert res["status"] == "done"
    assert res["metrics"]["customers"] == 8222
    assert len(res["citations"]) == 2
    assert len(res["findings"]) >= 2


@pytest.mark.asyncio
async def test_compare_no_data():
    conn = _FakeConn([], {"customers": 0, "at_risk": 0, "avg_at_risk": 0}, [])
    res = await ic.compare_to_industry(conn, ENT, embed_fn=_embed)
    assert res["status"] == "no_data"


@pytest.mark.asyncio
async def test_compare_insufficient_knowledge():
    agg = [{"metric_key": "total_revenue_at_risk", "metric_value": 0.0}]
    counts = {"customers": 10, "at_risk": 0, "avg_at_risk": 0}
    conn = _FakeConn(agg, counts, [])  # no KB → coverage 0 → decline
    res = await ic.compare_to_industry(conn, ENT, embed_fn=_embed)
    assert res["status"] == "insufficient_knowledge"
