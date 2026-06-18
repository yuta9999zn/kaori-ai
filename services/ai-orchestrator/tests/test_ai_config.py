"""CR-0019 — platform AI config service + admin endpoints."""
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

import ai_orchestrator.routers.llm_ops as ops
import ai_orchestrator.shared.ai_config as cfg


def _prime(d: dict):
    cfg._cache = dict(d)
    cfg._cache_at = time.monotonic()   # fresh → _load returns cache, no DB


# ─── ai_config service (cache + fallback) ─────────────────────────────
class TestAiConfigService:
    @pytest.mark.asyncio
    async def test_get_float_from_cache(self):
        _prime({"grounding_tolerance": "0.05"})
        assert await cfg.get_float("grounding_tolerance", 0.02) == 0.05

    @pytest.mark.asyncio
    async def test_missing_key_uses_default(self):
        _prime({})
        assert await cfg.get_float("nope", 0.02) == 0.02
        assert await cfg.get_int("nope", 5) == 5
        assert await cfg.get_str("nope", "bge-m3") == "bge-m3"

    @pytest.mark.asyncio
    async def test_get_int_and_str(self):
        _prime({"rag_max_citations": "8", "embedding_model": "qwen-emb"})
        assert await cfg.get_int("rag_max_citations", 5) == 8
        assert await cfg.get_str("embedding_model", "bge-m3") == "qwen-emb"

    @pytest.mark.asyncio
    async def test_bad_value_falls_back_to_default(self):
        _prime({"grounding_tolerance": "abc"})
        assert await cfg.get_float("grounding_tolerance", 0.02) == 0.02

    def test_invalidate_resets_cache_clock(self):
        _prime({"k": "v"})
        cfg.invalidate()
        assert cfg._cache_at == 0.0


# ─── validation (bounds come from the row, not hard-coded) ────────────
class TestValidateConfigValue:
    def test_int_must_be_integer(self):
        with pytest.raises(HTTPException):
            ops._validate_config_value("5.5", "int", 1, 50)

    def test_out_of_range_rejected(self):
        with pytest.raises(HTTPException):
            ops._validate_config_value("100", "int", 1, 50)
        with pytest.raises(HTTPException):
            ops._validate_config_value("-0.1", "float", 0, 1)

    def test_non_numeric_rejected(self):
        with pytest.raises(HTTPException):
            ops._validate_config_value("abc", "float", 0, 1)

    def test_valid_values_pass(self):
        ops._validate_config_value("8", "int", 1, 50)
        ops._validate_config_value("0.5", "float", 0, 1)
        ops._validate_config_value("bge-m3", "string", None, None)  # string passthrough


# ─── admin gate ───────────────────────────────────────────────────────
class TestRequireSuperAdmin:
    def test_blocks_non_admin(self):
        with pytest.raises(HTTPException) as e:
            ops._require_super_admin("MANAGER")
        assert e.value.status_code == 403

    def test_blocks_missing_role(self):
        with pytest.raises(HTTPException):
            ops._require_super_admin(None)

    def test_allows_super_admin(self):
        ops._require_super_admin("SUPER_ADMIN")
        ops._require_super_admin("admin")   # case-insensitive


# ─── endpoints (mock pool) ────────────────────────────────────────────
def _mock_pool(monkeypatch, *, fetch=None, fetchrow_seq=None):
    conn = AsyncMock()
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.fetchrow = AsyncMock(side_effect=list(fetchrow_seq or []))
    pool = MagicMock()

    @asynccontextmanager
    async def _acq():
        yield conn

    pool.acquire = _acq
    monkeypatch.setattr(ops, "get_pool", lambda: pool)
    return conn


class TestConfigEndpoints:
    @pytest.mark.asyncio
    async def test_list_requires_admin(self, monkeypatch):
        with pytest.raises(HTTPException) as e:
            await ops.list_ai_config(x_user_role="MANAGER")
        assert e.value.status_code == 403

    @pytest.mark.asyncio
    async def test_list_returns_rows_for_admin(self, monkeypatch):
        import datetime as dt
        row = {"config_key": "grounding_tolerance", "config_value": "0.02",
               "value_type": "float", "min_value": 0.0, "max_value": 1.0,
               "description": "x", "applied": True, "updated_at": dt.datetime.now()}
        _mock_pool(monkeypatch, fetch=[row])
        out = await ops.list_ai_config(x_user_role="SUPER_ADMIN")
        assert len(out) == 1 and out[0].config_key == "grounding_tolerance"

    @pytest.mark.asyncio
    async def test_update_out_of_range_returns_400(self, monkeypatch):
        _mock_pool(monkeypatch, fetchrow_seq=[
            {"value_type": "float", "min_value": 0.0, "max_value": 1.0}])
        with pytest.raises(HTTPException) as e:
            await ops.update_ai_config(
                body=ops.AIConfigUpdate(config_value="5"),
                config_key="grounding_tolerance",
                x_user_role="SUPER_ADMIN", x_user_id=None)
        assert e.value.status_code == 400

    @pytest.mark.asyncio
    async def test_update_unknown_key_returns_404(self, monkeypatch):
        _mock_pool(monkeypatch, fetchrow_seq=[None])
        with pytest.raises(HTTPException) as e:
            await ops.update_ai_config(
                body=ops.AIConfigUpdate(config_value="0.5"),
                config_key="nope",
                x_user_role="SUPER_ADMIN", x_user_id=None)
        assert e.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_happy_path_invalidates_cache(self, monkeypatch):
        import datetime as dt
        full = {"config_key": "grounding_tolerance", "config_value": "0.05",
                "value_type": "float", "min_value": 0.0, "max_value": 1.0,
                "description": "x", "applied": True, "updated_at": dt.datetime.now()}
        _mock_pool(monkeypatch, fetchrow_seq=[
            {"value_type": "float", "min_value": 0.0, "max_value": 1.0}, full])
        _prime({"grounding_tolerance": "0.02"})
        out = await ops.update_ai_config(
            body=ops.AIConfigUpdate(config_value="0.05"),
            config_key="grounding_tolerance",
            x_user_role="SUPER_ADMIN", x_user_id=None)
        assert out.config_value == "0.05"
        assert cfg._cache_at == 0.0   # cache invalidated
