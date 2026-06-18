# Vault — secret rotation + KMS auto-unseal recovery

> **Severity:** P0 if Vault is sealed (all services that depend on Vault read can't get secrets), P2 for routine rotation
> **Affects:** all Phase 1.5+ services that switched from env-var to Vault read (per K-18). Rotation event affects only the rotated secret's consumers.
> **First responder:** anh
> **Related:** ADR-0013 (per-tenant secret paths), `infrastructure/vault/policies/`, K-18 (Vault-only secrets in production)

## Symptoms

### Sealed Vault (P0)
- Service startup logs show: `vault.read_failed: api error: status 503: Vault is sealed`.
- `kaori_vault.get_or_env(path)` falls through to env-var fallback (per the chain) — services come up but with stale or missing secrets, often surfacing as auth-mismatch errors against external providers.
- `vault status` returns `Sealed: true`.
- Vault Web UI (port 8200 dev) shows the seal banner.

### Routine rotation (P2)
- Operator scheduled rotation kicked off (e.g. monthly LLM API key cycle).
- Service consumers see auth failures from the external provider on calls made between "secret updated in Vault" and "service config refresh picked up the new value".

## Quick triage (≤ 60 seconds)

- [ ] **Sealed?** `docker exec kaori-vault-1 vault status` — if `Sealed: true`, **GOTO Mitigation 1 (Sealed)**.
- [ ] **Routine rotation in progress?** Check `audit.log` (Vault path) or operator change log — if yes, follow Mitigation 2 (Rotation).
- [ ] **Did Vault Postgres / Raft storage go down?** Vault HA Raft cluster needs quorum (2/3 nodes). `kubectl -n vault get pods` (prod) or `docker compose ps vault` (dev).
- [ ] **Is this just a service that misconfigured `VAULT_ADDR`?** Check the failing service's env. Misconfig != Vault outage.

## Diagnosis

```bash
# 1. Vault status — sealed or unsealed.
docker exec kaori-vault-1 vault status
# look for: Sealed (true/false), HA Mode (active/standby), Raft Cluster Health

# 2. KMS unseal config check — Vault should auto-unseal at start when KMS is reachable.
docker exec kaori-vault-1 vault read sys/seal-status -format=json | jq

# 3. Vault Raft cluster peers (HA mode).
docker exec kaori-vault-1 vault operator raft list-peers
# expect 3 voters (P15-S9 D2 layout: 3 replicas + KMS auto-unseal)

# 4. Audit log — recent reads/writes (helps identify rotation timing + failed reads).
docker exec kaori-vault-1 tail -50 /vault/logs/audit.log

# 5. Service-side — which services failed Vault read recently.
for svc in ai-orchestrator data-pipeline notification-service llm-gateway; do
  echo "=== $svc ==="
  docker logs kaori-$svc-1 --tail 100 2>&1 | grep -iE "vault\.(read|read_failed|fallback)"
done

# 6. KMS reachability (the unseal mechanism).
# AWS KMS:
docker exec kaori-vault-1 aws kms describe-key --key-id "$KAORI_VAULT_KMS_KEY_ID"
# GCP KMS / FPT Cloud KMS — equivalent describe call
```

## Mitigation 1 — Sealed Vault recovery

1. **Confirm KMS is reachable** — the auto-unseal flow needs to call KMS Decrypt. If KMS is the cause, fix that first (separate runbook for the KMS provider).

2. **Force unseal via recovery keys** if KMS is permanently unreachable + you have the recovery key shamir shards:

   ```bash
   # Each operator with a shard runs:
   docker exec -it kaori-vault-1 vault operator unseal
   # paste your shard; repeat until threshold met (default 3-of-5)
   ```

3. **Restart the unseal** if Vault came up before KMS was ready:

   ```bash
   docker compose restart vault
   sleep 10
   docker exec kaori-vault-1 vault status
   # expect Sealed: false if KMS now reachable
   ```

4. **Service-side recovery** — services with Vault fallback (K-18 chain Vault → env → fail) keep running on env-var fallback. Once Vault is unsealed, they pick up Vault reads on next refresh interval (default 5 min for `kaori_vault.py`). To force immediate refresh: restart the service.

## Mitigation 2 — Routine rotation (zero-downtime)

1. **Write the new secret** to a new version path; do NOT overwrite the old:

   ```bash
   docker exec kaori-vault-1 vault kv put secret/platform/llm/anthropic_key \
     value="$NEW_KEY" \
     rotated_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
   # Vault KV v2 keeps version history automatically; old version still readable
   ```

2. **Verify external provider accepts the new key** by issuing a test call from a throwaway client BEFORE rolling services:

   ```bash
   curl -fsS -H "x-api-key: $NEW_KEY" https://api.anthropic.com/v1/models
   ```

3. **Roll services** one at a time, watching for auth-error spikes:

   ```bash
   docker compose restart llm-gateway
   sleep 5
   docker logs kaori-llm-gateway-1 --tail 50 | grep -iE "auth|forbidden|unauthorized"
   # if clean, proceed to next service
   ```

4. **Revoke the old key** at the provider AFTER all consumers confirmed on the new key (typically 1h soak):

   ```bash
   # Provider-side: console / API call to revoke OLD_KEY
   # Vault-side: optionally `vault kv metadata delete -versions=N secret/...` to purge
   ```

## Permanent fix considerations

- **Rotation cadence** — operational secrets (LLM provider keys, SMTP password, Telegram bot token) target 90-day rotation; emergency rotation on suspected leak. Tracked per secret in `docs/runbooks/secret-inventory.md` (write if missing).
- **Per-tenant secret rotation** — Phase 2 — `secret/tenant/{tenant_id}/connectors/*` paths. Each tenant gets their own Vault namespace; rotation is per-tenant, not platform-wide.
- **Rotation automation** — long-term: a Vault-side job that calls the provider's "rotate this key" API + writes new version. Phase 1.5 = manual; document the exact provider rotation API per secret in this file as we learn each one.
- **Service auto-refresh** — `kaori_vault.py` should support a `refresh_now()` that re-reads all currently-cached paths; right now refresh happens only on TTL expiry.

## Postmortem hooks

After every routine rotation:
- Time from "new secret written" to "old secret revoked" — measures soak duration.
- Service auth errors during the cutover window (count, per-service breakdown).
- Was any consumer still on the old key when revoked? If yes, the rotation playbook missed a step — document.

After every sealed-Vault incident:
- Was KMS the cause? If yes, this runbook chains into the KMS provider's runbook — link.
- Did K-18 fallback chain (Vault → env-var) actually save us? Or did the affected service refuse to start? Tells us whether fallback policy needs adjusting.
