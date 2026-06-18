# UAT — F-060 North Star Tile + Customer Action

> **Function:** F-060 — Canonical `gold_features.is_actioned` column + dashboard tile + per-customer action toggle
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role can read the tile + at-risk list; any role can flip is_actioned (no role gate yet — pilot trust model is "audit trail catches abuse"; future v1 consideration: ANALYST+)
> **Service:** ai-orchestrator (`/api/v1/customers/*`, `/api/v1/dashboard/north-star`)
> **DB tables:** `gold_features` (existing — migration 018 pre-baked `is_actioned`/`actioned_at`; migration 032 added `actioned_by_user`)
> **Kafka topic:** `kaori.feedback.actions` (existing — enum extended with `customer.actioned` / `customer.unactioned`)
> **Owner:** Customer Success driver
> **Prepared:** 2026-05-03

---

## 0. What landed (this PR)

| Surface | Purpose |
|---|---|
| Migration 032 | Adds `actioned_by_user UUID` to gold_features + partial index `idx_gold_features_actioned WHERE is_actioned=TRUE` for the tile + audit query hot paths |
| `POST /api/v1/customers/{customer_external_id}/action` | Toggle is_actioned for one (enterprise_id, customer_external_id). Idempotent (same value re-write OK). Best-effort Kafka emit. 404 when customer not in gold_features |
| `GET  /api/v1/dashboard/north-star` | Tile payload — total_at_risk_vnd, resolved_vnd, resolution_rate_pct, at_risk_count, actioned_count, recent_actions[] (5 latest) |
| `GET  /api/v1/customers/at-risk` | Cursor-paginated list (revenue_at_risk DESC, customer_external_id DESC). Filterable by `?actioned=true\|false` |
| Kafka enum extension | `customer.actioned` + `customer.unactioned` added (additive — contract guard PASS) |
| CLAUDE.md §14 | North Star half-closed limitation **fully closed** |

Formula in v0:
```
SUM(revenue_at_risk WHERE revenue_at_risk > 0 AND is_actioned = TRUE)
```

`revenue_at_risk > 0` is the v0 proxy for `churn_risk_label='HIGH'` because the Phase 1 aggregator (services/data-pipeline/.../gold/aggregator.py) only writes non-zero `revenue_at_risk` for model-flagged customers. F-051 explicit classifier later narrows to a label column.

Sprint 7 PR D's `decision_actions` side table stays in place for the per-decision toggle on `/decisions` — that's a different product surface. The dashboard tile + ROI rollup now key off the canonical column.

---

## 1. Pre-flight checks

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8093/health` | ok |
| A2 | Migration 032 applied: `SELECT column_name FROM information_schema.columns WHERE table_name='gold_features' AND column_name='actioned_by_user';` | one row |
| A3 | Pilot tenant has gold_features rows with `revenue_at_risk > 0` | needed — run a pipeline + analysis to populate; otherwise tile shows zero state |
| A4 | Kafka topic `kaori.feedback.actions` exists / auto-creates | yes |

---

## 2. Happy path — toggle + tile + Kafka

```bash
EID=<pilot-enterprise-id>
UID=<analyst-user-id>
CUST=<a customer_external_id with revenue_at_risk > 0>
JWT=<JWT carrying X-Enterprise-ID + X-User-ID>

# 1. Snapshot tile before action
curl -s http://localhost:8080/api/v1/dashboard/north-star \
     -H "Authorization: Bearer $JWT" | jq

# 2. List at-risk customers, find $CUST
curl -s http://localhost:8080/api/v1/customers/at-risk?limit=20 \
     -H "Authorization: Bearer $JWT" | jq '.items[] | {customer_external_id, revenue_at_risk, is_actioned}'

# 3. Mark $CUST as actioned
curl -sX POST http://localhost:8080/api/v1/customers/$CUST/action \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{ "is_actioned": true, "notes": "Đã liên hệ — khách ký hợp đồng năm." }' | jq

# Expected 200 + customer_external_id, is_actioned=true, actioned_at, actioned_by_user.

# 4. Re-snapshot tile — resolved_vnd and actioned_count should bump
curl -s http://localhost:8080/api/v1/dashboard/north-star \
     -H "Authorization: Bearer $JWT" | jq

# 5. Confirm Kafka emit
docker exec kaori-kafka-1 kafka-console-consumer \
    --bootstrap-server kafka:9092 --topic kaori.feedback.actions \
    --from-beginning --max-messages 1 | jq

# Expected payload action: "customer.actioned"

# 6. Filter list to actioned-only
curl -s "http://localhost:8080/api/v1/customers/at-risk?actioned=true" \
     -H "Authorization: Bearer $JWT" | jq

# 7. Revert (e.g. typo)
curl -sX POST http://localhost:8080/api/v1/customers/$CUST/action \
     -H "Authorization: Bearer $JWT" -H "Content-Type: application/json" \
     -d '{ "is_actioned": false }' | jq
