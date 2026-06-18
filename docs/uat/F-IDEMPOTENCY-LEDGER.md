# UAT — F-IDEMPOTENCY-LEDGER (K-13 Persistent Ledger)

> **Function:** Phase 2.6 P0.3 — workflow_idempotency_records persistent ledger replacing in-process cache
> **Portal:** P2 Enterprise (transparent backend; external nodes retry-safe across worker restarts)
> **Service:** ai-orchestrator (`workflow_runtime/idempotency_store.py`)
> **DB:** mig 095 `workflow_idempotency_records`
> **Owner:** QA Lead + Platform Eng
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.6 P0.3 ship `e68f841`)

| Surface | Purpose |
|---|---|
| Mig 095 `workflow_idempotency_records` | `(record_id, enterprise_id, idempotency_key UNIQUE, response_payload jsonb, response_status, attempt_count, expires_at)` + RLS |
| `idempotency_store.py` | derive_key (SHA-256) + get_or_set (atomic SELECT FOR UPDATE) + record_outcome + sweep_expired |
| call_api executor | Tiers: in-process cache → persistent ledger → HTTP. Worker restart no longer re-fires POST |

Tests pass: `tests/test_idempotency_store.py` 10/10 (incl. miss/hit/expired/concurrent SELECT FOR UPDATE).

---

## 1. Test scenarios

### TC-1 Happy path (call_api with idempotency)
- **Given** workflow call_api node với header `Idempotency-Key: req-abc-123`
- **When** first call → outcome stored
- **Then** ledger has row with response_payload + response_status; second call same key → return cached without HTTP fire

### TC-2 Worker restart safety
- **Given** Worker calls external API, success but crashes BEFORE recording outcome
- **When** Worker restarts + retries same idempotency_key
- **Then** get_or_set: ledger row LOCKED (in-progress state via SELECT FOR UPDATE); 1st worker recover writes outcome; 2nd worker sees recorded outcome — KHÔNG re-fire POST

### TC-3 TTL expiry
- **Given** Idempotency record với `expires_at = now - 1 hour` (expired)
- **When** get_or_set called same key
- **Then** Treated as fresh; new HTTP call fires; new row inserted; sweep_expired cron removes old expired rows

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Normal idempotent call | TC-1 |
| **Validation** | Idempotency-Key missing | 400 USR-ERR-400-IDEMPOTENCY-MISSING (K-13 enforce on POST mutations) |
| **Permission** | RLS K-1 | Different tenant cannot see other's idempotency records |
| **Dependency** | DB pool exhausted | Caller retry; pool_exhausted_alert per chaos matrix |

## 3. K-rule invariants

- **K-1** RLS ✓
- **K-13** Idempotency persistent + 7d TTL ✓
- **K-19** OTel span per get_or_set call

## 4. Performance

| NFR | Target |
|---|---|
| get_or_set P99 | <30ms |
| sweep_expired cron | nightly, <2min for 1M rows |

## 5. UAT execution checklist

- [ ] Verify mig 095 applied + UNIQUE constraint on idempotency_key
- [ ] Fire call_api with same Idempotency-Key 2x → verify HTTP only fires 1x
- [ ] Worker restart sim: kill mid-call, restart → verify no double-fire
- [ ] Concurrent SELECT FOR UPDATE: 10 workers race same key → 1 success, 9 wait then read cached
- [ ] sweep_expired: insert 1M expired rows, run sweep → <2min

---

*UAT ID: UAT-IDEMPOTENCY-LEDGER-001 · Owner Platform Eng*
