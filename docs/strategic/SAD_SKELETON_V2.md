# Kaori AI — Software Architecture Document (SAD)
Master Architecture Document — Unified View of Kaori AI Platform
Phiên bản: v2.0 (Comprehensive Rewrite) Phát hành: Tháng 5 / 2026 Audience: Engineering Lead · Architects · Senior Engineers · DevOps/SRE · Security · Product · CTO/CIO Master document — references: - Pipeline Unified v1.1 — L1-L2 (Ingestion + Data Plane) - Reasoning Layer v4.0 — L3 (AI Brain) - Workflow System v2.0 — L4 (Orchestration) + L4.5 (Org Intelligence) - 90-day Playbook v3 — Operational deployment context - Gaps Analysis v1 — Risk + open questions context
Mục đích: Tài liệu này là single source of truth cho kiến trúc toàn hệ thống. Các doc khác đào sâu từng layer; SAD này tổng hợp toàn cảnh.
Cách dùng: - Engineer mới onboard → đọc SAD trước, sau đó zoom vào layer doc tương ứng - Architect → reference cho ADRs, design reviews - DevOps → deployment + cross-cutting concerns - Security audit → kiểm tra multi-tenancy, secrets, isolation

## Triết lý kiến trúc
1. LAYERED ARCHITECTURE
   6 layer rõ ràng, dependency chỉ chạy 1 chiều (top-down request, bottom-up data)
   Mỗi layer có contract API riêng, có thể swap implementation

2. EVENT-DRIVEN BACKBONE
   Layer-to-layer communication primary qua events (Redis Streams)
   Async by default; sync chỉ khi cần ngay
   Decoupled = scale independently + replay historic events

3. POLYGLOT PERSISTENCE
   Right tool for right data:
   - Postgres: transactional (workflows, configs, ACLs)
   - ClickHouse: analytical (metrics, traces, time-series)
   - MinIO: blob (files, exports)
   - Redis: cache + pubsub
   - Pinecone: vectors (RAG)
   - Vault: secrets

4. MULTI-TENANCY = FIRST-CLASS CITIZEN
   Every layer carries tenant_id
   Row-level security at DB
   Quota + isolation per tenant
   Cross-tenant leak = critical bug

5. RELIABILITY OVER PERFORMANCE
   Idempotency by design (retry-safe)
   Saga pattern cho irreversible operations
   Distributed tracing every operation
   At-least-once + idempotency >>> exactly-once complexity

6. AI AS LAYER, NOT FEATURE
   Reasoning Layer là service riêng, không scattered
   LLM version pinned per workflow (no silent drift)
   Cost-aware (per-tenant caps, per-workflow caps)

7. PROCESS MINING = MOAT
   Discover before build
   SME không biết workflow thật → AI mine từ logs
   Builder pre-populated, user CHỈNH chứ không build từ đầu

8. OPERATIONAL ECONOMICS = MANAGER LANGUAGE
   Mọi capability đều quy ra VND
   NOV (Net Operational Value) tracked monthly
   ROI dashboard là first-class UI

9. ADOPTION INTELLIGENCE LAYER
   Theo dõi resistance signals (workflow abandonment, override, side-channel)
   Proactive intervention (auto + CSM)
   Vietnam-specific context (Zalo, Excel, hierarchical decision)

10. VIETNAM-NATIVE
    Hosted in Vietnam (data residency)
    Zalo + Misa + Fast + Bravo first-class connectors
    Vietnamese language throughout product
    Pricing in VND, billing in VND

## Mục lục
### PART I — TỔNG QUAN KIẾN TRÚC
Phần 0. Mục đích & Phạm vi của SAD
Phần 1. Architectural Style & Patterns
Phần 2. High-Level System Diagram
Phần 3. Layer-by-Layer Overview
Phần 4. Quan hệ giữa các Layer Docs
### PART II — LAYER 0-1 (INFRASTRUCTURE & INGESTION)
Phần 5. Layer 0 — Infrastructure Foundation
Phần 6. Layer 1 — Ingestion Architecture
Phần 7. Connector Library (Vietnam-specific)
Phần 8. Streaming + Batch Patterns
### PART III — LAYER 2 (DATA PLANE)
Phần 9. Bronze · Silver · Gold Architecture
Phần 10. Feature Store
Phần 11. Data Quality Architecture
Phần 12. Schema Evolution & Governance
### PART IV — LAYER 3 (REASONING + KNOWLEDGE)
Phần 13. Reasoning Layer Architecture
Phần 14. Insight Engine · Recommendation · Constraint
Phần 15. Formula Library & Criteria Engine
Phần 16. RAG Engine & Knowledge Graph
Phần 17. LLM Integration Patterns
### PART V — LAYER 4 (ORCHESTRATION + WORKFLOW)
Phần 18. Workflow Engine Architecture (Temporal-based)
Phần 19. Workflow Builder Architecture
Phần 20. Action Runtime
Phần 21. State Machines & Workflow Lifecycle
### PART VI — LAYER 4.5 (ORG INTELLIGENCE — NEW v2.0)
Phần 22. Process Mining Engine Architecture
Phần 23. Adoption Intelligence Architecture
Phần 24. Operational Economics (NOV) Engine
### PART VII — LAYER 5 (USER LAYER)
Phần 25. Web UI Architecture
Phần 26. Mobile + Zalo Bot
Phần 27. Notification & Alert Channels
Phần 28. API Gateway & Public APIs
### PART VIII — CROSS-CUTTING CONCERNS
Phần 29. Multi-Tenancy Architecture
Phần 30. Security Architecture
Phần 31. Observability Architecture
Phần 32. Reliability Architecture (Idempotency, Saga, DLQ)
Phần 33. Cost Management Architecture
Phần 34. Audit & Compliance
### PART IX — INTEGRATION & DATA FLOW
Phần 35. Inter-Layer API Contracts
Phần 36. Event Schemas & Topics
Phần 37. End-to-End Data Flow Examples
Phần 38. External Integration Patterns
### PART X — DEPLOYMENT ARCHITECTURE
Phần 39. Kubernetes Layout
Phần 40. Vietnam Region Hosting
Phần 41. CI/CD Pipeline
Phần 42. Disaster Recovery & Backup
### PART XI — NON-FUNCTIONAL REQUIREMENTS
Phần 43. Performance Targets
Phần 44. Scalability Architecture
Phần 45. Availability & SLA
Phần 46. Security Requirements
Phần 47. Maintainability & Evolution
### PART XII — ARCHITECTURE DECISION RECORDS (ADRs)
Phần 48. ADR-001: Modular Monolith → Microservices Evolution
Phần 49. ADR-002: Temporal.io for Workflow Orchestration
Phần 50. ADR-003: Postgres + ClickHouse Polyglot
Phần 51. ADR-004: Multi-Tenancy via RLS (not Schema-per-Tenant)
Phần 52. ADR-005: At-Least-Once + Idempotency (not Exactly-Once)
Phần 53. ADR-006: Vendor LLM (Anthropic/OpenAI) over Self-Hosted
Phần 54. ADR-007: Vietnam Hosting (FPT/Viettel) over Cloud Hyperscaler
### PART XIII — RISKS & MITIGATIONS
Phần 55. Architectural Risks (top 15)
Phần 56. Mitigation Strategies
### PART XIV — ROADMAP
Phần 57. Phase 1 — Foundation (4 months)
Phần 58. Phase 1.5 — Stabilization (2 months)
Phần 59. Phase 2 — Differentiation (6 months)
Phần 60. Phase 3 — Platform (Year 2)

# PART I — TỔNG QUAN KIẾN TRÚC
# Phần 0. Mục đích & Phạm vi của SAD
## 0.1 Mục đích
SAD là kim chỉ nam kiến trúc cho toàn bộ hệ thống Kaori AI:
SAD trả lời các câu hỏi:
  1. Kaori AI gồm những thành phần gì?
  2. Các thành phần kết nối với nhau như thế nào?
  3. Dữ liệu chảy ra sao từ ingestion đến user?
  4. Quyết định kiến trúc nào đã được đưa ra và tại sao?
  5. Hệ thống có thể scale, secure, recover ra sao?
  6. Lộ trình tiến hóa kiến trúc qua các phase
## 0.2 Phạm vi
in_scope:
  - All layers (L0 to L5)
  - Cross-cutting concerns (security, observability, reliability)
  - Inter-layer integration patterns
  - Deployment architecture
  - Non-functional requirements
  - Architecture decisions
  - Phase evolution

out_of_scope_in_SAD_only:
  - Detailed business logic per domain (xem layer docs)
  - Specific UI mockups (xem product specs)
  - Sales/marketing strategy
  - Pricing structure (briefly only — full in Workflow doc)
  - Customer success procedures (xem Playbook)

referenced_but_not_duplicated:
  - Pipeline data tier specs → Pipeline Unified v1.1
  - Reasoning formulas/criteria → Reasoning Layer v4.0
  - Workflow node catalog → Workflow System v2.0
  - 60-90 day deployment loop → 90-day Playbook v3
## 0.3 Audience-Specific Reading Path
Engineer mới onboard (4-6 hours total):
  1. SAD Part I (overview) — 30 min
  2. SAD Part II-VII (layer-by-layer) — 2 hours
  3. SAD Part VIII (cross-cutting) — 1 hour
  4. Layer doc của domain mình work on — 1-2 hours

Architect/Tech Lead:
  1. SAD Part I + Part XII (ADRs) first — 1 hour
  2. SAD Part IX (integration patterns) — 1 hour
  3. SAD Part XI (NFRs) — 30 min
  4. Deep-dive layer docs as needed

DevOps/SRE:
  1. SAD Part X (deployment) — 1 hour
  2. SAD Part VIII (observability + reliability) — 1 hour
  3. SAD Part XI (NFRs SLA) — 30 min

Security Auditor:
  1. SAD Part VIII (multi-tenancy + security) — 2 hours
  2. SAD Phần 51-52 (RLS ADR + threat model) — 1 hour
  3. Workflow System v2.0 Phần 51-52 (security details)

Product Manager / CTO:
  1. SAD Part I (overview + principles) — 30 min
  2. SAD Part XIV (roadmap) — 30 min
  3. SAD Part XIII (risks) — 30 min

# Phần 1. Architectural Style & Patterns
## 1.1 Architectural Style
style: "Layered Modular Monolith → evolving to Microservices"

rationale:
  - Phase 1 (4 months): Modular monolith
    - Faster to ship, single deployment unit
    - Modules clearly separated (boundary maintained)
    - Database shared, but logical separation
  
  - Phase 2+ (6+ months): Selective extraction
    - Heavy services extracted (Workflow Engine, Process Mining)
    - Reasoning Layer remains shared service
    - Data Plane stays consolidated
  
  - Phase 3+ (Year 2): Full microservices
    - Each layer = independent deployable service(s)
    - Service mesh (Istio or Linkerd)
    - Independent scaling

why_not_microservices_from_start:
  - Premature complexity for 6-8 person team
  - Distributed debugging painful at small scale
  - Network calls between every layer = 10x latency
  - Single transaction across services = saga complexity from day 1
## 1.2 Architectural Patterns Applied
patterns:
  
  1_clean_architecture:
    description: "Domain core independent of infrastructure"
    where: "All business logic in domain modules; adapters at edges"
    example: "Workflow domain doesn't know about Postgres or Redis directly"
  
  2_event_driven:
    description: "Layers communicate via events when possible"
    where: "Workflow state changes, data updates, AI insights surface"
    backbone: "Redis Streams (Phase 1) → Kafka (Phase 2+ if needed)"
  
  3_cqrs_lite:
    description: "Read and write paths separated where helpful"
    where: "Workflow execution writes via Temporal; reads via API on materialized views"
  
  4_saga_pattern:
    description: "Distributed transactions via compensating actions"
    where: "Multi-node workflows with irreversible operations"
    detail: "Workflow System v2.0 PART IX"
  
  5_repository_pattern:
    description: "Data access abstracted behind repository interfaces"
    where: "All entity access goes through repositories"
  
  6_strategy_pattern:
    description: "Pluggable algorithms"
    where: "Anomaly detection methods, sequence mining algorithms, NOV calculation methods"
  
  7_observer_pattern:
    description: "React to system events"
    where: "Adoption Intelligence observes workflow execution events"
  
  8_circuit_breaker:
    description: "Fail fast when downstream unavailable"
    where: "External API calls (LLM, integrations)"
    library: "py-circuit-breaker or resilience4j-style"
  
  9_bulkhead:
    description: "Resource isolation per tenant"
    where: "Connection pools, thread pools, rate limits"
  
  10_outbox_pattern:
    description: "Reliable event publishing alongside transactions"
    where: "When DB write triggers event, ensure both happen atomically"
## 1.3 Anti-Patterns Avoided
anti_patterns_avoided:
  
  big_ball_of_mud:
    avoidance: "Strict module boundaries enforced by code review + linting"
  
  god_class:
    avoidance: "Each module < 500 LOC for class; split if larger"
  
  shared_mutable_state:
    avoidance: "Immutable data structures; state changes via events"
  
  premature_optimization:
    avoidance: "Optimize after profiling, not based on hunches"
  
  tight_coupling_to_vendors:
    avoidance: "Adapter pattern for LLM, DBs, queues"
    example: "Switch from Anthropic to OpenAI = config change, not code"
  
  data_silos:
    avoidance: "Single source of truth per domain entity; no duplication"
  
  premature_microservices:
    avoidance: "See ADR-001 — modular monolith first"

# Phần 2. High-Level System Diagram
## 2.1 Master Architecture Diagram
╔═══════════════════════════════════════════════════════════════════════════╗
║                         KAORI AI PLATFORM — v2.0                          ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║   ┌──────────────────────────────────────────────────────────────────┐    ║
║   │  L5 — USER LAYER                                                 │    ║
║   │  ┌─────────────┐  ┌──────────┐  ┌─────────┐  ┌────────────────┐ │    ║
║   │  │  Web UI     │  │  Mobile  │  │  Zalo   │  │ API Gateway    │ │    ║
║   │  │  (React)    │  │  (R/N)   │  │  Bot    │  │ (FastAPI)      │ │    ║
║   │  └──────┬──────┘  └─────┬────┘  └────┬────┘  └────┬───────────┘ │    ║
║   └─────────┼───────────────┼────────────┼────────────┼─────────────┘    ║
║             │               │            │            │                  ║
║             └───────────────┴────────────┴────────────┘                  ║
║                              │                                           ║
║   ┌──────────────────────────┴──────────────────────────────────────┐    ║
║   │  L4.5 — ORG INTELLIGENCE LAYER ⭐ NEW v2.0                       │    ║
║   │  ┌───────────────┐ ┌──────────────────┐ ┌──────────────────┐    │    ║
║   │  │ Process       │ │ Adoption         │ │ Operational      │    │    ║
║   │  │ Mining Engine │ │ Intelligence     │ │ Economics (NOV)  │    │    ║
║   │  │               │ │                  │ │                  │    │    ║
║   │  │ Discover      │ │ Resistance       │ │ Revenue impact   │    │    ║
║   │  │ workflows     │ │ signals          │ │ Cost modeling    │    │    ║
║   │  │ from logs     │ │ Health score     │ │ Time-to-payback  │    │    ║
║   │  └───────────────┘ └──────────────────┘ └──────────────────┘    │    ║
║   └──────────────────────────┬──────────────────────────────────────┘    ║
║                              │                                           ║
║   ┌──────────────────────────┴──────────────────────────────────────┐    ║
║   │  L4 — ORCHESTRATION LAYER                                       │    ║
║   │  ┌────────────────┐  ┌──────────────────┐  ┌────────────────┐  │    ║
║   │  │ Workflow       │  │ Action Runtime   │  │ Distributed    │  │    ║
║   │  │ Engine         │  │ (side effects)   │  │ Tracing        │  │    ║
║   │  │ (Temporal.io)  │  │                  │  │ (OTel + Jaeger)│  │    ║
║   │  │                │  │ - Email/SMS      │  │                │  │    ║
║   │  │ - Idempotent   │  │ - API calls      │  │ Every workflow │  │    ║
║   │  │ - Saga rollback│  │ - DB writes      │  │ run = 1 trace  │  │    ║
║   │  │ - Retry + DLQ  │  │ - Workflow trig  │  │                │  │    ║
║   │  └────────────────┘  └──────────────────┘  └────────────────┘  │    ║
║   └──────────────┬─────────────────────────────────┬───────────────┘    ║
║                  │                                 │                    ║
║   ┌──────────────┴───────────┐    ┌───────────────┴────────────────┐    ║
║   │ L3a — REASONING LAYER    │    │ L3b — RAG / KNOWLEDGE          │    ║
║   │ (AI Brain)               │    │                                │    ║
║   │ ┌──────────────────────┐ │    │ ┌────────────────────────────┐ │    ║
║   │ │ Insight Engine       │ │    │ │ Vector Store (Pinecone)    │ │    ║
║   │ │ Recommendation       │ │    │ │ Knowledge Graph            │ │    ║
║   │ │ Constraint Engine    │ │    │ │ Document RAG               │ │    ║
║   │ │ Formula Library      │ │    │ │ Domain Ontology            │ │    ║
║   │ │ Criteria Engine      │ │    │ │                            │ │    ║
║   │ │ Memory · Profile     │ │    │ │ Citation tracking          │ │    ║
║   │ │ LLM Integration      │ │    │ │ Recency awareness          │ │    ║
║   │ │ (Claude / GPT pinned)│ │    │ │                            │ │    ║
║   │ └──────────────────────┘ │    │ └────────────────────────────┘ │    ║
║   └──────────────┬───────────┘    └───────────────┬────────────────┘    ║
║                  │                                │                    ║
║   ┌──────────────┴────────────────────────────────┴───────────────┐    ║
║   │ L2 — DATA PLANE                                              │    ║
║   │ ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────────┐ │    ║
║   │ │ Bronze   │→ │ Silver   │→ │ Gold     │  │ Feature Store  │ │    ║
║   │ │ (raw)    │  │ (clean)  │  │ (ready)  │  │ (ML features)  │ │    ║
║   │ └──────────┘  └──────────┘  └──────────┘  └────────────────┘ │    ║
║   │                                                              │    ║
║   │ Data Quality (Great Expectations) · Schema Registry          │    ║
║   │ Lineage Tracking (OpenLineage) · Privacy Filtering           │    ║
║   └──────────────┬───────────────────────────────────────────────┘    ║
║                  │                                                    ║
║   ┌──────────────┴───────────────────────────────────────────────┐    ║
║   │ L1 — INGESTION LAYER                                         │    ║
║   │ ┌─────────────┐ ┌─────────────┐ ┌──────────────────────────┐ │    ║
║   │ │ Connectors  │ │ Streaming   │ │ Batch                    │ │    ║
║   │ │ - Misa      │ │ Redis       │ │ Cron-scheduled           │ │    ║
║   │ │ - Fast      │ │ Streams     │ │ Airflow (or Prefect)     │ │    ║
║   │ │ - Bravo     │ │             │ │                          │ │    ║
║   │ │ - Zalo API  │ │ CDC         │ │                          │ │    ║
║   │ │ - Postgres  │ │ Webhooks    │ │                          │ │    ║
║   │ │ - MySQL     │ │             │ │                          │ │    ║
║   │ │ - Excel     │ └─────────────┘ └──────────────────────────┘ │    ║
║   │ │ - Email     │                                              │    ║
║   │ │ - Calendar  │                                              │    ║
║   │ └─────────────┘                                              │    ║
║   └──────────────┬───────────────────────────────────────────────┘    ║
║                  │                                                    ║
║   ┌──────────────┴───────────────────────────────────────────────┐    ║
║   │ L0 — INFRASTRUCTURE                                          │    ║
║   │                                                              │    ║
║   │  Compute:    Kubernetes (Vietnam region — FPT/Viettel)       │    ║
║   │  Persistence:                                                │    ║
║   │    - Postgres 15+ (transactional, RLS for multi-tenancy)     │    ║
║   │    - ClickHouse (analytical, traces, time-series)            │    ║
║   │    - MinIO S3 (blob storage, files, exports)                 │    ║
║   │    - Redis 7 (cache, streams, distributed locks)             │    ║
║   │    - Pinecone (vector, RAG)                                  │    ║
║   │  Secrets:    HashiCorp Vault                                 │    ║
║   │  Tracing:    OpenTelemetry → Jaeger                          │    ║
║   │  Metrics:    Prometheus + Grafana                            │    ║
║   │  Logs:       Loki                                            │    ║
║   │  Alerts:     PagerDuty / On-call rotation                    │    ║
║   └──────────────────────────────────────────────────────────────┘    ║
║                                                                       ║
║   ┌──────────────────────────────────────────────────────────────┐    ║
║   │ CROSS-CUTTING CONCERNS (apply to all layers)                 │    ║
║   │                                                              │    ║
║   │  • Multi-Tenancy (tenant_id everywhere, RLS at DB)           │    ║
║   │  • Authentication & Authorization (JWT, RBAC)                │    ║
║   │  • Secrets Management (Vault references, never inline)       │    ║
║   │  • Observability (every operation traced)                    │    ║
║   │  • Reliability (idempotency, retry, saga, DLQ)               │    ║
║   │  • Cost Tracking (per-tenant, per-workflow)                  │    ║
║   │  • Audit Logging (immutable trail)                           │    ║
║   │  • Privacy (PII redaction, consent management)               │    ║
║   └──────────────────────────────────────────────────────────────┘    ║
╚═══════════════════════════════════════════════════════════════════════════╝
## 2.2 Data Flow at a Glance
External Sources                                    User Decisions
       │                                                   ↑
       ▼                                                   │
