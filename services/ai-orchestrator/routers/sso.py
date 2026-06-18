"""
P2-AUTH-001 SSO endpoints — Google + Microsoft OAuth 2.0.

Endpoints (mounted under /p2/auth/sso)
---------------------------------------
GET   /p2/auth/sso/{provider}/start
        Issue state token, return authorization URL. FE redirects
        browser to that URL.

GET   /p2/auth/sso/{provider}/callback
        Verify state, exchange code, lookup/create user, issue
        one-shot exchange code, redirect browser to FE return URL with
        ?sso_code=... query param.

POST  /p2/auth/sso/exchange-info  (INTERNAL)
        Called by auth-service Java to swap an sso_code for the
        underlying matched user. Caller MUST supply
        X-Internal-Service-Token header (cross-service trust, K-12).
        Returns user_id + enterprise_id + sso_identity_id; marks the
        code consumed.

Provider matrix
---------------
- google     : production-ready; needs GOOGLE_CLIENT_ID + SECRET
- microsoft  : code complete, inactive until MICROSOFT_CLIENT_ID + SECRET land

Java auth-service contract (TO BUILD)
-------------------------------------
Once FE redirects to its callback page with ?sso_code=<X>, FE POSTs:

    POST {auth-service}/api/v1/auth/sso/exchange
    Body: { "sso_code": "<X>" }

Internal flow:
    1. auth-service hits POST /p2/auth/sso/exchange-info on ai-orchestrator
       with X-Internal-Service-Token = (shared secret KAORI_INTERNAL_SVC_TOKEN)
       and body { "sso_code": "<X>" }
    2. ai-orchestrator validates code + returns matched user_id +
       enterprise_id + sso_identity_id; marks consumed.
    3. auth-service loads the user, generates RS256 JWT, returns to FE.
    4. FE stores the JWT and proceeds as if password login.

This split keeps RS256 private-key access inside auth-service per the
existing security boundary.
"""
from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from ..shared.db import acquire_for_tenant, get_pool
from ..shared.sso_providers import (
    OAuthExchangeError,
    ProviderNotConfigured,
    UnknownProvider,
    get_provider,
)

log = structlog.get_logger()

router = APIRouter(prefix="/p2/auth/sso", tags=["SSO"])


_STATE_TTL_SECONDS    = 600   # 10 minutes
_EXCHANGE_TTL_SECONDS = 60    # 1 minute


# ─── Helpers ─────────────────────────────────────────────────────────


def _new_token(n_bytes: int = 32) -> str:
    return secrets.token_urlsafe(n_bytes)


def _internal_token() -> Optional[str]:
    return os.getenv("KAORI_INTERNAL_SVC_TOKEN")


async def _store_state(conn, provider: str, state: str, return_url: Optional[str]) -> None:
    now = datetime.now(timezone.utc)
    await conn.execute(
        """INSERT INTO sso_oauth_state
               (state_token, provider, return_url, created_at, expires_at)
           VALUES ($1, $2, $3, $4, $5)""",
        state, provider, return_url, now,
        now + timedelta(seconds=_STATE_TTL_SECONDS),
    )


async def _consume_state(conn, state: str, provider: str) -> dict:
    row = await conn.fetchrow(
        """SELECT provider, return_url, expires_at, consumed_at
           FROM sso_oauth_state
           WHERE state_token = $1""",
        state,
    )
    if row is None:
        raise HTTPException(status_code=400, detail="Unknown state token")
    if row["provider"] != provider:
        raise HTTPException(status_code=400, detail="State / provider mismatch")
    if row["consumed_at"] is not None:
        raise HTTPException(status_code=410, detail="State already consumed (replay)")
    if row["expires_at"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="State expired")
    await conn.execute(
        """UPDATE sso_oauth_state SET consumed_at = NOW()
           WHERE state_token = $1""",
        state,
    )
    return {"return_url": row["return_url"]}


async def _find_user_by_email(conn, email: str) -> Optional[dict]:
    """Match a verified email to an existing enterprise_users row.
    Case-insensitive. Returns dict(user_id, enterprise_id) or None."""
    row = await conn.fetchrow(
        """SELECT user_id, enterprise_id
           FROM enterprise_users
           WHERE lower(email) = lower($1)
           LIMIT 1""",
        email,
    )
    return dict(row) if row else None


