"""
P2-AUTH-001 SSO tests.

8-section template:
  1. Mig 079 shape         — 3 tables + check constraints + indexes
  2. Provider factory       — get_provider + registry + ProviderNotConfigured
  3. Google provider        — authorize_url + exchange_code_for_profile
  4. Microsoft provider     — authorize_url + exchange_code_for_profile
  5. Router /start           — state issued + URL valid
  6. Router /callback        — state replay + email match + exchange code
  7. Router /exchange-info  — internal token gate + race condition
  8. End-to-end integration — full lifecycle
"""
from __future__ import annotations

import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_orchestrator.shared.sso_providers import (
    GoogleProvider,
    MicrosoftProvider,
    OAuthExchangeError,
    ProviderNotConfigured,
    SSOProfile,
    UnknownProvider,
    _reset_registry_for_tests,
    get_provider,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
MIG_DIR = REPO_ROOT / "infrastructure" / "postgres" / "migrations"

ENT = UUID("11111111-1111-1111-1111-111111111111")
USR = UUID("22222222-2222-2222-2222-222222222222")


@pytest.fixture(autouse=True)
def _reset_registry():
    _reset_registry_for_tests()
    yield
    _reset_registry_for_tests()


class _Row(dict):
    """Mimic asyncpg.Record — supports both row['key'] and dict(row)."""
    def __init__(self, **kw):
        super().__init__(**kw)


def _row(**kw):
    return _Row(**kw)


class _FakeConn:
    """In-memory stand-in for asyncpg. Models the tables touched by SSO."""

    def __init__(self):
        self.users:        list[dict] = []
        self.identities:   list[dict] = []
        self.states:       list[dict] = []
        self.exchanges:    list[dict] = []

    @asynccontextmanager
    async def transaction(self):
        yield self

    async def execute(self, sql, *args):
        s = " ".join(sql.split())
        now = datetime.now(timezone.utc)

        if s.startswith("INSERT INTO sso_oauth_state"):
            state, provider, return_url, created_at, expires_at = args
            self.states.append({
                "state_token": state, "provider": provider,
                "return_url": return_url, "created_at": created_at,
                "expires_at": expires_at, "consumed_at": None,
            })
            return "INSERT 0 1"
        if s.startswith("UPDATE sso_oauth_state SET consumed_at"):
            for r in self.states:
                if r["state_token"] == args[0] and r["consumed_at"] is None:
                    r["consumed_at"] = now
            return "UPDATE 1"
        if s.startswith("INSERT INTO sso_exchange_codes"):
            (code, ent, uid, sid, prov, c_at, e_at) = args
            self.exchanges.append({
                "code": code, "enterprise_id": ent, "user_id": uid,
                "sso_identity_id": sid, "provider": prov,
                "created_at": c_at, "expires_at": e_at,
                "consumed_at": None, "consumed_by_ip": None,
            })
            return "INSERT 0 1"
        raise AssertionError(f"unhandled execute: {s[:120]}")

    async def fetchrow(self, sql, *args):
        s = " ".join(sql.split())
        if s.startswith("SELECT provider, return_url, expires_at, consumed_at"):
            for r in self.states:
                if r["state_token"] == args[0]:
                    return _row(**r)
            return None
        if s.startswith("INSERT INTO sso_identities"):
            (ent, uid, prov, sub, email, name, raw) = args
            for r in self.identities:
                if r["provider"] == prov and r["provider_sub"] == sub:
                    r["last_seen_at"] = datetime.now(timezone.utc)
                    r["email_at_signup"] = email
                    r["name_at_signup"] = name
                    return _row(sso_identity_id=r["sso_identity_id"])
            sid = uuid4()
            self.identities.append({
                "sso_identity_id": sid, "enterprise_id": ent,
                "user_id": uid, "provider": prov, "provider_sub": sub,
                "email_at_signup": email, "name_at_signup": name,
                "raw_profile": raw,
                "first_seen_at": datetime.now(timezone.utc),
                "last_seen_at": datetime.now(timezone.utc),
            })
            return _row(sso_identity_id=sid)
        if s.startswith("SELECT user_id, enterprise_id FROM enterprise_users"):
            email = args[0]
            for r in self.users:
                if r["email"].lower() == email.lower():
                    return _row(user_id=r["user_id"],
                                enterprise_id=r["enterprise_id"])
            return None
        if s.startswith("SELECT enterprise_id, user_id, sso_identity_id"):
            for r in self.exchanges:
                if r["code"] == args[0]:
                    return _row(**r)
            return None
        if s.startswith("UPDATE sso_exchange_codes"):
            code, ip = args
            for r in self.exchanges:
                if r["code"] == code and r["consumed_at"] is None:
                    r["consumed_at"] = datetime.now(timezone.utc)
                    r["consumed_by_ip"] = ip
                    return _row(consumed_at=r["consumed_at"])
            return None
        if s.startswith("SELECT email_at_signup FROM sso_identities"):
            for r in self.identities:
                if r["sso_identity_id"] == args[0]:
                    return _row(email_at_signup=r["email_at_signup"])
            return None
        raise AssertionError(f"unhandled fetchrow: {s[:120]}")


def _make_app(conn: _FakeConn) -> FastAPI:
    from ai_orchestrator.routers import sso as sso_mod

    @asynccontextmanager
    async def fake_acquire(*_a, **_kw):
        yield conn

    class _FakePool:
        def acquire(self):
            return fake_acquire()

    sso_mod.get_pool = lambda: _FakePool()
    app = FastAPI()
    app.include_router(sso_mod.router)
    return app


# ═════════════════════════════════════════════════════════════════════
# 1. Mig 079 shape
# ═════════════════════════════════════════════════════════════════════


class TestMig083Shape:

    @pytest.fixture(scope="class")
    def mig(self) -> str:
        return (MIG_DIR / "083_sso_identities.sql").read_text(encoding="utf-8")

    def test_three_tables_present(self, mig):
        for t in ("sso_identities", "sso_oauth_state", "sso_exchange_codes"):
            assert f"CREATE TABLE IF NOT EXISTS {t}" in mig

    def test_unique_provider_sub(self, mig):
        assert "uq_sso_provider_sub" in mig
        assert "UNIQUE (provider, provider_sub)" in mig

    def test_provider_check(self, mig):
        assert "chk_sso_provider" in mig
        for p in ("google", "microsoft"):
            assert f"'{p}'" in mig

    def test_state_expires_after_created(self, mig):
        assert "chk_sso_state_expires_after_created" in mig

    def test_exchange_expires_after_created(self, mig):
        assert "chk_sso_exchange_expires_after_created" in mig

    def test_state_active_partial_index(self, mig):
        assert "idx_sso_state_active" in mig
        assert "WHERE consumed_at IS NULL" in mig

    def test_email_case_insensitive_index(self, mig):
        assert "idx_sso_email" in mig
        assert "lower(email_at_signup)" in mig


# ═════════════════════════════════════════════════════════════════════
# 2. Provider factory
# ═════════════════════════════════════════════════════════════════════


class TestProviderFactory:

    def test_unknown_provider_raises(self):
        with pytest.raises(UnknownProvider):
            get_provider("facebook")

    def test_google_not_configured(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        with pytest.raises(ProviderNotConfigured):
            get_provider("google")

    def test_microsoft_not_configured(self, monkeypatch):
        monkeypatch.delenv("MICROSOFT_CLIENT_ID", raising=False)
        monkeypatch.delenv("MICROSOFT_CLIENT_SECRET", raising=False)
        with pytest.raises(ProviderNotConfigured):
            get_provider("microsoft")

    def test_google_configured(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-test")
        p = get_provider("google")
        assert isinstance(p, GoogleProvider)
        assert p.client_id == "test-id.apps.googleusercontent.com"

    def test_registry_caches(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "x")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "y")
        p1 = get_provider("google")
        p2 = get_provider("google")
        assert p1 is p2


# ═════════════════════════════════════════════════════════════════════
# 3. Google provider
# ═════════════════════════════════════════════════════════════════════


class TestGoogleProvider:

    def test_authorize_url_contains_required_params(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        p = GoogleProvider.from_env()
        url = p.authorize_url(state="abc123")
        assert url.startswith("https://accounts.google.com/")
        assert "client_id=test-id" in url
        assert "state=abc123" in url
        assert "response_type=code" in url
        assert "scope=openid+email+profile" in url

    @pytest.mark.asyncio
    async def test_exchange_success(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        p = GoogleProvider.from_env()

        token_resp = MagicMock()
        token_resp.status_code = 200
        token_resp.json.return_value = {"access_token": "tok"}
        ui_resp = MagicMock()
        ui_resp.status_code = 200
        ui_resp.json.return_value = {
            "sub": "google-sub-123",
            "email": "user@example.com",
            "email_verified": True,
            "name": "Nguyen Test",
        }

        async def _post(_url, **_kw):
            return token_resp

        async def _get(_url, **_kw):
            return ui_resp

        client_ctx = MagicMock()
        client_ctx.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=token_resp),
            get=AsyncMock(return_value=ui_resp),
        ))
        client_ctx.__aexit__ = AsyncMock(return_value=False)

        with patch("httpx.AsyncClient", return_value=client_ctx):
            profile = await p.exchange_code_for_profile(code="abc")
        assert profile.provider == "google"
        assert profile.provider_sub == "google-sub-123"
        assert profile.email == "user@example.com"
        assert profile.email_verified is True

    @pytest.mark.asyncio
    async def test_token_exchange_400(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        p = GoogleProvider.from_env()

        bad_resp = MagicMock()
        bad_resp.status_code = 400
        bad_resp.text = "invalid_grant"
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=bad_resp),
        ))
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=ctx):
            with pytest.raises(OAuthExchangeError):
                await p.exchange_code_for_profile(code="bad")

    @pytest.mark.asyncio
    async def test_userinfo_missing_sub_raises(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        p = GoogleProvider.from_env()

        token_resp = MagicMock(status_code=200,
                               json=MagicMock(return_value={"access_token": "tok"}))
        ui_resp = MagicMock(status_code=200,
                            json=MagicMock(return_value={"email": "no-sub@example.com"}))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=token_resp),
            get=AsyncMock(return_value=ui_resp),
        ))
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=ctx):
            with pytest.raises(OAuthExchangeError):
                await p.exchange_code_for_profile(code="x")


