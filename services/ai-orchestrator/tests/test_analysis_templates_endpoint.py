"""
GET /analysis/templates — analysis-template catalogue (demo AABW 2026-07-11).

The FE Basic/Intermediate picker (36-analyst-basic.tsx) fetched its template
list from a retired MSW-only path `/api/v2/enterprise/analysis/templates`,
which has no BE handler → 503 at the edge → the whole page showed
"Có lỗi xảy ra" and both dropdowns were empty. The list must come from the
canonical TEMPLATE_REGISTRY so the picker offers real, runnable templates.

Contract pinned here:
  * GET /analysis/templates → 200 with {items: [{id, name, description}]}
  * items are sourced from TEMPLATE_REGISTRY (real display names, not blanks)
  * catalogue is tenant-agnostic — no X-Enterprise-ID required (gateway JWT
    still gates it at the edge)
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.routers import multi_tier as multi_tier_router


def _client():
    app = FastAPI()
    app.include_router(multi_tier_router.router)
    return TestClient(app)


def test_templates_endpoint_returns_registry():
    r = _client().get("/analysis/templates?tier=basic")
    assert r.status_code == 200
    items = r.json()["items"]
    ids = {i["id"] for i in items}
    # canonical registry entries — real templates, not the MSW mock
    assert "summary_stats" in ids
    assert "time_series" in ids
    # shape the FE Basic picker consumes
    first = items[0]
    assert set(first) >= {"id", "name", "description"}
    assert all(i["name"] for i in items)  # display_name, never blank


def test_templates_endpoint_no_auth_header_needed():
    # catalogue is static/tenant-agnostic; gateway JWT gates it at the edge
    r = _client().get("/analysis/templates")
    assert r.status_code == 200
    assert r.json()["items"]
