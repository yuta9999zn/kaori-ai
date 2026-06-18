"""
P2-AUTH-001 Microsoft Entra ID OAuth 2.0 adapter.

Microsoft identity platform v2.0 endpoints (multi-tenant `common`):
  Auth:     https://login.microsoftonline.com/common/oauth2/v2.0/authorize
  Token:    https://login.microsoftonline.com/common/oauth2/v2.0/token
  Userinfo: https://graph.microsoft.com/oidc/userinfo

Scopes:
  - openid
  - profile
  - email
  - offline_access

Activation
----------
Adapter is fully implemented but inactive until anh provisions a
Microsoft Entra ID tenant (M365 Developer Program — free) and sets
MICROSOFT_CLIENT_ID + MICROSOFT_CLIENT_SECRET env vars. Without them,
from_env() raises ProviderNotConfigured and the router returns 503
"SSO provider not configured" for /sso/microsoft/* requests. Once
the env vars land, no code change needed.
"""
from __future__ import annotations

import os
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


_USERINFO_URL = "https://graph.microsoft.com/oidc/userinfo"
_DEFAULT_REDIRECT = (
    "http://localhost:8080/api/v1/p2/auth/sso/microsoft/callback"
)
_SCOPES = "openid profile email offline_access"


def _authority_for(tenant: str) -> tuple[str, str]:
    """Build (auth_url, token_url) for the configured tenant.

    `tenant` is one of:
      - "common"                           — multi-tenant (default): accepts
                                              tokens from ANY Entra ID tenant
                                              + personal Microsoft accounts
      - "<GUID>" (e.g. "abc-123-...")      — single-tenant: only accepts
                                              tokens from that specific tenant
      - "organizations"                    — work/school accounts only
                                              (excludes personal)
      - "consumers"                        — personal Microsoft accounts only

    For Kaori dev we default to "common" so anh's M365 Dev Program tenant
    AND any customer's Entra ID work without rebinding. Set
    MICROSOFT_TENANT_ID env to a specific GUID if you want to restrict.
    """
    base = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0"
    return f"{base}/authorize", f"{base}/token"


class MicrosoftProvider(SSOProvider):
    name = "microsoft"

    def __init__(self, client_id: str, client_secret: str,
                 redirect_uri: str, tenant: str = "common"):
        super().__init__(client_id=client_id,
                         client_secret=client_secret,
                         redirect_uri=redirect_uri)
        self.tenant = tenant
        self.auth_url, self.token_url = _authority_for(tenant)

    @classmethod
    def from_env(cls) -> "MicrosoftProvider":
        client_id     = os.getenv("MICROSOFT_CLIENT_ID", "").strip()
        client_secret = os.getenv("MICROSOFT_CLIENT_SECRET", "").strip()
        redirect_uri  = os.getenv("MICROSOFT_REDIRECT_URI", _DEFAULT_REDIRECT).strip()
        # MICROSOFT_TENANT_ID is optional. If unset, em multi-tenant via
        # the "common" authority; if set to a GUID, em restrict to that
        # tenant only. For dev with M365 Developer Program, leave unset.
        tenant        = os.getenv("MICROSOFT_TENANT_ID", "common").strip() or "common"
        if not client_id or not client_secret:
            raise ProviderNotConfigured(
                "MICROSOFT_CLIENT_ID / MICROSOFT_CLIENT_SECRET env vars not set"
            )
        return cls(client_id=client_id,
                   client_secret=client_secret,
                   redirect_uri=redirect_uri,
                   tenant=tenant)

    def authorize_url(self, *, state: str) -> str:
        params = {
            "client_id":     self.client_id,
            "redirect_uri":  self.redirect_uri,
            "response_type": "code",
            "scope":         _SCOPES,
            "response_mode": "query",
            "prompt":        "select_account",
            "state":         state,
        }
        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code_for_profile(self, *, code: str) -> SSOProfile:
        token_payload = {
            "code":          code,
            "client_id":     self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri":  self.redirect_uri,
            "grant_type":    "authorization_code",
            "scope":         _SCOPES,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                tok_resp = await client.post(self.token_url, data=token_payload)
        except httpx.HTTPError as e:
            raise OAuthExchangeError(f"Microsoft token exchange network error: {e}") from e
        if tok_resp.status_code != 200:
            raise OAuthExchangeError(
                f"Microsoft token exchange failed ({tok_resp.status_code}): "
                f"{tok_resp.text[:200]}"
            )
        try:
            tok_body = tok_resp.json()
        except Exception as e:   # noqa: BLE001
            raise OAuthExchangeError(f"Microsoft token response not JSON: {e}") from e
        access_token = tok_body.get("access_token")
        if not access_token:
            raise OAuthExchangeError(
                f"Microsoft token response missing access_token; got keys "
                f"{sorted(tok_body.keys())}"
            )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                ui_resp = await client.get(
                    _USERINFO_URL,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.HTTPError as e:
            raise OAuthExchangeError(f"Microsoft userinfo network error: {e}") from e
        if ui_resp.status_code != 200:
            raise OAuthExchangeError(
                f"Microsoft userinfo failed ({ui_resp.status_code}): "
                f"{ui_resp.text[:200]}"
            )
        try:
            profile = ui_resp.json()
        except Exception as e:   # noqa: BLE001
            raise OAuthExchangeError(f"Microsoft userinfo not JSON: {e}") from e

        sub = profile.get("sub") or profile.get("oid")
        email = (profile.get("email") or
                 profile.get("preferred_username") or
                 profile.get("upn"))
        if not sub or not email:
            raise OAuthExchangeError(
                f"Microsoft userinfo missing sub/email; got keys {sorted(profile.keys())}"
            )
        return SSOProfile(
            provider="microsoft",
            provider_sub=str(sub),
            email=str(email),
            email_verified=True,   # Entra-issued tokens are pre-verified
            name=profile.get("name"),
            raw_profile=profile,
        )
