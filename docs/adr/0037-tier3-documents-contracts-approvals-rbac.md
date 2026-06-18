# ADR-0037 — Tier-3: Document Tree, Contracts, Approval Chains + RBAC (additive)

> **Status:** accepted (design) — Phase 1 (Document Tree) shipping; Phase 2/3 designed, deferred
> **Date:** 2026-05-30
> **Deciders:** Nguyen Truong An
> **Related:** mig 046 (org hierarchy) · 053 (workflow builder) · 068 (node catalog) · 088/089 (runs + approvals) · 099 (policy engine) · 062 (customer/vendor contracts) · 106/111 (knowledge versioning) · 072 (workflow_editors) · ADR-0013 (RLS) · ADR-0014 (saga/idempotency) · K-1/K-6/K-12/K-13/K-17

## Context

The workflow platform has solid Tier-1 (org) + Tier-2 (process) foundations, but **Tier-3** — the documents, contracts, approvals and role model attached to each step — is thin. A survey of the codebase (2026-05-30) showed most primitives the three design prompts assumed "missing" actually **exist**, so Tier-3 must be **additive reconciliation**, not a greenfield rebuild:

**Already present (REUSE):**
- Org: `departments` (046, `dept_type`, `manager_user_id`, `pii_sensitivity`), `branches`, `workflows.department_id`.
- Process: `workflows`/`workflow_nodes`/`edges`/`runs`/`run_nodes`, `node_type` (10 structural) + `node_type_catalog` (45, incl. `approval_gate`), **`workflow_nodes.lane_name`** (the BPMN role axis), `required_document_types` JSONB.
- Documents: `workflow_step_documents` (053) — a FLAT attach (file→`bronze_files`, `document_kind` text, **no** class/status/version).
- Approval: `workflow_approvals` (089, single-level) + `ApprovalGateExecutor` (pause/resume, `auto_threshold`) + **`policy_rules` (099)** — already ships `finance_invoice_cfo_threshold` (amount > 100M → CFO). The dynamic-approval-condition substrate partly exists.
- Contracts: `customer_contracts`/`vendor_contracts` (062) — but these are **Kaori's own sales contracts** (Kaori-as-vendor), a different domain from a tenant's workflow-generated business contracts.
- Versioning pattern: `knowledge_documents.supersedes/superseded_by/change_reason` (111) — mirror it.
- RBAC: 4 enterprise roles (MANAGER/OPERATOR/ANALYST/VIEWER) + `workflow_editors` (072, workflow-scoped OWNER/EDITOR/REVIEWER/VIEWER) + `decision_audit_log` (K-6).

**⚠️ Hard dependency (Phase 0):** file **bytes are not yet persisted to MinIO** (`ingestor.py`: "Phase 1.5+"). PDF/DOCX register metadata only (`unstructured_pending`). The Document Tree + Contract modules need real bytes to view/sign — schema can land first, but the modules are not *functionally complete* until MinIO byte storage is wired. Tracked as **Phase 0**, parallel.

## Decision

Four architecture forks, resolved (anh: "theo em recommend"):

1. **Sequencing** — ship an ADR (this doc) defining the full data model for all three modules, then build **Phase 1 = Document Tree foundation** first (it is the base; contracts and approvals both *attach documents*). Phases 2 (Approval/RBAC) and 3 (Contract/e-sign) are designed here, built later.
2. **Contract entity** — a **new generic `contracts`** entity linked to `workflow_run_id` + a `contract` node type, NOT an extension of `customer_contracts`. The two domains stay separate (Kaori's sales vs the tenant's business contracts) to keep semantics + RLS clean.
3. **Role model** — **keep the 4 global roles**; add a per-step **functional** assignment (`assigned_role`: executor/reviewer/approver) that *maps onto* the global roles, plus `approval_chains`/`approval_levels` layered over `workflow_approvals`, plus `user_department_roles` (N:M). Additive — no churn to auth-service/JWT/every router.
4. **E-signature** — v1 is **internal click-to-sign** writing an append-only `contract_signatures` row (user + timestamp + IP + document SHA-256 → non-repudiation, K-6). External providers (VNPT eContract / DocuSign) land later behind an adapter, opt-in (K-4 for any external call).

### Unified data model (additive, migrations 119+)

```
departments (046) ─< workflows (053) ─< workflow_nodes (053)
   node: + assigned_role, + step_kind (extend to include 'contract')           [P2/P3]
   node ─< workflow_step_document_requirements (NEW 119) — input/output/reference template per step   [P1]
workflow_runs (088) ─< workflow_run_nodes (088)
   ─< workflow_step_documents (053, EXTENDED 120: doc_class + status + version chain + review + expiry) [P1]
   ─< approval_requests  (workflow_approvals 089, EXTENDED: + chain_id, level, escalated_from)          [P2]
   ─< contracts (NEW) ─< contract_parties (NEW) ─< contract_signatures (NEW, append-only)               [P3]
approval_chains (NEW) ─< approval_levels (NEW: level, role, mode, timeout, escalate_to)                 [P2]
user_department_roles (NEW: user × dept × functional_role)                                              [P2]
```

