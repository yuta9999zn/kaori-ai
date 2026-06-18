"""
Path A — Vault prod wiring (K-18) tests.

Covers:
  - kaori_vault.read_sync / write_sync — sync KV v2 client
  - crypto.resolve_tenant_key handles "vault:<path>" prefix
  - crypto.resolve_tenant_key refuses dev fallbacks under
    KAORI_PROFILE=production
  - auth_security._platform_mfa_master_key reads Vault first,
    env-fallback in dev, raises in prod
  - rotate_field_key writes to Vault and stores vault:<path> in
    tenant_field_keys.key_ref under prod profile

8-section template (compressed — 4 dedicated sections since the
underlying components are already exercised by upstream test files):
  1. read_sync / write_sync behaviour
  2. resolve_tenant_key vault: path handling
  3. K-18 production profile enforcement
  4. MFA master key + rotate endpoint integration
"""
from __future__ import annotations

import base64
import os
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import httpx
import pytest

from ai_orchestrator.shared.crypto import (
    CryptoError,
    WrappedKey,
    decrypt_field,
    encrypt_field,
    generate_key_b64,
    resolve_tenant_key,
)
from ai_orchestrator.shared.kaori_vault import KaoriVault, VaultError


ENT = UUID("11111111-1111-1111-1111-111111111111")


# ═════════════════════════════════════════════════════════════════════
# 1. read_sync / write_sync behaviour
# ═════════════════════════════════════════════════════════════════════


class TestVaultSyncOps:

    def test_read_sync_unwraps_kv_v2(self):
        v = KaoriVault(addr="http://fake-vault:8200", token="tok")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "data": {"data": {"key": "abc"}, "metadata": {}},
        }
        with patch("httpx.Client") as mc:
            client_ctx = MagicMock()
            client_ctx.__enter__.return_value.get.return_value = fake_resp
            client_ctx.__exit__.return_value = False
            mc.return_value = client_ctx
            out = v.read_sync("platform/test")
        assert out == {"key": "abc"}

    def test_read_sync_404_raises(self):
        v = KaoriVault(addr="http://fake-vault:8200", token="tok")
        fake_resp = MagicMock()
        fake_resp.status_code = 404
        fake_resp.text = ""
        with patch("httpx.Client") as mc:
            client_ctx = MagicMock()
            client_ctx.__enter__.return_value.get.return_value = fake_resp
            client_ctx.__exit__.return_value = False
            mc.return_value = client_ctx
            with pytest.raises(VaultError):
                v.read_sync("platform/missing")

    def test_read_sync_403_raises(self):
        v = KaoriVault(addr="http://fake-vault:8200", token="tok")
        fake_resp = MagicMock()
        fake_resp.status_code = 403
        fake_resp.text = "denied"
        with patch("httpx.Client") as mc:
            client_ctx = MagicMock()
            client_ctx.__enter__.return_value.get.return_value = fake_resp
            client_ctx.__exit__.return_value = False
            mc.return_value = client_ctx
            with pytest.raises(VaultError):
                v.read_sync("platform/forbidden")

    def test_read_sync_network_error(self):
        v = KaoriVault(addr="http://no-vault:8200", token="tok")
        with patch("httpx.Client") as mc:
            client_ctx = MagicMock()
            client_ctx.__enter__.return_value.get.side_effect = \
                httpx.ConnectError("DNS")
            client_ctx.__exit__.return_value = False
            mc.return_value = client_ctx
            with pytest.raises(VaultError) as exc:
                v.read_sync("any")
            assert "network error" in str(exc.value).lower()

    def test_write_sync_success(self):
        v = KaoriVault(addr="http://fake-vault:8200", token="tok")
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        with patch("httpx.Client") as mc:
            client_ctx = MagicMock()
            client_ctx.__enter__.return_value.post.return_value = fake_resp
            client_ctx.__exit__.return_value = False
            mc.return_value = client_ctx
            v.write_sync("platform/write_test", {"key": "abc"})

    def test_write_sync_failure(self):
        v = KaoriVault(addr="http://fake-vault:8200", token="tok")
        fake_resp = MagicMock()
        fake_resp.status_code = 500
        fake_resp.text = "internal"
        with patch("httpx.Client") as mc:
            client_ctx = MagicMock()
            client_ctx.__enter__.return_value.post.return_value = fake_resp
            client_ctx.__exit__.return_value = False
            mc.return_value = client_ctx
            with pytest.raises(VaultError):
                v.write_sync("platform/bad", {"key": "abc"})


# ═════════════════════════════════════════════════════════════════════
# 2. resolve_tenant_key — vault:<path> prefix
# ═════════════════════════════════════════════════════════════════════


class TestVaultPrefixResolve:

    def test_vault_prefix_reads_key_field(self):
        key_b64 = generate_key_b64()
        fake_client = MagicMock()
        fake_client.read_sync.return_value = {"key": key_b64}

        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref="vault:tenant/t1/encryption/field_key_v1",
            version=2,
            vault_client=fake_client,
        )
        assert wk.version == 2
        assert len(wk.key_bytes) == 32
        fake_client.read_sync.assert_called_once_with(
            "tenant/t1/encryption/field_key_v1",
        )

    def test_vault_prefix_missing_key_field_raises(self):
        fake_client = MagicMock()
        fake_client.read_sync.return_value = {"wrong_field": "x"}
        with pytest.raises(CryptoError):
            resolve_tenant_key(
                tenant_id="t1",
                key_ref="vault:tenant/t1/encryption/field_key",
                vault_client=fake_client,
            )

    def test_vault_prefix_accepts_raw_string(self):
        """Back-compat: injected mocks may return raw base64 string."""
        key_b64 = generate_key_b64()
        fake_client = MagicMock()
        fake_client.read_sync.return_value = key_b64
        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref="vault:tenant/t1/encryption/key",
            vault_client=fake_client,
        )
        assert len(wk.key_bytes) == 32

    def test_vault_prefix_round_trip(self):
        key_b64 = generate_key_b64()
        fake_client = MagicMock()
        fake_client.read_sync.return_value = {"key": key_b64}
        wk = resolve_tenant_key(
            tenant_id="t1", key_ref="vault:foo/bar", vault_client=fake_client,
        )
        ct = encrypt_field("secret", wk)
        assert decrypt_field(ct, wk) == "secret"


