"""
Tests for shared.log_context — LogContextMiddleware + bind/unbind helpers.

P1-S1 (OBS-012 / K-19) — every log line in a request scope must carry
tenant_id / user_id / role from gateway-trusted X-* headers. These tests
guard:
  * Headers map to the correct contextvar keys.
  * Missing headers don't bind (no stale data).
  * Unbind on request exit (no leak across requests).
  * Worker bind/unbind helpers behave the same way.
"""
from __future__ import annotations

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.shared.log_context import (
    LogContextMiddleware,
    bind_log_context,
    clear_log_context,
    unbind_log_context,
)


@pytest.fixture(autouse=True)
def _wipe_contextvars():
    """Each test starts with a clean structlog scope. Without this,
    leftover binds from previous tests leak (the whole point of these
    tests is to verify isolation)."""
    structlog.contextvars.clear_contextvars()
    yield
    structlog.contextvars.clear_contextvars()


def _make_app_with_middleware():
    """Tiny FastAPI app that returns the structlog scope as JSON so the
    test can assert what the middleware bound."""
    app = FastAPI()
    app.add_middleware(LogContextMiddleware)

    @app.get("/echo-context")
    async def echo_context():
        return dict(structlog.contextvars.get_contextvars())

    return app


# ---------------------------------------------------------------------------
# LogContextMiddleware behaviour
# ---------------------------------------------------------------------------


def test_middleware_binds_tenant_user_role_from_x_headers():
    """All five mapped headers should land in contextvars under the
    expected keys (matching what Loki + structlog merge_contextvars
    will see)."""
    client = TestClient(_make_app_with_middleware())
    resp = client.get(
        "/echo-context",
        headers={
            "X-Enterprise-Id": "ent_123",
            "X-User-Id": "user_456",
            "X-User-Role": "MANAGER",
            "X-Session-Id": "sess_789",
            "X-Request-Id": "req_abc",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "tenant_id": "ent_123",
        "user_id": "user_456",
        "role": "MANAGER",
        "session_id": "sess_789",
        "request_id": "req_abc",
    }


def test_middleware_binds_only_present_headers():
    """Missing X-* headers must NOT bind — never invent a tenant_id of
    None (downstream RLS would fail in confusing ways)."""
    client = TestClient(_make_app_with_middleware())
    resp = client.get(
        "/echo-context",
        headers={"X-Enterprise-Id": "ent_only"},
    )
    assert resp.status_code == 200
    body = resp.json()
    # Only tenant_id should be set; the others are absent (not None).
    assert body == {"tenant_id": "ent_only"}


def test_middleware_no_headers_means_empty_context():
    """A request with no X-* headers (e.g. /health probe) leaves the
    contextvars dict empty. Logs from this request still get
    service.name + trace_id from other processors."""
    client = TestClient(_make_app_with_middleware())
    resp = client.get("/echo-context")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_middleware_unbinds_after_request():
    """After the response returns, contextvars must be empty so the
    next request on the same worker doesn't inherit tenant_id from the
    previous one (K-12 spirit — never leak tenant identity)."""
    client = TestClient(_make_app_with_middleware())
    client.get(
        "/echo-context",
        headers={"X-Enterprise-Id": "ent_first"},
    )
    # Inspect the worker's structlog scope directly — it should be empty.
    assert structlog.contextvars.get_contextvars() == {}


def test_middleware_isolation_across_requests():
    """Two sequential requests with different tenants must see only
    their own bindings. This guards against the classic worker-pool
    bug where contextvars are reused across requests."""
    app = _make_app_with_middleware()
    client = TestClient(app)

    resp1 = client.get(
        "/echo-context",
        headers={"X-Enterprise-Id": "tenant_a"},
    )
    resp2 = client.get(
        "/echo-context",
        headers={"X-Enterprise-Id": "tenant_b"},
    )
    assert resp1.json() == {"tenant_id": "tenant_a"}
    assert resp2.json() == {"tenant_id": "tenant_b"}


def test_middleware_unbinds_on_exception():
    """If the route raises, the middleware must still unbind. Otherwise
    a 500 error would leave stale tenant_id in worker scope.

    Implementation note: BaseHTTPMiddleware wraps `call_next` such that
    application exceptions are surfaced — our middleware uses try/finally
    so cleanup happens regardless.
    """
    app = FastAPI()
    app.add_middleware(LogContextMiddleware)

    @app.get("/boom")
    async def boom():
        raise RuntimeError("ouch")

    client = TestClient(app, raise_server_exceptions=False)
    client.get("/boom", headers={"X-Enterprise-Id": "tenant_x"})
    # Even though the route raised, the worker scope must be clean.
    assert structlog.contextvars.get_contextvars() == {}


# ---------------------------------------------------------------------------
# Worker helpers (Kafka consumer / outbox poller use case)
# ---------------------------------------------------------------------------


def test_bind_log_context_merges_into_scope():
    bind_log_context(tenant_id="t1", workflow_id="wf1")
    ctx = structlog.contextvars.get_contextvars()
    assert ctx == {"tenant_id": "t1", "workflow_id": "wf1"}


def test_unbind_log_context_removes_keys():
    bind_log_context(tenant_id="t1", workflow_id="wf1", run_id="r1")
    unbind_log_context("workflow_id", "run_id")
    ctx = structlog.contextvars.get_contextvars()
    assert ctx == {"tenant_id": "t1"}


def test_unbind_log_context_with_no_keys_is_noop():
    bind_log_context(tenant_id="t1")
    unbind_log_context()  # no args — should not raise, should not delete
    assert structlog.contextvars.get_contextvars() == {"tenant_id": "t1"}


def test_clear_log_context_wipes_everything():
    bind_log_context(tenant_id="t1", workflow_id="wf1", arbitrary="x")
    clear_log_context()
    assert structlog.contextvars.get_contextvars() == {}
