#!/usr/bin/env bash
# K-18 Vault bootstrap — dev/staging only.
#
# Run once after the Vault container starts, BEFORE any service tries
# to resolve a vault: prefix key_ref. Production uses Helm-managed
# Vault with pre-baked policies + AppRole — this script is dev-only.
#
# What it does
# ------------
# 1. Enables KV v2 at mount path "secret" (default Vault install does
#    this automatically in dev mode, but we make it idempotent).
# 2. Seeds the MFA master key at `secret/platform/encryption/mfa_master_key`
#    so auth-service can resolve it under KAORI_PROFILE=production.
# 3. Provisions a per-tenant test field key at
#    `secret/tenant/<test_enterprise_id>/encryption/field_key_initial`
#    so anh can smoke-test the rotate endpoint without hand-seeding.
#
# Idempotency: each call checks-then-creates. Re-running is safe.
#
# Usage
# -----
#   ./infrastructure/vault/bootstrap.sh
#   # OR via docker:
#   docker exec kaorisystem-vault-1 sh /vault/bootstrap.sh
#
# Override the dev token by setting KAORI_VAULT_DEV_TOKEN to match the
# value in docker-compose.yml.

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://localhost:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-${KAORI_VAULT_DEV_TOKEN:-kaori-dev-root}}"

curl_vault() {
    curl -fsS -H "X-Vault-Token: $VAULT_TOKEN" "$@"
}

# ---- 1. Confirm KV v2 mounted at "secret" -----------------------------

echo "[bootstrap] checking Vault is reachable at $VAULT_ADDR"
curl_vault "$VAULT_ADDR/v1/sys/health" >/dev/null \
    || { echo "  Vault not reachable; is the container up?"; exit 1; }
echo "  ok"

echo "[bootstrap] ensuring KV v2 mount at 'secret/'"
EXISTING=$(curl_vault "$VAULT_ADDR/v1/sys/mounts" 2>/dev/null \
    | grep -o '"secret/":[^}]*}' || true)
if [ -z "$EXISTING" ]; then
    curl_vault -X POST -H "Content-Type: application/json" \
        -d '{"type":"kv","options":{"version":"2"}}' \
        "$VAULT_ADDR/v1/sys/mounts/secret"
    echo "  enabled KV v2 at secret/"
else
    echo "  already enabled (dev mode default)"
fi

# ---- 2. Seed MFA master key -------------------------------------------

MFA_PATH="secret/data/platform/encryption/mfa_master_key"
echo "[bootstrap] seeding MFA master key at platform/encryption/mfa_master_key"
EXISTING=$(curl_vault "$VAULT_ADDR/v1/$MFA_PATH" 2>/dev/null || true)
if echo "$EXISTING" | grep -q '"key"'; then
    echo "  already seeded — skip"
else
    # Generate a 32-byte random key → base64
    if command -v openssl >/dev/null 2>&1; then
        KEY_B64=$(openssl rand -base64 32)
    else
        # Vault container ships busybox; use /dev/urandom directly.
        KEY_B64=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
    fi
    curl_vault -X POST -H "Content-Type: application/json" \
        -d "{\"data\":{\"key\":\"$KEY_B64\"}}" \
        "$VAULT_ADDR/v1/$MFA_PATH" >/dev/null
    echo "  seeded (32-byte AES key, base64-encoded)"
fi

# ---- 3. Per-tenant test field key -------------------------------------

# Hard-coded test tenant ID matches the seed data anh's been using for
# the SSO smoke test (Gmail Olist tenant). Adjust if your dev tenant
# differs.
TEST_TENANT="${KAORI_TEST_TENANT_ID:-f90e0cdb-dc0c-4b91-b86a-92c824aa1103}"
FIELD_KEY_PATH="secret/data/tenant/$TEST_TENANT/encryption/field_key_initial"

echo "[bootstrap] seeding field-encryption key for test tenant $TEST_TENANT"
EXISTING=$(curl_vault "$VAULT_ADDR/v1/$FIELD_KEY_PATH" 2>/dev/null || true)
if echo "$EXISTING" | grep -q '"key"'; then
    echo "  already seeded — skip"
else
    if command -v openssl >/dev/null 2>&1; then
        KEY_B64=$(openssl rand -base64 32)
    else
        KEY_B64=$(head -c 32 /dev/urandom | base64 | tr -d '\n')
    fi
    curl_vault -X POST -H "Content-Type: application/json" \
        -d "{\"data\":{\"key\":\"$KEY_B64\"}}" \
        "$VAULT_ADDR/v1/$FIELD_KEY_PATH" >/dev/null
    echo "  seeded — tenant_field_keys.key_ref should be set to:"
    echo "    vault:tenant/$TEST_TENANT/encryption/field_key_initial"
fi

# ---- Done -------------------------------------------------------------

echo "[bootstrap] complete."
echo
echo "Smoke test:"
echo "  curl -H 'X-Vault-Token: $VAULT_TOKEN' $VAULT_ADDR/v1/$MFA_PATH | head"
echo
echo "Then restart auth-service + ai-orchestrator with KAORI_PROFILE=production"
echo "to refuse env/inline secret fallbacks per K-18."