### Phase 1 — Document Tree (migrations 119 + 120) — THIS PHASE

**mig 119 `workflow_step_document_requirements`** — the builder-time template: per node, declare the documents a step needs, classified:
- `doc_class ∈ {input, output, reference}` — 📥 nộp lên / 📤 sinh ra / 📎 tham chiếu (color + icon axis).
- `is_required`, `allowed_formats text[]`, `template_file_id` (for output blanks / reference docs), `sort_order`, name_vi/description. RLS K-1 + ABAC dept, mirrors mig 053.

**mig 120 extends `workflow_step_documents`** (the actual uploaded instances) with:
- `requirement_id` (which requirement this fulfils, nullable for ad-hoc), `doc_class`,
- `status ∈ {cho_nop, da_nop, dang_xem_xet, da_duyet, tu_choi, yeu_cau_bo_sung, het_han}` (the 7-state document machine),
- version chain: `version int`, `supersedes`, `superseded_by`, `change_reason`, `is_current` (mirrors mig 111),
- review: `reviewed_by`, `reviewed_at`, `review_note`; `valid_until` (expiry, e.g. CMND).
- The existing `UNIQUE(workflow_id, node_id, file_id)` survives — a new version uploads a new `file_id` (new bytes → new bronze row), so versions chain via `supersedes` without colliding.

**BE** (`routers/workflow_documents.py`, new, mounted under the workflow prefix): requirement CRUD (builder), the 7-state status transition endpoint (submit → review → approve/reject/request-more), version supersede on re-upload, and an enriched `GET /workflows/{id}/document-tree` returning the **3-tier** shape (workflow → step → {input[],output[],reference[]} with status/version/history). A pure status state-machine helper (allowed transitions) keeps the executor + router honest.

**FE**: the "Cây tài liệu" tab → a real 3-tier collapsible tree with class colors, status badges, and a version-history side panel (mirrors the Step-5 redesign discipline: business language, no jargon).

### Phase 2 — Approval Chains + RBAC (migs 121-124) — DESIGNED, deferred

- `approval_chains` + `approval_levels` (level N: role, mode ∈ {one, all, majority, threshold}, `timeout_minutes`, `escalate_to_level`/`escalate_to_role`). Dynamic conditions reuse `policy_rules` (099) — the `finance_invoice_cfo_threshold` rule is the template.
- Extend `workflow_approvals` with `chain_id`, `level`, `escalated_from` (additive nullable). `ApprovalGateExecutor` walks the chain; a new **escalation cron** (Temporal activity, mirrors `memory_*` cadence) checks `sla_minutes` (stored since 089, never enforced) → escalate/skip-OOO/alert.
- `user_department_roles` (user × dept × functional_role) + `workflow_nodes.assigned_role`. Per-document RBAC matrix evaluated in a `require_doc_permission` dependency (extends the existing X-role gate). Department-scoped RLS on `workflows`/`workflow_nodes` via the ABAC GUC already wired in mig 053 (`app.current_department_id`).
- `approval_delegations` (reassign pending approval; logged to `decision_audit_log` with new decision_types).

### Phase 3 — Contracts + e-sign (migs 125-127) — DESIGNED, deferred

- `contracts` (generic): `contract_id`, `enterprise_id`, `department_id`, `workflow_run_id` (source), `contract_no` (auto HD-YYYY-NNN), `title`, `contract_type`, `status ∈ {nhap, cho_ky, hieu_luc, het_han, thanh_ly, tu_choi}`, `value_vnd NUMERIC(20,0)` (K-9), `effective_at`, `expires_at`, `template_file_id`, `signed_file_id`, `renewal_type`.
- `contract_parties` (party_role, internal `user_id` OR external name/email, `sign_order` for sequential vs parallel, `signed` bool).
- `contract_signatures` (**append-only**, K-2 pattern from `bronze_rows`): party, user_id, signed_at, signer_ip, `document_sha256` (non-repudiation), `method ∈ {internal_click, vnpt, docusign}`. v1 = internal_click only.
- New `node_type_catalog` row `contract` + `ContractNodeExecutor`: on activate, instantiate `contracts` from a template, create parties, pause like an approval gate until "all/threshold parties signed", then resume (contract "hiệu lực" → triggers next node).
- Contract lifecycle events: hiệu-lực → trigger next node; từ-chối → create "đàm phán lại" task; T-30d before expiry → alert (reuses the escalation cron).

## Consequences

### Positive
- Tier-3 is fully additive: every new table mirrors the mig-053 RLS+ABAC+grant pattern; every extension is nullable columns on existing tables. Zero churn to auth-service, JWT, or the 45-node catalog/executor registry.
- The existing `policy_rules` engine, `approval_gate` pause/resume, `lane_name` role axis, and `knowledge_documents` version pattern are reused — not reinvented.
- Phase 1 ships standalone value (classified + versioned + status-tracked document tree) without waiting on contracts or the approval chain.
- Contract domain separation keeps `customer_contracts` (Kaori sales) and tenant business contracts from polluting each other's RLS/semantics.

