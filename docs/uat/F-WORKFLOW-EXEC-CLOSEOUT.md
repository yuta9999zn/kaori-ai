# UAT — F-WORKFLOW-EXEC-CLOSEOUT (45 Catalog Executors + 25 Templates End-to-End)

> **Function:** Phase 2 Workflow Execution Closeout — 5 waves shipping 45/45 node-type catalog executors; ALL 25 mig 069 business templates fully LIVE 5/5 nodes
> **Portal:** P2 Enterprise (Workflow Builder + Run)
> **Service:** ai-orchestrator (workflow runtime + 45 executor registry)
> **DB:** mig 088 workflow_runs + workflow_run_nodes; mig 089 workflow_approvals; mig 091-093 (workflow output sinks + chat outbox + wave5 tables)
> **Owner:** QA Lead + Workflow Designer (Studio)
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. What landed (Phase 2 closeout `bf2aa0d` + wave 5)

| Wave | Executors | Templates flip | Coverage |
|---|---|---|---|
| Wave 1 (post-audit) | node_executor.py + 6 first-wave (if_else/switch/aggregate/read_table/update_record/send_email) + run endpoint | 0 templates LIVE yet | 6/45 (13%) |
| Wave 2 approval | + ApprovalGateExecutor + ReadFormSubmissionExecutor | 6 approval templates LIVE | 8/45 (18%) |
| Wave 2b AI | + 8 AI nodes (classify_text/generate_narrative/rag_query/call_*) | 2 more LIVE (D.3 NPS + E.1 Restock) | 16/45 (36%) |
| Wave 3 | + 10 output/action/validate/data (publish_*/create_task/call_api/trigger_workflow/validate/read_email/etc) | 17 of 25 LIVE | 26/45 (58%) |
| Wave 4 | + 8 utility (scheduled_trigger/filter/transform/split/join/log/send_chat_message/read_webhook) | ALL 25 mig 069 LIVE | 34/45 (76%) |
| Wave 5 | + 11 final (sort/merge/dedup/enrich/wait_for_condition/read_api/read_calendar/read_chat/read_file_upload/send_sms/export_file) | unchanged 25 LIVE | **45/45 (100%)** |

ai-orch tests: 1900 → 2128 (+228 across waves).

---

## 1. Test scenarios

### TC-1 Happy path (run C.4 Discount Approval end-to-end)
- **Given** Template instantiated → workflow with 5 cards (read_form_submission + validate + switch + approval_gate + send_email)
- **When** POST `/workflows/{id}/run` with input `{discount_pct: 18, deal_amount_vnd: 200M, customer_id: 'CUS-123'}`
- **Then** Run topo-executes 5 nodes; branch routes 18% → Manager approval (10-25%); approval pause/resume; final send_email fires; workflow_run.status='completed'; ai-orch event_store mig 094 has 5+ events

### TC-2 Approval gate auto-threshold
- **Given** Discount Approval template configured `auto_threshold: 10%`; input discount=8%
- **When** run
- **Then** approval_gate auto-approves <10%; skip Manager pause; workflow completes faster

### TC-3 Saga compensation on external fail
- **Given** F.4 Vendor Payment template; payment API returns 502 mid-saga
- **When** run reaches send_payment external node
- **Then** Compensation registry mig 094 walks completed external/write_non_idempotent nodes in reverse; cancel_approval_request + retract_alert fire; workflow_run.status='failed' + compensation_completed event

### TC-4 In-process runner deterministic re-run
- **Given** Same workflow + same input, run twice
- **When** compare run #1 vs run #2
- **Then** Same DAG order (Kahn topo-sort); same outputs per node; idempotency_records mig 095 dedup external calls; ReplayHarness P0.4 confirms projection identical

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Valid template + input | TC-1 |
| **Validation** | Missing required field | 422 USR-ERR-422 per workflow.required_fields |
| **Permission** | VIEWER POST /run | 403 USR-ERR-403-ROLE |
| **Dependency** | External node 5xx (saga case) | TC-3 compensation |
| Catalog drift | Workflow YAML references unknown node_type_key | 422 RFC 7807 `{code: USR-ERR-422-EXECUTOR_MISSING, hints: [...]}` |
| State machine violation | Try to resume completed run | 409 RFC 7807 |

## 3. K-rule invariants

- **K-1** RLS on workflow_runs ✓
- **K-2** workflow_events mig 094 append-only ✓
- **K-6** Every node decision logged decision_audit_log + mig 098
- **K-13** Idempotency-Key on POST /run; idempotency_records mig 095 persistent (not just in-process)
- **K-17** Every catalog row declares side_effect_class
- **K-19** OTel span per node + per workflow_run

## 4. Performance

| NFR | Target |
|---|---|
| Workflow run (5-node simple) | <1s in-process (no external) |
| Workflow run (with 1 LLM node) | <8s |
| Concurrent workflow_concurrent quota | 20 rolling per tenant (mig 099) |

## 5. UAT execution checklist

- [ ] Verify mig 088/089/091/092/093/094/095 all applied
- [ ] Trigger 25 templates × 5 sample inputs each = 125 runs
- [ ] Verify 100% complete (zero abort due to executor missing)
- [ ] Saga compensation test: kill external node mid-saga → verify reverse walk
- [ ] State machine test: forbidden transitions raise StateTransitionDenied (P0.2)
- [ ] Replay test: ReplayHarness P0.4 → assert projection matches cached snapshot
- [ ] Idempotency test: same Idempotency-Key 2x → same response_payload from ledger
- [ ] Compound chaos (F4): kill workflow_events insert mid-run → verify graceful degradation

---

*UAT ID: UAT-WORKFLOW-EXEC-001 · Owner QA Lead*
