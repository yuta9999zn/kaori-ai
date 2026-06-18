"""
P2-S22 tests — LLM ops endpoints (P1-LLM-001/002/003/006) + NOV-CST-011
opportunity cost modeling.

8-section template:
  1. Mig 075 shape — 4 tables + CHECK constraints + seed providers
  2. Opportunity cost pure compute (5 cases)
  3. /catalog/providers — global list + filter
  4. /api-keys CRUD with encryption (dogfoods shared/crypto)
  5. /tokens/breakdown — rollup query
  6. /versions/upgrade-test — start + promote + reject flow
  7. Tenant isolation (X-Enterprise-ID required on all endpoints)
  8. Performance (catalog list < 50ms + opp_cost 1000× < 100ms)
"""
from __future__ import annotations

import base64
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.org_intel.economics import (
    OpportunityCost,
    estimate_opportunity_cost,
)


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER}
ENT_HEADERS = {"X-Enterprise-ID": ENTERPRISE}

REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"
NOW = datetime(2026, 5, 17, 12, 0, tzinfo=timezone.utc)


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    return conn


def _tenant_ctx(conn):
    @asynccontextmanager
    async def _fake(_enterprise_id):
        yield conn
    return _fake


def _row(**kw):
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kw[k]
    r.keys = MagicMock(return_value=list(kw.keys()))
    return r


def _make_app():
    from ai_orchestrator.routers import llm_ops
    app = FastAPI()
    app.include_router(llm_ops.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 075 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig075Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        return (MIG_DIR / "075_llm_ops.sql").read_text(encoding="utf-8")

    def test_4_tables_present(self, mig_text: str):
        for t in ("llm_providers", "tenant_llm_api_keys",
                  "llm_token_usage_daily", "llm_upgrade_tests"):
            assert f"CREATE TABLE IF NOT EXISTS {t}" in mig_text

    def test_provider_key_enum_limited(self, mig_text: str):
        assert "chk_llm_provider_key" in mig_text
        for p in ("qwen_local", "anthropic", "openai", "google",
                  "cohere", "mistral"):
            assert f"'{p}'" in mig_text

    def test_seeds_3_providers(self, mig_text: str):
        # Single multi-VALUES INSERT for the 3 default providers
        assert "INSERT INTO llm_providers" in mig_text
        for p in ("qwen_local", "anthropic", "openai"):
            assert f"'{p}'" in mig_text

    def test_tenant_provider_unique(self, mig_text: str):
        assert "uq_tenant_provider" in mig_text

    def test_token_usage_nonneg_check(self, mig_text: str):
        assert "chk_llm_tokens_nonneg" in mig_text

    def test_upgrade_test_status_enum(self, mig_text: str):
        for s in ("RUNNING", "PROMOTED", "REJECTED", "CANCELLED"):
            assert f"'{s}'" in mig_text

    def test_partial_indexes(self, mig_text: str):
        assert "idx_llm_providers_active" in mig_text
        assert "idx_llm_upgrade_tests_running" in mig_text


# ═════════════════════════════════════════════════════════════════════
# 2. Opportunity cost pure compute
# ═════════════════════════════════════════════════════════════════════


class TestOpportunityCost:

    def test_chosen_costlier_returns_positive_opp_cost(self):
        # Chosen: cost 100M, value 110M → net 10M
        # Alt   : cost 80M,  value 130M → net 50M
        # opp cost = alt_net - chosen_net = 40M (chose lost 40M in value)
        result = estimate_opportunity_cost(
            chosen_total_cost_vnd=Decimal("100000000"),
            chosen_realized_value_vnd=Decimal("110000000"),
            alt_total_cost_vnd=Decimal("80000000"),
            alt_projected_value_vnd=Decimal("130000000"),
            confidence=Decimal("0.8"),
            method="historical_baseline",
        )
        assert result.opportunity_cost_vnd == Decimal("40000000.0000")
        assert result.confidence == Decimal("0.8")
        assert result.method == "historical_baseline"

    def test_chosen_better_returns_negative_opp_cost(self):
        # Chosen better than alt → negative opp cost
        result = estimate_opportunity_cost(
            chosen_total_cost_vnd=Decimal("50000000"),
            chosen_realized_value_vnd=Decimal("150000000"),
            alt_total_cost_vnd=Decimal("100000000"),
            alt_projected_value_vnd=Decimal("120000000"),
        )
        # chosen_net=100M, alt_net=20M → opp = -80M (chosen was good call)
        assert result.opportunity_cost_vnd == Decimal("-80000000.0000")

    def test_zero_opp_cost_when_equal_net(self):
        result = estimate_opportunity_cost(
            chosen_total_cost_vnd=Decimal("100"),
            chosen_realized_value_vnd=Decimal("200"),
            alt_total_cost_vnd=Decimal("100"),
            alt_projected_value_vnd=Decimal("200"),
        )
        assert result.opportunity_cost_vnd == Decimal("0.0000")

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValueError):
            estimate_opportunity_cost(
                chosen_total_cost_vnd=Decimal("1"),
                chosen_realized_value_vnd=Decimal("2"),
                alt_total_cost_vnd=Decimal("1"),
                alt_projected_value_vnd=Decimal("2"),
                confidence=Decimal("1.5"),
            )

    def test_invalid_method_raises(self):
        with pytest.raises(ValueError):
            estimate_opportunity_cost(
                chosen_total_cost_vnd=Decimal("1"),
                chosen_realized_value_vnd=Decimal("2"),
                alt_total_cost_vnd=Decimal("1"),
                alt_projected_value_vnd=Decimal("2"),
                method="crystal_ball",
            )

    def test_all_outputs_quantize_to_4_decimals(self):
        result = estimate_opportunity_cost(
            chosen_total_cost_vnd=Decimal("100.12345"),
            chosen_realized_value_vnd=Decimal("200.67890"),
            alt_total_cost_vnd=Decimal("80.11111"),
            alt_projected_value_vnd=Decimal("250.99999"),
        )
        for d in (result.chosen_total_cost_vnd, result.alt_total_cost_vnd,
                  result.opportunity_cost_vnd):
            # 4 decimal places preserved
            assert d.as_tuple().exponent == -4


