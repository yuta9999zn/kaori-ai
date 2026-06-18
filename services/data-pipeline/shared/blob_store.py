"""Blob storage abstraction (ADR-0037 Phase 0) — persist raw file BYTES.

Bronze stored metadata + parsed rows but NOT the original bytes ("Phase 1.5+").
The Document Tree / Contract modules need the real file back (view / download /
sign), so this is the byte store, with two pluggable backends:

  • LocalBlobStore  (default) — writes under BLOB_STORE_PATH (a mounted volume),
    keyed by enterprise + SHA-256. Right for the pilot laptop; survives restarts.
  • S3BlobStore     (prod)    — any S3-compatible store (MinIO / AWS S3), gated by
    BLOB_STORE_BACKEND=s3 + S3_* env. boto3 imported lazily so the pilot needs no
    extra dependency.

Key scheme is deterministic from (enterprise_id, sha256) → content-addressed, so
identical content dedups (mirrors K-8) and the key can be reconstructed from the
pipeline_runs row without a schema change. Mirrored verbatim in ai-orchestrator
(cross-service mirror > import — separate images).
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import structlog

log = structlog.get_logger()

_DEFAULT_ROOT = os.getenv("BLOB_STORE_PATH", "/app/object-store")


def blob_key(enterprise_id: str, sha256: str) -> str:
    """Content-addressed key: <enterprise>/<sha256>. Deterministic so the same
    bytes never store twice and the key needs no DB column."""
    return f"{enterprise_id}/{sha256}"


class BlobStore(ABC):
    @abstractmethod
    async def put(self, key: str, content: bytes, *, content_type: Optional[str] = None) -> str:
        """Store bytes under key (idempotent — same key overwrites identically).
        Returns a URI/locator for logging."""

    @abstractmethod
    async def get(self, key: str) -> Optional[bytes]:
        """Return the bytes, or None if the key is absent."""

    @abstractmethod
    async def exists(self, key: str) -> bool:
        ...


class LocalBlobStore(BlobStore):
    """Filesystem-backed — BLOB_STORE_PATH/<enterprise>/<sha256>. The pilot
    mounts this as a Docker volume shared with ai-orchestrator (read side)."""

    def __init__(self, root: Optional[str] = None):
        self.root = Path(root or _DEFAULT_ROOT)

    def _path(self, key: str) -> Path:
        # key is already <enterprise>/<sha256> (no traversal — both are our own
        # UUID/hex). Resolve + guard anyway.
        p = (self.root / key).resolve()
        if not str(p).startswith(str(self.root.resolve())):
            raise ValueError("blob key escapes store root")
        return p

    async def put(self, key: str, content: bytes, *, content_type: Optional[str] = None) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Idempotent: identical content → identical file. Skip rewrite if present.
        if not p.exists():
            p.write_bytes(content)
        return f"file://{p}"

    async def get(self, key: str) -> Optional[bytes]:
        p = self._path(key)
        return p.read_bytes() if p.exists() else None

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3BlobStore(BlobStore):
    """S3-compatible (MinIO / AWS). boto3 imported lazily so the pilot path never
    requires it. Config via S3_ENDPOINT / S3_BUCKET / S3_ACCESS_KEY / S3_SECRET_KEY."""

    def __init__(self):
        self.bucket = os.getenv("S3_BUCKET", "kaori-blobs")
        self.endpoint = os.getenv("S3_ENDPOINT")  # e.g. http://minio:9000
        self._client = None

    def _c(self):
        if self._client is None:
            import boto3  # lazy — only when S3 backend is selected
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
                aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
                region_name=os.getenv("S3_REGION", "us-east-1"),
            )
        return self._client

    async def put(self, key: str, content: bytes, *, content_type: Optional[str] = None) -> str:
        extra = {"ContentType": content_type} if content_type else {}
        self._c().put_object(Bucket=self.bucket, Key=key, Body=content, **extra)
        return f"s3://{self.bucket}/{key}"

    async def get(self, key: str) -> Optional[bytes]:
        try:
            resp = self._c().get_object(Bucket=self.bucket, Key=key)
            return resp["Body"].read()
        except Exception:  # noqa: BLE001 — missing key / transient → None
            return None

    async def exists(self, key: str) -> bool:
        try:
            self._c().head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:  # noqa: BLE001
            return False


_store: Optional[BlobStore] = None


def get_blob_store() -> BlobStore:
    """Singleton, backend chosen by BLOB_STORE_BACKEND (local|s3, default local)."""
    global _store
    if _store is None:
        backend = os.getenv("BLOB_STORE_BACKEND", "local").lower()
        _store = S3BlobStore() if backend == "s3" else LocalBlobStore()
        log.info("blob_store.init", backend=backend)
    return _store