### Negative / accepted trade-offs
- **Phase 0 (MinIO bytes) is a real blocker** to *functional* completeness of Doc Tree + Contract — schema + UI can land first, but uploads can't store/serve PDF bytes until it's wired. Surfaced, not hidden.
- v1 e-sign is internal click-to-sign — legally "internal record", not a certified digital signature; certified providers are a later adapter. Acceptable for internal workflow approvals; flagged for any externally-binding contract.
- The functional roles (executor/reviewer/approver) map onto 4 global roles rather than a true 5-tier global system — simpler + non-disruptive, but department-manager/admin tiers are expressed via `user_department_roles` + `workflow_editors`, not a single global enum.

### Neutral / follow-ups
- Phase 2 escalation cron reuses the Temporal `memory_*` daily-activity pattern (ADR-0036 wiring).
- Migration ledger: 119 (doc requirements), 120 (doc instance extend) this phase; 121-124 (approval/RBAC), 125-127 (contracts) reserved.
- Tests: requirement CRUD + the 7-state document machine + version supersede + enriched tree shape (Phase 1). Each later phase carries its own.

### Wired 2026-05-31 — approval_gate ↔ chain binding (mig 127)

Pilot test of "Giải quyết khiếu nại" surfaced that the runtime executor consumed
`config.approval_chain_id` (Phase 2) but nothing let a workflow step *bind* a
chain — the gate config only exposed a single `approver_role`, so the
multi-level chains configured in "Duyệt & Phân quyền" were unreachable and a
gate could go live "rỗng quyền". Closed end-to-end:

- **mig 127** — `node_type_catalog.approval_gate` config_schema adds
  `approval_chain_id` (preferred) + keeps `approver_role` (fallback); `required`
  drops to `{timeout_action}` (the one-of is enforced at run-readiness, not by
  JSON Schema). Adds a `ui_schema_json` (chain-picker + role-select widgets).
- **FE** `ApprovalGateEditor` (60-workflow-detail.tsx) — chain dropdown from
  `GET /approval-chains` + role fallback + timeout-action; empty-permission
  warning. `decisionSummary` + client-side `activationBlockers` updated.
- **Run-readiness** `workflow_builder._check_approval_gates` — blocks the
  TESTING/ACTIVE_BASELINE transition (`WORKFLOW.EMPTY_APPROVAL_GATE`) when a gate
  has neither a chain-with-≥1-level nor a non-empty role. Runs alongside the
  dangling-branch gate.
- **Executor** `approval.py` — now accepts chain-only gates (defers the
  approver_role requirement; roles come from the chain's level 1) and fails loud
  if a bound chain resolves no roles.
- **Onboarding** `bootstrap_enterprise_from_industry` auto-provisions a default
  single-level chain ("Duyệt 1 cấp — Quản lý", MANAGER) per department.

### Wired 2026-05-31 — BPMN nodes→diagram projection (`POST /workflows/{id}/bpmn/from-steps`)

The BPMN tab only showed a start node because the linear Builder authors
`workflow_nodes` while sync runs BPMN→nodes (Model A *replace*). Added the
reverse projection (reuses `bpmn_mapper.build_bpmn_xml`, synthesises start/end,
read-only on steps) + an FE "Tạo sơ đồ từ bước" button, and a destructive-sync
confirm so the Builder steps aren't silently overwritten.

### Wired 2026-06-01 — requirement-fulfilment upload ("Nộp file") + current-version stats

Phase 1 declared *what* a step needs (`workflow_step_document_requirements`,
119) and the tree rendered the 📥/📤/📎 slots, but a slot had **no way to
actually submit a file** — so every requirement sat at `chờ nộp` and the report
tab counted 0 documents. Closed the loop:

- **FE** `DocSlotRow` (60-workflow-detail.tsx) — a "Nộp file" / "Nộp lại" button
  per slot uploads through the existing `POST /api/v1/upload` tagged with
  `X-Workflow-Step-ID` + `X-Requirement-ID`, a best-effort client SHA-256 hint
  (K-8) and an `Idempotency-Key` (K-13). On success it refetches the tree (slot
  flips to "Đã nộp", file appears) — no reload. Enterprise/user come from the
  JWT (K-12); never sent. Hidden once the slot is `da_duyet`. Routes a PDF/đơn
  through the document ingest path, **not** the analytics column-mapping wizard.
- **BE** `upload.py` accepts the `X-Requirement-ID` header (sync path) and
  forwards it to `ingest_file`, which resolves the requirement's `doc_class`
  from the DB (RLS-scoped, must belong to the node — trust the DB not the
  client, K-1/K-12; fail-soft to a loose attachment if it doesn't match) and
  writes `requirement_id` + `doc_class` on the resulting `workflow_step_documents`
  row across all three insert paths (dedup / unstructured / parse-and-land).
  `status` defaults to `da_nop` (mig 120).
- **Stats** `get_workflow_stats` now counts `AND is_current = TRUE` so superseded
  versions don't inflate the per-step document count.
- Tests: `X-Requirement-ID` forwarding (present / absent / malformed-422) in
  data-pipeline `test_api.py`.
