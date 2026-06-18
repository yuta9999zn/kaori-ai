# UAT — F-037 Alert Rules (billing-quota dispatcher)

> **Function:** F-037 — Alert Rules backend (billing-quota dispatcher + per-tenant CRUD; Slack/webhook + arbitrary-metric evaluator + FE `/p2/alerts` page deferred to v1 follow-ups)
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role for read (list/get/events); **MANAGER only** for create/update/delete
> **Service:** auth-service (`/api/v1/enterprises/alerts/*` CRUD + `BillingAlertService` dispatcher) + notification-service (outbox poller)
> **DB tables:** `alert_rules`, `alert_events` (migration 028)
> **Owner:** Customer Success driver
> **Prepared:** 2026-05-03

---

## 0. What landed (this PR)

| Surface | Purpose |
|---|---|
| Migration 028 | `alert_rules` (per-tenant CRUD) + `alert_events` (append-only fire history + cooldown source-of-truth). Both tenant-scoped via standard tenant_isolation + admin_bypass RLS policies |
| `BillingAlertService` | Called by `BillingAggregationService.aggregate(...)` after each upsert. On first 80%/95% crossing per month (or after the 6h implicit cooldown), enqueues `quota-alert` to `notification_outbox` and inserts an `alert_events` fire row with the outbox_id |
| Implicit-default rule IDs | Stable sentinels `00000000-0000-0000-0000-000000000080` and `...0095` — billing alerts work for every active enterprise without seeding `alert_rules` per-tenant |
| `quota_alert.html` template | Per-tier upsell text — PILOT → Enterprise Basic, BASIC → Mid, MID → Max, MAX → ROI. Closes the CLAUDE.md §14 "Quota alert email copy" limitation |
| `/api/v1/enterprises/alerts` CRUD | POST/GET/PATCH/DELETE (soft delete) — MANAGER role required for mutations. v0 supports `metric_type='billing_quota_pct'` only; future metrics extend the CHECK additively |
| `/api/v1/enterprises/alerts/events` | Recent fire history (default 50 rows, max 500) including suppressed=true rows for forensics |

Recipient resolution: tenant's first active MANAGER (sorted by `created_at`). No MANAGER → suppressed event with `suppress_reason='no_recipient'`, no enqueue.

Cooldown: 6h on the implicit defaults. Scoped by `(rule_id, enterprise_id)` so two tenants don't share a window.

Best-effort dispatch: `BillingAggregationService` catches and logs any `BillingAlertService` exception so a dispatcher failure never aborts the canonical billing aggregation.

---

## 1. Pre-flight checks

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8091/actuator/health` | `{"status":"UP"}` |
| A2 | `curl -fsS localhost:8094/health` | `{"status":"ok"}` (notification-service running) |
| A3 | Migration 028 applied: `SELECT to_regclass('alert_rules'); SELECT to_regclass('alert_events');` | both return non-NULL |
| A4 | Pilot tenant has at least 1 active MANAGER user | `SELECT COUNT(*) FROM enterprise_users WHERE enterprise_id=:eid AND role='MANAGER' AND status='active';` ≥ 1 |
| A5 | `notification-service` running and polling outbox | check container logs for periodic poll |

If A4 fails, the dispatcher records `suppressed=true` events with `suppress_reason='no_recipient'` and no email is sent. Add a MANAGER user via F-015 first.

---

## 2. End-to-end happy path — first 80% crossing fires email

```bash
# 1. Push usage to ~80% by inserting silver_rows (or run F-017→F-021 wizard).
#    Quick simulation: bypass aggregation logic and call the manual trigger.

EID="<pilot-enterprise-id>"
JWT="<jwt-with-X-User-Role:MANAGER + X-Enterprise-ID:$EID>"

# 2. Confirm starting state — no alert events for this tenant.
psql -c "SELECT COUNT(*) FROM alert_events WHERE enterprise_id='$EID';"
# Expected: 0

# 3. Trigger aggregation (manual cron path).
curl -sX POST http://localhost:8080/api/v1/platform/billing/aggregate-now \
     -H "Authorization: Bearer $PLATFORM_ADMIN_JWT"

# 4. Inspect what happened.
psql -c "SELECT alert_80_fired, alert_95_fired FROM enterprise_monthly_billing
          WHERE enterprise_id='$EID' AND billing_month=date_trunc('month',NOW())::date;"
