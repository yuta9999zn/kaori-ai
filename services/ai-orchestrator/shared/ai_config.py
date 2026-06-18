"""Platform AI config (CR-0019 / FR-PLT-08) — read the platform_ai_config knobs
at runtime, cached, with a code-constant FALLBACK so a missing row or a DB blip
never breaks a reasoning path (fail-open to the shipped default).

Global table (no tenant) — read via the raw pool. SUPER_ADMIN edits go through
routers/llm_ops.py, which calls invalidate() so the next read is fresh.
"""
from __future__ import annotations

import time

import structlog

from .db import get_pool

log = structlog.get_logger()

_CACHE_TTL_S = 60.0
_cache: dict[str, str] = {}
_cache_at: float = 0.0


async def _load() -> dict[str, str]:
    """Return the {key: value} map, refreshing from DB at most every TTL.
    On any DB error keep the existing cache (fail-open) — callers then fall back
    to their code default for missing keys."""
    global _cache, _cache_at
    now = time.monotonic()
    if _cache_at and (now - _cache_at) < _CACHE_TTL_S:
        return _cache
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT config_key, config_value FROM platform_ai_config")
        _cache = {r["config_key"]: r["config_value"] for r in rows}
        _cache_at = now
    except Exception as e:  # noqa: BLE001 — fail-open to defaults
        log.warning("ai_config.load_failed", error=str(e))
    return _cache


async def get_float(key: str, default: float) -> float:
    raw = (await _load()).get(key)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


async def get_int(key: str, default: int) -> int:
    raw = (await _load()).get(key)
    if raw is None:
        return default
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return default


async def get_str(key: str, default: str) -> str:
    raw = (await _load()).get(key)
    return raw if raw is not None else default


def invalidate() -> None:
    """Drop the cache so the next read reloads from DB (called after an edit)."""
    global _cache_at
    _cache_at = 0.0
