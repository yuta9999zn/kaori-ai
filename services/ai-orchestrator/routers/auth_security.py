"""
P2-S25 D2 + D3 — enterprise auth security endpoints.

Endpoints (mounted under /p2/auth)
----------------------------------
MFA (P2-AUTH-002):
    POST   /p2/auth/mfa/enroll          generate secret + return QR otpauth_url
    POST   /p2/auth/mfa/verify          verify code → enabled=TRUE (first time)
    GET    /p2/auth/mfa/status          check enrollment state
    POST   /p2/auth/mfa/backup-codes    regenerate 10 codes
    DELETE /p2/auth/mfa                 disable MFA (requires recent verify)

Field encryption (P2-ENC-001):
    POST   /p2/auth/field-key/rotate    rotate tenant's encryption key
    GET    /p2/auth/field-key/status    current key version + rotated_at

K-rules
-------
K-1 / K-12: user_id from X-User-ID, tenant from X-Enterprise-ID — never body.
K-5: TOTP secrets encrypted at rest with platform master key
     (KAORI_MFA_KEY env). Tenant field keys are SEPARATE — encrypted
     per-tenant via Vault.
K-18: production keys live in Vault; dev profile uses env var fallback.
"""
from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from ..shared.crypto import generate_key_b64
from ..shared.db import acquire_for_tenant
from ..shared.field_key_rotation import reencrypt_tenant
from ..shared.totp import (
    decrypt_secret,
    encrypt_secret,
    generate_backup_codes,
    generate_secret,
    hash_backup_code,
    otpauth_url,
    verify_totp,
)

log = structlog.get_logger()

router = APIRouter(prefix="/p2/auth")


# ─── Master key resolution ───────────────────────────────────────────


_MFA_VAULT_PATH = "platform/encryption/mfa_master_key"


def _platform_mfa_master_key() -> bytes:
    """Load the platform-wide AES-256 key used to encrypt MFA secrets
    at rest. K-18 — production resolves via Vault at
    `platform/encryption/mfa_master_key` (expects {"key": "<b64>"});
    dev/staging fall back to KAORI_MFA_KEY env var with a warning.

    Phase 1 callsites didn't change shape — this is a swap-in.
    """
    is_prod = os.getenv("KAORI_PROFILE", "dev") in ("production", "prod")
    key_b64: Optional[str] = None

    # 1. Vault first
    try:
        from ..shared.kaori_vault import VaultError, get_default_client
        client = get_default_client()
        data = client.read_sync(_MFA_VAULT_PATH)
        if "key" not in data:
            raise VaultError(
                f"Vault path '{_MFA_VAULT_PATH}' missing 'key' field"
            )
        key_b64 = str(data["key"])
        log.info("auth.mfa_master_key.from_vault", path=_MFA_VAULT_PATH)
    except Exception as e:  # noqa: BLE001
        if is_prod:
            raise HTTPException(
                status_code=500,
                detail=(
                    f"K-18: production requires Vault path "
                    f"'{_MFA_VAULT_PATH}' to resolve MFA master key. "
                    f"Vault error: {e}"
                ),
            ) from e
        # Non-prod: log + env fallback
        log.warning("auth.mfa_master_key.vault_fallback",
                    error=str(e),
                    note="dev profile — falling back to KAORI_MFA_KEY env")
        raw = os.getenv("KAORI_MFA_KEY")
        if not raw:
            raise HTTPException(
                status_code=500,
                detail="KAORI_MFA_KEY env var not configured (and Vault unavailable)",
            ) from e
        key_b64 = raw

    try:
        key = base64.b64decode(key_b64)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail=f"MFA master key decode failed: {e}",
        ) from e
    if len(key) != 32:
        raise HTTPException(
            status_code=500,
            detail=f"MFA master key must decode to 32 bytes; got {len(key)}",
        )
    return key


