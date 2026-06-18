"""
P2 retro item 6 — background re-encrypt worker for field-key rotation.

After /p2/auth/field-key/rotate bumps a tenant's encryption-key version,
existing ciphertext is still encrypted under the prior key. This module
walks every registered encrypted column for the tenant, decrypts using
the historical key (mig 080 tenant_field_key_versions), and re-encrypts
under the current version.

Lifecycle (driven by tenant_field_keys.reencrypt_status):

    idle      -> pending          [POST /p2/auth/field-key/rotate]
    pending   -> running          [worker picks up]
    running   -> completed         [all rows re-encrypted under current]
    running   -> failed            [one+ row undecryptable with ANY key version]
    completed -> idle              [implicit; idle is the steady state until next rotate]

A `failed` run leaves the row marked so anh can inspect `reencrypt_error`
and decide manual intervention. The worker is idempotent — re-running on
'completed' is a no-op; re-running on 'failed' retries from scratch.

Column registry
---------------
Columns must opt in to re-encryption by appearing in COLUMNS below. Each
entry declares the table, primary-key column, the encrypted column, and
the tenant column name. The worker queries per-tenant rows, decrypts,
re-encrypts under the current key, and writes back via UPDATE.

K-rules
-------
K-1 / K-12: all SELECT/UPDATE are scoped via WHERE enterprise_id = $1.
K-13 idempotency: the worker can be invoked multiple times safely. Each
     row is re-encrypted in place — a duplicate run on an already-current
     row decrypts under the current key and rewrites the same plaintext
     under the same key (different IV — fine, just a noop in effect).
K-18: only the tenant's CURRENT key_ref is used to encrypt outputs;
     history keys are decrypt-only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import structlog

from .crypto import (
    CryptoError,
    WrappedKey,
    decrypt_field_with_history,
    encrypt_field,
    resolve_tenant_key,
)

log = structlog.get_logger()


# ─── Column registry ─────────────────────────────────────────────────


@dataclass(frozen=True)
class EncryptedColumn:
    """A column whose contents are AES-GCM ciphertext under the
    tenant's current field-encryption key."""
    table:             str
    primary_key:       str
    encrypted_column:  str
    enterprise_column: str = "enterprise_id"


COLUMNS: tuple[EncryptedColumn, ...] = (
    EncryptedColumn(
        table="tenant_llm_api_keys",
        primary_key="key_id",
        encrypted_column="api_key_enc",
    ),
    # Future encrypted columns (cccd / salary / contact details) opt in here.
)


# ─── Report shapes ───────────────────────────────────────────────────


@dataclass
class ColumnReport:
    """Per-column outcome of one worker run."""
    column:               str
    rows_scanned:         int = 0
    rows_already_current: int = 0
    rows_reencrypted:     int = 0
    rows_failed:          int = 0
    failed_pks:           list[str] = field(default_factory=list)


@dataclass
class ReencryptReport:
    """Top-level outcome of one worker run for one tenant."""
    enterprise_id: UUID
    started_at:    datetime
    finished_at:   Optional[datetime] = None
    status:        str = "running"     # running | completed | failed
    current_version: int = 0
    columns:       list[ColumnReport] = field(default_factory=list)
    error:         Optional[str] = None

    @property
    def total_reencrypted(self) -> int:
        return sum(c.rows_reencrypted for c in self.columns)

    @property
    def total_failed(self) -> int:
        return sum(c.rows_failed for c in self.columns)


# ─── Key history loader ──────────────────────────────────────────────


async def load_key_history(
    conn,
    enterprise_id: UUID,
    *,
    vault_client: Optional[object] = None,
) -> tuple[WrappedKey, list[WrappedKey]]:
    """Return (current_key, all_keys_descending) for the tenant.

    `all_keys_descending` includes the current key at index 0, so it
    can be passed straight to decrypt_field_with_history.

    Pulls from tenant_field_key_versions; if a tenant has no history
    rows yet (pre-mig-076 install), falls back to the current
    tenant_field_keys row.
    """
    rows = await conn.fetch(
        """SELECT version, key_ref FROM tenant_field_key_versions
           WHERE enterprise_id = $1 AND purged_at IS NULL
           ORDER BY version DESC""",
        enterprise_id,
    )

    if not rows:
        cur = await conn.fetchrow(
            """SELECT version, key_ref FROM tenant_field_keys
               WHERE enterprise_id = $1""",
            enterprise_id,
        )
        if cur is None:
            raise CryptoError(
                f"Tenant {enterprise_id} has no field-encryption key provisioned"
            )
        wk = resolve_tenant_key(
            tenant_id=str(enterprise_id),
            key_ref=cur["key_ref"],
            version=int(cur["version"]),
            vault_client=vault_client,
        )
        return wk, [wk]

    keys = [
        resolve_tenant_key(
            tenant_id=str(enterprise_id),
            key_ref=r["key_ref"],
            version=int(r["version"]),
            vault_client=vault_client,
        )
        for r in rows
    ]
    return keys[0], keys


# ─── Worker entry points ─────────────────────────────────────────────


