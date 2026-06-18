# Kaori AI — Workflow Management System
Drag-drop builder · Process Mining · Iterative transformation · Adoption-aware · Runtime-reliable · ROI-quantified
Phiên bản: v2.0 (Comprehensive Rewrite) Phát hành: Tháng 5 / 2026 Audience: Product Lead · UX Designer · Backend Engineer · SRE · Data Engineer · Customer Success · Implementation Consultant · CFO/COO Quan hệ với các docs khác: - Pipeline Unified v1.1 — provides clean data sources mà workflows consume - Reasoning Layer v4.0 — provides AI insights/recommendations mà workflows tích hợp - Playbook v3 — operational deployment context
Cập nhật từ v1.0: - Thêm PART IV — Process Mining & Workflow Discovery - Thêm PART VIII — Adoption Intelligence (organizational behavior layer) - Thêm PART IX — Runtime Reliability Architecture (saga, idempotency, DLQ) - Thêm PART X — Runtime Observability (distributed tracing) - Thêm PART XI — Operational Economics (Net Operational Value engine) - Thêm Workflow as Code, LLM Version Drift, Multi-tenancy Security, Secrets Management - Phase 1 scope thu hẹp đáng kể — phản ánh execution reality

## Triết lý cốt lõi (cập nhật v2.0)
1. WORKFLOW = SỐ HÓA QUY TRÌNH NGHIỆP VỤ
   Mỗi workflow = digital twin của 1 quy trình của 1 phòng ban
   Drag-drop visual, không hard-code

2. PROCESS MINING TRƯỚC, BUILDER SAU
   SME không biết workflow thật của họ là gì
   Cái họ NÓI ≠ cái thực tế DIỄN RA
   AI mine event logs để DISCOVER actual flow
   Builder pre-populated từ discovery → user CHỈNH chứ không build từ đầu

3. CHUYỂN ĐỔI SỐ LÀ ITERATIVE
   60-day baseline → meeting → propose new
   90-day testing parallel → meeting → evaluate
   Không thay thế overnight

4. ADOPTION INTELLIGENCE = MOAT
   Workflow technically correct ≠ Organization accepts it
   Track resistance signals: abandonment, override, bypass, side-channel
   Detect adoption failure EARLY, intervene targeted

5. RUNTIME RELIABILITY = ENTERPRISE-GRADE
   Idempotency, saga pattern, DLQ, exactly-once semantics
   Distributed tracing every workflow run
   Partial failure recovery, event replay

6. WORKFLOW + AI = SYMBIOSIS
   Workflow consume clean data + AI insights
   AI watches execution → surface bottlenecks/risks/opportunities

7. VERSIONING + IMPACT TRANSPARENCY
   Mọi thay đổi versioned
   Impact analysis: data nào affected, downstream nào affected
   Better/worse hiển thị rõ TRƯỚC khi commit

8. OPERATIONAL ECONOMICS — MANAGER LANGUAGE
   Manager nói "lời được bao nhiêu tiền/tháng"
   Net Operational Value (NOV) = revenue impact - (people + infra + AI cost)
   Time-to-payback cho mọi workflow change

9. PLATFORM-SIDE OBSERVABILITY
   Kaori team thấy được customer's workflows + insights
   Pro-active support khi detect issues

10. PRICING-CONSTRAINED CAPABILITY
    Quotas per plan: # workflows, # nodes, AI access, integration depth

## Mục lục
### PART I — TỔNG QUAN
Phần 0. Stack Position · Triết lý · Quan hệ docs
### PART II — WORKFLOW ANATOMY
Phần 1. Workflow Schema (Nodes, Edges, Branches, Conditions)
Phần 2. Node Types Catalog (45 node types in 6 categories)
Phần 3. Workflow Versioning Model
Phần 4. Workflow as Code (YAML import/export)
### PART III — WORKFLOW LIFECYCLE & STATES
Phần 5. 8 Workflow States Model
Phần 6. State Transitions & Approval Gates
Phần 7. 60-Day Baseline Monitoring Phase
Phần 8. 90-Day Testing Phase
Phần 9. Replacement & Migration Strategy
### PART IV — PROCESS MINING & WORKFLOW DISCOVERY ⭐ NEW
Phần 10. Process Mining Architecture & Why
Phần 11. Event Log Sources (8 source types)
Phần 12. Sequence Reconstruction Algorithm
Phần 13. Hidden Workflow & Shadow Process Detection
Phần 14. Bottleneck & Bypass Mining
Phần 15. Discovery → Builder Translation
### PART V — DRAG-DROP WORKFLOW BUILDER (UX)
Phần 16. Builder UX Architecture
Phần 17. Component Library & Templates
Phần 18. Validation & Error Handling
### PART VI — INTEGRATION WITH DATA + AI
Phần 19. Data Binding (Workflow Nodes ↔ Clean Data Sources)
Phần 20. AI Insight Injection (Reasoning Layer Integration)
Phần 21. LLM Version Drift Handling ⭐ NEW
Phần 22. Output Binding
### PART VII — IMPACT ANALYSIS & CHANGE MANAGEMENT
Phần 23. Workflow Change Impact Analysis (4 dimensions)
Phần 24. Data Dependencies Tracking
Phần 25. Better/Worse Comparison Framework
Phần 26. Insight Surfacing of Workflow Changes
### PART VIII — ADOPTION INTELLIGENCE ⭐ NEW
Phần 27. Why Adoption Fails (Psychological + Structural)
Phần 28. Resistance Signals Catalog (9 signals)
Phần 29. Detection Methods per Signal
Phần 30. Adoption Health Score (Composite)
Phần 31. Intervention Playbook
### PART IX — RUNTIME RELIABILITY ARCHITECTURE ⭐ NEW
Phần 32. Idempotency Architecture
Phần 33. Retry & Backoff Strategy
Phần 34. Saga Pattern & Compensating Transactions
Phần 35. Dead-Letter Queue & Event Replay
Phần 36. Partial Failure Recovery & Checkpointing
Phần 37. Exactly-Once vs At-Least-Once Decision Framework
### PART X — RUNTIME OBSERVABILITY ⭐ NEW
Phần 38. Distributed Tracing Model
Phần 39. Workflow Run Trace Schema
Phần 40. Real-Time Execution Dashboard
Phần 41. Runtime Anomaly Detection
### PART XI — OPERATIONAL ECONOMICS (ROI ENGINE) ⭐ NEW
Phần 42. Net Operational Value (NOV) Engine
Phần 43. Revenue Impact Estimation Methodology
Phần 44. Cost Impact Modeling (People + Infra + AI)
Phần 45. Time-to-Payback Calculation
Phần 46. ROI Dashboard for Managers/CFO
### PART XII — DOMAIN-SPECIFIC DB PARAMETERS
Phần 47. Priority Parameters per Domain (6 domains)
Phần 48. Schema Validation in Workflow Deployment
### PART XIII — PRICING & SECURITY
Phần 49. Workflow Quotas per Plan
Phần 50. Feature Gates per Tier
Phần 51. Multi-Tenancy Security ⭐ NEW
Phần 52. Workflow Secrets Management ⭐ NEW
### PART XIV — RISKS & MITIGATIONS
Phần 53. Usability Risks
Phần 54. Technical Risks
Phần 55. Business Risks
Phần 56. Migration Risks
Phần 57. Adoption Risks (Summary)
### PART XV — PLATFORM-SIDE MONITORING
Phần 58. Customer Success Dashboard
Phần 59. Proactive Engagement Triggers
### PART XVI — IMPLEMENTATION
Phần 60. Tech Stack
Phần 61. Phase Scope (REVISED — much tighter)
Phần 62. Quality KPIs

# PART I — TỔNG QUAN
# Phần 0. Stack Position & Architecture
## 0.1 Vai trò trong Kaori Stack (cập nhật v2.0)
┌──────────────────────────────────────────────────────────────┐
│ L5 USER LAYER                                                │
│  - Reports / Insights / Alerts (Reasoning Layer)            │
│  - Workflow Builder UI ◄── PART V                            │
│  - Workflow Runtime Dashboard ◄── PART X                     │
│  - Operational ROI Dashboard ◄── PART XI                     │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ L4.5 ORG INTELLIGENCE LAYER ⭐ NEW v2.0                       │
│  - Process Mining Engine ◄── PART IV                         │
│  - Adoption Intelligence ◄── PART VIII                       │
│  - Operational Economics ◄── PART XI                         │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ L4 ORCHESTRATION                                             │
│  - Workflow Engine (Reliable Runtime) ◄── PART IX            │
│  - Distributed Tracing ◄── PART X                            │
│  - Action Runtime (Pipeline §11)                             │
│  - Memory · Ontology · State Machines                        │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
                  ┌──────────┴──────────┐
                  ▼                     ▼
┌────────────────────────┐    ┌─────────────────────────┐
│ L3 AI/REASONING        │    │ L3 RAG ENGINE           │
│  - Insight Engine      │    │  - Knowledge sources    │
│  - Recommendation      │    │    (Reasoning v4.0)     │
│  - Constraint Engine   │    │                         │
└────────────────────────┘    └─────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ L2 DATA PLANE (Pipeline Unified §1-8)                        │
│  - Bronze · Silver · Gold                                    │
│  - Cleaned, governed data                                    │
└──────────────────────────────────────────────────────────────┘
Workflow System vai trò mở rộng (v2.0): - Discover actual processes từ event logs (Process Mining — PART IV) - Build workflows via drag-drop, pre-populated từ discovery (PART V) - Execute reliably với idempotency, saga, DLQ (PART IX) - Observe every run với distributed tracing (PART X) - Adopt monitor — detect resistance, support adoption (PART VIII) - Quantify ROI — Net Operational Value cho manager (PART XI) - Iterate với 60-day + 90-day cycles (PART III)
## 0.2 Why Workflow System v2.0 (vs v1.0)
v1.0 assumption (FAIL): > “User sẽ tự build workflow của họ”
v2.0 reality: > “SME không biết workflow thật của họ. Process Mining discover trước, user chỉnh sau.”
v1.0 missed: - Adoption layer (workflow chạy được không = người ta dùng) - Runtime reliability (idempotency, saga) - Operational Economics (ngôn ngữ của manager) - Multi-tenancy security depth - LLM version drift
v2.0 addresses tất cả P0 gaps.
## 0.3 Triết lý “Iterative Digital Transformation” (v2.0 expanded)
┌──────────────────────────────────────────────────────────────┐
│  KAORI APPROACH v2.0                                         │
├──────────────────────────────────────────────────────────────┤
│  Phase 0 (Week 1-2): PROCESS MINING ⭐ NEW                    │
│    → Connect to logs/Excel/email/Zalo                        │
│    → Discover ACTUAL workflows (vs claimed)                  │
│    → Surface shadow processes, bypasses, bottlenecks         │
│    → Output: discovered_workflow_v0 (fact-based baseline)    │
│                                                              │
│  Phase 1 (Day 1-60): BASELINE DEPLOYMENT                     │
│    → User reviews discovered workflow in builder             │
│    → User adjusts (rare) hoặc accept-as-is (common)          │
│    → Deploy as ACTIVE_BASELINE                               │
│    → AI observes execution + adoption + economics            │
│                                                              │
│  Phase 2 (Day 60): MEETING #1                                │
│    → Review: performance + adoption + economics              │
│    → Co-design new workflow with department                  │
│    → AI generates proposed_new_v1 with predicted NOV         │
│                                                              │
│  Phase 3 (Day 60-150): TESTING (90 days parallel)            │
│    → Both v1 + v2 run                                        │
│    → A/B compare: performance + adoption + NOV               │
│    → Department adopts gradually                             │
│                                                              │
│  Phase 4 (Day 150): MEETING #2                               │
│    → Evaluate composite (technical + adoption + economic)    │
│    → If better → promote v2 as baseline                      │
│    → If worse → revert + iterate                             │
│                                                              │
│  Phase 5 (Continuous): Monitor + repeat from Phase 1         │
└──────────────────────────────────────────────────────────────┘
Key insight v2.0: Trust is built bằng cách let actual existing process work first (Process Mining ensures this is fact-based), không phải “let what user CLAIMS work first” (v1 assumption — leads to wrong baseline).

# PART II — WORKFLOW ANATOMY
# Phần 1. Workflow Schema
## 1.1 Top-Level Schema
workflow:
  workflow_id: UUID
  tenant_id: UUID
  
  # Identity
  name: string
  name_vi: string
  description: text
  
  # Categorization
  department: string  # 'marketing', 'sales', 'operations', 'finance', 'hr'
  category: string  # 'campaign', 'pipeline', 'inventory', 'reporting', 'compliance'
  business_function: string
  
  # Lifecycle
  state: enum  # See Phần 5
  version: integer
  predecessor_workflow_id: UUID | null
  
  # ⭐ NEW v2.0 — Process Mining provenance
  source: enum  # 'process_mining_discovered' | 'user_built' | 'template_based'
  mining_session_id: UUID | null  # link to discovery session if applicable
  fidelity_to_discovered: numeric  # 0-1, how close to discovered baseline
  
  # Execution
  trigger: object
    type: 'manual' | 'scheduled' | 'event' | 'webhook'
    schedule_cron: string | null
    event_type: string | null
    idempotency_window_seconds: integer  # ⭐ NEW — for runtime reliability
  
  # Structure
  nodes: list[Node]
  edges: list[Edge]
  
  # ⭐ NEW v2.0 — Reliability config
  reliability:
    semantics: 'at_least_once' | 'exactly_once' | 'at_most_once'
    max_retries_default: integer (default 3)
    timeout_seconds: integer (default 1800)
    saga_enabled: bool
    checkpoint_interval_nodes: integer (default 5)
  
  # ⭐ NEW v2.0 — Operational Economics annotations
  economics:
    estimated_revenue_impact_vnd_per_month: numeric | null
    estimated_cost_per_execution_vnd: numeric
    estimated_executions_per_month: integer
    estimated_headcount_impact_fte: numeric  # +/- FTEs
    nov_estimate_vnd_per_month: numeric  # Net Operational Value
  
  # Metadata
  created_at: timestamp
  created_by: user_id
  last_modified_at: timestamp
  last_modified_by: user_id
  
  # Performance (filled by execution)
  avg_execution_time_seconds: numeric
  success_rate_percent: numeric
  total_executions: integer
  
  # ⭐ NEW v2.0 — Adoption metrics
  adoption:
    adoption_health_score: numeric  # 0-100
    abandonment_rate: numeric
    override_rate: numeric
    last_adoption_audit: timestamp
  
  # Permissions
  edit_permissions: list[role]
  view_permissions: list[role]
  execute_permissions: list[role]
  
  # ⭐ NEW v2.0 — Secrets references (not values)
  secrets_used: list[string]  # references to vault keys, never inline
## 1.2 Node Schema (v2.0 expanded)
node:
  node_id: UUID
  workflow_id: UUID
  
  type: NodeType
  category: 'data_input' | 'processing' | 'decision' | 'ai' | 'action' | 'output'
  
  position: {x, y}
  
  config: JSONB  # type-specific
  
  input_ports: list[Port]
  output_ports: list[Port]
  
  # Validation
  is_valid: boolean
  validation_errors: list[string]
  
  # ⭐ NEW v2.0 — Reliability config per node
  reliability:
    idempotent: bool  # is this node naturally idempotent?
    idempotency_key_extractor: string | null  # how to compute idempotency key
    retry_policy:
      max_retries: integer
      backoff: 'exponential' | 'linear' | 'fixed'
      base_delay_seconds: numeric
      max_delay_seconds: numeric
      jitter: bool
    timeout_seconds: integer
    compensating_action: string | null  # for saga rollback
  
  # ⭐ NEW v2.0 — Side-effect classification (critical for reliability)
  side_effect_class: 'pure' | 'read_only' | 'write_idempotent' | 'write_non_idempotent' | 'external_irreversible'
  
  # Execution stats
  avg_runtime_ms: numeric
  last_run_at: timestamp
  last_run_status: 'success' | 'failure' | 'timeout'
  
  cost_per_execution_estimate: numeric
## 1.3 Edge Schema
edge:
  edge_id: UUID
  workflow_id: UUID
  
  source_node_id: UUID
  source_port: string
  
  target_node_id: UUID
  target_port: string
  
  condition: string | null
  data_mapping: object | null
  
  # ⭐ NEW v2.0 — Edge semantics
  delivery_guarantee: 'best_effort' | 'guaranteed' | 'transactional'
  ordering: 'fifo' | 'unordered'
## 1.4 Storage Schema
CREATE TABLE workflows (
  workflow_id UUID PRIMARY KEY,
  tenant_id UUID NOT NULL,
  
  name VARCHAR(500),
  name_vi VARCHAR(500),
  description TEXT,
  
  department VARCHAR(50),
  category VARCHAR(100),
  business_function VARCHAR(100),
  
  state VARCHAR(30),
  version INTEGER,
  predecessor_workflow_id UUID,
  
  -- v2.0
  source VARCHAR(50),
  mining_session_id UUID,
  fidelity_to_discovered NUMERIC,
  
  trigger JSONB,
  nodes JSONB,
  edges JSONB,
  reliability JSONB,
  economics JSONB,
  adoption JSONB,
  
  created_at TIMESTAMPTZ,
  created_by UUID,
  last_modified_at TIMESTAMPTZ,
  last_modified_by UUID,
  
  avg_execution_time_seconds NUMERIC,
  success_rate_percent NUMERIC,
  total_executions BIGINT,
  
  edit_permissions JSONB,
  view_permissions JSONB,
  execute_permissions JSONB,
  
  secrets_used JSONB,
  
  -- Multi-tenancy isolation enforced at DB level
  UNIQUE (tenant_id, name, version)
);

CREATE INDEX idx_workflow_tenant ON workflows (tenant_id);
CREATE INDEX idx_workflow_state ON workflows (state);
CREATE INDEX idx_workflow_dept ON workflows (department);
CREATE INDEX idx_workflow_source ON workflows (source);

-- Row-level security for multi-tenancy
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON workflows
  USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
## 1.5 Acceptance Criteria — Phần 1
☐ Schema supports v2.0 enrichments (reliability, economics, adoption, mining provenance)
☐ Side-effect class enforced per node
☐ Multi-tenancy via row-level security
☐ Secrets only as references, never inline
☐ Versioning + predecessor tracked
☐ Permissions granular

# Phần 2. Node Types Catalog (45 node types in 6 categories)
## 2.1 Side-Effect Classification ⭐ NEW v2.0
Mỗi node được classify để runtime engine biết cách handle retry/saga/idempotency:

| Class | Definition | Retry-safe | Saga-needed |
|---|---|---|---|
| pure | Pure function, no side effects | Yes | No |
| read_only | Reads data, no writes | Yes | No |
| write_idempotent | Writes, but same input → same result | Yes | No |
| write_non_idempotent | Writes that change state on each call | Conditional | Yes |
| external_irreversible | External call cannot undo (e.g., sent email) | No | Yes |

## 2.2 Category 1: Data Input Nodes (8 types)
data_input_nodes:
  
  read_table:
    side_effect_class: read_only
    config: {table, columns, filters, limit}
    output: list of records
    cost: low
  
  read_file_upload:
    side_effect_class: read_only
    config: {file_path, format, sheet_name}
    output: records or document
    cost: low
  
  read_api:
    side_effect_class: read_only  # GET only
    config: {url, method (GET only), headers, auth_ref}
    output: API response
    cost: medium
    risk: external dependency
  
  read_webhook:
    side_effect_class: read_only
    config: {webhook_path, auth}
    output: webhook payload
    cost: low
  
  read_form_submission:
    side_effect_class: read_only
    config: {form_id}
    output: form data
    cost: low
  
  read_email:
    side_effect_class: read_only
    config: {email_account_ref, filter}
    output: email object
    cost: medium
  
  read_calendar:
    side_effect_class: read_only
    config: {calendar_id, time_range}
    output: events
    cost: low
  
  read_chat:
    side_effect_class: read_only
    config: {channel, filter}
    output: messages
    cost: medium
## 2.3 Category 2: Processing Nodes (10 types)
processing_nodes:
  
  filter: {side_effect_class: pure, config: {condition}, cost: low}
  aggregate: {side_effect_class: pure, config: {group_by, aggregations}, cost: medium}
  join: {side_effect_class: pure, config: {join_type, on}, cost: high}
  transform: {side_effect_class: pure, config: {transformations}, cost: low}
  validate: {side_effect_class: pure, config: {schema, on_invalid}, cost: low}
  enrich: {side_effect_class: read_only, config: {lookup_source, key, fields}, cost: medium}
  sort: {side_effect_class: pure, cost: low}
  deduplicate: {side_effect_class: pure, cost: low}
  split: {side_effect_class: pure, cost: low}
  merge: {side_effect_class: pure, cost: low}
## 2.4 Category 3: Decision Nodes (5 types)
decision_nodes:
  
  if_else: {side_effect_class: pure, config: {condition}}
  switch: {side_effect_class: pure, config: {switch_field, cases}}
  wait_for_condition: {side_effect_class: pure, config: {condition, timeout, poll_interval}}
  scheduled_trigger: {side_effect_class: pure, config: {schedule_cron, timezone}}
  approval_gate: {
    side_effect_class: write_idempotent  # idempotent: same approval = same outcome
    config: {approver_role, message, timeout_action}
    note: "Critical for high-stakes workflows"
  }
## 2.5 Category 4: AI Nodes (8 types) — PRICING-LIMITED
ai_nodes:
  
  call_insight_engine:
    side_effect_class: read_only
    config: {insight_type, focus_metric, methods, severity_threshold, llm_pinned_version}  # ⭐ pin LLM version
    output: insight object + confidence
    cost: high (LLM call)
    pricing_tier_required: BASIC+
    rate_limit: 100/day BASIC, 1000/day MID, unlimited MAX
    determinism: "approximate_idempotent"  # ⭐ same input usually → similar output (LLM stochastic)
  
  call_recommendation_engine:
    side_effect_class: read_only
    config: {action_type, constraint_check, llm_pinned_version}
    output: recommendation list
    cost: high
    pricing_tier_required: BASIC+
  
  call_risk_detection:
    side_effect_class: read_only
    config: {risk_categories, severity_threshold}
    cost: high
    pricing_tier_required: MID+
  
  call_forecasting:
    side_effect_class: read_only
    config: {target_metric, horizon_days, method}
    cost: very_high
    pricing_tier_required: MID+
  
  generate_narrative:
    side_effect_class: read_only
    config: {style, language, llm_pinned_version}
    cost: medium
    pricing_tier_required: BASIC+
  
  classify_text:
    side_effect_class: read_only
    config: {categories, multi_label, model_pinned_version}
    cost: medium
    pricing_tier_required: BASIC+
  
  extract_entities:
    side_effect_class: read_only
    config: {entity_types, model_pinned_version}
    cost: medium
    pricing_tier_required: MID+
  
  rag_query:
    side_effect_class: read_only
    config: {knowledge_namespace, max_results}
    cost: medium
    pricing_tier_required: MID+
## 2.6 Category 5: Action Nodes (8 types) — REQUIRES SAGA
action_nodes:
  
  send_email:
    side_effect_class: external_irreversible  # ⭐ cannot un-send
    config: {provider, template, to, subject, content, idempotency_key}
    compensating_action: send_retraction_email  # for saga
    cost: low
    rate_limit: tiered
    
  send_sms:
    side_effect_class: external_irreversible
    compensating_action: none  # SMS truly cannot be retracted
    cost: medium
    pricing_tier_required: BASIC+
  
  send_chat_message:
    side_effect_class: external_irreversible
    compensating_action: delete_message  # if provider supports
    cost: low
  
  create_task:
    side_effect_class: write_idempotent  # idempotency_key prevents duplicate
    compensating_action: delete_task
    cost: low
  
  call_api:
    side_effect_class: configurable  # depends on API behavior
    config: {url, method, auth_ref, idempotency_key}
    compensating_action: configurable  # user-defined
    cost: medium
    risk: external dependency
  
  trigger_workflow:
    side_effect_class: write_idempotent
    config: {workflow_id, trigger_data, idempotency_key}
    compensating_action: cancel_workflow_run
    cost: low
  
  export_file:
    side_effect_class: write_idempotent
    compensating_action: delete_file
    cost: low
  
  generate_report:
    side_effect_class: write_idempotent
    compensating_action: delete_report
    cost: medium
## 2.7 Category 6: Output Nodes (6 types)
output_nodes:
  
  save_to_database:
    side_effect_class: write_idempotent  # if mode=upsert; non_idempotent if insert without key
    config: {table, mode (insert/upsert/replace), idempotency_key}
    compensating_action: delete_records
    cost: low
  
  update_record:
    side_effect_class: write_idempotent
    config: {table, key_field}
    compensating_action: revert_with_snapshot
    cost: low
  
  publish_alert:
    side_effect_class: write_idempotent
    compensating_action: retract_alert
    cost: low
  
  publish_insight:
    side_effect_class: write_idempotent
    compensating_action: retract_insight
    cost: low
  
  display_dashboard:
    side_effect_class: write_idempotent
    cost: low
  
  log:
    side_effect_class: write_idempotent
    cost: low
## 2.8 Node Types Summary Matrix (v2.0)

| Category | # Nodes | Avg Cost | Pricing | Reliability Class Distribution |
|---|---|---|---|---|
| Data Input | 8 | Low-Med | All tiers | All read_only |
| Processing | 10 | Low-Med | All tiers | Mostly pure |
| Decision | 5 | Low | All tiers | Pure + 1 idempotent |
| AI | 8 | High | BASIC+ | All read_only |
| Action | 8 | Low-Med | Some BASIC+ | Mix idempotent + irreversible |
| Output | 6 | Low | All tiers | All idempotent |
| Total | 45 |  |  |  |

Key insight: Most “irreversible” nodes là Action category. Saga pattern (Phần 34) tập trung ở đây.

# Phần 3. Workflow Versioning Model
## 3.1 Versioning Schema
workflow_version:
  workflow_id: UUID
  version: integer
  
  snapshot: object  # full nodes + edges + config
  
  diff_from_previous: object | null
    nodes_added: list
    nodes_removed: list
    nodes_modified: list
    edges_added: list
    edges_removed: list
    config_changes: list
  
  state_at_creation: enum
  created_at: timestamp
  created_by: user_id
  reason: text
  
  approved: bool
  approved_at: timestamp
  approved_by: user_id
  approval_notes: text
  
  performance_vs_previous: object | null
  economics_vs_previous: object | null  # ⭐ NEW v2.0
  adoption_vs_previous: object | null  # ⭐ NEW v2.0
## 3.2 Version Lifecycle
v1 created → DRAFT → ACTIVE_BASELINE
                       ▼ (modifications)
v2 created → TESTING (parallel run with v1)
              ▼ (90 days evaluation)
   APPROVED → v1 archived, v2 becomes baseline
   REJECTED → v2 archived, v1 continues
## 3.3 Version Comparison API
def compare_versions(workflow_id, v_old, v_new):
    return {
        'structural_changes': diff_structure(v_old.snapshot, v_new.snapshot),
        'config_changes': diff_config(v_old.snapshot, v_new.snapshot),
        'performance_diff': compare_performance(v_old, v_new),
        'cost_diff': compare_cost(v_old, v_new),
        'data_dependency_changes': diff_data_deps(v_old, v_new),
        'downstream_impacts': find_downstream_impacts(v_old, v_new),
        'predicted_better_or_worse': predict_outcome(v_old, v_new),
        # v2.0
        'reliability_diff': compare_reliability_config(v_old, v_new),
        'economics_diff': compare_nov(v_old, v_new),  # Net Operational Value
        'adoption_risk_diff': estimate_adoption_risk_change(v_old, v_new)
    }
## 3.4 Acceptance Criteria — Phần 3
☐ Every workflow change creates new version
☐ Diffs auto-computed (structural + economic + adoption)
☐ Performance comparison after sufficient runs
☐ Approval workflow for high-stakes versions
☐ Easy rollback to any previous version

# Phần 4. Workflow as Code (YAML import/export) ⭐ NEW v2.0
Mục đích: Power users + DevOps + version control. Drag-drop là default, nhưng YAML giúp: - Git-based workflow management - Bulk operations (clone, modify, deploy) - CI/CD pipelines for workflow changes - Disaster recovery (export all → re-import)
## 4.1 YAML Schema
# Example: marketing_email_campaign.yaml
apiVersion: kaori.workflow/v2
kind: Workflow
metadata:
  name: marketing_email_campaign
  name_vi: "Chiến dịch email marketing"
  tenant: abc_retail
  department: marketing
  
