# UAT — F-LINEAGE-WALK (12-ObjectKind Lineage Traversal)

> **Function:** Phase 2.7 P1 — data_lineage_edges with 12 ObjectKind enum + BFS walk
> **Portal:** P2 Enterprise (P2-20 Insight Detail "Xem lineage" button + admin lineage browser)
> **Service:** ai-orchestrator (`shared/lineage.py` + `routers/lineage.py`)
> **DB:** mig 097 `data_lineage_edges` with 12 ObjectKind enum + RLS + ON CONFLICT idempotent
> **Owner:** QA Lead + Data Analyst
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2.7 ship `011965b` + wiring `31af408`)

| ObjectKind | Layer |
|---|---|
| bronze_file | L1 |
| silver_row | L2 |
| gold_row | L2 |
| ontology_entity | L4 |
| ai_decision | L3 |
| workflow_run | L4 |
| workflow_node | L4 |
| workflow_insight | L5 |
| workflow_alert | L5 |
| workflow_task | L5 |
| document_chunk | L4 |
| embedding_vector | L4 |

Endpoints: `GET /lineage/{kind}/{id}/upstream` + `GET /lineage/{kind}/{id}/downstream`. BFS walk + cycle detection + max_depth/max_nodes caps.

Tests pass: `tests/test_lineage.py` 14/14.

---

## 1. Test scenarios

### TC-1 Happy path (insight → bronze upstream walk)
- **Given** ai_decision generated insight; upstream chain: insight → workflow_run → silver_row → bronze_file
- **When** GET `/lineage/ai_decision/{id}/upstream?max_depth=5`
- **Then** Response BFS tree with 4 levels; bronze_file at root; trace shows transformation chain

### TC-2 Downstream walk (bronze_file → all derived objects)
- **Given** Bronze file XYZ processed by 3 workflow runs → 5 insights generated
- **When** GET `/lineage/bronze_file/{id}/downstream?max_depth=5`
- **Then** Response: bronze_file → 1 silver_row → 3 workflow_runs → 5 workflow_insights (15 nodes total)

### TC-3 Cycle detection
- **Given** Manual cycle inserted (impossible in normal flow but test edge case)
- **When** BFS walk
- **Then** Cycle detected at depth N; visited set prevents infinite loop; truncated result with `truncated_reason: 'cycle'`

### TC-4 Max nodes cap
- **Given** Dense lineage > max_nodes=1000
- **When** walk
- **Then** Truncated at 1000; response has `truncated_reason: 'max_nodes_exceeded', total_visited: 1000`

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid kind + id + walk | TC-1/2 |
| **Validation** | Invalid kind (not in 12 ObjectKind) | 422 USR-ERR-422-LINEAGE-KIND |
| **Permission** | Cross-tenant lookup attempt | RLS blocks (K-1); returns empty |
| **Dependency** | data_lineage_edges DB query timeout | Best-effort partial result + warning |

## 3. K-rule invariants

- **K-1** RLS on data_lineage_edges per tenant ✓
- **K-19** OTel span per walk

## 4. Performance

| NFR | Target |
|---|---|
| Walk 100-node lineage | <500ms P99 |
| Walk 1000-node lineage (cap) | <2s |

## 5. UAT execution checklist

- [ ] Verify mig 097 applied + 12 ObjectKind enum
- [ ] Create sample lineage: upload → pipeline → insight; verify edges auto-recorded
- [ ] Walk upstream from insight → verify reaches bronze_file
- [ ] Walk downstream from bronze → verify reaches all derived insights
- [ ] Cycle protection test
- [ ] Max nodes cap test (insert dense lineage)
- [ ] FE P2-20 "Xem lineage" button → modal graph viz

---

*UAT ID: UAT-LINEAGE-001 · Owner QA Lead*
