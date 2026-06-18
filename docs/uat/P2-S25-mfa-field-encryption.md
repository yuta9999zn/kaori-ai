# UAT — P2-S25 MFA TOTP + field-level encryption

> Ship 2026-05-17 commit `b46bdca`. Tests pass local 43/43; UAT here is end-to-end smoke with real Postgres + real auth-service.

## Scope

- P2-AUTH-002 MFA TOTP (mig 074 + `/p2/auth/mfa/*` endpoints + `shared/totp.py`)
- P2-ENC-001 field-level encryption (`shared/crypto.py` + `/p2/auth/field-key/*` endpoints)

Out of scope: P2-AUTH-001 SSO (defer until OAuth credentials provisioned).

## Pre-flight

- [ ] Mig 074 applied to the target environment.
- [ ] `KAORI_MFA_KEY` env var set on ai-orchestrator (32-byte base64).
- [ ] One enterprise user account ready for enrollment (note `user_id` + `enterprise_id`).
- [ ] Authenticator app installed (Google Authenticator / Microsoft Authenticator / Authy).

## Happy path — MFA enroll → verify → status

### Step 1: Enroll

```bash
curl -X POST https://kaori.example.com/p2/auth/mfa/enroll \
  -H "X-Enterprise-ID: $ENT" \
  -H "X-User-ID: $USER" \
  -H "X-User-Email: user@acme.com" \
  -H "Authorization: Bearer $JWT"
```

**Expected response:**
- `201 Created`
- `secret_b32`: 32-character base32 string
- `otpauth_url`: `otpauth://totp/Kaori%20AI:user%40acme.com?secret=...&issuer=...`
- `backup_codes`: array of 10 codes, each 10 chars uppercase alphanumeric
- `enrolled`: `true`

**Side effects to verify:**
- [ ] `mfa_secrets` row created with `enabled=FALSE`
- [ ] 10 rows in `mfa_backup_codes` with `used_at IS NULL`

### Step 2: Scan QR

- [ ] Render `otpauth_url` as QR code (any standard QR library)
- [ ] Scan with authenticator app
- [ ] Account name shows as "Kaori AI: user@acme.com"

### Step 3: First verify (enables MFA)

```bash
curl -X POST https://kaori.example.com/p2/auth/mfa/verify \
  -H "X-Enterprise-ID: $ENT" -H "X-User-ID: $USER" \
  -d '{"code": "<6-digit code from app>"}'
```

**Expected:**
- `verified: true`
- `enabled_after: true`
- `used_backup_code: false`
- `backup_codes_remaining: 10`

**Side effect:**
- [ ] `mfa_secrets.enabled` flips to `TRUE`
- [ ] `mfa_secrets.last_verified_at` set to current time

### Step 4: Backup code verify (consume one)

```bash
curl -X POST https://kaori.example.com/p2/auth/mfa/verify \
  -H "X-Enterprise-ID: $ENT" -H "X-User-ID: $USER" \
  -d '{"code": "<one of the 10 backup codes>"}'
```

**Expected:**
- `verified: true`
- `used_backup_code: true`
- `backup_codes_remaining: 9`

**Side effect:**
- [ ] One row in `mfa_backup_codes` gets `used_at` set
- [ ] Same code now fails on second use

### Step 5: Status check

```bash
curl -X GET https://kaori.example.com/p2/auth/mfa/status \
  -H "X-Enterprise-ID: $ENT" -H "X-User-ID: $USER"
```

**Expected:**
- `enabled: true`
- `enrolled_at` and `last_verified_at` set
- `backup_codes_remaining: 9` (after Step 4)

### Step 6: Disable

```bash
curl -X DELETE https://kaori.example.com/p2/auth/mfa \
  -H "X-Enterprise-ID: $ENT" -H "X-User-ID: $USER"
```

**Expected:** `204 No Content`

**Side effects:**
- [ ] `mfa_secrets` row deleted
- [ ] All `mfa_backup_codes` for this user cascade-deleted (FK ON DELETE CASCADE)
- [ ] `GET /p2/auth/mfa/status` now returns `enabled=false, enrolled=false`

## Edge cases

### Wrong code rejected

- [ ] Submitting random 6 digits → `verified: false`, no DB change.
- [ ] Re-enrolling (POST /enroll twice) overwrites secret + wipes old backup codes + flips `enabled` back to FALSE until next verify.

### Time drift

- [ ] Set system clock back 30 seconds; verify works (`drift_steps=1` default).
- [ ] Set clock back 90 seconds; verify FAILS (outside ±30s window).

### Cross-tenant isolation (K-1)

- [ ] User A in tenant T1 enrolled. User A in tenant T2 (different `enterprise_id`) calls `/status` → `enabled=false, enrolled=false` (T1's record invisible to T2).

## Happy path — Field encryption rotate

### Step 1: Bootstrap a key (dev path)

Manually insert a `tenant_field_keys` row (Phase 1.5 has no onboarding wizard yet):

```sql
INSERT INTO tenant_field_keys (enterprise_id, key_ref, version)
VALUES ('<enterprise_uuid>',
        'inline:' || encode(gen_random_bytes(32), 'base64'),
        1);
```

### Step 2: Status

```bash
curl -X GET https://kaori.example.com/p2/auth/field-key/status \
  -H "X-Enterprise-ID: $ENT"
```

**Expected:**
- `version: 1`
- `key_ref_kind: inline_dev` (or `vault` once Vault wired)

### Step 3: Rotate

```bash
curl -X POST https://kaori.example.com/p2/auth/field-key/rotate \
  -H "X-Enterprise-ID: $ENT"
```

**Expected:**
- `new_version: 2`
- `rotated_at`: recent timestamp

**Side effect:**
- [ ] `tenant_field_keys.version` = 2
- [ ] `tenant_field_keys.key_ref` is a new `inline:` value (different from old)

### Step 4: Encrypt → Decrypt round-trip

Manual Python session (until production caller path lands):

```python
from ai_orchestrator.shared.crypto import (
    encrypt_field, decrypt_field, resolve_tenant_key,
)
key = resolve_tenant_key(tenant_id="<uuid>", key_ref="inline:<from-DB>")
ct = encrypt_field("Nguyễn Văn A — 0901234567", key)
assert decrypt_field(ct, key) == "Nguyễn Văn A — 0901234567"
```

- [ ] Round-trip succeeds.
- [ ] Tampering 1 byte of `ct` → `decrypt_field` raises `CryptoError`.

## Sign-off

| Tester | Date | Pass / Fail | Notes |
|---|---|---|---|
| | | | |

## Known limitations (defer to follow-up)

- SSO OAuth (P2-AUTH-001) not in this UAT — requires Google + Microsoft OAuth credentials anh.
- Vault production path not exercised (`inline:` dev fallback only).
- No background re-encrypt worker yet — old-version ciphertext stays decryptable after rotation but never gets re-encrypted automatically (Phase 2 follow-up).