# Expected: t, f  (or f,f if pilot data is below 80% — go load more silver_rows)

psql -c "SELECT rule_id, suppressed, outbox_id FROM alert_events
          WHERE enterprise_id='$EID' ORDER BY fired_at DESC LIMIT 1;"
# Expected: ...0080 sentinel | f | non-null UUID

# 5. Confirm outbox enqueued.
psql -c "SELECT template, recipient_email, status FROM notification_outbox
          WHERE enterprise_id='$EID' ORDER BY created_at DESC LIMIT 1;"
# Expected: quota-alert | <manager-email> | pending → sent (after dispatcher tick)

# 6. Inspect the rendered email — ask Customer Success to forward the inbox.
#    Confirm the per-tier upsell paragraph matches CLAUDE.md §10:
#       PILOT      → "bước tiếp theo Enterprise Basic"
#       ENT_BASIC  → "bước tiếp theo Enterprise Mid"
#       ENT_MID    → "bước tiếp theo Enterprise Max"
#       ENT_MAX    → "liên hệ Sales / gói ROI"
```

---

## 3. Cooldown — second crossing within 6h is suppressed

```bash
# Run the aggregator a second time (e.g., 30 min later).
curl -sX POST http://localhost:8080/api/v1/platform/billing/aggregate-now \
     -H "Authorization: Bearer $PLATFORM_ADMIN_JWT"

# Two alert_events rows now: the original (suppressed=false, has outbox_id)
# and the second attempt (suppressed=true, outbox_id=NULL).
psql -c "SELECT suppressed, outbox_id, context->>'suppress_reason'
           FROM alert_events WHERE enterprise_id='$EID' ORDER BY fired_at DESC;"
# Expected:
#   t | NULL | cooldown
#   f | <uuid> | NULL
```

---

## 4. CRUD walk-through

```bash
# Auth headers — set once.
H_E="X-Enterprise-ID: $EID"
H_R="X-User-Role: MANAGER"
H_U="X-User-ID: <manager-user-id>"

# --- list (any role) ---
curl -s -H "$H_E" http://localhost:8080/api/v1/enterprises/alerts | jq
# Expected: { data: [], meta: { total: 0, page: 1, limit: 20 } }

# --- create (MANAGER only) ---
curl -sX POST -H "$H_E" -H "$H_R" -H "$H_U" -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/enterprises/alerts -d '{
    "name": "Quota 90% custom",
    "description": "Sớm hơn ngưỡng 95% mặc định",
    "metric_type": "billing_quota_pct",
    "operator": "gte",
    "threshold_value": 90.0,
    "channel": "email",
    "cooldown_seconds": 3600
  }' | jq
# Expected: 201 + data.rule_id (UUID)

# --- update threshold ---
curl -sX PATCH -H "$H_E" -H "$H_R" -H "$H_U" -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/enterprises/alerts/<rule_id> -d '{ "threshold_value": 88.0 }' | jq

# --- recent events (any role) ---
curl -s -H "$H_E" http://localhost:8080/api/v1/enterprises/alerts/events?limit=20 | jq

# --- soft delete (MANAGER only) ---
curl -sX DELETE -H "$H_E" -H "$H_R" -H "$H_U" \
  http://localhost:8080/api/v1/enterprises/alerts/<rule_id> | jq
# Expected: { data: { rule_id, status: "deleted" } }
# Row stays in DB with deleted_at set; subsequent list omits it.
```

---

## 5. Negative paths

| Test | Expected |
|---|---|
| `GET /alerts` without `X-Enterprise-ID` | 401 RFC 7807 with `type=/docs/errors/missing-enterprise-id` |
| `POST /alerts` with `X-User-Role: VIEWER` | 403 RFC 7807 with detail "Only MANAGER can manage alert rules" |
| `POST /alerts` with `metric_type: "unknown"` | 400 with detail listing allowed metrics |
| `POST /alerts` with `threshold_value: -1` | 400 with detail "threshold_value must be ≥ 0" |
| `POST /alerts` with `cooldown_seconds: 999999` | 400 with detail "cooldown_seconds must be ≤ 86400 (24h)" |
| `PATCH /alerts/{id}` with empty body `{}` | 400 with detail "at least one field must be provided" |
| `GET /alerts/{nonexistent-uuid}` | 404 RFC 7807 with `type=/docs/errors/alert-rule-not-found` |
| Cross-tenant read (`X-Enterprise-ID` of tenant B, rule belongs to tenant A) | 404 (RLS makes the row invisible — same shape as missing) |

---

## 6. Forensics queries

```sql
-- "Customer says they didn't receive the alert email"
SELECT ae.fired_at, ae.suppressed, ae.outbox_id,
       no.status, no.attempts, no.last_error, no.sent_at
  FROM alert_events ae
  LEFT JOIN notification_outbox no ON no.outbox_id = ae.outbox_id
 WHERE ae.enterprise_id = '<eid>'
 ORDER BY ae.fired_at DESC
 LIMIT 20;