async def _upsert_sso_identity(
    conn,
    *,
    enterprise_id: UUID,
    user_id: UUID,
    provider: str,
    profile,
) -> UUID:
    """Insert or update the sso_identities row for this (provider, sub).
    Returns the sso_identity_id."""
    import json
    row = await conn.fetchrow(
        """INSERT INTO sso_identities
               (enterprise_id, user_id, provider, provider_sub,
                email_at_signup, name_at_signup, raw_profile)
           VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb)
           ON CONFLICT (provider, provider_sub) DO UPDATE SET
               last_seen_at    = NOW(),
               email_at_signup = EXCLUDED.email_at_signup,
               name_at_signup  = EXCLUDED.name_at_signup,
               raw_profile     = EXCLUDED.raw_profile
           RETURNING sso_identity_id""",
        enterprise_id, user_id, provider, profile.provider_sub,
        profile.email, profile.name, json.dumps(profile.raw_profile),
    )
    return row["sso_identity_id"]


async def _issue_exchange_code(
    conn,
    *,
    enterprise_id: UUID,
    user_id: UUID,
    sso_identity_id: UUID,
    provider: str,
) -> str:
    code = _new_token(48)
    now = datetime.now(timezone.utc)
    await conn.execute(
        """INSERT INTO sso_exchange_codes
               (code, enterprise_id, user_id, sso_identity_id,
                provider, created_at, expires_at)
           VALUES ($1, $2, $3, $4, $5, $6, $7)""",
        code, enterprise_id, user_id, sso_identity_id, provider, now,
        now + timedelta(seconds=_EXCHANGE_TTL_SECONDS),
    )
    return code


# ─── Endpoints ───────────────────────────────────────────────────────


class StartResponse(BaseModel):
    authorize_url: str
    state:         str


@router.get("/{provider}/start", response_model=StartResponse)
async def sso_start(
    provider: str,
    return_url: Optional[str] = Query(default=None),
):
    """Issue a state token and return the provider's authorization URL.
    FE redirects the browser there next.

    Pre-auth endpoint — no tenant header required (we don't know which
    enterprise the user belongs to until callback resolves the email).
    """
    try:
        prov = get_provider(provider)
    except UnknownProvider as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProviderNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))

    state = _new_token()
    pool = get_pool()
    async with pool.acquire() as conn:
        await _store_state(conn, provider, state, return_url)

    url = prov.authorize_url(state=state)
    log.info("sso.start", provider=provider, state=state[:8] + "...",
             return_url=return_url)
    return StartResponse(authorize_url=url, state=state)


@router.get("/{provider}/callback")
async def sso_callback(
    provider: str,
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
):
    """Handle the provider's redirect after user authorization.

    Validates state (CSRF), exchanges code for userinfo, matches by
    email to an enterprise_users row, persists/refreshes the sso_identity,
    issues a one-shot exchange code, redirects the browser to
    return_url with ?sso_code=<code>.

    Browser flow → FE picks up sso_code → POSTs to auth-service
    /auth/sso/exchange (Java side TO BUILD) → gets JWT.
    """
    if error:
        log.warning("sso.callback.provider_error",
                    provider=provider, error=error)
        raise HTTPException(status_code=400,
                            detail=f"Provider returned error: {error}")
    if not code or not state:
        raise HTTPException(status_code=400,
                            detail="Missing code or state in callback")

    try:
        prov = get_provider(provider)
    except UnknownProvider as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ProviderNotConfigured as e:
        raise HTTPException(status_code=503, detail=str(e))

    pool = get_pool()
    async with pool.acquire() as conn:
        state_info = await _consume_state(conn, state, provider)

    try:
        profile = await prov.exchange_code_for_profile(code=code)
    except OAuthExchangeError as e:
        log.error("sso.callback.exchange_failed",
                  provider=provider, error=str(e))
        raise HTTPException(status_code=502, detail=str(e))

    if not profile.email_verified:
        raise HTTPException(
            status_code=403,
            detail=f"{provider} email '{profile.email}' is not verified",
        )

    pool = get_pool()
    async with pool.acquire() as conn:
        match = await _find_user_by_email(conn, profile.email)
        if match is None:
            log.warning("sso.callback.no_match", email=profile.email)
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Email '{profile.email}' is not a registered enterprise "
                    "user. Ask your admin to invite you first."
                ),
            )

        enterprise_id = match["enterprise_id"]
        user_id       = match["user_id"]
        sso_identity_id = await _upsert_sso_identity(
            conn,
            enterprise_id=enterprise_id,
            user_id=user_id,
            provider=provider,
            profile=profile,
        )
        sso_code = await _issue_exchange_code(
            conn,
            enterprise_id=enterprise_id,
            user_id=user_id,
            sso_identity_id=sso_identity_id,
            provider=provider,
        )

    log.info("sso.callback.success",
             provider=provider,
             enterprise_id=str(enterprise_id),
             user_id=str(user_id))

    target = state_info.get("return_url") or "/"
    sep = "&" if "?" in target else "?"
    return RedirectResponse(
        url=f"{target}{sep}sso_code={sso_code}",
        status_code=302,
    )


