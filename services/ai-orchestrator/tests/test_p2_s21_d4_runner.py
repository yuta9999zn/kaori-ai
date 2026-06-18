"""
P2-S21 D4 — runner.py tests.

Verifies the env-gated startup-hook behaviour:
  1. Disabled-by-default returns immediately
  2. Enabled but no DB pool → log error + return
  3. stop_event fires → loop exits cleanly
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from ai_orchestrator.reasoning.trace_distiller import runner


# ─── env gate ─────────────────────────────────────────────────────────


class TestEnvGate:

    def test_disabled_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("TRACE_DISTILLER_ENABLED", raising=False)
        assert runner.is_enabled() is False

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", "FALSE", "  "])
    def test_disabled_for_falsy(self, monkeypatch, val):
        monkeypatch.setenv("TRACE_DISTILLER_ENABLED", val)
        assert runner.is_enabled() is False

    @pytest.mark.parametrize("val", ["true", "1", "yes", "on", "TRUE", "On"])
    def test_enabled_for_truthy(self, monkeypatch, val):
        monkeypatch.setenv("TRACE_DISTILLER_ENABLED", val)
        assert runner.is_enabled() is True

    def test_env_int_falls_back_on_invalid(self, monkeypatch):
        monkeypatch.setenv("TRACE_DISTILLER_POLL_SECONDS", "not-a-number")
        assert runner._env_int("TRACE_DISTILLER_POLL_SECONDS", 42) == 42

    def test_env_float_falls_back_on_invalid(self, monkeypatch):
        monkeypatch.setenv("TRACE_DISTILLER_CONFIDENCE", "qwerty")
        assert runner._env_float("TRACE_DISTILLER_CONFIDENCE", 0.5) == 0.5


# ─── loop lifecycle ───────────────────────────────────────────────────


class TestLoopLifecycle:

    @pytest.mark.asyncio
    async def test_returns_immediately_when_disabled(self, monkeypatch):
        monkeypatch.setenv("TRACE_DISTILLER_ENABLED", "false")
        stop_event = asyncio.Event()
        # Should NOT hang — disabled path is a fast return
        await asyncio.wait_for(runner.run_distiller_loop(stop_event), timeout=1.0)

    @pytest.mark.asyncio
    async def test_returns_when_no_db_pool(self, monkeypatch):
        monkeypatch.setenv("TRACE_DISTILLER_ENABLED", "true")
        # Patch db_module.get_pool to return None
        with patch("ai_orchestrator.shared.db.get_pool", return_value=None):
            stop_event = asyncio.Event()
            await asyncio.wait_for(runner.run_distiller_loop(stop_event), timeout=1.0)

    @pytest.mark.asyncio
    async def test_stop_event_exits_loop_promptly(self, monkeypatch):
        """When the loop is enabled + has a pool, setting stop_event must
        cause the next `await stop_event.wait()` to return so the loop
        exits without waiting the full poll interval."""
        monkeypatch.setenv("TRACE_DISTILLER_ENABLED", "true")
        monkeypatch.setenv("TRACE_DISTILLER_POLL_SECONDS", "300")

        # Pool stub that returns 0 candidates so run_once is fast
        class _StubPool:
            async def fetch(self, *_a, **_kw):
                return []
            async def fetchrow(self, *_a, **_kw):
                return None
            async def execute(self, *_a, **_kw):
                return None

        with patch("ai_orchestrator.shared.db.get_pool", return_value=_StubPool()):
            stop_event = asyncio.Event()
            task = asyncio.create_task(runner.run_distiller_loop(stop_event))
            # Let the loop run one cycle
            await asyncio.sleep(0.05)
            stop_event.set()
            # Must exit within 2 seconds (not the 300s poll interval)
            await asyncio.wait_for(task, timeout=2.0)


# ─── stub LLM ────────────────────────────────────────────────────────


class TestStubLLM:

    @pytest.mark.asyncio
    async def test_stub_returns_for_each_prompt_type(self, monkeypatch):
        monkeypatch.setenv("LLM_GATEWAY_USE_STUB", "true")
        llm = runner._build_llm_client()
        struct = await llm.complete(tenant_id="t1", prompt="5 BƯỚC SẠCH",
                                    max_tokens=100)
        semantic = await llm.complete(tenant_id="t1", prompt="INSIGHT CỐT LÕI",
                                      max_tokens=100)
        reflect = await llm.complete(tenant_id="t1", prompt="BẪY",
                                     max_tokens=100)
        assert struct.startswith("1.")
        assert "Khi" in semantic
        assert "BẪY" in reflect


# ─── llm-gateway adapter (HTTP path) ─────────────────────────────────


class TestLLMGatewayClient:

    def test_factory_defaults_to_gateway_client(self, monkeypatch):
        monkeypatch.delenv("LLM_GATEWAY_USE_STUB", raising=False)
        client = runner._build_llm_client()
        assert isinstance(client, runner._LLMGatewayClient)
        # Default URL is the docker-compose service name
        assert client._base_url.endswith(":8095")
        assert client._task == "trace_distillation"

    def test_factory_respects_url_override(self, monkeypatch):
        monkeypatch.delenv("LLM_GATEWAY_USE_STUB", raising=False)
        monkeypatch.setenv("LLM_GATEWAY_URL", "http://custom:9999/")
        monkeypatch.setenv("LLM_GATEWAY_TASK", "custom_task")
        monkeypatch.setenv("LLM_GATEWAY_TIMEOUT_SECONDS", "30")
        client = runner._build_llm_client()
        assert client._base_url == "http://custom:9999"   # trailing slash stripped
        assert client._task == "custom_task"
        assert client._timeout == 30.0

    def test_factory_use_stub_env_returns_stub(self, monkeypatch):
        monkeypatch.setenv("LLM_GATEWAY_USE_STUB", "true")
        client = runner._build_llm_client()
        assert isinstance(client, runner._StubLLM)

    @pytest.mark.asyncio
    async def test_gateway_client_posts_to_v1_infer(self, monkeypatch):
        """Verify the HTTP body shape: K-3 task name, K-4 consent_external
        default False, K-20 pinned_model passed through when model arg set."""
        from unittest.mock import AsyncMock, MagicMock, patch as mock_patch

        captured: dict = {}

        class _FakeResponse:
            def raise_for_status(self):
                return None
            def json(self):
                return {"completion": "fake answer", "model_used": "qwen2.5:14b",
                        "method": "internal", "cache_hit": False,
                        "tokens": {"prompt_chars": 1, "completion_chars": 1},
                        "latency_ms": 5}

        class _FakeClient:
            def __init__(self, **_kw):
                pass
            async def __aenter__(self):
                return self
            async def __aexit__(self, *_a):
                return False
            async def post(self, url, json=None):
                captured["url"] = url
                captured["body"] = json
                return _FakeResponse()

        client = runner._LLMGatewayClient(
            base_url="http://x:8095", task="trace_distillation", timeout=10.0
        )
        with mock_patch("httpx.AsyncClient", _FakeClient):
            result = await client.complete(
                tenant_id="11111111-1111-1111-1111-111111111111",
                prompt="test prompt",
                max_tokens=600,
                model="qwen2.5:14b",
            )
        assert result == "fake answer"
        assert captured["url"] == "http://x:8095/v1/infer"
        body = captured["body"]
        # K-3
        assert body["task"] == "trace_distillation"
        # K-4 — consent_external defaults False (distillation stays Qwen-local)
        assert body["consent_external"] is False
        # K-20 — pinned_model + pinned_version when model arg supplied
        assert body["pinned_model"] == "qwen2.5:14b"
        assert "pinned_version" in body
        # tenant_id stringified
        assert body["enterprise_id"] == "11111111-1111-1111-1111-111111111111"
        assert body["max_tokens"] == 600

    @pytest.mark.asyncio
    async def test_gateway_client_omits_pinned_when_no_model(self, monkeypatch):
        from unittest.mock import patch as mock_patch

        captured: dict = {}

        class _FakeResponse:
            def raise_for_status(self): return None
            def json(self):
                return {"completion": "x", "model_used": "qwen2.5:14b",
                        "method": "internal", "cache_hit": False,
                        "tokens": {"prompt_chars": 1, "completion_chars": 1},
                        "latency_ms": 5}

        class _FakeClient:
            def __init__(self, **_kw): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *_a): return False
            async def post(self, url, json=None):
                captured["body"] = json
                return _FakeResponse()

        client = runner._LLMGatewayClient(
            base_url="http://x:8095", task="trace_distillation", timeout=10.0
        )
        with mock_patch("httpx.AsyncClient", _FakeClient):
            await client.complete(tenant_id="11111111-1111-1111-1111-111111111111",
                                  prompt="x", max_tokens=100)
        # K-20 — when no model pin, body must NOT include pinned_* keys.
        # llm-gateway's contract: either both pinned_model + pinned_version,
        # or neither.
        assert "pinned_model" not in captured["body"]
        assert "pinned_version" not in captured["body"]
