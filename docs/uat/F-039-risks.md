# UAT — F-039 Risk Management (BE)

> **Function:** F-039 — Manual risk register CRUD (auto-detect from data + risk_snapshots history + alert wiring deferred to v1)
> **Portal:** P2 Enterprise
> **Roles allowed:** any P2 role can read; **MANAGER only** for create/update/delete
> **Service:** auth-service (`/api/v1/enterprises/risks/*`)
> **DB tables:** `risk_items` (migration 033) — append-only at the rule layer (UPDATE only, soft-delete via `deleted_at`)
> **Owner:** Customer Success driver
> **Prepared:** 2026-05-03

---

## 0. What landed (this PR)

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/enterprises/risks?page=&limit=&status=&severity=` | Paginated list (sorted score DESC) |
| `GET /api/v1/enterprises/risks/severity-rollup` | Heat map header tile — counts per severity bucket (open + mitigating only) |
| `GET /api/v1/enterprises/risks/{riskId}` | Single risk detail |
| `POST /api/v1/enterprises/risks` | Create — MANAGER only |
| `PATCH /api/v1/enterprises/risks/{riskId}` | Partial update — MANAGER only |
| `DELETE /api/v1/enterprises/risks/{riskId}` | Soft delete — MANAGER only |

Migration 033 — `risk_items`:
- Standard tenant_isolation + admin_bypass RLS
- `score` + `severity` auto-computed by DB trigger from `likelihood × impact` (1..25 → low/medium/high/critical)
- `updated_at` auto-bumped on every UPDATE
- 3 indexes: per-tenant by score (heat map), per-owner open (workload), severity rollup partial
- Soft-delete via `deleted_at`; no DELETE grant on kaori_app

---

## 1. Pre-flight

| # | Check | Expected |
|---|---|---|
| A1 | Migration 033 applied: `SELECT to_regclass('risk_items');` | non-NULL |
| A2 | Trigger registered: `SELECT tgname FROM pg_trigger WHERE tgname='trg_risk_items_score_severity';` | one row |
| A3 | Pilot tenant has at least 1 active MANAGER user | needed to create risks |

---

## 2. Happy path

```bash
EID=<pilot-enterprise-id>
UID=<manager-user-id>
H_E="X-Enterprise-ID: $EID"
H_R="X-User-Role: MANAGER"
H_U="X-User-ID: $UID"

# 1. Create
curl -sX POST -H "$H_E" -H "$H_R" -H "$H_U" -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/enterprises/risks -d '{
    "title": "Tồn kho phụ kiện cao",
    "description": "Tồn 120 ngày — chiếm 18% kho",
    "likelihood": 3,
    "impact": 4,
    "status": "open",
    "mitigation_plan": "Thanh lý 30% nhóm A trong tháng 5",
    "mitigation_progress": 0,
    "due_date": "2026-06-30"
  }' | jq

# Expected 201 + auto-computed score=12, severity=high.

# 2. Heat map rollup
curl -s -H "$H_E" http://localhost:8080/api/v1/enterprises/risks/severity-rollup | jq
# Expected: { data: { by_severity: { critical, high, medium, low }, open_total } }

# 3. Update mitigation progress
curl -sX PATCH -H "$H_E" -H "$H_R" -H "$H_U" -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/enterprises/risks/$RID -d '{
    "mitigation_progress": 60,
    "status": "mitigating"
  }' | jq

# 4. Reduce likelihood (recomputes score+severity via trigger)
curl -sX PATCH -H "$H_E" -H "$H_R" -H "$H_U" -H "Content-Type: application/json" \
  http://localhost:8080/api/v1/enterprises/risks/$RID -d '{ "likelihood": 1 }' | jq
# severity now "low" (1×4=4, < 5 = low)

# 5. List filtered by severity
curl -s -H "$H_E" "http://localhost:8080/api/v1/enterprises/risks?severity=critical" | jq

# 6. Soft delete
curl -sX DELETE -H "$H_E" -H "$H_R" -H "$H_U" \
  http://localhost:8080/api/v1/enterprises/risks/$RID | jq
```

---

## 3. Negative paths

| Test | Expected |
|---|---|
| `POST` with `X-User-Role: VIEWER` | 403 — only MANAGER |
| `POST` with `likelihood: 0` | 400 — likelihood 1..5 |
| `POST` with `impact: 6` | 400 — impact 1..5 |
| `POST` with empty `title` | 400 — title required |
| `POST` with `status: "WIP"` | 400 — status must be one of [open, mitigating, closed] |
| `POST` with `mitigation_progress: 150` | 400 — must be 0..100 |
| `PATCH /{id}` with empty body | 400 — at least one field |
| `GET /{nonexistent-uuid}` | 404 |
| Cross-tenant `GET` | 404 (RLS hides the row) |
| `DELETE` with VIEWER role | 403 |

---

## 4. Forensics

```sql
-- "Top 5 highest-impact open risks"
SELECT title, score, severity, likelihood, impact, owner_user_id, due_date
  FROM risk_items
 WHERE enterprise_id = '<eid>'
   AND status != 'closed'
   AND deleted_at IS NULL
 ORDER BY score DESC LIMIT 5;

-- "Risks overdue (due_date past, not closed)"
SELECT title, due_date, status, mitigation_progress
  FROM risk_items
 WHERE enterprise_id = '<eid>'
   AND deleted_at IS NULL
   AND status != 'closed'
   AND due_date < CURRENT_DATE
 ORDER BY due_date;

-- "Severity drift after re-rating (audit trail via updated_at)"
SELECT title, severity, score, likelihood, impact, updated_at
  FROM risk_items
 WHERE enterprise_id = '<eid>'
 ORDER BY updated_at DESC LIMIT 20;
```

---

## 5. Sign-off

- [ ] Migration 033 applies cleanly (FlywayMigrationIT cold-boot 33/33)
- [ ] `RiskItemServiceTest` 16/16 green
- [ ] `WorkspaceControllerIT` 10/10 still green (slice context boots with new beans)
- [ ] Schema snapshot regenerated (`scripts/schema-drift.py --check` PASS)
- [ ] Trigger correctly recomputes score+severity when likelihood/impact changes (manual SQL test)
- [ ] Cross-tenant requests return 404
- [ ] Non-MANAGER roles get 403 on mutations

## 6. Deferred (v1 follow-ups)

- **Auto-detect from data** — analysis pipeline emits suggested risks (anomaly + threshold breach); needs ai-orchestrator hook
- **risk_snapshots history table** — periodic frozen rollups for trend charts ("severity distribution over time")
- **F-037 alert wiring** — when a risk crosses critical, fire kaori.alerts.fire (extends current billing-only alert dispatcher)
- **FE heat map page** at `/p2/risks` — templates 56-58 ready (B5.5 Risks Hub + Detail + Export)
- **Owner reassignment workflow** with notifications
- **Bulk import from CSV** — pilot does manual entry which is fine for <50 risks
