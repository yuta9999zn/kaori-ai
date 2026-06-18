# UAT — F-POLICY-ENGINE (Declarative K-Rule + Policy Engine)

> **Function:** Phase 2.7 P3 — policy_rules table + evaluate() with priority + scope filtering
> **Portal:** Internal (transparent to customer; enforced at approval_gate + admin policy mgmt later)
> **Service:** ai-orchestrator (`shared/policy_engine.py`)
> **DB:** mig 099 `policy_rules`
> **Owner:** Platform Eng + SEC + PO
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.7 ship `5e750b2` + wiring `1796c16`)

| Surface | Purpose |
|---|---|
| Mig 099 `policy_rules` | (rule_key UNIQUE + scope global/tenant/role + priority asc + condition_json + action enum allow/deny/require_approval/rate_limit/audit + action_params + metadata) seeded with 3 K-rule conversions |
| `policy_engine.py` | PolicyDecision dataclass + evaluate_condition (pure recursive eval, ==/!=/>/>=/</<=/in/notin + and/or compound) + evaluate (priority order, first match wins) + 60s TTL cache |
| Seeded rules | `k4_consent_external_required` (global deny) + `finance_invoice_cfo_threshold` (>100M VND require_approval) + `mfa_required_super_admin` (role deny) |
| Wiring approval_gate | Builds policy_ctx + calls evaluate(); deny→NodeExecutorError; require_approval→override config; allow→fall through |

Tests pass: `tests/test_policy_engine.py` 23/23.

---

## 1. Test scenarios

### TC-1 Happy path (CFO threshold approval gate)
- **Given** Workflow F.1 Invoice Approval; input amount=150M VND
- **When** approval_gate node runs → policy_engine.evaluate()
- **Then** Rule `finance_invoice_cfo_threshold` matches (>100M); action=`require_approval` with `approver_roles=['CFO'], sla_minutes=1440`; overrides config auto_threshold

### TC-2 K-4 deny external LLM without consent
- **Given** Tenant consent_external_ai=false; workflow node calls LLM with prefer_external=true
- **When** policy_engine.evaluate() with method='external'
- **Then** Rule `k4_consent_external_required` matches; action=`deny`; LLM call blocked; fallback Qwen local

### TC-3 First-match-wins priority
- **Given** Policy rules: rule A priority=10 (deny) + rule B priority=20 (allow) — both conditions match
- **When** evaluate
- **Then** Rule A wins (lower priority = higher ranking); decision=`deny`

### TC-4 Cache invalidation
- **Given** policy_rules table updated via admin endpoint; cache 60s TTL
- **When** policy.evaluate called within 60s window
- **Then** Cache returns stale; after 60s → DB refresh; reload_cache test hook for unit tests

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid policy match | TC-1/2/3 |
| **Validation** | Invalid condition_json (malformed) | Policy fails closed: action='deny' + log error |
| **Permission** | Admin policy edit endpoint not yet implemented | Phase 2.9 |
| **Dependency** | policy_rules DB down | best_effort: log + skip policy enforce (allow fall-through); flag for audit |

## 3. K-rule invariants

- **K-3** N/A
- **K-6** Every policy evaluation logged
- **K-15** Policy violations alert SEC NFR-SEC-19 (>5/hour/user → escalate)
- **K-19** OTel span per evaluate call

## 4. Performance

| NFR | Target |
|---|---|
| evaluate() cached P99 | <1ms |
| evaluate() cache miss + DB refresh | <50ms |
| Cache hit rate | >95% (60s TTL) |

## 5. UAT execution checklist

- [ ] Verify mig 099 applied + 3 K-rule seeded
- [ ] Test K-4 deny: workflow request external LLM without consent → Qwen fallback fired
- [ ] Test CFO threshold: 150M invoice → CFO approval required
- [ ] Test MFA SUPER_ADMIN: admin without MFA tries action → deny
- [ ] Priority order test: 2 rules both match → lower priority wins
- [ ] Cache invalidation: update rule → wait 60s → verify new behavior

---

*UAT ID: UAT-POLICY-ENGINE-001 · Owner SEC + PO*
