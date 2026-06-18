# UAT — F-036 Decision Override

> **Function:** F-036 — Decision detail + override + revoke (SHAP explain layer + FE detail page deferred to v1)
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role can read; ANALYST+ recommended for override (no role gate enforced server-side yet — pilot trust model is "anyone with JWT can override; audit trail catches abuse")
> **Service:** ai-orchestrator (`/api/v1/decisions/*`)
> **DB tables:** `decision_audit_log` (existing) · `decision_overrides` (migration 031)
> **Kafka topic:** `kaori.feedback.actions` (new — schema in `infrastructure/kafka/schemas/kaori.feedback.actions.json`)
> **Owner:** Customer Success driver
> **Prepared:** 2026-05-03

---

## 0. What landed (this PR)

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/decisions/{id}` | Decision detail with overrides history (latest non-revoked is the effective one) + is_actioned flag from decision_actions join |
| `POST /api/v1/decisions/{id}/override` | Append a new override row + emit `kaori.feedback.actions` action='override.created' |
| `POST /api/v1/decisions/{id}/override/{oid}/revoke` | Soft-revoke a prior override + emit action='override.revoked' |

Migration 031 — `decision_overrides`:
- Append-only (UPDATE only on the soft-revoke columns; never on `override_value` / `reason`)
- FK to `decision_audit_log(decision_id)` ON DELETE CASCADE
- Standard tenant_isolation + admin_bypass RLS
- 3 indexes: per-decision history, tenant rollup, partial active-only for the FE join

Kafka topic `kaori.feedback.actions`:
- 2 actions in v0: `override.created` · `override.revoked`
- Required fields: override_id, decision_id, enterprise_id, action, occurred_at
- Optional: decision_type, original_value, override_value, reason, user_id
- Schema is additive-only (CI guard `scripts/check-kafka-contracts.py` enforces)
- Producers today: `services/ai-orchestrator/routers/decisions.py`
- Consumers (planned): F-074 fine-tuning trigger · F-060 ROI rollup · audit/compliance exporter

Best-effort emit: a Kafka outage logs `decision.override.kafka_emit_failed` but does NOT roll back the override row insert (matches the F-038 reports terminal-event pattern).

---

## 1. Pre-flight checks

| # | Check | Expected |
|---|---|---|
| A1 | `curl -fsS localhost:8093/health` | ok |
| A2 | Migration 031 applied: `SELECT to_regclass('decision_overrides');` | non-NULL |
| A3 | Kafka topic exists: `docker exec kaori-kafka-1 kafka-topics --bootstrap-server kafka:9092 --list \| grep feedback.actions` | shows topic (or auto-creates on first emit if `auto.create.topics.enable=true`) |
| A4 | Pilot tenant has at least 1 decision_audit_log row | needed for the override target — run a pipeline + analysis to populate |

---

## 2. Happy path — create + revoke

```bash
EID=<pilot-enterprise-id>
UID=<analyst-user-id>
DID=<an existing decision_audit_log.decision_id from EID>
JWT=<JWT carrying X-Enterprise-ID:$EID + X-User-ID:$UID>

# 1. Read detail (overrides=[])
curl -s http://localhost:8080/api/v1/decisions/$DID \
     -H "Authorization: Bearer $JWT" | jq '.data | {decision_id, chosen_value, overrides}'

# 2. Override the AI's choice.
curl -sX POST http://localhost:8080/api/v1/decisions/$DID/override \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{
       "override_value": "non-churn",
       "reason": "Khách VIP vừa ký lại hợp đồng năm — AI chưa thấy event."
     }' | jq

# Expected 201 + override_id + original_chosen_value snapshot.

# 3. Verify history.
curl -s http://localhost:8080/api/v1/decisions/$DID \
     -H "Authorization: Bearer $JWT" | jq '.data.overrides'
# 1 row, is_active=true.

# 4. Confirm Kafka emit (poll the topic).
docker exec kaori-kafka-1 kafka-console-consumer \
    --bootstrap-server kafka:9092 \
    --topic kaori.feedback.actions \
    --from-beginning --max-messages 1 | jq

# Expected payload:
# { override_id, decision_id, enterprise_id, action: "override.created",
#   decision_type, original_value, override_value, reason, user_id, occurred_at }

# 5. Revoke (e.g. user realised they were wrong).
OID=<override_id from step 2>
curl -sX POST http://localhost:8080/api/v1/decisions/$DID/override/$OID/revoke \
     -H "Authorization: Bearer $JWT" \
     -H "Content-Type: application/json" \
     -d '{ "reason": "Đọc lại email — khách thực sự churn." }' | jq

# Detail now shows is_active=false on that override.
curl -s http://localhost:8080/api/v1/decisions/$DID \
     -H "Authorization: Bearer $JWT" | jq '.data.overrides[0] | {is_active, revoked_at, revoke_reason}'
