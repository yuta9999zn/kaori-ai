# UAT — F-ONTOLOGY-GOV (Lifecycle FSM + Edge Taxonomy Governance)

> **Function:** Phase 2.6 P2.2 + P2.3 — Lifecycle state machine + Ontology edge type governance
> **Portal:** Internal (no customer-facing UI)
> **Service:** ai-orchestrator (`shared/governance.py` + ontology layer)
> **DB:** mig 096 `lifecycle_state_transitions` + `ontology_edge_types`
> **Owner:** Data Analyst + Platform Eng
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.6 P2.2/P2.3 ship `6ddb099`)

| Surface | Purpose |
|---|---|
| Mig 096 `lifecycle_state_transitions` | (entity_type + from + to + requires_event + requires_role + is_recovery). Seeded 9 transitions |
| Mig 096 `ontology_edge_types` | (edge_type_key + 7-primitive source/target CHECK enum + cardinality + retention_days + governance_owner + deprecated_at). Seeded 11 v0 edges |
| `governance.validate_lifecycle_transition()` | Refuses unknown transitions, missing required event, wrong required role |
| `governance.validate_edge_type()` | Free-form edges blocked; process-level cache for registry lookups |

Tests pass: `tests/test_governance.py` 18/18.

---

## 1. Test scenarios

### TC-1 Customer lifecycle (lead → active_customer)
- **Given** Lifecycle row: `entity_type='customer', from='lead', to='active_customer', requires_event='first_purchase'`
- **When** Caller `validate_lifecycle_transition(customer_id, 'lead', 'active_customer', event='first_purchase')`
- **Then** Returns valid; ontology updates customer state

### TC-2 Win-back recovery (churned → lead)
- **Given** Transition `churned → lead requires win_back event + MANAGER role + is_recovery=true`
- **When** OPERATOR calls without win_back event
- **Then** 403 + error "Transition requires MANAGER + win_back event"

### TC-3 Free-form edge blocked
- **Given** Neo4j adapter try to insert edge type `random_relation_xyz` (not in `ontology_edge_types`)
- **When** validate_edge_type called pre-INSERT
- **Then** Raises EdgeTypeUnknownError; INSERT blocked; warning to caller

### TC-4 Deprecated edge type
- **Given** Edge type marked `deprecated_at = 2026-01-01`
- **When** validate_edge_type for that key
- **Then** Returns valid with warning log "edge_type X deprecated, use Y instead"; metric counter `deprecated_edge_used_total++`

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid transition + valid edge | TC-1/2/3/4 |
| **Validation** | Unknown lifecycle state | LifecycleStateUnknownError |
| **Permission** | Wrong role for transition | RoleInsufficientError |
| **Dependency** | governance cache stale (1-day TTL) | Refresh from DB; if DB down → use cached (best-effort) |

## 3. K-rule invariants

- **K-19** OTel span per validate call

## 4. Performance

| NFR | Target |
|---|---|
| validate_lifecycle_transition (cached) | <1ms |
| validate_edge_type (cached) | <1ms |
| Cache refresh (DB query) | <50ms |

## 5. UAT execution checklist

- [ ] Verify mig 096 applied + 9 lifecycle + 11 edge types seeded
- [ ] Test each of 9 lifecycle transitions: valid path + invalid path
- [ ] Test 11 edge types: valid INSERT + free-form blocked
- [ ] Win-back recovery: simulate MANAGER role + win_back event → success
- [ ] Deprecation warning: query deprecated edge → warning emitted

---

*UAT ID: UAT-ONTOLOGY-GOV-001 · Owner Data Analyst*
