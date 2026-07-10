"""
Tests for /analysis/sources resilience (incident 2026-07-10, demo AABW).

The pilot DB carries the v3-era WIDE ``gold_features`` (one row per
customer: revenue_at_risk, total_purchases, ...) while the repository
queried the long (feature_name, feature_value) shape — the gold query
raised UndefinedColumnError and the WHOLE endpoint 500'd, blanking the
intermediate-tier picker even though silver sources were fine.

Contract pinned here (tenet 13 — per-item failure ≠ abort run):
  * list_gold_sources falls back to the wide schema and still returns
    feature entries;
  * the router degrades per layer: a layer that still fails is skipped
    with a warning, remaining layers are returned with HTTP 200.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import asyncpg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.multi_tier import repository
from ai_orchestrator.routers import multi_tier as multi_tier_router


ENTERPRISE = str(uuid4())


# ── repository.list_gold_sources wide-schema fallback ────────────────────────

@pytest.mark.asyncio
async def test_gold_sources_falls_back_to_wide_schema():
    conn = AsyncMock()
    wide_row = {
        "revenue_at_risk": 42, "total_purchases": 40,
        "purchase_count": 42, "avg_purchase_value": 39,
    }
    conn.fetchrow = AsyncMock(return_value=wide_row)
    conn.fetch = AsyncMock(
        side_effect=asyncpg.exceptions.UndefinedColumnError(
            'column "feature_name" does not exist'
        )
    )

    items = await repository.list_gold_sources(conn)

    labels = {i["id"] for i in items}
    assert "revenue_at_risk" in labels
    assert all(i["layer"] == "gold" for i in items)
    by_id = {i["id"]: i for i in items}
    assert by_id["revenue_at_risk"]["row_count"] == 42
    assert by_id["avg_purchase_value"]["row_count"] == 39


@pytest.mark.asyncio
async def test_gold_sources_long_schema_still_works():
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=[
        {"feature_name": "churn_risk", "row_count": 7},
    ])
    items = await repository.list_gold_sources(conn)
    assert items == [
        {"id": "churn_risk", "label": "churn_risk", "layer": "gold", "row_count": 7},
    ]


# ── router degrade ───────────────────────────────────────────────────────────

@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(multi_tier_router.router)
    return TestClient(app)


def _fake_tenant_conn():
    @asynccontextmanager
    async def _fake(_eid):
        yield AsyncMock()
    return _fake


def test_sources_endpoint_degrades_when_one_layer_fails(client):
    silver = [{"id": "run1", "label": "file.csv", "layer": "silver", "row_count": 108}]
    with patch.object(multi_tier_router, "acquire_for_tenant", _fake_tenant_conn()), \
         patch.object(multi_tier_router.repository, "list_silver_sources",
                      AsyncMock(return_value=silver)), \
         patch.object(multi_tier_router.repository, "list_gold_sources",
                      AsyncMock(side_effect=RuntimeError("schema drift"))):
        r = client.get("/analysis/sources",
                       headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    body = r.json()
    assert [i["id"] for i in body["items"]] == ["run1"]
    assert body.get("warnings"), "failed layer must surface a warning"


def test_sources_endpoint_all_layers_ok_no_warnings(client):
    silver = [{"id": "run1", "label": "f.csv", "layer": "silver", "row_count": 10}]
    gold = [{"id": "revenue_at_risk", "label": "revenue_at_risk",
             "layer": "gold", "row_count": 5}]
    with patch.object(multi_tier_router, "acquire_for_tenant", _fake_tenant_conn()), \
         patch.object(multi_tier_router.repository, "list_silver_sources",
                      AsyncMock(return_value=silver)), \
         patch.object(multi_tier_router.repository, "list_gold_sources",
                      AsyncMock(return_value=gold)):
        r = client.get("/analysis/sources",
                       headers={"X-Enterprise-ID": ENTERPRISE})
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
    assert not r.json().get("warnings")
