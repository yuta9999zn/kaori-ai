# ADR-0026 — Industry Template 3-Tier Bootstrap

| | |
|---|---|
| **Status**   | Accepted |
| **Date**     | 2026-05-20 |
| **Phase**    | 2.8 |
| **Mig**      | 101 + 102 + 103 |
| **Anh ref**  | 2026-05-20 spec ("Workflow chưa rõ vật thể... Industry → Department → Workflow Template") |

## Context

Phase 2.5 đã ship 25 production workflow_templates + 45-node catalog + multi-user collab. Phase 2.6 đã ship orchestration hardening + state machine. Phase 2.7 đã ship governance (lineage/quota/policy/AI audit).

Nhưng anh review UX 2026-05-20: **"Workflow builder hiện kỹ thuật quá. SME không tạo workflow được từ canvas trắng. Phải bắt đầu từ ngữ cảnh phòng ban. Mỗi bước phải là card công việc rõ ràng. Phải có cấu hình chuẩn theo ngành."**

Đề xuất 3-tier:
```
Industry / Mảng kinh doanh
    → Department / Phòng ban
        → Workflow Template / Quy trình mẫu
            → Workflow Card (= node với input/owner/SLA/AI/branch/output/docs)
```

8 industry đề xuất: Retail, F&B, Logistics, Finance, Healthcare, Manufacturing, Education, Generic SME.

## Decision

Thêm tier `industry_templates` **ABOVE** existing `workflow_templates`, KHÔNG sửa workflow_templates schema (additive-only).

### Schema delta (mig 101 + 102 + 103)

| Bảng | Phạm vi | RLS |
|---|---|---|
| `industry_templates` | 8 industries, platform-shared | — |
| `industry_department_templates` | Per-industry default dept list | — |
| `industry_workflow_links` | M-N bridge industry × dept × workflow_template | — |
| `industry_kpi_templates` | Per (industry, dept) KPI suggestion + default threshold | — |
| `industry_data_schema_templates` | Per (industry, dept) expected data columns + sample file | — |
| `industry_role_permission_templates` | Per (industry, dept_type, seniority) → role + permissions | — |
| `customer_workflow_versions` | Immutable snapshot per save (K-2 trigger) | ✅ |
| `workflow_customizations` | Change log per editing session | ✅ |
| `enterprise_industry_bootstrap` | One-shot per-tenant bootstrap event (UNIQUE) | ✅ |
| `enterprise_workflow_mode` | Per-tenant 3-mode UI flag (simple/advanced/developer) | ✅ |
| `workflow_change_requests` | Runtime CR linked to BA 4.2 register | ✅ |

### API delta

```
GET  /industries                                    — list 3-of-8 catalog
GET  /industries/{id}                               — full detail bundle
GET  /industries/{id}/departments                   — dept list
GET  /industries/{id}/workflows                     — workflow links
       ?recommendation_level=core|suggested|advanced
POST /enterprises/{id}/bootstrap-from-industry      — clone industry → tenant
GET  /enterprises/{id}/bootstrap-status             — idempotency probe
GET  /workflows/{id}/versions                       — snapshot history
POST /workflows/{id}/customize                      — record edit
GET  /enterprises/{id}/workflow-mode                — read 3-mode
PATCH /enterprises/{id}/workflow-mode               — update 3-mode
```

### Seed scope

3 industry **fully** seeded để chứng minh shape:

| Industry | Dept | Workflow link | KPI | Schema | Role-perm |
|---|---|---|---|---|---|
| Retail      | 6 | 15 | 8 | 6 | 5 |
| Finance     | 5 | 4  | 7 | 4 | 5 |
| Generic SME | 4 | 5  | 4 | 3 | 4 |

5 industry còn lại (F&B / Logistics / Healthcare / Manufacturing / Education) **defer** — seed khi customer đầu tiên thuộc industry đó ký hợp đồng. Ràng buộc: KHÔNG ship industry vào catalog mà không có customer thật, tránh "template chết".

### 3-Mode flag

- **Simple** (default cho SME): rename, owner, SLA, threshold. UI hide branch/integration.
- **Advanced**: thêm branch, schema mapping, KPI tuning, approval flow. CSM / analyst.
- **Developer**: thêm connector, custom node type, API integration. Platform admin / partner.

Plan gating: PILOT plan = simple-only (`advanced_unlocked=false`); ENT_BASIC trở lên unlock advanced; developer chỉ bật khi customer ký Custom Implementation contract.

### Customization → CR flow

Phân loại theo anh's spec 2026-05-20:

1. **Cấu hình nhỏ** (Simple mode): user tự chỉnh inline. Log vào `workflow_customizations` với `edit_mode='simple'`. Không cần CR.
2. **Cấu hình trung bình** (Advanced mode): CSM hỗ trợ. Log vào `workflow_customizations` với `edit_mode='advanced'`. Không cần BA CR; nhưng SAU 5 customization HOẶC khi chạm schema, system suggest "tạo CR để chính thức hoá".
3. **Cấu hình lớn**: bắt buộc CR. Tạo row trong `workflow_change_requests` (link sang BA `4.2_Change_Request_Register.md`). Block ANY save tới `developer` mode cho tới khi CR APPROVED.

Quy tắc bất biến: KHÔNG sửa workflow_templates gốc khi customize per-tenant. Mỗi tenant edit → snapshot mới ở `customer_workflow_versions`. Template upstream chỉ sync khi `source='template_sync'` (rare, opt-in).

## Consequences

### Positive
- SME bootstrap full org config trong 1 click thay vì xây từ canvas trắng.
- Khi customer đổi ý chọn industry khác sau bootstrap → có `force=true` re-bootstrap.
- Immutable snapshot per save → audit trail như git tag.
- 3-mode rõ ràng who-can-edit-what; reduce risk SME phá workflow.
- Foundation cho FE Workflow Library page (per-industry empty state + "Tạo workflow đầu tiên cho phòng Sales").

### Negative
- Thêm 10 bảng + 6 view → schema phình. Mitigation: không có RLS bottleneck (5 bảng read-only platform-shared); 5 bảng RLS đã có index trên enterprise_id.
- Seed 3 of 8 industry → cần documentation rõ "5 còn lại defer", tránh khách hỏi "tại sao tôi không thấy F&B?".
- Bootstrap row UNIQUE per enterprise → re-bootstrap force=true là destructive (drop prior row); cần guard rail UI confirm 2 lần.
- FE phải đợi restructure (paused per CLAUDE.md §2) để render Workflow Library page. BE foundation sẵn, FE chỉ wire khi resume.

### Neutral
- Không phá compatibility với 25 existing mig 069 templates — `industry_workflow_links` chỉ reference, không sửa.
- Workflow runner Phase 2.6 vẫn dùng `workflows.workflow_id` + executor catalog → industry layer chỉ là "menu trên runner".

## Alternatives considered

### A. Mở rộng workflow_templates với industry tag — không tách bảng
**Pros**: schema gọn hơn. **Cons**: mỗi industry phải duplicate template; "Invoice Processing" cần 3 row (retail + finance + sme). Bridge table `industry_workflow_links` cho phép template 1-to-many industry → reuse. Đã reject.

### B. Industry tier = enterprise_industry_config dạng JSONB cấu hình toàn bộ
**Pros**: 1 row per tenant. **Cons**: không có catalog level để bộ phận Kaori cập nhật. Mỗi tenant tự định nghĩa industry → "Retail của tôi" khác "Retail của bạn" → mất giá trị template. Reject.

### C. Industry tier là code-level (Python dict), không phải DB
**Pros**: dev edit dễ. **Cons**: customer-facing data phải sống ở DB để admin UI edit được; code-level constants không show trong /platform admin panel. Reject.

## Implementation refs

### BE
- Mig 101 `infrastructure/postgres/migrations/101_industry_templates.sql`
- Mig 102 `infrastructure/postgres/migrations/102_customer_workflow_versioning.sql`
- Mig 103 `infrastructure/postgres/migrations/103_industry_templates_seed.sql`
- Router `services/ai-orchestrator/routers/industry_bootstrap.py`
- Tests `services/ai-orchestrator/tests/test_industry_bootstrap_router.py`

### UX spec (anh's redesign 2026-05-20 EOD)
- **SME-facing mockup** `docs/sprint/workflow-builder-ux.html` — interactive 5-step wizard demonstrate card format chuẩn (Owner/Input/Required docs/AI action/Branch/Output/SLA). FE team reference cho React component implementation.
- **Screen inventory** `docs/sprint/feature-screens.html` — 72 màn × 6 portals. Phase 2.8 redesign: 4 màn priority updated (P2-02 Onboarding 7-step Industry-first / P2-03 Today Queue action-first / P2-04 3-view Cards-Tree-CrossWF / P2-26 3-mode Simple-Advanced-Developer + Branch Inspector) + 2 NEW (P2-31 Industry Template Library / P2-32 Bootstrap Preview).
- **Internal catalog** `docs/sprint/feature-workflows.html` — KHÔNG show cho khách. Dùng cho dev / AI agent audit.

## Links

- ADR-0022 Org-first onboarding then workflow then data (sister ADR — order of operations)
- ADR-0023 Knowing-doing gap heuristic (informs which workflows go in `recommendation_level='core'`)
- BA `docs/ba/4.2_Change_Request_Register.md` — runtime CR linked via `workflow_change_requests.ba_cr_ref`
- BA `docs/ba/3.1_SRS_Software_Requirements_Specification.md` §UC-TB-01 (workflow per phòng ban)
- CLAUDE.md §14 Phase 2.8 row