# ─── K-13 idempotency helpers (Phase 2.9 closeout) ────────────────────


async def _idempotency_short_circuit(
    enterprise_id: UUID,
    idempotency_key: Optional[str],
    side_effect_class: str = "write_non_idempotent",
) -> Optional[dict]:
    """Return cached response_payload dict if duplicate Idempotency-Key,
    else None. MFA enroll = write_non_idempotent because re-enroll
    overwrites secret + drops backup codes — replay must be rejected.

    Guard: when caller invokes the handler directly (not via FastAPI
    HTTP route), the parameter receives the Header() default object
    instead of None — isinstance check rules that out.
    """
    if not isinstance(idempotency_key, str) or not idempotency_key:
        return None
    from ..workflow_runtime.idempotency_store import get_or_set
    hit = await get_or_set(
        enterprise_id=enterprise_id, key=idempotency_key,
        side_effect_class=side_effect_class, ttl_seconds=86_400,
    )
    return hit.response_payload if hit.cached else None


async def _record_idempotency_outcome(
    enterprise_id: UUID,
    idempotency_key: Optional[str],
    response: dict,
) -> None:
    if not isinstance(idempotency_key, str) or not idempotency_key:
        return
    from ..workflow_runtime.idempotency_store import record_outcome
    await record_outcome(
        enterprise_id=enterprise_id, key=idempotency_key,
        response_payload=response,
    )


# ─── MFA endpoints ───────────────────────────────────────────────────


class MFAEnrollOut(BaseModel):
    secret_b32:        str
    otpauth_url:       str
    backup_codes:      list[str] = Field(..., description="Show ONCE; user records.")
    enrolled:          bool = False
    qr_payload_size:   int


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10,
                      description="6-digit TOTP code OR a backup code (10 chars).")


class MFAStatusOut(BaseModel):
    enabled:                 bool
    enrolled:                bool
    enrolled_at:             Optional[datetime]
    last_verified_at:        Optional[datetime]
    backup_codes_remaining:  int


class MFAVerifyOut(BaseModel):
    verified:                bool
    enabled_after:           bool
    used_backup_code:        bool
    backup_codes_remaining:  int