# ═════════════════════════════════════════════════════════════════════
# 3. /catalog/providers
# ═════════════════════════════════════════════════════════════════════


class TestProviderCatalog:

    def test_list_providers_smoke(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetch.return_value = [
            _row(provider_id=uuid4(), provider_key="qwen_local",
                  display_name="Qwen 2.5 14B", requires_api_key=False,
                  supports_streaming=True, is_external=False,
                  default_models=["qwen2.5:14b"],
                  cost_per_1k_input=Decimal("0"),
                  cost_per_1k_output=Decimal("0")),
        ]
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/platform/llm/catalog/providers", headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert len(body) == 1
        assert body[0]["provider_key"] == "qwen_local"
        assert body[0]["is_external"] is False

    def test_include_inactive_flag(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            client.get("/platform/llm/catalog/providers?include_inactive=true",
                       headers=ENT_HEADERS)
        called_sql = conn.fetch.await_args.args[0]
        assert "is_active" not in called_sql or "TRUE" not in called_sql


# ═════════════════════════════════════════════════════════════════════
# 4. /api-keys CRUD (with encryption dogfood)
# ═════════════════════════════════════════════════════════════════════


class TestApiKeysCRUD:

    def test_add_key_missing_field_key_returns_400(self):
        """Adding a tenant API key requires the tenant to already have
        a field-encryption key provisioned (mig 074 P2-S25)."""
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        # 1st fetchrow: provider lookup → found
        # 2nd fetchrow: tenant_field_keys lookup → None
        conn.fetchrow.side_effect = [
            _row(provider_id=uuid4(), requires_api_key=True),
            None,
        ]
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/platform/llm/api-keys/anthropic/new",
                            json={"api_key": "sk-test-1234567890"},
                            headers=ENT_HEADERS)
        assert r.status_code == 400
        assert "field-encryption key" in r.json()["detail"]

    def test_add_key_provider_not_found(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/platform/llm/api-keys/bogus_provider/new",
                            json={"api_key": "sk-1234567890"},
                            headers=ENT_HEADERS)
        assert r.status_code == 404

    def test_add_key_for_provider_not_requiring_key_returns_400(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetchrow.return_value = _row(
            provider_id=uuid4(), requires_api_key=False,
        )
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/platform/llm/api-keys/qwen_local/new",
                            json={"api_key": "irrelevant"},
                            headers=ENT_HEADERS)
        assert r.status_code == 400
        assert "does not require an API key" in r.json()["detail"]

    def test_list_keys_smoke(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetch.return_value = [
            _row(key_id=uuid4(), label="anthropic-prod",
                  enabled=True, last_used_at=None,
                  created_at=NOW, rotated_at=None,
                  provider_key="anthropic"),
        ]
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/platform/llm/api-keys", headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body[0]["provider_key"] == "anthropic"
        # Crucially: api_key plaintext NEVER returned via list
        assert "api_key" not in body[0]
        assert "api_key_enc" not in body[0]

    def test_delete_key_smoke(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.delete("/platform/llm/api-keys/openai",
                              headers=ENT_HEADERS)
        assert r.status_code == 204


# ═════════════════════════════════════════════════════════════════════
# 5. /tokens/breakdown
# ═════════════════════════════════════════════════════════════════════


class TestTokenBreakdown:

    def test_breakdown_smoke(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetch.return_value = [
            _row(period_day=date(2026, 5, 16),
                  input_tokens=1000, output_tokens=200,
                  cost_usd=Decimal("0.5"), cost_vnd=Decimal("12500"),
                  call_count=5, cache_hit_count=2, error_count=0,
                  provider_key="anthropic"),
        ]
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/platform/llm/tokens/breakdown?days=7",
                           headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body[0]["call_count"] == 5
        assert body[0]["cost_vnd"] == "12500"

    def test_provider_filter_in_sql(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            client.get("/platform/llm/tokens/breakdown?days=30&provider=anthropic",
                       headers=ENT_HEADERS)
        called_sql = conn.fetch.await_args.args[0]
        assert "p.provider_key =" in called_sql


# ═════════════════════════════════════════════════════════════════════
# 6. /versions/upgrade-test
# ═════════════════════════════════════════════════════════════════════


class TestUpgradeTests:

    def _provider_row(self):
        return _row(provider_id=uuid4())

    def _full_test_row(self, **kw):
        defaults = dict(
            test_id=uuid4(), provider_id=uuid4(),
            current_model="claude-sonnet-4-6", current_version="2026-01-01",
            candidate_model="claude-opus-4-7", candidate_version="2026-04-15",
            started_at=NOW, ends_at=NOW + timedelta(days=90),
            status="RUNNING", shadow_call_count=0,
            agreement_rate=None, avg_cost_delta_usd=None,
            notes=None, provider_key="anthropic",
        )
        defaults.update(kw)
        return _row(**defaults)

    def test_start_test_happy(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetchrow.side_effect = [
            self._provider_row(),    # provider lookup
            self._full_test_row(),   # INSERT RETURNING
        ]
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post(
                "/platform/llm/versions/upgrade-test",
                json={
                    "provider_key": "anthropic",
                    "current_model": "claude-sonnet-4-6",
                    "current_version": "2026-01-01",
                    "candidate_model": "claude-opus-4-7",
                    "candidate_version": "2026-04-15",
                    "test_days": 90,
                },
                headers=ENT_HEADERS,
            )
        assert r.status_code == 201, r.text
        assert r.json()["status"] == "RUNNING"
        assert r.json()["candidate_model"] == "claude-opus-4-7"

    def test_test_days_range_enforced(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post(
                "/platform/llm/versions/upgrade-test",
                json={
                    "provider_key": "anthropic",
                    "current_model": "x", "current_version": "v1",
                    "candidate_model": "y", "candidate_version": "v2",
                    "test_days": 5,    # below min 7
                },
                headers=ENT_HEADERS,
            )
        assert r.status_code == 422

    def test_promote_404_when_not_running(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post(
                f"/platform/llm/versions/upgrade-test/{uuid4()}/promote",
                headers=HEADERS,
            )
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# 7. Tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestTenantIsolation:

    def test_catalog_requires_enterprise_header(self):
        client = TestClient(_make_app())
        r = client.get("/platform/llm/catalog/providers")
        assert r.status_code == 422

    def test_api_keys_requires_enterprise_header(self):
        client = TestClient(_make_app())
        r = client.get("/platform/llm/api-keys")
        assert r.status_code == 422

    def test_promote_requires_user_header(self):
        client = TestClient(_make_app())
        r = client.post(f"/platform/llm/versions/upgrade-test/{uuid4()}/promote",
                        headers={"X-Enterprise-ID": ENTERPRISE})
        assert r.status_code == 422


# ═════════════════════════════════════════════════════════════════════
# 8. Performance
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_opportunity_cost_1000_under_100ms(self):
        t0 = time.perf_counter()
        for _ in range(1000):
            estimate_opportunity_cost(
                chosen_total_cost_vnd=Decimal("100000000"),
                chosen_realized_value_vnd=Decimal("150000000"),
                alt_total_cost_vnd=Decimal("80000000"),
                alt_projected_value_vnd=Decimal("160000000"),
            )
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.1, f"opp_cost too slow: {elapsed:.3f}s"

    def test_catalog_list_under_50ms(self):
        from ai_orchestrator.routers import llm_ops

        conn = _make_conn()
        conn.fetch.return_value = [
            _row(provider_id=uuid4(), provider_key=f"p{i}",
                  display_name=f"P{i}", requires_api_key=True,
                  supports_streaming=False, is_external=True,
                  default_models=[], cost_per_1k_input=Decimal("0"),
                  cost_per_1k_output=Decimal("0"))
            for i in range(20)
        ]
        with patch.object(llm_ops, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            t0 = time.perf_counter()
            for _ in range(10):
                r = client.get("/platform/llm/catalog/providers",
                               headers=ENT_HEADERS)
                assert r.status_code == 200
            avg = (time.perf_counter() - t0) / 10
        assert avg < 0.05, f"catalog too slow: {avg:.3f}s"
