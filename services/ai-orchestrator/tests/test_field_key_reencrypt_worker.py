"""
P2 retro item 6 — background re-encrypt worker for field-key rotation.

8-section template (per established Phase 2 methodology):
  1. Mig 076 shape         — tenant_field_key_versions + reencrypt_* cols
  2. Crypto helpers         — WrappedKey.version semantics + decrypt history
  3. Worker registry        — EncryptedColumn + ColumnReport shapes
  4. Key history loader     — multi-version + backfill fallback
  5. Worker logic           — per-column reencrypt + status state machine
  6. Endpoint smoke         — rotate-with-history + trigger + status
  7. Integration            — full rotate→reencrypt→re-rotate chain
  8. Performance + tenant   — N rows benchmark + cross-tenant isolation
"""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.shared.crypto import (
    CryptoError,
    WrappedKey,
    decrypt_field,
    decrypt_field_with_history,
    encrypt_field,
    generate_key_b64,
    resolve_tenant_key,
)
from ai_orchestrator.shared.field_key_rotation import (
    COLUMNS,
    ColumnReport,
    EncryptedColumn,
    ReencryptReport,
    load_key_history,
    reencrypt_tenant,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"

ENT = UUID("11111111-1111-1111-1111-111111111111")
ENT_OTHER = UUID("22222222-2222-2222-2222-222222222222")
ENT_HEADERS = {"X-Enterprise-ID": str(ENT)}


# ─── Test fixtures ───────────────────────────────────────────────────


def _key(version: int = 1) -> WrappedKey:
    return WrappedKey(key_bytes=os.urandom(32), version=version)


class _FakeConn:
    """In-memory stand-in for asyncpg connection.

    Supports the SQL shapes used by the worker + endpoints. Each table
    is a list of dicts; queries are pattern-matched on the leading
    keyword of the SQL string.

    Tables modelled:
      tenant_field_keys           (enterprise_id, version, key_ref,
                                    rotated_at, created_at,
                                    reencrypt_status,
                                    reencrypt_started_at,
                                    reencrypt_completed_at,
                                    reencrypt_error)
      tenant_field_key_versions   (enterprise_id, version, key_ref,
                                    created_at, superseded_at, purged_at)
      tenant_llm_api_keys         (key_id, enterprise_id, api_key_enc)
    """

    def __init__(self):
        self.tfk: list[dict] = []
        self.tfkv: list[dict] = []
        self.llm: list[dict] = []

    @asynccontextmanager
    async def transaction(self):
        yield self

    # Helpers
    def _tfk_row(self, enterprise_id):
        for r in self.tfk:
            if r["enterprise_id"] == enterprise_id:
                return r
        return None

    async def fetchrow(self, sql, *args):
        s = " ".join(sql.split())

        if s.startswith("SELECT version, key_ref FROM tenant_field_keys"):
            r = self._tfk_row(args[0])
            return _row(version=r["version"], key_ref=r["key_ref"]) if r else None

        if s.startswith("SELECT key_ref, version FROM tenant_field_keys"):
            r = self._tfk_row(args[0])
            return _row(key_ref=r["key_ref"], version=r["version"]) if r else None

        if s.startswith("SELECT version, reencrypt_status, reencrypt_started_at"):
            r = self._tfk_row(args[0])
            if r is None:
                return None
            return _row(
                version=r["version"],
                reencrypt_status=r["reencrypt_status"],
                reencrypt_started_at=r.get("reencrypt_started_at"),
                reencrypt_completed_at=r.get("reencrypt_completed_at"),
                reencrypt_error=r.get("reencrypt_error"),
            )

        if s.startswith("INSERT INTO tenant_field_keys"):
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            self.tfk.append({
                "enterprise_id": args[0],
                "key_ref": args[1],
                "version": 1,
                "rotated_at": None,
                "created_at": now,
                "reencrypt_status": "idle",
                "reencrypt_started_at": None,
                "reencrypt_completed_at": None,
                "reencrypt_error": None,
            })
            return _row(version=1, rotated_at=None, created_at=now)

        if s.startswith("UPDATE tenant_field_keys SET key_ref"):
            # rotate bump
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            r = self._tfk_row(args[0])
            assert r is not None
            r["key_ref"] = args[1]
            r["version"] = args[2]
            r["rotated_at"] = now
            r["reencrypt_status"] = "pending"
            r["reencrypt_error"] = None
            return _row(version=r["version"], rotated_at=now, created_at=r["created_at"])

        raise AssertionError(f"unhandled fetchrow: {s[:120]}")

    async def fetch(self, sql, *args):
        s = " ".join(sql.split())

        if s.startswith("SELECT version, key_ref FROM tenant_field_key_versions"):
            rows = [r for r in self.tfkv
                    if r["enterprise_id"] == args[0] and r.get("purged_at") is None]
            rows.sort(key=lambda x: -x["version"])
            return [_row(version=r["version"], key_ref=r["key_ref"]) for r in rows]

        if "FROM tenant_llm_api_keys" in s:
            rows = [r for r in self.llm if r["enterprise_id"] == args[0]]
            return [_row(key_id=r["key_id"], api_key_enc=r["api_key_enc"]) for r in rows]

        raise AssertionError(f"unhandled fetch: {s[:120]}")

    async def execute(self, sql, *args):
        s = " ".join(sql.split())

        if s.startswith("INSERT INTO tenant_field_key_versions"):
            for r in self.tfkv:
                if r["enterprise_id"] == args[0] and r["version"] == args[1]:
                    return "INSERT 0 0"
            from datetime import datetime, timezone
            self.tfkv.append({
                "enterprise_id": args[0],
                "version":       args[1],
                "key_ref":       args[2],
                "created_at":    datetime.now(timezone.utc),
                "superseded_at": None,
                "purged_at":     None,
            })
            return "INSERT 0 1"

        if s.startswith("UPDATE tenant_field_key_versions SET superseded_at"):
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc)
            for r in self.tfkv:
                if (r["enterprise_id"] == args[0] and r["version"] == args[1]
                        and r["superseded_at"] is None):
                    r["superseded_at"] = now
            return "UPDATE 1"

        if s.startswith("UPDATE tenant_field_key_versions SET purged_at"):
            # signature: tenant, version_list, now
            tenant, versions, now = args
            for r in self.tfkv:
                if (r["enterprise_id"] == tenant and r["version"] in versions
                        and r.get("purged_at") is None):
                    r["purged_at"] = now
            return "UPDATE N"

        if s.startswith("UPDATE tenant_field_keys SET reencrypt_status = 'running'"):
            r = self._tfk_row(args[0])
            r["reencrypt_status"] = "running"
            r["reencrypt_started_at"] = args[1]
            r["reencrypt_error"] = None
            return "UPDATE 1"

        if s.startswith("UPDATE tenant_field_keys SET reencrypt_status = 'completed'"):
            r = self._tfk_row(args[0])
            r["reencrypt_status"] = "completed"
            r["reencrypt_completed_at"] = args[1]
            r["reencrypt_error"] = None
            return "UPDATE 1"

        if s.startswith("UPDATE tenant_field_keys SET reencrypt_status = 'failed'"):
            r = self._tfk_row(args[0])
            r["reencrypt_status"] = "failed"
            r["reencrypt_completed_at"] = args[1]
            r["reencrypt_error"] = args[2]
            return "UPDATE 1"

        if "UPDATE tenant_llm_api_keys" in s:
            new_ct, pk, ent = args
            for r in self.llm:
                if r["key_id"] == pk and r["enterprise_id"] == ent:
                    r["api_key_enc"] = new_ct
                    return "UPDATE 1"
            return "UPDATE 0"

        raise AssertionError(f"unhandled execute: {s[:120]}")

    async def fetchval(self, sql, *args):
        s = " ".join(sql.split())
        if s.startswith("SELECT COUNT(*) FROM tenant_field_key_versions"):
            return sum(1 for r in self.tfkv
                       if r["enterprise_id"] == args[0] and r.get("purged_at") is None)
        raise AssertionError(f"unhandled fetchval: {s[:120]}")