async def reencrypt_tenant(
    conn,
    enterprise_id: UUID,
    *,
    vault_client: Optional[object] = None,
    columns: tuple[EncryptedColumn, ...] = COLUMNS,
) -> ReencryptReport:
    """Re-encrypt all registered ciphertext rows under the tenant's
    current key. Loads key history, walks each column, and updates
    tenant_field_keys.reencrypt_status as it runs.

    Pass `columns=...` to scope to a subset (useful in tests).
    """
    started = datetime.now(timezone.utc)
    report = ReencryptReport(
        enterprise_id=enterprise_id,
        started_at=started,
    )

    try:
        current, history = await load_key_history(
            conn, enterprise_id, vault_client=vault_client,
        )
    except CryptoError as e:
        report.status = "failed"
        report.error = str(e)
        report.finished_at = datetime.now(timezone.utc)
        log.error("field_key_rotation.no_key",
                  tenant_id=str(enterprise_id), error=str(e))
        return report

    report.current_version = current.version

    await conn.execute(
        """UPDATE tenant_field_keys
           SET reencrypt_status     = 'running',
               reencrypt_started_at = $2,
               reencrypt_error      = NULL
           WHERE enterprise_id = $1""",
        enterprise_id, started,
    )

    for col_spec in columns:
        col_report = await _reencrypt_column(
            conn, enterprise_id, col_spec, current, history,
        )
        report.columns.append(col_report)

    finished = datetime.now(timezone.utc)
    report.finished_at = finished

    if report.total_failed > 0:
        report.status = "failed"
        report.error = (
            f"{report.total_failed} row(s) could not be decrypted with "
            f"any of {len(history)} known key version(s). See per-column "
            f"failed_pks for details."
        )
        await conn.execute(
            """UPDATE tenant_field_keys
               SET reencrypt_status        = 'failed',
                   reencrypt_completed_at  = $2,
                   reencrypt_error         = $3
               WHERE enterprise_id = $1""",
            enterprise_id, finished, report.error[:500],
        )
    else:
        report.status = "completed"
        await conn.execute(
            """UPDATE tenant_field_keys
               SET reencrypt_status        = 'completed',
                   reencrypt_completed_at  = $2,
                   reencrypt_error         = NULL
               WHERE enterprise_id = $1""",
            enterprise_id, finished,
        )
        # Mark superseded versions as purged — no row uses them anymore.
        if len(history) > 1:
            superseded_versions = [k.version for k in history[1:]]
            await conn.execute(
                """UPDATE tenant_field_key_versions
                   SET purged_at = $3
                   WHERE enterprise_id = $1
                     AND version = ANY($2::int[])
                     AND purged_at IS NULL""",
                enterprise_id, superseded_versions, finished,
            )

    log.info("field_key_rotation.run_complete",
             tenant_id=str(enterprise_id),
             status=report.status,
             current_version=current.version,
             total_reencrypted=report.total_reencrypted,
             total_failed=report.total_failed,
             history_depth=len(history))
    return report


async def _reencrypt_column(
    conn,
    enterprise_id: UUID,
    spec: EncryptedColumn,
    current: WrappedKey,
    history: list[WrappedKey],
) -> ColumnReport:
    """Walk every row in spec.table where enterprise_id matches.
    Decrypt with history (any version), re-encrypt under current,
    write back."""
    report = ColumnReport(column=f"{spec.table}.{spec.encrypted_column}")

    rows = await conn.fetch(
        f"SELECT {spec.primary_key}, {spec.encrypted_column} "  # noqa: S608
        f"FROM {spec.table} WHERE {spec.enterprise_column} = $1",
        enterprise_id,
    )

    for row in rows:
        report.rows_scanned += 1
        pk = row[spec.primary_key]
        ciphertext = row[spec.encrypted_column]

        if ciphertext is None or ciphertext == "":
            # Nothing to do; empty/NULL columns aren't encrypted under any key.
            continue

        # Fast-path: try current key only. If it decrypts, the row is
        # already under the current version — skip the rewrite.
        from .crypto import _try_decrypt  # noqa: PLC0415 (internal helper)
        plaintext = _try_decrypt(ciphertext, current)
        if plaintext is not None:
            report.rows_already_current += 1
            continue

        # Slow-path: try every historical key.
        try:
            plaintext, found_version = decrypt_field_with_history(
                ciphertext, history,
            )
        except CryptoError as e:
            report.rows_failed += 1
            report.failed_pks.append(str(pk))
            log.warning("field_key_rotation.row_undecryptable",
                        tenant_id=str(enterprise_id),
                        column=report.column,
                        pk=str(pk),
                        error=str(e))
            continue

        new_ct = encrypt_field(plaintext, current)
        await conn.execute(
            f"UPDATE {spec.table} SET {spec.encrypted_column} = $1 "  # noqa: S608
            f"WHERE {spec.primary_key} = $2 AND {spec.enterprise_column} = $3",
            new_ct, pk, enterprise_id,
        )
        report.rows_reencrypted += 1
        log.info("field_key_rotation.row_rewritten",
                 tenant_id=str(enterprise_id),
                 column=report.column,
                 pk=str(pk),
                 from_version=found_version,
                 to_version=current.version)

    return report