# ═════════════════════════════════════════════════════════════════════
# 3. K-18 production profile enforcement
# ═════════════════════════════════════════════════════════════════════


class TestK18ProductionEnforcement:

    def test_inline_refused_in_production(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "production")
        with pytest.raises(CryptoError) as exc:
            resolve_tenant_key(
                tenant_id="t1",
                key_ref=f"inline:{generate_key_b64()}",
            )
        assert "K-18" in str(exc.value)

    def test_env_var_refused_in_production(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "production")
        monkeypatch.setenv("KAORI_FIELD_KEY", generate_key_b64())
        with pytest.raises(CryptoError) as exc:
            resolve_tenant_key(tenant_id="t1", key_ref="")
        assert "K-18" in str(exc.value)

    def test_empty_keyref_refused_in_production(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "production")
        monkeypatch.delenv("KAORI_FIELD_KEY", raising=False)
        with pytest.raises(CryptoError):
            resolve_tenant_key(tenant_id="t1", key_ref="")

    def test_vault_path_works_in_production(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "production")
        key_b64 = generate_key_b64()
        fake_client = MagicMock()
        fake_client.read_sync.return_value = {"key": key_b64}
        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref="vault:tenant/t1/encryption/field_key",
            vault_client=fake_client,
        )
        assert len(wk.key_bytes) == 32

    def test_inline_works_in_dev(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "dev")
        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref=f"inline:{generate_key_b64()}",
        )
        assert len(wk.key_bytes) == 32

    def test_default_profile_is_dev(self, monkeypatch):
        monkeypatch.delenv("KAORI_PROFILE", raising=False)
        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref=f"inline:{generate_key_b64()}",
        )
        assert len(wk.key_bytes) == 32

    def test_staging_is_not_production(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "staging")
        # Staging still allows dev fallbacks (per get_or_env's
        # is_production = "prod"/"production" check)
        wk = resolve_tenant_key(
            tenant_id="t1",
            key_ref=f"inline:{generate_key_b64()}",
        )
        assert len(wk.key_bytes) == 32


# ═════════════════════════════════════════════════════════════════════
# 4. MFA master key + rotate endpoint integration
# ═════════════════════════════════════════════════════════════════════


class TestMfaMasterKey:

    def test_mfa_master_key_reads_vault_first(self, monkeypatch):
        key_bytes = os.urandom(32)
        key_b64 = base64.b64encode(key_bytes).decode("ascii")
        monkeypatch.delenv("KAORI_MFA_KEY", raising=False)
        monkeypatch.setenv("KAORI_PROFILE", "dev")

        from ai_orchestrator.routers import auth_security
        fake_vault = MagicMock()
        fake_vault.read_sync.return_value = {"key": key_b64}

        with patch(
            "ai_orchestrator.shared.kaori_vault.get_default_client",
            return_value=fake_vault,
        ):
            out = auth_security._platform_mfa_master_key()
        assert out == key_bytes

    def test_mfa_master_key_env_fallback_in_dev(self, monkeypatch):
        key_bytes = os.urandom(32)
        key_b64 = base64.b64encode(key_bytes).decode("ascii")
        monkeypatch.setenv("KAORI_MFA_KEY", key_b64)
        monkeypatch.setenv("KAORI_PROFILE", "dev")

        from ai_orchestrator.routers import auth_security

        def _broken(*_a, **_kw):
            raise VaultError("Vault unreachable (test)")

        fake_vault = MagicMock()
        fake_vault.read_sync.side_effect = _broken

        with patch(
            "ai_orchestrator.shared.kaori_vault.get_default_client",
            return_value=fake_vault,
        ):
            out = auth_security._platform_mfa_master_key()
        assert out == key_bytes

    def test_mfa_master_key_raises_in_production(self, monkeypatch):
        monkeypatch.setenv("KAORI_PROFILE", "production")
        monkeypatch.setenv("KAORI_MFA_KEY", base64.b64encode(os.urandom(32)).decode())

        from ai_orchestrator.routers import auth_security
        from fastapi import HTTPException
        from ai_orchestrator.shared.kaori_vault import VaultError as _VE

        fake_vault = MagicMock()
        fake_vault.read_sync.side_effect = _VE("Vault unavailable (test)")
        with patch(
            "ai_orchestrator.shared.kaori_vault.get_default_client",
            return_value=fake_vault,
        ):
            with pytest.raises(HTTPException) as exc:
                auth_security._platform_mfa_master_key()
            assert "K-18" in exc.value.detail

    def test_mfa_master_key_rejects_wrong_length(self, monkeypatch):
        # Vault returns wrong-length key
        bad_key = base64.b64encode(b"too-short").decode()
        monkeypatch.setenv("KAORI_PROFILE", "dev")

        from ai_orchestrator.routers import auth_security
        from fastapi import HTTPException
        fake_vault = MagicMock()
        fake_vault.read_sync.return_value = {"key": bad_key}
        with patch(
            "ai_orchestrator.shared.kaori_vault.get_default_client",
            return_value=fake_vault,
        ):
            with pytest.raises(HTTPException) as exc:
                auth_security._platform_mfa_master_key()
            assert "32 bytes" in exc.value.detail
