"""
P2-AUTH-001 Google OAuth 2.0 provider adapter.

Authorization URL: https://accounts.google.com/o/oauth2/v2/auth
Token URL:         https://oauth2.googleapis.com/token
Userinfo URL:      https://openidconnect.googleapis.com/v1/userinfo

Scopes (must match Google Cloud Console Data Access config):
  - openid
  - https://www.googleapis.com/auth/userinfo.email
  - https://www.googleapis.com/auth/userinfo.profile

Env vars:
  GOOGLE_CLIENT_ID       — OAuth client ID (.apps.googleusercontent.com)
  GOOGLE_CLIENT_SECRET   — OAuth client secret (GOCSPX-...)
  GOOGLE_REDIRECT_URI    — registered redirect URI; defaults to
                            http://localhost:8080/api/v1/p2/auth/sso/google/callback
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import httpx
import structlog

from .base import (
    OAuthExchangeError,
    ProviderNotConfigured,
    SSOProfile,
    SSOProvider,
)

log = structlog.get_logger()


_AUTH_URL     = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL    = "https://oauth2.googleapis.com/token"
_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
_DEFAULT_REDIRECT = (
    "http://localhost:8080/api/v1/p2/auth/sso/google/callback"
)
_SCOPES = "openid email profile"


class GoogleProvider(SSOProvider):
    name = "google"

    @classmethod
    def from_env(cls) -> "GoogleProvider":
        client_id     = os.getenv("GOOGLE_CLIENT_ID", "").strip()
        client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
        redirect_uri  = os.getenv("GOOGLE_REDIRECT_URI", _DEFAULT_REDIRECT).strip()
        if not client_id or not client_secret:
            raise ProviderNotConfigured(
                "GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET env vars not set"
            )
        return cls(client_id=client_id,
                   client_secret=client_secret,
                   redirect_uri=redirect_uri)

    def authorize_url(self, *, state: str) -> str:
        params = {
            "client_id":     self.client_id,
            "redirect_uri":  self.redirect_uri,
            "response_type": "code",
            "scope":         _SCOPES,
            "access_type":   "offline",     # ask for refresh token
            "prompt":        "select_account",
            "state":         state,
        }
        return f"{_AUTH_URL}?{urlencode(params)}"

    async def exchange_code_for_profile(self, *, code: str) -> SSOProfile:
        token_payload = {
            "code":          code,
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri":  self.redirect_uri,
            "grant_type":    "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                tok_resp = await client.post(_TOKEN_URL, data=token_payload)
        except httpx.HTTPError as e:
            raise OAuthExchangeError(f"Google token exchange network error: {e}") from e
        if tok_resp.status_code != 200:
            raise OAuthExchangeError(
                f"Google token exchange failed ({tok_resp.status_code}): "
                f"{tok_resp.text[:200]}"
            )
        try:
            tok_body = tok_resp.json()
        except Exception as e:   # noqa: BLE001
            raise OAuthExchangeError(f"Google token response not JSON: {e}") from e
        access_token = tok_body.get("access_token")
        if not access_token:
            raise OAuthExchangeError(
                f"Google token response missing access_token; got keys "
                f"{sorted(tok_body.keys())}"
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                ui_resp = await client.get(
                    _USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as e:
            raise OAuthExchangeError(f"Google userinfo network error: {e}") from e
        if ui_resp.status_code != 200:
            raise OAuthExchangeError(
                f"Google userinfo failed ({ui_resp.status_code}): "
                f"{ui_resp.text[:200]}"
            )
        try:
            profile = ui_resp.json()
        except Exception as e:   # noqa: BLE001
            raise OAuthExchangeError(f"Google userinfo not JSON: {e}") from e

        sub = profile.get("sub")
        email = profile.get("email")
        if not sub or not email:
            raise OAuthExchangeError(
                f"Google userinfo missing sub/email; got keys {sorted(profile.keys())}"
            )
        return SSOProfile(
            provider="google",
            provider_sub=str(sub),
            email=str(email),
            email_verified=bool(profile.get("email_verified", False)),
            name=profile.get("name"),
            raw_profile=profile,
        )
