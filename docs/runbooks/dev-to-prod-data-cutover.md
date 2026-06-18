# Dev → prod data cutover

> **Status:** TODO pointer from `k8s-fpt-cloud-provision.md` Step 11. Closes the missing runbook em referenced when shipping the K8s provisioning doc 1 commit prior (`41eb7c3` 2026-05-19).
> **Severity:** P1 (customer-visible — anh runs this once per customer when promoting from pilot box → FPT prod cluster)
> **Affects:** Tenant data continuity. Done wrong = field-encrypted data unreadable + Bronze files missing + pipeline_runs orphaned.

## When to run

Trigger any of:
- Pilot customer (Olist) promotes from anh's laptop docker-compose → FPT prod K8s cluster (Step 11 of `k8s-fpt-cloud-provision.md`)
- Customer #2 onboards — em provisions a fresh tenant in prod, NOT a cutover
- Disaster recovery: dev backup → prod re-hydrate after prod corruption (rare; SOC 2 Phase 2 covers proper DR)

If anh is just doing a staging refresh (dev → staging), the same steps apply with staging URLs swapped in. Production carries the read-only-freeze step; staging usually doesn't.

## Pre-flight gate

Em refuses to run cutover unless ALL of:

| Gate | Verify |
|---|---|
| Prod cluster healthy | `kubectl get pods -n kaori -A` — 0 CrashLoopBackOff / Pending |
| Prod Postgres reachable + empty | `psql -h <prod-pg> -c "SELECT COUNT(*) FROM pipeline_runs"` returns 0 |
| Prod Vault unsealed + seeded | `vault kv get platform/encryption/mfa_master_key` returns a key (per `vault-rotation.md`) |
| Prod MinIO bucket exists | `mc ls prod-minio/kaori-bronze` → empty bucket exists |
| Pilot box pg_dump tested last 7 days | `ls -la /backups/kaori-dev-*.dump` recent |
| Customer notified | Email sent — confirmed 30-min downtime window |

## Step 1 — Read-only freeze on dev

```bash
# Stop anh's ingestor + workflow worker so no new writes land while em dumps
docker compose -f docker-compose.dev.yml stop data-pipeline ai-orchestrator
# Auth + gateway stay UP — users can log in + read; just no mutations
docker compose -f docker-compose.dev.yml ps
```

Verify by attempting an upload from FE — expect 503 "service unavailable" on `/api/v1/upload`.

Customer sees: "Hệ thống đang nâng cấp dữ liệu, vui lòng quay lại sau 30 phút."

## Step 2 — Postgres dump

```bash
# Full dump including schema + data + Flyway schema_history
docker exec kaori-postgres-1 pg_dump \
  -U kaori \
  -d kaori_dev \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file=/tmp/kaori-cutover-$(date +%Y%m%d-%H%M).dump

# Copy out
docker cp kaori-postgres-1:/tmp/kaori-cutover-*.dump ./

# Verify dump is well-formed
pg_restore --list ./kaori-cutover-*.dump | head -20
# Expect lines like "; SCHEMA - public" + "TABLE - pipeline_runs" etc
```

Em recommend `--format=custom` (NOT plain SQL) so anh gets parallel restore + selective filtering at restore time.

**Sanity check the dump size**:
```bash
ls -lh ./kaori-cutover-*.dump
# Should be roughly the same order as: docker exec kaori-postgres-1 du -sh /var/lib/postgresql/data
# If 10× smaller, dump truncated — re-run with --verbose to debug
```

## Step 3 — Postgres restore on prod

Path depends on which DBaaS option anh picked in `k8s-fpt-cloud-provision.md` Step 5:

**Path A (FPT managed Postgres)**:
```bash
# Upload dump to a bastion in FPT VPC (FPT-managed DB doesn't accept WAN connections)
scp kaori-cutover-*.dump bastion-hcm:/tmp/

# From bastion
ssh bastion-hcm
pg_restore \
  -h <fpt-pg-private-endpoint> \
  -U kaori_prod \
  -d kaori_prod \
  --no-owner \
  --no-privileges \
  --jobs=4 \
  /tmp/kaori-cutover-*.dump
```

**Path B (CNPG in cluster)**:
```bash
# Copy into the primary Postgres pod
kubectl cp kaori-cutover-*.dump kaori/postgres-primary-0:/tmp/

# Restore (postgres user owns this; em never use kaori user for ops)
kubectl exec -n kaori postgres-primary-0 -- pg_restore \
  -U postgres \
  -d kaori_prod \
  --no-owner \
  --no-privileges \
  --jobs=4 \
  /tmp/kaori-cutover-*.dump
```