```

---

## 3. Negative paths

| Test | Expected |
|---|---|
| GET `/decisions/<missing-uuid>` | 404 `Decision not found` |
| GET cross-tenant decision | 404 (RLS hides the row) |
| POST `/override` with empty `reason` | 422 (Pydantic min_length=1) |
| POST `/override` with 2001-char `reason` | 422 (Pydantic max_length=2000) |
| POST `/override` on missing decision | 404 |
| POST `/revoke` on missing override | 404 |
| POST `/revoke` on already-revoked override | 409 `Override already revoked at ...` (preserves first-revoke metadata) |
| Kafka relay down during POST | 201 still returned, Kafka emit logged + swallowed (best-effort) |

---

## 4. Forensics queries

```sql
-- Active override + revocation count per decision
SELECT decision_id,
       COUNT(*)                           AS total_overrides,
       COUNT(*) FILTER (WHERE revoked_at IS NULL) AS active,
       COUNT(*) FILTER (WHERE revoked_at IS NOT NULL) AS revoked,
       MAX(overridden_at)                 AS latest_override
  FROM decision_overrides
 WHERE enterprise_id = '<eid>'
 GROUP BY decision_id
HAVING COUNT(*) > 0
 ORDER BY latest_override DESC
 LIMIT 20;

-- Tenant rollup — disagreement rate by decision_type (last 30 days)
SELECT d.decision_type,
       COUNT(DISTINCT d.decision_id)                 AS decisions,
       COUNT(DISTINCT o.decision_id) FILTER (WHERE o.revoked_at IS NULL) AS overridden,
       ROUND(100.0 * COUNT(DISTINCT o.decision_id) FILTER (WHERE o.revoked_at IS NULL)
                   / NULLIF(COUNT(DISTINCT d.decision_id), 0), 1) AS override_rate_pct
  FROM decision_audit_log d
  LEFT JOIN decision_overrides o
         ON o.decision_id = d.decision_id
        AND o.overridden_at > NOW() - INTERVAL '30 days'
 WHERE d.enterprise_id = '<eid>'
   AND d.created_at    > NOW() - INTERVAL '30 days'
 GROUP BY d.decision_type
 ORDER BY override_rate_pct DESC NULLS LAST;
```

The override_rate_pct column is what F-074 fine-tuning will key off — high values per decision_type identify model weakness.

---

## 5. Sign-off — backend (PR #122)

- [ ] Migration 031 applies cleanly (FlywayMigrationIT cold-boot 31/31)
- [ ] `pytest tests/test_decisions.py` 23/23 green (was 12, +11 new for F-036)
- [ ] ai-orchestrator full suite 322/322 green (was 311, +11 new)
- [ ] OpenAPI snapshot refreshed (29 paths)
- [ ] FE types regenerated (`frontend/lib/api/types/orchestrator.d.ts`)
- [ ] Schema snapshot regenerated (`scripts/schema-drift.py --check` PASS)
- [ ] Kafka contract guard PASS (`scripts/check-kafka-contracts.py` — additive-only)
- [ ] One real override + revoke cycle produces 2 events on `kaori.feedback.actions`
- [ ] Cross-tenant requests return 404
- [ ] Already-revoked revoke returns 409 with the first-revoke timestamp

---

## 6. Frontend walk-through (this FE PR)

`/p2/decisions/[id]` is a Next.js dynamic route (the legacy literal
`/p2/decisions/id` folder coexists for backward compat — never linked
from any wired template). Existing list / insight / pipeline templates
already point at `/p2/decisions/<uuid>` so deep-linking just works.

Header card:
- Subject + decision_type badge + method badge + uncertainty/needs-confirm badges
- "Đã hành động" badge when is_actioned=true
- "Đã override" red badge when an active override exists; in that case the chosen_value renders struck-through with the override_value next to it
- 3 KPI tiles: confidence (Cao/Vừa/Thấp), uncertainty flags, is_actioned toggle (Sprint 7 PR D existing endpoint)

Override section:
- "Override mới" header button → opens a modal
- Modal fields: override_value (≤500 chars) + reason (1-2000, fine-tuning copy hint)
- POST `/api/v1/decisions/{id}/override` → 201 → success banner mentions Kafka
- History list: each row = active or revoked badge + relative time + user prefix + struck-through original → override_value + reason. Active rows have a "Thu hồi" button → `prompt()` for revoke reason → POST `/.../revoke`
- 409 on already-revoked surfaces as the standard ErrorBanner

Audit section: decision_id / run_id / method / created_at + K-2 immutability hint.

| FE test | Expected |
|---|---|
| First load on `/p2/decisions/dec-0001-uuid` | Header + reasoning + 2 alternatives + 2 overrides (1 active, 1 revoked) |
| Active override banner | Subject card shows "Đã override" badge + struck-through chosen_value |
| Submit empty `override_value` | Button disabled (FE-side validation) |
| Submit empty `reason` | Button disabled |
| Submit valid override | Banner success + history refreshes (new row at top) + Kafka emit visible in BE logs (real path) |
| Click "Thu hồi" on active row → cancel prompt | No request fired |
| Click "Thu hồi" on active row → enter reason | History refreshes; row flips to "Đã thu hồi" badge |
| Click "Thu hồi" on already-revoked row | Button absent — no-op possible |
| Visit `/p2/decisions/<missing-uuid>` | ErrorBanner "Không tải được quyết định" — 404 from BE |
| Toggle `is_actioned` | Existing Sprint 7 PR D /action endpoint (unchanged) |
| Disable MSW (real BE) | Same UI, real `/api/v1/decisions/{id}` round-trip; Kafka emit confirmable via `kaori-console-consumer --topic kaori.feedback.actions` |
