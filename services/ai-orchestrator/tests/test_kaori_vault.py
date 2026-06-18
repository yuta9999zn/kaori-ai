"""
Tests for shared.kaori_vault — KV v2 wrapper.

P1-S2 (K-18 prep) — exercises path builders + HTTP roundtrip with a
mocked httpx client (no live Vault container needed).
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID

import httpx
import pytest

from ai_orchestrator.shared.kaori_vault import (
    KaoriVault,
    VaultError,
    get_default_client,
)


# ---------------------------------------------------------------------------
# Path builders
# ---------------------------------------------------------------------------


def test_platform_path_format():
    assert KaoriVault.platform_path("api_keys", "anthropic") == "platform/api_keys/anthropic"


def test_tenant_path_with_uuid():
    eid = UUID("11111111-1111-1111-1111-111111111111")
    assert KaoriVault.tenant_path(eid, "oauth_tokens", "google") == \
        "tenant/11111111-1111-1111-1111-111111111111/oauth_tokens/google"


def test_tenant_path_with_string_id():
    """Workspace_id-style identifiers (Phase 1 legacy) pass through verbatim."""
    assert KaoriVault.tenant_path("ws-abc-123", "connectors", "misa") == \
        "tenant/ws-abc-123/connectors/misa"


def test_service_path_format():
    assert KaoriVault.service_path("auth-service", "mfa_master_key") == \
        "service/auth-service/mfa_master_key"


# ---------------------------------------------------------------------------
# get() happy path + error mapping
# ---------------------------------------------------------------------------


def _mock_response(status: int, json_body: dict | None = None, text: str = ""):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.json = MagicMock(return_value=json_body or {})
    resp.text = text
    return resp


@pytest.mark.asyncio
async def test_get_returns_data_dict_from_kv_v2_envelope():
    """KV v2 wraps data: { "data": { "data": {...}, "metadata": {...} } }
    The wrapper unpacks the inner ``data`` so callers see plain dict."""
    body = {"data": {"data": {"api_key": "sk-anthropic-xxx"}, "metadata": {"version": 3}}}

    async def _get(url, headers):
        return _mock_response(200, body)

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(get=_get))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(addr="http://vault:8200", token="dev-token")
        result = await v.get("platform/api_keys/anthropic")

    assert result == {"api_key": "sk-anthropic-xxx"}


@pytest.mark.asyncio
async def test_get_404_raises_path_not_found():
    async def _get(url, headers):
        return _mock_response(404)

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(get=_get))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(token="dev-token")
        with pytest.raises(VaultError, match="path not found"):
            await v.get("platform/missing/key")


@pytest.mark.asyncio
async def test_get_403_raises_forbidden():
    async def _get(url, headers):
        return _mock_response(403, text="permission denied")

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(get=_get))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(token="dev-token")
        with pytest.raises(VaultError, match="forbidden"):
            await v.get("tenant/forbidden/api_keys/x")


@pytest.mark.asyncio
async def test_get_network_error_wraps_in_vault_error():
    async def _get(url, headers):
        raise httpx.ConnectError("connection refused")

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(get=_get))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(token="dev-token")
        with pytest.raises(VaultError, match="network error"):
            await v.get("platform/api_keys/x")


@pytest.mark.asyncio
async def test_get_unexpected_response_shape_raises():
    """If the body isn't the expected KV v2 envelope, fail loud rather
    than return None and let downstream null-deref."""
    bad_body = {"data": "not a dict"}

    async def _get(url, headers):
        return _mock_response(200, bad_body)

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(get=_get))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(token="dev-token")
        with pytest.raises(VaultError, match="response shape unexpected"):
            await v.get("platform/api_keys/x")


# ---------------------------------------------------------------------------
# put() + delete()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_put_wraps_data_in_kv_v2_payload():
    captured = {}

    async def _post(url, headers, json):
        captured["url"] = url
        captured["json"] = json
        return _mock_response(200, {"data": {"version": 1}})

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(post=_post))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(token="dev-token")
        await v.put("platform/smtp/credentials", {"host": "smtp", "user": "kaori"})

    # KV v2 requires { "data": { ... } } envelope
    assert captured["json"] == {"data": {"host": "smtp", "user": "kaori"}}
    assert captured["url"].endswith("/v1/secret/data/platform/smtp/credentials")


@pytest.mark.asyncio
async def test_delete_treats_404_as_success():
    """Deleting a missing path is idempotent — caller's intent ('it
    should be gone') is met whether or not the path existed."""
    async def _delete(url, headers):
        return _mock_response(404)

    client_cm = MagicMock()
    client_cm.__aenter__ = AsyncMock(return_value=MagicMock(delete=_delete))
    client_cm.__aexit__ = AsyncMock(return_value=False)

    with patch("httpx.AsyncClient", return_value=client_cm):
        v = KaoriVault(token="dev-token")
        await v.delete("platform/api_keys/old")  # must not raise


# ---------------------------------------------------------------------------
# Auth header + missing token
# ---------------------------------------------------------------------------


def test_missing_token_raises_on_auth_attempt():
    v = KaoriVault(token="")  # empty token
    with pytest.raises(VaultError, match="VAULT_TOKEN not configured"):
        v._auth_headers()


def test_token_passed_through_as_x_vault_token_header():
    v = KaoriVault(token="hvs.dev-root-token")
    assert v._auth_headers() == {"X-Vault-Token": "hvs.dev-root-token"}


# ---------------------------------------------------------------------------
# Lazy singleton
# ---------------------------------------------------------------------------


