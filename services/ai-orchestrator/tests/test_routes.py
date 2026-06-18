"""
Routing-correctness tests for ai-orchestrator.

These guard the contract between the FastAPI mount points in main.py and
the gateway's rewrite filter:
    gateway:   /api/v1/(.*)  →  /$1
    service:   handlers must therefore listen at /$1, NOT /api/v1/$1

If anyone re-introduces an /api/v1 prefix on a router mount, every
frontend call to that router 404s at the orchestrator. These assertions
fail fast in CI before that ships.

We use FastAPI's app.routes inventory directly — no TestClient, no
lifespan, no DB / Kafka init. Static introspection only.
"""
import importlib
import pytest


@pytest.fixture(scope="module")
def app_routes() -> set[str]:
    """Set of mounted path patterns on the orchestrator app."""
    main = importlib.import_module("ai_orchestrator.main")
    # APIRoute.path holds the registered FastAPI path (with {param} placeholders).
    return {getattr(r, "path", None) for r in main.app.routes if getattr(r, "path", None)}


# ─── Frontend client.ts paths the orchestrator must serve ──────────────────────

EXPECTED_ORCHESTRATOR_PATHS = [
    # analytics router
    "/analytics/templates",
    "/analytics/runs",
    "/analytics/runs/{analysis_run_id}",
    # strategy router
    "/strategy/ask",
    "/ai/query",
    "/ai/recommendations",
    # dashboard router
    "/dashboard/state",
    "/insights/feed",
    "/billing/summary",
    # decisions router (F-029)
    "/decisions",
    "/decisions/export.csv",
    # chat router (Sprint 8)
    "/chat/enterprise/stream",
    "/chat/platform/stream",
    # multi-tier analysis router (F-033 PR A + PR B approve endpoint)
    "/analysis/sources",
    "/analysis/cross-workspaces",
    "/analysis/quota/external-ai",
    "/analysis/runs",
    "/analysis/runs/{run_id}",
    "/analysis/runs/{run_id}/approve",
    # explainability (F-041)
    "/explainability/explain",
    # health
    "/health",
    "/health/ready",
]


@pytest.mark.parametrize("path", EXPECTED_ORCHESTRATOR_PATHS)
def test_route_is_mounted_at_expected_path(app_routes, path):
    """Every frontend-visible orchestrator path is mounted at the bare
    (no-/api/v1) path. The gateway adds the /api/v1 prefix for callers."""
    assert path in app_routes, (
        f"orchestrator route {path!r} not found.\n"
        f"This usually means main.py mounted a router with the wrong prefix.\n"
        f"Currently mounted paths: {sorted(app_routes)}"
    )


# ─── Negative guard: prefix must NOT be /api/v1 ────────────────────────────────

DOUBLE_PREFIX_REGRESSION_PATHS = [
    "/api/v1/analytics/templates",
    "/api/v1/analytics/runs",
    "/api/v1/dashboard/state",
    "/api/v1/insights/feed",
    "/api/v1/billing/summary",
    "/api/v1/strategy/ask",
]


@pytest.mark.parametrize("path", DOUBLE_PREFIX_REGRESSION_PATHS)
def test_no_double_api_v1_prefix(app_routes, path):
    """Regression guard for the orchestrator double-prefix bug.

    The gateway already rewrites /api/v1/X → /X before forwarding. If a
    router is mounted with prefix='/api/v1' (or '/api/v1/something'), the
    orchestrator ends up listening at /api/v1/X and the rewritten request
    misses → 404.

    This test fails the moment a router is mounted with /api/v1 again.
    """
    assert path not in app_routes, (
        f"orchestrator must NOT expose {path!r}. The gateway rewrites "
        f"/api/v1/X → /X, so handlers should be mounted at /X without "
        f"the /api/v1 prefix. See main.py include_router calls."
    )