-- "Why is this rule firing too often / not firing"
SELECT rule_id, suppressed, fired_at,
       context->>'suppress_reason' AS reason
  FROM alert_events
 WHERE enterprise_id = '<eid>' AND rule_id = '<rule_id>'
 ORDER BY fired_at DESC LIMIT 50;

-- Platform-wide: how many tenants are at warn (80%+) or critical (95%+) right now
SELECT COUNT(*) FILTER (WHERE alert_95_fired) AS at_critical,
       COUNT(*) FILTER (WHERE alert_80_fired AND NOT alert_95_fired) AS at_warn
  FROM enterprise_monthly_billing
 WHERE billing_month = date_trunc('month', NOW())::date;
```

---

## 7. Sign-off checklist

- [ ] Migration 028 applies cleanly on Testcontainers (FlywayMigrationIT cold-boot)
- [ ] `BillingAlertServiceTest` 7/7 + `AlertRuleServiceTest` 12/12 + `BillingAggregationServiceTest` 7/7 green
- [ ] WorkspaceControllerIT 10/10 still green (slice context boots with new beans)
- [ ] One real billing aggregation tick produces exactly one outbox row per crossing per tenant
- [ ] Email arrives in Customer Success inbox with the right per-tier paragraph
- [ ] Cross-tenant CRUD attempts return 404 (RLS-driven)
- [ ] CLAUDE.md §14 "Quota alert email copy" limitation marked closed

---

## 8. Frontend walk-through (FE PR follow-up)

`/p2/alerts` page loads with two tabs:

**Tab "Lịch sử"** (default) — recent fire events:
- 4 KPI tiles: fired in last 7 days · suppressed in last 7 days · total events · latest fire (relative time)
- Search box + checkbox to toggle suppressed events on/off
- Table: rule name (resolves sentinel UUIDs to "Hạn mức 80% (mặc định)" / "Hạn mức 95% (mặc định)") · metric · value/threshold (with operator symbol) · timestamp · status badge ("Đã enqueue" green vs "Bị nén" with reason)

**Tab "Quy tắc"** — alert_rules CRUD:
- Empty state with primary "Tạo quy tắc đầu tiên" button when no custom rules exist (note that implicit defaults still work)
- Table: name · metric/operator/threshold · target email (or "MANAGER mặc định") · cooldown · active badge · edit/delete actions
- "+ Tạo quy tắc" header button opens modal editor (same modal handles edit). Slack/webhook + DSL editor are intentionally NOT in the form because BE doesn't support them in v0
- Delete = soft delete (browser `confirm()` first), row disappears from list but events remain in history

Bottom hint always visible reminds users that 80%/95% defaults fire automatically without needing custom rules.

| Test | Expected |
|---|---|
| First load with no custom rules | "Lịch sử" tab shows seeded MSW events (5 rows) — 80% fire, 95% fire, 95% suppressed (cooldown), custom-rule fire, custom-rule suppressed (no_recipient). "Quy tắc" tab shows 2 seeded rules. |
| Click "+ Tạo quy tắc" → fill form → Lưu | New rule appears at top of rules table, count badge bumps |
| Click pencil icon on a row → modify threshold → Lưu | Row updates in place |
| Click trash icon → confirm | Row disappears, count badge decreases |
| Switch to Lịch sử tab | Renders existing events plus the implicit-default fires labelled correctly |
| Toggle "Hiện các sự kiện bị nén" off | Suppressed rows hide |
| Test with `notifyswr` MSW disabled (real BE) | Same UI, real `/api/v1/enterprises/alerts*` data — must include `X-Enterprise-ID` + `X-User-Role: MANAGER` headers via JWT |
