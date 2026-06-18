# Phase 2 Execution Tracker — Intelligence Layer (Month 5–9)
> Kaori AI | Status: NOT STARTED | Activates after Phase 1 completion (F-008 + F-031 + F-032 done)

---

## 🔴 CURRENT EXECUTION STATE

| Field                 | Value                                          |
|-----------------------|------------------------------------------------|
| **Phase**             | 2 — Intelligence Layer                         |
| **Status**            | ⛔ LOCKED — Phase 1 incomplete (71%)            |
| **Unlock Condition**  | F-031 ✅ AND F-032 ✅ AND F-008 ✅               |
| **Active Function**   | — (not started)                                |
| **Active Task**       | — (not started)                                |

---

## Phase 2 Progress

| Metric              | Value                    |
|---------------------|--------------------------|
| **Total Functions** | 36 (F-033–F-068)         |
| **Done**            | 0                        |
| **Pending**         | 36                       |
| **Phase Progress**  | **0%**                   |

---

## Sprint Breakdown

### Sprint 2.1 — Feature Store + Knowledge Graph
**Goal:** Online/offline feature store; Knowledge Graph foundation for multi-tenant AI

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-033  | Feature Store Online (Redis Cluster) | feature-store          | P0       | ⬜     |
| F-034  | Feature Store Offline (ClickHouse) | feature-store            | P0       | ⬜     |
| F-035  | Feature Drift Monitor              | feature-store             | P1       | ⬜     |
| F-036  | Knowledge Graph (Neo4j CE)         | kg-service                | P1       | ⬜     |
| F-037  | KG Builder (Kafka consumer)        | kg-service                | P1       | ⬜     |

### Sprint 2.2 — Model Serving + Registry
**Goal:** Triton + vLLM serving; MLflow registry per tenant

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-038  | Model Registry (MLflow + PG)       | model-registry            | P0       | ⬜     |
| F-039  | Model Serving (Triton + vLLM)      | model-serving             | P0       | ⬜     |
| F-040  | Training Pipeline (Ray + PyTorch)  | training-pipeline         | P1       | ⬜     |
| F-041  | Continuous Learning Loop           | training-pipeline         | P1       | ⬜     |
| F-042  | Explainability Layer (SHAP)        | explainability-service    | P1       | ⬜     |

### Sprint 2.3 — Workflow Engine + Agent Framework
**Goal:** Temporal.io workflows; MS Agent Framework (Planner/Executor/Critic)

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-043  | Workflow Engine (Temporal.io)      | workflow-engine           | P0       | ⬜     |
| F-044  | AI Agent System — Planner          | ai-orchestrator           | P0       | ⬜     |
| F-045  | AI Agent System — Executor         | ai-orchestrator           | P0       | ⬜     |
| F-046  | AI Agent System — Critic           | ai-orchestrator           | P1       | ⬜     |
| F-047  | Agent Tool Registry                | ai-orchestrator           | P1       | ⬜     |

### Sprint 2.4 — P3 Studio Portal
**Goal:** Internal analyst workspace; custom model building per enterprise

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-048  | Studio Login + Scope               | auth-service              | P0       | ⬜     |
| F-049  | Studio Model Builder               | model-registry + frontend | P1       | ⬜     |
| F-050  | Studio Dataset Manager             | data-pipeline + frontend  | P1       | ⬜     |
| F-051  | Studio Training Launcher           | training-pipeline         | P1       | ⬜     |
| F-052  | Studio Report Generator            | ai-orchestrator + frontend| P2       | ⬜     |
| F-053  | Studio Model Promotion             | model-registry            | P1       | ⬜     |

### Sprint 2.5 — MCP Server
**Goal:** Kaori MCP Server exposing Knowledge Graph + tools via JSON-RPC 2.0

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-054  | MCP Server Foundation (Node.js)    | mcp-server                | P1       | ⬜     |
| F-055  | MCP Tool: query_knowledge_graph    | mcp-server                | P1       | ⬜     |
| F-056  | MCP Tool: run_analysis             | mcp-server                | P1       | ⬜     |
| F-057  | MCP Tool: get_customer_risk        | mcp-server                | P1       | ⬜     |
| F-058  | MCP Auth: tenant_id per call + audit | mcp-server + auth-service | P0      | ⬜     |

### Sprint 2.6 — P2 Advanced Features
**Goal:** Advanced P2 Enterprise features: multi-analysis, Finance vertical

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-059  | Multi-Analysis Parallel Runner     | ai-orchestrator           | P1       | ⬜     |
| F-060  | Finance Vertical Templates         | ai-orchestrator           | P1       | ⬜     |
| F-061  | Alert Engine + Notification Rules  | ai-orchestrator           | P1       | ⬜     |
| F-062  | Fairness & Bias Detection          | explainability-service    | P2       | ⬜     |
| F-063  | Compliance Exporter (audit)        | audit-service             | P2       | ⬜     |

### Sprint 2.7 — P4 Personal Portal
**Goal:** Freelancer/individual use; self-serve pipeline + goals

| ID     | Function                          | Service                   | Priority | Status |
|--------|-----------------------------------|---------------------------|----------|--------|
| F-064  | P4 Login + Personal Scope          | auth-service              | P0       | ⬜     |
| F-065  | Personal Pipeline (self-serve)     | data-pipeline + frontend  | P1       | ⬜     |
| F-066  | Personal Goals Tracker             | ai-orchestrator + frontend| P1       | ⬜     |
| F-067  | Personal AI Suggestions            | ai-orchestrator           | P1       | ⬜     |
| F-068  | Personal Settings + Privacy        | auth-service + frontend   | P1       | ⬜     |

---

## New Services Required (Phase 2)

| Service            | Technology            | Port  | Depends On        |
|--------------------|-----------------------|-------|-------------------|
| feature-store      | Redis Cluster + ClickHouse | 6380 / 8123 | F-033, F-034 |
| model-registry     | MLflow + PostgreSQL   | 5000  | F-038             |
| model-serving      | Triton + vLLM         | 8001  | F-039             |
| training-pipeline  | Ray + PyTorch         | 8265  | F-040             |
| workflow-engine    | Temporal.io           | 7233  | F-043             |
| explainability     | FastAPI + SHAP        | 8095  | F-042             |
| kg-service         | Neo4j CE              | 7474  | F-036             |
| mcp-server         | Node.js               | 3002  | F-054             |

---

*This file will be expanded with full task breakdowns when Phase 1 reaches 100%.*
*Prerequisite check: run `grep -c "done" docs/phase_1_execution.md` before starting.*