def _row(**kw):
    r = MagicMock()
    r.__getitem__ = lambda _self, k: kw[k]
    r.get = lambda k, default=None: kw.get(k, default)
    r.keys = MagicMock(return_value=list(kw.keys()))
    return r


def _make_app(conn: _FakeConn):
    from ai_orchestrator.routers import auth_security

    @asynccontextmanager
    async def fake_acquire(_eid):
        yield conn

    auth_security.acquire_for_tenant = fake_acquire
    app = FastAPI()
    app.include_router(auth_security.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 076 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig080Shape:

    @pytest.fixture(scope="class")
    def mig(self) -> str:
        return (MIG_DIR / "080_field_key_history.sql").read_text(encoding="utf-8")

    def test_history_table_exists(self, mig):
        assert "CREATE TABLE IF NOT EXISTS tenant_field_key_versions" in mig

    def test_primary_key_is_enterprise_plus_version(self, mig):
        assert "PRIMARY KEY (enterprise_id, version)" in mig

    def test_version_positive_check(self, mig):
        assert "chk_tfkv_version_pos" in mig
        assert "version > 0" in mig

    def test_purge_requires_supersede(self, mig):
        assert "chk_tfkv_purge_after_supersede" in mig

    def test_active_keys_partial_index(self, mig):
        assert "idx_tfkv_active" in mig
        assert "WHERE purged_at IS NULL" in mig

    def test_reencrypt_status_column_added(self, mig):
        for col in (
            "reencrypt_status",
            "reencrypt_started_at",
            "reencrypt_completed_at",
            "reencrypt_error",
        ):
            assert col in mig

    def test_reencrypt_status_check_constraint(self, mig):
        assert "chk_tfk_reencrypt_status" in mig
        for state in ("idle", "pending", "running", "completed", "failed"):
            assert f"'{state}'" in mig

    def test_backfill_idempotent(self, mig):
        assert "INSERT INTO tenant_field_key_versions" in mig
        assert "ON CONFLICT (enterprise_id, version) DO NOTHING" in mig


# ═════════════════════════════════════════════════════════════════════
# 2. Crypto helpers — WrappedKey.version semantics + decrypt history
# ═════════════════════════════════════════════════════════════════════


class TestWrappedKeyVersion:

    def test_version_must_be_positive(self):
        with pytest.raises(ValueError):
            WrappedKey(key_bytes=os.urandom(32), version=0)

    def test_version_carried_through_resolve(self):
        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref=f"inline:{generate_key_b64()}",
            version=7,
        )
        assert wk.version == 7

    def test_encrypt_works_with_any_tenant_version(self):
        wk = WrappedKey(key_bytes=os.urandom(32), version=99)
        ct = encrypt_field("hello", wk)
        assert decrypt_field(ct, wk) == "hello"


