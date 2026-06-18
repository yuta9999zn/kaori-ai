# Workflow Visualization Redesign — Spec

> **Date:** 2026-05-17
> **Anh's directive:** Workflow Builder phải thể hiện branching logic rõ ràng — if/else/switch + decision path + execution state. Linear-card view hiện tại không đủ cho enterprise workflows (Vingroup, logistics, fintech, ERP, manufacturing).
> **Status:** **BE infrastructure 100% ship 2026-05-17 (mig 076).** FE redesign defers — FE đang TẠM DỪNG per CLAUDE.md §2.
> **Reference:** anh paste full ChatGPT prompt 2026-05-17 (8 sections: Visual Structure, If/Else, Node Design, Flow Line, Scalability, Execution Thinking, UX Direction, Important).

## What anh asked for

Current state: Workflow renders as linear "Card 1 → Card 2 → Card 3 → Card 4".

Weakness:
- Người dùng không nhìn được decision flow
- Không thấy nhánh điều kiện
- Không phân biệt success / fallback / exception path
- Workflow nhìn giống checklist hơn là orchestration system
- Khó scale cho doanh nghiệp lớn

Target: enterprise orchestration platform — BPMN-inspired, Temporal/Camunda/Airflow-level. Users see workflow trong 5 giây + understand branching + audit/debug được.

## What BE supports today (audit)

### Decision logic infrastructure — ✅ ALL ALREADY SHIPPED

| Capability | BE feature | Migration |
|---|---|---|
| if/else node | `node_type='decision_if_else'` + `decision_config={"condition","true_target_id","false_target_id"}` | mig 058 + 060 |
| switch node | `node_type='decision_switch'` + `decision_config={"switch_field","cases","default_target_id"}` | mig 058 |
| approval_gate | `node_type='approval_gate'` + `decision_config={"approver_role","timeout_action"}` | mig 058 + 068 |
| wait_for_condition | catalog node `wait_for_condition` (poll until condition) | mig 060 + 068 |
| sla_timer | catalog node `sla_timer` (timeout + escalation) | mig 060 |
| parallel_split / parallel_join | parallel branches with sync | mig 060 |
| subworkflow | nested workflow execution | mig 060 |
| notification | side-effect node for stakeholders | mig 060 |
| Loop / retry | side_effect_class + default_retry_policy per node | mig 068 K-17 |
| Edge condition + label | `workflow_edges.condition` + `label` | mig 053 |
| Node config schema | `node_type_catalog.config_schema_json` (45 entries) | mig 068 |
| Tags / hashtags | `workflow_nodes.hashtags TEXT[]` | mig 053 |
| Attached documents | `workflow_step_documents` + folders | mig 053 + 058 |
| Position x/y for layout | `workflow_nodes.position_x` + `position_y` | mig 053 |
| Multi-user collab | mig 072 editors/comments/locks | mig 072 |
| Cross-workflow link | mig 057 workflow_cross_links | mig 057 |
| YAML import/export | `/workflows/import` + `/workflows/{id}/export.yaml` | P2-S16 |

### BE gaps em fix 2026-05-17 (mig 076)

| Gap | Field | Why it matters |
|---|---|---|
| **Swimlane** | `workflow_nodes.swimlane_id` UUID | FE renders horizontal swimlane band per department/actor. anh's enterprise-scale need (VinGroup-class). |
| **Mandatory/optional/conditional flag** | `workflow_nodes.mandatory` VARCHAR(16) | Phân biệt "always run" vs "skip on precondition fail" vs "run only if branch_path true". Different visual treatment per type. |
| **Subprocess group** | `workflow_nodes.group_id` UUID | Collapse-branch needs grouping — FE shows collapsed group as single block. |
| **Branch path identifier** | `workflow_edges.branch_path` VARCHAR(16) — `success/fallback/exception/default/true/false` | FE picks arrow color + style per semantic path. Critical for "5-second understanding" target. |
| **Edge color override** | `workflow_edges.branch_color` VARCHAR(7) — hex | Tenant theming override of FE default branch colors. |
| **Execution state** | `workflow_node_execution_state` table (8-value state enum + iteration counter) | FE overlay renders execution view over designed flow. Append-only audit trail of run state transitions. |

mig 076 ship 2026-05-17 — all backward-compatible (defaults on ALTER cols + new table independent of existing rows).

## FE redesign — what the FE must do (defer)

Per anh's 8-section ChatGPT prompt, the FE Workflow Builder must:

### 1. Visual structure — DAG-like business pipeline

