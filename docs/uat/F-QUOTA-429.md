# UAT — F-QUOTA-429 (Tenant Quotas + 429 with Retry-After)

> **Function:** Phase 2.7 P2 — tenant_quotas + tenant_quota_usage with rolling windows + 429 enforcement
> **Portal:** Internal (transparent enforcement; customer sees 429 RFC 7807 if hit)
> **Service:** llm-gateway + ai-orchestrator (`shared/tenant_quotas.py`)
> **DB:** mig 099 `tenant_quotas` + `tenant_quota_usage`
> **Owner:** Platform Eng + SRE + PO
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.7 ship `5e750b2` + wiring `6f93cff`)

| Surface | Purpose |
|---|---|
| Mig 099 `tenant_quotas` | (per-tenant per-type per-period max). Seeded 5 default types per enterprise |
| Mig 099 `tenant_quota_usage` | Rolling counter UNIQUE on tenant+type+window_start |
| `tenant_quotas.py` | _window_bounds pure window math (per_minute/hour/day/month/rolling, December rollover) + check_and_consume atomic SELECT FOR UPDATE + UPSERT (raises QuotaExceeded BEFORE commit) + get_usage non-mutating read + fail_open_if_unconfigured graceful degradation |
| Wiring | llm-gateway /v1/infer charges `llm_tokens_external` or `llm_tokens_local`; workflow runner charges `workflow_concurrent` BEFORE WorkflowRunner.create_run |

Default quotas seeded: llm_tokens_external (per_day 1M), llm_tokens_local (per_day 10M), workflow_concurrent (rolling 20), api_calls (per_minute 1000), export_files (per_day 100).

Tests pass: `tests/test_tenant_quotas.py` 27/27 (incl. December rollover edge case).

---

## 1. Test scenarios

### TC-1 Happy path (LLM token consumed)
- **Given** Tenant with llm_tokens_external default cap 1M/day, current usage 999.5K
- **When** LLM /v1/infer call estimate 500 tokens (prompt_chars + max_tokens × 4)
- **Then** check_and_consume succeeds; usage 999.5K → 1M; subsequent call would exceed

### TC-2 Quota exceeded 429
- **Given** Tenant usage exactly at cap
- **When** Next LLM call check_and_consume
- **Then** QuotaExceeded raised BEFORE providers.invoke fires (no token spend, no audit, no governance row); 429 RFC 7807 returned with `Retry-After: <seconds until next window>` per NFR-SEC-09

### TC-3 Rolling window (workflow_concurrent)
- **Given** 20 concurrent workflow runs (rolling)
- **When** 21st POST /workflows/{id}/run
- **Then** check_and_consume fails; 429 returned BEFORE create_run (no run_id row pollution); user sees "Quá nhiều workflow đang chạy. Đợi 1 phút."

### TC-4 fail_open_on_infra_error flag
- **Given** quota table DB down + fail_open_on_infra_error=true (default for llm-gateway)
- **When** check_and_consume
- **Then** Returns success (best-effort); request proceeds; warning log; quota_table_unavailable_total++ metric

### TC-5 December rollover
- **Given** Tenant quota windows per_month; Dec 31 23:59:59
- **When** rollover Dec → Jan
- **Then** _window_bounds correctly computes new window starting Jan 1 00:00:00; usage resets to 0

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Within quota | TC-1 |
| **Validation** | Negative amount | 422 USR-ERR-422-QUOTA-AMOUNT |
| **Permission** | Cross-tenant quota query | RLS blocks (K-1) |
| **Dependency** | quota DB down + fail_open=true | TC-4 |
| **Dependency** | quota DB down + fail_open=false | 503 SYS-ERR-503 |

## 3. K-rule invariants

- **K-1** RLS on tenant_quota_usage ✓
- **K-19** OTel span per check_and_consume

## 4. Performance

| NFR | Target |
|---|---|
| NFR-SEC-09 Rate limiting | Token Bucket per tenant per endpoint; 429 + Retry-After |
| check_and_consume P99 | <30ms |

## 5. UAT execution checklist

- [ ] Verify mig 099 applied + 5 quota types seeded per enterprise
- [ ] Fire LLM calls to exhaust llm_tokens_external → verify 429 on next call
- [ ] Verify Retry-After header reasonable (seconds until window reset)
- [ ] Test workflow_concurrent: 21 simultaneous runs → 21st 429
- [ ] December rollover test: simulate Dec 31 23:59:59 → Jan 1 00:00:01
- [ ] fail_open: kill quota DB → verify llm-gateway still serves with warning

---

*UAT ID: UAT-QUOTA-429-001 · Owner SRE*