class TestDecryptWithHistory:

    def test_current_key_wins_when_first(self):
        cur = _key(2)
        old = _key(1)
        ct = encrypt_field("payload", cur)
        pt, v = decrypt_field_with_history(ct, [cur, old])
        assert pt == "payload"
        assert v == 2

    def test_falls_back_to_older(self):
        cur = _key(2)
        old = _key(1)
        ct = encrypt_field("legacy", old)
        pt, v = decrypt_field_with_history(ct, [cur, old])
        assert pt == "legacy"
        assert v == 1

    def test_walks_full_chain(self):
        keys = [_key(3), _key(2), _key(1)]
        ct = encrypt_field("ancient", keys[2])
        pt, v = decrypt_field_with_history(ct, keys)
        assert pt == "ancient"
        assert v == 1

    def test_empty_short_circuits(self):
        pt, v = decrypt_field_with_history("", [_key(1)])
        assert pt == ""
        assert v == -1

    def test_no_keys_raises(self):
        with pytest.raises(CryptoError):
            decrypt_field_with_history("nonempty-b64-payload", [])

    def test_undecryptable_raises(self):
        keys = [_key(2), _key(1)]
        # Encrypt with a key NOT in the candidates list.
        rogue = _key(1)
        ct = encrypt_field("orphan", rogue)
        with pytest.raises(CryptoError):
            decrypt_field_with_history(ct, keys)


