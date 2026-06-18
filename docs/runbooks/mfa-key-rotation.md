# Runbook — MFA master key rotation (KAORI_MFA_KEY)

> **When to use:** annual key rotation, suspected key compromise, or migration from env-var to Vault.
> **Audience:** ops + security lead.
> **Severity:** HIGH — all enterprise + platform admin MFA enrollments break if procedure mis-applied.

## What this key encrypts

`KAORI_MFA_KEY` is the AES-256 master key encrypting **TOTP secret blobs at rest** for two surfaces:

- **Platform admin MFA** — `services/auth-service` (Java) `PlatformAdmin.mfa_secret_enc` column.
- **Enterprise user MFA** — `services/ai-orchestrator/shared/totp.py` `encrypt_secret()` writes to `mfa_secrets.secret_enc` (mig 074, ship P2-S25 2026-05-17).

Wire shape: `base64(IV(12B) || GCM_ciphertext(secret(20B)))`. Java + Python use identical layout for cross-service interop (auth-service issues platform tokens, ai-orchestrator handles enterprise verify).

## Pre-rotation checklist

- [ ] Announce to all platform admins + enterprise users with active MFA: "MFA may briefly require re-verification on ~2026-XX-XX."
- [ ] Backup of `mfa_secrets` + `platform_admins.mfa_secret_enc` taken (in case rollback needed).
- [ ] Both old + new keys staged in Vault (or env-var holder).
- [ ] Maintenance window scheduled — 15-min window typical.

## Rotation procedure

### Step 1 — Generate new key

```bash
python -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"
# Save output as NEW_KEY_B64.
```

### Step 2 — Dual-write phase (decrypt old, re-encrypt new)

This script re-encrypts every `mfa_secrets` row:

```python
# scripts/rotate_mfa_key.py
import asyncio, base64, asyncpg
from ai_orchestrator.shared.totp import decrypt_secret, encrypt_secret

OLD_KEY = base64.b64decode("<OLD_KEY_B64>")
NEW_KEY = base64.b64decode("<NEW_KEY_B64>")

async def rotate():
    conn = await asyncpg.connect("postgresql://...")
    rows = await conn.fetch("SELECT user_id, secret_enc FROM mfa_secrets")
    for r in rows:
        secret = decrypt_secret(r["secret_enc"], OLD_KEY)
        new_blob = encrypt_secret(secret, NEW_KEY)
        await conn.execute(
            "UPDATE mfa_secrets SET secret_enc = $1, updated_at = NOW() WHERE user_id = $2",
            new_blob, r["user_id"],
        )
    print(f"Rotated {len(rows)} enterprise MFA secrets")

asyncio.run(rotate())
```

Repeat for `platform_admins.mfa_secret_enc` (Java side — invoke via auth-service admin endpoint or a sister Java rotation script).

### Step 3 — Cutover

1. Set `KAORI_MFA_KEY=<NEW_KEY_B64>` in ai-orchestrator + auth-service environment.
2. Restart both services (rolling restart OK — but be aware that mid-rotation `/p2/auth/mfa/verify` calls will fail on rows not yet re-encrypted).
3. Verify a known user can `/p2/auth/mfa/verify` with their authenticator app.

### Step 4 — Verify + clean up

- [ ] Spot-check 3 enterprise users + 1 platform admin can verify TOTP.
- [ ] Drop the old key from Vault / env var.
- [ ] Wipe the rotation script's old key from disk (`shred` or `sdelete` on Windows).
- [ ] Record rotation in `docs/runbooks/_log.md` (datetime + operator).

## Rollback procedure

If rotation fails mid-way and some rows are re-encrypted but others not:

1. Stop ai-orchestrator + auth-service.
2. Restore `KAORI_MFA_KEY` to the OLD value.
3. Re-run rotation script — it's idempotent in the sense that decrypt-with-old → re-encrypt-with-old leaves the row unchanged. Rows already encrypted under NEW key will fail decrypt; for those, run the rotation script with `OLD_KEY` swapped to `NEW_KEY` to bring them back.

## Phase 2 migration (Vault-based)

Once Vault HA is wired (K-18), `KAORI_MFA_KEY` env var disappears entirely. Rotation becomes a Vault `kv put` + `kv list-keys` operation, with the ai-orchestrator and auth-service both pulling the current version on cold start. Rotation script then iterates per-version rather than swapping a single env var.

## Related

- `services/ai-orchestrator/shared/totp.py` `encrypt_secret` / `decrypt_secret`
- `services/auth-service/src/main/java/com/kaorisystem/auth/service/TotpService.java`
- `infrastructure/postgres/migrations/074_mfa_field_encryption.sql`
- ADR-0015 (Qwen-first LLM, secrets via Vault) · K-18 invariant
