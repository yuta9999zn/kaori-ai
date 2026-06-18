"""CR-0019 — memory promote/forget read their thresholds from platform config
(falling back to the module constants), and explicit args bypass the read."""
from uuid import uuid4

import pytest

import ai_orchestrator.shared.ai_config as cfg
from ai_orchestrator.reasoning.memory.service import (
    FORGET_AGE_DAYS, FORGET_THRESHOLD, PROMOTION_THRESHOLD, MemoryService,
)


@pytest.mark.asyncio
async def test_promote_resolves_config_threshold(monkeypatch):
    seen = {}
    async def fake_float(key, default):
        seen[key] = default
        return 0.95
    monkeypatch.setattr(cfg, "get_float", fake_float)

    await MemoryService().promote(uuid4())   # no explicit threshold
    assert seen.get("memory_promotion_threshold") == PROMOTION_THRESHOLD  # const = fallback


@pytest.mark.asyncio
async def test_promote_explicit_threshold_skips_config(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("explicit threshold must NOT read config")
    monkeypatch.setattr(cfg, "get_float", boom)

    moved = await MemoryService().promote(uuid4(), importance_threshold=0.5)
    assert moved == 0   # empty store, and no config read happened


@pytest.mark.asyncio
async def test_forget_ttl_resolves_config(monkeypatch):
    seen = {}
    async def fake_float(key, default):
        seen[key] = default
        return 0.3
    async def fake_int(key, default):
        seen[key] = default
        return 90
    monkeypatch.setattr(cfg, "get_float", fake_float)
    monkeypatch.setattr(cfg, "get_int", fake_int)

    await MemoryService().forget(uuid4())   # TTL sweep, no explicit args
    assert seen.get("memory_forget_threshold") == FORGET_THRESHOLD
    assert seen.get("memory_forget_age_days") == FORGET_AGE_DAYS


@pytest.mark.asyncio
async def test_forget_full_wipe_skips_ttl_config(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("full wipe must NOT read TTL config")
    monkeypatch.setattr(cfg, "get_float", boom)
    monkeypatch.setattr(cfg, "get_int", boom)

    await MemoryService().forget(uuid4(), full_tenant_wipe=True)   # no config read
