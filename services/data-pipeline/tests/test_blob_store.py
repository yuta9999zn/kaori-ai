"""ADR-0037 Phase 0 — blob store (raw file bytes)."""
from __future__ import annotations

import pytest

from data_pipeline.shared.blob_store import (
    LocalBlobStore, blob_key, get_blob_store,
)


def test_blob_key_is_content_addressed():
    k = blob_key("ent-1", "abc123")
    assert k == "ent-1/abc123"


@pytest.mark.asyncio
async def test_local_roundtrip(tmp_path):
    store = LocalBlobStore(root=str(tmp_path))
    key = blob_key("ent-1", "deadbeef")
    assert not await store.exists(key)
    uri = await store.put(key, b"hello bytes", content_type="text/plain")
    assert uri.startswith("file://")
    assert await store.exists(key)
    assert await store.get(key) == b"hello bytes"


@pytest.mark.asyncio
async def test_local_get_missing_returns_none(tmp_path):
    store = LocalBlobStore(root=str(tmp_path))
    assert await store.get(blob_key("ent-1", "nope")) is None


@pytest.mark.asyncio
async def test_local_put_is_idempotent(tmp_path):
    store = LocalBlobStore(root=str(tmp_path))
    key = blob_key("ent-2", "feed")
    await store.put(key, b"v1")
    # same key (content-addressed) — second put keeps the same bytes, no error.
    await store.put(key, b"v1")
    assert await store.get(key) == b"v1"


@pytest.mark.asyncio
async def test_key_traversal_guarded(tmp_path):
    store = LocalBlobStore(root=str(tmp_path))
    with pytest.raises(ValueError):
        await store.put("../../etc/passwd", b"x")


def test_get_blob_store_defaults_local(monkeypatch):
    monkeypatch.delenv("BLOB_STORE_BACKEND", raising=False)
    # reset the module singleton
    import data_pipeline.shared.blob_store as bs
    bs._store = None
    assert isinstance(get_blob_store(), LocalBlobStore)
    bs._store = None