# ═════════════════════════════════════════════════════════════════════
# 3. Worker registry + report shapes
# ═════════════════════════════════════════════════════════════════════


class TestRegistry:

    def test_default_registry_includes_llm_api_keys(self):
        names = [c.encrypted_column for c in COLUMNS]
        assert "api_key_enc" in names

    def test_encrypted_column_defaults_enterprise_col(self):
        c = EncryptedColumn(
            table="foo", primary_key="id", encrypted_column="bar",
        )
        assert c.enterprise_column == "enterprise_id"

    def test_column_report_starts_zero(self):
        r = ColumnReport(column="x")
        assert r.rows_scanned == 0
        assert r.rows_reencrypted == 0
        assert r.failed_pks == []

    def test_reencrypt_report_aggregates(self):
        rep = ReencryptReport(
            enterprise_id=ENT,
            started_at=__import__("datetime").datetime.now(),
        )
        rep.columns = [
            ColumnReport(column="a", rows_reencrypted=3, rows_failed=1),
            ColumnReport(column="b", rows_reencrypted=5, rows_failed=0),
        ]
        assert rep.total_reencrypted == 8
        assert rep.total_failed == 1


# ═════════════════════════════════════════════════════════════════════
# 4. Key history loader
# ═════════════════════════════════════════════════════════════════════


class TestLoadKeyHistory:

    @pytest.mark.asyncio
    async def test_multi_version_descending(self):
        conn = _FakeConn()
        k1, k2, k3 = generate_key_b64(), generate_key_b64(), generate_key_b64()
        conn.tfkv = [
            {"enterprise_id": ENT, "version": 1, "key_ref": f"inline:{k1}",
             "created_at": None, "superseded_at": None, "purged_at": None},
            {"enterprise_id": ENT, "version": 2, "key_ref": f"inline:{k2}",
             "created_at": None, "superseded_at": None, "purged_at": None},
            {"enterprise_id": ENT, "version": 3, "key_ref": f"inline:{k3}",
             "created_at": None, "superseded_at": None, "purged_at": None},
        ]
        current, history = await load_key_history(conn, ENT)
        assert current.version == 3
        assert [k.version for k in history] == [3, 2, 1]

    @pytest.mark.asyncio
    async def test_skips_purged(self):
        conn = _FakeConn()
        kv1, kv2 = generate_key_b64(), generate_key_b64()
        conn.tfkv = [
            {"enterprise_id": ENT, "version": 1, "key_ref": f"inline:{kv1}",
             "created_at": None, "superseded_at": None, "purged_at": "x"},
            {"enterprise_id": ENT, "version": 2, "key_ref": f"inline:{kv2}",
             "created_at": None, "superseded_at": None, "purged_at": None},
        ]
        current, history = await load_key_history(conn, ENT)
        assert [k.version for k in history] == [2]

    @pytest.mark.asyncio
    async def test_falls_back_to_tfk_when_history_empty(self):
        conn = _FakeConn()
        kv = generate_key_b64()
        conn.tfk = [{
            "enterprise_id": ENT, "version": 5, "key_ref": f"inline:{kv}",
            "rotated_at": None, "created_at": None,
            "reencrypt_status": "idle",
        }]
        current, history = await load_key_history(conn, ENT)
        assert current.version == 5
        assert len(history) == 1

    @pytest.mark.asyncio
    async def test_no_key_raises(self):
        conn = _FakeConn()
        with pytest.raises(CryptoError):
            await load_key_history(conn, ENT)


# ═════════════════════════════════════════════════════════════════════
# 5. Worker logic — per-column reencrypt + status state machine
# ═════════════════════════════════════════════════════════════════════