class ExchangeRequest(BaseModel):
    sso_code: str


class ExchangeResponse(BaseModel):
    enterprise_id:   UUID
    user_id:         UUID
    sso_identity_id: UUID
    provider:        str
    email:           str
    consumed_at:     datetime


@router.post("/exchange-info", response_model=ExchangeResponse)
async def sso_exchange_info(
    body: ExchangeRequest,
    request: Request,
    x_internal_service_token: Optional[str] = Header(
        None, alias="X-Internal-Service-Token",
    ),
):
    """INTERNAL — auth-service Java side calls this to translate an
    sso_code into the matched user, then mints a real JWT and returns
    it to the FE.

    Requires X-Internal-Service-Token == KAORI_INTERNAL_SVC_TOKEN env
    var. The token is a shared secret between the two services; rotate
    via Vault path `platform/auth/internal_service_token` Phase 2.5+.
    """
    expected = _internal_token()
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=(
                "KAORI_INTERNAL_SVC_TOKEN env var not set; SSO exchange "
                "endpoint disabled until configured"
            ),
        )
    if x_internal_service_token != expected:
        log.warning("sso.exchange.bad_token",
                    src_ip=request.client.host if request.client else "?")
        raise HTTPException(status_code=401, detail="Bad internal service token")

    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT enterprise_id, user_id, sso_identity_id, provider,
                      expires_at, consumed_at
               FROM sso_exchange_codes
               WHERE code = $1""",
            body.sso_code,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="Unknown exchange code")
        if row["consumed_at"] is not None:
            raise HTTPException(status_code=410, detail="Exchange code already consumed")
        if row["expires_at"] < datetime.now(timezone.utc):
            raise HTTPException(status_code=410, detail="Exchange code expired")

        ip = (request.client.host if request.client else None)
        consumed = await conn.fetchrow(
            """UPDATE sso_exchange_codes
               SET consumed_at = NOW(), consumed_by_ip = $2
               WHERE code = $1 AND consumed_at IS NULL
               RETURNING consumed_at""",
            body.sso_code, ip,
        )
        if consumed is None:
            # Race lost — another caller consumed in between
            raise HTTPException(status_code=410,
                                detail="Exchange code already consumed (race)")

        identity = await conn.fetchrow(
            """SELECT email_at_signup
               FROM sso_identities WHERE sso_identity_id = $1""",
            row["sso_identity_id"],
        )

    log.info("sso.exchange.success",
             provider=row["provider"],
             user_id=str(row["user_id"]),
             enterprise_id=str(row["enterprise_id"]))
    return ExchangeResponse(
        enterprise_id=row["enterprise_id"],
        user_id=row["user_id"],
        sso_identity_id=row["sso_identity_id"],
        provider=row["provider"],
        email=identity["email_at_signup"] if identity else "",
        consumed_at=consumed["consumed_at"],
    )