# ═════════════════════════════════════════════════════════════════════
# 4. Microsoft provider
# ═════════════════════════════════════════════════════════════════════


class TestMicrosoftProvider:

    def test_authorize_url_uses_common_tenant(self, monkeypatch):
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "ms-id")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "ms-secret")
        monkeypatch.delenv("MICROSOFT_TENANT_ID", raising=False)
        p = MicrosoftProvider.from_env()
        url = p.authorize_url(state="s")
        assert "login.microsoftonline.com/common/oauth2/v2.0/authorize" in url
        assert "client_id=ms-id" in url
        assert "scope=openid+profile+email+offline_access" in url

    def test_authorize_url_uses_specific_tenant(self, monkeypatch):
        """MICROSOFT_TENANT_ID env routes auth to the tenant-specific
        authority instead of /common/."""
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "ms-id")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "ms-secret")
        monkeypatch.setenv("MICROSOFT_TENANT_ID",
                            "abc12345-6789-0000-0000-000000000000")
        p = MicrosoftProvider.from_env()
        url = p.authorize_url(state="s")
        assert ("login.microsoftonline.com/"
                "abc12345-6789-0000-0000-000000000000"
                "/oauth2/v2.0/authorize") in url
        assert "/common/" not in url

    def test_empty_tenant_id_falls_back_to_common(self, monkeypatch):
        """An empty-string env var should NOT produce
        login.microsoftonline.com//oauth2/... — em fall back to "common".
        """
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "ms-id")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "ms-secret")
        monkeypatch.setenv("MICROSOFT_TENANT_ID", "   ")  # whitespace
        p = MicrosoftProvider.from_env()
        assert p.tenant == "common"
        assert "/common/" in p.authorize_url(state="s")

    @pytest.mark.asyncio
    async def test_exchange_uses_oid_when_sub_missing(self, monkeypatch):
        monkeypatch.setenv("MICROSOFT_CLIENT_ID", "ms")
        monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "x")
        p = MicrosoftProvider.from_env()

        token_resp = MagicMock(status_code=200,
                               json=MagicMock(return_value={"access_token": "t"}))
        ui_resp = MagicMock(status_code=200,
                            json=MagicMock(return_value={
                                "oid": "ms-oid-1",
                                "email": "ms@user.com",
                                "name": "MS User",
                            }))
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=MagicMock(
            post=AsyncMock(return_value=token_resp),
            get=AsyncMock(return_value=ui_resp),
        ))
        ctx.__aexit__ = AsyncMock(return_value=False)
        with patch("httpx.AsyncClient", return_value=ctx):
            profile = await p.exchange_code_for_profile(code="c")
        assert profile.provider_sub == "ms-oid-1"
        assert profile.email_verified is True


