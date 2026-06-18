# Runbook — Tenant field-encryption key rotation

> **When to use:** per-tenant key rotation (annual cadence or suspected compromise) for `shared/crypto.py` AES-256-GCM column encryption.
> **Audience:** ops + tenant admin.
> **Severity:** MEDIUM — existing ciphertext stays decryptable under old key version until a separate re-encrypt job runs.

## What this key encrypts

`tenant_field_keys` (mig 074) holds ONE row per tenant carrying `key_ref` + `version`. The key is used by `shared/crypto.py`:

- `encrypt_field(plaintext, WrappedKey)` — application encrypts column values (cccd, salary, contract numbers) before INSERT.
- `decrypt_field(ciphertext_b64, WrappedKey)` — application decrypts on SELECT.

Each ciphertext stores `base64(version(1B) || IV(12B) || GCM_ciphertext+tag)`. Version byte lets the decryptor route to the right key — **so existing ciphertext stays readable under the OLD key after rotation, until a re-encrypt worker rewrites it**.

## Pre-rotation checklist

- [ ] Confirm tenant has a key row in `tenant_field_keys` (`GET /p2/auth/field-key/status`).
- [ ] Tenant admin notified — no operational disruption expected; rotation is hot.
- [ ] Backup of current `tenant_field_keys` row taken (key_ref + version).

## Rotation procedure

### Step 1 — Bump key version

Single HTTP call:

```bash
curl -X POST https://kaori.example.com/p2/auth/field-key/rotate \
  -H "X-Enterprise-ID: <tenant_uuid>" \
  -H "Authorization: Bearer <jwt>"
```

Response includes `new_version`. The endpoint:
- Generates a fresh AES-256 key (`generate_key_b64`)
- Updates `tenant_field_keys.key_ref` to the new `inline:base64key` (dev) or new Vault path (prod when wired)
- Bumps `version` by 1
- Sets `rotated_at = NOW()`

### Step 2 — Verify

```bash
curl -X GET https://kaori.example.com/p2/auth/field-key/status \
  -H "X-Enterprise-ID: <tenant_uuid>"
# Expect: version bumped, rotated_at recent, key_ref_kind unchanged
```

### Step 3 — Optionally trigger re-encrypt worker (PHASE 2)

When the background re-encrypt worker ships (NOT yet in Phase 2), it walks every encrypted column for the tenant, decrypts under the previous version, re-encrypts under the new version, and updates the row. Phase 1.5 / early Phase 2: this runs lazily — each column gets re-encrypted on next UPDATE.

Until the worker lands, anh accepts that old-version ciphertext keeps decrypting fine; the new-version key is only used for new INSERT / UPDATE writes.

## Rollback procedure

If a rotation request mis-fires (e.g. wrong tenant): the rotated key is preserved in the tenant_field_keys row. To roll back to pre-rotation state, manually `UPDATE tenant_field_keys SET key_ref = '<previous_key_ref>', version = version - 1 WHERE enterprise_id = ...`. Existing ciphertext encrypted under the bumped version will then fail decrypt — but the bumped key was only used for writes between rotation and rollback, so impact is bounded.

## Vault prod migration

Currently `key_ref` accepts `inline:base64key` prefix for dev. Production swaps to a Vault path like `kv/data/tenants/<tenant_uuid>/field-key`. `shared/crypto.py:resolve_tenant_key()` supports both — pass a `vault_client` arg to use Vault, omit to use inline/env fallback.

## Related

- `services/ai-orchestrator/shared/crypto.py` — `encrypt_field` / `decrypt_field` / `resolve_tenant_key` / `generate_key_b64`
- `services/ai-orchestrator/routers/auth_security.py` — `/p2/auth/field-key/{status,rotate}` endpoints
- `infrastructure/postgres/migrations/074_mfa_field_encryption.sql` — `tenant_field_keys` table
- ADR-0015 K-4 / K-5 / K-18 — secrets via Vault