@router.post("/mfa/enroll", response_model=MFAEnrollOut, status_code=201)
async def enroll_mfa(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       UUID = Header(..., alias="X-User-ID"),
    x_user_email:    Optional[str] = Header(None, alias="X-User-Email"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Generate a fresh TOTP secret + 10 backup codes. Stores
    encrypted secret + hashed codes; returns the secret (base32 +
    otpauth URL) and PLAINTEXT codes so the user can save them.

    Re-enroll overwrites existing secret. enabled flips back to FALSE
    until /verify succeeds.

    K-13: HIGH severity — double-enroll overwrites secret + drops
    backup codes. Idempotency-Key header returns the original
    enrollment payload (with the same secret + codes the caller
    already saved) instead of generating a fresh one. Cached 24h.
    """
    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return MFAEnrollOut(**cached)

    master = _platform_mfa_master_key()
    secret = generate_secret()
    secret_enc = encrypt_secret(secret, master)
    codes = generate_backup_codes(count=10)
    hashed = [hash_backup_code(c) for c in codes]

    issuer = "Kaori AI"
    label = x_user_email or str(x_user_id)
    uri = otpauth_url(issuer=issuer, account_label=label, secret=secret)
    b32 = uri.split("secret=")[1].split("&")[0]

    async with acquire_for_tenant(x_enterprise_id) as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO mfa_secrets
                       (user_id, enterprise_id, secret_enc, enabled,
                        enrolled_at, backup_codes_remaining)
                   VALUES ($1, $2, $3, FALSE, NOW(), $4)
                   ON CONFLICT (user_id) DO UPDATE SET
                       secret_enc             = EXCLUDED.secret_enc,
                       enabled                = FALSE,
                       enrolled_at            = EXCLUDED.enrolled_at,
                       backup_codes_remaining = EXCLUDED.backup_codes_remaining,
                       updated_at             = NOW()""",
                x_user_id, x_enterprise_id, secret_enc, len(codes),
            )
            # Drop any prior backup codes
            await conn.execute(
                "DELETE FROM mfa_backup_codes WHERE user_id = $1",
                x_user_id,
            )
            for h in hashed:
                await conn.execute(
                    """INSERT INTO mfa_backup_codes
                           (user_id, enterprise_id, code_hash)
                       VALUES ($1, $2, $3)""",
                    x_user_id, x_enterprise_id, h,
                )

    log.info("auth.mfa.enrolled",
             user_id=str(x_user_id), tenant_id=str(x_enterprise_id),
             backup_count=len(codes))
    out = MFAEnrollOut(
        secret_b32=b32,
        otpauth_url=uri,
        backup_codes=codes,
        enrolled=True,
        qr_payload_size=len(uri),
    )
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.post("/mfa/verify", response_model=MFAVerifyOut)
async def verify_mfa(
    body: MFAVerifyRequest,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       UUID = Header(..., alias="X-User-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Verify a TOTP code (6 digits) OR a backup code (10 alphanumeric).

    On first successful TOTP verify after /enroll, flips enabled=TRUE.
    Backup-code verify marks the code as used (single-use).

    K-13: backup-code verify burns the code (single-use); double-click
    on slow network could fire 2 calls. DB-level natural dedup wins the
    race (`WHERE used_at IS NULL` returning rows), but client sees only
    one success. Idempotency-Key caches the response so both replies
    are identical — UX clean.
    """
    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return MFAVerifyOut(**cached)

    master = _platform_mfa_master_key()
    code = body.code.strip()

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT secret_enc, enabled, backup_codes_remaining
               FROM mfa_secrets WHERE user_id = $1""",
            x_user_id,
        )
        if row is None:
            raise HTTPException(status_code=404, detail="MFA not enrolled")

        # Try TOTP first (6 digits)
        if code.isdigit() and len(code) == 6:
            secret = decrypt_secret(row["secret_enc"], master)
            ok = verify_totp(secret, code, drift_steps=1)
            if ok:
                async with conn.transaction():
                    await conn.execute(
                        """UPDATE mfa_secrets
                           SET enabled = TRUE, last_verified_at = NOW(),
                               updated_at = NOW()
                           WHERE user_id = $1""",
                        x_user_id,
                    )
                log.info("auth.mfa.verified", user_id=str(x_user_id), method="totp")
                out = MFAVerifyOut(
                    verified=True, enabled_after=True,
                    used_backup_code=False,
                    backup_codes_remaining=int(row["backup_codes_remaining"]),
                )
                await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
                return out
            out = MFAVerifyOut(
                verified=False, enabled_after=bool(row["enabled"]),
                used_backup_code=False,
                backup_codes_remaining=int(row["backup_codes_remaining"]),
            )
            await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
            return out

        # Backup code path (10-char alphanumeric)
        if len(code) == 10 and code.isalnum():
            h = hash_backup_code(code.upper())
            used = await conn.fetchrow(
                """UPDATE mfa_backup_codes
                   SET used_at = NOW()
                   WHERE user_id = $1 AND code_hash = $2 AND used_at IS NULL
                   RETURNING code_id""",
                x_user_id, h,
            )
            if used is not None:
                remaining = int(row["backup_codes_remaining"]) - 1
                await conn.execute(
                    """UPDATE mfa_secrets
                       SET backup_codes_remaining = $1, last_verified_at = NOW(),
                           enabled = TRUE, updated_at = NOW()
                       WHERE user_id = $2""",
                    remaining, x_user_id,
                )
                log.info("auth.mfa.verified",
                         user_id=str(x_user_id), method="backup",
                         backup_remaining=remaining)
                out = MFAVerifyOut(
                    verified=True, enabled_after=True,
                    used_backup_code=True,
                    backup_codes_remaining=remaining,
                )
                await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
                return out

        out = MFAVerifyOut(
            verified=False, enabled_after=bool(row["enabled"]),
            used_backup_code=False,
            backup_codes_remaining=int(row["backup_codes_remaining"]),
        )
        await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
        return out


@router.get("/mfa/status", response_model=MFAStatusOut)
async def get_mfa_status(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       UUID = Header(..., alias="X-User-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT enabled, enrolled_at, last_verified_at,
                      backup_codes_remaining
               FROM mfa_secrets WHERE user_id = $1""",
            x_user_id,
        )
    if row is None:
        return MFAStatusOut(
            enabled=False, enrolled=False, enrolled_at=None,
            last_verified_at=None, backup_codes_remaining=0,
        )
    return MFAStatusOut(
        enabled=row["enabled"],
        enrolled=row["enrolled_at"] is not None,
        enrolled_at=row["enrolled_at"],
        last_verified_at=row["last_verified_at"],
        backup_codes_remaining=int(row["backup_codes_remaining"]),
    )


@router.delete("/mfa", status_code=204)
async def disable_mfa(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id:       UUID = Header(..., alias="X-User-ID"),
):
    """Disable MFA — wipes secret + all backup codes. Caller is
    expected to require a recent re-verification before invoking this
    (frontend gate); router does NOT re-check here for simplicity."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            "DELETE FROM mfa_secrets WHERE user_id = $1",
            x_user_id,
        )
    log.info("auth.mfa.disabled", user_id=str(x_user_id))
    return None


# ─── Field encryption key endpoints ──────────────────────────────────


class FieldKeyStatusOut(BaseModel):
    enterprise_id: UUID
    key_id:        UUID
    version:       int
    rotated_at:    Optional[datetime]
    created_at:    datetime
    key_ref_kind:  str    # 'vault' | 'inline_dev'


class FieldKeyRotateOut(BaseModel):
    enterprise_id: UUID
    old_version:   int
    new_version:   int
    rotated_at:    datetime


@router.get("/field-key/status", response_model=FieldKeyStatusOut)
async def field_key_status(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """SELECT key_id, version, rotated_at, created_at, key_ref
               FROM tenant_field_keys WHERE enterprise_id = $1""",
            x_enterprise_id,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="No field-encryption key provisioned for this tenant",
        )
    kind = "vault" if not row["key_ref"].startswith("inline:") else "inline_dev"
    return FieldKeyStatusOut(
        enterprise_id=x_enterprise_id, key_id=row["key_id"],
        version=row["version"], rotated_at=row["rotated_at"],
        created_at=row["created_at"], key_ref_kind=kind,
    )


@router.post("/field-key/rotate", response_model=FieldKeyRotateOut)
async def rotate_field_key(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Rotate the tenant's field-encryption key. Increments version
    and archives the prior key into tenant_field_key_versions so
    existing ciphertext stays decryptable until the re-encrypt worker
    (POST /field-key/reencrypt) rewrites every row under the new key.

    K-13: rotation writes to Vault under prod profile — wasteful double
    Vault writes from double-click would litter the secret store with
    abandoned keys. Idempotency-Key collapses to 1 rotation.

    Lifecycle:
      1. Capture current (version, key_ref) — both old + new go into
         tenant_field_key_versions so history fallback can decrypt
         pre-rotation ciphertext.
      2. Bump version on tenant_field_keys; install new key_ref.
      3. Mark reencrypt_status='pending' so the worker (manual trigger
         or scheduled) picks the tenant up.

    First call for a new tenant inserts version=1 (no rotation; just
    provisions the initial key) and skips the pending flag.

    In dev profile, generates a fresh inline:base64 key. Production
    swaps to writing to Vault path.
    """
    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return FieldKeyRotateOut(**cached)

    new_key_b64 = generate_key_b64()
    # K-18: production stores in Vault and returns the path. Dev keeps
    # inline:base64 for transparent local testing.
    is_prod = os.getenv("KAORI_PROFILE", "dev") in ("production", "prod")
    if is_prod:
        try:
            from ..shared.kaori_vault import get_default_client
            client = get_default_client()
            # Each rotation gets a unique versioned path so old keys
            # stay readable until the re-encrypt worker confirms purge.
            from datetime import datetime as _dt
            stamp = _dt.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            path = f"tenant/{x_enterprise_id}/encryption/field_key_{stamp}"
            client.write_sync(path, {"key": new_key_b64})
            new_ref = f"vault:{path}"
            log.info("auth.field_key.vault_written",
                     tenant_id=str(x_enterprise_id), path=path)
        except Exception as e:   # noqa: BLE001
            raise HTTPException(
                status_code=500,
                detail=(
                    f"K-18: production requires Vault write to succeed; "
                    f"refusing to rotate with inline: fallback. Error: {e}"
                ),
            ) from e
    else:
        new_ref = f"inline:{new_key_b64}"
    async with acquire_for_tenant(x_enterprise_id) as conn:
        async with conn.transaction():
            existing = await conn.fetchrow(
                """SELECT version, key_ref FROM tenant_field_keys
                   WHERE enterprise_id = $1""",
                x_enterprise_id,
            )

            if existing is None:
                row = await conn.fetchrow(
                    """INSERT INTO tenant_field_keys
                           (enterprise_id, key_ref, version, reencrypt_status)
                       VALUES ($1, $2, 1, 'idle')
                       RETURNING version, rotated_at, created_at""",
                    x_enterprise_id, new_ref,
                )
                await conn.execute(
                    """INSERT INTO tenant_field_key_versions
                           (enterprise_id, version, key_ref)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (enterprise_id, version) DO NOTHING""",
                    x_enterprise_id, 1, new_ref,
                )
                new_version = 1
                old_version = 0
                log.info("auth.field_key.provisioned",
                         tenant_id=str(x_enterprise_id), version=1)
            else:
                old_version = int(existing["version"])
                new_version = old_version + 1

                # Make sure the old key is mirrored in history (idempotent
                # — backfill in mig 080 may have already done this).
                await conn.execute(
                    """INSERT INTO tenant_field_key_versions
                           (enterprise_id, version, key_ref)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (enterprise_id, version) DO NOTHING""",
                    x_enterprise_id, old_version, existing["key_ref"],
                )
                # Mark the prior version as superseded.
                await conn.execute(
                    """UPDATE tenant_field_key_versions
                       SET superseded_at = NOW()
                       WHERE enterprise_id = $1
                         AND version = $2
                         AND superseded_at IS NULL""",
                    x_enterprise_id, old_version,
                )

                # Bump current row + record the new version in history.
                row = await conn.fetchrow(
                    """UPDATE tenant_field_keys
                       SET key_ref           = $2,
                           version           = $3,
                           rotated_at        = NOW(),
                           reencrypt_status  = 'pending',
                           reencrypt_error   = NULL
                       WHERE enterprise_id = $1
                       RETURNING version, rotated_at, created_at""",
                    x_enterprise_id, new_ref, new_version,
                )
                await conn.execute(
                    """INSERT INTO tenant_field_key_versions
                           (enterprise_id, version, key_ref)
                       VALUES ($1, $2, $3)
                       ON CONFLICT (enterprise_id, version) DO NOTHING""",
                    x_enterprise_id, new_version, new_ref,
                )
                log.info("auth.field_key.rotated",
                         tenant_id=str(x_enterprise_id),
                         old_version=old_version,
                         new_version=new_version)

    out = FieldKeyRotateOut(
        enterprise_id=x_enterprise_id,
        old_version=old_version,
        new_version=new_version,
        rotated_at=row["rotated_at"] or datetime.now(timezone.utc),
    )
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


# ─── Re-encrypt worker endpoints (P2 retro item 6) ───────────────────


class ReencryptColumnOut(BaseModel):
    column:               str
    rows_scanned:         int
    rows_already_current: int
    rows_reencrypted:     int
    rows_failed:          int
    failed_pks:           list[str]


class ReencryptRunOut(BaseModel):
    enterprise_id:       UUID
    status:              str          # running | completed | failed
    current_version:     int
    started_at:          datetime
    finished_at:         Optional[datetime]
    total_reencrypted:   int
    total_failed:        int
    columns:             list[ReencryptColumnOut]
    error:               Optional[str]


class ReencryptStatusOut(BaseModel):
    enterprise_id:           UUID
    reencrypt_status:        str
    reencrypt_started_at:    Optional[datetime]
    reencrypt_completed_at:  Optional[datetime]
    reencrypt_error:         Optional[str]
    current_version:         int
    history_depth:           int


@router.post("/field-key/reencrypt", response_model=ReencryptRunOut, status_code=200)
async def trigger_reencrypt(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Run the field-key re-encrypt worker for the calling tenant.
    Walks every registered encrypted column, decrypts via key history,
    rewrites under the current key version. Idempotent — safe to call
    repeatedly; rows already under current key are skipped.

    Synchronous in this Phase 2 implementation. Phase 2.5+ moves the
    work onto a Temporal worker (TEMPORAL_ENABLE_WORKER=true) for
    tenants with high row counts.

    K-13: re-encrypt is natural-idempotent (rows already current skip)
    but worker invocation is heavy (scans all encrypted columns).
    Idempotency-Key dedupes worker runs from double-click on admin panel
    so we don't pay the scan cost twice.
    """
    cached = await _idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_idempotent")
    if cached is not None:
        return ReencryptRunOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        report = await reencrypt_tenant(conn, x_enterprise_id)

    out = ReencryptRunOut(
        enterprise_id=x_enterprise_id,
        status=report.status,
        current_version=report.current_version,
        started_at=report.started_at,
        finished_at=report.finished_at,
        total_reencrypted=report.total_reencrypted,
        total_failed=report.total_failed,
        columns=[
            ReencryptColumnOut(
                column=c.column,
                rows_scanned=c.rows_scanned,
                rows_already_current=c.rows_already_current,
                rows_reencrypted=c.rows_reencrypted,
                rows_failed=c.rows_failed,
                failed_pks=c.failed_pks,
            )
            for c in report.columns
        ],
        error=report.error,
    )
    await _record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.get("/field-key/reencrypt/status", response_model=ReencryptStatusOut)
async def get_reencrypt_status(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    """Report the tenant's current re-encrypt worker state. Returns
    404 if the tenant has no field-encryption key provisioned yet."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        cur = await conn.fetchrow(
            """SELECT version, reencrypt_status, reencrypt_started_at,
                      reencrypt_completed_at, reencrypt_error
               FROM tenant_field_keys WHERE enterprise_id = $1""",
            x_enterprise_id,
        )
        if cur is None:
            raise HTTPException(
                status_code=404,
                detail="No field-encryption key provisioned for this tenant",
            )
        depth = await conn.fetchval(
            """SELECT COUNT(*) FROM tenant_field_key_versions
               WHERE enterprise_id = $1 AND purged_at IS NULL""",
            x_enterprise_id,
        )

    return ReencryptStatusOut(
        enterprise_id=x_enterprise_id,
        reencrypt_status=cur["reencrypt_status"],
        reencrypt_started_at=cur["reencrypt_started_at"],
        reencrypt_completed_at=cur["reencrypt_completed_at"],
        reencrypt_error=cur["reencrypt_error"],
        current_version=int(cur["version"]),
        history_depth=int(depth or 0),
    )