**Verify row counts match dev**:
```bash
# Run on BOTH dev + prod, compare side-by-side
psql -c "SELECT 'pipeline_runs' AS t, COUNT(*) FROM pipeline_runs
         UNION ALL SELECT 'bronze_files', COUNT(*) FROM bronze_files
         UNION ALL SELECT 'silver_pipeline_rows', COUNT(*) FROM silver_pipeline_rows
         UNION ALL SELECT 'enterprise_users', COUNT(*) FROM enterprise_users
         UNION ALL SELECT 'sso_identities', COUNT(*) FROM sso_identities
         UNION ALL SELECT 'tenant_field_keys', COUNT(*) FROM tenant_field_keys;"
```

All 6 row counts must match exactly. If not, dump corruption — re-run Step 2 + 3.

## Step 4 — Flyway schema_history sync

The schema_history table tracks which migrations have run. After pg_restore it carries dev's history. Em verify prod Flyway baseline matches:

```bash
# In prod (Path B example)
kubectl exec -n kaori postgres-primary-0 -- psql -U postgres -d kaori_prod -c \
  "SELECT version, description, success FROM flyway_schema_history ORDER BY installed_rank DESC LIMIT 10;"

# Expected: most recent row matches what em see in dev — 105 currently (admin-bypass RLS drift fix)
# If prod is BEHIND, that means anh's auth-service Flyway will try to re-apply migs already in the dump → checksum mismatch
# Mitigation: SPRING_FLYWAY_VALIDATE_ON_MIGRATE=false on the FIRST auth-service start; flip back to true after first successful boot
```

Em flagged this exact failure mode in [[project_2026_05_18_sso_google_live]] when local Flyway state went inconsistent post-renumber of mig 080-083. The `SPRING_FLYWAY_VALIDATE_ON_MIGRATE=false` knob is the proven workaround.

### Step 4b — ⚠️ Stubbed pilot migrations (schema_history LIES)