[L1 Ingestion] ─────► [L2 Data Plane] ──────────► [L5 User Layer]
                            │                          ↑
                            ▼                          │
                      [L3 Reasoning] ──────────────────┤
                            │                          │
                            ▼                          │
                      [L4 Workflow] ────────► [L4.5 Org Intel] 
                            │                          │
                            └──────────────────────────┘
                            (workflow execution → adoption signals → ROI)

# Phần 3. Layer-by-Layer Overview
## 3.1 Layer Responsibility Summary
layers:
  
  L0_infrastructure:
    role: "Foundation: compute, storage, network"
    components: ["Kubernetes", "Postgres", "ClickHouse", "MinIO", "Redis", "Vault", "OTel/Jaeger"]
    sla: 99.9% uptime
    deep_doc: "Pipeline Unified §1-3 + this SAD Phần 5"
  
  L1_ingestion:
    role: "Pull data from sources, normalize, route to data plane"
    components: ["Connectors", "Streaming pipelines", "Batch jobs"]
    key_capabilities: ["50+ source types", "Vietnam-specific (Zalo, Misa, Fast)", "CDC + webhooks"]
    deep_doc: "Pipeline Unified §4-5 + this SAD Phần 6-8"
  
  L2_data_plane:
    role: "Cleansed, validated, queryable data"
    components: ["Bronze/Silver/Gold tiers", "Feature Store", "Data Quality"]
    sla: "Silver freshness < 5 min for streaming sources"
    deep_doc: "Pipeline Unified §6-9 + this SAD Phần 9-12"
  
  L3a_reasoning:
    role: "AI brain — generate insights, recommendations, validations"
    components: ["Insight Engine", "Recommendation Engine", "Constraint Engine", "Formula Library", "Criteria Engine", "Memory"]
    sla: "Sync insights < 3s; async insights < 30s"
    deep_doc: "Reasoning Layer v4.0 (full doc) + this SAD Phần 13-17"
  
  L3b_rag:
    role: "Knowledge retrieval, document grounding"
    components: ["Vector store (Pinecone)", "Knowledge graph", "Document RAG", "Citation tracker"]
    deep_doc: "Reasoning Layer v4.0 §RAG + this SAD Phần 16"
  
  L4_orchestration:
    role: "Execute workflows reliably with side effects"
    components: ["Workflow Engine (Temporal)", "Action Runtime", "Distributed Tracing"]
    sla: "Workflow execution success rate > 99.5%"
    deep_doc: "Workflow System v2.0 PART IX-X + this SAD Phần 18-21"
  
  L4_5_org_intelligence:
    role: "Understand the organization (NEW v2.0)"
    components: ["Process Mining", "Adoption Intelligence", "Operational Economics"]
    capabilities:
      - "Discover actual workflows from event logs"
      - "Detect adoption resistance signals"
      - "Quantify ROI in VND (NOV)"
    deep_doc: "Workflow System v2.0 PART IV + VIII + XI; this SAD Phần 22-24"
  
  L5_user:
    role: "Human interface to platform"
    components: ["Web UI", "Mobile", "Zalo Bot", "API Gateway", "Notifications"]
    deep_doc: "this SAD Phần 25-28"
## 3.2 Layer Interaction Matrix
              L0  L1  L2  L3a L3b L4  L4.5 L5
L0 (infra)    -   ↑   ↑   ↑   ↑   ↑   ↑    ↑    (provides resources)
L1 (ingest)   ↓   -   ↑   .   .   .   ↑    .    (writes to L2; logs to L4.5)
L2 (data)     ↓   .   -   ↑   ↑   ↑   ↑    ↑    (read by L3, L4, L4.5, L5)
L3a (reason)  ↓   .   ↑   -   ↑   ↑   ↑    ↑    (called by L4, L4.5, L5)
L3b (RAG)     ↓   .   .   ↑   -   ↑   .    ↑    (called by L3a, L4, L5)
L4 (workflow) ↓   .   ↕   ↑   .   -   ↕    ↑    (read/write data, call AI)
L4.5 (org)    ↓   ↑   ↑   ↑   .   ↑   -    ↑    (observes everything)
L5 (user)     ↓   .   ↑   ↑   ↑   ↑   ↑    -    (top of stack)

Legend:
  ↑ — calls upward (read)
  ↓ — provides resource
  ↕ — bidirectional
  . — no direct interaction
## 3.3 Dependency Direction Rules
dependency_rules:
  
  rule_1_layered:
    statement: "Higher layer can call lower layer; never vice versa"
    enforcement: "Module imports checked in CI/CD"
  
  rule_2_no_circular:
    statement: "No circular dependencies between modules"
    enforcement: "Architecture tests fail build"
  
  rule_3_event_for_inversion:
    statement: "If lower layer needs to notify higher, use events (not direct calls)"
    example: "L4 workflow execution → emits event → L4.5 adoption observer subscribes"
  
  rule_4_no_db_skip:
    statement: "L5 does NOT directly access DB; goes through L4 or L3 APIs"
    rationale: "Maintain abstraction, allow DB schema changes"

# Phần 4. Quan hệ giữa các Layer Docs
## 4.1 Doc Map
┌──────────────────────────────────────────────────────────────────────┐
│ KAORI AI DOCUMENT ECOSYSTEM (8 documents, ~110K words total)         │
└──────────────────────────────────────────────────────────────────────┘

    ┌────────────────────────────────────────────┐
    │ SAD v2.0 (this doc)                        │ ← MASTER
    │ Tổng quan kiến trúc                        │   Single source of
    │ ~22-25K từ                                 │   truth for archi
    └─────────┬──────────────────────────────────┘
              │
              │  references
              ▼
    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          ▼
  ┌──────────────────────┐    ┌──────────────────────────────┐
  │ Pipeline Unified     │    │ Reasoning Layer v4.0         │
  │ v1.1 (~16K từ)       │    │ (~16K từ)                    │
  │ L1-L2 deep dive      │    │ L3a deep dive                │
  └──────────────────────┘    └──────────────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                                                          │
    ▼                                                          ▼
  ┌──────────────────────┐    ┌──────────────────────────────┐
  │ Workflow System      │    │ 90-day Playbook v3 Unified   │
  │ v2.0 (~22K từ)       │    │ (~14K từ)                    │
  │ L4 + L4.5 deep dive  │    │ Operational deployment       │
  └──────────────────────┘    └──────────────────────────────┘

  Supporting docs:
  ┌──────────────────────┐    ┌──────────────────────────────┐
  │ Gaps Analysis v1     │    │ Dataset Selection Report     │
  │ Risk + open questions│    │ + manifest + sample CSVs     │
  └──────────────────────┘    └──────────────────────────────┘
## 4.2 When to Read What
reading_guide:
  
  scenario_1_new_engineer_onboarding:
    sequence: [SAD, Workflow_System, Pipeline_Unified, Reasoning_Layer]
    duration: "1 week deep read + reference"
  
  scenario_2_implementing_a_feature:
    layer_data: "Pipeline Unified specific section"
    layer_ai: "Reasoning Layer specific section"
    layer_workflow: "Workflow System specific section"
    cross_layer: "SAD Part IX (integration patterns)"
  
  scenario_3_security_audit:
    sequence: [SAD_Part_VIII, Workflow_System_Phần_51-52, Pipeline_Phần_security]
  
  scenario_4_customer_implementation:
    sequence: [Playbook, Workflow_System_Phần_61_phase_scope, SAD_Part_X_deployment]
  
  scenario_5_executive_brief:
    sequence: [SAD_Part_I_overview, Gaps_Analysis_summary, Workflow_PART_XI_economics]
## 4.3 Cross-References Convention
Trong toàn bộ docs, sử dụng convention sau cho cross-reference:
reference_format:
  
  same_doc_section: "(see Phần X)"
  
  another_doc_section: "(see [DocName] Phần X)"
  examples:
    - "(see Pipeline Unified Phần 4)"
    - "(see Reasoning Layer Phần 6)"
    - "(see Workflow System PART IX)"
  
  ADR_reference: "(see ADR-NNN)"

# PART II — LAYER 0-1 (INFRASTRUCTURE & INGESTION)
# Phần 5. Layer 0 — Infrastructure Foundation
## 5.1 Compute Platform
compute:
  primary: Kubernetes
  version: "1.28+"
  hosting:
    primary: "FPT Cloud (Vietnam region)"
    secondary: "Viettel IDC"
    rationale: "Data residency, latency for Vietnamese customers"
  
  cluster_topology:
    production:
      - node_pool_general: 6 nodes (8 CPU, 32GB each)
      - node_pool_compute: 4 nodes (16 CPU, 64GB each) for heavy workloads
      - node_pool_storage: 3 nodes (4 CPU, 64GB, large disk)
    staging:
      - node_pool_general: 3 nodes (smaller)
    development:
      - shared cluster or local minikube
  
  networking:
    cni: Calico (network policies for tenant isolation)
    ingress: NGINX Ingress Controller
    service_mesh:
      phase_1: not used
      phase_2_plus: Istio or Linkerd
  
  autoscaling:
    horizontal_pod_autoscaler: yes (CPU + custom metrics)
    cluster_autoscaler: yes (scale node pools)
## 5.2 Persistence Layer
persistence:
  
  postgresql_15:
    role: "Transactional data — workflows, configs, ACLs, idempotency"
    deployment: "Stolon or CloudNativePG operator"
    instances:
      - primary (writes)
      - 2 replicas (reads + HA)
    backup:
      strategy: "WAL archiving + daily full backup"
      retention: "30 days"
      destination: "MinIO + offsite (S3-compatible)"
    multi_tenancy:
      strategy: "Row-Level Security (RLS)"
      isolation: "Logical (not physical) — see ADR-004"
  
  clickhouse:
    role: "Analytical — traces, metrics, time-series, large aggregations"
    deployment: "ClickHouse Operator (Altinity)"
    instances: "3 nodes (sharded + replicated)"
    use_cases:
      - "OpenTelemetry trace storage"
      - "Workflow execution metrics"
      - "Adoption signal events"
      - "NOV time-series"
  
  minio:
    role: "Object storage — files, exports, backups, model artifacts"
    deployment: "Distributed mode, 4 nodes"
    s3_api: "S3-compatible (ACL via IAM-style policies)"
    multi_tenancy:
      strategy: "Bucket prefix per tenant"
      iam: "Tenant-scoped read/write paths"
  
  redis_7:
    role: "Cache, distributed locks, event streams, pub/sub"
    deployment: "Redis Cluster (3 master + 3 replica)"
    use_cases:
      - "Session cache"
      - "Rate limiting counters"
      - "Distributed locks (idempotency)"
      - "Event streams (Redis Streams) — Phase 1 backbone"
      - "Pub/sub for real-time UI updates"
  
  pinecone:
    role: "Vector database for RAG"
    deployment: "Managed (Pinecone cloud) — Vietnam egress allowed"
    alternative: "Qdrant (self-hosted) for data residency strict customers"
    multi_tenancy: "Namespace per tenant"
## 5.3 Secrets Management
secrets:
  
  vault: HashiCorp Vault
  deployment: "Vault HA mode (3 nodes, Raft consensus)"
  
  paths:
    - "/tenant/{tenant_id}/api_keys/*"
    - "/tenant/{tenant_id}/oauth_tokens/*"
    - "/tenant/{tenant_id}/db_credentials/*"
    - "/internal/llm_api_keys/*"
    - "/internal/infra_credentials/*"
  
  access_control:
    - "Workflow execution role: read scoped to tenant"
    - "Admin role: read/write all"
    - "Audit logged on every access"
  
  rotation:
    - "API keys: 90 days"
    - "OAuth tokens: per token TTL"
    - "Encryption keys: 365 days"
## 5.4 Observability Stack
observability:
  
  tracing:
    standard: OpenTelemetry
    backend: Jaeger (Phase 1) → Tempo (Phase 2 if scale demands)
    sampling: "Head-based: 100% errors, 10% successful"
    storage: "30 days hot in Jaeger, 90 days warm in ClickHouse"
  
  metrics:
    collection: Prometheus
    visualization: Grafana
    retention: "15 days hot, 90 days downsampled"
    custom_metrics:
      - workflow_executions_total
      - ai_calls_total
      - tenant_quota_usage
      - nov_per_workflow
      - adoption_score_per_workflow
  
  logs:
    collection: Promtail
    aggregation: Loki
    structured: JSON only (parseable fields)
    retention: "14 days hot, 90 days cold"
  
  alerts:
    routing: PagerDuty
    on_call: "Rotation between 4 engineers"
    severity_levels: [P1_critical, P2_high, P3_medium, P4_low]
    sla_response:
      P1: 15 minutes
      P2: 1 hour
      P3: 4 hours
      P4: 24 hours
  
  apm:
    tool: Sentry
    error_tracking: yes
    performance_monitoring: yes
    user_session_replay: opt-in only
## 5.5 Network Architecture
                    ┌──────────────────────────┐
                    │  Vietnam customers       │
                    │  (web, mobile, Zalo)     │
                    └────────────┬─────────────┘
                                 ▼
                       ┌─────────────────┐
                       │  CDN (Bunny.net │
                       │   or VN-based)  │
                       └────────┬────────┘
                                ▼
                       ┌─────────────────┐
                       │  Load Balancer  │
                       │  (NGINX / HAProxy)
                       └────────┬────────┘
                                ▼
                  ┌─────────────────────────┐
                  │  Kubernetes Cluster     │
                  │  ┌───────────────────┐  │
                  │  │ Ingress Controller│  │
                  │  └─────────┬─────────┘  │
                  │            ▼            │
                  │  ┌───────────────────┐  │
                  │  │  API Gateway      │  │
                  │  │  (FastAPI)        │  │
                  │  └─────────┬─────────┘  │
                  │            ▼            │
                  │  ┌───────────────────┐  │
                  │  │ Application Pods  │  │
                  │  │ (per layer/svc)   │  │
                  │  └─────────┬─────────┘  │
                  │            ▼            │
                  │  ┌───────────────────┐  │
                  │  │ Internal Services │  │
                  │  │ (DB, Cache, etc)  │  │
                  │  └───────────────────┘  │
                  └─────────────────────────┘
## 5.6 Acceptance Criteria — Phần 5
☐ Kubernetes cluster operational (Vietnam region)
☐ All persistence layers deployed (Postgres, ClickHouse, MinIO, Redis, Vault, Pinecone)
☐ Observability stack functional (traces, metrics, logs, alerts)
☐ Network policies enforce tenant isolation
☐ Secrets accessed only via Vault, never inline
☐ Backup + DR procedures tested

# Phần 6. Layer 1 — Ingestion Architecture
## 6.1 Ingestion Patterns
ingestion_patterns:
  
  pattern_1_streaming_cdc:
    description: "Change Data Capture from operational DBs"
    when: "Real-time sync needed (< 1 min latency)"
    tech: "Debezium → Redis Streams → Bronze tier"
    sources: ["Postgres WAL", "MySQL binlog", "MongoDB oplog"]
  
  pattern_2_streaming_webhooks:
    description: "External services push events"
    when: "Provider supports webhooks"
    tech: "FastAPI webhook receiver → Redis Streams → Bronze"
    sources: ["Stripe", "Shopify", "Custom apps"]
  
  pattern_3_polling_api:
    description: "Pull from APIs at intervals"
    when: "No webhook support, OR backfill"
    tech: "Scheduled job (Airflow/Prefect) → API call → Bronze"
    sources: ["Salesforce", "HubSpot", "Calendar APIs", "Misa", "Fast"]
  
  pattern_4_batch_file_upload:
    description: "User uploads Excel/CSV"
    when: "Manual data import, one-off analysis"
    tech: "Web upload → MinIO → Bronze ingestion job"
    sources: ["Excel", "CSV", "JSON files"]
  
  pattern_5_filesystem_watcher:
    description: "Watch shared folder for new/modified files"
    when: "Vietnam SME pattern: Excel auto-saved to shared drive"
    tech: "Watcher service → trigger ingestion → Bronze"
    sources: ["OneDrive shared folders", "Google Drive folders", "SMB shares"]
  
  pattern_6_chat_metadata:
    description: "Read message metadata (NOT content) from chat"
    when: "Process Mining for off-system communications"
    tech: "Zalo Business API / Slack Audit API → Bronze (metadata only)"
    privacy: "Strict — no content, only metadata + thread structure"
    sources: ["Zalo", "Slack", "Microsoft Teams"]