spec:
  state: ACTIVE_BASELINE
  version: 3
  
  trigger:
    type: scheduled
    cron: "0 9 * * MON"
    idempotency_window_seconds: 300
  
  reliability:
    semantics: at_least_once
    max_retries_default: 3
    timeout_seconds: 1800
    saga_enabled: true
  
  economics:
    estimated_revenue_impact_vnd_per_month: 12000000
    estimated_cost_per_execution_vnd: 2900
    estimated_executions_per_month: 4
    nov_estimate_vnd_per_month: 11990000  # ~12M revenue - ~12K cost
  
  nodes:
    - id: read_customers
      type: data_input.read_table
      side_effect_class: read_only
      config:
        table: silver.customers
        filters:
          - "subscribed = true"
          - "active = true"
    
    - id: generate_content
      type: ai.generate_personalized_content
      side_effect_class: read_only
      config:
        template_id: newsletter_v3
        llm_pinned_version: claude-sonnet-4.0  # ⭐ pin model version
        personalization_fields: [first_name, interest_category]
      reliability:
        max_retries: 2
        timeout_seconds: 30
    
    - id: send
      type: action.send_email
      side_effect_class: external_irreversible
      config:
        provider: sendgrid
        from: newsletter@company.com
        idempotency_key: "{{customer_id}}_{{campaign_id}}_{{date}}"
      reliability:
        max_retries: 5
        backoff: exponential
        base_delay_seconds: 1
  
  edges:
    - from: read_customers.customers
      to: generate_content.customer
      iteration: for_each
    - from: generate_content.email_content
      to: send.content
  
  permissions:
    edit: [marketing_lead, admin]
    view: [marketing_team]
    execute: [marketing_team, automation_service]
  
  secrets_used:
    - sendgrid_api_key
## 4.2 Import/Export API
class WorkflowAsCode:
    
    def export(workflow_id) -> str:
        """Export workflow as YAML."""
        wf = get_workflow(workflow_id)
        return yaml.dump(serialize_to_kaori_v2_schema(wf))
    
    def import_yaml(yaml_text, tenant_id, dry_run=False):
        """Import YAML, validate, create or update workflow."""
        parsed = yaml.safe_load(yaml_text)
        validate_schema(parsed, schema='kaori.workflow/v2')
        
        if dry_run:
            return ValidationResult(parsed)
        
        existing = find_workflow(tenant_id, parsed.metadata.name)
        if existing:
            return create_new_version(existing, parsed)
        else:
            return create_workflow(tenant_id, parsed)
    
    def diff(yaml_old, yaml_new):
        """Show diff between two YAML versions."""
        return generate_yaml_diff(yaml_old, yaml_new)
## 4.3 CI/CD Integration
# Example .github/workflows/kaori-deploy.yml
on: [push]