class TestReencryptTenant:

    def _setup_v1_only(self, conn, plaintext="api_secret_xyz"):
        kv = generate_key_b64()
        ref = f"inline:{kv}"
        conn.tfk = [{
            "enterprise_id": ENT, "version": 1, "key_ref": ref,
            "rotated_at": None, "created_at": None,
            "reencrypt_status": "pending",
            "reencrypt_started_at": None,
            "reencrypt_completed_at": None,
            "reencrypt_error": None,
        }]
        conn.tfkv = [{
            "enterprise_id": ENT, "version": 1, "key_ref": ref,
            "created_at": None, "superseded_at": None, "purged_at": None,
        }]
        k_v1 = resolve_tenant_key(tenant_id=str(ENT), key_ref=ref, version=1)
        ct = encrypt_field(plaintext, k_v1)
        conn.llm = [{
            "key_id": uuid4(),
            "enterprise_id": ENT,
            "api_key_enc": ct,
        }]
        return ref, plaintext

    @pytest.mark.asyncio
    async def test_idempotent_when_already_current(self):
        conn = _FakeConn()
        self._setup_v1_only(conn)
        report = await reencrypt_tenant(conn, ENT)
        assert report.status == "completed"
        # Row was already under current key v1 → fast-path
        assert report.columns[0].rows_already_current == 1
        assert report.columns[0].rows_reencrypted == 0

    @pytest.mark.asyncio
    async def test_rewrites_after_rotation(self):
        conn = _FakeConn()
        ref_v1, plaintext = self._setup_v1_only(conn)

        # Simulate rotation: add v2 to history + bump current
        kv2 = generate_key_b64()
        ref_v2 = f"inline:{kv2}"
        conn.tfk[0]["version"] = 2
        conn.tfk[0]["key_ref"] = ref_v2
        conn.tfk[0]["reencrypt_status"] = "pending"
        conn.tfkv.append({
            "enterprise_id": ENT, "version": 2, "key_ref": ref_v2,
            "created_at": None, "superseded_at": None, "purged_at": None,
        })

        report = await reencrypt_tenant(conn, ENT)
        assert report.status == "completed"
        assert report.current_version == 2
        col = report.columns[0]
        assert col.rows_scanned == 1
        assert col.rows_reencrypted == 1
        assert col.rows_failed == 0

        # Verify ciphertext is now decryptable under v2
        new_ct = conn.llm[0]["api_key_enc"]
        k_v2 = resolve_tenant_key(tenant_id=str(ENT), key_ref=ref_v2, version=2)
        assert decrypt_field(new_ct, k_v2) == plaintext

        # Verify status flipped to completed
        assert conn.tfk[0]["reencrypt_status"] == "completed"

    @pytest.mark.asyncio
    async def test_marks_old_versions_purged_on_success(self):
        conn = _FakeConn()
        ref_v1, _ = self._setup_v1_only(conn)
        # Rotate to v2
        kv2 = generate_key_b64()
        ref_v2 = f"inline:{kv2}"
        conn.tfk[0]["version"] = 2
        conn.tfk[0]["key_ref"] = ref_v2
        conn.tfkv.append({
            "enterprise_id": ENT, "version": 2, "key_ref": ref_v2,
            "created_at": None, "superseded_at": None, "purged_at": None,
        })

        await reencrypt_tenant(conn, ENT)
        v1_row = next(r for r in conn.tfkv if r["version"] == 1)
        assert v1_row["purged_at"] is not None

    @pytest.mark.asyncio
    async def test_undecryptable_row_marks_failed(self):
        """If a ciphertext can't be decrypted with ANY known key, the
        worker marks status=failed and records the row's PK."""
        conn = _FakeConn()
        self._setup_v1_only(conn)
        # Corrupt the ciphertext to simulate orphan row
        conn.llm[0]["api_key_enc"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="

        report = await reencrypt_tenant(conn, ENT)
        assert report.status == "failed"
        assert report.total_failed == 1
        assert report.columns[0].failed_pks  # has at least one
        assert conn.tfk[0]["reencrypt_status"] == "failed"
        assert conn.tfk[0]["reencrypt_error"] is not None

    @pytest.mark.asyncio
    async def test_no_key_provisioned_returns_failed(self):
        conn = _FakeConn()
        report = await reencrypt_tenant(conn, ENT)
        assert report.status == "failed"
        assert "no field-encryption key" in (report.error or "").lower()

    @pytest.mark.asyncio
    async def test_empty_ciphertext_skipped(self):
        conn = _FakeConn()
        ref_v1, _ = self._setup_v1_only(conn)
        conn.llm[0]["api_key_enc"] = ""
        report = await reencrypt_tenant(conn, ENT)
        assert report.status == "completed"
        assert report.columns[0].rows_reencrypted == 0


# ═════════════════════════════════════════════════════════════════════
# 6. Endpoint smoke
# ═════════════════════════════════════════════════════════════════════


class TestEndpoints:

    def test_rotate_initial_provision_inserts_v1(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["new_version"] == 1
        assert body["old_version"] == 0
        assert len(conn.tfk) == 1
        assert any(v["version"] == 1 for v in conn.tfkv)

    def test_rotate_archives_old_key(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)

        # First rotate provisions v1
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        # Second rotate bumps to v2 and archives v1
        r = client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        body = r.json()
        assert body["old_version"] == 1
        assert body["new_version"] == 2

        versions = sorted(v["version"] for v in conn.tfkv)
        assert versions == [1, 2]
        v1 = next(v for v in conn.tfkv if v["version"] == 1)
        assert v1["superseded_at"] is not None

    def test_rotate_marks_pending(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        assert conn.tfk[0]["reencrypt_status"] == "pending"

    def test_reencrypt_endpoint_runs_worker(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        r = client.post("/p2/auth/field-key/reencrypt", headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "completed"
        assert body["current_version"] == 1
        assert body["total_reencrypted"] == 0  # nothing encrypted yet

    def test_status_endpoint_404_when_missing(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get("/p2/auth/field-key/reencrypt/status", headers=ENT_HEADERS)
        assert r.status_code == 404

    def test_status_endpoint_returns_idle_after_provision(self):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        r = client.get("/p2/auth/field-key/reencrypt/status", headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["reencrypt_status"] == "idle"
        assert body["current_version"] == 1
        assert body["history_depth"] == 1


# ═════════════════════════════════════════════════════════════════════
# 7. Integration — full rotate→reencrypt→re-rotate chain
# ═════════════════════════════════════════════════════════════════════


class TestRotationChain:

    @pytest.mark.asyncio
    async def test_three_rotations_decrypt_all_history(self):
        """Simulate three rotations without running the worker; verify
        that decrypt_field_with_history can recover plaintext encrypted
        under any historical key."""
        plaintext = "sk-anthropic-test"
        keys: list[WrappedKey] = []
        ciphertexts: list[str] = []

        for v in (1, 2, 3):
            wk = _key(v)
            keys.append(wk)
            ciphertexts.append(encrypt_field(plaintext, wk))

        history_descending = list(reversed(keys))
        for ct in ciphertexts:
            pt, _ = decrypt_field_with_history(ct, history_descending)
            assert pt == plaintext

    def test_full_rotate_reencrypt_chain(self):
        """End-to-end: provision -> insert encrypted row -> rotate ->
        reencrypt -> verify row is now under the new key."""
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)

        # 1. Provision v1
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        v1_ref = conn.tfk[0]["key_ref"]
        k_v1 = resolve_tenant_key(
            tenant_id=str(ENT), key_ref=v1_ref, version=1,
        )

        # 2. Simulate a tenant_llm_api_keys row encrypted under v1
        plaintext = "secret-anthropic-key"
        conn.llm.append({
            "key_id": uuid4(),
            "enterprise_id": ENT,
            "api_key_enc": encrypt_field(plaintext, k_v1),
        })

        # 3. Rotate to v2
        client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        v2_ref = conn.tfk[0]["key_ref"]
        k_v2 = resolve_tenant_key(
            tenant_id=str(ENT), key_ref=v2_ref, version=2,
        )

        # 4. Reencrypt
        r = client.post("/p2/auth/field-key/reencrypt", headers=ENT_HEADERS)
        body = r.json()
        assert body["status"] == "completed"
        assert body["total_reencrypted"] == 1

        # 5. The row is now under v2
        assert decrypt_field(conn.llm[0]["api_key_enc"], k_v2) == plaintext

        # 6. v1 marked purged
        v1_row = next(v for v in conn.tfkv if v["version"] == 1)
        assert v1_row["purged_at"] is not None


# ═════════════════════════════════════════════════════════════════════
# 8. Performance + tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestPerformanceAndIsolation:

    @pytest.mark.asyncio
    async def test_100_rows_under_one_second(self):
        """Pure-Python crypto budget: 100 rows reencrypt should run
        well under 1 second on commodity hardware."""
        conn = _FakeConn()
        kv = generate_key_b64()
        ref = f"inline:{kv}"
        conn.tfk = [{
            "enterprise_id": ENT, "version": 1, "key_ref": ref,
            "rotated_at": None, "created_at": None,
            "reencrypt_status": "pending",
            "reencrypt_started_at": None,
            "reencrypt_completed_at": None,
            "reencrypt_error": None,
        }]
        conn.tfkv = [{
            "enterprise_id": ENT, "version": 1, "key_ref": ref,
            "created_at": None, "superseded_at": None, "purged_at": None,
        }]
        # Rotate to v2 + seed 100 rows under v1
        kv2 = generate_key_b64()
        ref_v2 = f"inline:{kv2}"
        k_v1 = resolve_tenant_key(tenant_id=str(ENT), key_ref=ref, version=1)
        for _ in range(100):
            conn.llm.append({
                "key_id": uuid4(),
                "enterprise_id": ENT,
                "api_key_enc": encrypt_field("payload", k_v1),
            })
        conn.tfk[0]["version"] = 2
        conn.tfk[0]["key_ref"] = ref_v2
        conn.tfkv.append({
            "enterprise_id": ENT, "version": 2, "key_ref": ref_v2,
            "created_at": None, "superseded_at": None, "purged_at": None,
        })

        t0 = time.perf_counter()
        report = await reencrypt_tenant(conn, ENT)
        elapsed = time.perf_counter() - t0
        assert report.status == "completed"
        assert report.total_reencrypted == 100
        assert elapsed < 1.0, f"100 rows took {elapsed:.2f}s — perf regression"

    @pytest.mark.asyncio
    async def test_cross_tenant_row_skipped(self):
        """K-1: worker only touches rows belonging to the requested
        tenant. A row owned by a different enterprise_id is left
        untouched even though it sits in the same table."""
        conn = _FakeConn()
        kv = generate_key_b64()
        ref = f"inline:{kv}"
        conn.tfk = [{
            "enterprise_id": ENT, "version": 1, "key_ref": ref,
            "rotated_at": None, "created_at": None,
            "reencrypt_status": "pending",
            "reencrypt_started_at": None,
            "reencrypt_completed_at": None,
            "reencrypt_error": None,
        }]
        conn.tfkv = [{
            "enterprise_id": ENT, "version": 1, "key_ref": ref,
            "created_at": None, "superseded_at": None, "purged_at": None,
        }]
        k_v1 = resolve_tenant_key(tenant_id=str(ENT), key_ref=ref, version=1)
        conn.llm = [
            {"key_id": uuid4(), "enterprise_id": ENT,
             "api_key_enc": encrypt_field("mine", k_v1)},
            # Foreign tenant — different enterprise_id
            {"key_id": uuid4(), "enterprise_id": ENT_OTHER,
             "api_key_enc": "FOREIGN-DO-NOT-TOUCH"},
        ]

        report = await reencrypt_tenant(conn, ENT)
        assert report.status == "completed"
        # Only the matching-tenant row was scanned
        assert report.columns[0].rows_scanned == 1
        # Foreign row untouched
        assert conn.llm[1]["api_key_enc"] == "FOREIGN-DO-NOT-TOUCH"