## 6.2 Ingestion Architecture Diagram
                       External Sources
   ┌──────────┬──────────┬──────────┬──────────┬───────────┐
   │ DB CDC   │ Webhooks │ API      │ Files    │ Chat APIs │
   └─────┬────┴────┬─────┴────┬─────┴─────┬────┴─────┬─────┘
         │         │          │           │          │
         └─────────┴────┬─────┴───────────┴──────────┘
                        ▼
              ┌────────────────────┐
              │ Connector Library  │
              │ (50+ connectors)   │
              └────────┬───────────┘
                       ▼
              ┌────────────────────┐
              │ Normalization      │
              │ (common schema)    │
              └────────┬───────────┘
                       ▼
              ┌────────────────────┐
              │ PII Detection +    │
              │ Privacy Filtering  │
              └────────┬───────────┘
                       ▼
              ┌────────────────────┐
              │ Tenant Tagging     │
              │ (tenant_id stamp)  │
              └────────┬───────────┘
                       ▼
              ┌────────────────────┐
              │ Bronze Tier        │
              │ (raw landing zone) │
              └────────┬───────────┘
                       ▼
                   [L2 Data Plane]
## 6.3 Connector Architecture
# Abstract base
class Connector(ABC):
    
    @abstractmethod
    def connect(self, credentials_ref: str) -> Connection:
        """Establish connection using credentials from Vault."""
    
    @abstractmethod
    def fetch(self, query_params: dict) -> Iterable[Record]:
        """Fetch records, yielding for streaming."""
    
    @abstractmethod
    def normalize(self, raw_record: Any) -> NormalizedRecord:
        """Transform to common schema."""
    
    @abstractmethod
    def detect_schema_change(self, sample: List[Record]) -> SchemaChange | None:
        """Detect if source schema changed since last sync."""

# Specific connectors
class MisaConnector(Connector):
    """Connector for Misa accounting software."""
    
    def fetch(self, query_params):
        # Misa-specific API logic
        pass

class ZaloBusinessConnector(Connector):
    """Connector for Zalo Business API."""
    
    def fetch(self, query_params):
        # Zalo OAuth + message metadata API
        # Returns metadata only, NEVER message content
        pass

# Phần 7. Connector Library (Vietnam-specific)
## 7.1 Phase 1 Connectors (Priority)
phase_1_connectors:
  
  databases:
    - postgres_cdc: "Debezium-based CDC"
    - mysql_cdc: "Debezium-based CDC"
    - mssql_cdc: "Debezium-based CDC"
  
  vietnam_erps:
    - misa: "ASP version + standalone"
    - fast_accounting: "API-based"
    - bravo: "API-based (or DB-direct if API unavailable)"
  
  files:
    - excel_filesystem_watcher: "Detect file changes in shared folders"
    - csv_uploader: "Manual upload via UI"
    - sharepoint_files: "Microsoft SharePoint"
    - google_drive: "Google Drive API"
    - onedrive: "Microsoft OneDrive"
  
  communication:
    - zalo_business_api: "CRITICAL for Vietnam"
    - gmail_metadata: "Email subject/from/to/timestamp"
    - outlook_metadata: "Email metadata via Microsoft Graph"
  
  calendar:
    - google_calendar: "Standard"
    - outlook_calendar: "Microsoft Graph"
  
  custom:
    - rest_api_generic: "Configurable REST API connector"
    - webhook_receiver: "Generic webhook endpoint"
## 7.2 Phase 2+ Connectors
phase_2_connectors:
  
  saas:
    - salesforce
    - hubspot
    - shopify
    - magento
    - lazada (Vietnam ecommerce)
    - shopee (Vietnam ecommerce)
    - tiki (Vietnam ecommerce)
  
  payment:
    - vnpay
    - momo
    - zalopay
    - bank_apis (vietnamese banks)
  
  communication:
    - slack
    - microsoft_teams
    - twilio (SMS, voice)
  
  pm_tools:
    - jira
    - asana
    - monday
    - notion
  
  infrastructure:
    - mongodb_oplog
    - kafka_consumer
## 7.3 Connector Lifecycle
┌─────────────────────────────────────────────────────────────┐
│ CONNECTOR DEVELOPMENT LIFECYCLE                             │
└────────────────────────────┬────────────────────────────────┘
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ 1. Customer Demand Signal                           │
   │    - Multiple customers requesting same source      │
   │    - Sales team escalates                           │
   └─────────────────────────────────────────────────────┘
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ 2. Spike (1-2 days)                                 │
   │    - API documentation review                       │
   │    - Authentication mechanism                       │
   │    - Rate limits                                    │
   │    - Schema sample                                  │
   └─────────────────────────────────────────────────────┘
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ 3. MVP Build (3-5 days)                             │
   │    - Implement Connector interface                  │
   │    - Unit tests                                     │
   │    - Integration test with real source              │
   └─────────────────────────────────────────────────────┘
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ 4. Beta Customer Test (1-2 weeks)                   │
   │    - 1 friendly customer                            │
   │    - Production data                                │
   │    - Bug fixes + edge cases                         │
   └─────────────────────────────────────────────────────┘
                             ▼
   ┌─────────────────────────────────────────────────────┐
   │ 5. GA Release                                       │
   │    - Documentation                                  │
   │    - Templates using this connector                 │
   │    - Marketing announcement                         │
   └─────────────────────────────────────────────────────┘
## 7.4 Acceptance Criteria — Phần 7
☐ Phase 1: 12+ connectors operational
☐ Vietnam-specific (Misa, Fast, Bravo, Zalo) functional
☐ Each connector: tested, documented, has templates
☐ Connector versioning (multiple versions can coexist)
☐ Schema change detection per connector

# Phần 8. Streaming + Batch Patterns
## 8.1 Streaming Architecture
streaming:
  
  backbone:
    phase_1: Redis Streams
    phase_2_plus: Apache Kafka (if scale demands)
  
  topics_naming_convention:
    pattern: "tenant.{tenant_id}.{domain}.{event_type}"
    examples:
      - "tenant.abc.workflow.execution_started"
      - "tenant.abc.data.customer_updated"
      - "tenant.abc.adoption.override_detected"
  
  consumer_groups:
    - "data_plane_silver_processor"
    - "reasoning_layer_event_observer"
    - "adoption_intel_signal_extractor"
    - "operational_economics_metric_aggregator"
  
  delivery_guarantee: at-least-once (combined with idempotency)
  ordering: per-partition (within tenant + domain)
  retention: 7 days hot, then archived to MinIO
## 8.2 Batch Architecture
batch:
  
  scheduler: 
    phase_1: Cron-based (Kubernetes CronJobs)
    phase_2: Apache Airflow OR Prefect
  
  job_categories:
    
    data_ingestion_polling:
      schedule: "every 15min for high-priority sources"
      timeout: 30 min
      retries: 3
    
    daily_aggregations:
      schedule: "01:00 Vietnam time"
      builds: "gold tier daily aggregates"
    
    monthly_aggregations:
      schedule: "first day of month, 02:00"
      builds: "monthly NOV reports, billing"
    
    cleanup_jobs:
      schedule: "daily 03:00"
      activities: "expire idempotency records, archive old traces"
    
    process_mining_sessions:
      schedule: "weekly OR on-demand"
      duration: "30-60 min per tenant"
## 8.3 Streaming vs Batch Decision
                Latency SLA
                ┌──────────────┬──────────────┬──────────────┐
                │  < 1 min     │ < 1 hour     │ > 1 hour     │
                ├──────────────┼──────────────┼──────────────┤
   Volume       │              │              │              │
   < 10K/day    │ Streaming    │ Streaming    │ Batch        │
                │              │              │              │
   10K-1M/day   │ Streaming    │ Streaming    │ Batch        │
                │              │ or batch     │              │
   > 1M/day     │ Streaming    │ Batch        │ Batch        │
                │ (sharded)    │              │              │
                └──────────────┴──────────────┴──────────────┘

# PART III — LAYER 2 (DATA PLANE)
# Phần 9. Bronze · Silver · Gold Architecture
## 9.1 Tier Responsibilities
tier_architecture:
  
  bronze:
    role: "Raw landing zone — exactly as received from source"
    storage: PostgreSQL (operational) + MinIO (large files)
    schema: minimal — preserve source format
    transformations: ZERO (just landing)
    retention: 90 days hot, then archive
    queryable: yes (but not for business use)
    
    why_bronze:
      - "Recoverability: re-process if Silver logic bug"
      - "Audit: prove what we received"
      - "Replay: feed Silver again with new logic"
  
  silver:
    role: "Cleaned, validated, deduped"
    storage: PostgreSQL
    schema: normalized + tenant-scoped
    transformations:
      - PII handling (redact OR encrypt)
      - Type casting
      - Validation against schema
      - Deduplication
      - Reference data joining
    retention: per data type policy (typically 2-7 years)
    queryable: yes (primary for L3 + L4)
    
    quality_gates:
      - "Reject record if validation fails"
      - "Quarantine if uncertain (manual review)"
      - "Auto-correct if known patterns (e.g., phone format)"
  
  gold:
    role: "Business-ready aggregates"
    storage: PostgreSQL (small) + ClickHouse (large)
    schema: denormalized for query performance
    transformations:
      - Aggregations (daily, monthly)
      - Joins across silver tables
      - Pre-computed metrics
      - Customer 360 views
    retention: 7+ years (business reporting)
    queryable: yes (primary for L5 reports)
    refresh_cadence: daily for most; near-real-time for hot metrics
  
  feature_store:
    role: "ML/AI ready features"
    storage: PostgreSQL + Redis (online serving)
    schema: feature-oriented (entity + feature_name + value + timestamp)
    use_cases:
      - "Customer churn score"
      - "Product recommendation embeddings"
      - "Anomaly detection baselines"
    consistency: 
      - offline (training): batch, eventual consistency
      - online (serving): low latency, real-time updates
## 9.2 Tier Flow Example
Source: Misa accounting record
   │
   ▼
[BRONZE]
   ├─ Schema: misa_raw_v1
   ├─ Fields: id, raw_xml, ingested_at, source_id
   └─ Retention: 90 days
   │
   ▼ (Silver job: every 15 min)
[SILVER]
   ├─ Table: silver.invoices
   ├─ Fields normalized: invoice_id, customer_id, amount_vnd, date, ...
   ├─ PII: customer_id is hashed reference
   ├─ Validation: amount > 0, date valid, customer exists
   └─ Retention: 7 years (legal)
   │
   ▼ (Gold job: nightly)
[GOLD]
   ├─ Table: gold.customer_360
   │  ├─ customer_id, total_invoices_count, total_revenue_vnd_30d, ...
   ├─ Table: gold.daily_revenue
   │  └─ date, total_revenue_vnd, by_segment_revenue, ...
   └─ Refresh: nightly batch + materialized views
   │
   ▼ (Feature Store: continuous)
[FEATURE STORE]
   ├─ feature.customer_ltv_predicted (online + offline)
   ├─ feature.customer_churn_risk_30d (online)
   └─ Updated continuously based on Silver/Gold changes
## 9.3 Multi-Tenancy at Data Tier
-- Every silver/gold table has tenant_id
CREATE TABLE silver.customers (
    customer_id UUID,
    tenant_id UUID NOT NULL,  -- always present
    name TEXT,
    email TEXT,
    -- ...
    PRIMARY KEY (customer_id),
    UNIQUE (tenant_id, customer_external_id)
);

-- Row-Level Security
ALTER TABLE silver.customers ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON silver.customers
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);

-- Indexes always include tenant_id first
CREATE INDEX idx_silver_customers_tenant ON silver.customers (tenant_id, customer_id);
CREATE INDEX idx_silver_customers_tenant_email ON silver.customers (tenant_id, email);

# Phần 10. Feature Store
## 10.1 Architecture
┌──────────────────────────────────────────────────────────┐
│ FEATURE STORE (Phase 1: custom; Phase 2: Feast or Tecton)│
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Offline Store (training):                               │
│    PostgreSQL/ClickHouse — historical features           │
│                                                          │
│  Online Store (serving):                                 │
│    Redis — hot features for sub-100ms reads              │
│                                                          │
│  Feature Registry:                                       │
│    Postgres — feature definitions, lineage, ownership    │
└──────────────────────────────────────────────────────────┘
## 10.2 Feature Definition Example
feature_definition:
  
  feature_name: "customer_churn_risk_score_30d"
  owner: "growth_team"
  
  description: "Predicted probability customer will churn in next 30 days"
  
  entity: customer_id
  
  source:
    type: derived
    inputs:
      - silver.customers.lifecycle_stage
      - silver.transactions.last_purchase_date
      - silver.engagement.last_login_at
    transformation: "ML model: XGBoost trained weekly"
  
  freshness_sla: "< 24 hours"
  online_latency_sla: "< 100ms"
  
  schema:
    type: float
    range: [0.0, 1.0]
  
  consumers:
    - reasoning.recommendation_engine
    - workflow.churn_prevention_template

# Phần 11. Data Quality Architecture
## 11.1 Quality Gates
quality_layers:
  
  ingestion_time:
    checks:
      - "Schema conformance"
      - "Required fields present"
      - "Type validity"
    on_fail: "Quarantine record + notify"
  
  silver_promotion:
    checks:
      - "Cross-field validation (e.g., end_date >= start_date)"
      - "Referential integrity (customer_id exists)"
      - "Range checks (amount > 0)"
    on_fail: "Reject record + log to data quality dashboard"
  
  gold_refresh:
    checks:
      - "Count anomaly (today's records vs avg)"
      - "Distribution drift detection"
      - "Aggregation sanity (totals match details)"
    on_fail: "Alert team + halt downstream until investigation"
  
  data_quality_dashboard:
    metrics:
      - records_processed_per_day
      - records_quarantined_per_day  
      - records_rejected_per_day
      - schema_changes_detected
      - quality_score_per_table
## 11.2 Tools
tools:
  
  great_expectations:
    use: "Define + run quality expectations"
    integration: "Run as part of Silver promotion job"
    examples:
      - "expect_column_values_to_not_be_null"
      - "expect_column_values_to_be_in_set"
      - "expect_table_row_count_to_be_between"
  
  custom_validators:
    use: "Vietnam-specific validations"
    examples:
      - "Vietnamese phone format check"
      - "Vietnamese ID number format"
      - "VND amount sanity (< 1 trillion)"

# Phần 12. Schema Evolution & Governance
## 12.1 Schema Registry
schema_registry:
  
  storage: Postgres table with versioning
  
  per_table:
    - table_name
    - tenant_id (or null for global)
    - schema_version
    - column_definitions (JSONB)
    - migration_script (if applicable)
    - effective_from / effective_to timestamps
  
  schema_change_workflow:
    1. propose_change: PR with new schema version
    2. impact_analysis: 
       - Find consumers (workflows, reports, AI features)
       - Estimate migration effort
    3. approval: Tech lead + product owner
    4. migration:
       - Add new columns (additive first)
       - Backfill if needed
       - Update consumers
       - Remove old columns (after grace period)
    5. registry_update: New schema version active
## 12.2 Backward Compatibility
compatibility_strategy:
  
  additive_changes: always backward compatible
    examples:
      - "Add new column with default"
      - "Add new optional field"
  
  removing_columns: requires migration period (90 days minimum)
    process:
      - announce deprecation
      - update all consumers to not use
      - actually remove
  
  type_changes: requires migration
    process:
      - add new column with new type
      - backfill
      - migrate consumers
      - remove old column

# PART IV — LAYER 3 (REASONING + KNOWLEDGE)
# Phần 13. Reasoning Layer Architecture
## 13.1 High-Level
Reasoning Layer là AI Brain của Kaori — generates insights, recommendations, validates decisions. Doc chi tiết: Reasoning Layer v4.0.
┌──────────────────────────────────────────────────────────────┐
│ REASONING LAYER (L3a)                                        │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ INPUT INTERFACE                                       │   │
│  │  - REST API (sync requests)                           │   │
│  │  - Event subscriber (async observation)               │   │
│  │  - Workflow integration (called from workflow nodes)  │   │
│  └───────────────────────────────────────────────────────┘   │
│                          │                                   │
│                          ▼                                   │
│  ┌───────────────────────────────────────────────────────┐   │
│  │ CONTEXT BUILDER                                       │   │
│  │  - Load tenant business profile                       │   │
│  │  - Load active criteria                               │   │
│  │  - Load active formulas                               │   │
│  │  - Load relevant memory                               │   │
│  └───────────────────────────────────────────────────────┘   │
│                          │                                   │
│        ┌─────────────────┼─────────────────┐                 │
│        ▼                 ▼                 ▼                 │
│  ┌──────────┐     ┌──────────┐      ┌──────────────┐        │
│  │ Insight  │     │ Recomm-  │      │ Constraint   │        │
│  │ Engine   │     │ endation │      │ Engine       │        │
│  │          │     │ Engine   │      │              │        │
│  │ Anomaly  │     │ Action   │      │ Validate     │        │
│  │ Trend    │     │ Best-fit │      │ Block unsafe │        │
│  │ Pattern  │     │ Ranking  │      │ Explainable  │        │
│  └─────┬────┘     └────┬─────┘      └──────┬───────┘        │
│        │               │                   │                │
│        └───────┬───────┴───────────────────┘                │
│                ▼                                            │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ FORMULA LIBRARY + CRITERIA ENGINE                     │  │
│  │  - 100+ business formulas (LTV, churn, ROI, etc)      │  │
│  │  - Domain criteria (when to flag, when to recommend)  │  │
│  │  - Per-tenant variants                                │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ LLM INTEGRATION                                       │  │
│  │  - Anthropic Claude (primary)                         │  │
│  │  - OpenAI GPT (fallback)                              │  │
│  │  - Version pinned per workflow                        │  │
│  │  - Drift detection                                    │  │
│  │  - Cost capping                                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                          │                                  │
│                          ▼                                  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ OUTPUT                                                │  │
│  │  - Structured insight (JSON)                          │  │
│  │  - Confidence score                                   │  │
│  │  - Explainability (executive/analyst/auditor levels)  │  │
│  │  - Citations                                          │  │
│  │  - LLM version used (audit)                           │  │
│  └───────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
## 13.2 API Surface
# Sync API for workflow nodes
POST /api/v1/reasoning/insights/generate
{
    "tenant_id": "...",
    "insight_type": "anomaly_detection",
    "focus_metric": "revenue",
    "data_window": {"start": "...", "end": "..."},
    "llm_pinned_version": "claude-sonnet-4.0",  # required
    "use_active_criteria": true
}
Response:
{
    "insight": {...},
    "confidence": 0.78,
    "explainability": {
        "executive": "Revenue anomaly detected in Q2...",
        "analyst": "Statistical method: zscore=3.2...",
        "auditor": "Data sources: silver.transactions where..."
    },
    "citations": [...],
    "llm_version_used": "claude-sonnet-4.0",
    "cost_vnd": 47
}

# Recommendation API
POST /api/v1/reasoning/recommendations/generate
{...}

# Constraint validation
POST /api/v1/reasoning/constraints/validate
{
    "action": {"type": "send_email", "to": "..."},
    "tenant_id": "..."
}
Response:
{
    "allowed": true | false,
    "violations": [...],
    "explanation": "..."
}

# Phần 14. Insight Engine · Recommendation · Constraint
## 14.1 Insight Engine
insight_engine:
  
  insight_types:
    - anomaly_detection (zscore, iqr, isolation_forest)
    - trend_detection (regression, change_point)
    - pattern_recognition (clustering, sequence patterns)
    - benchmark_comparison (vs industry, vs peer cohort)
    - root_cause_analysis (causal inference)
  
  detection_methods:
    statistical: ["zscore", "iqr", "ttest", "anova"]
    ml_based: ["isolation_forest", "lof", "kmeans"]
    rule_based: ["threshold", "boundary", "pattern_match"]
  
  output_format:
    title: short, scannable
    description: detailed but readable
    severity: [LOW, MEDIUM, HIGH, CRITICAL]
    confidence: 0-1
    evidence: data points + sources
    recommended_actions: list (links to workflow recommendations)
