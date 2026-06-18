# UAT — F-DLQ-CONSOLE (5-Source Unified DLQ Recovery Console)

> **Function:** Phase 2.7 P1 — DLQ Console unifying 5 failure sources
> **Portal:** P5 Shared Infrastructure (`P5-04` per `feature-screens.html`); admin-only
> **Service:** ai-orchestrator (`routers/dlq_console.py`)
> **DB:** No new table — aggregates 5 existing sources
> **Owner:** Platform Eng + SRE
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.7 ship `011965b`)

| Source | Where data lives |
|---|---|
| Kafka DLQ | `kaori.dlq.*` topics |
| Redis Stream DLQ | Redis stream entries |
| Workflow runs failed | mig 088 `workflow_runs WHERE status='failed'` |
| Idempotency expired | mig 095 `workflow_idempotency_records WHERE expires_at < NOW()` |
| Compensation logs | mig 094 `workflow_events WHERE event_type LIKE 'compensation_%'` |

Endpoints: `GET /admin/dlq` paginated + `POST /admin/dlq/{source}/{id}/{retry|replay|requeue|discard}` (BackgroundTasks for non-blocking replay).

Tests pass: `tests/test_dlq_console.py` 22/22.

---

## 1. Test scenarios

### TC-1 Happy path (unified list view)
- **Given** 5 failures across all 5 sources (1 each)
- **When** GET `/admin/dlq?source=all&limit=50`
- **Then** Response 5 entries với source tag + timestamp + tenant_id (admin-only); pagination cursor

### TC-2 Retry from Kafka DLQ
- **Given** Kafka DLQ entry stale 1 day
- **When** POST `/admin/dlq/kafka/{msg_id}/retry`
- **Then** Background task republish to original topic; entry tagged `retry_count++`; max 5 retries enforced

### TC-3 Replay workflow run
- **Given** workflow run failed at node 3
- **When** POST `/admin/dlq/workflow_run/{rid}/replay`
- **Then** New run spawned với same input + state copied from event_store mig 094 up to node 3; replay continues from there; K-13 idempotency keys reused to avoid re-fire externals

### TC-4 Admin-only authz
- **Given** Non-SUPER_ADMIN user calls GET `/admin/dlq`
- **When** request fires
- **Then** 403 + claim check `manage_dlq` (NFRS §5.bis catalog)

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Admin valid GET/POST | TC-1/2/3 |
| **Validation** | source=invalid | 422 USR-ERR-422-DLQ_SOURCE |
| **Permission** | Non-admin | 403 USR-ERR-403-CLAIM `manage_dlq` |
| **Dependency** | Underlying source service down (Kafka/Redis) | Per-source error tag; other sources still listable |

## 3. K-rule invariants

- **K-12** Admin role + claim required (anti-IDOR; admin sees all tenants but logs cross-tenant access)
- **K-15** Audit every admin action mig 098
- **K-19** OTel span per source aggregation

## 4. Performance

| NFR | Target |
|---|---|
| GET /admin/dlq (50 entries from 5 sources) | <500ms P99 |
| Replay workflow_run background task | <30s |

## 5. UAT execution checklist

- [ ] Verify endpoints exposed + claim `manage_dlq` enforced
- [ ] Inject failures in each of 5 sources → verify unified list
- [ ] Test retry/replay/requeue/discard each per source
- [ ] PagerDuty integration: depth >100 alert + >1000 escalate
- [ ] Customer-impact verify: P2-03 Today Queue shows "2 workflow failures" without exposing DLQ to customer

---

*UAT ID: UAT-DLQ-001 · Owner SRE*
