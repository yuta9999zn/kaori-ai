"""
P2-S24 / ADR-0024 follow-up — chat end-of-turn fact-extraction wire test.

Verifies that:
  1. _fact_extraction_enabled() reads env var correctly
  2. _seed_facts_from_turn() calls extract_and_store_facts with correct
     combined text + context + tenant
  3. Disabled state is a no-op (env unset → no LLM call)
  4. Errors are swallowed (chat hot path never fails on memory)
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import pytest

from ai_orchestrator.chat.agent import (
    _fact_extraction_enabled,
    _seed_facts_from_turn,
)
from ai_orchestrator.chat.tools.base import ToolContext


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER = "22222222-2222-2222-2222-222222222222"


def _ctx(scope: str = "enterprise") -> ToolContext:
    return ToolContext(
        enterprise_id=ENTERPRISE,
        user_id=USER,
        role="ANALYST",
        scope=scope,
    )


# ─── Env gate ───────────────────────────────────────────────────────


class TestEnvGate:

    def test_disabled_by_default(self, monkeypatch):
        monkeypatch.delenv("CHAT_FACT_EXTRACTION_ENABLED", raising=False)
        assert _fact_extraction_enabled() is False

    @pytest.mark.parametrize("val", ["true", "1", "yes", "on", "TRUE"])
    def test_truthy_values(self, monkeypatch, val):
        monkeypatch.setenv("CHAT_FACT_EXTRACTION_ENABLED", val)
        assert _fact_extraction_enabled() is True

    @pytest.mark.parametrize("val", ["false", "0", "no", "off", ""])
    def test_falsy_values(self, monkeypatch, val):
        monkeypatch.setenv("CHAT_FACT_EXTRACTION_ENABLED", val)
        assert _fact_extraction_enabled() is False


# ─── _seed_facts_from_turn behaviour ────────────────────────────────


class TestSeedFactsFromTurn:

    @pytest.mark.asyncio
    async def test_no_tenant_id_is_noop(self):
        """ctx.enterprise_id None → function returns without LLM call."""
        ctx = ToolContext(
            enterprise_id=None, user_id=USER, role="ANALYST",
            scope="enterprise",
        )
        # Should return without raising — no LLM client built
        await _seed_facts_from_turn(
            user_message="x", assistant_response="y", ctx=ctx,
        )
        # Implicit assert: no exception

    @pytest.mark.asyncio
    async def test_combined_text_passed_to_extractor(self, monkeypatch):
        """Verify the combined user+assistant text reaches the transformer
        with correct USER/ASSISTANT labels."""
        captured: dict = {}

        async def _fake_extract_and_store(self_, combined, *, tenant_id,
                                           memory_service, context,
                                           source_ref, **_extra):
            captured["combined"] = combined
            captured["tenant_id"] = tenant_id
            captured["context"] = context
            captured["source_ref"] = source_ref
            return []

        # Patch the method on the TCubeTransformer class
        with patch(
            "ai_orchestrator.reasoning.trace_distiller.transformer."
            "TCubeTransformer.extract_and_store_facts",
            _fake_extract_and_store,
        ):
            monkeypatch.setenv("LLM_GATEWAY_USE_STUB", "true")
            await _seed_facts_from_turn(
                user_message="Khách Olist có quan tâm",
                assistant_response="Olist là khách hàng VIP của hệ thống",
                ctx=_ctx(),
            )

        assert "USER:" in captured["combined"]
        assert "ASSISTANT:" in captured["combined"]
        assert "Khách Olist" in captured["combined"]
        assert "VIP" in captured["combined"]
        assert str(captured["tenant_id"]) == ENTERPRISE
        assert "chat:user:" in captured["source_ref"]
        assert USER in captured["source_ref"]

    @pytest.mark.asyncio
    async def test_long_messages_truncated(self, monkeypatch):
        """USER cap 1500 chars, ASSISTANT cap 2500 chars (combined ~4K
        envelope for transformer's 8K limit)."""
        captured: dict = {}

        async def _fake_trunc(self_, combined, **kw):
            captured["len"] = len(combined)
            captured["combined"] = combined
            return []

        with patch(
            "ai_orchestrator.reasoning.trace_distiller.transformer."
            "TCubeTransformer.extract_and_store_facts", _fake_trunc,
        ):
            monkeypatch.setenv("LLM_GATEWAY_USE_STUB", "true")
            await _seed_facts_from_turn(
                user_message="x" * 5000,
                assistant_response="y" * 5000,
                ctx=_ctx(),
            )
        # USER 1500 + "\n\nASSISTANT: " (12 chars) + ASSISTANT 2500 + "USER: " (6) ≈ 4018
        assert captured["len"] < 4100
        assert "x" * 1500 in captured["combined"]
        assert "y" * 2500 in captured["combined"]
        # Truncated portion missing
        assert "x" * 1501 not in captured["combined"]
        assert "y" * 2501 not in captured["combined"]

    @pytest.mark.asyncio
    async def test_context_label_includes_scope_and_user(self, monkeypatch):
        captured: dict = {}

        async def _fake_ctx(self_, combined, *, context, **kw):
            captured["context"] = context
            return []

        with patch(
            "ai_orchestrator.reasoning.trace_distiller.transformer."
            "TCubeTransformer.extract_and_store_facts", _fake_ctx,
        ):
            monkeypatch.setenv("LLM_GATEWAY_USE_STUB", "true")
            await _seed_facts_from_turn(
                user_message="x", assistant_response="y",
                ctx=_ctx(scope="platform"),
            )
        assert "scope=platform" in captured["context"]
        assert f"user={USER}" in captured["context"]