## 14.2 Recommendation Engine
recommendation_engine:
  
  recommendation_types:
    - action_recommendation (what to do)
    - workflow_recommendation (build new workflow X)
    - threshold_recommendation (adjust setting Y)
    - integration_recommendation (connect data source Z)
  
  ranking:
    by: [expected_impact, ease_of_implementation, business_priority]
    surfacing_threshold: confidence > 0.6 by default
  
  constraint_aware:
    "Recommendations always pass through Constraint Engine"
    rationale: "Don't suggest action that violates business rules"
## 14.3 Constraint Engine
constraint_engine:
  
  constraint_types:
    - business_rules ("don't email customer if opt-out")
    - regulatory ("comply with PDPL data handling")
    - safety ("don't auto-execute >$100M VND transactions")
    - operational ("don't run during business hours peak")
  
  validation_flow:
    1. Receive proposed action
    2. Load applicable constraints (tenant + global)
    3. Validate each constraint
    4. If any fail → block + explain
    5. If all pass → allow
  
  explainability:
    - "Why blocked": specific constraint name + reason
    - "How to fix": suggested modifications
    - "Override path": who can override + how

# Phần 15. Formula Library & Criteria Engine
## 15.1 Formula Library
formula_library:
  
  categories:
    
    customer_metrics:
      - LTV (Lifetime Value): multiple methods
      - CAC (Customer Acquisition Cost)
      - Churn Rate
      - Retention Rate
      - NPS / CSAT
      - RFM (Recency, Frequency, Monetary)
    
    revenue_metrics:
      - MRR / ARR
      - Revenue Growth Rate
      - Average Order Value
      - Revenue per Customer
    
    operational_metrics:
      - Conversion Rate
      - Cycle Time
      - Throughput
      - Error Rate
    
    financial_metrics:
      - Gross Margin
      - Burn Rate
      - Runway
      - Unit Economics
    
    forecasting:
      - Linear regression
      - Time series (ARIMA, Prophet)
      - ML-based (XGBoost on features)
  
  variants_per_tenant:
    "Same metric, different formula per industry"
    example:
      retail_LTV: "based on purchase frequency"
      saas_LTV: "based on subscription tenure × ARR"
      service_LTV: "based on contract value × renewal probability"
  
  validation:
    "All formulas validated using SymPy + Z3 for sanity"
    "Output range checked for plausibility"
## 15.2 Criteria Engine
criteria_engine:
  
  role: "When + how to apply formulas + insights"
  
  example_criteria:
    
    customer_at_risk:
      criteria: "RFM score < 30 OR churn_probability > 0.7"
      action: "trigger retention workflow"
    
    revenue_anomaly_alert:
      criteria: "daily_revenue zscore > 2.5 OR < -2.5"
      severity: "HIGH"
      action: "alert manager"
    
    upgrade_recommendation:
      criteria: "feature_usage_growth > 20% AND plan = BASIC"
      action: "recommend MID upgrade"
  
  per_tenant_customization:
    "Tenants can override criteria thresholds"
    "Saved as criteria_variants table"

