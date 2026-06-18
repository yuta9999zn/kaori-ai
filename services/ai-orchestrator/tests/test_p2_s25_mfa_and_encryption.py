"""
P2-S25 tests:
  P2-AUTH-002 — MFA TOTP enrollment + verify + backup codes
  P2-ENC-001  — field-level AES-256-GCM encryption

8-section template per anh's "chuẩn chỉ + hiệu năng + phi chức năng":
  1. Mig 074 shape         — 3 tables + CHECK + UNIQUE + indexes
  2. TOTP RFC 6238 pure    — verify drift window + invalid codes
  3. Backup codes          — generation + hash + uniqueness
  4. Secret encryption     — round-trip + bad master key
  5. Field encryption      — round-trip + tampering detection + null-friendly
  6. Key resolver          — Vault + inline + env-var paths
  7. Endpoint smoke        — enroll + verify + status + rotate
  8. Performance + tenant isolation
"""
from __future__ import annotations

import base64
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.shared.crypto import (
    CryptoError,
    WrappedKey,
    decrypt_field,
    encrypt_field,
    generate_key_b64,
    resolve_tenant_key,
)
from ai_orchestrator.shared.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_secret,
    hash_backup_code,
    otpauth_url,
    totp_code,
    verify_totp,
)


ENTERPRISE = "11111111-1111-1111-1111-111111111111"
USER       = "22222222-2222-2222-2222-222222222222"
USER2      = "33333333-3333-3333-3333-333333333333"
HEADERS = {"X-Enterprise-ID": ENTERPRISE, "X-User-ID": USER,
           "X-User-Email": "user@acme.com"}
ENT_HEADERS = {"X-Enterprise-ID": ENTERPRISE}

REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"

MASTER_KEY = os.urandom(32)
MASTER_KEY_B64 = base64.b64encode(MASTER_KEY).decode("ascii")