jobs:
  deploy_workflows:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Validate workflows
        run: |
          for f in workflows/*.yaml; do
            kaori-cli validate $f
          done
      
      - name: Deploy to staging
        if: github.ref == 'refs/heads/develop'
        run: |
          for f in workflows/*.yaml; do
            kaori-cli import $f --env staging --tenant ${{ secrets.STAGING_TENANT }}
          done
      
      - name: Deploy to production
        if: github.ref == 'refs/heads/main'
        run: |
          for f in workflows/*.yaml; do
            kaori-cli import $f --env production --tenant ${{ secrets.PROD_TENANT }} --require-approval
          done
## 4.4 Acceptance Criteria — Phần 4
☐ Bidirectional drag-drop ↔ YAML
☐ YAML schema validated against kaori.workflow/v2
☐ CLI tool for import/export/diff/validate
☐ Git-friendly (deterministic ordering)
☐ CI/CD examples documented

# PART III — WORKFLOW LIFECYCLE & STATES
# Phần 5. 8 Workflow States Model
┌──────────────────────────────────────────────────────────────┐
│   1. DRAFT             User đang xây, chưa hoàn thành        │
│   2. REVIEWING         Đang chờ peer/dept-head approval      │
│   3. ACTIVE_BASELINE   Đang chạy production (60-day kicks)   │
│   4. EVALUATING        Sau 60d, đang phân tích (Meeting #1)  │
│   5. PROPOSED_NEW      New workflow design, chờ approve test │
│   6. TESTING           Parallel với baseline, 90-day A/B     │
│   7. APPROVED_REPLACEMENT   Approved, transitioning          │
│   8. ARCHIVED          Đã bị replace, preserved cho audit    │
└──────────────────────────────────────────────────────────────┘
## 5.1 State Transition Diagram
         ┌─────────┐
         │ DRAFT   │
         └────┬────┘
              │ submit
              ▼
         ┌──────────┐
         │REVIEWING │
         └────┬─────┘
              │ approve
              ▼
         ┌──────────────────┐
         │ ACTIVE_BASELINE  │ ← 60-day monitoring
         └────┬─────────────┘
              │
              ▼
         ┌──────────────┐
         │ EVALUATING   │ ← Meeting #1
         └────┬─────────┘
              │ design new
              ▼
         ┌──────────────┐
         │ PROPOSED_NEW │
         └────┬─────────┘
              │ approve test
              ▼
         ┌──────────────┐
         │TESTING (90d) │ ← parallel run
         └────┬─────────┘
              │ Meeting #2
              ▼
         ┌────┴─────┐
         ▼          ▼
    APPROVED_     REJECTED  
    REPLACEMENT
         │
         ▼
    ┌────────────────┐
    │ Old → ARCHIVED │
    │ New → ACTIVE_  │
    │   BASELINE     │
    └────────────────┘
## 5.2 State Properties
state_properties:
  
  DRAFT:
    visible_to: [creator, edit_permissions]
    executable: false
    can_edit: yes
    can_delete: yes
    auto_save: every 30 seconds
  
  REVIEWING:
    visible_to: [creator, reviewers, dept_head]
    executable: false
    can_edit: limited (comments only)
    requires_approval_from: department_head
    sla: 5 working days (auto-escalate)
  
  ACTIVE_BASELINE:
    visible_to: [department members, dept_head, manager]
    executable: yes
    can_edit: NO (only via versioning)
    monitoring: yes (60-day kick-off)
    deletion: requires manager + admin approval
  
  EVALUATING:
    visible_to: [department, manager, kaori_team]
    executable: yes (continues running)
    can_edit: no
    duration: typically 1-2 weeks
    output: evaluation_report (Phần 7)
  
  PROPOSED_NEW:
    visible_to: [department, manager]
    executable: false (not yet)
    can_edit: yes (refining design)
    requires_approval_from: dept_head + manager
  
  TESTING:
    visible_to: [department, manager, kaori_team]
    executable: yes (alongside baseline)
    can_edit: limited (config tweaks)
    duration: 90 days strict
    monitoring: enhanced (compare with baseline)
  
  APPROVED_REPLACEMENT:
    visible_to: [department, manager]
    executable: yes
    duration: 1-2 weeks transition
    actions: [migrate dependents, archive old]
  
  ARCHIVED:
    visible_to: [audit team, kaori_team]
    executable: false
    retention: 7 years
    purpose: reference + audit
## 5.3 State History Storage
CREATE TABLE workflow_state_history (
  workflow_id UUID,
  version INTEGER,
  state VARCHAR(30),
  entered_at TIMESTAMPTZ,
  exited_at TIMESTAMPTZ,
  
  transition_reason TEXT,
  transition_actor UUID,
  approval_record JSONB,
  
  performance_snapshot JSONB,
  economics_snapshot JSONB,  -- v2.0
  adoption_snapshot JSONB,   -- v2.0
  
  PRIMARY KEY (workflow_id, version, state, entered_at)
);
## 5.4 Acceptance Criteria — Phần 5
☐ All 8 states implemented
☐ State transitions audited (immutable log)
☐ Approval gates enforced
☐ Visibility rules respected
☐ Auto-escalation on stuck states
☐ Snapshots include economics + adoption (v2.0)

# Phần 6. State Transitions & Approval Gates
## 6.1 Transition Rules Matrix
allowed_transitions:
  
  from_DRAFT:
    to_REVIEWING: required = none (any user can submit own draft)
    to_DELETED: required = creator
  
  from_REVIEWING:
    to_DRAFT: required = creator (withdraw)
    to_ACTIVE_BASELINE: required = department_head_approval
    to_REJECTED: required = department_head
  
  from_ACTIVE_BASELINE:
    to_EVALUATING: automatic after 60 days
    to_DEPRECATED: required = manager
  
  from_EVALUATING:
    to_ACTIVE_BASELINE: if no changes proposed
    to_PROPOSED_NEW: when new version designed
  
  from_PROPOSED_NEW:
    to_TESTING: required = department_head + manager
    to_DRAFT: required = creator (withdraw)
    to_REJECTED: required = department_head
  
  from_TESTING:
    to_APPROVED_REPLACEMENT: required = department_head + manager (after 90 days)
    to_DRAFT: required = manager (back to drawing board)
    to_REJECTED: required = manager
  
  from_APPROVED_REPLACEMENT:
    to_ACTIVE_BASELINE: automatic
    Old → ARCHIVED: automatic
## 6.2 Approval Gate Configuration
approval_gates:
  
  reviewing_to_active:
    approvers_required: 1
    approver_role: 'department_head'
    sla_days: 5
    escalation: manager after 5 days
  
  proposed_to_testing:
    approvers_required: 2
    approver_roles: ['department_head', 'manager']
    sla_days: 7
    requires_review_data: yes  # 60-day analysis must be reviewed
  
  testing_to_replacement:
    approvers_required: 2
    approver_roles: ['department_head', 'manager']
    sla_days: 14  # important decision
    requires_review_data: yes
    requires_sign_off:
      - performance_comparison
      - data_impact_analysis
      - downstream_impact_analysis
      - economics_comparison  # ⭐ v2.0
      - adoption_health_comparison  # ⭐ v2.0
## 6.3 Transition Side Effects
def execute_transition(workflow_id, from_state, to_state, actor, reason):
    workflow = get_workflow(workflow_id)
    
    validate_transition_allowed(from_state, to_state, actor)
    validate_required_data_present(workflow, to_state)
    
    record_state_change(workflow_id, from_state, to_state, actor, reason)
    
    if to_state == 'ACTIVE_BASELINE':
        kick_off_60_day_monitoring(workflow_id)
        notify_department(workflow_id, 'workflow_now_live')
        register_with_action_runtime(workflow_id)
        # v2.0: kick off adoption tracking
        initialize_adoption_tracker(workflow_id)
        # v2.0: initialize NOV baseline
        capture_economics_baseline(workflow_id)
    
    elif to_state == 'EVALUATING':
        generate_60_day_evaluation_report(workflow_id)
        schedule_meeting_1(workflow_id)
        notify_kaori_team(workflow_id, 'evaluation_phase')
    
    elif to_state == 'TESTING':
        kick_off_90_day_testing(workflow_id)
        deploy_parallel_run(workflow_id, baseline_workflow_id=workflow.predecessor)
        register_ab_comparison(workflow_id, baseline_workflow_id)
    
    elif to_state == 'APPROVED_REPLACEMENT':
        plan_migration(workflow_id)
        notify_dependents(workflow_id, 'replacement_imminent')
    
    elif to_state == 'ARCHIVED':
        cleanup_active_runs(workflow_id)
        preserve_for_audit(workflow_id, retention_years=7)

# Phần 7. 60-Day Baseline Monitoring Phase
## 7.1 What Gets Monitored (v2.0 expanded)
60_day_monitoring_metrics:
  
  execution_metrics:
    - total_executions_count
    - executions_per_day_distribution
    - success_rate_overall + per_node
    - failure_modes (categorized)
    - retry_rate
  
  performance_metrics:
    - end_to_end_runtime_seconds (avg, p50, p95, p99)
    - per_node_runtime_seconds
    - bottleneck_node_identification
    - throughput
  
  cost_metrics:
    - ai_api_calls_count + cost
    - external_api_calls_count + cost
    - estimated_cost_per_execution
    - total_cost_period
  
  business_outcome_metrics:
    - business_kpis_affected_by_workflow
    - kpi_movement_during_period
    - correlation: workflow execution vs KPI change
  
  user_interaction_metrics:
    - manual_interventions_count
    - approval_gate_response_times
    - human_override_rate
    - workflow_abandonment_rate
  
  exception_metrics:
    - data_quality_issues
    - schema_change_breaks
    - external_dependency_failures
    - rate_limit_hits
  
  # ⭐ v2.0 — Adoption Intelligence (PART VIII)
  adoption_metrics:
    - resistance_signal_count_by_type
    - side_channel_communication_count
    - bypass_attempts
    - adoption_health_score
  
  # ⭐ v2.0 — Operational Economics (PART XI)
  economics_metrics:
    - actual_revenue_impact_vnd
    - actual_total_cost_vnd
    - actual_nov_vnd
    - vs_predicted_nov_variance_pct
    - time_to_payback_days
## 7.2 60-Day Evaluation Report (v2.0 expanded)
60_day_evaluation_report:
  
  workflow_id: UUID
  workflow_name: string
  monitoring_period: [start_date, end_date]
  
  ─── PERFORMANCE SUMMARY ───
  total_executions: 1247
  success_rate: 87.3%
  failure_rate: 12.7%
  avg_runtime: 4m 23s
  p95_runtime: 11m 15s
  
  ─── BOTTLENECKS IDENTIFIED ───
  Node 'enrichment_step_3':
    avg_runtime: 2m 48s (60% of total)
    failure_rate: 8% (highest)
    manual_interventions: 47 cases
  → Likely root cause: external API rate limits
  → Recommendation: Add caching node + retry logic
  
  ─── BUSINESS OUTCOME CORRELATION ───
  KPIs correlated with workflow:
    - email_open_rate: -3.2%  ⚠️
    - email_click_rate: -1.8%
    - newsletter_unsubscribe_rate: +0.7%
  → Concerning trend
  → Hypothesis: Personalization quality declining
  
  ─── COST ANALYSIS ───
  Total cost: 4.2M VND
  Cost per execution: 3,367 VND
  Industry benchmark: 2,500-3,000 VND
  → Slightly above benchmark
  
  ─── ADOPTION HEALTH (v2.0) ───
  Adoption score: 72/100
  Signal breakdown:
    - Manual override rate: 23% (HIGH — concerning)
    - Approval delays avg: 2.3h (HIGH)
    - Side-channel communications detected: 14 in period
    - Workflow abandonment: 8% (acceptable)
  → Diagnosis: Department finds approval step burdensome,
    bypassing via Zalo-direct communications
  
  ─── OPERATIONAL ECONOMICS (v2.0) ───
  Predicted NOV: 11M VND/month
  Actual NOV: 8.2M VND/month  (variance: -25%)
  
  Breakdown:
    Revenue impact: +9.5M (predicted +12M)
    People cost: -0.8M (overhead from manual interventions)
    Infra cost: -0.3M
    AI cost: -0.2M
  
  Time to payback: not yet (continues monitoring)
  
  ─── EXCEPTIONS & PAIN POINTS ───
  Top 5 issues:
    1. Data missing for 23 customer records (1.8%)
    2. Email bounce rate 4.2% (target < 2%)
    3. Manual approval delays avg 2.3h
    4. Schema change in source table → 1d downtime
    5. AI personalization fallback triggered 14 times
  
  ─── RECOMMENDED IMPROVEMENTS ───
  Priority 1 (high impact, low effort):
    - Add data validation node before personalization
    - Implement bounce list checking
    - Cache enrichment lookups (TTL 24h)
    - ⭐ Replace approval gate with auto-approve for routine cases
      (reduces override rate, improves adoption)
  
  Priority 2 (medium):
    - Add fallback content when AI personalization fails
  
  Priority 3 (high impact, high effort):
    - Migrate to event-driven trigger
    - Multi-stage personalization with A/B testing
  
  ─── PROPOSED NEW WORKFLOW (v2 draft) ───
  Auto-generated as PROPOSED_NEW state.
  Key changes from v1:
    - +2 nodes (validation, cache)
    - 1 node modified (personalization with fallback)
    - 1 approval gate REMOVED for routine cases
  
  Expected improvements:
    - Success rate: 87% → 94% (+7pp)
    - Avg runtime: 4m 23s → 3m 10s (-28%)
    - Cost per exec: 3,367 → 2,892 VND (-14%)
    - Email bounce: 4.2% → 2.1% (-50%)
    - Adoption score: 72 → 85 (+13 points, fewer overrides)
    - Predicted NOV: 8.2M → 11.5M VND/month (+40%)
  
  Recommendation: Approve for 90-day TESTING phase
## 7.3 Mid-Period Insights
Don’t wait 60 days. AI continuously surfaces:
mid_period_triggers:
  
  performance_degradation:
    - "Workflow X success rate dropped to 76% on day 23"
  
  adoption_red_flags:  # ⭐ v2.0
    - "Override rate spiked from 12% to 31% this week"
    - "5 side-channel communications detected today (was 0/week)"
  
  economics_red_flags:  # ⭐ v2.0
    - "Actual NOV trending 40% below predicted"
    - "Cost overrun: AI calls 3x expected"
  
  notify:
    - real_time_alerts: critical
    - daily_digest: performance
    - weekly_report: trends + recommendations

# Phần 8. 90-Day Testing Phase
## 8.1 Parallel Run Architecture
              Production traffic
                     ▼
              Workflow Router
                     ▼
            ┌────────┴────────┐
            ▼                 ▼
       BASELINE (v1)     NEW (v2)
            ▼                 ▼
         Outputs          Outputs
            ▼                 ▼
       Compared in real-time
            ▼
      A/B Comparison Engine
            ▼
       Daily comparison report
       (perf + adoption + NOV)
## 8.2 Routing Strategies
routing_strategies:
  
  strategy_1_full_parallel:
    description: "Both workflows process all events"
    use_case: "Read-only workflows (no side effects)"
    pros: "Maximum data for comparison"
    cons: "2x execution cost"
  
  strategy_2_shadow:
    description: "Both run, only baseline acts on output"
    use_case: "Workflows with side effects (email, API)"
    pros: "Safe — new workflow doesn't affect production"
    cons: "Can't measure real-world outcome of new"
  
  strategy_3_canary:
    description: "X% traffic to new, rest to baseline"
    use_case: "Confident about new, want gradual rollout"
    starting: 5% → 10% → 25% → 50% → 75% → 100%
    pros: "Real-world testing with limited risk"
    cons: "Complex routing"
  
  strategy_4_segmented:
    description: "Specific segments use new, rest baseline"
    use_case: "Targeted at specific use case"
    example: "VIP customers use new workflow"
    pros: "Targeted testing"
    cons: "Selection bias"
## 8.3 Comparison Metrics (v2.0 expanded)
ab_comparison_metrics:
  
  reliability:
    - success_rate_difference
    - error_type_distribution_change
    - retry_pattern_change
    - saga_compensation_rate  # ⭐ v2.0
  
  performance:
    - runtime_change_distribution
    - throughput_change
    - resource_usage_change
  
  cost:
    - cost_per_execution_change
    - total_cost_projection
  
  quality:
    - output_quality_score_change
    - business_kpi_impact (downstream)
    - user_satisfaction_change
  
  safety:
    - error_rate_change
    - constraint_violations
    - manual_override_rate_change
  
  # ⭐ v2.0
  adoption:
    - adoption_health_score_change
    - resistance_signal_change
    - side_channel_communication_change
  
  # ⭐ v2.0
  economics:
    - nov_change_vnd_per_month
    - revenue_impact_change
    - cost_impact_change
    - time_to_payback_change
## 8.4 Daily Comparison Report (v2.0)
daily_ab_comparison:
  
  date: "2026-04-15"
  test_day: 23 of 90
  
  ─── SUCCESS RATE ───
  Baseline: 87.5%
  New:      93.1%
  Diff:     +5.6pp (p < 0.001)
  
  ─── RUNTIME ───
  Baseline: 4m 21s avg
  New:      3m 14s avg
  Diff:     -25.7%
  
  ─── COST PER EXECUTION ───
  Baseline: 3,371 VND
  New:      2,892 VND
  Diff:     -14.2%
  
  ─── DOWNSTREAM IMPACT ───
  Email open rate (24h after):
    Baseline: 22.3%
    New:      24.1%
    Diff:     +1.8pp
  
  ─── ADOPTION COMPARISON (v2.0) ───
  Baseline override rate: 23%
  New override rate:       8%
  → Adoption improving with new
  
  Side-channel comms baseline: 14 in period
  New:                          3 in period
  → Department engaging with new workflow vs bypassing
  
  ─── ECONOMICS COMPARISON (v2.0) ───
  Baseline NOV: 8.2M VND/month (actual)
  New NOV:      11.7M VND/month (extrapolated from 23 days)
  → Diff: +3.5M VND/month
  → Annual: +42M VND
  → ROI on workflow change: 18-month payback at this rate
  
  ─── PROJECTION ───
  At day 90, expected:
    Success rate diff: +5-7pp (CI: +3.2pp to +8.1pp)
    Cost savings: ~7M VND/month projected
    KPI improvement: +1.5-2.5pp open rate
    Adoption score improvement: +13-18 points
    NOV improvement: +35M-45M VND/year
## 8.5 90-Day Decision Framework (v2.0)
def evaluate_90_day_results(test_workflow_id, baseline_workflow_id):
    comparison = aggregate_90_day_comparison(test_workflow_id, baseline_workflow_id)
    
    # v2.0: composite criteria including adoption + economics
    criteria = {
        # Technical
        'reliability_better': comparison.success_rate_diff > 0,
        'reliability_significant': comparison.success_rate_p_value < 0.05,
        'performance_better': comparison.runtime_diff < 0,
        'cost_acceptable': comparison.cost_diff <= 0 OR business_value_offset > 0,
        'quality_improved': comparison.business_kpi_diff > 0,
        'no_critical_failures': comparison.critical_failures_in_new == 0,
        'safety_improved_or_equal': comparison.constraint_violations_diff <= 0,
        # v2.0 adoption criteria
        'adoption_improved': comparison.adoption_score_diff > 0,
        'no_adoption_red_flags': comparison.side_channel_comms_increase < 0,
        # v2.0 economics criteria
        'nov_improved': comparison.nov_diff_vnd > 0,
        'roi_positive': comparison.time_to_payback_days < 365
    }
    
    score = sum(criteria.values()) / len(criteria)
    
    # Hard floors
    if not criteria['no_critical_failures']:
        return 'REJECT'  # safety override
    if not criteria['no_adoption_red_flags']:
        return 'EXTEND_TESTING'  # adoption issue, need more data
    
    if score >= 0.85:
        recommendation = 'APPROVE_REPLACEMENT'
    elif score >= 0.70:
        recommendation = 'APPROVE_WITH_MODIFICATIONS'
    elif score >= 0.50:
        recommendation = 'EXTEND_TESTING_60_MORE_DAYS'
    else:
        recommendation = 'REJECT_KEEP_BASELINE'
    
    return {
        'recommendation': recommendation,
        'criteria': criteria,
        'score': score,
        'detailed_comparison': comparison,
        'rationale': generate_rationale(criteria, comparison),
        'meeting_2_agenda': prepare_meeting_2_materials(comparison)
    }

# Phần 9. Replacement & Migration Strategy
## 9.1 Migration Plan
After APPROVED_REPLACEMENT:
       ▼
Step 1: Identify dependents
  - Other workflows consuming this output
  - Reports/dashboards using data
  - Alerts triggered
  - Downstream processes
       ▼
Step 2: Migration window scheduling
  - Default: 14 days transition
  - Customer can extend
       ▼
Step 3: Dependent migration
  - Update edge configs
  - Update report bindings
  - Update alert subscriptions
       ▼
Step 4: Final cutover
  - Old → ARCHIVED
  - New → ACTIVE_BASELINE
  - 60-day monitoring resets for new baseline
       ▼
Step 5: Post-migration verification (7 days)
  - Monitor breaking changes
  - Quick rollback path available 30 days
## 9.2 Rollback Provision
def rollback_replacement(workflow_id, reason):
    if days_since_migration(workflow_id) > 30:
        return error("Rollback not allowed after 30 days")
    
    new_workflow = get_active_workflow(workflow_id)
    old_workflow = get_archived_predecessor(new_workflow.id)
    
    old_workflow.state = 'ACTIVE_BASELINE'
    new_workflow.state = 'ARCHIVED_AFTER_ROLLBACK'
    
    migrate_dependents_back(new_workflow.id, old_workflow.id)
    notify_rollback(workflow_id, reason)
    schedule_review_meeting(workflow_id, 'rollback_post_mortem')

# PART IV — PROCESS MINING & WORKFLOW DISCOVERY ⭐ NEW v2.0
# Phần 10. Process Mining Architecture & Why
## 10.1 The Critical Insight
Vấn đề: SME không biết workflow thật của họ.
What managers SAY:
   Lead → Sales contact → Quote → Approval → Close

What logs SHOW:
   Lead arrives in CRM
     → Sales doesn't see for 4 hours (no notification setup)
     → Sales calls customer
     → Customer asks for info, sales sends via Zalo (off-system)
     → Quote made in Excel (not CRM)
     → Quote sent via email (not tracked)
     → Manager approves in face-to-face conversation (not in system)
     → Sometimes approval skipped entirely for known customers
     → Deal closed in CRM (status updated retroactively, missing dates)
     → Customer onboarding emails sent late (no automation)

Reality: 11 actual steps vs 5 claimed steps.
4 of 11 happen OFF-SYSTEM (Zalo, email, in-person, Excel).
Hệ quả nếu không Process Mining: - User builds workflow from “what they think happens” → workflow ≠ reality - Adoption fails: people keep doing what they actually do (off-system) - Optimization based on fictional baseline → wasted effort - Manager surprised by results that don’t match expectations
## 10.2 Process Mining Architecture
┌──────────────────────────────────────────────────────────────┐
│ EVENT LOG SOURCES (Phần 11)                                  │
│  - DB transaction logs                                       │
│  - CRM/ERP action logs                                       │
│  - Excel file modification timestamps                        │
│  - Email metadata (subject, from, to, time)                  │
│  - Zalo/Slack/Teams message logs                             │
│  - Calendar events                                           │
│  - Phone call logs                                           │
│  - Document edit history                                     │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ INGESTION & NORMALIZATION                                    │
│  - Connector library (50+ source types)                     │
│  - Schema normalization to event log format:                 │
│    {case_id, activity, timestamp, actor, attributes}         │
│  - Privacy filtering (PII redaction option)                  │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ SEQUENCE RECONSTRUCTION (Phần 12)                            │
│  - Group events by case_id                                   │
│  - Sort by timestamp                                         │
│  - Identify recurring patterns                               │
│  - Algorithms: Alpha Miner, Heuristic Miner, Inductive Miner│
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ PATTERN DETECTION (Phần 13-14)                               │
│  - Hidden workflows (off-system steps)                       │
│  - Shadow processes (parallel unofficial flows)              │
│  - Approval bypasses                                         │
│  - Bottlenecks (where time is lost)                          │
│  - Rework loops (going back to earlier step)                 │
│  - Outliers (unusual cases)                                  │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ DISCOVERY OUTPUT                                             │
│  - Process map (visual)                                      │
│  - Frequency statistics                                      │
│  - Variant analysis (top 5 variants)                         │
│  - Conformance to claimed flow                               │
│  - Anomaly catalog                                           │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ TRANSLATION TO BUILDER (Phần 15)                             │
│  - Generate proposed workflow YAML                           │
│  - Pre-populate drag-drop builder                            │
│  - Highlight off-system steps for user decision              │
│  - User reviews + accepts/modifies                           │
└──────────────────────────────────────────────────────────────┘
## 10.3 Why This is the Moat
competitive_landscape:
  
  workflow_tools_today:
    - n8n, Zapier, Make: drag-drop, NO process mining
    - Monday, Asana: project management, NO process mining
    - Power Automate: drag-drop + simple triggers, NO real PM
    - Pega, ServiceNow: enterprise, expensive, complex
  
  process_mining_tools_today:
    - Celonis: $13B company, enterprise-only
    - UiPath Process Mining: enterprise focus
    - Disco: standalone, no workflow execution
    - SAP Signavio: SAP ecosystem only
  
  kaori_unique_position:
    - First to combine PM + workflow execution + AI insights
    - SME-priced (not $100K+ enterprise)
    - Vietnamese market context (Zalo integration, Vietnamese ERP support)
    - Iterative transformation philosophy (60-90 day cycles)
## 10.4 Acceptance Criteria — Phần 10
☐ Architecture documented end-to-end
☐ Connector library covers 8+ source types (Phần 11)
☐ Sequence reconstruction algorithm implemented
☐ Pattern detection covers shadow + bypass + bottleneck
☐ Output translates to builder YAML

# Phần 11. Event Log Sources (8 source types)
## 11.1 Source Type Inventory
event_log_sources:
  
  source_1_database_logs:
    description: "Transaction logs from operational DBs"
    examples: ["MySQL binlog", "PostgreSQL WAL", "MongoDB oplog"]
    granularity: per-transaction
    typical_events_extractable:
      - record created/updated/deleted
      - status changes
      - approval flag flips
    privacy: high control (can filter PII at source)
    coverage: HIGH (all DB-mediated processes)
    setup_complexity: medium (requires DBA access)
  
  source_2_application_audit_logs:
    description: "App-level audit trails"
    examples: ["CRM action log", "ERP transaction log", "Custom app logs"]
    granularity: per-user-action
    typical_events:
      - login/logout
      - record viewed/edited
      - report generated
      - workflow triggered
    privacy: medium (often has user PII)
    coverage: HIGH (in-system actions)
    setup_complexity: medium (API access needed)
  
  source_3_excel_file_history:
    description: "Excel modification metadata"
    examples: ["File timestamps", "Cell change tracking", "OneDrive history"]
    granularity: per-save (not per-cell typically)
    typical_events:
      - file created
      - file modified (by whom)
      - file shared
      - file approved (filename change pattern)
    privacy: medium
    coverage: CRITICAL for SME Việt (Excel = de facto database)
    setup_complexity: low (file system + cloud storage APIs)
  
  source_4_email_metadata:
    description: "Email headers (NOT body, privacy)"
    examples: ["Outlook history", "Gmail metadata API", "SMTP logs"]
    granularity: per-email
    typical_events:
      - email sent/received
      - subject classification (routine vs decision-making)
      - attachment patterns
    privacy: HIGH concern (need consent + redaction)
    coverage: HIGH (decisions often made via email)
    setup_complexity: medium (OAuth + scoping)
  
  source_5_zalo_slack_teams:
    description: "Chat platform message logs"
    examples: ["Zalo Business API", "Slack Audit Logs", "Teams Activity"]
    granularity: per-message
    typical_events:
      - 1-on-1 vs group chat
      - message frequency patterns
      - file sharing
      - reactions/responses
    privacy: HIGH concern
    coverage: CRITICAL for SME Việt (Zalo = primary biz comms)
    setup_complexity: medium-high (Zalo Business API integration)
  
  source_6_calendar_events:
    description: "Meeting + scheduling data"
    examples: ["Google Calendar", "Outlook Calendar"]
    granularity: per-event
    typical_events:
      - meeting scheduled/attended
      - meeting type (1-on-1 vs team)
      - duration patterns
    privacy: medium (attendee lists)
    coverage: medium (meeting-based decisions)
    setup_complexity: low (standard APIs)
  
  source_7_phone_call_logs:
    description: "Call records from VoIP/PBX"
    examples: ["Twilio logs", "Vietnam VoIP providers", "Call center systems"]
    granularity: per-call
    typical_events:
      - call made/received
      - duration
      - outcome tag (if CRM-linked)
    privacy: medium-high
    coverage: HIGH for sales/support workflows
    setup_complexity: high (depends on provider)
  
  source_8_document_edit_history:
    description: "Google Docs / Office 365 edit logs"
    examples: ["Google Drive activity API", "SharePoint version history"]
    granularity: per-edit
    typical_events:
      - document created/edited
      - shared/permission changes
      - comments added
    privacy: medium
    coverage: medium (knowledge work processes)
    setup_complexity: medium
## 11.2 Event Normalization Schema
All sources normalized to common format:
@dataclass
class ProcessMiningEvent:
    event_id: UUID
    case_id: str  # what business case this belongs to (e.g., "lead_12345")
    activity: str  # what happened (e.g., "lead_qualified", "quote_sent")
    timestamp: datetime
    actor: str  # who did it (user_id, system, or "external")
    
    source_type: str  # one of 8 source types
    source_record_id: str  # original record ID for traceability
    
    attributes: dict  # flexible bag for source-specific data
    # Examples:
    # - email source: {subject, sender_domain, to_count}
    # - DB source: {table, operation, record_id}
    # - chat source: {channel_type, message_length}
    
    pii_redacted: bool  # was this event run through PII redaction?
    confidence: float  # how confident we are in this event extraction (0-1)
## 11.3 Privacy Architecture
privacy_controls:
  
  consent_management:
    - tenant_admin_must_consent: per source_type
    - user_consent_for_personal_email_zalo: required
    - revocable_anytime: yes
  
  pii_handling:
    - default: redact_all_pii (names → roles, emails → domains)
    - opt_in_for_full_detail: tenant choice
    - never_send_to_external_services: rule
    - retention: configurable, default 12 months
  
  data_residency:
    - vietnam_first: data stays in VN region
    - cross_region_transfer: only with explicit consent
  
  audit:
    - every_pm_query_logged
    - tenant_can_view_who_accessed_what
## 11.4 Connector Implementation Priority
connector_priority:
  
  phase_1_must_have:
    - postgres_log_reader (most common DB)
    - excel_filesystem_watcher (universal SME)
    - zalo_business_api (Vietnam-critical)
    - gmail_metadata_oauth (universal)
    - csv_file_uploader (manual fallback)
  
  phase_2_should_have:
    - mysql_binlog_reader
    - outlook_metadata
    - slack_audit_logs
    - google_calendar
    - common_vietnam_erp_connectors (Misa, Fast, Bravo)
  
  phase_3_nice_to_have:
    - sharepoint_activity
    - twilio_call_logs
    - sap_audit_logs
    - oracle_logs
    - mongodb_oplog
## 11.5 Acceptance Criteria — Phần 11
☐ 5+ connector types in Phase 1
☐ Event normalization to common schema
☐ Privacy controls enforced
☐ Audit logging
☐ Vietnam-specific connectors (Zalo, Misa, Fast)

# Phần 12. Sequence Reconstruction Algorithm
## 12.1 The Problem
Given thousands of events từ multiple sources, group them theo case_id và reconstruct workflow.
Challenge: case_id không luôn explicit. Cần infer.
## 12.2 Case ID Inference
class CaseIDInference:
    """Infer which events belong to same business case."""
    
    def infer_cases(self, events):
        cases = []
        
        # Strategy 1: Explicit case_id (when available)
        explicit = [e for e in events if e.case_id_hint]
        cases.extend(group_by(explicit, 'case_id_hint'))
        
        # Strategy 2: Foreign key tracing
        # E.g., lead_id appears in DB event AND email subject AND Zalo message
        for entity_id in extract_potential_ids(events):
            related = find_events_referencing(entity_id, events)
            if len(related) > 1:
                cases.append(Case(id=entity_id, events=related))
        
        # Strategy 3: Temporal clustering
        # Events close in time + same actor + same channel = likely same case
        clusters = temporal_cluster(events, window_minutes=60, by_actor=True)
        cases.extend(clusters)
        
        # Strategy 4: ML-based correlation
        # Train model: given 2 events, are they same case?
        if config.use_ml_correlation:
            cases = refine_with_ml(cases, model='case_correlation_v1')
        
        return cases
## 12.3 Sequence Mining Algorithms
algorithms:
  
  alpha_miner:
    description: "Classic algorithm, simple"
    pros: "Mathematically proven, works for clean data"
    cons: "Fails on noise, doesn't handle parallelism well"
    use_for: "Initial baseline, well-structured logs"
  
  heuristic_miner:
    description: "Frequency-based, noise-tolerant"
    pros: "Handles real-world messiness"
    cons: "Less rigorous than alpha"
    use_for: "Default for SME data"
  
  inductive_miner:
    description: "Hierarchical, produces sound model"
    pros: "Always produces valid model"
    cons: "Computationally expensive"
    use_for: "Complex workflows, high quality output"
  
  fuzzy_miner:
    description: "Visualization-friendly"
    pros: "Good for understanding spaghetti processes"
    cons: "Less for execution, more for analysis"
    use_for: "Initial exploration with users"
## 12.4 Implementation Approach
class SequenceMiner:
    
    def mine(self, events, algorithm='heuristic_miner'):
        # Step 1: Group into cases
        cases = self.case_inferer.infer_cases(events)
        
        # Step 2: For each case, extract activity sequence
        sequences = [self.extract_sequence(case) for case in cases]
        
        # Step 3: Mine pattern
        if algorithm == 'heuristic_miner':
            process_model = self.heuristic_miner(sequences)
        elif algorithm == 'inductive_miner':
            process_model = self.inductive_miner(sequences)
        # ...
        
        # Step 4: Compute statistics
        stats = self.compute_stats(sequences, process_model)
        
        # Step 5: Identify variants (top 5)
        variants = self.identify_variants(sequences, top_n=5)
        
        return ProcessMiningResult(
            model=process_model,
            stats=stats,
            variants=variants,
            cases_analyzed=len(cases),
            confidence=self.compute_confidence(stats)
        )
## 12.5 Output Example
mined_process_example:
  
  process_name: "Sales Lead → Close" (auto-detected)
  total_cases: 247
  date_range: 2025-11-01 to 2026-04-30
  
  main_variant: # 67% of cases follow this
    sequence:
      1. Lead created (CRM event)
      2. Sales notification (system delay avg 2.3h)
      3. Sales calls customer (phone log)
      4. Email follow-up (email metadata)
      5. Quote in Excel (file event)
      6. Quote sent via Zalo (Zalo event)  ⚠️ off-system
      7. Manager approval (DB status change)
      8. Close in CRM (status update)
    avg_duration: 4.2 days
    success_rate: 78%
  
  variant_2: # 18% of cases
    sequence:
      [Same steps 1-7]
      8. Approval skipped — direct close (DB anomaly)
    note: "BYPASS DETECTED — known customers"
    avg_duration: 2.1 days
    success_rate: 89%
  
  variant_3: # 9% of cases
    sequence:
      [Same start]
      4. Multiple email exchanges (5+ emails)
      5. Quote rebuild 2-3 times
      ...
    note: "REWORK LOOP — complex deals"
    avg_duration: 12.7 days
    success_rate: 41%
  
  bottlenecks:
    - "Sales notification delay: avg 2.3h, p95 8.4h"
    - "Quote rebuild: 9% of cases need 2+ iterations"
    - "Manager approval: avg 1.4 days waiting"
  
  off_system_steps:
    - "Zalo communications: 73% of quotes sent via Zalo"
    - "Excel quote: 100% (no CRM-native quote)"
    - "Phone calls: not tracked in any system"
  
  shadow_processes:
    - "Direct close without approval: 18% of cases"
    - "Side-channel approvals via Zalo to manager: detected"
## 12.6 Acceptance Criteria — Phần 12
☐ Case ID inference works for unlabeled events
☐ At least 2 mining algorithms (heuristic + inductive)
☐ Top variants identified
☐ Bottlenecks quantified
☐ Off-system steps flagged

# Phần 13. Hidden Workflow & Shadow Process Detection
## 13.1 What to Detect
detection_targets:
  
  hidden_workflow_steps:
    description: "Steps that happen but aren't in claimed process"
    examples:
      - "Approval really happens via Zalo, not CRM"
      - "Data reconciled in Excel before entering ERP"
      - "Customer called for clarification (untracked)"
  
  shadow_processes:
    description: "Parallel unofficial workflows"
    examples:
      - "Sales team has private Excel tracking parallel to CRM"
      - "Manager runs separate weekly review unrelated to system"
  
  approval_bypasses:
    description: "Cases where approval skipped"
    examples:
      - "VIP customers: 80% bypass approval"
      - "Junior staff approving on behalf of senior"
  
  rework_loops:
    description: "Steps repeated due to errors/changes"
    examples:
      - "Quote revised 3+ times average"
      - "Approval rejected, re-submitted"
  
  abandoned_paths:
    description: "Cases that started but didn't complete"
    examples:
      - "23% of leads stuck at qualification stage > 30 days"
      - "12% of quotes never followed up"
  
  out_of_hours_activity:
    description: "Work happening outside business hours"
    examples:
      - "Manager approves via Zalo Sundays evening"
      - "Sales sends quotes 11pm regularly"
## 13.2 Detection Heuristics
class ShadowProcessDetector:
    
    def detect_off_system_steps(self, mined_process, events):
        """Find steps that happen in chat/email but not in 'system'."""
        
        findings = []
        
        # For each pair of consecutive in-system events
        for case in mined_process.cases:
            for i, event in enumerate(case.events[:-1]):
                next_event = case.events[i+1]
                gap_minutes = (next_event.timestamp - event.timestamp).total_seconds() / 60
                
                # If gap > 30 min, check chat/email for activity
                if gap_minutes > 30:
                    in_gap = find_chat_email_events(
                        case_id=case.id,
                        from_time=event.timestamp,
                        to_time=next_event.timestamp
                    )
                    
                    if in_gap:
                        findings.append({
                            'case_id': case.id,
                            'between_steps': (event.activity, next_event.activity),
                            'off_system_events': in_gap,
                            'gap_filled_off_system': True
                        })
        
        return findings
    
    def detect_approval_bypasses(self, mined_process):
        """Find cases that skipped expected approval step."""
        
        expected_approval = mined_process.main_variant.has_step('approval')
        if not expected_approval:
            return []
        
        bypasses = []
        for case in mined_process.cases:
            if not case.has_activity('approval'):
                bypasses.append({
                    'case_id': case.id,
                    'expected': 'approval',
                    'actual': 'direct_close',
                    'closed_by': case.last_actor,
                    'risk_level': self.assess_bypass_risk(case)
                })
        
        return bypasses
    
    def detect_shadow_processes(self, all_events):
        """Find parallel workflows not in claimed process."""
        
        # Cluster events by activity + actor patterns
        clusters = self.activity_clustering(all_events)
        
        # Identify clusters NOT mapped to any claimed workflow
        shadow_candidates = []
        for cluster in clusters:
            if not is_mapped_to_known_workflow(cluster):
                if cluster.frequency > THRESHOLD:
                    shadow_candidates.append({
                        'description': cluster.activity_summary,
                        'frequency': cluster.frequency,
                        'actors': cluster.actors,
                        'evidence': cluster.sample_events
                    })
        
        return shadow_candidates
## 13.3 Risk Scoring
def assess_bypass_risk(case):
    """How risky is this approval bypass?"""
    risk_score = 0
    
    if case.value > 100_000_000:  # > 100M VND
        risk_score += 40
    if case.actor_seniority < 'manager':
        risk_score += 30
    if case.customer_new:
        risk_score += 20
    if case.outside_business_hours:
        risk_score += 10
    
    if risk_score >= 60: return 'HIGH'
    elif risk_score >= 30: return 'MEDIUM'
    else: return 'LOW'
## 13.4 Surface Findings to User
findings_report_for_user:
  
  ─── DISCOVERED OFF-SYSTEM STEPS ───
  
  Finding #1: Quote sent via Zalo (73% of cases)
    Evidence: 247 cases analyzed, 180 have Zalo message between 
              "quote_created" and "approval" steps
    Impact: Customer communication not searchable, no audit trail
    Recommendation: 
      - Option A: Integrate Zalo into workflow (Zalo node)
      - Option B: Build CRM email/SMS native
      - Option C: Accept off-system but log Zalo links to CRM
    
  Finding #2: Manager approval via Zalo private chat
    Evidence: 32 of 45 manager approvals correlated with private Zalo
    Impact: Approval not recorded in system, audit issue
    Recommendation:
      - Add Zalo-integrated approval node
      - OR enforce in-system approval (cultural change)
  
  ─── DISCOVERED BYPASSES ───
  
  Finding #3: 18% of cases close without approval
    Evidence: 45 of 247 cases skip approval step
    Risk breakdown:
      - 22 cases: VIP customers (acceptable per policy)
      - 18 cases: Below approval threshold (acceptable)
      - 5 cases: HIGH RISK — value exceeds threshold, no approval
    Recommendation:
      - Auto-approve for documented exceptions
      - Block bypasses for high-value cases
      - Surface to manager dashboard
  
  ─── SHADOW PROCESSES ───
  
  Finding #4: Sales team maintains parallel Excel tracker
    Evidence: 15 sales reps have private Excel files updated daily
    Impact: Duplicate work, data inconsistency, no central insight
    Recommendation:
      - Investigate why CRM doesn't meet their needs
      - Add missing CRM features
      - Phase out Excel tracker once CRM adequate
  
  ─── RECOMMENDATIONS FOR DISCOVERED WORKFLOW v0 ───
  
  Based on all findings, system proposes initial workflow:
    [Visual workflow diagram with off-system steps marked]
  
  User decisions needed:
    1. Include Zalo communication in workflow? (Y/N)
    2. Block or allow approval bypasses for VIPs?
    3. Migrate Excel data into CRM?
    4. ... etc
## 13.5 Acceptance Criteria — Phần 13
☐ 6 detection categories implemented
☐ Risk scoring for bypasses
☐ Findings actionable (user can decide)
☐ Surface to user with evidence
☐ Track which findings user addresses

# Phần 14. Bottleneck & Bypass Mining
## 14.1 Bottleneck Detection
class BottleneckMiner:
    
    def find_bottlenecks(self, mined_process):
        bottlenecks = []
        
        for activity in mined_process.activities:
            # Time analysis
            wait_times_before = [
                (case.events[i].timestamp - case.events[i-1].timestamp).total_seconds()
                for case in mined_process.cases
                for i, e in enumerate(case.events)
                if e.activity == activity and i > 0
            ]
            
            if wait_times_before:
                avg_wait = mean(wait_times_before)
                p95_wait = percentile(wait_times_before, 95)
                
                # Compare to total cycle time
                wait_share = avg_wait / mined_process.avg_total_cycle_time
                
                if wait_share > 0.20:  # this activity takes 20%+ of cycle time
                    bottlenecks.append({
                        'activity': activity,
                        'type': 'long_waiting_time',
                        'avg_wait_seconds': avg_wait,
                        'p95_wait_seconds': p95_wait,
                        'percent_of_cycle': wait_share,
                        'impact': self.estimate_impact(activity, mined_process)
                    })
        
        return bottlenecks
## 14.2 Rework Loop Detection
def find_rework_loops(mined_process):
    """Find cases where same activity repeats."""
    rework_findings = []
    
    for case in mined_process.cases:
        activity_counts = Counter(e.activity for e in case.events)
        
        for activity, count in activity_counts.items():
            if count > 1 and activity not in EXPECTED_REPEATING_ACTIVITIES:
                rework_findings.append({
                    'case_id': case.id,
                    'activity': activity,
                    'occurrences': count,
                    'time_lost': calculate_rework_time(case, activity)
                })
    
    # Aggregate
    by_activity = defaultdict(list)
    for f in rework_findings:
        by_activity[f['activity']].append(f)
    
    return [
        {
            'activity': activity,
            'rework_rate': len(findings) / len(mined_process.cases),
            'avg_rework_count': mean([f['occurrences'] for f in findings]),
            'time_lost_hours': sum([f['time_lost'] for f in findings]) / 3600,
            'sample_cases': [f['case_id'] for f in findings[:5]]
        }
        for activity, findings in by_activity.items()
    ]
## 14.3 Conformance Analysis
def conformance_analysis(claimed_process_yaml, mined_process):
    """Compare what user claims vs what we mined."""
    
    claimed_activities = extract_activities(claimed_process_yaml)
    mined_activities = mined_process.activities
    
    return {
        'claimed_but_not_mined': claimed_activities - mined_activities,
        # → Steps user thinks happen but logs don't show
        # → Either: not implemented, OR off-system
        
        'mined_but_not_claimed': mined_activities - claimed_activities,
        # → Steps that actually happen but user didn't mention
        # → Likely off-system steps OR shadow processes
        
        'sequence_conformance': sequence_alignment_score(claimed_process_yaml, mined_process),
        # → How closely the actual order matches claimed order
        
        'frequency_conformance': frequency_alignment(claimed_process_yaml, mined_process)
        # → How frequent each activity vs expected
    }
## 14.4 Acceptance Criteria — Phần 14
☐ Bottleneck detection with cycle time analysis
☐ Rework loop detection
☐ Conformance analysis (claimed vs actual)
☐ Time-loss quantification
☐ Sample case references for evidence

# Phần 15. Discovery → Builder Translation
## 15.1 Auto-Generate Workflow YAML from Discovery
class DiscoveryToBuilder:
    
    def generate_workflow_yaml(self, mined_process, conformance_findings):
        """Convert mined process to drag-drop builder format."""
        
        nodes = []
        edges = []
        
        # For each activity in main variant
        for i, activity in enumerate(mined_process.main_variant.activities):
            node_type = self.infer_node_type(activity, mined_process)
            
            node = {
                'id': f'n_{i}',
                'type': node_type,
                'name': activity.name,
                'config': self.infer_config(activity, mined_process),
                'discovered_metadata': {
                    'frequency': activity.frequency,
                    'avg_duration_seconds': activity.avg_duration,
                    'is_off_system': activity.is_off_system,
                    'is_bottleneck': activity in mined_process.bottlenecks,
                    'evidence_case_count': activity.case_count
                }
            }
            
            # Mark off-system steps for user decision
            if activity.is_off_system:
                node['discovery_flags'] = {
                    'off_system': True,
                    'recommendation': 'Review and decide: integrate or accept off-system'
                }
            
            # Mark bottlenecks
            if activity in mined_process.bottlenecks:
                node['discovery_flags'] = {
                    **node.get('discovery_flags', {}),
                    'bottleneck': True,
                    'optimization_suggestion': activity.bottleneck_suggestion
                }
            
            nodes.append(node)
        
        # Generate edges from sequence
        for i in range(len(nodes) - 1):
            edges.append({'from': f'n_{i}', 'to': f'n_{i+1}'})
        
        return WorkflowYAML(
            metadata={
                'name': f'discovered_{mined_process.process_name}',
                'source': 'process_mining_discovered',
                'mining_session_id': mined_process.session_id,
                'fidelity_to_discovered': 1.0  # 100% match initially
            },
            spec={
                'nodes': nodes,
                'edges': edges,
                'discovery_findings': conformance_findings,
                'state': 'DRAFT'  # User reviews before activating
            }
        )
    
    def infer_node_type(self, activity, mined_process):
        """Map mined activity to a node type from catalog."""
        
        # Heuristics based on activity characteristics
        if activity.is_off_system:
            if 'zalo' in activity.source:
                return 'action.send_chat_message'  # Zalo-integrated
            elif 'email' in activity.source:
                return 'action.send_email'
            elif 'phone' in activity.source:
                return 'action.log_phone_call'  # external integration
        
        elif activity.activity_type == 'data_read':
            return 'data_input.read_table'
        elif activity.activity_type == 'data_write':
            return 'output.save_to_database'
        elif activity.activity_type == 'approval':
            return 'decision.approval_gate'
        elif activity.activity_type == 'notification':
            return 'action.send_email'
        # ... etc
        
        return 'processing.transform'  # generic fallback
## 15.2 User Review UI
┌─────────────────────────────────────────────────────────────┐
│ Discovered Workflow: Sales Lead → Close                     │
│                                                             │
│ Based on analysis of 247 cases over 6 months                │
│ Confidence: HIGH (consistent pattern in 67% of cases)       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  [Visual workflow with discovered steps]                    │
│                                                             │
│  Step 1: Lead Created                                       │
│  Step 2: Sales Notified ⚠️ BOTTLENECK (avg 2.3h delay)     │
│  Step 3: Phone Call ⚠️ OFF-SYSTEM                           │
│  Step 4: Email Follow-up ⚠️ OFF-SYSTEM                      │
│  Step 5: Quote in Excel ⚠️ OFF-SYSTEM                       │
│  Step 6: Quote via Zalo ⚠️ OFF-SYSTEM                       │
│  Step 7: Manager Approval (sometimes via Zalo)              │
│  Step 8: Close in CRM                                       │
│                                                             │
│ ─── DECISIONS NEEDED ───                                    │
│                                                             │
│ ⚠️ 4 off-system steps detected. For each, choose:           │
│                                                             │
│ Step 3 (Phone Call):                                        │
│   ○ Integrate phone log into workflow                       │
│   ● Accept as off-system (mark for tracking)                │
│   ○ Replace with in-system action                           │
│                                                             │
│ Step 4 (Email Follow-up):                                   │
│   ● Integrate via Gmail API node                            │
│   ○ Accept as off-system                                    │
│   ○ Replace with template-based system email                │
│                                                             │
│ ... [more decisions for each off-system step]              │
│                                                             │
│ ─── BOTTLENECK ALERT ───                                    │
│                                                             │
│ Step 2 takes 2.3h on average — recommend:                   │
│   ☑ Add real-time notification (auto-fix suggested)         │
│                                                             │
│ ─── BYPASS ALERT ───                                        │
│                                                             │
│ 18% of cases skip Step 7 (Approval).                        │
│ Top bypass reasons: VIP customers, low-value deals.         │
│                                                             │
│ Action:                                                     │
│   ● Add auto-approve rule for VIP + low-value               │
│   ○ Block all bypasses                                      │
│   ○ Accept current behavior                                 │
│                                                             │
│ [Review in Builder] [Accept All] [Customize]               │
└─────────────────────────────────────────────────────────────┘
## 15.3 Iteration Path
discovery_workflow_iteration:
  
  step_1: Discovery generates baseline_v0
  step_2: User reviews, makes decisions on off-system steps
  step_3: User accepts → workflow goes to REVIEWING state
  step_4: After review → ACTIVE_BASELINE
  step_5: 60-day monitoring
  step_6: New mining session at day 60 (with fresh data + new workflow)
  step_7: Detect changes since v0 (did people start using system?)
  step_8: Loop
## 15.4 Acceptance Criteria — Phần 15
☐ Mined process auto-generates valid workflow YAML
☐ Off-system steps highlighted for user decision
☐ Bottleneck/bypass auto-suggestions
☐ User review UI clear + actionable
☐ Iteration loop with re-mining at day 60

# PART V — DRAG-DROP WORKFLOW BUILDER (UX)
# Phần 16. Builder UX Architecture
## 16.1 UX Layout
┌─────────────────────────────────────────────────────────────────┐
│ Header: Workflow Name | Save | Validate | Test Run | Deploy    │
├──────────────┬──────────────────────────────────────────────────┤
│              │                                                  │
│  COMPONENT   │           CANVAS (drag-drop area)               │
│  PALETTE     │                                                  │
│              │                                                  │
│ Categories:  │              [Visual workflow]                   │
│ □ Data Input │              ┌─────┐                             │
│ □ Processing │              │  N1 │                             │
│ □ Decision   │              └──┬──┘                             │
│ □ AI         │                 │                                │
│ □ Action     │              ┌──┴──┐                             │
│ □ Output     │              │  N2 │                             │
│              │              └──┬──┘                             │
│ Search:      │           ┌─────┴─────┐                          │
│ [search box] │       ┌───┴────┐ ┌────┴────┐                    │
│              │       │   N3   │ │   N4    │                    │
│ Templates:   │       └────────┘ └─────────┘                    │
│ - Marketing  │                                                  │
│ - Sales      │                                                  │
│ - Ops        │                                                  │
│              │                                                  │
├──────────────┼──────────────────────────────────────────────────┤
│              │  PROPERTIES (selected node)                      │
│              │                                                  │
│ MINIMAP      │  Node Type: AI - Generate Insight                │
│              │  Config:                                         │
│              │    Insight Type: [Anomaly ▼]                    │
│              │    Focus Metric: [revenue]                       │
│              │    LLM Version: claude-sonnet-4.0 (pinned)       │
│              │  Cost: ~50 VND/execution                         │
│              │  ⚠️ Pricing tier: BASIC required                 │
└──────────────┴──────────────────────────────────────────────────┘
## 16.2 Interaction Patterns
ux_interactions:
  
  drag_node_from_palette:
    - User clicks + drags from palette
    - Drop on canvas creates new node
    - Properties panel auto-opens
  
  connect_nodes:
    - Hover over source → output port glows
    - Drag from port → connector
    - Drop on target's input port
    - Auto-validates type compatibility
    - Invalid → red flash + tooltip
  
  edit_node_config:
    - Click node → Properties panel
    - Form-based config (no JSON for non-power-users)
    - Power user mode: raw YAML edit option
  
  edit_edge:
    - Click edge → properties
    - Add condition: "execute only if X"
    - Add data mapping: "rename field A to B"
  
  zoom_pan_minimap:
    - Mouse wheel zoom
    - Right-click drag pan
    - Minimap for large workflows
  
  group_nodes:
    - Select multiple → group as sub-workflow
    - Reuse groups across workflows
  
  undo_redo:
    - Cmd+Z / Cmd+Shift+Z, 50-step history
## 16.3 Performance Requirements
performance_requirements:
  canvas_render: 60fps for ≤100 nodes
  node_drag_latency: < 16ms
  config_panel_load: < 200ms
  validation_time: < 500ms
  test_run_kickoff: < 1s
  auto_save: every 30s
  explicit_save: < 500ms

# Phần 17. Component Library & Templates
## 17.1 Templates per Department (Phase 1)
template_library_phase_1:
  
  marketing (5 templates):
    - "Email Campaign with Segmentation"
    - "Customer Onboarding Sequence"
    - "Newsletter with AI Personalization"
    - "Abandoned Cart Recovery"
    - "Re-engagement Campaign"
  
  sales (5 templates):
    - "Lead Qualification Workflow"
    - "Pipeline Stage Automation"
    - "Quote-to-Cash"
    - "Customer Renewal Reminder"
    - "Deal Risk Assessment"
  
  operations (5 templates):
    - "Inventory Reorder Trigger"
    - "Stock-out Risk Alert"
    - "Daily Operations Dashboard"
    - "Supplier Performance Monitoring"
    - "Quality Issue Resolution"
  
  finance (5 templates):
    - "Invoice Processing"
    - "Expense Approval Workflow"
    - "AR Collection Reminder"
    - "Cash Flow Forecasting"
    - "Budget vs Actual Reporting"
Phase 2 expansion: HR + Customer Service templates.
## 17.2 Template Anatomy
template:
  template_id: UUID
  display_name: string
  display_name_vi: string
  description: text
  
  category: department
  use_case: text
  applicable_industries: list
  applicable_archetypes: list
  
  estimated_setup_time_minutes: integer
  estimated_monthly_cost_vnd: numeric
  pricing_tier_required: string
  
  workflow_definition: object
  required_data_sources: list
  required_integrations: list
  
  expected_outcomes:
    - kpi_affected: string
    - expected_improvement: string
    - confidence: 'low' | 'medium' | 'high'
  
  customization_points:
    - field_name: string
      description: string
      default: any
      type: string

# Phần 18. Validation & Error Handling
## 18.1 Validation Layers (4)
class WorkflowValidator:
    
    def validate_full(self, workflow):
        results = []
        results += self.validate_structural(workflow)
        results += self.validate_semantic(workflow)
        results += self.validate_business_rules(workflow)
        results += self.validate_pricing_tier(workflow)
        results += self.validate_permissions(workflow)
        results += self.simulate_runtime(workflow)
        # v2.0
        results += self.validate_reliability_config(workflow)
        results += self.validate_secrets_references(workflow)
        results += self.validate_economics_estimates(workflow)
        return results
    
    def validate_structural(self, workflow):
        errors = []
        # No orphan nodes (unless trigger/terminal)
        # No cycles (unless explicit loop)
        # All required ports connected
        # Type compatibility on edges
        # ...
        return errors
    
    def validate_reliability_config(self, workflow):
        """v2.0 — ensure reliability settings sensible."""
        errors = []
        for node in workflow.nodes:
            if node.side_effect_class == 'external_irreversible':
                if not node.reliability.idempotency_key_extractor:
                    errors.append(f"Node {node.id}: external_irreversible nodes must have idempotency_key")
                if node.reliability.max_retries > 1 and not node.reliability.compensating_action:
                    errors.append(f"Node {node.id}: retries without compensating_action risky for irreversible")
        return errors
    
    def validate_secrets_references(self, workflow):
        """v2.0 — no inline secrets."""
        errors = []
        for node in workflow.nodes:
            if has_inline_secrets(node.config):
                errors.append(f"Node {node.id}: contains inline secret. Use vault reference.")
        return errors
## 18.2 Error Display & Auto-Fix
┌─────────────────────────────────────────────────────┐
│ Workflow Issues Found (3)                           │
├─────────────────────────────────────────────────────┤
│                                                     │
│ ❌ ERRORS (must fix before deploy):                 │
│                                                     │
│ 1. Node 'fetch_customers' has no outgoing edge      │
│    → [Highlight node]                               │
│                                                     │
│ 2. Node 'send_email' is external_irreversible       │
│    but has no idempotency_key configured.           │
│    → [Auto-fix: use customer_id + campaign_id]      │
│                                                     │
│ ⚠️ WARNINGS (recommended):                          │
│                                                     │
│ 3. AI node 'generate_content' costs ~50 VND/exec    │
│    With expected 1000 executions/day → 50K VND/day  │
│    Consider caching or batching                     │
│    → [View cost analysis]                           │
│                                                     │
│ [Validate Again] [Auto-fix all] [Deploy]           │
└─────────────────────────────────────────────────────┘

# PART VI — INTEGRATION WITH DATA + AI
# Phần 19. Data Binding (Workflow Nodes ↔ Clean Data)
## 19.1 Data Source Types Supported
data_sources_for_workflow:
  
  silver_tier: # Cleaned, validated
    examples: ['silver.customers', 'silver.transactions']
    use_for: per-record processing
  
  gold_tier: # Aggregated, business-ready
    examples: ['gold.customer_360', 'gold.daily_revenue']
    use_for: dashboards, reports
  
  feature_store: # Pre-computed features for ML
    examples: ['features.churn_score', 'features.ltv_predicted']
    use_for: AI nodes
  
  external_api: # Configured external services
    examples: ['shopify_orders', 'salesforce_contacts']
    use_for: integration with SaaS
  
  uploaded_file: # User-uploaded in current run
    use_for: batch processing
  
  workflow_input: # Input passed to workflow at trigger
    use_for: parameterized workflows
## 19.2 Schema Awareness
def on_schema_change(table, change):
    affected_workflows = find_workflows_using(table)
    
    for workflow in affected_workflows:
        impact = assess_impact(workflow, change)
        
        if impact.severity == 'breaking':
            workflow.state = 'BROKEN'
            notify_owner(workflow, "Schema change broke workflow")
            block_executions(workflow)
        elif impact.severity == 'warning':
            notify_owner(workflow, "Schema change may affect outputs")
            log_warning_in_workflow(workflow)
## 19.3 Real-Time vs Batch
data_freshness_modes:
  real_time: < 1s, streaming, event triggers
  near_real_time: 5-15 min, scheduled frequent
  batch: hourly/daily, scheduled
  on_demand: workflow runtime

# Phần 20. AI Insight Injection (Reasoning Layer Integration)
## 20.1 AI Node Architecture
Workflow execution reaches AI node
       ▼
AI node prepares request:
  - Input data
  - Insight type required
  - Context (tenant, profile, criteria)
  - LLM version pinned (v2.0)
       ▼
Call Reasoning Layer API:
  POST /api/v1/insights/generate
  {
    tenant_id,
    insight_type,
    context: {profile, active_criteria, active_formulas},
    input_data,
    llm_version_pinned: "claude-sonnet-4.0"  # ⭐ v2.0
  }
       ▼
Reasoning Layer:
  - Uses pinned LLM version (no drift)
  - Selects formula variant per profile
  - Runs detection method
  - Validates with Constraint Engine
  - Returns structured insight + confidence
       ▼
AI node receives:
  {
    insight: {...},
    confidence: 0.78,
    explainability: {executive, analyst, auditor},
    citations: [...],
    llm_version_used: "claude-sonnet-4.0"
  }
       ▼
Workflow continues
## 20.2 AI Node Configuration
ai_node_config_example:
  
  node_id: "ai_001"
  type: "ai.call_insight_engine"
  
  config:
    insight_type: "anomaly_detection"
    focus_metric: "{{previous_node.output.metric_name}}"
    detection_methods: ["zscore", "iqr"]
    severity_threshold: "MEDIUM"
    
    # ⭐ v2.0 — pin LLM version
    llm_pinned_version: "claude-sonnet-4.0"
    fallback_versions: ["claude-sonnet-3.5"]  # if primary unavailable
    
    use_active_criteria: true
    use_active_formulas: true
    use_business_profile: true
    
    cost_cap_per_execution_vnd: 100
    timeout_seconds: 30
    
    on_low_confidence:
      action: 'pass_through_with_warning'
      threshold: 0.5
    
    on_constraint_violation:
      action: 'block_workflow'
      notify: ['workflow_owner']
## 20.3 Confidence-Aware Workflow Routing
confidence_branching_example:
  - ai.generate_insight
  - decision.if_else:
      condition: "confidence > 0.8"
      true_branch:
        - action.send_alert (auto)
      false_branch:
        - decision.approval_gate (human review)
        - action.send_alert (after approval)
## 20.4 Cost Management
class AINodeCostManager:
    
    def estimate_workflow_cost(workflow):
        ai_nodes = [n for n in workflow.nodes if n.category == 'ai']
        total = 0
        for node in ai_nodes:
            cost_per_call = node.type.estimated_cost_vnd
            calls_per_run = estimate_calls(node, workflow)
            runs_per_month = estimate_runs(workflow)
            total += cost_per_call * calls_per_run * runs_per_month
        
        return {
            'total_monthly_estimated_vnd': total,
            'warning_if_exceeds': tenant.plan.ai_cost_warning,
            'hard_cap': tenant.plan.ai_cost_hard_cap
        }
    
    def runtime_cost_tracking(execution):
        for step in execution.steps:
            if step.node.category == 'ai':
                if step.actual_cost > step.node.cost_cap:
                    halt_execution(execution, reason='cost_cap_exceeded')
        
        if tenant.monthly_ai_cost > tenant.plan.hard_cap:
            disable_ai_nodes_for_tenant(tenant.id, until_billing_reset=True)
            notify_admin(tenant.id, 'ai_budget_exhausted')

# Phần 21. LLM Version Drift Handling ⭐ NEW v2.0
Why this matters: When LLM model updates (Claude 3.5 → 4.0), output behavior changes. Production workflow output may shift unexpectedly. This is silent breakage if not managed.
## 21.1 The Problem
llm_drift_scenarios:
  
  scenario_a_subtle_format_change:
    description: "Model upgrade changes output format slightly"
    example: "v3.5 returns 'Customer X is at risk'; v4.0 returns 'Risk identified for Customer X'"
    impact: "Downstream regex/parsing breaks silently"
    
  scenario_b_quality_degradation:
    description: "Newer model less verbose, missing some details"
    example: "v3.5 narrative 200 words; v4.0 narrative 80 words, missing causation analysis"
    impact: "Reports look different to manager, complaints"
  
  scenario_c_content_shift:
    description: "Model interpretation evolves"
    example: "Same input → different recommendation classification"
    impact: "Inconsistent behavior over time, hard to trust"
  
  scenario_d_cost_change:
    description: "Newer model more expensive per token"
    example: "Auto-upgrade increases monthly bill 40%"
    impact: "Budget overrun"
  
  scenario_e_deprecation:
    description: "Old model deprecated by provider"
    example: "Anthropic deprecates Claude 3.0 with 90-day notice"
    impact: "Forced migration"
## 21.2 Version Pinning Strategy
llm_version_pinning:
  
  default: pinned_to_specific_version
  # Every AI node MUST specify llm_version
  
  workflow_lock:
    - When workflow goes ACTIVE_BASELINE → version locked
    - Cannot auto-upgrade without going through TESTING
    - Forces drift evaluation before promotion
  
  pinned_version_metadata:
    llm_pinned_version: "claude-sonnet-4.0"
    pinned_at: timestamp
    pinned_by: user_id
    fallback_versions: ["claude-sonnet-3.5"]
    deprecation_alert_days: 30  # warn 30d before EOL
## 21.3 Drift Detection
class LLMDriftDetector:
    """Continuously monitor for output drift even with pinned version."""
    
    def monitor_output_consistency(self, workflow_id, ai_node_id):
        """Compare current outputs to historical baseline."""
        
        recent_outputs = get_recent_ai_outputs(ai_node_id, days=7)
        baseline_outputs = get_baseline_outputs(ai_node_id, period='first_30_days')
        
        # Compare structural format
        format_drift = compare_output_formats(recent_outputs, baseline_outputs)
        
        # Compare content distribution (length, sentiment, etc.)
        content_drift = compare_content_distributions(recent_outputs, baseline_outputs)
        
        # Compare confidence distribution
        confidence_drift = compare_confidence_distributions(recent_outputs, baseline_outputs)
        
        if any([format_drift > 0.20, content_drift > 0.15, confidence_drift > 0.20]):
            alert_drift(workflow_id, ai_node_id, {
                'format_drift': format_drift,
                'content_drift': content_drift,
                'confidence_drift': confidence_drift,
                'sample_old': baseline_outputs[:3],
                'sample_new': recent_outputs[:3]
            })
## 21.4 Upgrade Process (Controlled)
llm_upgrade_workflow:
  
  trigger: "New LLM version available OR pinned version deprecation announced"
  
  step_1_eval_in_test_environment:
    - Spin up shadow workflow with new LLM version
    - Run on production traffic (read-only)
    - Compare outputs vs current pinned version
    - Generate drift report
  
  step_2_human_review:
    - User reviews drift report
    - Decides: accept new, reject, or investigate
  
  step_3_test_phase:
    - If accepted, create new workflow version with new LLM
    - Goes through 90-day TESTING phase like any other change
    - A/B compared to current pinned baseline
  
  step_4_promotion:
    - Only after 90-day testing approval → promote to baseline
    - Old LLM-pinned version archived
  
  emergency_path:
    - If pinned version EOL'd by provider before test complete
    - Use fallback_versions until test done
    - Communicate impact to user transparently
## 21.5 Acceptance Criteria — Phần 21
☐ All AI nodes have llm_pinned_version
☐ Drift detection running daily
☐ Upgrade goes through formal process (not auto)
☐ Fallback versions handle EOL gracefully
☐ User notified of all LLM-related changes

# Phần 22. Output Binding
## 22.1 Output Targets
output_targets:
  
  database:
    - silver.X tables
    - gold.X tables
    - custom_workflow_output tables
  
  reasoning_layer:
    - publish_insight → Insight catalog
    - publish_alert → Alert system
    - publish_recommendation → Recommendation engine
  
  reports:
    - update_report_data
    - generate_report
    - distribute_report
  
  notifications:
    - email, slack, teams, zalo, sms, in-app, webhook
  
  downstream_workflows:
    - trigger_workflow (with idempotency)
    - pass data
  
  external:
    - call_api
    - update_crm (Salesforce/HubSpot)
    - update_pm (Jira/Asana)
## 22.2 Output Binding Configuration
output_binding_example:
  
  node: "publish_insight"
  config:
    insight_category: "operational"
    severity: "{{previous_node.output.severity}}"
    
    insight_template:
      title: "{{workflow_name}} detected {{anomaly_type}}"
      description: "{{generate_narrative_node.output}}"
      data_sources_cited: "{{workflow.execution.data_sources}}"
      confidence: "{{ai_node.output.confidence}}"
    
    audience:
      - role: "department_manager"
      - role: "head_of_{{department}}"
    
    visibility:
      - dashboard_tile: "operational_alerts"
      - daily_digest: true
      - immediate_notification: severity == 'CRITICAL'

# PART VII — IMPACT ANALYSIS & CHANGE MANAGEMENT
# Phần 23. Workflow Change Impact Analysis (4 dimensions)
## 23.1 4 Dimensions
IMPACT ANALYSIS = {
    1. STRUCTURAL CHANGES (what changed in workflow)
    2. DATA IMPACT (which sources/outputs affected)
    3. DOWNSTREAM IMPACT (what depends on this)
    4. PERFORMANCE IMPACT (better/worse expected)
}
## 23.2 Structural Change Detection
def diff_workflow_versions(v_old, v_new):
    return {
        'nodes_added': [n for n in v_new.nodes if n.id not in v_old.node_ids],
        'nodes_removed': [n for n in v_old.nodes if n.id not in v_new.node_ids],
        'nodes_modified': [
            {'id': n.id, 'changes': diff_node_config(v_old.get(n.id), n)}
            for n in v_new.nodes 
            if n.id in v_old.node_ids and node_config_differs(v_old.get(n.id), n)
        ],
        'edges_added': diff_edges(v_old.edges, v_new.edges).added,
        'edges_removed': diff_edges(v_old.edges, v_new.edges).removed,
        'edges_modified': diff_edges(v_old.edges, v_new.edges).modified,
        'config_changes': diff_workflow_config(v_old, v_new),
        # v2.0
        'reliability_changes': diff_reliability(v_old, v_new),
        'economics_changes': diff_economics(v_old, v_new)
    }
## 23.3 Data Impact Analysis
def analyze_data_impact(v_old, v_new):
    return {
        'data_sources': {
            'added': new_data_sources(v_new) - new_data_sources(v_old),
            'removed': new_data_sources(v_old) - new_data_sources(v_new),
            'modified': filter_changes_with_same_table(v_old, v_new)
        },
        'data_outputs': {
            'added': output_targets(v_new) - output_targets(v_old),
            'removed': output_targets(v_old) - output_targets(v_new),
            'schema_changes': detect_output_schema_diff(v_old, v_new)
        },
        'data_volume_estimate': {
            'old_records_per_run': estimate_volume(v_old),
            'new_records_per_run': estimate_volume(v_new),
            'change_pct': pct_change(v_old, v_new)
        },
        'data_quality_impact': {
            'validation_added': new_validations(v_new) - new_validations(v_old),
            'validation_removed': new_validations(v_old) - new_validations(v_new)
        }
    }
## 23.4 Downstream Impact Discovery
def find_downstream_impacts(workflow_id, change_diff):
    impacts = {
        'workflows_dependent': [],
        'reports_dependent': [],
        'alerts_dependent': [],
        'dashboards_dependent': [],
        'external_systems': []
    }
    
    output_tables = get_output_tables(workflow_id)
    for table in output_tables:
        impacts['workflows_dependent'].extend(find_workflows_reading(table))
    
    impacts['reports_dependent'] = find_reports_using_workflow(workflow_id)
    impacts['alerts_dependent'] = find_alerts_triggered_by(workflow_id)
    impacts['dashboards_dependent'] = find_dashboards_using(workflow_id)
    impacts['external_systems'] = find_external_targets(workflow_id)
    
    for category, items in impacts.items():
        for item in items:
            item.impact_severity = assess_severity(item, change_diff)
    
    return impacts
## 23.5 Performance Prediction
def predict_performance_impact(v_old, v_new):
    """Better or worse? Heuristic + historical."""
    
    node_count_change = len(v_new.nodes) - len(v_old.nodes)
    ai_nodes_old = count_ai_nodes(v_old)
    ai_nodes_new = count_ai_nodes(v_new)
    cost_estimate_change = (ai_nodes_new - ai_nodes_old) * AVG_AI_NODE_COST
    
    new_caching = detect_new_caching(v_old, v_new)
    new_parallelization = detect_new_parallelization(v_old, v_new)
    
    similar_past_changes = find_similar_changes_in_history(v_old, v_new)
    historical_avg_impact = compute_avg_impact(similar_past_changes)
    
    return {
        'expected_runtime_change_pct': estimate_runtime_change(...),
        'expected_cost_change_pct': cost_estimate_change / current_cost,
        'expected_success_rate_change_pp': estimate_success_change(...),
        'confidence': 'low' | 'medium' | 'high',
        'overall_direction': 'better' | 'worse' | 'mixed' | 'uncertain',
        'reasoning': generate_explanation(...)
    }
## 23.6 Impact Report UI
┌─────────────────────────────────────────────────────────────┐
│ Workflow Change Impact Analysis                             │
│ Marketing Email Campaign — v1 → v2                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│ ─── STRUCTURAL CHANGES ───                                  │
│ + 2 nodes added (validation, cache)                         │
│ ~ 1 node modified (personalization with fallback)          │
│ ~ 1 edge condition refined                                  │
│                                                             │
│ ─── DATA IMPACT ───                                         │
│ Data Sources: ✓ unchanged                                   │
│ Data Outputs: + new validation_log table                    │
│                                                             │
│ ─── DOWNSTREAM IMPACT ───                                   │
│ Workflows: 2 (low impact)                                   │
│ Reports: 4 (3 auto-adapt, 1 needs manual update)           │
│ Alerts: 1 (low impact)                                      │
│                                                             │
│ ─── PERFORMANCE IMPACT (PREDICTED) ───                      │
│ ✅ Runtime: 4m 23s → 3m 10s (-28%)                         │
│ ✅ Success rate: 87% → 94% (+7pp)                           │
│ ✅ Cost per run: 3,367 → 2,892 VND (-14%)                  │
│ ✅ Email bounce rate: 4.2% → 2.1% (-50%)                    │
│                                                             │
│ Confidence: MEDIUM (based on 23 similar past changes)       │
│ Overall direction: ✅ BETTER (high confidence)              │
│                                                             │
│ ─── ECONOMICS IMPACT (v2.0) ───                             │
│ Predicted NOV change: +3.5M VND/month                       │
│ Annual: +42M VND                                            │
│ Time to payback: 18 months                                  │
│                                                             │
│ ─── ADOPTION IMPACT (v2.0) ───                              │
│ Predicted adoption score: 72 → 85 (+13)                     │
│ Reason: removing burdensome approval gate                   │
│                                                             │
│ [Approve for Testing] [Modify Workflow] [Reject]           │
└─────────────────────────────────────────────────────────────┘

# Phần 24. Data Dependencies Tracking
## 24.1 Dependency Graph
                  [Workflow X]
                       │
              ┌────────┼────────┐
              ▼        ▼        ▼
         silver.A   gold.B   features.C
              │        │        │
              └────────┼────────┘
                       ▼
                  [Workflow Y]  ← reads from output of X
                       ▼
                  silver.D (output)
                       ▼
              ┌────────┼────────┐
              ▼        ▼        ▼
         Report 1   Alert 2   Dashboard 3
## 24.2 Storage
CREATE TABLE workflow_dependencies (
  source_id UUID,
  source_type VARCHAR(20),
  target_id UUID,
  target_type VARCHAR(20),
  dependency_type VARCHAR(30),
  detected_at TIMESTAMPTZ,
  detection_method VARCHAR(50),
  is_critical BOOLEAN,
  PRIMARY KEY (source_id, source_type, target_id, target_type, dependency_type)
);
## 24.3 Discovery Methods
class DependencyDiscovery:
    
    def discover_static(workflow):
        """Parse workflow definition."""
        deps = []
        for node in workflow.nodes:
            if node.category == 'data_input':
                deps.append({'type': 'reads', 'target': node.config.table})
            elif node.category == 'output':
                deps.append({'type': 'writes', 'target': node.config.table})
            elif node.type == 'action.trigger_workflow':
                deps.append({'type': 'triggers', 'target': node.config.workflow_id})
        return deps
    
    def discover_runtime(workflow_id, runs=100):
        """Observe last N executions."""
        runs = get_recent_runs(workflow_id, n=runs)
        deps = []
        for run in runs:
            for query in run.executed_queries:
                target_tables = parse_tables(query)
                deps.extend([{'type': 'reads_runtime', 'target': t} for t in target_tables])
        return aggregate_unique(deps)
    
    def reconcile(static_deps, runtime_deps):
        only_in_runtime = runtime_deps - static_deps
        if only_in_runtime:
            log_warning(f"Runtime dependencies not declared statically: {only_in_runtime}")

# Phần 25. Better/Worse Comparison Framework
## 25.1 Multi-Criteria (v2.0 — 8 dimensions)
better_worse_dimensions_v2:
  
  dim_1_reliability: weight: 0.20, direction: higher_better
    metrics: [success_rate, error_rate, retry_count]
  
  dim_2_performance: weight: 0.15, direction: lower_better (runtime)
    metrics: [runtime, throughput]
  
  dim_3_cost: weight: 0.10, direction: lower_better
    metrics: [cost_per_execution, monthly_cost]
  
  dim_4_quality: weight: 0.15, direction: higher_better
    metrics: [output_quality_score, business_kpi_impact]
  
  dim_5_user_experience: weight: 0.10, direction: lower_friction_better
    metrics: [manual_intervention_rate, user_complaints]
  
  dim_6_safety: weight: 0.05, direction: zero_violations_required
    metrics: [constraint_violations, compliance_issues]
  
  # ⭐ v2.0 — Adoption
  dim_7_adoption: weight: 0.15, direction: higher_better
    metrics: [adoption_health_score, override_rate (inverse), side_channel_count (inverse)]
  
  # ⭐ v2.0 — Economics
  dim_8_economics: weight: 0.10, direction: higher_better
    metrics: [nov_change, time_to_payback (inverse)]
## 25.2 Composite Score
def compute_better_worse_score(old_workflow, new_workflow):
    score = 0
    breakdown = {}
    
    for dim_name, dim_config in BETTER_WORSE_DIMENSIONS_V2.items():
        old_val = compute_dim_value(old_workflow, dim_config.metrics)
        new_val = compute_dim_value(new_workflow, dim_config.metrics)
        
        if dim_config.direction == 'higher_better':
            improvement = (new_val - old_val) / max(abs(old_val), 1)
        elif dim_config.direction == 'lower_better':
            improvement = (old_val - new_val) / max(abs(old_val), 1)
        elif dim_config.direction == 'zero_violations_required':
            improvement = -1 if new_val > 0 else 0  # hard floor
        
        improvement = max(-1, min(1, improvement))
        score += improvement * dim_config.weight
        breakdown[dim_name] = {'improvement': improvement, 'weight': dim_config.weight}
    
    return {
        'composite_score': score,
        'verdict': verdict_from_score(score),
        'breakdown': breakdown
    }

def verdict_from_score(score):
    if score > 0.10: return 'CLEARLY_BETTER'
    elif score > 0.03: return 'SLIGHTLY_BETTER'
    elif score > -0.03: return 'NEUTRAL'
    elif score > -0.10: return 'SLIGHTLY_WORSE'
    else: return 'CLEARLY_WORSE'
## 25.3 Mixed Outcomes
mixed_outcome_handling:
  
  scenario_better_with_higher_cost:
    breakdown: {reliability: +12, performance: +8, cost: -25, quality: +15}
    verdict: BETTER_BUT_MORE_EXPENSIVE
    decision_aid: "Compare cost increase vs business value"
    typical_acceptable: cost_increase < value_gain × 0.5
  
  scenario_faster_but_less_reliable:
    breakdown: {reliability: -8, performance: +35, cost: -12, quality: 0}
    verdict: FASTER_BUT_LESS_RELIABLE
    decision_aid: "Reliability critical — investigate failures"
    typical_acceptable: reliability_drop < 2pp AND failures recoverable
  
  scenario_better_perf_worse_adoption:
    breakdown: {reliability: +5, performance: +20, adoption: -15}
    verdict: TECHNICALLY_BETTER_BUT_TEAM_RESISTING
    decision_aid: "Performance gain useless if team won't use it"
    action: investigate_adoption_blockers + iterate

# Phần 26. Insight Surfacing of Workflow Changes
## 26.1 Auto-Generated Insights
auto_generated_insights:
  
  workflow_state_changes:
    - "Workflow X moved to TESTING — parallel run with v1"
    - "Workflow Y completed 60-day baseline — review materials ready"
    - "Workflow Z replacement approved — deprecating old"
  
  workflow_performance_changes:
    - "Workflow X (new) shows +12% success rate vs baseline"
    - "Workflow X (new) costs 25% more — review value tradeoff"
    - "Workflow Y bottleneck node Z runtime increased 80%"
  
  workflow_break_or_failure:
    - "Workflow X stopped working — schema change in source"
    - "Workflow Y error rate spike 23% in last 4h"
  
  workflow_recommendation:
    - "AI recommends new workflow Z based on identified inefficiency"
    - "Pattern matches known optimization — review proposal"
  
  # v2.0 — adoption insights
  adoption_alerts:
    - "Override rate spiked 30% this week for Workflow X"
    - "5 side-channel communications detected — investigate"
  
  # v2.0 — economics insights
  economics_alerts:
    - "NOV trending 30% below predicted for Workflow Y"
    - "Time-to-payback extending: was 12mo, now 18mo"
## 26.2 Insight Display
┌────────────────────────────────────────────────────────────┐
│ [INSIGHT] Workflow Performance Change                       │
│                                                             │
│ "Email Campaign workflow (testing v2) improving on baseline"│
│                                                             │
│ ─── DETAILS ───                                             │
│ Day 23 of 90 in TESTING phase                              │
│                                                             │
│ Performance:                                                │
│   Success rate: v1=87%  v2=93%  (+6pp ✓)                   │
│   Runtime:      v1=4m   v2=3m   (-25% ✓)                   │
│   Cost/run:     v1=3.3K v2=2.9K (-12% ✓)                   │
│                                                             │
│ Adoption (v2.0):                                            │
│   Override rate: v1=23% v2=8% (-65% ✓)                     │
│   Side-channel: v1=14 v2=3 (-79% ✓)                        │
│                                                             │
│ Economics (v2.0):                                           │
│   NOV: v1=8.2M v2=11.7M VND/month (+43% ✓)                  │
│   Annualized gain: +42M VND                                 │
│                                                             │
│ Predicted at day 90: APPROVE_REPLACEMENT (high confidence) │
│                                                             │
│ [View Workflow] [View Comparison] [Discuss in Meeting #2]  │
└────────────────────────────────────────────────────────────┘

# PART VIII — ADOPTION INTELLIGENCE ⭐ NEW v2.0
# Phần 27. Why Adoption Fails (Psychological + Structural)
## 27.1 The Brutal Truth
70% các digital transformation projects FAIL, không phải vì công nghệ kém — mà vì người ta không dùng.
"Workflow technically correct" ≠ "Organization accepts it"

Chỉ cần 1 trong các nhóm sau resist → workflow chết:
- End users (sales, ops, marketing): "phiền quá, làm theo cách cũ nhanh hơn"
- Middle managers: "tôi mất kiểm soát, không nhìn thấy team mình đang làm gì"
- Leadership: "ROI không rõ ràng, dừng investment"
- IT/Security: "không an toàn, không tích hợp"
## 27.2 Two Categories of Resistance
resistance_categories:
  
  psychological_resistance:
    description: "Cảm xúc + nhận thức cá nhân"
    signals:
      - fear_of_being_replaced: "AI sẽ thay thế tôi"
      - loss_of_status: "tôi không còn là gatekeeper của process này"
      - cognitive_load: "phải học cái mới, mệt"
      - distrust_of_ai: "AI quyết định sai thì sao"
      - habit_inertia: "10 năm làm theo cách này, sao phải đổi"
    
    detection_difficulty: HIGH (subjective, hard to measure directly)
    intervention: training, change management, transparent AI
  
  structural_resistance:
    description: "Bottlenecks trong tổ chức"
    signals:
      - workflow_too_burdensome: "click 8 lần để làm 1 việc"
      - workflow_too_rigid: "không handle exception"
      - missing_features: "thiếu cái tôi cần, phải workaround"
      - slow_performance: "system chậm, Excel nhanh hơn"
      - integration_gaps: "không nói chuyện được với system khác"
      - permission_issues: "không có quyền, phải nhờ admin"
    
    detection_difficulty: MEDIUM (observable in workflow patterns)
    intervention: workflow redesign, performance optimization
## 27.3 Why SME Việt Especially Vulnerable
vietnamese_sme_context:
  
  factor_1_relationship_based_business:
    impact: "Quy trình thật chạy qua quan hệ cá nhân, không qua system"
    example: "Sale qua Zalo với customer thân quen, không nhập CRM"
  
  factor_2_zalo_dominance:
    impact: "Zalo = primary biz tool, system phải compete with Zalo's UX"
    example: "Approval qua Zalo nhanh, hệ thống phải mở app, login..."
  
  factor_3_excel_native_culture:
    impact: "Mọi quyết định cuối cùng đều qua Excel"
    example: "Báo cáo system OK nhưng phải export ra Excel để 'kiểm tra'"
  
  factor_4_low_tech_maturity:
    impact: "Người dùng không quen drag-drop, không quen workflow"
    example: "Nhân viên 45+ tuổi từ chối học UI mới"
  
  factor_5_hierarchical_decision:
    impact: "Decisions taken in private meetings, not in system"
    example: "Sếp quyết miệng, sau đó nhân viên cập nhật system"
## 27.4 Adoption ≠ Initial Activation
Common mistake: “Department X có 20 nhân viên đăng nhập tuần này → adoption thành công.”
Reality: Login ≠ usage ≠ value extraction. Đo adoption đúng:
adoption_levels:
  
  level_0_aware:
    metric: "Heard about Kaori"
    indicator: "trained_users_count"
  
  level_1_logged_in:
    metric: "Đã login at least once"
    indicator: "first_login_count"
  
  level_2_executed:
    metric: "Đã chạy workflow at least once"
    indicator: "workflows_executed_per_user"
  
  level_3_routine_use:
    metric: "Dùng đều đặn (>= 3x/week)"
    indicator: "active_users_weekly"
  
  level_4_dependent:
    metric: "System là default tool, không workaround"
    indicator: "side_channel_count_low + override_rate_low"
  
  level_5_evangelist:
    metric: "Recommend to others, suggest improvements"
    indicator: "feature_requests + invite_colleagues"

# True adoption = level 4-5 sustained
## 27.5 Acceptance Criteria — Phần 27
☐ Resistance categories documented for training/playbook
☐ Vietnamese SME context built into detection
☐ Adoption levels measured (not just login count)
☐ Distinction between psychological vs structural resistance

# Phần 28. Resistance Signals Catalog (9 signals)
## 28.1 9-Signal Catalog
resistance_signals_v2:
  
  signal_1_workflow_abandonment:
    description: "Workflow started but not completed"
    measurement: "abandoned_runs / started_runs"
    indicator_strength: HIGH (clear behavioral evidence)
    typical_threshold: > 10% concerning, > 20% red alert
    
    what_it_means:
      - Workflow too complex
      - Users don't understand what to do next
      - Workflow asks for things users don't have
      - Permission/access issues mid-flow
    
    sample_message: "Hôm qua user A bắt đầu 12 instances, chỉ hoàn thành 3"
  
  signal_2_excessive_overrides:
    description: "AI suggestions/decisions overridden by humans"
    measurement: "overridden_count / ai_decisions_count"
    indicator_strength: HIGH
    typical_threshold: > 15% concerning, > 30% red alert
    
    what_it_means:
      - AI quality issue (recommendations bad)
      - Trust issue (don't believe AI)
      - Context gap (AI missing info user has)
      - Process mismatch (AI optimizing wrong thing)
    
    distinguish:
      - Override + accept: low concern (sanity check)
      - Override + reverse: medium concern (disagreement)
      - Override + ignore + workaround: HIGH concern (avoidance)
  
  signal_3_approval_delays:
    description: "Approval gates sit pending > expected time"
    measurement: "avg_approval_time vs expected_sla"
    indicator_strength: MEDIUM
    typical_threshold: > 2x SLA concerning
    
    what_it_means:
      - Approver overloaded
      - Approval criteria unclear
      - Approver doesn't trust auto-prep
      - Approver bypasses via off-system channel
    
    correlate_with: signal_8_side_channel
  
  signal_4_manual_exports:
    description: "Users export data to work outside system"
    measurement: "exports_per_user_per_week"
    indicator_strength: MEDIUM-HIGH
    typical_threshold: > 5/user/week concerning
    
    what_it_means:
      - System missing analysis capability
      - User comfort with Excel
      - Distrust of system reports
      - Sharing requirements not met by system
  
  signal_5_side_channel_communication:
    description: "Decisions communicated via Zalo/email instead of system"
    measurement: "off_system_decision_count detected"
    indicator_strength: HIGH (cultural signal)
    typical_threshold: > 5/week per workflow concerning
    
    detection:
      - Cross-reference timestamps: workflow stuck + Zalo activity spike
      - Email subject line matching
      - User self-report (in surveys)
    
    what_it_means:
      - System too slow/clunky
      - Relationship-based culture overriding system
      - Permission/visibility issues
  
  signal_6_workaround_creation:
    description: "Users build their own tools (Excel, Notion) parallel to system"
    measurement: "shadow_tool_detection"
    indicator_strength: HIGH
    
    what_it_means:
      - Critical missing feature
      - System doesn't fit workflow
      - Trust issue (need own copy)
  
  signal_7_low_engagement_with_insights:
    description: "AI insights generated but not viewed/acted on"
    measurement: "insight_view_rate, insight_action_rate"
    indicator_strength: MEDIUM
    typical_threshold: < 30% view rate concerning
    
    what_it_means:
      - Insights not relevant
      - Too many insights (alert fatigue)
      - Insights timing wrong
      - Insights not actionable
  
  signal_8_role_avoidance:
    description: "Specific roles never login or always delegate"
    measurement: "login_rate_by_role, delegation_rate_by_role"
    indicator_strength: MEDIUM
    
    what_it_means:
      - Role doesn't see value
      - Role threatened by visibility
      - UI not designed for this role
  
  signal_9_complaints_and_support_tickets:
    description: "User feedback signals dissatisfaction"
    measurement: "support_tickets, NPS, feature_requests, complaints"
    indicator_strength: MEDIUM (lagging but rich)
    
    what_it_means:
      - Direct expression of issues
      - Often surfaces root cause
## 28.2 Signal Severity Matrix
signal_severity:
  
  GREEN (no concern):
    abandonment_rate: < 5%
    override_rate: < 10%
    side_channel: 0-2/week
    workaround_created: none
  
  YELLOW (monitor):
    abandonment_rate: 5-15%
    override_rate: 10-25%
    side_channel: 3-5/week
    workaround_created: 1-2 instances
  
  ORANGE (intervene):
    abandonment_rate: 15-25%
    override_rate: 25-40%
    side_channel: 6-10/week
    workaround_created: 3-5 instances
  
  RED (critical):
    abandonment_rate: > 25%
    override_rate: > 40%
    side_channel: > 10/week
    workaround_created: > 5 instances

# Phần 29. Detection Methods per Signal
## 29.1 Detection Architecture
┌──────────────────────────────────────────────────────────────┐
│ ADOPTION TELEMETRY COLLECTORS                                │
│  - Workflow execution events (Part X tracing)                │
│  - User action logs (clicks, navigates, dwells)              │
│  - Process Mining session data (Part IV)                     │
│  - External signals (chat metadata, email metadata)          │
│  - Survey responses + NPS                                    │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ SIGNAL EXTRACTORS (1 per signal type)                        │
│  - Parse events → signal occurrences                         │
│  - Aggregate to time windows                                 │
│  - Compute baselines                                         │
│  - Detect anomalies                                          │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ ADOPTION HEALTH SCORE COMPUTATION (Phần 30)                  │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ INTERVENTION RECOMMENDATIONS (Phần 31)                       │
│  - Auto-actions (e.g., simplify UI for confused user)        │
│  - CSM alerts (account at risk)                              │
│  - Manager surfacing (department-level issues)               │
└──────────────────────────────────────────────────────────────┘
## 29.2 Implementation Per Signal
class AdoptionSignalExtractors:
    
    def detect_abandonment(self, workflow_id, window_days=7):
        """Signal 1: Workflow Abandonment"""
        runs = get_workflow_runs(workflow_id, last_days=window_days)
        
        abandoned = []
        for run in runs:
            if run.status == 'started' and not run.has_terminal_state:
                if (now - run.started_at).hours > 24:
                    abandoned.append(run)
            
            elif run.status == 'in_progress' and run.last_event_age_hours > 4:
                if not run.is_long_running_by_design:
                    abandoned.append(run)
        
        rate = len(abandoned) / max(len(runs), 1)
        
        return Signal(
            type='abandonment',
            value=rate,
            severity=self.classify_severity('abandonment', rate),
            sample_runs=abandoned[:5],
            actors=group_by_actor(abandoned)
        )
    
    def detect_overrides(self, workflow_id, window_days=7):
        """Signal 2: Excessive Overrides"""
        ai_decisions = get_ai_decisions(workflow_id, last_days=window_days)
        
        overrides = []
        for decision in ai_decisions:
            if decision.was_overridden:
                overrides.append({
                    'decision_id': decision.id,
                    'override_type': self.classify_override(decision),
                    'actor': decision.overridden_by,
                    'reason': decision.override_reason or 'unspecified'
                })
        
        rate = len(overrides) / max(len(ai_decisions), 1)
        
        return Signal(
            type='override',
            value=rate,
            breakdown_by_type=Counter(o['override_type'] for o in overrides),
            severity=self.classify_severity('override', rate)
        )
    
    def detect_side_channel(self, workflow_id, window_days=7):
        """Signal 5: Side-Channel Communication"""
        # Cross-reference workflow events with chat/email metadata
        workflow_events = get_workflow_events(workflow_id, last_days=window_days)
        
        side_channel_count = 0
        evidence = []
        
        for case_id in get_active_cases(workflow_id):
            workflow_timestamps = [e.timestamp for e in workflow_events if e.case_id == case_id]
            chat_events = get_chat_events_for_case(case_id, last_days=window_days)
            email_events = get_email_events_for_case(case_id, last_days=window_days)
            
            for chat in chat_events:
                if not is_chat_recorded_in_workflow(chat, workflow_events):
                    if is_decision_making_chat(chat):
                        side_channel_count += 1
                        evidence.append({
                            'case_id': case_id,
                            'channel': 'zalo',
                            'timestamp': chat.timestamp,
                            'parties': chat.parties
                        })
        
        return Signal(
            type='side_channel',
            value=side_channel_count,
            severity=self.classify_severity('side_channel', side_channel_count, window_days),
            evidence=evidence[:10]
        )
    
    def detect_workaround(self, workflow_id, tenant_id):
        """Signal 6: Workaround Creation"""
        # Detect Excel files created with similar data structure
        # Detect Notion/external tool URLs in user comms
        # Detect data export patterns followed by external editing
        
        suspicious_files = scan_filesystem_metadata(tenant_id)
        external_tool_mentions = scan_communications_for_tool_mentions(tenant_id)
        export_then_modify_patterns = detect_export_modify_pattern(tenant_id)
        
        workarounds = []
        for f in suspicious_files:
            if has_similar_schema_to_workflow_output(f, workflow_id):
                workarounds.append({
                    'type': 'parallel_excel',
                    'file': f.path_redacted,
                    'last_modified_by': f.modifier,
                    'frequency': f.modification_frequency
                })
        
        return Signal(
            type='workaround',
            value=len(workarounds),
            severity=self.classify_severity('workaround', len(workarounds)),
            workarounds=workarounds
        )
## 29.3 Signal Storage Schema
CREATE TABLE adoption_signals (
  signal_id UUID PRIMARY KEY,
  tenant_id UUID,
  workflow_id UUID,
  signal_type VARCHAR(50),
  
  detection_window_start TIMESTAMPTZ,
  detection_window_end TIMESTAMPTZ,
  
  raw_value NUMERIC,
  normalized_value NUMERIC,  -- 0-1 scale
  severity VARCHAR(10),  -- GREEN/YELLOW/ORANGE/RED
  
  evidence JSONB,
  affected_actors JSONB,  -- which users/roles
  
  detected_at TIMESTAMPTZ,
  
  -- Lifecycle
  acknowledged BOOLEAN DEFAULT false,
  acknowledged_by UUID,
  acknowledged_at TIMESTAMPTZ,
  intervention_taken JSONB,
  resolved BOOLEAN DEFAULT false,
  resolved_at TIMESTAMPTZ
);

CREATE INDEX idx_adoption_tenant_workflow ON adoption_signals (tenant_id, workflow_id);
CREATE INDEX idx_adoption_severity ON adoption_signals (severity, resolved);
CREATE INDEX idx_adoption_detected ON adoption_signals (detected_at DESC);

# Phần 30. Adoption Health Score (Composite)
## 30.1 Score Formula
class AdoptionHealthScore:
    """Compose 9 signals into single 0-100 score per workflow."""
    
    SIGNAL_WEIGHTS = {
        'abandonment': 0.20,
        'override': 0.15,
        'approval_delays': 0.10,
        'manual_exports': 0.10,
        'side_channel': 0.15,
        'workaround': 0.15,
        'low_engagement': 0.05,
        'role_avoidance': 0.05,
        'complaints': 0.05
    }
    
    def compute(self, workflow_id, window_days=30):
        signals = {
            name: extractor.extract(workflow_id, window_days)
            for name, extractor in self.extractors.items()
        }
        
        score = 100  # start perfect
        
        for signal_name, signal in signals.items():
            severity_penalty = {
                'GREEN': 0,
                'YELLOW': 10,
                'ORANGE': 25,
                'RED': 50
            }[signal.severity]
            
            weighted_penalty = severity_penalty * self.SIGNAL_WEIGHTS[signal_name]
            score -= weighted_penalty
        
        score = max(0, min(100, score))
        
        return {
            'composite_score': score,
            'classification': self.classify(score),
            'signals': signals,
            'top_issues': self.rank_issues(signals),
            'trend': self.compute_trend(workflow_id, score)
        }
    
    def classify(self, score):
        if score >= 85: return 'EXCELLENT'
        elif score >= 70: return 'HEALTHY'
        elif score >= 55: return 'AT_RISK'
        elif score >= 40: return 'STRUGGLING'
        else: return 'CRITICAL'
## 30.2 Department-Level Aggregation
def department_adoption_summary(tenant_id, department):
    workflows = get_active_workflows(tenant_id, department=department)
    
    workflow_scores = [
        AdoptionHealthScore().compute(w.id) for w in workflows
    ]
    
    return {
        'department_avg_score': mean(s['composite_score'] for s in workflow_scores),
        'workflows_at_risk': [s for s in workflow_scores if s['composite_score'] < 55],
        'top_signals_in_department': aggregate_top_signals(workflow_scores),
        'cultural_pattern': detect_pattern(workflow_scores)
    }
## 30.3 Adoption Score Dashboard
┌──────────────────────────────────────────────────────────────┐
│ ADOPTION HEALTH — Marketing Department                       │
│                                                              │
│ Department Average: 68/100  (HEALTHY)                        │
│ Trend: ↘ -7 points last 14 days  ⚠️                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Workflows by Health:                                         │
│                                                              │
│  Email Campaign Workflow         85/100  EXCELLENT  ✓        │
│  Newsletter Personalization      72/100  HEALTHY    ✓        │
│  Customer Onboarding             58/100  AT_RISK    ⚠️       │
│  Re-engagement Campaign          42/100  STRUGGLING ❗        │
│                                                              │
│ ─── TOP ISSUES THIS WEEK ───                                 │
│                                                              │
│ 1. Re-engagement Campaign - Side-channel comms +15           │
│    Evidence: 15 Zalo conversations between sales-customer    │
│    after AI flagged but before workflow completes            │
│    → Likely cause: AI flag → user prefers to call manually  │
│    Recommended: Add "call attempted" step in workflow        │
│                                                              │
│ 2. Customer Onboarding - Override rate 32%                   │
│    Evidence: AI suggests Tier-A onboarding, user picks B     │
│    → Likely cause: AI doesn't see customer's industry        │
│    Recommended: Add industry input to AI context             │
│                                                              │
│ 3. Re-engagement Campaign - Abandonment 28%                  │
│    Evidence: Step "review AI proposal" not completed         │
│    → Likely cause: UI confusing, too many options            │
│    Recommended: Simplify to 3 buttons (Accept/Modify/Skip)   │
│                                                              │
│ [Drill into workflow] [Schedule CSM call] [Auto-fix issue]   │
└──────────────────────────────────────────────────────────────┘

# Phần 31. Intervention Playbook
## 31.1 Intervention Hierarchy
intervention_levels:
  
  level_1_auto_in_product:
    when: "YELLOW signal, low risk"
    examples:
      - "User confused at step X → show inline help tooltip"
      - "Frequent override of insight type Y → reduce frequency"
      - "Low engagement with insight Z → demote in priority"
    actor: "system (no human needed)"
  
  level_2_in_product_nudge:
    when: "YELLOW-ORANGE signal, structural issue"
    examples:
      - "Show 'Did you mean to do X?' suggestion"
      - "Offer simpler workflow variant"
      - "Surface workflow tips at right moment"
    actor: "system"
  
  level_3_csm_alert:
    when: "ORANGE signal sustained > 2 weeks"
    examples:
      - "Account at risk — schedule check-in"
      - "Department X struggling — offer training"
    actor: "Customer Success Manager (CSM)"
  
  level_4_csm_active_engagement:
    when: "ORANGE-RED signal"
    examples:
      - "Onsite training session"
      - "1:1 walkthrough with department head"
      - "Workflow redesign workshop"
    actor: "CSM + Implementation Consultant"
  
  level_5_executive_intervention:
    when: "RED signal at department or company level"
    examples:
      - "Account renewal at risk"
      - "Cancellation likely"
    actor: "Account Manager + Customer Lead + Engineering"
## 31.2 Auto-Intervention Examples
class AutoInterventions:
    
    def respond_to_abandonment(self, signal):
        if signal.most_common_abandonment_step:
            step = signal.most_common_abandonment_step
            
            # Add inline help to that step
            update_workflow_node_help(
                node_id=step.node_id,
                help_text=self.generate_contextual_help(step)
            )
            
            # Track if intervention reduces abandonment
            self.track_intervention_outcome(signal, intervention='inline_help')
    
    def respond_to_override(self, signal):
        if signal.value > 0.30:  # very high override
            # Reduce AI confidence expression to user
            for affected_node in signal.affected_nodes:
                lower_recommendation_threshold(affected_node, by=0.10)
            
            # Surface "why" more prominently
            enable_explainability_panel_for_node(affected_node)
    
    def respond_to_side_channel(self, signal):
        # Hardest to auto-fix; mostly requires CSM
        # But can: 
        # 1. Add Zalo integration node suggestion
        # 2. Send email to manager about pattern
        notify_manager(
            workflow_id=signal.workflow_id,
            template='side_channel_pattern_detected',
            evidence=signal.evidence_summary
        )
    
    def respond_to_workaround(self, signal):
        # Suggest the missing feature in product roadmap discussion
        create_feature_request(
            tenant_id=signal.tenant_id,
            type='workaround_replacement',
            evidence=signal.workarounds,
            proposed_feature=infer_missing_feature(signal.workarounds)
        )
## 31.3 CSM Engagement Triggers
csm_alert_rules:
  
  rule_1_account_health_decline:
    trigger: "Adoption score drops > 15 points in 14 days"
    sla: "CSM contacts within 48h"
    template: "account_health_check"
  
  rule_2_department_struggling:
    trigger: "Department avg < 55 for 21+ days"
    sla: "CSM proposes training within 7 days"
    template: "department_training_offer"
  
  rule_3_critical_workflow_at_risk:
    trigger: "Important workflow (high economic impact) hits CRITICAL"
    sla: "CSM + engineering review within 24h"
    template: "critical_workflow_emergency"
  
  rule_4_executive_pattern_emerging:
    trigger: "Multiple departments declining + high churn risk"
    sla: "Account manager engages within 24h"
    template: "executive_intervention"
## 31.4 Intervention Effectiveness Tracking
def track_intervention_effectiveness(intervention):
    pre_intervention_score = get_adoption_score(intervention.workflow_id, before=intervention.timestamp)
    
    schedule_check(intervention, after_days=14)
    schedule_check(intervention, after_days=30)
    
    @callback(after_days=14)
    def evaluate():
        post_score = get_adoption_score(intervention.workflow_id)
        improvement = post_score.composite_score - pre_intervention_score.composite_score
        
        log_intervention_outcome(intervention.id, {
            'improvement': improvement,
            'effective': improvement > 5,
            'side_effects': detect_side_effects(intervention)
        })
        
        # Feed back into intervention recommendation engine
        train_intervention_model(intervention, improvement)

# PART IX — RUNTIME RELIABILITY ARCHITECTURE ⭐ NEW v2.0
# Phần 32. Idempotency Architecture
## 32.1 Why Idempotency is Critical
Reality: Workflow runs can fail mid-flight. Network glitches. Server restarts. Race conditions. Without idempotency, retry → duplicate side effects.
Without idempotency:
   Send email node → fails after sending
   Retry → sends email AGAIN
   Customer receives 2 emails  ❌

With idempotency:
   Send email node with key "user_123_campaign_456_2026-05-07"
   First call: sends, records key
   Retry: sees key already used, returns success without re-send  ✓
## 32.2 Idempotency Key Strategy
idempotency_keys:
  
  per_node_class:
    
    pure: # no side effects
      key_needed: NO
      approach: "Re-execute freely, same input → same output"
    
    read_only: # external reads
      key_needed: NO (cached if useful)
      approach: "Re-read OK; cache for performance"
    
    write_idempotent: # writes that are safe to repeat
      key_needed: YES
      approach: "Use natural key (e.g., upsert by primary key)"
      example: "save_to_database with mode=upsert + record_id"
    
    write_non_idempotent: # creates new state each call
      key_needed: YES (CRITICAL)
      approach: "Generate idempotency key, dedupe at caller"
      example: "create_task: key = workflow_run_id + node_id + record_id"
    
    external_irreversible: # cannot undo
      key_needed: YES (CRITICAL)
      approach: "Idempotency key + provider-side dedupe (when supported)"
      example: "send_email: provider checks dedupe key before sending"
## 32.3 Implementation
class IdempotencyManager:
    
    def execute_with_idempotency(self, node, execution_context, input_data):
        if node.side_effect_class in ['pure', 'read_only']:
            return node.execute(input_data)
        
        idempotency_key = self.compute_key(node, execution_context, input_data)
        
        existing_result = self.idempotency_store.lookup(idempotency_key)
        if existing_result:
            log.info(f"Idempotent: {idempotency_key} already executed, returning cached result")
            return existing_result.result
        
        with self.idempotency_store.lock(idempotency_key, timeout=300):
            existing_result = self.idempotency_store.lookup(idempotency_key)
            if existing_result:
                return existing_result.result
            
            try:
                result = node.execute(input_data)
                self.idempotency_store.record(idempotency_key, result, ttl_days=30)
                return result
            except Exception as e:
                # Don't record failures (allow retry)
                # But record permanent failures (don't retry)
                if isinstance(e, PermanentFailure):
                    self.idempotency_store.record_failure(idempotency_key, e, ttl_days=30)
                raise
    
    def compute_key(self, node, execution_context, input_data):
        if node.config.idempotency_key_extractor:
            template = node.config.idempotency_key_extractor
            return self.render_template(template, execution_context, input_data)
        else:
            # Default: hash workflow_run_id + node_id + input_hash
            return hash(f"{execution_context.workflow_run_id}:{node.id}:{stable_hash(input_data)}")
## 32.4 Storage
CREATE TABLE idempotency_records (
  idempotency_key VARCHAR(500) PRIMARY KEY,
  tenant_id UUID,
  workflow_id UUID,
  node_id VARCHAR(100),
  
  result JSONB,
  status VARCHAR(20),  -- 'success' | 'permanent_failure'
  
  recorded_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  
  -- For tenant cleanup
  INDEX (tenant_id, expires_at)
);

-- Automatic cleanup
CREATE OR REPLACE FUNCTION cleanup_expired_idempotency()
RETURNS void AS $$
  DELETE FROM idempotency_records WHERE expires_at < NOW();
$$ LANGUAGE sql;
## 32.5 Acceptance Criteria — Phần 32
☐ Every non-idempotent node has idempotency_key configured
☐ Idempotency store with TTL (30 days default)
☐ Distributed lock prevents race conditions
☐ Permanent failures recorded (no retry storms)
☐ Cleanup job runs daily

# Phần 33. Retry & Backoff Strategy
## 33.1 Retry Policy Per Node Class
default_retry_policies:
  
  pure_or_read_only:
    max_retries: 3
    backoff: exponential
    base_delay_seconds: 1
    max_delay_seconds: 60
    jitter: true
    retry_on: [TransientError, NetworkError, RateLimitError]
    no_retry_on: [PermanentError, ConfigError]
  
  write_idempotent:
    max_retries: 5
    backoff: exponential
    base_delay_seconds: 2
    max_delay_seconds: 120
    jitter: true
  
  write_non_idempotent:
    max_retries: 3  # lower; idempotency key handles dedupe
    backoff: exponential
    base_delay_seconds: 1
    max_delay_seconds: 30
    jitter: true
  
  external_irreversible:
    max_retries: 1  # very conservative
    backoff: fixed
    base_delay_seconds: 5
    rationale: "Cannot risk multiple sends; idempotency key only safety"
  
  ai_calls:
    max_retries: 2
    backoff: exponential
    base_delay_seconds: 5
    max_delay_seconds: 60
    rationale: "AI calls expensive; don't retry storm"
## 33.2 Backoff Math
def compute_delay(attempt_number, policy):
    if policy.backoff == 'fixed':
        delay = policy.base_delay_seconds
    elif policy.backoff == 'linear':
        delay = policy.base_delay_seconds * attempt_number
    elif policy.backoff == 'exponential':
        delay = policy.base_delay_seconds * (2 ** (attempt_number - 1))
    
    delay = min(delay, policy.max_delay_seconds)
    
    if policy.jitter:
        # Full jitter: random between 0 and delay
        delay = random.uniform(0, delay)
    
    return delay
## 33.3 Retry Budget per Workflow
retry_budget:
  
  per_workflow_run:
    max_total_retries_across_all_nodes: 20
    rationale: "Prevent infinite retry storms"
    on_exceeded: "fail workflow run, send to DLQ"
  
  per_tenant_per_hour:
    max_total_retries: 1000
    rationale: "Prevent one bad workflow draining capacity"
    on_exceeded: "rate-limit tenant retries, alert ops"
## 33.4 Retry vs DLQ Decision
def retry_or_dlq(node, attempt_number, last_error):
    policy = node.reliability.retry_policy
    
    if attempt_number >= policy.max_retries:
        return 'send_to_dlq'
    
    if isinstance(last_error, PermanentFailure):
        return 'send_to_dlq'
    
    if budget_exceeded(node.workflow_run_id):
        return 'send_to_dlq'
    
    delay = compute_delay(attempt_number + 1, policy)
    return f'retry_after_{delay}s'

# Phần 34. Saga Pattern & Compensating Transactions
## 34.1 Saga Pattern Explained
Problem: Workflow has multiple write/external steps. If step 5 fails, what about steps 1-4 (already completed)?
Saga solution: Each forward step has a compensating step that undoes it. If failure → execute compensations in reverse order.
Workflow:  A → B → C → D → E
                       ✗ fails

Saga rollback:
  D-compensation
  C-compensation
  B-compensation
  A-compensation
## 34.2 Saga Configuration
workflow_with_saga:
  
  reliability:
    saga_enabled: true
    saga_strategy: 'orchestrated'  # or 'choreographed'
  
  nodes:
    - id: charge_card
      side_effect_class: external_irreversible
      compensating_action: refund_card
    
    - id: reserve_inventory
      side_effect_class: write_non_idempotent
      compensating_action: release_inventory
    
    - id: send_confirmation_email
      side_effect_class: external_irreversible
      compensating_action: send_cancellation_email
    
    - id: update_loyalty_points
      side_effect_class: write_idempotent
      compensating_action: revert_loyalty_points
## 34.3 Saga Engine Implementation
class SagaEngine:
    
    def execute_with_saga(self, workflow):
        executed_nodes = []
        
        try:
            for node in workflow.execution_order:
                result = self.execute_node(node)
                executed_nodes.append((node, result))
        
        except Exception as e:
            log.error(f"Saga failure at node {node.id}: {e}")
            self.execute_compensations(executed_nodes)
            raise SagaRolledBackException(e)
        
        return executed_nodes
    
    def execute_compensations(self, executed_nodes):
        for node, result in reversed(executed_nodes):
            if not node.compensating_action:
                log.warning(f"Node {node.id} has no compensation; manual cleanup needed")
                continue
            
            try:
                self.execute_compensation(node, result)
                log.info(f"Compensated node {node.id}")
            except Exception as e:
                log.error(f"Compensation failed for {node.id}: {e}")
                # Send to DLQ for manual cleanup
                self.dlq.send({
                    'type': 'compensation_failed',
                    'node_id': node.id,
                    'original_result': result,
                    'compensation_error': str(e)
                })
## 34.4 Saga Edge Cases
saga_edge_cases:
  
  case_1_compensation_also_fails:
    handling: "Send to DLQ for manual ops review"
    alert: "Operations team must clean up"
  
  case_2_no_compensation_defined:
    handling: "Log warning, continue rollback for other nodes"
    note: "Some operations have no compensation (e.g., SMS sent)"
  
  case_3_partial_compensation:
    example: "Refund only partially completes"
    handling: "Mark as partially-compensated, manual review"
  
  case_4_cascading_compensation:
    example: "Compensation triggers another workflow"
    handling: "Yes, but with depth limit (max 3) to prevent loops"
  
  case_5_long_running_saga:
    example: "Saga spans days (e.g., physical shipment)"
    handling: "Persist saga state; resume from checkpoint after restart"
## 34.5 Acceptance Criteria — Phần 34
☐ Workflows with external_irreversible nodes have saga_enabled
☐ Compensation defined for each non-pure node
☐ Saga engine executes rollback on failure
☐ Compensation failures → DLQ
☐ Saga state persisted (survives restart)

# Phần 35. Dead-Letter Queue & Event Replay
## 35.1 DLQ Architecture
┌─────────────────────────────────────────────────────────────┐
│ Workflow Execution                                          │
│   Node fails → retry exhausted → SEND TO DLQ                │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ DEAD-LETTER QUEUE (DLQ)                                     │
│   - Stores failed messages                                  │
│   - Categorized by error type                               │
│   - Retention: 30 days                                      │
└──────┬──────────────────────────────────────┬───────────────┘
       │                                      │
       ▼                                      ▼
┌──────────────────┐                  ┌──────────────────────┐
│ MANUAL REVIEW    │                  │ AUTOMATED RECOVERY   │
│   - Ops dashboard│                  │   - Pattern detection│
│   - Inspect data │                  │   - Auto-replay if   │
│   - Trigger replay                  │     transient        │
└──────────────────┘                  └──────────────────────┘
## 35.2 DLQ Schema
CREATE TABLE dlq_messages (
  message_id UUID PRIMARY KEY,
  tenant_id UUID,
  workflow_id UUID,
  workflow_run_id UUID,
  node_id VARCHAR(100),
  
  failure_type VARCHAR(50),  -- 'permanent_error', 'retry_exhausted', 'compensation_failed', etc.
  error_message TEXT,
  error_class VARCHAR(200),
  stack_trace TEXT,
  
  input_data JSONB,
  partial_state JSONB,  -- where in workflow we got
  
  attempt_count INTEGER,
  first_attempted_at TIMESTAMPTZ,
  last_attempted_at TIMESTAMPTZ,
  sent_to_dlq_at TIMESTAMPTZ,
  
  -- Resolution tracking
  status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'replayed', 'discarded', 'manually_resolved'
  resolved_at TIMESTAMPTZ,
  resolved_by UUID,
  resolution_notes TEXT
);

CREATE INDEX idx_dlq_tenant_status ON dlq_messages (tenant_id, status);
CREATE INDEX idx_dlq_failure_type ON dlq_messages (failure_type, sent_to_dlq_at);
## 35.3 Event Replay
class EventReplay:
    """Replay failed workflow runs from DLQ or for debugging."""
    
    def replay_from_dlq(self, message_id, modifications=None):
        message = self.dlq.get(message_id)
        
        if not self.is_replayable(message):
            raise ReplayNotAllowed(f"Message {message_id} not replayable: {reason}")
        
        replay_input = message.input_data
        if modifications:
            replay_input = apply_modifications(replay_input, modifications)
        
        new_run = create_workflow_run(
            workflow_id=message.workflow_id,
            trigger_data=replay_input,
            replay_of=message_id,
            start_from_node=message.node_id  # resume from failed node
        )
        
        execute_workflow_run(new_run)
        
        message.status = 'replayed'
        message.resolved_at = now()
        self.dlq.update(message)
        
        return new_run
    
    def is_replayable(self, message):
        if message.failure_type == 'permanent_error':
            return False  # data is bad, replay won't help
        
        if days_since(message.sent_to_dlq_at) > 30:
            return False  # too stale
        
        return True
    
    def auto_replay_transients(self):
        """Periodically auto-replay transient failures."""
        candidates = self.dlq.query(
            status='pending',
            failure_type__in=['network_error', 'rate_limit', 'timeout'],
            sent_to_dlq_at__gte=now() - timedelta(hours=24)
        )
        
        for message in candidates:
            try:
                self.replay_from_dlq(message.message_id)
            except Exception as e:
                log.warning(f"Auto-replay failed for {message.message_id}: {e}")
## 35.4 Operations Dashboard for DLQ
┌──────────────────────────────────────────────────────────────┐
│ DLQ — Customer Tenant ABC Retail                             │
│                                                              │
│ Pending: 23 messages                                         │
│ Last 24h: 47 failures, 12 auto-replayed, 35 pending          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ─── BY FAILURE TYPE ───                                      │
│  network_error: 15  [Auto-replay enabled]                   │
│  rate_limit: 8       [Auto-replay with backoff]             │
│  permanent_error: 3  [Manual review required]               │
│  compensation_failed: 1  [URGENT — operations escalation]   │
│                                                              │
│ ─── BY WORKFLOW ───                                          │
│  Email Campaign v3: 12 pending                               │
│  Customer Onboarding: 8 pending                              │
│  Inventory Reorder: 3 pending                                │
│                                                              │
│ ─── RECENT FAILURES ───                                      │
│  12:34 send_email node — SMTP timeout (5 retries)            │
│        Workflow Run: abc123  Customer: cust_456              │
│        [View] [Replay] [Discard] [Modify & Replay]           │
│                                                              │
│  12:31 charge_card → reserve_inventory                       │
│        SAGA ROLLBACK FAILED — manual cleanup needed          │
│        [Critical: View] [Operations Escalate]                │
│                                                              │
│ [Bulk replay] [Export to CSV] [Configure auto-replay]        │
└──────────────────────────────────────────────────────────────┘

# Phần 36. Partial Failure Recovery & Checkpointing
## 36.1 Checkpoint Strategy
checkpoint_strategy:
  
  default:
    interval: every 5 nodes
    after_long_running_nodes: yes
    after_external_calls: yes
  
  state_captured_per_checkpoint:
    - completed_nodes
    - intermediate_outputs
    - workflow_variables
    - saga_executed_steps (for rollback)
  
  storage:
    location: workflow_run_checkpoints table
    retention: 7 days after run completes
    compression: enabled
## 36.2 Checkpoint Schema
CREATE TABLE workflow_run_checkpoints (
  checkpoint_id UUID PRIMARY KEY,
  workflow_run_id UUID,
  
  checkpoint_index INTEGER,  -- 1, 2, 3... within run
  created_at TIMESTAMPTZ,
  
  completed_node_ids JSONB,
  node_outputs JSONB,
  workflow_variables JSONB,
  saga_executed_steps JSONB,
  
  -- For resumption
  next_node_id VARCHAR(100),
  
  -- Compression
  is_compressed BOOLEAN,
  data_size_bytes INTEGER,
  
  INDEX (workflow_run_id, checkpoint_index)
);
## 36.3 Recovery Process
class CheckpointRecovery:
    
    def recover_workflow_run(self, run_id):
        """Resume workflow from last checkpoint after failure/restart."""
        
        last_checkpoint = self.get_latest_checkpoint(run_id)
        if not last_checkpoint:
            log.warning(f"No checkpoint for {run_id}, restarting from beginning")
            return self.restart_workflow_run(run_id)
        
        run = self.workflow_run_store.get(run_id)
        
        # Restore state
        run.completed_nodes = last_checkpoint.completed_node_ids
        run.node_outputs = last_checkpoint.node_outputs
        run.workflow_variables = last_checkpoint.workflow_variables
        run.saga_executed_steps = last_checkpoint.saga_executed_steps
        
        # Resume from next node
        next_node = run.workflow.get_node(last_checkpoint.next_node_id)
        return self.execute_from_node(run, next_node)
## 36.4 Crash Recovery on Server Restart
class WorkflowRunRecoveryOnStartup:
    """Run on server startup to recover in-progress workflows."""
    
    def recover_all(self):
        in_progress = self.workflow_run_store.find(status='in_progress')
        
        for run in in_progress:
            # Heuristic: if last update > 5min ago, likely orphaned by crash
            if (now() - run.last_update_at).total_seconds() > 300:
                log.info(f"Recovering orphaned run {run.id}")
                self.recovery.recover_workflow_run(run.id)

# Phần 37. Exactly-Once vs At-Least-Once Decision Framework
## 37.1 Three Semantics
delivery_semantics:
  
  at_most_once:
    description: "Try once, don't retry"
    failure_mode: "Lose messages on failure"
    use_for: "When duplicates worse than loss (rare)"
    example: "Best-effort logging, fire-and-forget"
  
  at_least_once:
    description: "Retry until success; duplicates possible"
    failure_mode: "May execute multiple times"
    use_for: "Default; combine with idempotency for safety"
    example: "Most workflows; data sync with idempotent upsert"
  
  exactly_once:
    description: "Execute exactly once, no duplicates, no losses"
    failure_mode: "Slowest, most complex"
    use_for: "Critical financial/legal operations"
    example: "Payment processing, contract execution"
## 37.2 Decision Matrix
                        Loss Tolerated?
                        ┌──────────┬──────────┐
                        │   YES    │    NO    │
   Duplicates Tolerated?├──────────┼──────────┤
                  YES   │ at-most  │ at-least │
                        │   once   │   once   │
                  ─────┼──────────┼──────────┤
                  NO    │ (rare)   │ exactly  │
                        │          │   once   │
                        └──────────┴──────────┘
## 37.3 Achieving Exactly-Once
Hard! Requires: 1. Idempotency (Phần 32) — ensures duplicates harmless 2. Distributed locks — prevent concurrent execution 3. Atomic transactions — across systems (saga compensates) 4. Provider-side dedup — for external services (where supported)
class ExactlyOnceExecutor:
    """For workflow nodes requiring exactly-once."""
    
    def execute(self, node, input_data):
        idempotency_key = self.compute_key(node, input_data)
        
        with self.distributed_lock.acquire(idempotency_key, timeout=300):
            cached = self.idempotency_store.get(idempotency_key)
            if cached:
                return cached.result
            
            with self.transaction_manager.begin() as tx:
                result = node.execute(input_data)
                
                self.idempotency_store.set(
                    idempotency_key,
                    result,
                    transactional=True
                )
                
                tx.commit()
            
            return result
## 37.4 When NOT to use Exactly-Once
exactly_once_costs:
  performance: "5-10x slower than at-least-once"
  complexity: "Significantly more code"
  failure_modes: "More edge cases"
  
  default_recommendation: "Use at-least-once + idempotency for 95% of cases"
  reserve_exactly_once_for:
    - Financial transactions (>$1000)
    - Legal/compliance actions
    - Inventory commits with no slack

# PART X — RUNTIME OBSERVABILITY ⭐ NEW v2.0
# Phần 38. Distributed Tracing Model
## 38.1 Why Tracing for Workflows
Without tracing:
   "Workflow X is slow" — but where exactly?
   "Workflow Y failed" — but at which step?
   "Cost is high" — but which node?

With tracing:
   Every workflow run = 1 trace
   Every node execution = 1 span (within the trace)
   Every external call = 1 child span
   Result: granular visibility into every part of every run
## 38.2 OpenTelemetry-Based Architecture
┌──────────────────────────────────────────────────────────────┐
│ WORKFLOW EXECUTION LAYER                                     │
│   Workflow Engine instruments every node execution           │
│   Generates OpenTelemetry spans                              │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ OPENTELEMETRY COLLECTOR                                      │
│   - Receives spans                                           │
│   - Adds metadata (tenant, workflow, run_id)                 │
│   - Routes to backends                                       │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
                ┌────────────┴────────────┐
                ▼                         ▼
┌──────────────────────────┐  ┌──────────────────────────┐
│ JAEGER (or Tempo)        │  │ CLICKHOUSE (analytics)   │
│   - Trace search         │  │   - Aggregation queries  │
│   - Visual trace explore │  │   - Long-term retention  │
└──────────────────────────┘  └──────────────────────────┘
## 38.3 Span Hierarchy
Trace: workflow_run_id = abc123
├─ Span: workflow_execution (root)
│   ├─ Span: node_001 (read_table)
│   │   └─ Span: db_query (postgres)
│   ├─ Span: node_002 (transform)
│   ├─ Span: node_003 (ai.generate_insight)
│   │   ├─ Span: llm_api_call (claude)
│   │   └─ Span: constraint_check (reasoning_layer)
│   ├─ Span: node_004 (decision.if_else)
│   ├─ Span: node_005 (action.send_email) ◄── child branch
│   │   └─ Span: smtp_send
│   └─ Span: node_006 (output.save_to_database)
│       └─ Span: db_insert
## 38.4 Span Attributes
span_attributes_per_node:
  
  standard_attributes:
    - workflow_id
    - workflow_run_id
    - node_id
    - node_type
    - tenant_id
    - workflow_version
  
  performance_attributes:
    - duration_ms
    - cpu_time_ms
    - memory_peak_mb
    - input_size_bytes
    - output_size_bytes
  
  reliability_attributes:
    - retry_count
    - is_retry
    - idempotency_key (hashed)
    - status (success/failure/timeout)
  
  cost_attributes:
    - estimated_cost_vnd
    - llm_tokens_used (if AI node)
    - api_calls_made
  
  context_attributes:
    - user_id (if user-triggered)
    - parent_workflow_run_id (if triggered by other workflow)
    - replay_of (if this is a replay)

# Phần 39. Workflow Run Trace Schema
## 39.1 Trace Storage Schema
CREATE TABLE workflow_traces (
  trace_id UUID PRIMARY KEY,
  workflow_run_id UUID,
  workflow_id UUID,
  tenant_id UUID,
  
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  duration_ms INTEGER,
  
  status VARCHAR(20),  -- 'success', 'failure', 'partial', 'timeout'
  
  -- Aggregated metrics
  total_nodes INTEGER,
  succeeded_nodes INTEGER,
  failed_nodes INTEGER,
  retried_nodes INTEGER,
  total_retries INTEGER,
  
  total_cost_vnd NUMERIC,
  total_llm_tokens INTEGER,
  total_db_queries INTEGER,
  
  -- Trigger info
  triggered_by VARCHAR(50),
  triggered_by_user_id UUID,
  
  -- For aggregation
  workflow_version INTEGER,
  
  INDEX (tenant_id, started_at DESC),
  INDEX (workflow_id, started_at DESC),
  INDEX (status, started_at DESC) WHERE status != 'success'
);

CREATE TABLE workflow_trace_spans (
  span_id UUID PRIMARY KEY,
  trace_id UUID,
  parent_span_id UUID,
  
  span_kind VARCHAR(30),  -- 'workflow', 'node', 'external_call', 'db_query'
  span_name VARCHAR(200),
  
  started_at TIMESTAMPTZ,
  ended_at TIMESTAMPTZ,
  duration_ms INTEGER,
  
  status VARCHAR(20),
  status_message TEXT,
  
  -- Node-specific
  node_id VARCHAR(100),
  node_type VARCHAR(50),
  retry_attempt INTEGER,
  
  -- Performance
  input_size_bytes INTEGER,
  output_size_bytes INTEGER,
  cpu_time_ms INTEGER,
  
  -- Cost
  cost_vnd NUMERIC,
  llm_tokens INTEGER,
  
  attributes JSONB,
  events JSONB,  -- log events within span
  
  INDEX (trace_id, started_at)
);
## 39.2 Trace Query API
class TraceQuery:
    
    def get_trace(self, trace_id):
        trace = self.traces.get(trace_id)
        spans = self.spans.query(trace_id=trace_id)
        return self.build_hierarchy(trace, spans)
    
    def find_slow_runs(self, workflow_id, threshold_p95_ms):
        return self.traces.query(
            workflow_id=workflow_id,
            duration_ms__gt=threshold_p95_ms,
            order_by='duration_ms DESC',
            limit=100
        )
    
    def find_runs_with_retries(self, workflow_id, min_retries=3):
        return self.traces.query(
            workflow_id=workflow_id,
            total_retries__gte=min_retries
        )
    
    def find_expensive_runs(self, tenant_id, threshold_vnd):
        return self.traces.query(
            tenant_id=tenant_id,
            total_cost_vnd__gt=threshold_vnd,
            order_by='total_cost_vnd DESC'
        )
    
    def aggregate_node_performance(self, workflow_id, time_range):
        """Per-node performance aggregation."""
        return self.spans.aggregate(
            group_by=['node_id', 'node_type'],
            metrics={
                'avg_duration_ms': 'AVG(duration_ms)',
                'p95_duration_ms': 'PERCENTILE(duration_ms, 0.95)',
                'failure_rate': 'COUNT(status="failure") / COUNT(*)',
                'retry_rate': 'COUNT(retry_attempt > 0) / COUNT(*)',
                'avg_cost_vnd': 'AVG(cost_vnd)'
            },
            filters={
                'workflow_id': workflow_id,
                'started_at__between': time_range
            }
        )

# Phần 40. Real-Time Execution Dashboard
## 40.1 Live Runs View
┌──────────────────────────────────────────────────────────────┐
│ LIVE WORKFLOW EXECUTION                          [auto-refresh]│
│                                                              │
│ Currently Running: 23                                        │
│ Last 5min: 47 started, 41 completed, 6 in flight             │
│ Success rate (last hour): 94%                                │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ─── ACTIVE RUNS ───                                          │
│                                                              │
│  Run 1234 — Email Campaign                                   │
│  Started: 12:34:22  Duration: 47s                            │
│  Progress: 4/8 nodes  ●●●●○○○○                               │
│  Status: in_progress (node 5 in retry attempt 2)             │
│  [View Trace]                                                │
│                                                              │
│  Run 1235 — Customer Onboarding                              │
│  Started: 12:34:55  Duration: 14s                            │
│  Progress: 2/12 nodes  ●●○○○○○○○○○○                         │
│  Status: in_progress                                         │
│  [View Trace]                                                │
│                                                              │
│  Run 1228 — Inventory Reorder ⚠️ slow                        │
│  Started: 12:25:00  Duration: 9m 47s (expected ~4min)        │
│  Progress: 7/9 nodes ●●●●●●●○○                               │
│  Status: in_progress (node 8 = ai.forecasting)               │
│  [View Trace] [Investigate Slowness]                         │
│                                                              │
│ ─── RECENTLY COMPLETED (last 5min) ───                       │
│                                                              │
│  Run 1230 ✓ Email Campaign — 4m 12s                          │
│  Run 1229 ✓ Customer Onboarding — 1m 33s                     │
│  Run 1227 ✗ Re-engagement — failed at node 6 (DLQ)          │
│  Run 1226 ✓ Inventory Reorder — 3m 58s                       │
│                                                              │
└──────────────────────────────────────────────────────────────┘
## 40.2 Drill-Down Trace View
┌──────────────────────────────────────────────────────────────┐
│ Trace: workflow_run_id = abc123                              │
│ Workflow: Email Campaign v3                                  │
│ Duration: 4m 23s | Status: ✓ Success | Cost: 2,890 VND       │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Timeline (each row = node, width = duration):                │
│                                                              │
│ read_customers       ▓                            230ms      │
│ filter_active        ▓                            45ms       │
│ ai.generate_content     ▓▓▓▓▓▓▓▓▓▓▓▓▓             1.8s       │
│   ├─ llm_api_call        ▓▓▓▓▓▓▓▓▓▓▓▓             1.7s       │
│   └─ constraint_check    ▓                        50ms       │
│ decision.if_high_value      ▓                     12ms       │
│ action.send_email             ▓▓▓▓▓               280ms      │
│   └─ smtp_send                ▓▓▓▓▓               280ms      │
│ output.save_to_db                ▓                65ms       │
│                                                              │
│ [Export trace] [Compare to baseline] [Find similar runs]    │
└──────────────────────────────────────────────────────────────┘
## 40.3 Node Performance Heatmap
┌──────────────────────────────────────────────────────────────┐
│ Email Campaign — Node Performance (last 7 days, 1247 runs)   │
│                                                              │
│ Node             | Avg     | P95     | Failure | Retry      │
│ ──────────────── | ─────── | ─────── | ─────── | ─────      │
│ read_customers   | 230ms   | 380ms   | 0%      | 0%   ✓     │
│ filter_active    | 45ms    | 78ms    | 0%      | 0%   ✓     │
│ ai.gen_content   | 1.8s    | 4.2s    | 2.1%    | 5%   ⚠️    │
│ if_high_value    | 12ms    | 22ms    | 0%      | 0%   ✓     │
│ action.send_email| 280ms   | 1.2s ⚠️ | 1.3%    | 8%   ⚠️    │
│ output.save_db   | 65ms    | 145ms   | 0%      | 1%   ✓     │
│                                                              │
│ ⚠️ ai.gen_content P95 = 4.2s — investigate LLM latency       │
│ ⚠️ action.send_email retry rate 8% — SMTP issues?            │
│                                                              │
│ [Optimize bottleneck] [View failures]                       │
└──────────────────────────────────────────────────────────────┘

# Phần 41. Runtime Anomaly Detection
## 41.1 Anomaly Categories
runtime_anomaly_categories:
  
  performance_anomaly:
    detection: "Duration outside historical p95 + 2σ"
    examples:
      - "Workflow taking 3x longer than usual"
      - "Specific node degrading"
  
  failure_anomaly:
    detection: "Failure rate spike vs baseline"
    examples:
      - "Success rate dropped from 95% to 78% in 1 hour"
      - "Specific node started failing"
  
  cost_anomaly:
    detection: "Cost per run outside expected range"
    examples:
      - "AI cost 5x normal — runaway prompt?"
      - "DB queries 10x normal — missing index?"
  
  pattern_anomaly:
    detection: "Trace shape deviates from baseline"
    examples:
      - "Runs taking unusual paths"
      - "More retries than typical"
## 41.2 Detection Implementation
class RuntimeAnomalyDetector:
    
    def detect_workflow_anomalies(self, workflow_id, window='last_1_hour'):
        anomalies = []
        
        baseline = self.get_baseline(workflow_id, period='last_30_days')
        recent = self.get_recent_runs(workflow_id, window)
        
        if recent.success_rate < baseline.success_rate - 2 * baseline.success_rate_stddev:
            anomalies.append({
                'type': 'failure_anomaly',
                'severity': self.severity_from_diff(...),
                'baseline': baseline.success_rate,
                'recent': recent.success_rate,
                'detail': self.find_failure_causes(workflow_id, window)
            })
        
        if recent.avg_duration_ms > baseline.p95_duration_ms:
            anomalies.append({
                'type': 'performance_anomaly',
                'detail': self.find_slow_nodes(workflow_id, window)
            })
        
        if recent.avg_cost_vnd > baseline.avg_cost_vnd * 1.5:
            anomalies.append({
                'type': 'cost_anomaly',
                'detail': self.find_expensive_nodes(workflow_id, window)
            })
        
        return anomalies
    
    def detect_pattern_changes(self, workflow_id):
        """Are runs taking different paths than baseline?"""
        baseline_paths = self.get_path_distribution(workflow_id, period='last_30_days')
        recent_paths = self.get_path_distribution(workflow_id, period='last_1_day')
        
        kl_divergence = compute_kl(baseline_paths, recent_paths)
        if kl_divergence > THRESHOLD:
            return {
                'type': 'pattern_anomaly',
                'baseline': baseline_paths,
                'recent': recent_paths,
                'divergence': kl_divergence
            }
## 41.3 Anomaly Alerts
alert_routing:
  
  performance_anomaly:
    severity: WARNING
    notify: workflow_owner
    sla_response: 4 hours
  
  failure_anomaly:
    severity: ERROR
    notify: [workflow_owner, on_call_engineer]
    sla_response: 1 hour
  
  cost_anomaly:
    severity: WARNING
    notify: [tenant_admin, finance]
    sla_response: 8 hours
    auto_action: "If cost > 2x normal, halt new runs until investigation"
  
  pattern_anomaly:
    severity: INFO
    notify: workflow_owner
    sla_response: 24 hours

# PART XI — OPERATIONAL ECONOMICS (ROI ENGINE) ⭐ NEW v2.0
# Phần 42. Net Operational Value (NOV) Engine
## 42.1 Why Operational Economics Matters
Reality check: Manager Việt Nam không nói: - “Success rate tăng 12pp” - “P95 latency giảm 23%”
Manager nói: - “Cái này lợi được bao nhiêu tiền/tháng?” - “Tiết kiệm được bao nhiêu giờ làm/tuần?” - “ROI bao lâu thì hoàn vốn?”
Workflow System v2.0 nói ngôn ngữ của manager thông qua NOV Engine.
## 42.2 NOV Formula
Net Operational Value (NOV) per month =
    + Revenue Impact
    - People Cost
    - Infrastructure Cost
    - AI Call Cost
    - Opportunity Cost (if any)

NOV breakdown components:

1. Revenue Impact (+)
   = (workflow-driven revenue gain or loss prevention)
   
2. People Cost (-)
   = FTE delta × (avg salary + overhead)
   = (people freed up × salary) saved
   = OR (additional people needed × salary) added cost

3. Infrastructure Cost (-)
   = compute + storage + network
   = (cost of additional infra to run workflow)

4. AI Call Cost (-)
   = LLM calls × avg cost per call
   = forecasting calls × avg cost
   = embedding/RAG queries × cost

5. Opportunity Cost (-) [optional]
   = value of work NOT done because doing this workflow
## 42.3 NOV Schema
@dataclass
class NetOperationalValue:
    period_month: str  # "2026-04"
    workflow_id: UUID
    
    # Revenue
    revenue_impact_vnd: Decimal  # positive = gain, negative = loss
    revenue_impact_method: str  # 'pre_post_comparison', 'attribution_model', 'survey_estimated'
    revenue_impact_confidence: float  # 0-1
    
    # Costs (all positive numbers, subtracted)
    people_cost_delta_vnd: Decimal  # positive = added cost; negative = saved cost
    infrastructure_cost_vnd: Decimal
    ai_call_cost_vnd: Decimal
    opportunity_cost_vnd: Decimal
    
    # Composite
    total_cost_vnd: Decimal
    nov_vnd: Decimal  # revenue - costs
    
    # Comparison
    nov_predicted_vnd: Decimal  # what we predicted
    variance_pct: float  # (actual - predicted) / predicted
    
    # Time-based
    months_since_workflow_active: int
    cumulative_nov_vnd: Decimal  # since launch
    time_to_payback_months: float  # if applicable
## 42.4 NOV Computation Pipeline
┌──────────────────────────────────────────────────────────────┐
│ MONTHLY NOV COMPUTATION (runs first day of month)           │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 1: Aggregate Workflow Metrics                          │
│   - Executions count, success rate                           │
│   - Total runtime, retry counts                              │
│   - User interactions, manual interventions                  │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 2: Compute Revenue Impact (Phần 43)                     │
│   - Pre/post comparison (KPI movements)                      │
│   - Attribution modeling                                     │
│   - Or fallback: industry-benchmark estimation               │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 3: Compute Cost Impact (Phần 44)                        │
│   - People cost delta (FTE saved/added)                      │
│   - Infrastructure cost (compute, DB, storage)               │
│   - AI cost (actual LLM token usage)                         │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 4: Composite NOV                                        │
│   NOV = revenue - sum(costs)                                 │
│   Compare to predicted NOV → variance                        │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 5: Time-to-Payback (Phần 45)                            │
│   If cumulative NOV > setup cost → payback achieved         │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ STEP 6: Surface to ROI Dashboard (Phần 46)                   │
└──────────────────────────────────────────────────────────────┘

# Phần 43. Revenue Impact Estimation Methodology
## 43.1 Three Methodologies
revenue_estimation_methods:
  
  method_1_pre_post_comparison:
    description: "Compare KPI 30 days before vs 30 days after workflow"
    confidence: MEDIUM (correlation, not causation)
    use_when: "Workflow launched recently, simple causal chain"
    formula: |
      revenue_impact = (KPI_after - KPI_before) × revenue_per_KPI_unit × volume
    example: |
      Before workflow: avg conversion 3.2%
      After workflow: avg conversion 4.1%
      Volume: 10,000 leads/month
      Revenue per converted lead: 5M VND
      → Revenue impact = (0.041 - 0.032) × 10000 × 5M = 450M VND/month
  
  method_2_ab_attribution:
    description: "Compare workflow-affected segment vs control segment"
    confidence: HIGH (causal evidence)
    use_when: "Can split traffic; testing phase has parallel run"
    formula: |
      revenue_impact = (treatment_revenue - control_revenue) × scaling_factor
    example: |
      A/B test in TESTING phase:
      Treatment (new workflow): conversion 4.1%
      Control (old workflow): conversion 3.2%
      Difference: +0.9pp (statistically significant)
      Scaled to full population: +450M VND/month
  
  method_3_industry_benchmark:
    description: "Use industry data when own data insufficient"
    confidence: LOW (assumption-heavy)
    use_when: "New workflow, no historical data; rough estimate needed"
    formula: |
      revenue_impact = workflow_type_avg_uplift × tenant_revenue × applicability_factor
    example: |
      Email campaign workflows industry-avg uplift: 8% engagement → 1.5% revenue
      Tenant monthly revenue: 5B VND
      Applicability: 0.8 (decent fit)
      → Estimated impact: 60M VND/month (low confidence)
    note: "Use as PLACEHOLDER, refine with real data after 60 days"
## 43.2 Implementation
class RevenueImpactEstimator:
    
    def estimate_revenue_impact(self, workflow_id, month):
        workflow = self.get_workflow(workflow_id)
        
        # Try methods in order of confidence
        
        # Method 2: A/B if available (highest confidence)
        if workflow.state == 'TESTING' and workflow.has_ab_partner:
            return self.method_2_ab(workflow, month)
        
        # Method 1: Pre/post if old enough
        if workflow.months_since_active >= 2:
            return self.method_1_pre_post(workflow, month)
        
        # Method 3: Benchmark fallback
        return self.method_3_benchmark(workflow, month)
    
    def method_1_pre_post(self, workflow, month):
        affected_kpis = self.identify_affected_kpis(workflow)
        
        total_impact = 0
        for kpi in affected_kpis:
            kpi_before = self.get_kpi_average(kpi, before=workflow.activated_at, period_days=30)
            kpi_after = self.get_kpi_average(kpi, after=workflow.activated_at, period_days=30)
            
            kpi_change = kpi_after - kpi_before
            revenue_per_unit = self.lookup_revenue_per_kpi_unit(kpi, workflow.tenant_id)
            volume = self.get_kpi_volume(kpi, period='monthly')
            
            kpi_revenue_impact = kpi_change * revenue_per_unit * volume
            total_impact += kpi_revenue_impact
        
        return RevenueEstimate(
            value_vnd=total_impact,
            method='pre_post_comparison',
            confidence=0.6,
            breakdown=[...]
        )
## 43.3 KPI → Revenue Translation
common_kpi_to_revenue_mappings:
  
  marketing:
    email_open_rate:
      revenue_factor: "Each 1pp increase ≈ 0.1% revenue lift (rough)"
    click_through_rate:
      revenue_factor: "Each 1pp increase ≈ 0.5% conversion lift"
    conversion_rate:
      revenue_factor: "Direct: extra conversions × AOV"
  
  sales:
    lead_response_time:
      revenue_factor: "Each hour faster ≈ 7% better close rate"
    pipeline_velocity:
      revenue_factor: "Faster cycle = more cycles per period"
    win_rate:
      revenue_factor: "Direct: extra wins × deal size"
  
  operations:
    inventory_turnover:
      revenue_factor: "Faster = less stockout (revenue saved)"
    out_of_stock_rate:
      revenue_factor: "Each 1pp reduction ≈ 0.2-0.5% revenue saved"
  
  customer_service:
    first_response_time:
      revenue_factor: "Faster ≈ higher CSAT ≈ retention"
    resolution_time:
      revenue_factor: "Each 1h faster ≈ 0.05% retention boost"
    csat_score:
      revenue_factor: "Each 0.1 increase ≈ 1% retention"

# Phần 44. Cost Impact Modeling (People + Infra + AI)
## 44.1 People Cost Modeling
class PeopleCostEstimator:
    
    def estimate_people_cost_delta(self, workflow_id, month):
        workflow = self.get_workflow(workflow_id)
        
        # Method A: FTE saved (workflow automates manual work)
        manual_time_saved_hours = self.estimate_manual_time_saved(workflow, month)
        
        # Method B: FTE added (workflow needs human review/approval)
        manual_intervention_hours = self.actual_manual_intervention_hours(workflow_id, month)
        
        net_hours_saved = manual_time_saved_hours - manual_intervention_hours
        
        avg_hourly_cost_vnd = self.tenant_avg_hourly_cost(workflow.tenant_id, role=workflow.affected_role)
        
        return PeopleCostDelta(
            hours_saved=manual_time_saved_hours,
            hours_added=manual_intervention_hours,
            net_hours_saved=net_hours_saved,
            cost_delta_vnd=-net_hours_saved * avg_hourly_cost_vnd,  # negative = savings
            confidence=self.compute_confidence(...)
        )
    
    def estimate_manual_time_saved(self, workflow, month):
        runs = self.get_runs(workflow.id, month)
        # Each successful auto-run replaced manual work
        manual_time_per_case = workflow.metadata.estimated_manual_time_minutes
        return len(runs.successful) * manual_time_per_case / 60
## 44.2 Infrastructure Cost
class InfraCostEstimator:
    
    def estimate_infra_cost(self, workflow_id, month):
        cpu_hours = self.cpu_used(workflow_id, month)
        memory_gb_hours = self.memory_used(workflow_id, month)
        storage_gb_month = self.storage_used(workflow_id, month)
        network_gb = self.network_used(workflow_id, month)
        db_queries = self.db_queries(workflow_id, month)
        
        cost = {
            'cpu': cpu_hours * 1500,
            'memory': memory_gb_hours * 200,
            'storage': storage_gb_month * 5000,
            'network': network_gb * 1000,
            'db': db_queries * 0.5
        }
        
        return InfraCostDelta(
            total_vnd=sum(cost.values()),
            breakdown=cost,
            confidence=0.85
        )
## 44.3 AI Call Cost
class AICostEstimator:
    
    def estimate_ai_cost(self, workflow_id, month):
        ai_calls = self.get_ai_calls(workflow_id, month)
        
        total_cost = 0
        breakdown_by_type = defaultdict(int)
        breakdown_by_model = defaultdict(int)
        
        for call in ai_calls:
            cost_vnd = self.compute_call_cost(call)
            total_cost += cost_vnd
            breakdown_by_type[call.type] += cost_vnd
            breakdown_by_model[call.model] += cost_vnd
        
        return AICostDelta(
            total_vnd=total_cost,
            calls_count=len(ai_calls),
            breakdown_by_type=dict(breakdown_by_type),
            breakdown_by_model=dict(breakdown_by_model),
            avg_cost_per_call_vnd=total_cost / max(len(ai_calls), 1)
        )
## 44.4 Cost Anomaly Detection
def detect_cost_anomalies(workflow_id, month):
    current = get_total_cost(workflow_id, month)
    baseline = get_baseline_cost(workflow_id, period='last_3_months')
    
    if current > baseline.avg + 2 * baseline.stddev:
        return Anomaly(
            type='cost_spike',
            severity='WARNING',
            current=current,
            expected=baseline.avg,
            potential_causes=[
                'volume_increase',
                'ai_token_usage_growth',
                'infrastructure_inefficiency',
                'pricing_change'
            ],
            investigation_query=f"trace_query?workflow_id={workflow_id}&order=cost_desc"
        )

# Phần 45. Time-to-Payback Calculation
## 45.1 Payback Formula
Payback Time = Setup Cost / Monthly NOV

Setup Cost includes:
  - Process Mining session cost
  - Workflow build effort (days × consultant rate or FTE)
  - Training cost (people × hours × rate)
  - Initial integration setup

Monthly NOV = Revenue Impact - Total Costs (per month)
## 45.2 Implementation
class TimeToPaybackCalculator:
    
    def compute_payback(self, workflow_id):
        workflow = self.get_workflow(workflow_id)
        
        setup_cost_vnd = self.compute_setup_cost(workflow)
        
        recent_novs = self.get_recent_novs(workflow_id, months=3)
        
        if len(recent_novs) < 2:
            return PaybackResult(
                status='INSUFFICIENT_DATA',
                months_active=workflow.months_since_active
            )
        
        avg_monthly_nov = mean([nov.nov_vnd for nov in recent_novs])
        
        if avg_monthly_nov <= 0:
            return PaybackResult(
                status='NEVER_AT_CURRENT_RATE',
                avg_monthly_nov=avg_monthly_nov,
                cumulative_nov=sum([nov.nov_vnd for nov in self.all_novs(workflow_id)])
            )
        
        cumulative_nov = sum([nov.nov_vnd for nov in self.all_novs(workflow_id)])
        
        if cumulative_nov >= setup_cost_vnd:
            return PaybackResult(
                status='ACHIEVED',
                achieved_at_month=self.find_payback_month(workflow_id, setup_cost_vnd),
                cumulative_nov=cumulative_nov
            )
        
        remaining = setup_cost_vnd - cumulative_nov
        months_remaining = remaining / avg_monthly_nov
        
        return PaybackResult(
            status='PROJECTED',
            months_remaining=months_remaining,
            projected_payback_month=current_month + months_remaining,
            avg_monthly_nov=avg_monthly_nov,
            cumulative_so_far=cumulative_nov,
            setup_cost=setup_cost_vnd
        )
## 45.3 Industry Payback Benchmarks
typical_payback_periods:
  
  marketing_email_campaign: "2-6 months"
  customer_onboarding_automation: "6-12 months"
  inventory_reorder: "3-9 months"
  invoice_processing: "6-15 months"
  lead_qualification: "3-9 months"
  
  red_flag_if_payback_exceeds: "24 months"
  green_light_if_payback_under: "6 months"

# Phần 46. ROI Dashboard for Managers/CFO
## 46.1 Manager-Facing Dashboard
┌──────────────────────────────────────────────────────────────┐
│ KAORI ROI DASHBOARD — Marketing Department, April 2026       │
│                                                              │
│ Period: April 1 - 30, 2026                                   │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ─── HEADLINE NUMBERS ───                                     │
│                                                              │
│  💰 Net Operational Value: 87.3M VND  ↗ +14% vs March        │
│                                                              │
│  📊 Breakdown:                                               │
│    Revenue Impact:        +142.5M VND                        │
│    People Cost Saved:     +43.2M VND  (8.2 FTE-hours/day)    │
│    Infrastructure Cost:    -3.7M VND                         │
│    AI Call Cost:          -8.4M VND                          │
│    Opportunity Cost:      -86.3M VND                         │
│  ───────────────────────────────────                         │
│    NOV (April):           87.3M VND                          │
│                                                              │
│ ─── ACTIVE WORKFLOWS ───                                     │
│                                                              │
│  Email Campaign v3       NOV: +52M  ✓ Healthy   PB: 3 mo     │
│  Newsletter Personalize  NOV: +18M  ✓ Healthy   PB: 7 mo     │
│  Customer Onboarding     NOV: +24M  ⚠ Adoption   PB: 12 mo   │
│  Re-engagement           NOV: -7M   ❌ Negative  PB: never    │
│                                                              │
│ ─── RECOMMENDATIONS ───                                      │
│                                                              │
│  ⚠️ Re-engagement workflow: NOV negative 3 months running    │
│     → Recommended: review or deprecate                       │
│  ✓ Email Campaign v3: payback achieved month 3, accelerating│
│  📈 Customer Onboarding: adoption issues detected (PART VIII)│
│     → Schedule training: estimated NOV uplift +8M/month     │
│                                                              │
│ ─── CUMULATIVE SINCE LAUNCH ───                              │
│                                                              │
│  Cumulative NOV:          412M VND                           │
│  Setup costs:             185M VND                           │
│  Net so far:              227M VND  ✓ Positive               │
│                                                              │
│ [Export to Excel] [Share with CFO] [Drill into workflow]     │
└──────────────────────────────────────────────────────────────┘
## 46.2 CFO-Facing Summary
┌──────────────────────────────────────────────────────────────┐
│ KAORI INVESTMENT ROI — Q1 2026                               │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Total Kaori Cost Q1:                              45M VND    │
│ Total Operational Value Generated Q1:            312M VND    │
│ Net Q1:                                          267M VND    │
│ ROI Q1:                                            593%      │
│                                                              │
│ By Department:                                               │
│   Marketing:    NOV +156M  /  Cost 18M  =  ROI +767%        │
│   Sales:        NOV +98M   /  Cost 15M  =  ROI +553%        │
│   Operations:   NOV +58M   /  Cost 12M  =  ROI +383%        │
│                                                              │
│ Trend:                                                       │
│   Q4 2025:  Cumulative NOV 145M                              │
│   Q1 2026:  Cumulative NOV 412M  (+184%)                     │
│                                                              │
│ Forecast Q2 2026 (based on current trajectory):              │
│   Projected NOV: 480M-540M                                   │
│   Projected ROI: 700-800%                                    │
│                                                              │
│ Risks:                                                       │
│   • 1 workflow with negative NOV (action: review)            │
│   • LLM provider price changes possible                      │
│   • Macro economic factors affecting baseline KPIs           │
└──────────────────────────────────────────────────────────────┘

# PART XII — DOMAIN-SPECIFIC DB PARAMETERS
# Phần 47. Priority Parameters per Domain (6 domains)
## 47.1 Why Domain Parameters Matter
Mỗi phòng ban cần data fields khác nhau. Workflow templates không thể chạy nếu data thiếu fields critical. Định nghĩa parameters per domain để: - Templates pre-built knowing what fields exist - Data integration prioritized correctly - Onboarding focused on right tables first
## 47.2 Marketing Domain
marketing_essential:
  customer_email: required
  customer_phone: optional
  consent_status: required (legal)
  segment_tag: required
  lifecycle_stage: required
  last_engagement_date: required
  
marketing_priority:
  customer_lifetime_value: enables LTV-based targeting
  preferred_channel: enables channel routing
  acquisition_source: enables attribution
  product_interests: enables personalization
  
marketing_optional:
  birthday: enables birthday campaigns
  anniversary_date: enables loyalty campaigns
  social_media_handles: enables social outreach
## 47.3 Sales Domain
sales_essential:
  lead_source: required
  lead_score: required
  pipeline_stage: required
  deal_value: required
  expected_close_date: required
  owner_user_id: required
  
sales_priority:
  competitor_mentioned: useful for win-loss analysis
  decision_maker_role: useful for AI scoring
  industry: enables segment models
  company_size: enables targeting
  
sales_optional:
  technographic_data: enables tech-stack matching
  intent_signals: enables outreach timing
## 47.4 Operations Domain
operations_essential:
  product_sku: required
  current_stock_level: required (real-time)
  reorder_point: required
  supplier_id: required
  lead_time_days: required
  
operations_priority:
  storage_location: enables warehouse routing
  shelf_life_days: enables FIFO logic
  cost_per_unit: enables economic analysis
  demand_forecast: enables predictive ordering
  
operations_optional:
  alternative_suppliers: enables risk mitigation
  shipping_zones: enables logistics optimization
## 47.5 Finance Domain
finance_essential:
  invoice_number: required
  customer_id: required
  amount_vnd: required
  invoice_date: required
  due_date: required
  payment_status: required
  
finance_priority:
  payment_terms: enables AR collection
  payment_method: enables routing
  currency_code: enables multi-currency (if applicable)
  tax_amount: enables tax compliance
  
finance_optional:
  cost_center: enables departmental allocation
  project_code: enables project profitability
## 47.6 HR Domain
hr_essential:
  employee_id: required
  employee_name: required
  department: required
  position: required
  hire_date: required
  status: required (active/inactive)
  
hr_priority:
  manager_id: enables org chart
  performance_score: enables performance management
  skills: enables matching
  certifications: enables compliance tracking
  
hr_optional:
  salary_band: enables compensation analysis
  exit_reason: enables retention insights
## 47.7 Customer Service Domain
cs_essential:
  ticket_id: required
  customer_id: required
  issue_category: required
  priority: required
  status: required
  created_at: required
  
cs_priority:
  assigned_agent: enables routing
  resolution_time_minutes: enables SLA tracking
  customer_satisfaction_score: enables CSAT analysis
  product_affected: enables product feedback loop
  
cs_optional:
  related_tickets: enables pattern detection
  escalation_history: enables training

# Phần 48. Schema Validation in Workflow Deployment
## 48.1 Pre-Deployment Schema Check
class WorkflowSchemaValidator:
    
    def validate_before_deploy(self, workflow, tenant_id):
        results = []
        
        # For each data input node, verify required fields exist
        for node in workflow.nodes:
            if node.type.startswith('data_input.'):
                required_fields = node.config.get('required_fields', [])
                table = node.config.table
                
                missing = self.find_missing_fields(tenant_id, table, required_fields)
                if missing:
                    results.append({
                        'severity': 'ERROR',
                        'node_id': node.id,
                        'message': f"Required fields missing in {table}: {missing}",
                        'fix_suggestion': self.suggest_fix(tenant_id, table, missing)
                    })
        
        # For each AI node, verify training data sufficient
        for node in workflow.nodes:
            if node.category == 'ai':
                required_volume = node.config.get('min_training_volume', 100)
                actual_volume = self.get_data_volume(tenant_id, node)
                if actual_volume < required_volume:
                    results.append({
                        'severity': 'WARNING',
                        'node_id': node.id,
                        'message': f"Insufficient data: {actual_volume} records (recommended: {required_volume})"
                    })
        
        return results
    
    def suggest_fix(self, tenant_id, table, missing_fields):
        for field in missing_fields:
            sample_values = self.search_other_tables_for_field(tenant_id, field)
            if sample_values:
                return f"Field '{field}' may be in: {sample_values}"
            
            return f"Field '{field}' not found. Suggest: 1) Add to {table}, or 2) Use manual entry, or 3) Skip if optional"

# PART XIII — PRICING & SECURITY
# Phần 49. Workflow Quotas per Plan
## 49.1 Plan Tiers (cập nhật v2.0)
plans:
  
  PILOT (free trial):
    max_workflows: 3
    max_nodes_per_workflow: 10
    max_executions_per_month: 1000
    ai_node_access: NO
    process_mining: NO
    integrations: 2 sources
    duration: 30 days
    support: community only
  
  BASIC (3M VND/month):
    max_workflows: 10
    max_nodes_per_workflow: 25
    max_executions_per_month: 10,000
    ai_node_access: YES (limited: 100 AI calls/day)
    process_mining: NO
    integrations: 5 sources
    runtime_features: idempotency only
    observability: basic metrics
    operational_economics: basic NOV
    adoption_intelligence: basic signals
    support: email, 48h SLA
  
  MID (10M VND/month):
    max_workflows: 50
    max_nodes_per_workflow: 100
    max_executions_per_month: 100,000
    ai_node_access: YES (1000 AI calls/day)
    process_mining: YES (basic — 5 sources)
    integrations: 15 sources
    runtime_features: idempotency + saga + DLQ + retry
    observability: distributed tracing
    operational_economics: full NOV + payback
    adoption_intelligence: full signal catalog
    support: email + chat, 24h SLA
  
  MAX (25M VND/month):
    max_workflows: unlimited
    max_nodes_per_workflow: unlimited
    max_executions_per_month: unlimited
    ai_node_access: YES (unlimited within fair use)
    process_mining: YES (full — all 8 source types)
    integrations: all
    runtime_features: full (idempotency + saga + DLQ + exactly-once)
    observability: full + ai-powered anomaly detection
    operational_economics: full + custom KPI mappings
    adoption_intelligence: full + custom signals
    support: dedicated CSM, 4h SLA
    advanced_features: workflow as code, multi-tenant management, custom integrations
## 49.2 Quota Enforcement
class QuotaEnforcer:
    
    def can_create_workflow(self, tenant_id):
        plan = self.get_plan(tenant_id)
        current_count = self.count_workflows(tenant_id)
        if current_count >= plan.max_workflows:
            return False, f"Plan {plan.name} allows {plan.max_workflows} workflows. Upgrade to add more."
        return True, None
    
    def can_execute_workflow(self, tenant_id):
        plan = self.get_plan(tenant_id)
        executions_this_month = self.count_executions(tenant_id, period='month')
        if executions_this_month >= plan.max_executions_per_month:
            return False, "Monthly execution quota exceeded."
        return True, None
    
    def can_use_ai_node(self, tenant_id):
        plan = self.get_plan(tenant_id)
        if not plan.ai_node_access:
            return False, "AI nodes not available on your plan."
        ai_calls_today = self.count_ai_calls(tenant_id, period='today')
        if ai_calls_today >= plan.ai_calls_per_day:
            return False, "Daily AI quota exceeded."
        return True, None

# Phần 50. Feature Gates per Tier
feature_gates:
  
  process_mining:
    available_on: [MID, MAX]
    explanation: "Workflow Discovery requires advanced AI capabilities"
    
  saga_pattern:
    available_on: [MID, MAX]
    explanation: "Saga rollback for irreversible operations"
    
  distributed_tracing:
    available_on: [MID, MAX]
    explanation: "Per-run trace + span analytics"
    
  workflow_as_code:
    available_on: [MAX]
    explanation: "YAML import/export + CI/CD integration"
    
  custom_integrations:
    available_on: [MAX]
    explanation: "Build your own connectors"
    
  multi_tenant_admin:
    available_on: [MAX]
    explanation: "For agencies managing multiple tenants"

# Phần 51. Multi-Tenancy Security ⭐ NEW v2.0
## 51.1 Threat Model
threats:
  
  threat_1_cross_tenant_data_leak:
    description: "Tenant A workflow accidentally reads Tenant B data"
    severity: CRITICAL
    mitigation: row-level security + tenant context propagation
  
  threat_2_compute_resource_abuse:
    description: "One tenant's runaway workflow consumes all CPU"
    severity: HIGH
    mitigation: per-tenant resource quotas
  
  threat_3_ai_cost_attack:
    description: "Malicious tenant runs expensive AI nodes to inflate bill"
    severity: MEDIUM
    mitigation: rate limits + cost caps + alerts
  
  threat_4_workflow_injection:
    description: "Tenant A's workflow somehow triggers in Tenant B's context"
    severity: CRITICAL
    mitigation: tenant_id verification at every layer
  
  threat_5_secret_exposure:
    description: "Tenant A's secrets exposed to Tenant B"
    severity: CRITICAL
    mitigation: per-tenant secret namespaces, never inline
## 51.2 Isolation Layers
┌──────────────────────────────────────────────────────────────┐
│ LAYER 1: NETWORK ISOLATION                                   │
│   - Tenant subdomain (tenant_a.kaori.app)                    │
│   - JWT with tenant_id claim                                 │
│   - API gateway validates tenant_id                          │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 2: APPLICATION ISOLATION                               │
│   - Every request carries tenant_id (verified)               │
│   - All queries filter by tenant_id automatically            │
│   - Workflow engine sets tenant context per execution        │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 3: DATABASE ISOLATION                                  │
│   - Postgres Row-Level Security (RLS) policies               │
│   - SET app.current_tenant_id = '<tenant_uuid>' per session  │
│   - Policy: WHERE tenant_id = current_setting(...)           │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 4: STORAGE ISOLATION                                   │
│   - S3/MinIO bucket prefix per tenant                        │
│   - IAM policies enforce prefix access                       │
│   - File paths include tenant_id                             │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ LAYER 5: COMPUTE ISOLATION                                   │
│   - Kubernetes namespace per tenant (large customers)        │
│   - Resource quotas per namespace                            │
│   - Network policies prevent cross-namespace                 │
└──────────────────────────────────────────────────────────────┘
## 51.3 Row-Level Security Implementation
-- Every tenant-scoped table has RLS

ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;

CREATE POLICY tenant_isolation ON workflows
  USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Application connects with non-superuser role
CREATE ROLE kaori_app NOLOGIN;
GRANT SELECT, INSERT, UPDATE ON workflows TO kaori_app;

-- Per-request: SET tenant context
-- Done in connection middleware:
SET app.current_tenant_id = '<verified_tenant_id_from_jwt>';

-- Now ALL queries auto-filter by this tenant_id
## 51.4 Cross-Tenant Leak Testing
class CrossTenantLeakTest:
    """Run regularly to detect any leak."""
    
    def test_no_data_leak(self):
        # Setup: Two test tenants with distinct data
        tenant_a = create_test_tenant('A', test_data='alpha')
        tenant_b = create_test_tenant('B', test_data='beta')
        
        # Test 1: Tenant A login can only see A's data
        with set_tenant_context(tenant_a):
            workflows = query_workflows()
            assert all(w.tenant_id == tenant_a.id for w in workflows)
        
        # Test 2: Direct DB access without tenant context fails
        with set_tenant_context(None):
            with pytest.raises(NoTenantSetError):
                query_workflows()
        
        # Test 3: Tenant A workflow execution cannot read B's data
        a_workflow = create_workflow(tenant_a, reads_from='customers')
        execute_workflow(a_workflow)
        executed_data = get_workflow_run_data(a_workflow.last_run)
        assert all(d.tenant_id == tenant_a.id for d in executed_data)
        
        # Test 4: Process Mining session of A doesn't include B's events
        mining_session = run_process_mining(tenant_a)
        assert all(e.tenant_id == tenant_a.id for e in mining_session.events)
## 51.5 Acceptance Criteria — Phần 51
☐ All 5 isolation layers implemented
☐ RLS policies on every tenant-scoped table
☐ Cross-tenant leak tests in CI/CD
☐ Audit log for every cross-tenant attempt (should be 0)
☐ Penetration testing annually

# Phần 52. Workflow Secrets Management ⭐ NEW v2.0
## 52.1 What Secrets Workflows Need
common_workflow_secrets:
  
  api_keys:
    - SendGrid API key (email)
    - Twilio API key (SMS)
    - Slack bot token
    - Zalo Business API key
    - OpenAI/Anthropic API key (if user-provided)
  
  oauth_tokens:
    - Google OAuth refresh token (Gmail, Calendar, Drive)
    - Salesforce OAuth token
    - HubSpot OAuth token
  
  database_credentials:
    - External DB connection strings
    - Read-only credentials for source systems
  
  signing_keys:
    - Webhook signature keys
    - JWT signing keys for outgoing requests
  
  encryption_keys:
    - Data-at-rest keys for PII fields
## 52.2 Architecture: Secrets NEVER Inline
golden_rule:
  "Secrets are NEVER stored inline in workflow definitions."
  "Workflows reference secrets by name. Resolution happens at execution time."
# WRONG ❌
node:
  type: action.send_email
  config:
    api_key: "SG.actualkey..."  # NEVER

# RIGHT ✓
node:
  type: action.send_email
  config:
    api_key_secret_ref: "tenant_abc/sendgrid_api_key"
    # At runtime, resolved from vault
## 52.3 Secrets Vault
┌──────────────────────────────────────────────────────────────┐
│ SECRETS VAULT (HashiCorp Vault or AWS Secrets Manager)       │
│                                                              │
│ Path structure:                                              │
│   /tenant/{tenant_id}/                                       │
│     ├─ sendgrid_api_key                                      │
│     ├─ twilio_api_key                                        │
│     ├─ google_oauth_refresh_token                            │
│     └─ ...                                                   │
│                                                              │
│ Access control:                                              │
│   - Workflow execution role has SCOPED read access           │
│   - Only secrets for workflow's tenant readable              │
│   - All reads logged                                         │
└──────────────────────────────────────────────────────────────┘
## 52.4 Secret Rotation Policy
rotation_policy:
  
  api_keys:
    rotation_interval: 90 days
    notification: 14 days before
    auto_rotation: yes (where provider supports)
    fallback: dual-key during transition
  
  oauth_tokens:
    refresh_interval: per_token_TTL (typically 1 hour)
    auto_refresh: yes
  
  encryption_keys:
    rotation_interval: 365 days
    process: re-encrypt data with new key
    versioning: keep old keys for decryption only
## 52.5 Secret Audit Logging
class SecretAuditLogger:
    
    def log_secret_access(self, secret_path, accessor, reason):
        log_entry = {
            'timestamp': now(),
            'secret_path': secret_path,
            'accessor': accessor,  # workflow_run_id or user_id
            'reason': reason,  # 'workflow_execution' or 'admin_view'
            'tenant_id': extract_tenant(secret_path),
            'success': True
        }
        self.audit_store.write(log_entry)
        
        if self.is_anomalous_access(log_entry):
            alert_security_team(log_entry)
    
    def is_anomalous_access(self, entry):
        # Outside business hours?
        # Unusual frequency?
        # Different geographic region?
        return self.anomaly_detector.score(entry) > THRESHOLD
## 52.6 Acceptance Criteria — Phần 52
☐ All workflow definitions use secret_ref, never inline
☐ Vault integrated (HashiCorp Vault or equivalent)
☐ Per-tenant namespace in vault
☐ Rotation policy documented + tested
☐ Audit log for all secret accesses
☐ CI/CD scans for inline secret leaks

# PART XIV — RISKS & MITIGATIONS
# Phần 53. Usability Risks (8)
usability_risks:
  
  R-U-1_complexity_overwhelm:
    risk: "User overwhelmed by 45 node types"
    severity: HIGH
    mitigation:
      - Templates as starting point (Phần 17)
      - Progressive disclosure (show only relevant nodes per role)
      - "Recommended for you" based on department
      - Phase 1: 25 nodes only (cut 45 → 25)
  
  R-U-2_validation_friction:
    risk: "Validation errors confusing, user gives up"
    severity: MEDIUM
    mitigation:
      - Plain language errors (Vietnamese)
      - Auto-fix suggestions (Phần 18)
      - One-click fixes where possible
  
  R-U-3_no_idea_what_workflow_to_build:
    risk: "Blank canvas paralysis"
    severity: HIGH
    mitigation:
      - Process Mining auto-generates baseline (PART IV) ⭐ v2.0
      - Templates per industry/department
      - Onboarding wizard suggests workflows
  
  R-U-4_can_not_test_safely:
    risk: "User afraid to test, might break production"
    severity: MEDIUM
    mitigation:
      - "Test Run" button uses sandbox data
      - 90-day TESTING phase parallel-run model
      - Rollback always available
  
  R-U-5_unclear_what_changed:
    risk: "User confused after AI suggests changes"
    severity: MEDIUM
    mitigation:
      - Visual diff between versions
      - "Why this change?" explanations
      - Better/Worse comparison framework (Phần 25)
  
  R-U-6_zalo_user_resistance:
    risk: "Zalo-native users prefer chat over UI"
    severity: HIGH (Vietnam-specific)
    mitigation:
      - Zalo bot interface for common workflow actions
      - Approve/reject via Zalo
      - Mobile-first UI
  
  R-U-7_excel_user_resistance:
    risk: "Excel-native users export everything"
    severity: HIGH (Vietnam-specific)
    mitigation:
      - Excel-like data views
      - Bidirectional Excel sync (read AND write)
      - Don't fight it; embrace it
  
  R-U-8_role_uncertainty:
    risk: "Don't know which features I have access to"
    severity: LOW
    mitigation:
      - Clear permission display
      - Contextual help

# Phần 54. Technical Risks (10)
technical_risks:
  
  R-T-1_workflow_runtime_failures:
    risk: "Critical workflow fails silently"
    severity: HIGH
    mitigation:
      - Distributed tracing (PART X)
      - Real-time alerting on failures
      - Saga rollback (Phần 34)
      - DLQ + replay (Phần 35)
  
  R-T-2_cascading_failures:
    risk: "One workflow's failure breaks others"
    severity: HIGH
    mitigation:
      - Dependency graph (Phần 24)
      - Circuit breakers
      - Bulkheads (resource isolation per workflow)
  
  R-T-3_schema_change_breaks_workflows:
    risk: "Source schema change → workflow broken"
    severity: HIGH
    mitigation:
      - Schema awareness (Phần 19)
      - Auto-detection of breaking changes
      - Compatibility layer (column rename mapping)
  
  R-T-4_ai_model_degradation:
    risk: "LLM update changes output → workflow expectations off"
    severity: HIGH
    mitigation:
      - LLM version pinning (Phần 21) ⭐ v2.0
      - Drift detection
      - Controlled upgrade process
  
  R-T-5_cost_runaway:
    risk: "Infinite loop or runaway prompt → bill shock"
    severity: HIGH
    mitigation:
      - Cost caps per workflow run
      - Cost caps per tenant per day
      - Anomaly detection (Phần 41)
      - Auto-halt on cost spike
  
  R-T-6_data_volume_overwhelm:
    risk: "Workflow processes 1M records, takes hours"
    severity: MEDIUM
    mitigation:
      - Batching at sensible sizes
      - Background execution for long-running
      - Pagination + checkpointing (Phần 36)
  
  R-T-7_external_api_changes:
    risk: "Salesforce API breaking change"
    severity: MEDIUM
    mitigation:
      - Connector versioning
      - Provider monitoring
      - Multiple connector versions supported simultaneously
  
  R-T-8_database_growth:
    risk: "Workflow execution metrics fill DB"
    severity: MEDIUM
    mitigation:
      - Partitioning by date
      - ClickHouse for analytics (not Postgres)
      - Retention policies (90 days hot, archive cold)
  
  R-T-9_cross_tenant_leak:
    risk: "Tenant A sees Tenant B data"
    severity: CRITICAL
    mitigation:
      - 5-layer isolation (Phần 51) ⭐ v2.0
      - Continuous testing
      - Immediate revocation on detection
  
  R-T-10_secret_exposure:
    risk: "API key leaked in logs/exports"
    severity: CRITICAL
    mitigation:
      - Secrets never inline (Phần 52) ⭐ v2.0
      - Log redaction filters
      - Audit on every secret access

# Phần 55. Business Risks (8)
business_risks:
  
  R-B-1_low_adoption:
    risk: "Customers buy but don't use"
    severity: HIGH
    mitigation:
      - Adoption Intelligence (PART VIII) ⭐ v2.0
      - CSM proactive engagement
      - Process Mining lowers activation friction (PART IV)
  
  R-B-2_no_demonstrable_roi:
    risk: "Customer cancels, can't prove value"
    severity: HIGH
    mitigation:
      - NOV Engine (PART XI) ⭐ v2.0
      - Monthly ROI dashboard for CFO
      - Case studies + benchmarks
  
  R-B-3_pricing_misalignment:
    risk: "Customer pays more than value received"
    severity: MEDIUM
    mitigation:
      - Tier audit per customer quarterly
      - Right-size recommendations
      - Free tier downgrade path
  
  R-B-4_competition_from_celonis_etc:
    risk: "Enterprise PM vendor enters SME market"
    severity: MEDIUM
    mitigation:
      - SME-specific pricing
      - Vietnam-specific features (Zalo, Misa, Vietnamese ERP)
      - Iterative transformation philosophy as differentiator
  
  R-B-5_customer_data_breach:
    risk: "Breach → reputational damage"
    severity: CRITICAL
    mitigation:
      - Multi-tenancy security (Phần 51)
      - Secrets management (Phần 52)
      - Annual penetration testing
      - Cyber insurance
  
  R-B-6_legal_compliance_gaps:
    risk: "PDPL violations from data handling"
    severity: HIGH
    mitigation:
      - Privacy by design in Process Mining (Phần 11)
      - Consent management
      - Data residency (Vietnam)
      - DPA agreements
  
  R-B-7_implementation_delays:
    risk: "Team can't ship Phase 1 in 4 months"
    severity: HIGH
    mitigation:
      - Phase 1 scope cut tighter (Phần 61) ⭐ v2.0
      - Buffer for unknowns
      - Phased rollout
  
  R-B-8_team_burnout:
    risk: "Ambitious roadmap exhausts team"
    severity: MEDIUM
    mitigation:
      - Realistic milestones
      - Hire ahead of need
      - Defer Phase 2-3 if Phase 1 strained

# Phần 56. Migration Risks (5)
migration_risks:
  
  R-M-1_data_quality_issues:
    risk: "Customer's existing data dirty → workflows misfire"
    severity: HIGH
    mitigation:
      - Pipeline data quality layer first (Pipeline doc)
      - Data quality dashboard surfacing issues
      - Workflows fail-safe on bad data
  
  R-M-2_existing_workflow_replacement:
    risk: "Replacing established Excel/Zalo flows is hard"
    severity: HIGH
    mitigation:
      - Process Mining shows actual flow first
      - 60-90 day iterative replacement
      - Don't fight Zalo/Excel — integrate
  
  R-M-3_change_management_failure:
    risk: "People resist new system"
    severity: HIGH
    mitigation:
      - Adoption Intelligence + CSM intervention (PART VIII)
      - Champion model (1 person per dept)
      - Training programs
  
  R-M-4_integration_complexity:
    risk: "Customer's existing tools (Misa, Fast, etc) hard to integrate"
    severity: MEDIUM
    mitigation:
      - Pre-built Vietnam ERP connectors
      - File-based fallback (Excel imports)
      - Phased integration approach
  
  R-M-5_organizational_inertia:
    risk: "Manager not committed → adoption fails"
    severity: HIGH
    mitigation:
      - Executive sponsor required for sale
      - ROI dashboard (PART XI) keeps them engaged
      - Quick wins in 30/60/90 days

# Phần 57. Adoption Risks (Summary)
See PART VIII for full adoption intelligence framework. Summary risks:
adoption_risks_summary:
  
  R-A-1_workflow_abandonment:
    detection: signal_1 (Phần 28)
    intervention: simplify UI, add inline help (Phần 31)
  
  R-A-2_excessive_overrides:
    detection: signal_2
    intervention: improve AI quality, add explainability
  
  R-A-3_side_channel_communication:
    detection: signal_5 (CRITICAL for Vietnam)
    intervention: Zalo integration, manager surfacing
  
  R-A-4_workaround_proliferation:
    detection: signal_6
    intervention: feature gap analysis, missing-feature roadmap
  
  R-A-5_role_specific_avoidance:
    detection: signal_8
    intervention: role-specific UX redesign

# PART XV — PLATFORM-SIDE MONITORING
# Phần 58. Customer Success Dashboard
## 58.1 Per-Customer View
┌──────────────────────────────────────────────────────────────┐
│ CUSTOMER: ABC Retail (BASIC plan)                            │
│ CSM: Nguyen Van A | Onboarded: 2025-11-15                    │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ ─── HEALTH OVERVIEW ───                                      │
│  Adoption Score: 72/100 (HEALTHY) ↘ -5 last 14 days  ⚠️      │
│  ROI Score: ✓ Positive (NOV +47M VND/month)                  │
│  Payback: ✓ Achieved month 4                                 │
│  Renewal Risk: LOW                                           │
│                                                              │
│ ─── ACTIVE WORKFLOWS (8) ───                                 │
│  Email Campaign v3        ✓ EXCELLENT                        │
│  Newsletter Personalize   ✓ HEALTHY                          │
│  Customer Onboarding     ⚠️ AT_RISK (override rate ↑)        │
│  Inventory Reorder        ✓ HEALTHY                          │
│  Lead Scoring             ✓ HEALTHY                          │
│  Re-engagement           ❗ STRUGGLING                        │
│  Quote Generation         ✓ HEALTHY                          │
│  Daily Report             ✓ HEALTHY                          │
│                                                              │
│ ─── ATTENTION ITEMS ───                                      │
│  ⚠️ Re-engagement: NOV negative 2 months running             │
│      → Suggest deprecation OR redesign                       │
│  ⚠️ Customer Onboarding: override rate 32%                   │
│      → Schedule training session                             │
│                                                              │
│ ─── RECENT ACTIVITY ───                                      │
│  Workflow runs (last 7d): 1247                               │
│  AI calls (last 7d): 423                                     │
│  Cost (last 7d): 87,500 VND                                  │
│  Insights surfaced (last 7d): 23                             │
│                                                              │
│ ─── UPCOMING ───                                             │
│  Day 60 review for Re-engagement: 3 days away                │
│  Quarterly business review: 12 days away                     │
│                                                              │
│ [Schedule call] [View workflows] [Export ROI report]         │
└──────────────────────────────────────────────────────────────┘
## 58.2 Customer Cohort View (Internal Kaori Team)
┌──────────────────────────────────────────────────────────────┐
│ KAORI CUSTOMER PORTFOLIO — May 2026                          │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│ Total customers: 42                                          │
│ MRR: 287M VND                                                │
│                                                              │
│ ─── BY HEALTH STATUS ───                                     │
│  EXCELLENT:  8 customers  (19%)                              │
│  HEALTHY:   23 customers  (55%)                              │
│  AT_RISK:    7 customers  (17%)                              │
│  STRUGGLING: 3 customers  (7%)                               │
│  CRITICAL:   1 customer   (2%)  ← URGENT                     │
│                                                              │
│ ─── BY PLAN ───                                              │
│  PILOT:  5  (warming up)                                     │
│  BASIC: 22  (most common)                                    │
│  MID:   12                                                   │
│  MAX:    3  (whales)                                         │
│                                                              │
│ ─── ATTENTION REQUIRED ───                                   │
│                                                              │
│ ❗ XYZ Manufacturing — CRITICAL                               │
│   - Adoption score 38                                        │
│   - 3 workflows abandoned                                    │
│   - No CSM contact in 21 days                                │
│   - URGENT: Schedule recovery call                           │
│                                                              │
│ ⚠️ DEF Retail — STRUGGLING (renewal in 45 days)              │
│   - Adoption score 47, declining                             │
│   - ROI marginal (NOV +5M, costs 8M)                         │
│   - Consider: training session + workflow redesign           │
│                                                              │
│ [Drill into customer] [Schedule reviews] [Export]            │
└──────────────────────────────────────────────────────────────┘

# Phần 59. Proactive Engagement Triggers
## 59.1 7 Engagement Triggers
engagement_triggers:
  
  trigger_1_adoption_decline:
    condition: "Adoption score drops > 10 points in 14 days"
    action: "CSM contacts within 48h"
    template: "adoption_check_in"
  
  trigger_2_workflow_in_critical_state:
    condition: "Any workflow scores STRUGGLING for 14+ days"
    action: "CSM proposes workshop"
    template: "workflow_optimization_offer"
  
  trigger_3_negative_nov:
    condition: "Cumulative NOV negative for 3 months"
    action: "Account manager review"
    template: "value_alignment_call"
  
  trigger_4_quota_approaching:
    condition: "80%+ of plan quota used by mid-month"
    action: "Suggest upgrade"
    template: "tier_upgrade_offer"
  
  trigger_5_user_complaint:
    condition: "Support ticket with negative sentiment"
    action: "CSM follows up beyond support team"
    template: "satisfaction_check"
  
  trigger_6_renewal_approaching:
    condition: "60 days before renewal"
    action: "Schedule QBR (quarterly business review)"
    template: "qbr_invitation"
  
  trigger_7_milestone_achievement:
    condition: "Payback achieved OR major NOV milestone"
    action: "Celebrate + cross-sell"
    template: "success_celebration"
## 59.2 Implementation
class EngagementTriggerEngine:
    
    def evaluate_triggers_daily(self):
        for tenant in self.get_active_tenants():
            triggers_fired = []
            
            for trigger_name, trigger_config in TRIGGERS.items():
                if self.evaluate_trigger(tenant, trigger_config):
                    triggers_fired.append(trigger_name)
                    
                    self.create_csm_task(
                        tenant=tenant,
                        trigger=trigger_name,
                        sla=trigger_config.sla,
                        template=trigger_config.template
                    )
            
            if triggers_fired:
                self.notify_csm(tenant, triggers_fired)

# PART XVI — IMPLEMENTATION
# Phần 60. Tech Stack
## 60.1 Core Components
tech_stack:
  
  workflow_engine:
    language: Python 3.11+ (FastAPI for API)
    orchestration: Temporal.io (for reliable execution + saga + retries)
    queue: Redis Streams (for events)
    state_store: PostgreSQL (workflow state, idempotency)
  
  ui:
    framework: React + TypeScript
    drag_drop: React Flow library
    state: Redux Toolkit
    real_time: WebSocket for live execution view
  
  data:
    operational_db: PostgreSQL 15+ (with row-level security)
    analytics_db: ClickHouse (for trace analytics, time-series)
    object_storage: MinIO (S3-compatible) — Vietnam region
    cache: Redis 7
    secrets: HashiCorp Vault
  
  ai:
    llm_primary: Anthropic Claude (via API)
    llm_fallback: OpenAI GPT
    embedding: sentence-transformers + Pinecone
    formula_validation: SymPy + Z3
  
  process_mining:
    library: PM4Py (Python process mining toolkit)
    custom_extensions: Vietnamese context (Zalo, Misa, Fast connectors)
  
  observability:
    tracing: OpenTelemetry → Jaeger
    metrics: Prometheus + Grafana
    logs: Loki
    apm: Sentry
  
  infrastructure:
    container: Docker
    orchestration: Kubernetes (EKS or local K8s)
    ci_cd: GitHub Actions
    iac: Terraform
  
  monitoring:
    uptime: BetterUptime / Healthchecks.io
    alerts: PagerDuty
    on_call: PagerDuty rotations
## 60.2 Vietnam-Specific Components
vietnam_specific:
  
  zalo_integration:
    library: Zalo Business API SDK
    use_for: messaging, approvals, notifications
  
  vietnamese_erp_connectors:
    - Misa (ASP / Standalone)
    - Fast Accounting
    - Bravo
    - Effect
    - Smart-eOffice
  
  payment_integration:
    - VNPAY
    - MoMo
    - ZaloPay
    - Banks (via APIs)
  
  hosting:
    primary: Vietnam-based provider (FPT, Viettel IDC, VNPT)
    reason: data residency + latency

# Phần 61. Phase Scope (REVISED — much tighter than v1) ⭐ v2.0
## 61.1 Critical Insight from ChatGPT Review
“Bạn đang dần tiến tới ServiceNow + Celonis + Monday + Notion + AI consultant + Process mining + Transformation OS — trong một system. Phase 1 vẫn hơi lớn.”
Response: Aggressive scope cut applied to v2.0.
## 61.2 Phase 1 — TIGHTENED (4 months)
phase_1_scope_v2:
  
  duration: 4 months
  team: 6-8 engineers + 1 PM + 1 designer + 1 CSM
  
  MUST_HAVE:
    
    workflow_builder:
      - drag_drop_canvas: yes (basic, single-user editing)
      - node_types: 25 (cut from 45)
      - templates: 15 (cut from 40, focus on 4 departments not 6)
      - validation: basic structural + semantic
    
    workflow_runtime:
      - execution_engine: Temporal-based
      - idempotency: yes (Phần 32) ⭐ critical
      - retry_with_backoff: yes (Phần 33) ⭐ critical
      - dead_letter_queue: yes (Phần 35) ⭐ critical
      - distributed_tracing: basic (OpenTelemetry → Jaeger)
      - 60_day_monitoring: yes
    
    process_mining_v1:
      - source_types: 3 (DB log, Excel, Zalo only)
      - sequence_reconstruction: heuristic miner
      - off_system_step_detection: yes
      - bottleneck_detection: basic
      - NOT_INCLUDED: bypass risk scoring (Phase 2)
      - NOT_INCLUDED: shadow process detection (Phase 2)
    
    ai_integration:
      - 5 essential AI nodes (insight, narrative, classify, recommendation, RAG)
      - llm_version_pinning: yes (Phần 21) ⭐ critical
      - cost_caps: yes
      - NOT_INCLUDED: 8 AI node types (defer 3 to Phase 2)
    
    adoption_intelligence_basic:
      - track 5 of 9 signals (abandonment, override, side-channel, manual export, complaints)
      - basic adoption health score
      - YELLOW/RED alert to CSM
      - NOT_INCLUDED: full intervention playbook (Phase 1.5)
    
    operational_economics_basic:
      - revenue impact (method 1: pre/post comparison)
      - people cost (manual time saved)
      - infra + AI cost tracking
      - NOV calculation
      - basic ROI dashboard
      - NOT_INCLUDED: A/B attribution (Phase 1.5)
      - NOT_INCLUDED: time-to-payback projection (Phase 1.5)
    
    multi_tenancy_security:
      - row_level_security: yes ⭐ critical
      - tenant_isolation_tests: in CI/CD
      - secrets_vault_integration: yes ⭐ critical
    
    pricing_tier_enforcement:
      - quota_limits per plan
      - feature_gates
    
    workflow_versioning:
      - version on each change
      - diff visualization
      - rollback support
  
  CUT_FROM_PHASE_1:
    - 90_day_parallel_testing: defer to Phase 1.5
    - process_mining_full: defer to Phase 2
    - simulation_engine: defer to Phase 2
    - multi_user_collaboration: defer to Phase 2
    - workflow_marketplace: defer to Phase 3
    - federated_workflows: defer to Phase 3
    - workflow_as_code: defer to Phase 2 (MAX plan)
    - multi_agent_orchestration: defer to Phase 2-3
    - workflow_ontology: defer to Phase 3
    - strategic_okr_mapping: defer to Phase 2
    - 8_ai_node_types_full: 5 in Phase 1, others Phase 2
## 61.3 Phase 1.5 — STABILIZATION (2 months)
phase_1_5:
  duration: months 5-6
  focus: stabilize Phase 1 + add critical missing pieces
  
  additions:
    - 90_day_parallel_testing: full
    - adoption_intelligence: full 9 signals + full intervention playbook
    - operational_economics: A/B attribution method
    - process_mining: 5 source types (add email, calendar)
    - 3 more AI node types (forecasting, risk_detection, extract_entities)
    - 10 more templates
    - shadow_process_detection
    - bypass_risk_scoring
## 61.4 Phase 2 — DIFFERENTIATION (6 months)
phase_2:
  duration: months 7-12
  focus: moat features
  
  major_additions:
    - process_mining_full: 8 source types, full algorithms
    - simulation_engine: pre-deployment what-if
    - multi_user_collaboration: real-time editing
    - workflow_as_code: YAML import/export, CI/CD
    - organizational_memory_graph: cross-workflow causal graph
    - workflow_ontology: semantic layer
    - strategic_okr_mapping: workflows ↔ company OKRs
    - 45 node types complete
    - 40 templates
    - exactly_once_semantics: opt-in
    - custom_integrations: tenant-built connectors
## 61.5 Phase 3 — PLATFORM (Year 2)
phase_3:
  duration: months 13-24
  focus: platform + ecosystem
  
  additions:
    - multi_agent_orchestration
    - workflow_marketplace
    - federated_workflows (cross-tenant)
    - white_label_option
    - regional_expansion (SEA)
    - advanced_simulation
    - ai_agent_assistants

# Phần 62. Quality KPIs
## 62.1 Engineering KPIs
engineering_kpis:
  
  reliability:
    workflow_success_rate: > 99.5%
    api_uptime: > 99.9%
    deployment_frequency: weekly
    mean_time_to_recovery: < 1 hour
  
  performance:
    workflow_run_p95_latency: < 5 minutes
    api_response_p95_latency: < 200ms
    builder_canvas_fps: > 30fps
  
  cost:
    cost_per_workflow_run: track + monthly review
    ai_cost_per_tenant: track + alert on anomaly
    infrastructure_cost_per_tenant: track quarterly
  
  security:
    cross_tenant_leaks: 0 (target)
    secret_exposure_incidents: 0 (target)
    penetration_test_findings: < 5 medium per year
  
  observability:
    workflows_traced: 100%
    alert_response_time: < 5 minutes
    mttr_for_p1_incidents: < 1 hour
## 62.2 Product KPIs
product_kpis:
  
  adoption:
    active_workflows_per_tenant: > 5 (target)
    workflow_executions_per_user_per_week: > 10 (target)
    user_engagement_with_insights: > 50% view rate
  
  retention:
    monthly_churn: < 2% (target)
    NPS: > 50 (target)
    customer_lifetime_value: track quarterly
  
  outcomes:
    avg_NOV_per_tenant: > 50M VND/month
    avg_payback_time: < 12 months
    customers_at_positive_ROI: > 80%
  
  process_mining_quality:
    discovery_accuracy: > 80% (vs manual baseline)
    user_acceptance_of_discovered: > 70%
    time_to_first_workflow_post_PM: < 7 days
## 62.3 Business KPIs
business_kpis:
  
  revenue:
    MRR_growth: > 20% MoM in year 1
    expansion_revenue: > 30% of total revenue
    ACV (annual contract value): track quarterly
  
  efficiency:
    CAC_payback: < 12 months
    gross_margin: > 70%
    R&D_as_pct_of_revenue: 30-40% in year 1
  
  market:
    customer_count: 100 by end of year 1
    departmental_coverage_per_customer: > 3 departments avg
    market_share_VN_SME_workflow: track yearly

# Tổng kết — Kaori AI Workflow System v2.0
## Major Changes from v1.0
v1.0: 12 Parts, 33 sections, ~12K words
v2.0: 16 Parts, 62 sections, ~25K words

NEW PARTS (5):
  + PART IV — Process Mining & Workflow Discovery (THE moat)
  + PART VIII — Adoption Intelligence (organizational behavior layer)
  + PART IX — Runtime Reliability Architecture (idempotency + saga + DLQ)
  + PART X — Runtime Observability (distributed tracing)
  + PART XI — Operational Economics (NOV engine, manager language)

ENRICHED PARTS (existing):
  ~ PART II — Added Workflow as Code, side_effect_class, reliability config
  ~ PART VI — Added LLM Version Drift handling
  ~ PART VII — Adoption + Economics dimensions in better/worse framework
  ~ PART XIII — Multi-tenancy security + secrets management
  ~ PART XVI — Phase scope significantly tightened
## Triết lý cốt lõi (10 nguyên tắc v2.0 vs 6 ở v1.0)
1. WORKFLOW = SỐ HÓA QUY TRÌNH
2. PROCESS MINING TRƯỚC, BUILDER SAU ⭐ NEW
3. CHUYỂN ĐỔI SỐ LÀ ITERATIVE (60-90 day loops)
4. ADOPTION INTELLIGENCE = MOAT ⭐ NEW
5. RUNTIME RELIABILITY = ENTERPRISE-GRADE ⭐ NEW
6. WORKFLOW + AI = SYMBIOSIS
7. VERSIONING + IMPACT TRANSPARENCY
8. OPERATIONAL ECONOMICS — MANAGER LANGUAGE ⭐ NEW
9. PLATFORM-SIDE OBSERVABILITY
10. PRICING-CONSTRAINED CAPABILITY
## P0 Gaps Addressed (from ChatGPT critique)
✓ Gap 1 — Process Mining: PART IV
✓ Gap 3 — Adoption Intelligence: PART VIII
✓ Gap 7 — Runtime Reliability: PART IX
✓ Gap 8 — Runtime Observability: PART X
✓ Gap 9 — Operational Economics: PART XI

Plus self-identified:
✓ LLM Version Drift: Phần 21
✓ Multi-Tenancy Security: Phần 51
✓ Secrets Management: Phần 52
✓ Workflow as Code: Phần 4
## Deferred to Future Phases (per scope discipline)
Phase 2:
  - Simulation Engine (Gap 4)
  - Workflow Ontology (Gap 5)
  - Organizational Memory Graph (Gap 2)
  - Strategic OKR Mapping (Gap 10)

Phase 3:
  - Multi-Agent Orchestration (Gap 6)
  - Workflow Marketplace
  - Federated Workflows
## Phase 1 Scope Discipline
Cut from 45 → 25 node types
Cut from 40 → 15 templates
Cut from 6 → 4 departments initial
Cut 90-day parallel testing → Phase 1.5
Cut multi-user collaboration → Phase 2
Cut process mining full → Phase 2 (Phase 1 has v1 with 3 sources)
Cut workflow-as-code → Phase 2

Phase 1 still has all P0 critical capabilities:
  - Drag-drop builder + 25 nodes
  - Idempotency + retry + DLQ + distributed tracing
  - LLM version pinning
  - Multi-tenancy security + secrets vault
  - Adoption Intelligence (5 of 9 signals)
  - Operational Economics (basic NOV)
  - Process Mining v1 (3 sources)
## Bộ docs Kaori AI hiện tại
1. Kaori_AI_Gaps_Analysis_v1
2. Kaori_AI_SAD_Skeleton_v1
3. Kaori_Dataset_Selection_Report
4. Kaori_90day_Playbook_v3_Unified
5. Kaori_Pipeline_Unified v1.1 (data layer)
6. Kaori_AI_Reasoning_Layer v4.0 (AI brain)
7. Kaori_AI_Workflow_System v2.0 (this — workflow layer + process mining + adoption + ROI engine)

Total: ~85,000+ từ enterprise documentation

END OF DOCUMENT — Kaori AI Workflow System v2.0