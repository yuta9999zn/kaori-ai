"""
F-016 — K-4 enforcement tests for the llm_router HTTP shim.

K-4 invariant: external LLM calls are refused unless the calling tenant
has set ``tenant_settings.consent_external_ai = TRUE``. The shim looks
up the flag (cached 60s) and raises :class:`ConsentDeniedError` rather
than forwarding ``consent_external=true`` to the gateway when the tenant
hasn't opted in.

These tests stub both the DB layer (``acquire_for_tenant``) and the HTTP
layer (``httpx.AsyncClient.post``) so nothing real runs.
"""
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import httpx
import pytest

from ai_orchestrator.engine import llm_router as shim
from ai_orchestrator.engine.llm_router import ConsentDeniedError


def _fake_acquire_factory(consent_value, *, raises=None, call_counter=None):
    """Build an async-context-manager that yields a fake asyncpg connection
    whose ``fetchrow`` returns ``{"consent_external_ai": consent_value}``.

    If ``raises`` is set, the context manager raises that exception instead
    of yielding — used to test the fail-closed path.
    """

    @asynccontextmanager
    async def fake_acquire(enterprise_id):
        if call_counter is not None:
            call_counter["count"] += 1
        if raises is not None:
            raise raises
        fake_conn = AsyncMock()
        if consent_value is None:
            fake_conn.fetchrow = AsyncMock(return_value=None)
        else:
            fake_conn.fetchrow = AsyncMock(
                return_value={"consent_external_ai": consent_value}
            )
        yield fake_conn

    return fake_acquire


def _ok_gateway_response():
    return httpx.Response(
        200,
        request=httpx.Request("POST", "http://gw/v1/infer"),
        json={
            "completion": "ok",
            "model_used": "claude-sonnet-4-6",
            "method": "external",
            "cache_hit": False,
            "tokens": {"prompt_chars": 1, "completion_chars": 2},
            "latency_ms": 5,
        },
    )


@pytest.fixture(autouse=True)
def _clear_consent_cache():
    """Each test starts with an empty cache so we don't see leakage between
    cases (tests run in arbitrary order)."""
    shim._invalidate_consent_cache()
    yield
    shim._invalidate_consent_cache()


# =========================================================================
# K-4 enforcement matrix
# =========================================================================

@pytest.mark.asyncio
async def test_default_consent_false_skips_db_lookup_and_forwards():
    """consent_external=False (caller default) is the hot path for analytics
    runner — must NOT trigger a DB query per LLM call."""
    counter = {"count": 0}
    fake_acquire = _fake_acquire_factory(False, call_counter=counter)

    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["json"] = json
        return _ok_gateway_response()

    with patch.object(shim, "acquire_for_tenant", fake_acquire), \
         patch("httpx.AsyncClient.post", _fake_post):
        out = await shim.llm_router.complete(
            "p", task="t", enterprise_id=str(uuid4())
        )

    assert out == "ok"
    assert counter["count"] == 0, "DB must not be queried when consent_external=False"
    assert captured["json"]["consent_external"] is False


@pytest.mark.asyncio
async def test_consent_external_true_with_no_enterprise_id_raises_immediately():
    """Background callers without tenant context cannot reach external LLMs."""
    with pytest.raises(ConsentDeniedError) as exc:
        await shim.llm_router.complete(
            "p", task="t", consent_external=True, enterprise_id=""
        )
    assert "tenant context" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_consent_external_true_with_db_consent_false_raises():
    """DB row exists but flag is FALSE → refuse the external call."""
    fake_acquire = _fake_acquire_factory(False)

    async def _fake_post(self, url, json=None, **kw):
        pytest.fail("Gateway POST must not happen when K-4 refuses")

    with patch.object(shim, "acquire_for_tenant", fake_acquire), \
         patch("httpx.AsyncClient.post", _fake_post):
        with pytest.raises(ConsentDeniedError) as exc:
            await shim.llm_router.complete(
                "p", task="t", consent_external=True, enterprise_id=str(uuid4())
            )
    assert "consent_external_ai" in str(exc.value)


@pytest.mark.asyncio
async def test_consent_external_true_with_db_consent_true_forwards():
    """Happy path: DB consent TRUE → forward consent_external=True to gateway."""
    fake_acquire = _fake_acquire_factory(True)

    captured: dict = {}

    async def _fake_post(self, url, json=None, **kw):
        captured["json"] = json
        return _ok_gateway_response()

    with patch.object(shim, "acquire_for_tenant", fake_acquire), \
         patch("httpx.AsyncClient.post", _fake_post):
        out = await shim.llm_router.complete(
            "p", task="t", consent_external=True, enterprise_id=str(uuid4())
        )

    assert out == "ok"
    assert captured["json"]["consent_external"] is True


@pytest.mark.asyncio
async def test_missing_tenant_settings_row_treated_as_no_consent():
    """A tenant with no tenant_settings row yet → consent default FALSE,
    so external is refused. Lazy-create happens when the MANAGER opens the
    settings page; until then K-4 stays closed."""
    fake_acquire = _fake_acquire_factory(None)  # fetchrow returns None

    with patch.object(shim, "acquire_for_tenant", fake_acquire):
        with pytest.raises(ConsentDeniedError):
            await shim.llm_router.complete(
                "p", task="t", consent_external=True, enterprise_id=str(uuid4())
            )


@pytest.mark.asyncio
async def test_db_error_fails_closed():
    """DB blip while resolving consent → treat as FALSE, refuse external.
    Better to refuse a legitimate call than to leak data on a transient bug."""
    fake_acquire = _fake_acquire_factory(False, raises=RuntimeError("pool exhausted"))

    with patch.object(shim, "acquire_for_tenant", fake_acquire):
        with pytest.raises(ConsentDeniedError):
            await shim.llm_router.complete(
                "p", task="t", consent_external=True, enterprise_id=str(uuid4())
            )


@pytest.mark.asyncio
async def test_consent_lookup_is_cached_within_ttl():
    """Two consecutive calls for the same tenant should hit the DB at most
    once — analytics runs spawn many LLM calls per tenant per minute."""
    counter = {"count": 0}
    fake_acquire = _fake_acquire_factory(True, call_counter=counter)

    async def _fake_post(self, url, json=None, **kw):
        return _ok_gateway_response()

    eid = str(uuid4())
    with patch.object(shim, "acquire_for_tenant", fake_acquire), \
         patch("httpx.AsyncClient.post", _fake_post):
        await shim.llm_router.complete("p", task="t",
                                       consent_external=True, enterprise_id=eid)
        await shim.llm_router.complete("q", task="t",
                                       consent_external=True, enterprise_id=eid)

    assert counter["count"] == 1, f"Expected 1 DB lookup, got {counter['count']}"