def _make_conn() -> AsyncMock:
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchrow.return_value = None
    conn.execute.return_value = "INSERT 0 1"
    tx = AsyncMock()
    tx.__aenter__.return_value = tx
    tx.__aexit__.return_value = False
    conn.transaction = MagicMock(return_value=tx)
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
    from ai_orchestrator.routers import auth_security
    app = FastAPI()
    app.include_router(auth_security.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 074 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig074Shape:

    @pytest.fixture(scope="class")
    def mig_text(self) -> str:
        return (MIG_DIR / "074_mfa_field_encryption.sql").read_text(encoding="utf-8")

    def test_3_tables_present(self, mig_text: str):
        for t in ("mfa_secrets", "mfa_backup_codes", "tenant_field_keys"):
            assert f"CREATE TABLE IF NOT EXISTS {t}" in mig_text

    def test_mfa_backup_codes_nonneg_check(self, mig_text: str):
        assert "chk_mfa_backup_codes_nonneg" in mig_text
        assert "backup_codes_remaining >= 0" in mig_text

    def test_tenant_field_keys_unique_per_enterprise(self, mig_text: str):
        assert "UNIQUE REFERENCES enterprises" in mig_text

    def test_field_key_version_positive(self, mig_text: str):
        assert "chk_tfk_version_pos" in mig_text
        assert "version > 0" in mig_text

    def test_backup_codes_cascade_on_secret_delete(self, mig_text: str):
        assert "REFERENCES mfa_secrets(user_id) ON DELETE CASCADE" in mig_text

    def test_partial_index_active_backup_codes(self, mig_text: str):
        assert "idx_mfa_backup_user_active" in mig_text
        assert "WHERE used_at IS NULL" in mig_text


# ═════════════════════════════════════════════════════════════════════
# 2. TOTP RFC 6238 pure
# ═════════════════════════════════════════════════════════════════════


class TestTOTPPure:

    def test_code_is_6_digits(self):
        secret = generate_secret()
        code = totp_code(secret, at=1700000000)
        assert len(code) == 6
        assert code.isdigit()

    def test_same_input_same_code(self):
        secret = generate_secret()
        c1 = totp_code(secret, at=1700000000)
        c2 = totp_code(secret, at=1700000000)
        assert c1 == c2

    def test_different_time_different_code(self):
        secret = generate_secret()
        c1 = totp_code(secret, at=1700000000)
        c2 = totp_code(secret, at=1700000060)   # +60s = 2 steps
        assert c1 != c2

    def test_verify_accepts_current_step(self):
        secret = generate_secret()
        now = 1700000000
        code = totp_code(secret, at=now)
        assert verify_totp(secret, code, at=now) is True

    def test_verify_accepts_drift_within_window(self):
        secret = generate_secret()
        now = 1700000000
        prev_step = totp_code(secret, at=now - 30)
        next_step = totp_code(secret, at=now + 30)
        # drift_steps=1 (default) accepts ±30s
        assert verify_totp(secret, prev_step, at=now) is True
        assert verify_totp(secret, next_step, at=now) is True

    def test_verify_rejects_outside_window(self):
        secret = generate_secret()
        now = 1700000000
        far_past = totp_code(secret, at=now - 120)   # 4 steps back
        assert verify_totp(secret, far_past, at=now) is False

    def test_verify_rejects_wrong_format(self):
        secret = generate_secret()
        assert verify_totp(secret, "abc123") is False
        assert verify_totp(secret, "12345") is False    # too short
        assert verify_totp(secret, "1234567") is False  # too long
        assert verify_totp(secret, "") is False

    def test_verify_drift_zero_strict(self):
        """drift_steps=0 → strict; the current step only."""
        secret = generate_secret()
        now = 1700000000
        prev_step = totp_code(secret, at=now - 30)
        assert verify_totp(secret, prev_step, at=now, drift_steps=0) is False

    def test_otpauth_url_structure(self):
        secret = generate_secret()
        uri = otpauth_url(issuer="Kaori AI", account_label="user@acme.com",
                          secret=secret)
        assert uri.startswith("otpauth://totp/")
        assert "secret=" in uri
        assert "issuer=Kaori%20AI" in uri
        assert "algorithm=SHA1" in uri
        assert "digits=6" in uri
        assert "period=30" in uri


# ═════════════════════════════════════════════════════════════════════
# 3. Backup codes
# ═════════════════════════════════════════════════════════════════════


class TestBackupCodes:

    def test_generate_count(self):
        codes = generate_backup_codes(count=10)
        assert len(codes) == 10
        assert len(set(codes)) == 10    # unique

    def test_each_code_is_10_chars_alphanum(self):
        codes = generate_backup_codes(count=20)
        for c in codes:
            assert len(c) == 10
            assert c.isalnum()
            # No ambiguous chars
            for ch in "01OI":
                assert ch not in c

    def test_hash_deterministic(self):
        h1 = hash_backup_code("ABCDE12345")
        h2 = hash_backup_code("ABCDE12345")
        assert h1 == h2
        assert len(h1) == 64    # SHA-256 hex


# ═════════════════════════════════════════════════════════════════════
# 4. Secret encryption (at rest)
# ═════════════════════════════════════════════════════════════════════


class TestSecretEncryption:

    def test_round_trip(self):
        secret = generate_secret()
        enc = encrypt_secret(secret, MASTER_KEY)
        dec = decrypt_secret(enc, MASTER_KEY)
        assert dec == secret

    def test_each_encrypt_unique_ciphertext(self):
        """Different IV each time → different ciphertext for same plaintext."""
        secret = b"x" * 20
        e1 = encrypt_secret(secret, MASTER_KEY)
        e2 = encrypt_secret(secret, MASTER_KEY)
        assert e1 != e2

    def test_wrong_master_key_raises(self):
        secret = generate_secret()
        enc = encrypt_secret(secret, MASTER_KEY)
        wrong = os.urandom(32)
        with pytest.raises(Exception):
            decrypt_secret(enc, wrong)

    def test_master_key_wrong_size_rejected(self):
        with pytest.raises(ValueError):
            encrypt_secret(generate_secret(), os.urandom(16))


# ═════════════════════════════════════════════════════════════════════
# 5. Field encryption (column-level)
# ═════════════════════════════════════════════════════════════════════


class TestFieldEncryption:

    @pytest.fixture
    def key(self) -> WrappedKey:
        return WrappedKey(key_bytes=os.urandom(32), version=1)

    def test_round_trip(self, key):
        plain = "0123456789012"   # CCCD-like 13 digits
        ct = encrypt_field(plain, key)
        assert ct != plain
        assert decrypt_field(ct, key) == plain

    def test_empty_passes_through(self, key):
        assert encrypt_field("", key) == ""
        assert decrypt_field("", key) == ""

    def test_each_encrypt_unique(self, key):
        ct1 = encrypt_field("hello", key)
        ct2 = encrypt_field("hello", key)
        assert ct1 != ct2

    def test_tampering_detected(self, key):
        ct = encrypt_field("sensitive", key)
        blob = base64.b64decode(ct)
        # Flip a byte in the ciphertext body
        tampered = blob[:14] + bytes([blob[14] ^ 1]) + blob[15:]
        tampered_b64 = base64.b64encode(tampered).decode("ascii")
        with pytest.raises(CryptoError):
            decrypt_field(tampered_b64, key)

    def test_truncated_ciphertext_rejected(self, key):
        ct = encrypt_field("data", key)
        blob = base64.b64decode(ct)
        truncated = base64.b64encode(blob[:10]).decode("ascii")
        with pytest.raises(CryptoError):
            decrypt_field(truncated, key)

    def test_wrong_version_rejected(self, key):
        # Encrypt with version 1, then mangle the leading version byte
        ct = encrypt_field("x", key)
        blob = base64.b64decode(ct)
        bad_version = bytes([99]) + blob[1:]
        bad_b64 = base64.b64encode(bad_version).decode("ascii")
        with pytest.raises(CryptoError):
            decrypt_field(bad_b64, key)

    def test_invalid_base64_rejected(self, key):
        with pytest.raises(CryptoError):
            decrypt_field("not-valid-base64!!!", key)

    def test_unicode_round_trip(self, key):
        plain = "Nguyễn Văn A — số: 0901234567"
        ct = encrypt_field(plain, key)
        assert decrypt_field(ct, key) == plain


# ═════════════════════════════════════════════════════════════════════
# 6. Key resolver
# ═════════════════════════════════════════════════════════════════════


class TestKeyResolver:

    def test_inline_prefix_dev_path(self):
        key_b64 = generate_key_b64()
        wrapped = resolve_tenant_key(
            tenant_id="t1", key_ref=f"inline:{key_b64}",
        )
        assert len(wrapped.key_bytes) == 32
        assert wrapped.version == 1

    def test_env_var_fallback(self, monkeypatch):
        monkeypatch.setenv("KAORI_FIELD_KEY", generate_key_b64())
        wrapped = resolve_tenant_key(tenant_id="t1", key_ref="")
        assert len(wrapped.key_bytes) == 32

    def test_no_source_raises(self, monkeypatch):
        monkeypatch.delenv("KAORI_FIELD_KEY", raising=False)
        with pytest.raises(CryptoError):
            resolve_tenant_key(tenant_id="t1", key_ref="")

    def test_vault_client_path(self):
        class _MockVault:
            def read(self, _path):
                return generate_key_b64()
        wrapped = resolve_tenant_key(
            tenant_id="t1", key_ref="kv/data/tenants/t1/field-key",
            vault_client=_MockVault(),
        )
        assert len(wrapped.key_bytes) == 32


# ═════════════════════════════════════════════════════════════════════
# 7. Endpoint smoke
# ═════════════════════════════════════════════════════════════════════


class TestEndpointSmoke:

    @pytest.fixture(autouse=True)
    def _set_master_key(self, monkeypatch):
        monkeypatch.setenv("KAORI_MFA_KEY", MASTER_KEY_B64)

    def test_enroll_returns_secret_and_codes(self):
        from ai_orchestrator.routers import auth_security
        conn = _make_conn()
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/p2/auth/mfa/enroll", headers=HEADERS)
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["enrolled"] is True
        assert len(body["backup_codes"]) == 10
        assert body["otpauth_url"].startswith("otpauth://totp/")
        assert len(body["secret_b32"]) >= 26    # 20 bytes base32 = 32 chars unpadded

    def test_status_no_enrollment_returns_disabled(self):
        from ai_orchestrator.routers import auth_security
        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/p2/auth/mfa/status", headers=HEADERS)
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        assert r.json()["enrolled"] is False

    def test_verify_404_when_not_enrolled(self):
        from ai_orchestrator.routers import auth_security
        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/p2/auth/mfa/verify",
                            json={"code": "123456"}, headers=HEADERS)
        assert r.status_code == 404

    def test_field_key_status_404_when_no_key(self):
        from ai_orchestrator.routers import auth_security
        conn = _make_conn()
        conn.fetchrow.return_value = None
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.get("/p2/auth/field-key/status", headers=ENT_HEADERS)
        assert r.status_code == 404

    def test_field_key_rotate_creates_or_bumps(self):
        from ai_orchestrator.routers import auth_security
        conn = _make_conn()
        # Rotate now does two fetchrow calls:
        #   1. SELECT version, key_ref FROM tenant_field_keys (existence probe)
        #   2. UPDATE ... RETURNING (or INSERT ... RETURNING for first time)
        existing_row = _row(version=1, key_ref="inline:OLDKEYREF")
        bumped_row = _row(
            version=2,
            rotated_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        conn.fetchrow.side_effect = [existing_row, bumped_row]
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/p2/auth/field-key/rotate", headers=ENT_HEADERS)
        assert r.status_code == 200
        body = r.json()
        assert body["new_version"] == 2
        assert body["old_version"] == 1


# ═════════════════════════════════════════════════════════════════════
# 8. Performance + tenant isolation
# ═════════════════════════════════════════════════════════════════════


class TestPerformance:

    def test_totp_verify_under_1ms(self):
        secret = generate_secret()
        code = totp_code(secret, at=1700000000)
        t0 = time.perf_counter()
        for _ in range(1000):
            verify_totp(secret, code, at=1700000000)
        avg = (time.perf_counter() - t0) / 1000
        assert avg < 0.001, f"verify too slow: {avg:.5f}s"

    def test_field_encrypt_1000_under_500ms(self):
        key = WrappedKey(key_bytes=os.urandom(32), version=1)
        t0 = time.perf_counter()
        for i in range(1000):
            encrypt_field(f"value {i}", key)
        elapsed = time.perf_counter() - t0
        assert elapsed < 0.5, f"too slow: {elapsed:.3f}s for 1000 encrypts"


class TestTenantIsolation:

    def test_enroll_requires_user_header(self):
        client = TestClient(_make_app())
        r = client.post("/p2/auth/mfa/enroll",
                        headers={"X-Enterprise-ID": ENTERPRISE})
        assert r.status_code == 422

    def test_field_key_status_requires_enterprise(self):
        client = TestClient(_make_app())
        r = client.get("/p2/auth/field-key/status")
        assert r.status_code == 422


# ─── Phase 2.9 K-13 — MFA Idempotency-Key coverage ─────────────────


class TestIdempotencyKeyMfa:
    """K-13 coverage Phase 2.9: enroll_mfa + verify_mfa accept
    Idempotency-Key header. HIGH severity — double-enroll overwrites
    TOTP secret + drops backup codes; Idempotency-Key returns the
    original payload so the user keeps the codes they already saved."""

    @pytest.fixture(autouse=True)
    def _set_master_key(self, monkeypatch):
        monkeypatch.setenv("KAORI_MFA_KEY", MASTER_KEY_B64)

    def test_enroll_with_duplicate_key_returns_cached(self, monkeypatch):
        from ai_orchestrator.routers import auth_security

        # First call: cache miss → DB enroll
        # Second call same key: cache hit → return original payload
        cached_enroll = {
            "secret_b32": "JBSWY3DPEHPK3PXP" * 2,   # placeholder 32 chars
            "otpauth_url": "otpauth://totp/Kaori%20AI:user?secret=ABCD",
            "backup_codes": ["CODE000001", "CODE000002"] * 5,
            "enrolled": True,
            "qr_payload_size": 80,
        }

        class _Hit:
            cached = True
            response_payload = cached_enroll

        async def _fake_get_or_set(**kwargs):
            return _Hit()

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)

        # DB should NOT be touched on cache hit
        db_calls = {"count": 0}
        conn = _make_conn()
        original_execute = conn.execute

        async def _counting_execute(*a, **k):
            db_calls["count"] += 1
            return await original_execute(*a, **k)
        conn.execute = _counting_execute

        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post(
                "/p2/auth/mfa/enroll",
                headers={**HEADERS, "Idempotency-Key": "TEST-IDEMPOTENCY-ENROLL-DUP"},
            )
        assert r.status_code == 201
        body = r.json()
        # Cached payload returned verbatim
        assert len(body["backup_codes"]) == 10
        assert body["enrolled"] is True
        # DB enroll NEVER ran
        assert db_calls["count"] == 0

    def test_enroll_first_call_records_outcome(self, monkeypatch):
        from ai_orchestrator.routers import auth_security

        class _Miss:
            cached = False
            response_payload = {}

        recorded = {}

        async def _fake_get_or_set(**kwargs):
            return _Miss()

        async def _fake_record(**kwargs):
            recorded.update(kwargs)

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fake_get_or_set)
        monkeypatch.setattr(_idem, "record_outcome", _fake_record)

        conn = _make_conn()
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post(
                "/p2/auth/mfa/enroll",
                headers={**HEADERS, "Idempotency-Key": "TEST-IDEMPOTENCY-ENROLL-FIRSTCALL"},
            )
        assert r.status_code == 201
        # Verify the outcome was recorded with our key
        assert recorded.get("key") == "TEST-IDEMPOTENCY-ENROLL-FIRSTCALL"
        rp = recorded.get("response_payload", {})
        assert rp.get("enrolled") is True
        assert "backup_codes" in rp

    def test_enroll_no_key_skips_idempotency(self, monkeypatch):
        from ai_orchestrator.routers import auth_security

        idem_calls = {"get": 0, "record": 0}

        async def _fail_get(**kwargs):
            idem_calls["get"] += 1
            raise AssertionError("get_or_set should not be called")

        async def _fail_record(**kwargs):
            idem_calls["record"] += 1
            raise AssertionError("record_outcome should not be called")

        from ai_orchestrator.workflow_runtime import idempotency_store as _idem
        monkeypatch.setattr(_idem, "get_or_set", _fail_get)
        monkeypatch.setattr(_idem, "record_outcome", _fail_record)

        conn = _make_conn()
        with patch.object(auth_security, "acquire_for_tenant", _tenant_ctx(conn)):
            client = TestClient(_make_app())
            r = client.post("/p2/auth/mfa/enroll", headers=HEADERS)
        assert r.status_code == 201
        assert idem_calls["get"] == 0
        assert idem_calls["record"] == 0
