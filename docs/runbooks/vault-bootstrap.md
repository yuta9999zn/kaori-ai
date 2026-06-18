# Vault Bootstrap — K-18 production cutover

> **Status:** Live in dev + staging since 2026-05-18. Production needs Helm chart + AppRole (Phase 3 task).

This runbook covers bringing up HashiCorp Vault for Kaori's K-18 enforcement (every prod secret resolves via Vault, no env-var fallback).

## What Vault holds for Kaori

| Path | Holder | Resolved by |
|---|---|---|
| `platform/encryption/mfa_master_key` | 32-byte AES-256 key encrypting per-user TOTP secrets at rest | `auth_security._platform_mfa_master_key()` |
| `tenant/<enterprise_id>/encryption/field_key_<timestamp>` | Per-tenant AES-256 field-encryption keys | `crypto.resolve_tenant_key()` |
| `platform/auth/internal_service_token` | Shared token between auth-service ↔ ai-orchestrator for SSO exchange-info | (Phase 2.5 — currently env var `KAORI_INTERNAL_SVC_TOKEN`) |

All keys are stored as `{"key": "<base64-encoded bytes>"}` in KV v2 at mount `secret/`.

## First-time setup (dev / staging)

```bash
# 1. Start Vault container
docker compose up -d vault

# 2. Wait ~5 seconds, confirm health
curl -s http://localhost:8200/v1/sys/health | head

# 3. Run bootstrap (idempotent — re-running is safe)
bash infrastructure/vault/bootstrap.sh

# 4. Recreate the two services that consume Vault
docker compose up -d --force-recreate --no-deps ai-orchestrator auth-service
```

Bootstrap script seeds:
- `platform/encryption/mfa_master_key` (32-byte random base64)
- `tenant/<KAORI_TEST_TENANT_ID>/encryption/field_key_initial` for smoke testing

## Verify Vault is wired

```bash
# Should log "auth.mfa_master_key.from_vault"
docker logs kaorisystem-ai-orchestrator-1 2>&1 | grep -i vault | head -3

# Should resolve a key
docker exec kaorisystem-ai-orchestrator-1 python -c "
from ai_orchestrator.shared.kaori_vault import get_default_client
print(get_default_client().read_sync('platform/encryption/mfa_master_key')['key'][:10])
"
```

## Production enforcement (KAORI_PROFILE=production)

Set `KAORI_PROFILE=production` to flip K-18 strict mode:

| Behavior | dev/staging | production |
|---|---|---|
| Vault unavailable → env fallback | warn + use env | **raise K-18 error** |
| `key_ref="inline:<b64>"` | use as dev key | **raise K-18 error** |
| `key_ref=""` (env var fallback) | use `KAORI_FIELD_KEY` | **raise K-18 error** |
| Vault path success | use Vault key | use Vault key |

Test the gate locally:

```bash
docker exec kaorisystem-ai-orchestrator-1 sh -c "
  KAORI_PROFILE=production python -c '
from ai_orchestrator.routers.auth_security import _platform_mfa_master_key
key = _platform_mfa_master_key()
print(f\"OK ({len(key)} bytes)\")
  '
"
```

## Rotating the MFA master key

⚠️ **Caution:** Rotating the MFA master key requires re-encrypting every existing `mfa_secrets.secret_enc` value. Until that re-encrypt runs, users with enrolled MFA can't verify (their stored secrets decrypt with the OLD key only).

Procedure (manual; Phase 2.5 will automate):

```bash
# 1. Save the OLD key value for re-encrypt later
OLD=$(curl -s -H "X-Vault-Token: kaori-dev-root" \
  http://localhost:8200/v1/secret/data/platform/encryption/mfa_master_key \
  | jq -r '.data.data.key')

# 2. Generate + write new key
NEW=$(openssl rand -base64 32)
curl -s -X POST -H "X-Vault-Token: kaori-dev-root" \
  -H "Content-Type: application/json" \
  -d "{\"data\":{\"key\":\"$NEW\"}}" \
  http://localhost:8200/v1/secret/data/platform/encryption/mfa_master_key

# 3. Restart auth-service (picks up new key)
docker compose restart auth-service ai-orchestrator

# 4. (TODO Phase 2.5) Run re-encrypt-mfa-secrets cron with OLD=$OLD
```

## Rotating a tenant field-encryption key

This flow IS automated end-to-end via the re-encrypt worker shipped in mig 080:

```bash
# 1. Bump the tenant's key
curl -X POST http://localhost:8080/api/v1/p2/auth/field-key/rotate \
  -H "X-Enterprise-ID: <uuid>" \
  -H "Authorization: Bearer <jwt>"

# 2. Trigger the re-encrypt worker
curl -X POST http://localhost:8080/api/v1/p2/auth/field-key/reencrypt \
  -H "X-Enterprise-ID: <uuid>" \
  -H "Authorization: Bearer <jwt>"

# 3. Confirm completed
curl http://localhost:8080/api/v1/p2/auth/field-key/reencrypt/status \
  -H "X-Enterprise-ID: <uuid>" \
  -H "Authorization: Bearer <jwt>"
```

Under prod profile, the rotate endpoint writes the new key to a versioned Vault path; under dev, it stores `inline:<b64>` directly in `tenant_field_keys.key_ref`.

## Production deploy (Phase 3 — TO DO)

Current dev mode is NOT prod-safe:
- ❌ In-memory storage (data lost on restart)
- ❌ Auto-unsealed (no Shamir / KMS)
- ❌ Root token in plain text (`kaori-dev-root`)
- ❌ No TLS

Production deploy requires:
1. **HA Raft storage** — 3 Vault nodes with Raft consensus
2. **KMS auto-unseal** — AWS KMS / Azure Key Vault / GCP KMS
3. **AppRole auth method** — each service has its own role + secret-id; root token destroyed after bootstrap
4. **TLS** — mutual TLS via cert-manager
5. **Audit log** — file or syslog sink for every secret access

Helm chart skeleton at `infrastructure/vault/helm/` (P15-S9 prep — not yet rendered).

## Troubleshooting

### `kaori_vault.no_token` warning at boot
- `VAULT_TOKEN` env not set. In dev this is OK if `KAORI_PROFILE != production`; the service falls back to env-var secrets with a warning.
- In production this is fatal — set `VAULT_TOKEN` (AppRole-issued in prod) before container start.

### `Vault path not found: platform/encryption/mfa_master_key`
- Bootstrap script didn't run, OR Vault was restarted (dev mode loses data).
- Re-run `bash infrastructure/vault/bootstrap.sh`.

### `K-18: production requires Vault path ...`
- `KAORI_PROFILE=production` is set but Vault is unreachable / key missing.
- Either: revert to `KAORI_PROFILE=dev` (NOT prod-safe), OR fix Vault connectivity, OR seed the missing path.

### `permission denied for table mfa_backup_codes`
- mig 084_grants_phase2_tables.sql not applied. Run:
  ```bash
  docker exec -i kaorisystem-postgres-1 psql -U kaori -d kaori \
    < infrastructure/postgres/migrations/084_grants_phase2_tables.sql
  ```