def test_get_default_client_returns_same_instance():
    """Process-global client is built once + reused. Tests that need
    isolation should NOT use the singleton."""
    import ai_orchestrator.shared.kaori_vault as mod
    mod._default_client = None  # reset for this test
    a = get_default_client()
    b = get_default_client()
    assert a is b


# ---------------------------------------------------------------------------
# get_or_env() — K-18 Vault-first, env-fallback resolution chain
# ---------------------------------------------------------------------------


def _patched_get_returning(value: dict | None, *, raise_error: VaultError | None = None):
    """Build a context manager that patches KaoriVault.get to return
    ``value`` (or raise ``raise_error``). Avoids re-mocking the httpx
    layer for get_or_env tests — the chain is already covered above."""
    if raise_error is not None:
        return patch.object(KaoriVault, "get", AsyncMock(side_effect=raise_error))
    return patch.object(KaoriVault, "get", AsyncMock(return_value=value))


@pytest.mark.asyncio
async def test_get_or_env_vault_hit_returns_keyed_value():
    """Happy path — Vault has the secret; env var must NOT be consulted
    even if set, because Vault is the source of truth (K-18)."""
    v = KaoriVault(token="dev-token")
    with _patched_get_returning({"api_key": "from-vault"}):
        # Set env var to a sentinel that would clearly be wrong if leaked through
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "WRONG-FROM-ENV"}, clear=False):
            result = await v.get_or_env(
                env_var="ANTHROPIC_API_KEY",
                vault_path="platform/api_keys/anthropic",
                key="api_key",
                profile="dev",
            )
    assert result == "from-vault"


@pytest.mark.asyncio
async def test_get_or_env_dev_profile_falls_back_to_env_when_vault_missing():
    """Phase 1 transition path: Vault unreachable → env var picks up the
    slack so dev/staging keep booting. Production guard verified separately."""
    v = KaoriVault(token="dev-token")
    with _patched_get_returning(None, raise_error=VaultError("path not found: x")):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "from-env"}, clear=False):
            result = await v.get_or_env(
                env_var="ANTHROPIC_API_KEY",
                vault_path="platform/api_keys/anthropic",
                key="api_key",
                profile="dev",
            )
    assert result == "from-env"


@pytest.mark.asyncio
async def test_get_or_env_dev_profile_raises_when_both_missing():
    """If Vault is missing AND env var is unset, fail loud rather than
    return empty string — empty string masks misconfiguration."""
    v = KaoriVault(token="dev-token")
    with _patched_get_returning(None, raise_error=VaultError("path not found: x")):
        # Wipe the env var explicitly — patch.dict + pop guarantees it's
        # absent regardless of the host shell.
        env = {k: val for k, val in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(VaultError, match="missing AND env var"):
                await v.get_or_env(
                    env_var="ANTHROPIC_API_KEY",
                    vault_path="platform/api_keys/anthropic",
                    key="api_key",
                    profile="dev",
                )


@pytest.mark.asyncio
async def test_get_or_env_production_profile_disables_env_fallback():
    """K-18 enforcement: production must resolve via Vault. Even if the
    env var is set with a valid-looking value, the fallback is refused
    so a missing Vault entry can never silently degrade to env in prod."""
    v = KaoriVault(token="prod-token")
    with _patched_get_returning(None, raise_error=VaultError("path not found: x")):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "would-have-worked-in-dev"}, clear=False):
            with pytest.raises(VaultError, match="K-18: production requires Vault"):
                await v.get_or_env(
                    env_var="ANTHROPIC_API_KEY",
                    vault_path="platform/api_keys/anthropic",
                    key="api_key",
                    profile="production",
                )


@pytest.mark.asyncio
async def test_get_or_env_multi_value_secret_requires_key_param():
    """If a Vault secret has multiple keys (e.g. SMTP host+user+password)
    the caller MUST disambiguate via ``key=`` — collapsing arbitrarily
    would surprise downstream code."""
    v = KaoriVault(token="dev-token")
    multi = {"host": "smtp.example.com", "user": "kaori", "password": "secret"}
    with _patched_get_returning(multi):
        with pytest.raises(VaultError, match="pass `key=` to disambiguate"):
            await v.get_or_env(
                env_var="SMTP_PASSWORD",
                vault_path="platform/smtp/credentials",
                # key intentionally omitted
                profile="dev",
            )


@pytest.mark.asyncio
async def test_get_or_env_single_value_secret_collapses_without_key():
    """Convenience: when a secret has exactly one key the caller can
    omit ``key=`` and the lone value is returned. Prevents boilerplate
    for the common single-value case (most API keys)."""
    v = KaoriVault(token="dev-token")
    with _patched_get_returning({"api_key": "lone-value"}):
        result = await v.get_or_env(
            env_var="ANTHROPIC_API_KEY",
            vault_path="platform/api_keys/anthropic",
            # key omitted on purpose
            profile="dev",
        )
    assert result == "lone-value"


@pytest.mark.asyncio
async def test_get_or_env_missing_key_in_vault_data_raises():
    """If the caller asks for ``key='private_key'`` but Vault returned
    only ``{'public_key': ...}``, the error must name both expected and
    available keys so the operator knows what to fix."""
    v = KaoriVault(token="dev-token")
    with _patched_get_returning({"public_key": "pubpub"}):
        with pytest.raises(VaultError, match="without expected key 'private_key'"):
            await v.get_or_env(
                env_var="JWT_PRIVATE_KEY",
                vault_path="service/auth-service/jwt_keypair",
                key="private_key",
                profile="dev",
            )
