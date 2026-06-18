"""
Step 3b — RAG router env-gated registration of trace_recall engine.

When `RAG_TRACE_RECALL_ENABLED=true` env var is set, the singleton
RAGRouter built by routers/rag.py must include the trace_recall engine
(P2-S21 D2). Default (env unset / false) keeps the 3-engine bundle so
existing tests + production callers behave unchanged.
"""
from __future__ import annotations

import pytest

from ai_orchestrator.routers import rag as rag_router_mod


@pytest.fixture(autouse=True)
def _reset_singleton():
    """Force the lazily-built singleton to be rebuilt per test."""
    rag_router_mod._ROUTER_SINGLETON = None
    yield
    rag_router_mod._ROUTER_SINGLETON = None


class TestTraceRecallEnvGate:

    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("RAG_TRACE_RECALL_ENABLED", raising=False)
        router = rag_router_mod._get_router()
        # Default 3-engine bundle, trace_recall NOT registered
        assert set(router.engines.keys()) == {"pgvector", "pageindex", "docsage"}
        assert "trace_recall" not in router.engines

    @pytest.mark.parametrize("val", ["true", "1", "yes", "on", "TRUE"])
    def test_enabled_registers_trace_recall(self, monkeypatch, val):
        monkeypatch.setenv("RAG_TRACE_RECALL_ENABLED", val)
        router = rag_router_mod._get_router()
        assert "trace_recall" in router.engines

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", ""])
    def test_falsy_keeps_default_bundle(self, monkeypatch, val):
        monkeypatch.setenv("RAG_TRACE_RECALL_ENABLED", val)
        router = rag_router_mod._get_router()
        assert "trace_recall" not in router.engines
        assert {"pgvector", "pageindex", "docsage"}.issubset(router.engines.keys())

    def test_singleton_caches_across_calls(self, monkeypatch):
        monkeypatch.setenv("RAG_TRACE_RECALL_ENABLED", "true")
        r1 = rag_router_mod._get_router()
        r2 = rag_router_mod._get_router()
        assert r1 is r2