**Critical, easy to miss.** The pilot DB has migrations whose `flyway_schema_history` row says `success=true` but whose **DDL was never executed** — hand-inserted to skip the heavy Phase 2.5/2.6/2.7/2.8 schema on the lean pilot DB. Full map: [`pilot-db-state.md`](pilot-db-state.md). Detect the ones still missing (the `NOT ILIKE` clause excludes rows we've since back-filled and marked honest):

```bash
psql -U kaori -d kaori -c \
  "SELECT version, description FROM flyway_schema_history
    WHERE description ILIKE '%skip phase2 DDL%'
      AND description NOT ILIKE '%DDL applied to pilot%'
    ORDER BY CAST(version AS INT);"
# As of 2026-05-24 this returns migs 085-100 (101-104 were back-filled to pilot, so excluded).
```

Because the dump carries this history, prod Flyway will see 085-100 as **already applied and skip them** — so prod silently inherits the same missing schema: **workflow execution** (`workflow_runs` 088, `workflow_events` 094, `workflow_idempotency_records` 095, approvals/forms/outputs), **adoption + NOV** (090), **ontology/lineage/governance** (096-098), **policy engine + `tenant_quotas`** (099-100), and the extended node catalog (085-087). No error is raised; the gap surfaces only when a customer runs a workflow / hits a governed endpoint.

**Remediation — apply the real DDL manually after restore, before go-live**, in version order (some migs ALTER tables created by earlier stubbed ones — e.g. 100 needs 099's `tenant_quotas`). Files are idempotent-friendly (`CREATE TABLE IF NOT EXISTS`, `ON CONFLICT DO NOTHING`, `CREATE OR REPLACE FUNCTION`); do NOT delete the history rows (would force an out-of-order re-apply behind mig 105):

```bash
for n in 085 086 087 088 089 090 091 092 093 094 095 096 097 098 099 100; do
  f=$(ls infrastructure/postgres/migrations/${n}_*.sql | head -1)
  echo "applying real DDL for mig $n: $(basename "$f")"
  psql -U <prod_user> -d kaori_prod -v ON_ERROR_STOP=1 -f "$f"
done
# Spot-check a few feature tables now exist:
psql -U <prod_user> -d kaori_prod -c "\dt workflow_runs"
psql -U <prod_user> -d kaori_prod -c "\dt tenant_quotas"
```

> Re-run the detection query each cutover; don't assume. As pilot back-fills more migs (marking them `[DDL applied to pilot <date>]`), the query auto-narrows.

## Step 5 — Tenant field-key re-encryption

The hardest step. Tenant field-encryption keys live in `tenant_field_keys.key_ref` — em wired these to Vault paths in commit `d6a1113` (Vault production cutover) per [[project_2026_05_18_continue_session]]. Dev Vault and prod Vault have DIFFERENT root tokens + DIFFERENT seeded keys.

The pg_dump carries the ciphertext + the dev `key_ref` Vault path. After restore, ciphertext is unreadable from prod because prod Vault doesn't have those keys.

**Two paths**:

**Path X — Re-key in-place (recommended for production)**

1. For each tenant, run the re-encrypt worker em shipped commit `6a18352` (mig 080 + `shared/field_key_rotation.py` + `/p2/auth/field-key/reencrypt`):

```bash
# Get list of tenants
psql -c "SELECT enterprise_id FROM enterprises WHERE tenant_status='active';"

# For each tenant — call the rotation endpoint with prod's auth context
foreach ($tid in $tenants) {
  curl -X POST "https://api.kaori.io/api/v1/p2/auth/field-key/reencrypt" \
    -H "Authorization: Bearer <prod-admin-jwt>" \
    -H "X-Enterprise-ID: $tid"
  # Worker reads ciphertext using dev's key_ref (which anh must seed
  # temporarily in prod Vault to make this work — see Path Y if you'd
  # rather not), generates a fresh prod key, re-encrypts each row,
  # writes back with new key_ref pointing at prod Vault path
}

# Verify
curl "https://api.kaori.io/api/v1/p2/auth/field-key/reencrypt/status?enterprise_id=$tid" \
  -H "Authorization: Bearer <prod-admin-jwt>"
# Expect status='completed' + rows_reencrypted matching the encrypted-column count
```

**Path Y — Seed dev keys into prod Vault, then rotate**

If anh prefers not to expose dev keys to prod Vault even temporarily:
1. Run the re-encrypt locally on the dev box with prod Vault as the target (write only)
2. Dump → restore the rotated data
3. Skip the in-prod re-encryption entirely

Either works; Path X is the documented production-cutover pattern.

## Step 6 — Bronze MinIO bucket migration

Bronze stores immutable file bytes by SHA-256. Em mirror dev bucket → prod bucket using `mc` (MinIO Client):

```bash
# Configure aliases
mc alias set dev-minio http://localhost:9000 <dev-access-key> <dev-secret-key>
mc alias set prod-minio https://minio.kaori.io <prod-access-key> <prod-secret-key>

# Mirror (resumable; safe to re-run)
mc mirror --preserve dev-minio/kaori-bronze prod-minio/kaori-bronze

# Verify count match
mc ls --recursive dev-minio/kaori-bronze | wc -l
mc ls --recursive prod-minio/kaori-bronze | wc -l
```

For large pilots (>10 GB Bronze) em recommend running this in parallel with Step 2-5 — `mc mirror` is read-only on dev and prod-write-only on prod.

## Step 7 — pgvector index rebuild

The HNSW indexes on `memory_l3.embedding` + `bronze_files.docsage_embedding` (mig 067) are NOT included in pg_dump's default mode. After restore em rebuild:

```sql
-- Run on prod Postgres
REINDEX INDEX CONCURRENTLY idx_memory_l3_embedding;
REINDEX INDEX CONCURRENTLY idx_bronze_files_docsage_embedding;
-- Add other HNSW indexes if more got added since this runbook ship
```

Takes 5-30 min depending on row count. RAG quality drops to "linear scan" during rebuild — em accept the temporary slowdown since cutover is a planned window.

## Step 8 — Ollama model warmup

Prod cluster's Ollama pod cold-starts at first inference. Em pre-pull + pre-warm:

```bash
kubectl exec -n kaori ollama-0 -- ollama pull qwen2.5:14b
kubectl exec -n kaori ollama-0 -- ollama pull bge-m3
kubectl exec -n kaori ollama-0 -- ollama pull qwen2.5vl:7b   # OCR adapter, P2.5 commit 1c4667c

# Warm-up: one inference call to load model into RAM
kubectl exec -n kaori ollama-0 -- curl -s http://localhost:11434/api/generate \
  -d '{"model":"qwen2.5:14b","prompt":"hello","stream":false}' | jq .response
```

Without warmup, the first customer query takes 30-60s (model load + inference). After warmup, normal 1-3s.

## Step 9 — Smoke test (production-side)

```bash
# Hit the API surface via prod ingress
curl -fsS https://api.kaori.io/health
curl -fsS https://api.kaori.io/api/v1/health  # gateway

# Auth round-trip — log in with the migrated admin user
curl -X POST https://api.kaori.io/api/v1/p2/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@<customer-domain>","password":"<password>"}' \
  -i

# Pipeline read — list recent runs for the migrated tenant
curl https://api.kaori.io/api/v1/pipelines?limit=5 \
  -H "Authorization: Bearer <jwt-from-above>"
```

Expected: same pipeline_runs em see in dev appear in prod. Field-encrypted columns (email, phone) render correctly — if they show as garbage, Step 5 didn't take.

## Step 10 — DNS swap + sticky-session drain

```bash
# Update Route 53 / Cloudflare / GoDaddy DNS
# api.kaori.io  A  <new FPT cluster ingress IP>  TTL=60
# app.kaori.io  A  <same IP>                      TTL=60

# Wait for TTL flush (5-15 min typical for VN ISPs)
dig +short api.kaori.io
# Confirm resolves to new IP

# Drain old pilot box — give existing browser sessions 10 min to drift
# Then full shutdown
docker compose -f docker-compose.dev.yml down
```

Customer-visible: 5-15 min "Đang khôi phục dịch vụ" message on cached old-IP browsers; new visitors hit prod immediately.

## Step 11 — Customer confirmation + monitoring

```bash
# Watch Grafana for 30 min post-cutover
# - Request volume on api.kaori.io recovers to dev baseline
# - p95 latency stays under SLO (per OBS-017 alerts em shipped)
# - 0 spike on kaori_ai_calls_total{status="error"}
# - 0 spike on RFC 7807 4xx rate
```

Send "cutover complete" email to customer. Watch on-call for 24h.

## Rollback procedure

If em catch a regression in the first hour:

```bash
# 1. DNS swap back
# api.kaori.io  A  <pilot box IP>  TTL=60

# 2. Restart pilot box services
docker compose -f docker-compose.dev.yml up -d

# 3. Production cluster stays UP — em do NOT teardown until customer
#    has been on prod for ≥7 days incident-free

# 4. Customer-visible: 5-15 min for DNS flip
```

Em keep the pilot box pg_dump from Step 2 untouched in prod for ≥30 days post-cutover. If prod corruption surfaces late, re-running Steps 3-7 from that dump restores last-known-good.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pg_restore` errors with "permission denied" | Restored as `kaori` instead of `postgres` superuser | Re-run with `--role=postgres` or as the postgres user in the prod pod |
| Row counts off by 1 between dev + prod | Read-only freeze (Step 1) too late — a row landed mid-dump | Acceptable for pipeline_runs (the late row is incomplete anyway); UNACCEPTABLE for enterprise_users / tenant_field_keys → re-dump |
| Auth-service Flyway fails with "Validate failed: checksum mismatch" | dev + prod Flyway baselines drift | Set `SPRING_FLYWAY_VALIDATE_ON_MIGRATE=false`, restart auth-service, run app once, flip back to true |
| Encrypted email columns render as `<base64-garbage>` | Step 5 didn't run OR ran with wrong source key_ref | Re-run `/p2/auth/field-key/reencrypt` per affected tenant; check Vault is reachable from auth-service pod |
| RAG queries return empty results | Step 7 reindex didn't complete | `\d memory_l3` in psql — look for "INVALID" status on idx_memory_l3_embedding; REINDEX again |
| First customer query takes 60s | Step 8 warmup skipped | Run the warmup commands; subsequent queries normal |
| MinIO 404 on Bronze file fetch | Step 6 mirror incomplete | `mc mirror` is resumable — re-run; check `--preserve` flag was set so timestamps preserved |
| DNS still resolves to old IP after 30 min | ISP cache | Hit `https://dns.google/resolve?name=api.kaori.io` to bypass; force-flush via `ipconfig /flushdns` (Windows) or `sudo dscacheutil -flushcache` (macOS) |

## What this runbook does NOT cover

- **Live migration** (zero downtime via logical replication + cutover) — Phase 3, when SLA forbids the 30-min window
- **Multi-tenant cutover** (>1 tenant at a time) — same procedure but anh runs Step 5 in parallel per tenant; em recommend serializing the first 3 customers to limit blast radius
- **Kafka topic migration** — em's pilot doesn't use Kafka yet (Phase 1 legacy topics in dev only); Phase 2 customer #1 forces Kafka cutover, separate runbook needed
- **Clickhouse Silver tier migration** — ClickHouse 3-node deferred to P15-S10+ runtime; not in scope until that ships
- **Cross-region migration** — Phase 3 multi-region (HCM + HN) DR target

## Related

- `k8s-fpt-cloud-provision.md` Step 11 — em referenced this runbook there; closed the TODO
- `vault-rotation.md` — per-tenant Vault secret rotation (background for Step 5)
- `mfa-key-rotation.md` — MFA master key cadence (similar re-encrypt pattern)
- `field-encryption-key-rotation.md` — same re-key worker em invoke in Step 5
- mig 080 + `services/ai-orchestrator/shared/field_key_rotation.py` — re-encrypt worker implementation
- mig 067 — pgvector HNSW indexes that need REINDEX (Step 7)
- ADR-0013 — RLS multi-tenancy (em respect tenant boundary during cutover by running Step 5 per-tenant, not bulk)