# Phần 16. RAG Engine & Knowledge Graph
## 16.1 RAG Architecture
┌────────────────────────────────────────────────────────────┐
│ RAG ENGINE (L3b)                                           │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ KNOWLEDGE SOURCES                                   │   │
│  │  - Internal docs (uploaded by tenant)               │   │
│  │  - Industry knowledge (Kaori-curated)               │   │
│  │  - Vietnamese business law                          │   │
│  │  - Customer's previous decisions (memory)           │   │
│  └─────────────────────────────────────────────────────┘   │
│                       │                                    │
│                       ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ INGESTION                                           │   │
│  │  - Chunk documents (semantic + size-aware)          │   │
│  │  - Embed with sentence-transformers                 │   │
│  │  - Store in Pinecone (per-tenant namespace)         │   │
│  └─────────────────────────────────────────────────────┘   │
│                       │                                    │
│                       ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ RETRIEVAL                                           │   │
│  │  - Query embedding                                  │   │
│  │  - Hybrid search (vector + keyword)                 │   │
│  │  - Re-rank with cross-encoder                       │   │
│  │  - Recency boost                                    │   │
│  │  - Tenant-scoped only                               │   │
│  └─────────────────────────────────────────────────────┘   │
│                       │                                    │
│                       ▼                                    │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ GROUNDING                                           │   │
│  │  - Pass relevant chunks to LLM as context           │   │
│  │  - Track citations                                  │   │
│  │  - Verify response cites actual sources             │   │
│  └─────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
## 16.2 Knowledge Graph
knowledge_graph:
  
  entities:
    - Customer (tenant's customers)
    - Product (tenant's products)
    - Workflow (tenant's workflows)
    - Insight (generated insights)
    - Person (org members)
  
  relationships:
    - Customer.bought_Product
    - Workflow.affects_KPI
    - Insight.generated_for_Customer
    - Person.owns_Workflow
  
  storage:
    phase_1: PostgreSQL (relational, simpler)
    phase_2: Neo4j or AWS Neptune (if graph queries grow)
  
  use_cases:
    - "Show all workflows affecting customer X"
    - "Find similar customers based on behavior"
    - "Trace insight back to source data"

# Phần 17. LLM Integration Patterns
## 17.1 LLM Adapter Pattern
class LLMAdapter(ABC):
    """Abstract LLM interface; switching providers = config change."""
    
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        pass

class AnthropicAdapter(LLMAdapter):
    def generate(self, prompt, model='claude-sonnet-4.0', **kwargs):
        return anthropic_client.messages.create(...)

class OpenAIAdapter(LLMAdapter):
    def generate(self, prompt, model='gpt-4', **kwargs):
        return openai_client.chat.completions.create(...)

class LLMRouter:
    """Routes calls to right adapter based on workflow's pinned version."""
    
    def call(self, pinned_version, prompt, **kwargs):
        adapter = self.get_adapter_for(pinned_version)
        return adapter.generate(prompt, model=pinned_version, **kwargs)
## 17.2 Cost Management
cost_controls:
  
  per_tenant_budget:
    daily_cap_vnd: tier-dependent
    monthly_cap_vnd: tier-dependent
    on_exceed: "halt new AI calls until billing reset"
  
  per_workflow_budget:
    cap_per_run_vnd: configurable
    on_exceed: "halt workflow run, send to DLQ"
  
  per_call_estimation:
    method: "token-based: input_tokens + output_tokens × rate"
    pre_call_estimate: yes
    block_if_estimate_exceeds_cap: yes
## 17.3 Drift Detection
(Detail in Workflow System v2.0 Phần 21)
drift_monitoring:
  daily_job:
    - Compare recent AI outputs to baseline distribution
    - Detect format/length/sentiment shifts
    - Alert if drift > threshold

# PART V — LAYER 4 (ORCHESTRATION + WORKFLOW)
# Phần 18. Workflow Engine Architecture (Temporal-based)
## 18.1 Why Temporal.io
temporal_rationale:
  
  problems_solved:
    - "Reliable execution: handles retries, timeouts, failures"
    - "Saga support: built-in compensation framework"
    - "State persistence: workflow state survives crashes"
    - "Long-running workflows: hours, days, weeks supported"
    - "Idempotency: framework-level guarantees"
    - "Distributed tracing: native OpenTelemetry"
  
  alternatives_considered:
    - "Custom workflow engine": rejected — too much undifferentiated heavy lifting
    - "Apache Airflow": rejected — designed for batch ETL, not transactional workflows
    - "AWS Step Functions": rejected — vendor lock-in, not Vietnam-region
    - "Camunda": considered — heavy Java, BPMN-centric (overkill for SME)
    - "Cadence": predecessor of Temporal, less mature now
  
  decision: "Temporal — see ADR-002"
## 18.2 Architecture
┌────────────────────────────────────────────────────────────┐
│ WORKFLOW ENGINE (L4)                                       │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ TEMPORAL CLUSTER                                     │  │
│  │  - Frontend (gRPC API)                               │  │
│  │  - History service                                   │  │
│  │  - Matching service                                  │  │
│  │  - Worker pool                                       │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                 │
│                          ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ WORKFLOW DEFINITIONS                                 │  │
│  │  - Stored in Postgres (Kaori's DB)                   │  │
│  │  - Translated to Temporal workflow code at runtime   │  │
│  │  - One Temporal workflow type per Kaori workflow ID  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                 │
│                          ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ WORKERS                                              │  │
│  │  - Python worker pool                                │  │
│  │  - Each worker handles activities (= node executions)│  │
│  │  - Auto-scaled based on queue depth                  │  │
│  └──────────────────────────────────────────────────────┘  │
│                          │                                 │
│                          ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ ACTIVITY EXECUTION                                   │  │
│  │  - Each node = 1 activity                            │  │
│  │  - Activities run in worker (isolated)               │  │
│  │  - Heartbeating for long-running                     │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
## 18.3 Translation: Kaori Workflow → Temporal Workflow
# Conceptual translation
@workflow.defn
class KaoriWorkflowExecutor:
    
    @workflow.run
    async def run(self, kaori_workflow_id: str, trigger_data: dict):
        workflow_def = await workflow.execute_activity(
            load_workflow_definition,
            kaori_workflow_id,
            schedule_to_close_timeout=timedelta(seconds=10)
        )
        
        execution_state = ExecutionState(trigger_data)
        
        for node in workflow_def.execution_order:
            # Each node = 1 activity
            activity_options = ActivityOptions(
                start_to_close_timeout=timedelta(seconds=node.timeout),
                retry_policy=node.retry_policy,
                heartbeat_timeout=timedelta(seconds=30) if node.long_running else None,
            )
            
            try:
                result = await workflow.execute_activity(
                    execute_node_activity,
                    args=[node, execution_state],
                    **activity_options
                )
                execution_state.add_result(node.id, result)
            except Exception as e:
                if workflow_def.reliability.saga_enabled:
                    await self.execute_compensations(execution_state)
                raise
        
        return execution_state.final_output
## 18.4 Multi-Tenancy at Workflow Engine
multi_tenancy:
  
  task_queue_per_tenant: optional (for large tenants)
  task_queue_shared: default for cost efficiency
  
  tenant_context_propagation:
    "Every activity carries tenant_id"
    "Set in DB session (RLS), in span attributes, in logs"
  
  resource_limits_per_tenant:
    - "Max concurrent workflow executions: tier-dependent"
    - "Max history per workflow: 50K events"
    - "Workflow run timeout: 24 hours default"

# Phần 19. Workflow Builder Architecture
## 19.1 Frontend Architecture
frontend:
  
  framework: React 18 + TypeScript
  state: Redux Toolkit
  routing: React Router
  
  workflow_builder:
    canvas: React Flow (commercial license for Phase 1)
    properties_panel: custom forms
    node_palette: searchable, filtered by tier
    minimap: built-in React Flow
    auto_layout: dagre.js for tree layouts
  
  performance:
    canvas_target: 60fps for ≤100 nodes
    optimization:
      - virtualized rendering for large workflows
      - memoized node components
      - debounced auto-save (30s)
## 19.2 Backend API
# Workflow CRUD
GET    /api/v1/workflows                  # list user's workflows
POST   /api/v1/workflows                  # create workflow
GET    /api/v1/workflows/:id              # get workflow detail
PUT    /api/v1/workflows/:id              # update workflow (creates new version)
DELETE /api/v1/workflows/:id              # archive workflow

# Workflow execution
POST   /api/v1/workflows/:id/execute      # trigger execution
GET    /api/v1/workflows/:id/runs         # list runs
GET    /api/v1/workflows/:id/runs/:run_id # get run detail with trace

# Workflow lifecycle
POST   /api/v1/workflows/:id/promote-to-testing
POST   /api/v1/workflows/:id/promote-to-active
POST   /api/v1/workflows/:id/rollback

# Validation
POST   /api/v1/workflows/validate         # validate before save

# Templates
GET    /api/v1/templates
POST   /api/v1/templates/:id/instantiate

# Workflow as Code (MAX tier)
POST   /api/v1/workflows/import-yaml
GET    /api/v1/workflows/:id/export-yaml

# Phần 20. Action Runtime
## 20.1 Side-Effect Classification
(Detail in Workflow System v2.0 Phần 2.1)
Every node classified as: pure | read_only | write_idempotent | write_non_idempotent | external_irreversible
Action Runtime knows how to handle each class:
class ActionRuntime:
    
    def execute_node(self, node, input_data, execution_context):
        side_effect_class = node.side_effect_class
        
        if side_effect_class == 'pure':
            return self.execute_pure(node, input_data)
        
        elif side_effect_class == 'read_only':
            return self.execute_with_caching(node, input_data)
        
        elif side_effect_class == 'write_idempotent':
            return self.execute_with_idempotency_key(node, input_data, execution_context)
        
        elif side_effect_class == 'write_non_idempotent':
            return self.execute_with_strict_idempotency_lock(node, input_data, execution_context)
        
        elif side_effect_class == 'external_irreversible':
            return self.execute_with_provider_dedup(node, input_data, execution_context)
## 20.2 External Adapter Pattern
class ExternalServiceAdapter(ABC):
    """One adapter per external service (SendGrid, Twilio, Zalo, etc.)"""
    
    @abstractmethod
    def execute(self, params, idempotency_key): ...
    
    @abstractmethod
    def supports_idempotency(self) -> bool: ...
    
    @abstractmethod
    def get_compensation_action(self) -> str: ...

class SendGridAdapter(ExternalServiceAdapter):
    def execute(self, params, idempotency_key):
        return sendgrid.send(
            **params,
            unique_id=idempotency_key  # SendGrid supports server-side dedup
        )
    
    def supports_idempotency(self) -> bool:
        return True
    
    def get_compensation_action(self) -> str:
        return "send_retraction_email"

# Phần 21. State Machines & Workflow Lifecycle
(Full detail in Workflow System v2.0 PART III)
8 Workflow States:
1. DRAFT
2. REVIEWING
3. ACTIVE_BASELINE (60-day monitoring)
4. EVALUATING (Meeting #1)
5. PROPOSED_NEW
6. TESTING (90-day parallel)
7. APPROVED_REPLACEMENT
8. ARCHIVED
## 21.1 State Machine Implementation
class WorkflowStateMachine:
    
    ALLOWED_TRANSITIONS = {
        'DRAFT': ['REVIEWING'],
        'REVIEWING': ['DRAFT', 'ACTIVE_BASELINE', 'REJECTED'],
        'ACTIVE_BASELINE': ['EVALUATING', 'DEPRECATED'],
        'EVALUATING': ['ACTIVE_BASELINE', 'PROPOSED_NEW'],
        'PROPOSED_NEW': ['DRAFT', 'TESTING', 'REJECTED'],
        'TESTING': ['DRAFT', 'APPROVED_REPLACEMENT', 'REJECTED'],
        'APPROVED_REPLACEMENT': ['ACTIVE_BASELINE'],  # auto
        'ARCHIVED': []  # terminal
    }
    
    def transition(self, workflow_id, target_state, actor, reason):
        current = self.get_current_state(workflow_id)
        
        if target_state not in self.ALLOWED_TRANSITIONS[current]:
            raise InvalidTransition(f"{current} → {target_state}")
        
        # Validate prerequisites
        self.validate_prerequisites(workflow_id, current, target_state)
        
        # Validate actor permissions
        self.validate_authority(actor, current, target_state)
        
        # Execute transition with side effects
        self.execute_transition_side_effects(workflow_id, current, target_state)
        
        # Record state change (immutable audit)
        self.record_state_history(workflow_id, current, target_state, actor, reason)

# PART VI — LAYER 4.5 (ORG INTELLIGENCE — NEW v2.0)
# Phần 22. Process Mining Engine Architecture
## 22.1 Module Structure
process_mining/
├── connectors/           # Event log source connectors
│   ├── db_log_connector.py
│   ├── excel_history_connector.py
│   ├── zalo_metadata_connector.py
│   ├── email_metadata_connector.py
│   └── ...
├── ingestion/
│   ├── normalizer.py     # Common event log schema
│   ├── pii_filter.py     # Privacy-respecting filter
│   └── tenant_tagger.py
├── analysis/
│   ├── case_inferer.py   # Group events into cases
│   ├── sequence_miner.py # Heuristic + Inductive miners
│   ├── bottleneck_detector.py
│   ├── shadow_detector.py
│   └── conformance_analyzer.py
├── translation/
│   ├── builder_yaml_generator.py  # Output → Workflow Builder
│   └── findings_report_generator.py
└── api/
    └── mining_api.py     # REST endpoints
## 22.2 Mining Session Lifecycle
session_lifecycle:
  
  step_1_define_scope:
    inputs:
      - tenant_id
      - sources_to_include
      - time_range
      - department_filter (optional)
    
  step_2_extract_events:
    - call relevant connectors
    - normalize to common schema
    - filter PII
    - tag with tenant_id
    - store in mining_events table
    
  step_3_infer_cases:
    - group events by case_id (explicit or inferred)
    - estimated 5-30 min for typical SME
    
  step_4_run_miner:
    algorithm: heuristic_miner (default)
    output: process model + variants
    
  step_5_detect_anomalies:
    - bottlenecks
    - shadow processes
    - approval bypasses
    - rework loops
    
  step_6_generate_findings_report:
    - human-readable findings
    - evidence citations
    - recommendations
    
  step_7_translate_to_builder:
    - generate workflow YAML
    - mark off-system steps
    - flag bottlenecks
    
  step_8_user_review:
    - UI for accepting/modifying findings
    - decisions stored
    
  step_9_workflow_creation:
    - workflow goes to DRAFT state
    - normal lifecycle from there
## 22.3 Storage
CREATE TABLE mining_sessions (
    session_id UUID PRIMARY KEY,
    tenant_id UUID,
    initiated_by UUID,
    initiated_at TIMESTAMPTZ,
    
    scope_config JSONB,
    
    events_extracted_count INTEGER,
    cases_inferred_count INTEGER,
    
    process_model JSONB,
    findings JSONB,
    
    status VARCHAR(20),  -- 'running' | 'complete' | 'failed'
    completed_at TIMESTAMPTZ,
    
    INDEX (tenant_id, initiated_at DESC)
);

CREATE TABLE mining_events (
    event_id UUID PRIMARY KEY,
    session_id UUID,
    tenant_id UUID,
    
    case_id VARCHAR(200),  -- inferred or explicit
    activity VARCHAR(200),
    timestamp TIMESTAMPTZ,
    actor VARCHAR(200),
    
    source_type VARCHAR(50),
    source_record_id VARCHAR(500),
    
    attributes JSONB,
    pii_redacted BOOLEAN,
    
    INDEX (session_id, case_id, timestamp)
);

# Phần 23. Adoption Intelligence Architecture
## 23.1 Module Structure
adoption_intelligence/
├── collectors/
│   ├── workflow_event_collector.py  # subscribes to Workflow events
│   ├── user_action_collector.py     # tracks UI interactions
│   ├── chat_metadata_collector.py   # for side-channel detection
│   └── survey_collector.py
├── extractors/                      # one per signal type
│   ├── abandonment_extractor.py
│   ├── override_extractor.py
│   ├── side_channel_extractor.py
│   ├── workaround_extractor.py
│   └── ... (9 total)
├── scoring/
│   ├── adoption_health_score.py
│   └── trend_analyzer.py
├── intervention/
│   ├── auto_interventions.py        # in-product nudges
│   ├── csm_alerts.py                # alert CSM
│   └── effectiveness_tracker.py
└── api/
    └── adoption_api.py
## 23.2 Event Subscription Architecture
adoption_event_subscriptions:
  
  workflow_engine_topics:
    - workflow.execution_started
    - workflow.execution_completed
    - workflow.execution_failed
    - workflow.execution_abandoned (new event for adoption)
    - workflow.node_executed
    - workflow.ai_decision_overridden (new event)
  
  user_action_topics:
    - user.button_clicked
    - user.dwelled (long pause on UI)
    - user.exported_data
    - user.created_workaround_file
  
  chat_topics:
    - chat.message_metadata_received
  
  consumer_group: "adoption_intelligence_extractors"
  delivery: at-least-once
  parallelism: tenant-partitioned
## 23.3 Storage
CREATE TABLE adoption_signals (
    signal_id UUID PRIMARY KEY,
    tenant_id UUID,
    workflow_id UUID,
    signal_type VARCHAR(50),
    
    detection_window_start TIMESTAMPTZ,
    detection_window_end TIMESTAMPTZ,
    
    raw_value NUMERIC,
    normalized_value NUMERIC,
    severity VARCHAR(10),
    
    evidence JSONB,
    affected_actors JSONB,
    
    detected_at TIMESTAMPTZ,
    acknowledged BOOLEAN,
    intervention_taken JSONB,
    resolved BOOLEAN
);

CREATE TABLE adoption_health_scores (
    workflow_id UUID,
    tenant_id UUID,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    composite_score NUMERIC,  -- 0-100
    classification VARCHAR(20),  -- EXCELLENT / HEALTHY / AT_RISK / STRUGGLING / CRITICAL
    signal_breakdown JSONB,
    
    PRIMARY KEY (workflow_id, period_end)
);

# Phần 24. Operational Economics (NOV) Engine
## 24.1 Module Structure
operational_economics/
├── revenue_estimator/
│   ├── pre_post_method.py
│   ├── ab_attribution_method.py
│   ├── benchmark_method.py
│   └── kpi_to_revenue_mapper.py
├── cost_modeler/
│   ├── people_cost_estimator.py
│   ├── infra_cost_estimator.py
│   └── ai_cost_estimator.py
├── nov_engine/
│   ├── nov_calculator.py
│   ├── time_to_payback.py
│   └── variance_analyzer.py
├── reporting/
│   ├── manager_dashboard.py
│   └── cfo_summary.py
└── api/
    └── economics_api.py
## 24.2 Computation Pipeline
monthly_nov_pipeline:
  
  schedule: "First day of month, 02:00 Vietnam time"
  
  steps:
    1. for each tenant:
       2. for each active workflow:
          3. aggregate workflow metrics for month
          4. estimate revenue impact (Phần 43 of Workflow doc)
          5. compute cost impact (Phần 44 of Workflow doc)
          6. compose NOV
          7. compare to predicted (variance)
          8. update time-to-payback
          9. store in operational_economics_monthly
    10. for each tenant:
        11. aggregate department NOV summaries
        12. send manager email digest
## 24.3 Storage
CREATE TABLE operational_economics_monthly (
    workflow_id UUID,
    tenant_id UUID,
    period_month DATE,
    
    revenue_impact_vnd NUMERIC,
    revenue_impact_method VARCHAR(50),
    revenue_impact_confidence NUMERIC,
    
    people_cost_delta_vnd NUMERIC,
    infrastructure_cost_vnd NUMERIC,
    ai_call_cost_vnd NUMERIC,
    opportunity_cost_vnd NUMERIC,
    
    total_cost_vnd NUMERIC,
    nov_vnd NUMERIC,
    
    nov_predicted_vnd NUMERIC,
    variance_pct NUMERIC,
    
    cumulative_nov_vnd NUMERIC,
    time_to_payback_months NUMERIC,
    
    computed_at TIMESTAMPTZ,
    
    PRIMARY KEY (workflow_id, period_month)
);

# PART VII — LAYER 5 (USER LAYER)
# Phần 25. Web UI Architecture
## 25.1 Application Structure
web-app/
├── src/
│   ├── pages/
│   │   ├── Dashboard/         # Main landing
│   │   ├── WorkflowBuilder/   # Drag-drop builder
│   │   ├── WorkflowRuntime/   # Live execution view
│   │   ├── ProcessMining/     # Discovery UI
│   │   ├── Insights/          # Reasoning insights
│   │   ├── ROI/               # Operational economics
│   │   ├── Adoption/          # Adoption health
│   │   └── Settings/          # Tenant + user settings
│   ├── components/
│   │   ├── workflow/
│   │   ├── reports/
│   │   └── shared/
│   ├── store/                 # Redux Toolkit
│   ├── api/                   # API client (axios + react-query)
│   └── utils/
├── public/
└── package.json
## 25.2 Tech Stack Decisions
frontend_stack:
  framework: React 18
  language: TypeScript (strict mode)
  state: Redux Toolkit + RTK Query
  routing: React Router v6
  styling: Tailwind CSS + Headless UI
  forms: React Hook Form + Zod validation
  charts: Recharts (Phase 1) → D3 for advanced (Phase 2)
  workflow_canvas: React Flow (commercial for Phase 1)
  date_handling: date-fns
  i18n: react-i18next (Vietnamese primary, English secondary)
  testing: Vitest + React Testing Library + Playwright (E2E)
  build: Vite
## 25.3 Real-Time Features
realtime_architecture:
  
  websocket_use_cases:
    - "Live workflow execution updates"
    - "Real-time insight notifications"
    - "Collaborative editing" (Phase 2)
    - "Adoption alerts as they happen"
  
  implementation:
    backend: FastAPI WebSocket endpoint
    frontend: socket.io-client OR native WebSocket API
    auth: JWT in connection handshake
    scaling: Redis pub/sub for cross-pod broadcast
## 25.4 Performance Targets
ui_performance:
  initial_load_lcp: < 2.5s
  workflow_canvas_fps: > 30fps for ≤100 nodes
  api_response_perceived: < 1s for 95% requests
  build_bundle_size: < 400KB initial chunk
  
  optimizations:
    - code splitting per route
    - lazy loading workflow modules
    - service worker for offline read
    - image optimization (next-gen formats)

# Phần 26. Mobile + Zalo Bot
## 26.1 Mobile App (Phase 2)
mobile:
  framework: React Native (shared code with web)
  scope_phase_2:
    - View dashboards
    - Approve workflow actions
    - Receive notifications
    - View insights
  
  scope_phase_3:
    - Edit workflows (limited)
    - Process Mining review
    - Real-time runtime view
  
  vietnam_distribution:
    - Google Play (primary)
    - Apple App Store
    - Direct APK (some Vietnam SMEs prefer)
## 26.2 Zalo Bot (Phase 1 — CRITICAL for Vietnam)
zalo_bot:
  
  why_critical: "Zalo = primary biz tool in Vietnam"
  
  use_cases:
    - "Approve workflow steps"
    - "Receive notifications"
    - "Quick insight summaries"
    - "Side-channel detection (passive)"
  
  architecture:
    zalo_business_api: yes (requires Zalo Business account)
    bot_framework: custom Python on FastAPI
    state: Redis-cached conversation state
    fallback: web link if action complex
  
  example_flows:
    
    approval_flow:
      - System detects approval needed
      - Sends Zalo message with: details + Approve/Reject buttons
      - Manager taps Approve in Zalo
      - System confirms in Zalo + executes workflow
    
    notification_flow:
      - Insight generated
      - Sends Zalo summary with link to web for details
    
    daily_digest:
      - Sends Zalo at 8 AM with key metrics

# Phần 27. Notification & Alert Channels
## 27.1 Channel Matrix
notification_channels:
  
  email:
    use: "Detailed reports, weekly digests, formal alerts"
    provider: "SendGrid (primary), Amazon SES (fallback)"
    template_engine: MJML for responsive
  
  zalo:
    use: "Approvals, urgent alerts, quick updates (Vietnam)"
    detail: "Phần 26"
  
  in_app:
    use: "Real-time UI notifications"
    transport: WebSocket
  
  sms:
    use: "Critical alerts only (high cost)"
    provider: "Twilio (international) + Vietnamese SMS gateway"
  
  slack_teams:
    use: "Customers using Slack/Teams (Phase 2+)"
  
  webhook:
    use: "Customer's own integrations"
    delivery: at-least-once with retries
## 27.2 Notification Routing Logic
class NotificationRouter:
    
    def route(self, event: NotificationEvent):
        recipient_prefs = self.get_preferences(event.recipient)
        
        # User preferences override defaults
        for channel in recipient_prefs.preferred_channels:
            if self.is_appropriate(event.severity, channel):
                self.send_via(channel, event)
                
                if event.severity == 'CRITICAL':
                    # CRITICAL → all channels
                    continue
                else:
                    # Lower severity → first channel that works
                    return
## 27.3 Alert Fatigue Prevention
fatigue_prevention:
  
  digest_grouping:
    "Group similar non-urgent alerts into daily/weekly digest"
  
  rate_limiting:
    "Max 5 in-app notifications per hour per user"
    "Critical bypasses limit"
  
  intelligent_severity:
    "Demote severity if same alert fires repeatedly with no action"
  
  user_preferences:
    - "Mute specific types"
    - "Set quiet hours"
    - "Configure digest frequency"

# Phần 28. API Gateway & Public APIs
## 28.1 API Gateway Responsibilities
api_gateway:
  
  framework: FastAPI (Python 3.11+)
  responsibilities:
    - Authentication (JWT validation)
    - Authorization (RBAC enforcement)
    - Tenant context extraction
    - Rate limiting (per-tenant + per-IP)
    - Request logging (audit)
    - CORS handling
    - API versioning
    - Request/response transformation
  
  routes_pattern: "/api/v1/{layer}/{resource}/{action}"
  
  example_routes:
    /api/v1/workflows/...                    # L4
    /api/v1/data/...                         # L2
    /api/v1/reasoning/...                    # L3
    /api/v1/process-mining/...               # L4.5
    /api/v1/adoption/...                     # L4.5
    /api/v1/operational-economics/...        # L4.5
    /api/v1/users/...                        # User management
    /api/v1/tenants/...                      # Tenant management (admin)
## 28.2 Authentication Flow
User → Login (email + password OR SSO)
         ▼
     Auth Service validates
         ▼
     Returns JWT (15 min) + Refresh Token (7 days)
         ▼
User → API request with JWT in Authorization header
         ▼
     API Gateway:
       - Verify JWT signature
       - Check expiration
       - Extract user_id, tenant_id, roles
       - Set tenant context for downstream
         ▼
     Forward to backend service
         ▼
     Backend service:
       - Postgres connection: SET app.current_tenant_id
       - All queries auto-filtered by RLS
       - Return response
## 28.3 Rate Limiting
rate_limits:
  
  per_tenant:
    api_calls_per_minute: tier-dependent (60-1000)
    burst_allowance: 2x for short bursts
  
  per_user:
    api_calls_per_minute: 100
  
  per_ip:
    api_calls_per_minute: 200 (for non-authenticated routes)
    blocking_threshold: 1000/min (likely abuse)
  
  expensive_endpoints:
    process_mining_kickoff: 5 per day per tenant
    ai_insight_generation: tier-dependent quota

# PART VIII — CROSS-CUTTING CONCERNS
# Phần 29. Multi-Tenancy Architecture
## 29.1 Multi-Tenancy Strategy
(See ADR-004)
strategy: "Logical isolation via Row-Level Security (RLS)"
not: "Schema-per-tenant or DB-per-tenant"

rationale:
  pro_RLS:
    - Single DB to manage and backup
    - Easy cross-tenant analytics (admin)
    - Lower operational complexity
    - Cost-effective for SME scale
  
  con_RLS:
    - All tenants share resources (noisy neighbor)
    - One bug could leak (mitigation: continuous testing)
    - Heavy tenants impact others (mitigation: quotas)
  
  when_to_revisit:
    - Customer demands physical isolation (regulatory)
    - Scale exceeds single-DB capacity
    - Phase 3+ may introduce schema-per-tenant for whales
## 29.2 Implementation Layers
┌─────────────────────────────────────────────────────────────┐
│ NETWORK LAYER                                               │
│  - Subdomain per tenant: tenant_a.kaori.app                 │
│  - JWT contains tenant_id (server-validated)                │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ API GATEWAY                                                 │
│  - Extract tenant_id from JWT                               │
│  - Inject into request context (header)                     │
│  - Pass downstream                                          │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ APPLICATION LAYER                                           │
│  - Every service receives tenant_id                         │
│  - Sets DB session: SET app.current_tenant_id = '...'       │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ DATABASE LAYER                                              │
│  - RLS policies on every tenant-scoped table                │
│  - Queries auto-filter by tenant_id                         │
│  - Cannot select rows of other tenants                      │
└────────────────────────────┬────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ STORAGE LAYER                                               │
│  - MinIO bucket prefix per tenant                           │
│  - IAM policies enforce prefix access                       │
└─────────────────────────────────────────────────────────────┘
## 29.3 Continuous Testing
cross_tenant_leak_tests:
  
  ci_cd_tests:
    - "Setup 2 test tenants with distinct data"
    - "Login as tenant A → query → assert only A's data returned"
    - "Login as tenant A → workflow execution → assert only A's data accessed"
    - "Direct DB access without tenant context → assert error"
  
  production_monitoring:
    - "Audit log: track every cross-tenant access attempt (should be 0)"
    - "Alert if RLS policy is dropped or modified"
    - "Pen-testing quarterly"

# Phần 30. Security Architecture
## 30.1 Threat Model (STRIDE)
stride_analysis:
  
  spoofing:
    threat: "Attacker impersonates user"
    mitigation: 
      - JWT with strong signing (RS256)
      - Short expiration (15 min) + refresh tokens
      - MFA option (Phase 2)
  
  tampering:
    threat: "Modify data in transit or at rest"
    mitigation:
      - HTTPS everywhere
      - DB encryption at rest
      - Audit logs are append-only (immutable)
  
  repudiation:
    threat: "User denies action they took"
    mitigation:
      - Comprehensive audit logs
      - Cryptographically signed audit entries (Phase 2)
  
  information_disclosure:
    threat: "Unauthorized data access"
    mitigation:
      - Multi-tenancy (Phần 29)
      - Field-level encryption for PII
      - Secrets management (Vault)
  
  denial_of_service:
    threat: "Overwhelm system"
    mitigation:
      - Rate limiting (multi-level)
      - Per-tenant quotas
      - Auto-scaling
      - DDoS protection (Cloudflare or similar)
  
  elevation_of_privilege:
    threat: "User gains higher permissions"
    mitigation:
      - RBAC enforced at every layer
      - Least-privilege principle
      - Privileged actions require additional auth
## 30.2 Authentication & Authorization
authentication:
  
  user_login:
    primary: email + password
    sso_phase_2: 
      - Google Workspace
      - Microsoft Azure AD
      - SAML 2.0
    mfa_phase_2: TOTP, SMS
  
  password_policy:
    min_length: 12 characters
    complexity: required
    history: cannot reuse last 5
    rotation: 90 days for admin
    storage: bcrypt with cost factor 12
  
authorization:
  
  rbac_roles:
    - super_admin (Kaori internal only)
    - tenant_admin (full tenant control)
    - department_head
    - department_member
    - viewer (read-only)
    - automation_service (workflow execution role)
  
  permissions_per_role:
    "Defined in permissions.yaml, version controlled"
  
  resource_level:
    "Workflows have own permission lists per workflow"
    "Override role-based defaults"
## 30.3 Encryption
encryption:
  
  at_rest:
    db: 
      method: "AES-256 native Postgres encryption"
      key_management: "Vault KMS"
    object_storage:
      method: "MinIO server-side encryption"
    backups: "Encrypted before upload to offsite"
  
  in_transit:
    external: "TLS 1.3 minimum"
    internal: "mTLS in service mesh (Phase 2+)"
  
  field_level:
    pii_fields: "Encrypted with tenant-specific key (Phase 2)"
    examples: ["national_id", "bank_account"]
## 30.4 Compliance
compliance:
  
  vietnam_pdpl:
    - Data residency: Vietnam region
    - Consent management: explicit consent flows
    - Right to deletion: implemented (90 days)
    - Right to access: implemented (export API)
    - Data Processing Agreement (DPA): provided to customers
  
  iso_27001_phase_3:
    - Goal: certification by Year 2
    - Currently: implementing controls
  
  industry_specific:
    healthcare_phase_3: HIPAA-aligned (if expanding)
    finance: VN finance regulations

# Phần 31. Observability Architecture
## 31.1 Three Pillars
observability_pillars:
  
  metrics:
    tool: Prometheus + Grafana
    cardinality_strategy: "Per-tenant labels carefully"
    key_dashboards:
      - System Health (CPU, memory, disk per service)
      - Workflow Engine (executions, success rate, latency)
      - Reasoning Layer (AI calls, token usage, latency)
      - Adoption (signal counts, health scores)
      - Business (NOV totals, ROI dashboard)
  
  traces:
    tool: OpenTelemetry → Jaeger
    coverage: 100% of workflow runs (with sampling for high-volume)
    span_attributes: tenant_id, workflow_id, run_id, node_id
  
  logs:
    tool: Loki
    structured: JSON only
    correlation: trace_id + span_id in every log
    retention:
      hot: 14 days
      cold: 90 days
      archived: 1 year (S3)
## 31.2 SLI/SLO Architecture
slis_slos:
  
  api_availability:
    sli: "successful_requests / total_requests"
    slo: "99.9% (43 min downtime/month)"
  
  workflow_execution_success:
    sli: "successful_runs / total_runs"
    slo: "99.5%"
  
  api_latency:
    sli: "p95 latency"
    slo: "< 200ms for 95% of API calls"
  
  workflow_runtime:
    sli: "p95 workflow run duration"
    slo: "< 5 minutes for typical workflows"
  
  error_budget:
    "0.1% downtime budget per month"
    "Burning > 25% triggers slowdown of releases"

# Phần 32. Reliability Architecture
(Cross-references Workflow System v2.0 PART IX)
## 32.1 Reliability Patterns Summary
reliability_patterns:
  
  idempotency:
    layer: cross-cutting
    where: every node with side effects
    detail: Workflow doc Phần 32
  
  retry_with_backoff:
    layer: cross-cutting
    where: every external call
    library: tenacity (Python)
    detail: Workflow doc Phần 33
  
  saga_pattern:
    layer: workflow engine
    where: workflows with irreversible nodes
    framework: built into Temporal
    detail: Workflow doc Phần 34
  
  dead_letter_queue:
    layer: workflow engine + ingestion
    where: any async processing
    storage: Postgres dlq_messages table
    detail: Workflow doc Phần 35
  
  circuit_breaker:
    layer: external adapters
    where: LLM calls, external APIs
    library: pybreaker
  
  bulkhead:
    layer: resource pools
    where: per-tenant connection limits
  
  timeout:
    layer: every layer
    enforcement: at each integration boundary
## 32.2 Failure Recovery Matrix
                       Severity
                       ┌────────────┬────────────┬────────────┐
                       │  LOW       │ MEDIUM     │ HIGH       │
   Failure Type        ├────────────┼────────────┼────────────┤
                       │            │            │            │
   Single node retry   │ Auto retry │ Auto retry │ Auto retry │
                       │            │            │            │
   Workflow failure    │ DLQ        │ DLQ + Alert│ DLQ + Page │
                       │            │            │            │
   Service down        │ Failover   │ Failover   │ Failover   │
                       │            │            │ + Page     │
                       │            │            │            │
   DB failover         │ N/A        │ Auto       │ Page       │
                       │            │            │            │
   Region outage       │ N/A        │ N/A        │ DR plan    │
                       │            │            │ activated  │
                       └────────────┴────────────┴────────────┘

# Phần 33. Cost Management Architecture
## 33.1 Cost Tracking
cost_tracking:
  
  per_tenant_metrics:
    - api_calls_count (broken down by endpoint)
    - workflow_executions_count
    - ai_calls_count + cost_vnd
    - storage_gb
    - compute_hours
    - bandwidth_gb
    - support_hours
  
  storage:
    table: tenant_cost_ledger
    granularity: hourly aggregation
    retention: 5 years
  
  reporting:
    monthly: per-tenant cost breakdown
    real_time: tenant admin can see usage live
    forecast: projected next month based on trend
## 33.2 Cost Caps & Throttling
class CostGuardian:
    
    def check_before_expensive_action(self, tenant_id, estimated_cost_vnd):
        budget = self.get_remaining_budget(tenant_id)
        
        if estimated_cost_vnd > budget.daily_remaining:
            raise CostCapExceeded("Daily budget exhausted")
        
        if estimated_cost_vnd > budget.monthly_remaining:
            raise CostCapExceeded("Monthly budget exhausted")
        
        return True
    
    def record_actual_cost(self, tenant_id, actual_cost_vnd):
        self.cost_ledger.add(tenant_id, actual_cost_vnd, now())
        
        if self.is_at_warning_threshold(tenant_id):
            self.notify_tenant_admin('80% budget consumed')

# Phần 34. Audit & Compliance
## 34.1 Audit Logging
audit_logging:
  
  events_logged:
    - User login/logout
    - Tenant admin actions
    - Workflow CRUD
    - Workflow state transitions
    - Permission changes
    - Secret access
    - Data export
    - Cross-tenant access attempts (should be 0)
  
  storage:
    table: audit_log (append-only)
    immutability: 
      "DB-level: no UPDATE/DELETE permissions on audit table"
      "Phase 2: cryptographic hash chain (each entry references previous)"
    retention: 7 years
    
  format:
    timestamp: TIMESTAMPTZ
    actor: user_id OR service_id
    actor_type: USER | SERVICE | SYSTEM
    action: VARCHAR
    resource: VARCHAR
    resource_id: VARCHAR
    tenant_id: UUID
    result: SUCCESS | FAILURE
    metadata: JSONB
    ip_address: INET
    user_agent: TEXT
## 34.2 Compliance Reporting
compliance_reports:
  
  monthly:
    - Failed login attempts summary
    - Permission changes
    - Secret access patterns
    - Cross-tenant attempts (should be 0)
  
  quarterly:
    - Penetration test results
    - Vulnerability scan results
    - Compliance checklist review
  
  annual:
    - Full security audit
    - DR drill results
    - SOC 2 audit (Phase 3)

# PART IX — INTEGRATION & DATA FLOW
# Phần 35. Inter-Layer API Contracts
## 35.1 Contract Registry
api_contracts:
  
  format: OpenAPI 3.1 (REST) + JSON Schema (events)
  versioning: URL-based (/api/v1, /api/v2)
  storage: docs/api-contracts/ in monorepo
  validation:
    - "Pre-commit hook validates contracts"
    - "CI runs contract tests"
    - "Breaking changes require explicit version bump"
  
  contract_examples:
    L4_to_L3: "Workflow nodes → Reasoning Layer"
    L4_to_L2: "Workflow → Data Plane queries"
    L4_to_L4_5: "Workflow events → Adoption / Economics observers"
    L5_to_L4: "User UI → Workflow API"
    L5_to_L3: "User UI → Insights API"
## 35.2 Key Contract Examples
# Contract: L4 (Workflow) → L3 (Reasoning) — Insight Generation

POST /api/v1/reasoning/insights/generate
request:
  tenant_id: UUID (required)
  insight_type: enum [anomaly, trend, pattern, ...]
  focus_metric: string (required)
  data_window: {start: timestamp, end: timestamp}
  context:
    workflow_id: UUID
    workflow_run_id: UUID
    profile_id: UUID
    active_criteria_ids: [UUID]
    active_formulas_ids: [UUID]
  llm_pinned_version: string (required)  # critical for stability
  cost_cap_vnd: numeric (optional)

response_200:
  insight_id: UUID
  insight: {...structured insight...}
  confidence: number 0-1
  explainability:
    executive: string (1-2 sentences)
    analyst: string (technical detail)
    auditor: string (data sources + method)
  citations: [{...}]
  llm_version_used: string
  cost_vnd: numeric
  computed_at: timestamp

response_429:
  error: cost_cap_exceeded | rate_limit_exceeded
  retry_after_seconds: integer
# Contract: Event Schema — Workflow Execution Events

event: workflow.execution_started
schema:
  event_id: UUID
  event_type: "workflow.execution_started"
  tenant_id: UUID
  workflow_id: UUID
  workflow_run_id: UUID
  started_at: timestamp
  trigger:
    type: enum
    actor: UUID or "system"
  workflow_version: integer

event: workflow.node_executed
schema:
  event_id: UUID
  event_type: "workflow.node_executed"
  tenant_id: UUID
  workflow_id: UUID
  workflow_run_id: UUID
  node_id: string
  node_type: string
  side_effect_class: enum
  status: success | failure
  duration_ms: integer
  cost_vnd: numeric
  retry_attempt: integer
  trace_id: UUID

event: workflow.execution_abandoned (NEW v2.0)
schema:
  event_id: UUID
  event_type: "workflow.execution_abandoned"
  tenant_id: UUID
  workflow_id: UUID
  workflow_run_id: UUID
  abandoned_at_node: string
  reason_inferred: enum [timeout, no_user_action, manual_quit]
  user_id: UUID

# Phần 36. Event Schemas & Topics
## 36.1 Topic Naming Convention
topic_pattern: "tenant.{tenant_id}.{domain}.{event_type}"

domains:
  - data        # data plane events
  - reasoning   # AI events
  - workflow    # workflow lifecycle + execution
  - adoption    # adoption signals
  - economics   # NOV events
  - audit       # cross-cutting audit

examples:
  - tenant.abc.workflow.execution_started
  - tenant.abc.adoption.override_detected
  - tenant.abc.economics.monthly_nov_computed
  - tenant.abc.data.silver_record_updated
  - tenant.abc.audit.cross_tenant_attempt  # alarming
## 36.2 Event Versioning
event_versioning:
  
  schema_evolution_strategy:
    additive_only: "New fields default to null/zero"
    breaking_changes: "Bump version (event_type.v2)"
    coexistence: "v1 and v2 consumers can run in parallel"
  
  schema_registry:
    storage: Postgres schemas table
    enforcement: producers MUST specify schema_version
    validation: consumers can specify min_version they support

# Phần 37. End-to-End Data Flow Examples
## 37.1 Example 1: Customer Onboarding Workflow Run
1. TRIGGER (User Action / API)
   New customer signs up → API call to /api/v1/customers
   ↓
2. INGESTION (L1 → L2)
   Customer record → silver.customers (with tenant_id)
   ↓
3. EVENT (L2)
   Event: tenant.abc.data.customer_created → Redis Stream
   ↓
4. WORKFLOW TRIGGER (L4)
   Workflow "customer_onboarding" subscribes to event
   Temporal kicks off workflow run (workflow_run_id = wr_123)
   ↓
5. NODE 1: Read customer (read_only)
   Workflow Engine queries silver.customers (RLS auto-filters by tenant)
   ↓
6. NODE 2: Generate welcome content (AI - read_only)
   Workflow Engine calls L3 Reasoning Layer:
     POST /api/v1/reasoning/insights/generate
     Including: customer profile, llm_pinned_version
   L3 calls Anthropic Claude API
   Returns: personalized welcome content + citations
   ↓
7. NODE 3: Send email (external_irreversible)
   Action Runtime:
     - Generate idempotency_key (customer_id + workflow_run_id + node_id)
     - Check if already sent (no)
     - Call SendGrid with idempotency_key
     - Record success in idempotency store
   ↓
8. NODE 4: Save to onboarding_log (write_idempotent)
   Action Runtime:
     - Upsert to silver.onboarding_log with key (customer_id, run_id)
   ↓
9. WORKFLOW COMPLETE
   Event: tenant.abc.workflow.execution_completed
   ↓
10. ADOPTION INTELLIGENCE (L4.5)
    Adoption observer subscribes to execution_completed event
    Updates adoption signals (no abandonment, etc)
    ↓
11. OPERATIONAL ECONOMICS (L4.5)
    Economics tracker records:
      - cost: AI call + SendGrid + infra
      - revenue impact (deferred to monthly aggregation)
    ↓
12. TRACE STORAGE (L0)
    Full distributed trace stored in Jaeger
    Available for debugging + analytics
    ↓
13. UI UPDATE (L5)
    WebSocket broadcasts execution_completed
    User dashboard shows: "Welcome email sent to John Doe"
## 37.2 Example 2: Process Mining Discovery Session
1. INITIATION
   Tenant admin clicks "Discover My Workflows"
   POST /api/v1/process-mining/start
   ↓
2. SCOPE DEFINITION
   System asks: which sources, which time range, which department?
   User selects: Postgres CRM logs, last 6 months, Sales department
   ↓
3. EVENT EXTRACTION (L4.5 Process Mining → L1 Connectors)
   Process Mining Engine calls connectors:
     - postgres_log_connector for CRM events
     - excel_history_connector for Sales Excel files
     - zalo_metadata_connector for sales chats (with consent)
   
   ~50K events extracted, normalized
   ↓
4. PII FILTERING & TENANT TAGGING
   PII redacted (names → roles, contact details masked)
   All events tagged tenant_id
   Stored in mining_events table
   ↓
5. CASE INFERENCE
   Process Mining Engine groups events into cases:
     - 247 sales cases inferred (lead_id as anchor)
   ↓
6. SEQUENCE MINING
   Heuristic miner processes cases
   Generates process model with main variant + 2 alternates
   ↓
7. ANOMALY DETECTION
   Detects:
     - Bottleneck: Sales notification delay (avg 2.3h)
     - Off-system: Quote sent via Zalo (73% of cases)
     - Bypass: 18% of cases skip approval
   ↓
8. FINDINGS REPORT
   Generated with evidence, recommendations
   ↓
9. WORKFLOW YAML GENERATION
   Process Mining → Workflow Builder format
   Off-system steps marked with discovery_flags
   ↓
10. USER REVIEW
    UI shows process map + findings + draft workflow
    User makes decisions:
      - Integrate Zalo into workflow: YES
      - Block approval bypasses for high-value: YES
      - Add real-time notification: YES
    ↓
11. WORKFLOW CREATION
    Workflow created in DRAFT state
    User reviews → submits for review
    ↓
12. NORMAL LIFECYCLE
    Workflow goes through REVIEWING → ACTIVE_BASELINE → 60-day monitoring
## 37.3 Example 3: Monthly NOV Computation
1. SCHEDULER (cron job, day 1 of month, 02:00)
   Triggers: nov_monthly_computation
   ↓
2. ITERATE TENANTS
   For each active tenant:
     ↓
3. ITERATE WORKFLOWS
   For each ACTIVE_BASELINE workflow:
     ↓
4. AGGREGATE METRICS (L4.5 reads from L4 traces + L2 data)
   - Total executions in month
   - Success rate
   - Total runtime cost
   - AI costs from L3 ledger
   - Manual interventions
   ↓
5. ESTIMATE REVENUE IMPACT
   - Identify affected KPIs
   - Pre/post comparison method
   - Or A/B if in TESTING phase
   - Or benchmark fallback if new
   ↓
6. COMPUTE NOV
   nov = revenue_impact - (people_cost + infra_cost + ai_cost)
   ↓
7. COMPUTE TIME-TO-PAYBACK
   cumulative_nov vs setup_cost
   ↓
8. STORE IN operational_economics_monthly
   ↓
9. EVENT: economics.monthly_nov_computed
   ↓
10. EMAIL DIGEST
    Generate manager email with key metrics
    Send via L5 notification channels
    ↓
11. UPDATE DASHBOARDS
    Manager dashboard refreshes
    CFO summary updated

# Phần 38. External Integration Patterns
## 38.1 Integration Patterns
integration_patterns:
  
  pattern_pull_polling:
    description: "Kaori pulls from external API at intervals"
    when: "External doesn't support webhooks"
    rate_limit_aware: yes
    backoff_on_errors: yes
  
  pattern_pull_cdc:
    description: "Kaori reads DB change logs directly"
    when: "Customer hosts own DB and gives Kaori read access"
    consistency: high (real-time)
    setup: requires DBA permission
  
  pattern_push_webhook:
    description: "External pushes events to Kaori"
    when: "Provider supports webhooks"
    security:
      - HMAC signature validation
      - Idempotency keys
      - IP allowlist (optional)
  
  pattern_push_outbound_webhook:
    description: "Kaori pushes events to customer's systems"
    when: "Customer wants real-time integration"
    delivery: at-least-once with retries
    customer_endpoint_security: customer's responsibility
  
  pattern_oauth_app:
    description: "Customer authorizes Kaori as OAuth app"
    when: "Google Workspace, Microsoft 365, Salesforce"
    token_management: refresh tokens stored in Vault
    scopes: minimal necessary
## 38.2 Integration Resilience
external_integration_resilience:
  
  connection_pooling: per integration, with limits
  circuit_breaker: per integration, opens on failure spike
  timeout: aggressive (5-30s based on integration)
  retry: exponential backoff with jitter
  fallback: cached data OR manual trigger
  monitoring: per-integration health dashboard
  alerting: provider down → alert customer + Kaori team

# PART X — DEPLOYMENT ARCHITECTURE
# Phần 39. Kubernetes Layout
## 39.1 Namespace Strategy
namespaces:
  
  kaori-platform:
    purpose: "Application services (FastAPI apps, workers)"
    pods:
      - api-gateway
      - workflow-engine-frontend
      - reasoning-layer
      - process-mining-engine
      - adoption-intelligence
      - operational-economics
      - notification-service
      - websocket-server
  
  kaori-data:
    purpose: "Data plane services"
    pods:
      - silver-promotion-worker
      - gold-aggregator
      - feature-store-server
      - data-quality-runner
  
  kaori-ingestion:
    purpose: "Connectors and ingestion workers"
    pods:
      - connector-workers (one per connector type)
      - cdc-runners
      - webhook-receivers
      - schedulers
  
  kaori-temporal:
    purpose: "Temporal cluster"
    pods:
      - temporal-frontend
      - temporal-history
      - temporal-matching
      - temporal-worker (auto-scaled pool)
  
  kaori-infra:
    purpose: "Self-managed infrastructure"
    pods:
      - postgres-cluster (CloudNativePG)
      - clickhouse-cluster
      - redis-cluster
      - minio-cluster
      - vault
  
  kaori-observability:
    purpose: "Observability stack"
    pods:
      - prometheus
      - grafana
      - jaeger
      - loki
  
  kaori-tenant-isolation: (Phase 2+)
    purpose: "Per-large-tenant isolation"
    pods: created on-demand for whales
## 39.2 Resource Allocation
resource_allocation:
  
  api_gateway:
    replicas: 3
    resources: {cpu: 1, memory: 2Gi}
    autoscaling: HPA (min 3, max 20)
  
  reasoning_layer:
    replicas: 3
    resources: {cpu: 2, memory: 4Gi}
    autoscaling: HPA (min 3, max 30) — high variability
  
  workflow_engine_frontend:
    replicas: 3
    resources: {cpu: 1, memory: 2Gi}
  
  workflow_workers:
    replicas: 5 (start)
    resources: {cpu: 2, memory: 4Gi}
    autoscaling: HPA based on Temporal queue depth
  
  postgres:
    replicas: 3 (1 primary + 2 replicas)
    resources: {cpu: 4, memory: 16Gi}
    storage: 500GB SSD (scalable)
  
  clickhouse:
    replicas: 3 (sharded + replicated)
    resources: {cpu: 4, memory: 16Gi}
    storage: 1TB SSD (scalable)

# Phần 40. Vietnam Region Hosting
## 40.1 Why Vietnam Region
vietnam_hosting_rationale:
  
  data_residency:
    - Vietnam PDPL compliance
    - Customer comfort (data stays in country)
    - Government RFP requirements (some)
  
  latency:
    - Sub-50ms to most Vietnam customers
    - Critical for real-time workflow execution
  
  cost:
    - Vietnam IDC pricing competitive vs hyperscalers
    - No cross-border data transfer fees
  
  partnerships:
    - FPT Cloud, Viettel IDC: relationship advantage
    - Local support + Vietnamese language
## 40.2 Provider Selection
provider_evaluation:
  
  fpt_cloud:
    pros: largest, mature, good API
    cons: pricing tiers complex
  
  viettel_idc:
    pros: government-friendly, broad reach
    cons: Kubernetes maturity questionable
  
  vnpt:
    pros: nationwide infra
    cons: less developer-friendly
  
  decision: "Primary: FPT, secondary: Viettel"
  rationale: "Multi-provider for resilience + leverage"
## 40.3 Multi-Region (Future)
multi_region_strategy:
  
  phase_1: single region (HCMC primary, DR in Hanoi)
  
  phase_2: 
    - Active-passive: HCMC active, Hanoi standby
    - DR drill quarterly
  
  phase_3:
    - Active-active across HCMC + Hanoi
    - SEA expansion: Singapore for international customers

# Phần 41. CI/CD Pipeline
## 41.1 Pipeline Architecture
┌──────────────────────────────────────────────────────────────┐
│ DEVELOPER WORKFLOW                                           │
│                                                              │
│   Local dev → Git push to feature branch                     │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ CI (GitHub Actions)                                          │
│  - Lint (ruff, mypy)                                         │
│  - Unit tests                                                │
│  - Integration tests                                         │
│  - Architecture tests (boundary checks)                      │
│  - Security scan (snyk, trivy)                               │
│  - Multi-tenancy leak tests                                  │
│  - Build container images                                    │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ CD - STAGING (auto on merge to develop)                      │
│  - Deploy to staging cluster                                 │
│  - Run smoke tests                                           │
│  - Run E2E tests (Playwright)                                │
│  - Performance regression checks                             │
└────────────────────────────┬─────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────┐
│ CD - PRODUCTION (manual gate after staging passes)           │
│  - Canary deployment (5% traffic)                            │
│  - Monitor for 1 hour                                        │
│  - If healthy → 50% → 100%                                   │
│  - Auto-rollback on error spike                              │
└──────────────────────────────────────────────────────────────┘
## 41.2 Branch Strategy
branch_strategy: trunk-based
  
  main: always deployable
  feature_branches: short-lived (< 3 days)
  release_tagging: semantic versioning
  hotfix_branches: from main, merge back fast

# Phần 42. Disaster Recovery & Backup
## 42.1 RPO/RTO Targets
disaster_recovery:
  
  rpo (recovery point objective):
    transactional_data: 5 minutes (continuous WAL)
    analytical_data: 1 hour (batch)
    object_storage: 24 hours
  
  rto (recovery time objective):
    p1_complete_outage: 4 hours
    p2_partial_outage: 1 hour
    p3_single_service: 15 minutes
## 42.2 Backup Strategy
backup_strategy:
  
  databases:
    postgres:
      method: WAL archiving + daily full backup
      retention: 30 days hot, 1 year cold
      destination: MinIO (Vietnam) + offsite encrypted
    
    clickhouse:
      method: snapshot daily
      retention: 90 days
    
    redis:
      method: AOF + RDB snapshots
      note: not for primary data, just cache
  
  object_storage:
    minio:
      method: cross-region replication
      destination: Hanoi backup region
  
  configuration:
    method: Git (everything as code)
    backup: monorepo backed up to GitHub + GitLab
## 42.3 DR Drill Schedule
dr_drills:
  
  quarterly:
    - Postgres failover (primary → replica)
    - Restore from backup test
  
  bi_annually:
    - Full region failover (HCMC → Hanoi)
    - End-to-end recovery
  
  annually:
    - Complete infrastructure rebuild from scratch
    - Time: max 8 hours target

# PART XI — NON-FUNCTIONAL REQUIREMENTS
# Phần 43. Performance Targets
performance_targets:
  
  api_response_time:
    p50: < 100ms
    p95: < 200ms
    p99: < 500ms
  
  workflow_execution:
    typical_workflow: < 5 minutes p95
    long_running: < 1 hour p95
    timeout: 24 hours (configurable)
  
  ai_insight_generation:
    sync_call: < 3 seconds p95
    async_call: < 30 seconds p95
  
  process_mining_session:
    typical (50K events): < 10 minutes
    large (500K events): < 60 minutes
  
  ui_responsiveness:
    page_load (LCP): < 2.5s
    canvas_fps: > 30fps
    websocket_latency: < 100ms

# Phần 44. Scalability Architecture
## 44.1 Horizontal Scaling Strategy
scaling_axes:
  
  api_layer:
    method: HPA on CPU + custom metrics
    bottleneck: rate limit on backend services
  
  workflow_workers:
    method: HPA on Temporal queue depth
    bottleneck: external API rate limits
  
  data_processing:
    method: partitioning + parallel workers
    bottleneck: DB write throughput
  
  ai_calls:
    method: multiple LLM provider keys + load balancing
    bottleneck: provider rate limits
## 44.2 Capacity Planning
capacity_milestones:
  
  phase_1_target: 50 customers, 5K workflows
  phase_2_target: 250 customers, 25K workflows
  phase_3_target: 1000 customers, 100K workflows
  
  scaling_triggers:
    db_cpu_sustained_70: scale up DB
    queue_depth_sustained_1000: scale workers
    p95_latency_above_target: investigate + scale
    cost_per_tenant_growing: optimize

# Phần 45. Availability & SLA
availability_targets:
  
  internal_slos:
    api_availability: 99.9% (43 min downtime/month)
    workflow_engine_availability: 99.9%
    data_freshness_silver: < 5 min lag
  
  customer_facing_sla:
    pilot: best effort
    basic: 99.5% (3.6 hrs/month)
    mid: 99.9% (43 min/month)
    max: 99.95% (22 min/month) + financial credits
  
  scheduled_maintenance:
    window: Sunday 02:00-04:00 Vietnam time
    advance_notice: 7 days minimum
    customer_can_opt_out: max tier only

# Phần 46. Security Requirements
security_requirements:
  
  authentication:
    - JWT with strong signing (RS256)
    - Token expiry: 15 min access, 7 days refresh
    - MFA option (Phase 2)
    - SSO (Phase 2)
  
  authorization:
    - RBAC at every layer
    - Resource-level overrides
    - Least privilege principle
  
  data_protection:
    - Encryption at rest (DB, storage)
    - Encryption in transit (TLS 1.3)
    - PII redaction in logs
    - Secrets in Vault only
  
  network:
    - VPC isolation
    - Network policies (Calico)
    - WAF (Phase 2)
    - DDoS protection
  
  audit:
    - Comprehensive audit log
    - Immutable trail
    - Retention 7 years
  
  compliance:
    - Vietnam PDPL
    - ISO 27001 (Phase 3 cert)
    - Annual penetration testing

# Phần 47. Maintainability & Evolution
maintainability:
  
  code_quality:
    - Type hints everywhere (mypy strict)
    - Linting (ruff) + formatting (black)
    - Docstrings for public APIs
    - 80%+ unit test coverage target
  
  architecture_evolution:
    - ADRs for significant decisions
    - Quarterly architecture reviews
    - Tech debt tracked + prioritized
    - Refactoring budget: 20% of engineering time
  
  documentation:
    - SAD (this doc)
    - Layer docs (deep dives)
    - API docs (auto-generated from OpenAPI)
    - Runbooks for operations
    - Onboarding guide
  
  vendor_independence:
    - Adapter pattern for vendors
    - Multi-provider fallbacks (LLM)
    - Self-hosted alternatives identified

# PART XII — ARCHITECTURE DECISION RECORDS (ADRs)
# Phần 48. ADR-001: Modular Monolith → Microservices Evolution
## Context
Phase 1 cần ship trong 4 tháng với team 6-8 engineers. Kaori AI là hệ thống nhiều layer phức tạp (data plane, AI, workflow, process mining, adoption, economics). Câu hỏi: bắt đầu monolith hay microservices?
## Decision
Phase 1: Modular Monolith — single deployable, modules với boundary chặt. Phase 2 (month 7-12): Selective extraction — workflow engine + process mining tách ra microservice. Phase 3 (Year 2): Full microservices — mỗi layer = 1+ service.
## Rationale
### Tại sao không microservices từ đầu
microservices_costs_for_small_team:
  - Distributed tracing complexity tăng 5-10x
  - Network latency giữa services (10-50ms per call)
  - Saga complexity ngay từ ngày 1
  - DevOps overhead lớn (multiple deployments, service mesh)
  - Debugging cross-service issues
  - Database management (per-service DB)
  - Testing complexity (contract tests, integration tests)
  
team_constraint:
  - 6-8 engineers không thể vừa ship features vừa manage 10+ services
  - Microservices cần SRE dedicated → chưa có Phase 1
### Tại sao Modular Monolith works
modular_monolith_benefits:
  - Single deployment unit (deploy nhanh)
  - In-process calls (latency thấp)
  - Single transaction across modules (no saga needed for some flows)
  - Easier debugging
  - Lower infra cost
  
discipline_required:
  - Strict module boundaries (enforced by linting + arch tests)
  - Modules communicate via interfaces, not implementation
  - Database access only through repository per module
  - Events for cross-module notifications
  - This discipline → easy extraction later
### Khi nào extract
extraction_triggers:
  - Module có scaling requirement khác biệt (e.g., AI calls cần 10x compute)
  - Module có release cycle khác (e.g., Workflow Engine update thường xuyên)
  - Module có team riêng (Conway's Law)
  - Module có security boundary (e.g., payment processing)

phase_2_candidates:
  - Workflow Engine (high traffic, high reliability needs)
  - Process Mining (resource-intensive, batch nature)
  - LLM Integration (cost + latency isolation)
## Consequences
### Positive
Faster Phase 1 delivery
Lower complexity for small team
Easier to refactor module boundaries before commitment to service boundaries
Lower infra cost in Phase 1
### Negative
All modules deploy together (smaller blast radius vs full monolith but bigger than microservices)
Risk: discipline slips, modules become coupled (mitigation: arch tests in CI)
Future extraction effort needed (mitigation: do it gradually as needs arise)
## Alternatives Considered
alternatives:
  
  full_microservices_from_day_1:
    rejected_because: "Team too small, premature complexity"
  
  pure_monolith_no_modularity:
    rejected_because: "Big ball of mud risk, hard to extract later"
  
  serverless_functions:
    rejected_because: "State-heavy workflows don't fit Lambda model well"
  
  selected_modular_monolith:
    chosen: "Best balance of speed + future flexibility"
## Status: ACCEPTED (Phase 1)

# Phần 49. ADR-002: Temporal.io for Workflow Orchestration
## Context
Kaori workflow system cần execute long-running, reliable workflows với: - Idempotency - Retry logic with backoff - Saga pattern - State persistence (survive crashes) - Visibility into execution
## Decision
Use Temporal.io as workflow orchestration engine.
## Rationale
### Comparison
options_evaluated:
  
  custom_engine:
    pros: full control
    cons: 6-12 person-years to build right
    verdict: REJECTED
  
  apache_airflow:
    pros: mature, popular
    cons: 
      - Designed for batch ETL, not transactional
      - DAG model doesn't fit dynamic workflows
      - Saga not built-in
    verdict: REJECTED
  
  aws_step_functions:
    pros: managed, AWS-native
    cons:
      - Vendor lock-in
      - Not Vietnam-region
      - Cost scales aggressively
    verdict: REJECTED
  
  camunda:
    pros: enterprise mature, BPMN standard
    cons:
      - Java-heavy (our stack is Python)
      - BPMN overkill for SME workflows
      - License complexity
    verdict: REJECTED
  
  cadence:
    pros: predecessor of Temporal
    cons: Less active community now
    verdict: REJECTED (in favor of Temporal)
  
  temporal:
    pros:
      - Built for reliable workflows from ground up
      - Saga pattern native
      - Idempotency framework-level
      - Python SDK mature
      - Open source + cloud option
      - Active community
    cons:
      - Operational complexity (cluster management)
      - Learning curve
    verdict: SELECTED
## Consequences
### Positive
Reliable execution out of the box
Saga support → safer irreversible workflows
Distributed tracing built-in
Long-running workflow support (days/weeks)
Active community + good docs
### Negative
Operational overhead: Temporal cluster to manage
Learning curve for team
Some abstraction leakage (need to understand Temporal model)
## Mitigation
Start with Temporal Cloud (managed) for Phase 1, evaluate self-hosted Phase 2
Allocate 2-week training time for team
Build Kaori-specific abstractions on top to hide Temporal details
## Status: ACCEPTED

# Phần 50. ADR-003: Postgres + ClickHouse Polyglot Persistence
## Context
Kaori has different data access patterns: - Transactional: workflow definitions, configs, ACLs (high consistency, OLTP) - Analytical: traces, metrics, time-series (high volume, OLAP)
Single DB struggles with both efficiently.
## Decision
Polyglot persistence: - PostgreSQL 15+ for transactional (with RLS for multi-tenancy) - ClickHouse for analytical workloads - Redis for cache + streams + locks - MinIO for blob/files - Pinecone for vectors (RAG) - Vault for secrets
## Rationale
### Why not single DB
single_postgres:
  pros: "Simpler ops"
  cons:
    - "Time-series queries slow on Postgres"
    - "100M+ row analytics tables → bad performance"
    - "Trace queries (high cardinality) overwhelm"
  verdict: "Doesn't scale to platform analytics needs"

single_clickhouse:
  pros: "Fast analytics"
  cons:
    - "Not designed for transactional updates"
    - "No native foreign keys"
    - "Complex multi-tenant patterns"
  verdict: "Wrong tool for transactions"
### Tool Selection
postgres_use_cases:
  - workflow definitions, runs metadata
  - tenant configs, ACLs
  - idempotency records
  - silver tier business data
  - small gold aggregates
  - operational economics monthly
  reasons: "ACID, RLS, mature, well-known"

clickhouse_use_cases:
  - OpenTelemetry traces (high volume)
  - Workflow execution metrics
  - Adoption signal events (time-series)
  - Large gold aggregations
  reasons: "Columnar, fast aggregation, compression"

redis_use_cases:
  - Session cache
  - Rate limit counters
  - Distributed locks
  - Event streams (Phase 1)
  - Pub/sub
  reasons: "Sub-ms latency, mature"

minio_use_cases:
  - Uploaded files
  - Generated reports
  - Backups
  - ML model artifacts
  reasons: "S3-compatible, self-hostable, Vietnam-region"

pinecone_use_cases:
  - RAG vector store
  reasons: "Managed, fast, namespace per tenant"
  alternative: "Qdrant if data residency strict"

vault_use_cases:
  - All secrets
  reasons: "Audit, rotation, scoped access"
## Consequences
### Positive
Right tool for right job
Each system optimized for its workload
Independent scaling per persistence type
### Negative
Multiple systems to operate, monitor, backup
Cross-system queries need coordination
More operational expertise required
## Status: ACCEPTED

# Phần 51. ADR-004: Multi-Tenancy via RLS (not Schema-per-Tenant)
## Context
Multi-tenancy strategy options: 1. Database-per-tenant: complete isolation 2. Schema-per-tenant: shared DB, separate schemas 3. Row-Level Security (RLS): shared DB, shared schema, RLS filters
## Decision
Row-Level Security (RLS) for Phase 1 + most of Phase 2.
Re-evaluate for Phase 3 if needed.
## Rationale
### Comparison
db_per_tenant:
  pros: "Maximum isolation"
  cons:
    - "DB ops × N tenants (cost)"
    - "Cross-tenant analytics impossible"
    - "Schema migrations hard"
    - "Connection pooling per tenant complex"
  verdict: REJECTED for SME scale

schema_per_tenant:
  pros: "Logical isolation, single DB"
  cons:
    - "Schema migration runs N times"
    - "Connection pool per schema (overhead)"
    - "Cross-tenant analytics requires joining schemas"
    - "100s of schemas → DB metadata bloat"
  verdict: "Considered but not selected for SME scale"

rls:
  pros:
    - "Single schema, single connection pool"
    - "Migrations once for all"
    - "Cross-tenant analytics possible (admin role)"
    - "Postgres native feature, well-supported"
  cons:
    - "Bug in policy → potential leak (mitigation: tests)"
    - "All tenants share resources (mitigation: quotas)"
  verdict: SELECTED
### When to Revisit
reasons_to_evolve_away_from_rls:
  - "Customer demands physical isolation (regulatory)"
  - "Single tenant grows to demand dedicated capacity"
  - "Compliance requirement (e.g., government contracts)"
  
phase_3_consideration:
  - "Hybrid model: RLS default + dedicated DB for whales"
  - "Or schema-per-tenant for top 10 customers"
## Consequences
### Positive
Operational simplicity
Cost-effective at SME scale
Flexible (can evolve)
Cross-tenant analytics easy for admin
### Negative
Resource sharing (noisy neighbor risk → quotas)
Single bug could leak data → continuous testing required
Heavy tenants impact others → quotas
## Mitigation
Cross-tenant leak tests in CI/CD (every commit)
Quotas + rate limits per tenant
Audit log monitoring for cross-tenant attempts (must be 0)
Annual penetration testing
## Status: ACCEPTED (Phase 1-2)

# Phần 52. ADR-005: At-Least-Once + Idempotency (not Exactly-Once)
## Context
Workflow execution semantics: at-most-once, at-least-once, exactly-once. Each has tradeoffs.
## Decision
Default: at-least-once + idempotency for 95%+ of operations. Exception: exactly-once for specific high-stakes operations (payments, legal commits) — opt-in.
## Rationale
### Why Not Exactly-Once Default
exactly_once_costs:
  - "5-10x slower than at-least-once"
  - "More complex code (distributed locks, atomic across systems)"
  - "More failure modes (lock timeouts, transaction conflicts)"
  - "Requires provider-side dedup (often unavailable)"
  
real_world:
  - "Most operations idempotency-friendly with right design"
  - "send_email with idempotency_key → provider dedups → effectively exactly-once user experience"
  - "Database upsert with key → idempotent by design"
### When Exactly-Once Truly Required
exactly_once_use_cases:
  - "Financial transactions > $1000"
  - "Legal contract execution"
  - "Inventory commits with no slack"
  - "Healthcare records (compliance)"

implementation:
  - "Distributed lock + idempotency key + transactional storage"
  - "Workflow engine flag: reliability.semantics = 'exactly_once'"
  - "Enforced via additional checks at runtime"
## Consequences
### Positive
Faster execution for common case
Simpler code paths
Better resource utilization
### Negative
Edge cases possible (duplicate execution where idempotency check failed)
Some operations actually irreversible (sent SMS) → no full safety
## Mitigation
Idempotency keys for all non-pure operations
Audit logs catch duplicates (operations team can investigate)
Saga pattern for irreversible chains (compensate on failure)
## Status: ACCEPTED

# Phần 53. ADR-006: Vendor LLM (Anthropic/OpenAI) over Self-Hosted
## Context
LLM strategy: use vendor APIs (Anthropic Claude, OpenAI GPT) or self-host (Llama 2/3, Mistral)?
## Decision
Phase 1-2: Vendor LLMs (Anthropic primary, OpenAI fallback). Phase 3: Evaluate self-hosted for cost optimization on commodity tasks.
## Rationale
### Why Not Self-Hosted Day 1
self_hosted_costs:
  
  infrastructure:
    - GPU cluster: 4× A100 minimum = $50K+ upfront
    - GPU cloud: $3-5/hr per A100, sustained
    - Total monthly: $5K-$15K minimum at low usage
  
  expertise:
    - ML engineer to fine-tune, optimize
    - DevOps for GPU cluster
    - 2-3 FTE additional
  
  quality:
    - Open models (Llama 3, Mistral) close to but not match GPT-4 / Claude 3.5
    - Fine-tuning required for domain quality
    - Months of evaluation + iteration
  
  vietnamese_language:
    - Open models weaker on Vietnamese vs commercial
    - Need RLHF on Vietnamese → expensive
  
  vs_vendor:
    - Anthropic Claude: $3-15 per million tokens (input/output)
    - At Phase 1 scale (estimated): $3K-$10K/month total
    - Cheaper than self-hosted minimum
### Mitigation for Vendor Lock-in
vendor_independence_strategies:
  
  adapter_pattern:
    - LLMAdapter interface
    - Anthropic, OpenAI, future: Llama, Mistral
    - Switch via config, not code change
  
  multi_provider_routing:
    - Fallback between providers
    - Cost-based routing (cheap provider for commodity)
    - Quality-based routing (best provider for critical)
  
  prompt_portability:
    - Avoid provider-specific features when possible
    - Test prompts across providers periodically
  
  data_portability:
    - Don't store data on provider side
    - All inputs/outputs in our DB
    - Provider only sees individual API calls
### Phase 3 Self-Hosted Trigger
when_to_self_host:
  - Volume > 100M tokens/month sustained → cost crossover
  - Specific domain (Vietnamese SME) where fine-tuned smaller model competitive
  - Customer demands data not leave Vietnam (some gov + finance)
  - Strategic moat (proprietary model fine-tuned on Kaori data)
## Consequences
### Positive
Faster Phase 1
Best-in-class LLM quality
Lower upfront cost
Less ML expertise needed
### Negative
Recurring API costs scale with usage
Vendor lock-in risk (mitigated by adapters)
Data sent to vendors (privacy concern for some customers)
Provider availability dependency
## Status: ACCEPTED (Phase 1-2)

# Phần 54. ADR-007: Vietnam Hosting (FPT/Viettel) over Cloud Hyperscaler
## Context
Hosting options: AWS/GCP/Azure (hyperscalers) vs Vietnam local providers (FPT, Viettel, VNPT).
## Decision
Vietnam region hosting: FPT Cloud primary, Viettel IDC secondary.
## Rationale
vietnam_hosting_advantages:
  
  data_residency:
    - PDPL compliance default
    - Customer comfort (data stays in Vietnam)
    - Government RFP requirements (some sectors)
  
  latency:
    - Sub-50ms to Vietnam customers (vs 100-200ms to Singapore AWS)
    - Critical for real-time workflow execution
  
  cost:
    - VND pricing (no FX risk)
    - Cheaper than hyperscaler equivalent
    - No cross-border data transfer fees
  
  partnerships:
    - FPT, Viettel: relationship advantage
    - Local support in Vietnamese
    - Co-marketing opportunities
  
  pii_treatment:
    - Vietnam DPL friendly
    - Lower regulatory complexity vs hyperscaler with VN customers

hyperscaler_disadvantages:
  - Singapore/HK regions: latency penalty
  - Vietnam region (AWS): late and limited
  - Cross-border data flow scrutiny
  - Egress fees expensive
  - Hyperscaler overkill for SME tier pricing
### Mitigation for Vietnam Provider Risks
risks_and_mitigation:
  
  risk_1_provider_outage:
    mitigation: multi-provider (FPT + Viettel)
  
  risk_2_kubernetes_maturity:
    mitigation: 
      - FPT Cloud has managed K8s
      - Use standard tools (no provider-specific)
      - Can migrate if needed
  
  risk_3_specific_services_missing:
    mitigation:
      - Self-host for missing services (e.g., Vault, MinIO)
      - Use external for some (Pinecone managed)
      - Vendor agnostic by design
  
  risk_4_pricing_changes:
    mitigation:
      - Multi-year contracts
      - Multi-provider leverage
## Consequences
### Positive
Data residency
Better latency
Lower cost
Local support
### Negative
Less mature ecosystem vs AWS
Some advanced services missing → self-host
Multi-region (international) more complex
## Status: ACCEPTED

# PART XIII — RISKS & MITIGATIONS
# Phần 55. Architectural Risks (top 15)
## 55.1 Risk Catalog
architectural_risks:
  
  R-A-1_temporal_complexity:
    category: technical
    description: "Temporal cluster management complexity"
    severity: MEDIUM
    likelihood: HIGH
    impact: "DevOps overhead, learning curve"
    mitigation:
      - Start with Temporal Cloud (managed) Phase 1
      - Self-host Phase 2 only if cost demands
      - Train 2 engineers as Temporal experts
  
  R-A-2_cross_tenant_leak:
    category: security
    description: "RLS bug → cross-tenant data leak"
    severity: CRITICAL
    likelihood: LOW
    impact: "Reputational damage, legal liability"
    mitigation:
      - Continuous testing (CI/CD)
      - Production monitoring (audit logs)
      - Quarterly penetration testing
      - Bug bounty program (Phase 2)
  
  R-A-3_llm_vendor_dependency:
    category: technical/business
    description: "Anthropic/OpenAI outage or pricing change"
    severity: HIGH
    likelihood: MEDIUM
    impact: "Service degradation or cost spike"
    mitigation:
      - Multi-provider adapter pattern
      - Fallback chains
      - Cost caps + alerts
      - Phase 3: self-hosted option
  
  R-A-4_vietnam_provider_limitations:
    category: infrastructure
    description: "FPT/Viettel maturity gaps vs hyperscalers"
    severity: MEDIUM
    likelihood: MEDIUM
    impact: "Operational friction, missing services"
    mitigation:
      - Multi-provider strategy
      - Self-host critical pieces
      - Standard K8s (portable)
  
  R-A-5_data_quality_cascading:
    category: data
    description: "Bad data in Bronze → cascades to Silver → Gold → Insights"
    severity: HIGH
    likelihood: HIGH
    impact: "Wrong insights, wrong actions, customer trust"
    mitigation:
      - Quality gates between tiers
      - Great Expectations validation
      - Quarantine + manual review
      - Data quality dashboard
  
  R-A-6_workflow_engine_bottleneck:
    category: scalability
    description: "Temporal becomes bottleneck at scale"
    severity: MEDIUM
    likelihood: LOW (Phase 1)
    impact: "Workflow execution delays"
    mitigation:
      - Capacity planning quarterly
      - Auto-scaling workers
      - Sharded task queues
      - Phase 2: dedicated Temporal cluster per heavy tenant
  
  R-A-7_database_growth:
    category: scalability
    description: "Workflow traces + audit logs fill DB"
    severity: MEDIUM
    likelihood: HIGH
    impact: "Performance degradation, cost growth"
    mitigation:
      - Partitioning (date-based)
      - ClickHouse for high-volume analytics
      - Retention policies
      - Cold storage archival
  
  R-A-8_single_region_outage:
    category: availability
    description: "FPT HCMC region outage → service down"
    severity: CRITICAL
    likelihood: LOW
    impact: "Customer-visible downtime"
    mitigation:
      - DR plan to Hanoi region
      - DR drills quarterly
      - Documented runbook
      - Communication plan
  
  R-A-9_secret_compromise:
    category: security
    description: "Vault breach OR exposed key"
    severity: CRITICAL
    likelihood: LOW
    impact: "Multi-tenant security disaster"
    mitigation:
      - Vault hardening
      - Key rotation policies
      - Audit on every access
      - Separation: tenant secrets vs Kaori secrets
  
  R-A-10_zalo_api_changes:
    category: integration
    description: "Zalo Business API changes break our integration"
    severity: HIGH (Vietnam-specific)
    likelihood: MEDIUM
    impact: "Critical Vietnam feature broken"
    mitigation:
      - Versioned adapter
      - Beta program with Zalo
      - Fallback to email/SMS
      - Direct relationship with Zalo team
  
  R-A-11_kubernetes_complexity:
    category: operations
    description: "K8s ops overhead exceeds team capacity"
    severity: HIGH
    likelihood: MEDIUM
    impact: "Slow incident response, deployment delays"
    mitigation:
      - Use managed K8s (FPT)
      - GitOps (Flux/ArgoCD)
      - Standardized tooling
      - SRE hire by Phase 2
  
  R-A-12_event_storm:
    category: reliability
    description: "Cascading event amplification overloads system"
    severity: MEDIUM
    likelihood: LOW
    impact: "Service degradation"
    mitigation:
      - Circuit breakers
      - Rate limits per topic
      - DLQ for failed processing
      - Backpressure mechanisms
  
  R-A-13_schema_evolution_break:
    category: data
    description: "Schema change breaks active workflows"
    severity: HIGH
    likelihood: MEDIUM
    impact: "Workflow failures, customer complaints"
    mitigation:
      - Backward compatible changes (additive)
      - Migration period (90 days)
      - Schema registry + versioning
      - Impact analysis before deployment
  
  R-A-14_observability_gap:
    category: operations
    description: "Issue happens, can't reproduce or debug"
    severity: MEDIUM
    likelihood: MEDIUM
    impact: "Slow MTTR, customer frustration"
    mitigation:
      - Distributed tracing (every request)
      - Structured logging
      - Comprehensive metrics
      - On-call rotation with runbooks
  
  R-A-15_cost_runaway:
    category: financial
    description: "AI/infra costs grow faster than revenue"
    severity: HIGH
    likelihood: MEDIUM
    impact: "Margin pressure, possibly unsustainable"
    mitigation:
      - Per-tenant cost tracking
      - Cost caps + alerts
      - Quarterly cost reviews
      - Anomaly detection on cost
      - Pricing adjustment mechanism

# Phần 56. Mitigation Strategies (Cross-Cutting)
## 56.1 Strategic Mitigations
top_mitigations:
  
  resilience_first:
    statement: "Design for failure from day 1"
    practices:
      - Idempotency everywhere
      - Retry with backoff
      - Saga for irreversible
      - DLQ for unrecoverable
      - Circuit breakers
      - Bulkheads
  
  observability_first:
    statement: "Can't fix what you can't see"
    practices:
      - Trace everything
      - Structured logs
      - Custom metrics for business signals
      - Dashboards for every layer
      - Alert with playbooks
  
  testing_first:
    statement: "Production bugs are expensive"
    practices:
      - Unit tests (80%+ coverage)
      - Integration tests (key flows)
      - E2E tests (critical paths)
      - Multi-tenancy leak tests
      - Performance regression tests
      - Chaos engineering (Phase 2)
  
  documentation_first:
    statement: "Knowledge in heads = bus factor 1"
    practices:
      - SAD (this doc)
      - Layer docs
      - ADRs for decisions
      - Runbooks for operations
      - Onboarding guide
      - Architecture diagrams kept current

# PART XIV — ROADMAP
# Phần 57. Phase 1 — Foundation (4 months)
## 57.1 Scope (Aggressively Tightened)
phase_1_scope:
  
  duration: 4 months
  team: 6-8 engineers + 1 PM + 1 designer + 1 CSM
  
  must_have:
    
    L0_infrastructure:
      - Kubernetes cluster (FPT Cloud HCMC)
      - Postgres 15 (with RLS)
      - ClickHouse cluster
      - MinIO
      - Redis 7
      - Vault
      - Pinecone (managed)
      - Observability stack (OTel, Jaeger, Prometheus, Grafana, Loki)
    
    L1_ingestion:
      - 8 connector types (Postgres CDC, Excel, Zalo, Gmail, Misa, Fast, generic API, webhook)
      - Streaming via Redis Streams
      - Batch via K8s CronJobs
    
    L2_data_plane:
      - Bronze/Silver/Gold tiers
      - Schema registry
      - Data quality gates (Great Expectations)
      - Multi-tenancy with RLS
      - Feature store (basic)
    
    L3_reasoning:
      - Insight Engine (5 insight types)
      - Recommendation Engine
      - Constraint Engine (basic rules)
      - Formula Library (50+ formulas)
      - Criteria Engine
      - LLM integration (Anthropic primary, OpenAI fallback, version pinning)
      - RAG (vector search + grounding)
    
    L4_workflow:
      - Workflow Engine (Temporal-based)
      - Drag-drop builder + 25 node types
      - 15 templates (4 departments)
      - Idempotency + retry + DLQ
      - Distributed tracing
      - Workflow versioning
    
    L4_5_org_intelligence_v1:
      - Process Mining v1 (3 sources: Postgres, Excel, Zalo)
      - Adoption Intelligence (5 of 9 signals)
      - Operational Economics (basic NOV)
    
    L5_user:
      - Web UI (React)
      - Workflow Builder UI
      - Runtime Dashboard
      - ROI Dashboard (basic)
      - Zalo Bot (CRITICAL for Vietnam)
      - API Gateway
    
    cross_cutting:
      - Multi-tenancy security tested
      - Secrets management (Vault)
      - Cost tracking + caps
      - Audit logging
  
  cut_from_phase_1:
    - 90-day parallel testing → Phase 1.5
    - Process Mining full (8 sources, full algorithms) → Phase 2
    - Simulation engine → Phase 2
    - Multi-user collaboration → Phase 2
    - Workflow as Code (YAML import/export) → Phase 2
    - Multi-agent orchestration → Phase 3
    - Workflow marketplace → Phase 3
    - Mobile app → Phase 2
    - Strategic OKR mapping → Phase 2
    - Federated workflows → Phase 3
## 57.2 Phase 1 Milestones
month_1:
  - Infrastructure stood up (K8s, DBs, Vault)
  - Core monorepo + CI/CD
  - Basic auth + multi-tenancy
  - First 3 connectors (Postgres, Excel, Zalo metadata)
  - Bronze tier ingestion working

month_2:
  - Silver/Gold tiers
  - Reasoning Layer (Insight Engine first)
  - Constraint Engine
  - LLM integration with version pinning
  - RAG basic
  - Workflow Engine basic (Temporal cluster + 5 nodes)

month_3:
  - Workflow Builder UI
  - 25 node types complete
  - Idempotency + retry + DLQ
  - Distributed tracing
  - Process Mining v1 (3 sources)
  - Adoption Intelligence basic
  - Zalo Bot

month_4:
  - 15 templates
  - ROI Dashboard
  - Beta with 3-5 friendly customers
  - Performance + security hardening
  - Documentation completion
  - Phase 1 launch

# Phần 58. Phase 1.5 — Stabilization (2 months)
phase_1_5_scope:
  
  duration: months 5-6
  focus: stabilize + fill critical gaps from Phase 1 launch
  
  additions:
    - 90-day parallel testing infrastructure
    - Process Mining: add email + calendar sources
    - Adoption Intelligence: full 9 signals + intervention playbook
    - Operational Economics: A/B attribution method
    - 3 more AI node types (forecasting, risk_detection, extract_entities)
    - 10 more workflow templates
    - Customer-facing APIs (public)
    - Performance optimization based on real customer load
  
  improvements:
    - Workflow runtime optimization
    - Data plane partitioning
    - UI performance tuning
    - Cost optimization
  
  customers:
    - Onboard 10-15 customers total
    - Iterate based on feedback
    - First customer success stories + case studies

# Phần 59. Phase 2 — Differentiation (6 months)
phase_2_scope:
  
  duration: months 7-12
  focus: moat features + selective microservices
  
  major_additions:
    
    process_mining_full:
      - All 8 source types operational
      - Full algorithms (Heuristic, Inductive, Fuzzy)
      - Conformance analysis
      - Bypass risk scoring
      - Shadow process detection
    
    workflow_capabilities:
      - All 45 node types complete
      - 40 workflow templates
      - Multi-user collaboration on workflows
      - Workflow as Code (YAML import/export)
      - Workflow marketplace (beta)
      - Custom integrations (tenant-built)
    
    advanced_ai:
      - Workflow ontology
      - Strategic OKR mapping
      - Multi-step reasoning chains
      - Custom AI model fine-tuning option (MAX tier)
    
    architecture_evolution:
      - Extract Workflow Engine to microservice
      - Extract Process Mining to microservice
      - Service mesh (Istio or Linkerd)
      - Per-tenant K8s namespaces for whales
    
    mobile:
      - Mobile app (React Native)
      - Approve actions on mobile
      - Receive notifications
    
    security_compliance:
      - SOC 2 Type 1 audit prep
      - SSO (Google, Microsoft Azure AD)
      - MFA option
      - Field-level PII encryption
    
    business:
      - 100 customers target
      - International (English UI)
      - First non-Vietnam customer (Singapore/Thailand pilot)

# Phần 60. Phase 3 — Platform (Year 2)
phase_3_scope:
  
  duration: months 13-24
  focus: platform + ecosystem + scale
  
  major_additions:
    
    full_microservices:
      - All layers as independent services
      - Per-service databases where appropriate
      - Polyglot (some Go services for performance)
    
    multi_agent:
      - Multi-agent orchestration
      - Agent marketplace
      - Custom agent development
    
    federated_workflows:
      - Cross-tenant workflows (with consent)
      - Industry consortium workflows
      - Standard workflow library
    
    self_hosted_llm:
      - Fine-tuned Vietnamese model
      - Hybrid: vendor for premium, self for commodity
      - Cost optimization
    
    regional_expansion:
      - Singapore region
      - Thailand region
      - Indonesia region
    
    enterprise_features:
      - White label option
      - On-premises deployment option (for regulated)
      - Multi-region active-active
    
    ecosystem:
      - Public marketplace (workflows, templates, agents)
      - Developer platform (3rd party can build connectors)
      - Certified consultants program
    
    business:
      - 1000+ customers
      - International revenue > 30%
      - SOC 2 Type 2 certified
      - ISO 27001 certified
      - Series A → B funding milestone

# Tổng kết — Kaori AI SAD v2.0
## Major Architectural Decisions
1. Layered architecture (6 layers + cross-cutting)
2. Modular monolith → microservices evolution
3. Temporal.io for reliable workflow orchestration
4. Postgres + ClickHouse polyglot
5. Multi-tenancy via RLS
6. At-least-once + idempotency (not exactly-once default)
7. Vendor LLM with adapter pattern
8. Vietnam region hosting (FPT/Viettel)
## What Makes This Architecture Defensible
1. PROCESS MINING = MOAT
   No competitor combines PM + workflow + AI at SME scale
   Celonis is enterprise-only ($13B company)

2. ADOPTION INTELLIGENCE = MOAT
   Vietnam-specific resistance signals (Zalo, Excel, hierarchical)
   Detects failure before customer churns

3. OPERATIONAL ECONOMICS = MOAT
   Manager-language NOV in VND
   Time-to-payback for every workflow change
   Replaces "trust us, it works" with "here's the money"

4. RUNTIME RELIABILITY = TABLE STAKES
   Idempotency, saga, DLQ, distributed tracing
   Without this: doesn't scale to 100+ tenants

5. VIETNAM-NATIVE = MOAT
   Zalo, Misa, Fast first-class
   FPT/Viettel hosting
   Vietnamese language throughout
   Hyperscalers can't match latency/relationship
## Audience Quick Reference
new_engineer:
  read: SAD Part I-VII (5 hours)
  then: layer doc for your domain

architect:
  read: SAD Part I + Part XII (ADRs) + Part IX (integration)
  reference_during_design: full SAD

devops_sre:
  read: SAD Part X (deployment) + Part VIII (cross-cutting)
  reference_during_oncall: runbooks

security:
  read: SAD Part VIII (security) + ADR-004 (RLS)
  reference: Workflow System v2.0 Phần 51-52

product_pm:
  read: SAD Part I + Part XIV (roadmap) + Part XIII (risks)

cto_ceo:
  read: SAD Part I (overview) + Part XII (ADRs) + Part XIV (roadmap)
## Bộ docs Kaori AI hoàn chỉnh
1. SAD v2.0 (this doc) — Master architecture
2. Pipeline Unified v1.1 — Data layer deep dive
3. Reasoning Layer v4.0 — AI brain deep dive
4. Workflow System v2.0 — Workflow + PM + Adoption + Economics deep dive
5. 90-day Playbook v3 — Operational deployment
6. Gaps Analysis v1 — Risk + open questions
7. Dataset Selection Report — Pilot dataset rationale

Total: ~135,000 từ enterprise documentation
## Key Metrics for Success
phase_1_success_criteria:
  technical:
    - 99.5%+ workflow execution success rate
    - <5min p95 workflow runtime
    - 0 cross-tenant leaks
    - <1hr MTTR for P1 incidents
  
  product:
    - 10-15 customers onboarded
    - 50+ active workflows in production
    - Adoption health score > 70 average
    - NPS > 30
  
  business:
    - MRR target: 50M VND/month by month 4
    - Customer LTV > CAC × 3
    - First positive NOV customer story
    - 1+ case study published

END OF DOCUMENT — Kaori AI Software Architecture Document v2.0
Phiên bản: v2.0 (Comprehensive) Phát hành: Tháng 5 / 2026 Total: ~16 parts, 60 sections, ~22,000 từ Audience: Engineering · Architects · DevOps · Security · Product · Executive