Node graph rendering (React Flow recommended — Phase 2 FE template):
- Linear flow ✅ (today's behaviour)
- Parallel flow — render parallel_split → branches → parallel_join
- if/else — render decision_if_else as diamond/gateway node with 2 labeled exits
- switch — diamond with N labeled exits + default
- Loop / retry — visual loop-back arrow + retry counter overlay
- Approval gate — distinct icon + actor avatar
- Human task — different from automation task icon
- RPA / AI / Automation tasks — distinct iconography per node_type_key category
- Escalation + fallback + exception paths — colored by `workflow_edges.branch_path`

### 2. If/else visualization (anh's main pain point)

Example anh provided:
```
S01 → S02
From S02:
  IF stock available → S03
  ELSE IF reserve VIN → S04 → S03
  ELSE → procurement flow
```

Required FE output:
```
            [S02]
              |
       ┌──────┼──────┐
       |             |
 [IF stock]   [ELSE IF reserve]
       |             |
     [S03]        [S04]
                     |
                  [S03]
```

BE supports this NOW via:
- decision_if_else node S02 with `decision_config={"true_target_id": S03, "false_target_id": S04}`
- workflow_edges with `branch_path='true'` (label "stock") and `branch_path='false'` (label "reserve")
- Two edges converge to S03 — FE renders merge point automatically.

For ELSE IF chains: chain decision_if_else nodes (S02 → S02b → S03/S04/procurement).

### 3. Node design — per-card display

FE renders each workflow_node with:
- Step ID (`node_id` short form)
- Title + title_vi (`workflow_nodes.title` / `title_vi`)
- Node type icon — derived from `node_type_catalog.category` (data_input/processing/decision/ai/action/output) + `node_type_catalog.is_irreversible` (warning icon)
- Swimlane label — `swimlane_id` → join with departments
- Actor avatar — `workflow_nodes.created_by` or assignee field
- SLA badge — `node_type_catalog.default_retry_policy.max_attempts` × `backoff_seconds`
- Dependency lines — workflow_edges resolved into incoming/outgoing per node
- Documents — folder count via `workflow_step_folders` + file count via `workflow_step_documents`
- Hashtags — `workflow_nodes.hashtags`
- Mandatory marker — `mandatory='mandatory'` red border, `optional` dashed border, `conditional` yellow border

Compact + collapsible + hover-detail + click-side-panel — pure FE concern.

### 4. Flow line design

Connection rendering:
- Directional arrows (FE library default)
- Branch labels — `workflow_edges.label`
- Color per `branch_path` — FE theme map:
  - success → green
  - fallback → yellow
  - exception → red
  - default → grey
  - true / false (for decision_if_else) → light green / light orange
- `branch_color` override applies if non-NULL
- Animated execution path overlay — query `workflow_node_execution_state` filtered by run_id; FE animates edges between consecutively COMPLETED nodes.
- Edge state visual: pending (grey) / active (blue pulse) / completed (green) / blocked (red dashed) / waiting approval (yellow)

### 5. Scalability — 1000-node workflows

FE features (React Flow handles most):
- Zoom in/out (React Flow built-in)
- Mini-map (React Flow built-in)
- Grouping via `group_id` — collapsed group renders as single block; expanded shows children
- Subprocess — `node_type='subworkflow'` clickable opens nested workflow in new view
- Filter by:
  - department (resolve `swimlane_id` → `departments.department_type`)
  - actor (resolve `created_by`)
  - status (filter execution_state by state)
- Timeline mode — render nodes left-to-right on time axis using execution_state.started_at
- Execution replay mode — scrub through ordered execution_state events

### 6. Execution thinking — runtime overlay

FE must distinguish:
- **Designed flow** — what was authored. Pure workflow_nodes + workflow_edges read.
- **Running flow** — show RUNNING/WAITING nodes pulsing. Read latest workflow_node_execution_state per run.
- **Completed flow** — all COMPLETED. Replayable.
- **Failed flow** — FAILED/TIMED_OUT nodes highlighted red. Error_class + error_message on hover. Suggest retry vs rollback.

API contract:
- `GET /workflows/{id}/tree` — designed flow (already exists)
- `GET /workflows/{id}/runs/{run_id}/state` — execution overlay (NEW, defer to FE-resume sprint)

### 7. UX direction

- Enterprise modern — clean lines, generous whitespace, BPMN-inspired iconography
- Orchestration platform feel — not checklist, not Kanban, not student flowchart
- Temporal/Camunda/Airflow/LangGraph reference baseline
- Dark/light mode compatible — CSS variables for branch colors
- (Future VR scalability) — Phase 3+

### 8. Decision node emphasis

Decision nodes (decision_if_else, decision_switch, approval_gate) must:
- Render as **diamonds/gateways**, NOT cards
- Show condition expression as primary label
- Label each exit edge with case-text (true / false / case name / "auto-approved")
- Highlight on hover the merge node where branches converge

## Out-of-scope this commit (defer)

- React Flow / Mermaid / D3 implementation — FE work, paused
- Tenant theming UI for branch_color customization — FE work
- Real-time WebSocket overlay for execution_state — Phase 2 follow-up (needs Temporal worker enabled)
- BPMN 2.0 export — Phase 3 capability

## Sign-off

> **BE ship:** ✅ mig 076 + this spec doc 2026-05-17.
> **FE ship:** ⏳ defers until FE template work resumes per CLAUDE.md §2. When FE picks this up, em provides:
>   - `/workflows/{id}/tree` returns swimlane_id + mandatory + group_id on every node, and branch_path + branch_color on every edge
>   - `/workflows/{id}/runs/{run_id}/state` new endpoint reading workflow_node_execution_state (sketch SQL in spec §6)
>   - Tests guarantee migration backward-compat — existing workflows (no swimlane / mandatory='mandatory' / branch_path='default') render identically to today