# action: "customer.unactioned" on Kafka
```

---

## 3. Negative paths

| Test | Expected |
|---|---|
| POST `/customers/UNKNOWN/action` | 404 with detail mentioning gold_features |
| POST with `notes` 2001 chars | 422 (Pydantic max_length=2000) |
| POST without X-Enterprise-ID header | 422 (FastAPI required header) |
| GET `/customers/at-risk?cursor=not-base64` | 400 `Invalid cursor` |
| GET `/customers/at-risk?limit=1000` | 422 (le=500) |
| Cross-tenant customer toggle | 404 (RLS hides the row → UPDATE returns no rows → handler converts) |
| Kafka emit failure (kill kafka mid-call) | DB write succeeds (200), log shows `customer.action.kafka_emit_failed` |

---

## 4. Forensics queries

```sql
-- "Top 10 actioners this week"
SELECT actioned_by_user, COUNT(*) AS customers_actioned,
       SUM(revenue_at_risk) AS resolved_vnd
  FROM gold_features
 WHERE enterprise_id = '<eid>'
   AND is_actioned = TRUE
   AND actioned_at > NOW() - INTERVAL '7 days'
 GROUP BY actioned_by_user
 ORDER BY resolved_vnd DESC LIMIT 10;

-- "Resolution rate trend (current month)"
SELECT DATE_TRUNC('day', actioned_at)::date AS day,
       SUM(revenue_at_risk) AS resolved_vnd,
       COUNT(*)              AS customers_actioned
  FROM gold_features
 WHERE enterprise_id = '<eid>' AND is_actioned = TRUE
   AND actioned_at >= DATE_TRUNC('month', NOW())
 GROUP BY day ORDER BY day;

-- "Stale at-risk: flagged but not actioned in > 14 days"
SELECT customer_external_id, revenue_at_risk, computed_at
  FROM gold_features
 WHERE enterprise_id = '<eid>'
   AND revenue_at_risk > 0
   AND is_actioned = FALSE
   AND computed_at < NOW() - INTERVAL '14 days'
 ORDER BY revenue_at_risk DESC LIMIT 50;
```

---

## 4b. Frontend walk-through (this FE PR)

`/p2/customers/at-risk` lands with three sections stacked top-down:

**North Star tile (4 KPIs)**:
- `Doanh thu đã giải quyết` (highlighted gold) — primary North Star number
- `Tổng doanh thu rủi ro` — denominator
- `Tỷ lệ giải quyết` — % to 1 decimal
- `Khách đã xử lý` — count

**Hoạt động gần đây** card — 5 latest actioned customers with revenue + relative time. Hidden when no actions exist.

**Filter bar** — 3 chips: Chưa xử lý (default) · Đã xử lý · Tất cả. Toggling refetches the list with `?actioned=true|false` or unset.

**Customer table** — sorted revenue DESC. Columns: customer_external_id (mono) · revenue · last purchase · order count · status badge · action button.
- Pending row → primary "Đánh dấu đã xử lý" button → `prompt()` for optional notes → POST → success banner + tile refresh
- Resolved row → tertiary "Bỏ đánh dấu" button → `confirm()` warning → POST → tile refresh
- Pagination at bottom: cursor-stack so "Trang trước" works after multiple "Trang sau"

Footer hint reminds users mỗi toggle phát Kafka `kaori.feedback.actions`.

`NorthStarTile` is exported from the template — a follow-up PR can import it into `/dashboard` or `/p2/dashboard/overview` without rewiring.

| FE test | Expected |
|---|---|
| First load on `/p2/customers/at-risk` (MSW dev) | Tile shows 8 at-risk total · 3 actioned · resolution_rate ≈ 35.5%; table filtered to "Chưa xử lý" with 5 rows |
| Click "Đã xử lý" filter | Table shows 3 rows, all with success badge |
| Click "Đánh dấu đã xử lý" on `CUST-A0001` → fill notes → submit | Success banner; tile resolved jumps; row moves out of "Chưa xử lý" filter |
| Click "Bỏ đánh dấu" on `CUST-B0042` → confirm | Tile resolved drops; row moves to "Chưa xử lý" |
| Cancel the prompt | No request fires |
| Pagination "Trang sau" then "Trang trước" | Returns to original page (cursor stack) |
| Visit with MSW disabled (real BE, JWT) | Same UI, real /api/v1/customers/at-risk + /dashboard/north-star round-trip |

---

## 5. Sign-off

- [ ] Migration 032 applies cleanly (FlywayMigrationIT cold-boot 32/32)
- [ ] `pytest tests/test_north_star.py` 12/12 green
- [ ] ai-orchestrator full suite 334/334 green (was 322, +12)
- [ ] OpenAPI snapshot refreshed (32 paths, was 29)
- [ ] FE types regenerated (`frontend/lib/api/types/orchestrator.d.ts`)
- [ ] Schema snapshot regenerated (`scripts/schema-drift.py --check` PASS)
- [ ] Kafka contract guard PASS (`scripts/check-kafka-contracts.py` — additive enum extension)
- [ ] One real toggle round-trip → tile updates + Kafka event captured
- [ ] CLAUDE.md §14 North Star limitation marked **closed**

---

## 6. Deferred (v1 follow-ups)

- **FE dashboard tile** — wire the JSON into `/p2/dashboard` (tile component); currently consumable only via curl
- **FE customer-list page** — `/p2/customers/at-risk` table + per-row "Đánh dấu đã hành động" button; templates haven't been drafted yet
- **F-051 explicit churn classifier** — adds `churn_risk_label` column so the formula stops needing `revenue_at_risk > 0` as a proxy
- **decision_actions → gold_features.is_actioned propagation** — when a decision is marked actioned (Sprint 7 PR D path), surface the customer linkage and bump gold_features. Today the two surfaces are independent
- **Bulk action endpoint** — POST `/customers/action/bulk` with array of customer_external_ids. Pilot today does one-by-one which is fine for a single-digit at-risk count; ENT_MID+ will want bulk