# ═════════════════════════════════════════════════════════════════════
# 5. Router /start
# ═════════════════════════════════════════════════════════════════════


class TestStartEndpoint:

    def test_start_returns_authorize_url(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id.apps")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "GOCSPX-x")
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get("/p2/auth/sso/google/start",
                        params={"return_url": "http://localhost:3000/cb"})
        assert r.status_code == 200
        body = r.json()
        assert body["authorize_url"].startswith("https://accounts.google.com/")
        assert len(body["state"]) > 30
        assert len(conn.states) == 1
        assert conn.states[0]["return_url"] == "http://localhost:3000/cb"

    def test_start_unknown_provider_404(self, monkeypatch):
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get("/p2/auth/sso/facebook/start")
        assert r.status_code == 404

    def test_start_unconfigured_provider_503(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        monkeypatch.delenv("GOOGLE_CLIENT_SECRET", raising=False)
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get("/p2/auth/sso/google/start")
        assert r.status_code == 503


# ═════════════════════════════════════════════════════════════════════
# 6. Router /callback
# ═════════════════════════════════════════════════════════════════════


class TestCallbackEndpoint:

    def _seed_state(self, conn, *, state="state-xyz", provider="google",
                    return_url="http://localhost:3000/cb"):
        now = datetime.now(timezone.utc)
        conn.states.append({
            "state_token": state, "provider": provider,
            "return_url": return_url, "created_at": now,
            "expires_at": now + timedelta(seconds=600),
            "consumed_at": None,
        })

    def _seed_user(self, conn, email="user@example.com"):
        conn.users.append({
            "user_id": USR, "enterprise_id": ENT, "email": email,
        })

    def _patch_google_exchange(self, profile_kw):
        return patch(
            "ai_orchestrator.shared.sso_providers.google.GoogleProvider.exchange_code_for_profile",
            new=AsyncMock(return_value=SSOProfile(
                provider="google",
                provider_sub="sub-123",
                email=profile_kw.get("email", "user@example.com"),
                email_verified=profile_kw.get("email_verified", True),
                name="Nguyen",
                raw_profile={},
            )),
        )

    def test_callback_redirects_with_sso_code(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = _FakeConn()
        self._seed_state(conn)
        self._seed_user(conn)
        app = _make_app(conn)
        client = TestClient(app)

        with self._patch_google_exchange({}):
            r = client.get(
                "/p2/auth/sso/google/callback",
                params={"code": "auth-code", "state": "state-xyz"},
                follow_redirects=False,
            )
        assert r.status_code == 302
        assert "sso_code=" in r.headers["location"]
        assert len(conn.exchanges) == 1
        assert len(conn.identities) == 1

    def test_callback_unknown_state_400(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = _FakeConn()
        self._seed_user(conn)
        app = _make_app(conn)
        client = TestClient(app)
        with self._patch_google_exchange({}):
            r = client.get(
                "/p2/auth/sso/google/callback",
                params={"code": "c", "state": "never-issued"},
            )
        assert r.status_code == 400

    def test_callback_state_replay_410(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = _FakeConn()
        self._seed_state(conn)
        # Mark already consumed
        conn.states[0]["consumed_at"] = datetime.now(timezone.utc)
        self._seed_user(conn)
        app = _make_app(conn)
        client = TestClient(app)
        with self._patch_google_exchange({}):
            r = client.get(
                "/p2/auth/sso/google/callback",
                params={"code": "c", "state": "state-xyz"},
            )
        assert r.status_code == 410

    def test_callback_unverified_email_403(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = _FakeConn()
        self._seed_state(conn)
        self._seed_user(conn)
        app = _make_app(conn)
        client = TestClient(app)
        with self._patch_google_exchange({"email_verified": False}):
            r = client.get(
                "/p2/auth/sso/google/callback",
                params={"code": "c", "state": "state-xyz"},
            )
        assert r.status_code == 403

    def test_callback_no_matching_user_403(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = _FakeConn()
        self._seed_state(conn)
        # No user with that email
        app = _make_app(conn)
        client = TestClient(app)
        with self._patch_google_exchange({"email": "stranger@x.com"}):
            r = client.get(
                "/p2/auth/sso/google/callback",
                params={"code": "c", "state": "state-xyz"},
            )
        assert r.status_code == 403
        assert "registered enterprise" in r.text.lower() or \
               "invite" in r.text.lower()

    def test_callback_provider_error_400(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        conn = _FakeConn()
        self._seed_state(conn)
        app = _make_app(conn)
        client = TestClient(app)
        r = client.get(
            "/p2/auth/sso/google/callback",
            params={"error": "access_denied", "state": "state-xyz"},
        )
        assert r.status_code == 400


# ═════════════════════════════════════════════════════════════════════
# 7. Router /exchange-info
# ═════════════════════════════════════════════════════════════════════


class TestExchangeInfoEndpoint:

    def _seed_exchange(self, conn, code="exch-code"):
        now = datetime.now(timezone.utc)
        sid = uuid4()
        conn.identities.append({
            "sso_identity_id": sid, "enterprise_id": ENT, "user_id": USR,
            "provider": "google", "provider_sub": "s1",
            "email_at_signup": "user@example.com", "name_at_signup": "U",
            "raw_profile": "{}", "first_seen_at": now, "last_seen_at": now,
        })
        conn.exchanges.append({
            "code": code, "enterprise_id": ENT, "user_id": USR,
            "sso_identity_id": sid, "provider": "google",
            "created_at": now, "expires_at": now + timedelta(seconds=60),
            "consumed_at": None, "consumed_by_ip": None,
        })
        return sid

    def test_exchange_missing_token_503(self, monkeypatch):
        monkeypatch.delenv("KAORI_INTERNAL_SVC_TOKEN", raising=False)
        conn = _FakeConn()
        self._seed_exchange(conn)
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post(
            "/p2/auth/sso/exchange-info",
            json={"sso_code": "exch-code"},
        )
        assert r.status_code == 503

    def test_exchange_bad_token_401(self, monkeypatch):
        monkeypatch.setenv("KAORI_INTERNAL_SVC_TOKEN", "expected")
        conn = _FakeConn()
        self._seed_exchange(conn)
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post(
            "/p2/auth/sso/exchange-info",
            headers={"X-Internal-Service-Token": "wrong"},
            json={"sso_code": "exch-code"},
        )
        assert r.status_code == 401

    def test_exchange_success(self, monkeypatch):
        monkeypatch.setenv("KAORI_INTERNAL_SVC_TOKEN", "secret")
        conn = _FakeConn()
        self._seed_exchange(conn)
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post(
            "/p2/auth/sso/exchange-info",
            headers={"X-Internal-Service-Token": "secret"},
            json={"sso_code": "exch-code"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["enterprise_id"] == str(ENT)
        assert body["user_id"] == str(USR)
        assert body["email"] == "user@example.com"

    def test_exchange_replay_410(self, monkeypatch):
        monkeypatch.setenv("KAORI_INTERNAL_SVC_TOKEN", "secret")
        conn = _FakeConn()
        self._seed_exchange(conn)
        app = _make_app(conn)
        client = TestClient(app)
        # First call consumes
        client.post(
            "/p2/auth/sso/exchange-info",
            headers={"X-Internal-Service-Token": "secret"},
            json={"sso_code": "exch-code"},
        )
        # Second call should 410
        r = client.post(
            "/p2/auth/sso/exchange-info",
            headers={"X-Internal-Service-Token": "secret"},
            json={"sso_code": "exch-code"},
        )
        assert r.status_code == 410

    def test_exchange_unknown_code_404(self, monkeypatch):
        monkeypatch.setenv("KAORI_INTERNAL_SVC_TOKEN", "secret")
        conn = _FakeConn()
        app = _make_app(conn)
        client = TestClient(app)
        r = client.post(
            "/p2/auth/sso/exchange-info",
            headers={"X-Internal-Service-Token": "secret"},
            json={"sso_code": "never-issued"},
        )
        assert r.status_code == 404


# ═════════════════════════════════════════════════════════════════════
# 8. End-to-end integration
# ═════════════════════════════════════════════════════════════════════


class TestEndToEnd:

    def test_start_then_callback_then_exchange(self, monkeypatch):
        """Full life: /start → consume URL → /callback (with mocked
        Google exchange) → /exchange-info → matched user."""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")
        monkeypatch.setenv("KAORI_INTERNAL_SVC_TOKEN", "svc-token")
        conn = _FakeConn()
        conn.users.append({
            "user_id": USR, "enterprise_id": ENT,
            "email": "user@example.com",
        })
        app = _make_app(conn)
        client = TestClient(app)

        # 1. /start
        r = client.get("/p2/auth/sso/google/start",
                        params={"return_url": "http://app/cb"})
        state = r.json()["state"]

        # 2. /callback
        with patch(
            "ai_orchestrator.shared.sso_providers.google.GoogleProvider.exchange_code_for_profile",
            new=AsyncMock(return_value=SSOProfile(
                provider="google", provider_sub="s",
                email="user@example.com", email_verified=True,
                name="N", raw_profile={},
            )),
        ):
            r = client.get(
                "/p2/auth/sso/google/callback",
                params={"code": "auth", "state": state},
                follow_redirects=False,
            )
        assert r.status_code == 302
        loc = r.headers["location"]
        sso_code = loc.split("sso_code=")[1]

        # 3. /exchange-info (auth-service Java side calls this)
        r = client.post(
            "/p2/auth/sso/exchange-info",
            headers={"X-Internal-Service-Token": "svc-token"},
            json={"sso_code": sso_code},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["user_id"] == str(USR)
        assert body["enterprise_id"] == str(ENT)
        assert body["provider"] == "google"
