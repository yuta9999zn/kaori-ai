"""
P2-S22 D2 — LLM ops endpoints (MAX-tier features).

Endpoints (mounted under /platform/llm)
---------------------------------------
P1-LLM-001 catalog:
    GET    /platform/llm/catalog/providers              list providers (global)

P1-LLM-002 tenant API key management:
    GET    /platform/llm/api-keys                       list tenant's enabled providers
    POST   /platform/llm/api-keys/{provider_key}/new    encrypt + store API key
    DELETE /platform/llm/api-keys/{provider_key}        disable + wipe key

P1-LLM-003 token + cost monitoring:
    GET    /platform/llm/tokens/breakdown               per-provider per-day rollup
                                                         ?days=30&provider=anthropic

P1-LLM-006 controlled upgrade test (90-day shadow A/B):
    POST   /platform/llm/versions/upgrade-test          start a new shadow test
    GET    /platform/llm/versions/upgrade-test          list active tests
    POST   /platform/llm/versions/upgrade-test/{id}/promote   accept candidate
    POST   /platform/llm/versions/upgrade-test/{id}/reject    cancel test

K-rules
-------
K-1 / K-12: tenant from X-Enterprise-ID. Provider catalog read is global
            (no tenant filter), but PER-tenant tables stay tenant-scoped.
K-5 / K-18: API keys encrypted with TENANT field-key (mig 074 dogfood).
K-20: upgrade test always pins both current_version + candidate_version.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Header, HTTPException, Path, Query
from pydantic import BaseModel, Field

from ..shared.crypto import (
    CryptoError,
    decrypt_field,
    encrypt_field,
    resolve_tenant_key,
)
from ..shared import ai_config
from ..shared.db import acquire_for_tenant, get_pool
from ..shared.idempotency_helper import (
    idempotency_short_circuit,
    record_idempotency_outcome,
)

log = structlog.get_logger()

router = APIRouter(prefix="/platform/llm")


# ─── Shapes ──────────────────────────────────────────────────────────


class ProviderOut(BaseModel):
    provider_id:        UUID
    provider_key:       str
    display_name:       str
    requires_api_key:   bool
    supports_streaming: bool
    is_external:        bool
    default_models:     list[str]
    cost_per_1k_input:  str
    cost_per_1k_output: str


class TenantKeyOut(BaseModel):
    key_id:        UUID
    provider_key:  str
    label:         Optional[str]
    enabled:       bool
    last_used_at:  Optional[datetime]
    created_at:    datetime
    rotated_at:    Optional[datetime]


class TenantKeyCreate(BaseModel):
    api_key:       str = Field(..., min_length=8, max_length=500,
                                description="Raw API key — server encrypts before persist.")
    label:         Optional[str] = Field(default=None, max_length=100)


class TokenBreakdownRow(BaseModel):
    provider_key:    str
    period_day:      date
    input_tokens:    int
    output_tokens:   int
    cost_usd:        str
    cost_vnd:        str
    call_count:      int
    cache_hit_count: int
    error_count:     int


class UpgradeTestCreate(BaseModel):
    provider_key:       str
    current_model:      str = Field(..., min_length=1, max_length=100)
    current_version:    str = Field(..., min_length=1, max_length=64)
    candidate_model:    str = Field(..., min_length=1, max_length=100)
    candidate_version:  str = Field(..., min_length=1, max_length=64)
    test_days:          int = Field(default=90, ge=7, le=180)
    notes:              Optional[str] = None


class UpgradeTestOut(BaseModel):
    test_id:            UUID
    provider_key:       str
    current_model:      str
    current_version:    str
    candidate_model:    str
    candidate_version:  str
    started_at:         datetime
    ends_at:            datetime
    status:             str
    shadow_call_count:  int
    agreement_rate:     Optional[str]
    avg_cost_delta_usd: Optional[str]
    notes:              Optional[str]


# ─── Helpers ─────────────────────────────────────────────────────────


async def _resolve_tenant_field_key(conn, tenant_id: UUID):
    """Look up tenant_field_keys.{key_ref,version}, hand off to shared/crypto.

    `version` flows through to WrappedKey so re-encrypt worker can
    track which key produced which ciphertext."""
    row = await conn.fetchrow(
        "SELECT key_ref, version FROM tenant_field_keys WHERE enterprise_id = $1",
        tenant_id,
    )
    if row is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "Tenant has no field-encryption key. Call "
                "POST /p2/auth/field-key/rotate first to provision."
            ),
        )
    return resolve_tenant_key(
        tenant_id=str(tenant_id),
        key_ref=row["key_ref"],
        version=int(row["version"]),
    )


# ─── P1-LLM-001 catalog ──────────────────────────────────────────────


@router.get("/catalog/providers", response_model=list[ProviderOut])
async def list_providers(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    include_inactive: bool = Query(default=False),
):
    """Global provider catalog. Tenant header still required (K-12)
    for audit trail."""
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = """SELECT * FROM llm_providers"""
        if not include_inactive:
            sql += " WHERE is_active = TRUE"
        sql += " ORDER BY provider_key"
        rows = await conn.fetch(sql)
    return [
        ProviderOut(
            provider_id=r["provider_id"],
            provider_key=r["provider_key"],
            display_name=r["display_name"],
            requires_api_key=r["requires_api_key"],
            supports_streaming=r["supports_streaming"],
            is_external=r["is_external"],
            default_models=list(r["default_models"] or []),
            cost_per_1k_input=str(r["cost_per_1k_input"]),
            cost_per_1k_output=str(r["cost_per_1k_output"]),
        )
        for r in rows
    ]


# ─── P1-LLM-002 tenant API keys ──────────────────────────────────────


@router.get("/api-keys", response_model=list[TenantKeyOut])
async def list_tenant_keys(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        rows = await conn.fetch(
            """SELECT k.key_id, k.label, k.enabled, k.last_used_at,
                      k.created_at, k.rotated_at, p.provider_key
               FROM tenant_llm_api_keys k
               JOIN llm_providers p ON p.provider_id = k.provider_id
               WHERE k.enterprise_id = $1
               ORDER BY k.created_at""",
            x_enterprise_id,
        )
    return [
        TenantKeyOut(
            key_id=r["key_id"], provider_key=r["provider_key"],
            label=r["label"], enabled=r["enabled"],
            last_used_at=r["last_used_at"], created_at=r["created_at"],
            rotated_at=r["rotated_at"],
        )
        for r in rows
    ]


@router.post("/api-keys/{provider_key}/new",
             response_model=TenantKeyOut, status_code=201)
async def add_tenant_key(
    body: TenantKeyCreate,
    provider_key: str = Path(..., min_length=1, max_length=32),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Encrypt the raw API key with the tenant's field-encryption key
    (mig 074 dogfood) + upsert one row per (tenant, provider).

    K-13: financial impact — wrong-clicking "rotate" twice would not
    create 2 vendor keys (UPSERT clamps to 1 row), but billing audit log
    would show 2 rotations. Idempotency-Key collapses to 1 audit entry.
    """
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_idempotent")
    if cached is not None:
        return TenantKeyOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        provider = await conn.fetchrow(
            "SELECT provider_id, requires_api_key FROM llm_providers "
            "WHERE provider_key = $1 AND is_active = TRUE",
            provider_key,
        )
        if provider is None:
            raise HTTPException(status_code=404, detail="provider not in catalog")
        if not provider["requires_api_key"]:
            raise HTTPException(
                status_code=400,
                detail=f"provider {provider_key!r} does not require an API key",
            )

        field_key = await _resolve_tenant_field_key(conn, x_enterprise_id)
        encrypted = encrypt_field(body.api_key, field_key)

        row = await conn.fetchrow(
            """INSERT INTO tenant_llm_api_keys
                   (enterprise_id, provider_id, api_key_enc, label, enabled)
               VALUES ($1, $2, $3, $4, TRUE)
               ON CONFLICT (enterprise_id, provider_id) DO UPDATE SET
                   api_key_enc = EXCLUDED.api_key_enc,
                   label       = EXCLUDED.label,
                   enabled     = TRUE,
                   rotated_at  = NOW()
               RETURNING key_id, label, enabled, last_used_at, created_at, rotated_at""",
            x_enterprise_id, provider["provider_id"], encrypted, body.label,
        )
    log.info("llm.api_key.stored",
             tenant_id=str(x_enterprise_id), provider=provider_key)
    out = TenantKeyOut(
        key_id=row["key_id"], provider_key=provider_key,
        label=row["label"], enabled=row["enabled"],
        last_used_at=row["last_used_at"], created_at=row["created_at"],
        rotated_at=row["rotated_at"],
    )
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.delete("/api-keys/{provider_key}", status_code=204)
async def disable_tenant_key(
    provider_key: str = Path(..., min_length=1, max_length=32),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        await conn.execute(
            """DELETE FROM tenant_llm_api_keys
               WHERE enterprise_id = $1
                 AND provider_id = (
                     SELECT provider_id FROM llm_providers
                     WHERE provider_key = $2
                 )""",
            x_enterprise_id, provider_key,
        )
    log.info("llm.api_key.removed",
             tenant_id=str(x_enterprise_id), provider=provider_key)
    return None


# ─── P1-LLM-003 token + cost monitoring ──────────────────────────────


@router.get("/tokens/breakdown", response_model=list[TokenBreakdownRow])
async def token_breakdown(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    days: int = Query(default=30, ge=1, le=365),
    provider: Optional[str] = Query(default=None, max_length=32),
):
    cutoff = date.today() - timedelta(days=days)
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = """SELECT u.period_day, u.input_tokens, u.output_tokens,
                        u.cost_usd, u.cost_vnd, u.call_count,
                        u.cache_hit_count, u.error_count, p.provider_key
                 FROM llm_token_usage_daily u
                 JOIN llm_providers p ON p.provider_id = u.provider_id
                 WHERE u.enterprise_id = $1 AND u.period_day >= $2"""
        params: list[Any] = [x_enterprise_id, cutoff]
        if provider is not None:
            params.append(provider)
            sql += f" AND p.provider_key = ${len(params)}"
        sql += " ORDER BY u.period_day DESC, p.provider_key"
        rows = await conn.fetch(sql, *params)
    return [
        TokenBreakdownRow(
            provider_key=r["provider_key"],
            period_day=r["period_day"],
            input_tokens=int(r["input_tokens"]),
            output_tokens=int(r["output_tokens"]),
            cost_usd=str(r["cost_usd"]),
            cost_vnd=str(r["cost_vnd"]),
            call_count=int(r["call_count"]),
            cache_hit_count=int(r["cache_hit_count"]),
            error_count=int(r["error_count"]),
        )
        for r in rows
    ]


# ─── P1-LLM-006 90-day shadow upgrade tests ──────────────────────────


@router.post("/versions/upgrade-test", response_model=UpgradeTestOut, status_code=201)
async def start_upgrade_test(
    body: UpgradeTestCreate,
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Start a 90-day shadow A/B test (P1-LLM-006). The candidate
    runs alongside `current_model` — the orchestrator decides whether
    to mirror calls to it based on tenant's `shadow_sample_rate` setting
    (default 5% — implemented in llm-gateway adapter, not here).

    K-13: Idempotency-Key dedupes double-click; without it, 2 RUNNING
    test rows for same (tenant, candidate) would compete for shadow traffic.
    """
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return UpgradeTestOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        provider = await conn.fetchrow(
            "SELECT provider_id FROM llm_providers WHERE provider_key = $1",
            body.provider_key,
        )
        if provider is None:
            raise HTTPException(status_code=404, detail="provider not in catalog")
        ends = datetime.now(timezone.utc) + timedelta(days=body.test_days)
        row = await conn.fetchrow(
            """INSERT INTO llm_upgrade_tests
                   (enterprise_id, provider_id, current_model, current_version,
                    candidate_model, candidate_version, ends_at, notes)
               VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
               RETURNING *""",
            x_enterprise_id, provider["provider_id"],
            body.current_model, body.current_version,
            body.candidate_model, body.candidate_version,
            ends, body.notes,
        )
    log.info("llm.upgrade_test.started",
             tenant_id=str(x_enterprise_id),
             test_id=str(row["test_id"]),
             candidate=f"{body.candidate_model}/{body.candidate_version}")
    out = _upgrade_test_to_out(row, body.provider_key)
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.get("/versions/upgrade-test", response_model=list[UpgradeTestOut])
async def list_upgrade_tests(
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    status: Optional[str] = Query(default=None,
                                   pattern=r"^(RUNNING|PROMOTED|REJECTED|CANCELLED)$"),
):
    async with acquire_for_tenant(x_enterprise_id) as conn:
        sql = """SELECT t.*, p.provider_key
                 FROM llm_upgrade_tests t
                 JOIN llm_providers p ON p.provider_id = t.provider_id
                 WHERE t.enterprise_id = $1"""
        params: list[Any] = [x_enterprise_id]
        if status is not None:
            params.append(status)
            sql += f" AND t.status = ${len(params)}"
        sql += " ORDER BY t.started_at DESC"
        rows = await conn.fetch(sql, *params)
    return [_upgrade_test_to_out(r, r["provider_key"]) for r in rows]


@router.post("/versions/upgrade-test/{test_id}/promote",
             response_model=UpgradeTestOut)
async def promote_upgrade_test(
    test_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    x_user_id: UUID = Header(..., alias="X-User-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """K-13: promote is IRREVERSIBLE in business terms (new baseline starts
    billing). Idempotency-Key prevents double-fire 404 (2nd call would see
    status=PROMOTED + return 404 with WHERE status='RUNNING')."""
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return UpgradeTestOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE llm_upgrade_tests
               SET status = 'PROMOTED', promoted_at = NOW(), promoted_by = $1
               WHERE test_id = $2 AND status = 'RUNNING'
               RETURNING test_id, provider_id, current_model, current_version,
                         candidate_model, candidate_version, started_at, ends_at,
                         status, shadow_call_count, agreement_rate,
                         avg_cost_delta_usd, notes,
                         (SELECT provider_key FROM llm_providers WHERE provider_id = provider_id) AS provider_key""",
            x_user_id, test_id,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="upgrade test not found or not in RUNNING status",
        )
    log.info("llm.upgrade_test.promoted",
             tenant_id=str(x_enterprise_id), test_id=str(test_id))
    out = _upgrade_test_to_out(row, row["provider_key"])
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


@router.post("/versions/upgrade-test/{test_id}/reject",
             response_model=UpgradeTestOut)
async def reject_upgrade_test(
    test_id: UUID = Path(...),
    x_enterprise_id: UUID = Header(..., alias="X-Enterprise-ID"),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """K-13: same dedupe pattern as promote — 2nd reject click after status
    flipped REJECTED would see 404."""
    cached = await idempotency_short_circuit(x_enterprise_id, idempotency_key,
                                              side_effect_class="write_non_idempotent")
    if cached is not None:
        return UpgradeTestOut(**cached)

    async with acquire_for_tenant(x_enterprise_id) as conn:
        row = await conn.fetchrow(
            """UPDATE llm_upgrade_tests
               SET status = 'REJECTED'
               WHERE test_id = $1 AND status = 'RUNNING'
               RETURNING test_id, provider_id, current_model, current_version,
                         candidate_model, candidate_version, started_at, ends_at,
                         status, shadow_call_count, agreement_rate,
                         avg_cost_delta_usd, notes,
                         (SELECT provider_key FROM llm_providers WHERE provider_id = provider_id) AS provider_key""",
            test_id,
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail="upgrade test not found or not in RUNNING status",
        )
    out = _upgrade_test_to_out(row, row["provider_key"])
    await record_idempotency_outcome(x_enterprise_id, idempotency_key, out.model_dump())
    return out


def _upgrade_test_to_out(row, provider_key: str) -> UpgradeTestOut:
    return UpgradeTestOut(
        test_id=row["test_id"], provider_key=provider_key,
        current_model=row["current_model"],
        current_version=row["current_version"],
        candidate_model=row["candidate_model"],
        candidate_version=row["candidate_version"],
        started_at=row["started_at"], ends_at=row["ends_at"],
        status=row["status"], shadow_call_count=int(row["shadow_call_count"]),
        agreement_rate=(
            str(row["agreement_rate"]) if row["agreement_rate"] is not None else None
        ),
        avg_cost_delta_usd=(
            str(row["avg_cost_delta_usd"])
            if row["avg_cost_delta_usd"] is not None else None
        ),
        notes=row["notes"],
    )


# ─── Platform AI tuning knobs (CR-0019 / FR-PLT-08) ──────────────────

_SUPER_ADMIN_ROLES = ("SUPER_ADMIN", "ADMIN")


def _require_super_admin(role: Optional[str]) -> None:
    if (role or "").upper() not in _SUPER_ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="SUPER_ADMIN role required")


def _validate_config_value(value: str, value_type: str, min_value, max_value) -> None:
    """Type + range check using the bounds declared ON THE ROW (no hard-coded
    ranges in code — adding a knob = a seed row)."""
    if value_type in ("int", "float"):
        try:
            num = float(value)
        except ValueError:
            raise HTTPException(400, f"value phải là {value_type}")
        if value_type == "int" and num != int(num):
            raise HTTPException(400, "value phải là số nguyên")
        if min_value is not None and num < min_value:
            raise HTTPException(400, f"value phải ≥ {min_value}")
        if max_value is not None and num > max_value:
            raise HTTPException(400, f"value phải ≤ {max_value}")
    # string: chấp nhận (độ dài đã giới hạn bởi Pydantic field)


class AIConfigOut(BaseModel):
    config_key:   str
    config_value: str
    value_type:   str
    min_value:    Optional[float]
    max_value:    Optional[float]
    description:  Optional[str]
    applied:      bool
    updated_at:   datetime


class AIConfigUpdate(BaseModel):
    config_value: str = Field(..., min_length=1, max_length=256)


@router.get("/config", response_model=list[AIConfigOut])
async def list_ai_config(
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
):
    """List platform AI tuning knobs (RAG / memory / grounding / embedding).
    SUPER_ADMIN only. `applied=false` knobs are surfaced but not yet wired."""
    _require_super_admin(x_user_role)
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT config_key, config_value, value_type, min_value, max_value,
                      description, applied, updated_at
               FROM platform_ai_config
               ORDER BY applied DESC, config_key"""
        )
    return [AIConfigOut(**dict(r)) for r in rows]


@router.patch("/config/{config_key}", response_model=AIConfigOut)
async def update_ai_config(
    body: AIConfigUpdate,
    config_key: str = Path(..., max_length=64),
    x_user_role: Optional[str] = Header(default=None, alias="X-User-Role"),
    x_user_id: Optional[UUID] = Header(default=None, alias="X-User-ID"),
):
    """Update one knob. SUPER_ADMIN only. Validates against the row's declared
    type + min/max. Invalidates the ai_config cache so the change takes effect
    within seconds (TTL)."""
    _require_super_admin(x_user_role)
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT value_type, min_value, max_value FROM platform_ai_config WHERE config_key = $1",
            config_key,
        )
        if row is None:
            raise HTTPException(404, f"unknown config_key: {config_key}")
        _validate_config_value(body.config_value, row["value_type"],
                               row["min_value"], row["max_value"])
        updated = await conn.fetchrow(
            """UPDATE platform_ai_config
               SET config_value = $1, updated_by = $2, updated_at = NOW()
               WHERE config_key = $3
               RETURNING config_key, config_value, value_type, min_value, max_value,
                         description, applied, updated_at""",
            body.config_value, x_user_id, config_key,
        )
    ai_config.invalidate()
    return AIConfigOut(**dict(updated))
