# P5 Demo Workflow "Thu mua nông sản từ HTX" v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Nâng workflow Đồng Xanh `d2f72d21` thành flow 12 node chạy thật end-to-end trên pilot localhost: pause ở cổng phê duyệt giám đốc → duyệt → hợp đồng e-sign → hoàn tất; đủ chứng cứ demo P5 (capture/reuse/govern).

**Architecture:** Authoring qua BPMN (PUT /bpmn → POST /bpmn/sync full-replace nodes) rồi PUT config từng node bằng node_id mới. Chạy + duyệt + ký qua API ai-orchestrator :8093 (headers X-*). Không sửa code service — chỉ artifacts demo + seed data.

**Tech Stack:** ai-orchestrator FastAPI :8093, Postgres (container `kaorisystem-postgres-1`, user `kaori`, db `kaori`), bpmn_mapper.build_bpmn_xml (chạy trong container ai-orchestrator), curl/PowerShell.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-10-p5-demo-procurement-workflow-design.md`
- KHÔNG sửa code service — mọi thứ qua API + SQL seed. Artifacts demo commit vào `scripts/demo/p5_thu_mua_htx/`.
- Config runner ghi vào cột `config` (KHÔNG dùng `decision_config`).
- Số liệu thật từ `thu_mua_nong_san.xlsx` (HTX Đơn Dương, giá 2026-01). VND format "82.700.000₫" khi hiển thị.
- Node 5 dùng `call_insight_engine` (KHÔNG phải `call_risk_detection` — cái đó là tenant-health, sai ngữ nghĩa).
- BPMN sync = **full replace** → node_id đổi sau mỗi sync → mọi `$.<uuid>.field` ref phải ghi SAU sync cuối.

## Facts (đã xác minh 2026-07-10)

| Key | Value |
|---|---|
| workflow_id | `d2f72d21-21af-4351-8c0a-995afe164c74` (state ACTIVE_BASELINE) |
| enterprise_id | `3d1c1a53-f924-41fa-a4ce-defade00e898` (Công ty TNHH Thực phẩm Đồng Xanh) |
| department_id | `5350969f-1abe-4e7b-8dc5-f68f3297c551` |
| workspace_id | `0d97a317-9964-42de-9bd9-22b125f75be7` |
| Giám đốc | `4ebbb853-8aaf-4f0c-9e86-e5180337ee63` · giamdoc@dongxanh.vn · role `MANAGER` · Trần Văn Minh |
| KB (knowledge_documents, tenant_id=ent) | QĐ-01 "Ngưỡng phê duyệt hợp đồng mua" (>50tr → Giám đốc, SLA 240') · SOP-01 thu mua HTX · SOP-02 kiểm QA |
| Base URL | `http://localhost:8093` — headers `X-Enterprise-ID`, `X-User-ID`, `X-User-Role` |
| Approve authz | X-User-Role phải ∈ approver_roles của gate |
| contract node | LUÔN pause (`awaiting_approval`); POST /contracts/{id}/sign đủ chữ ký → `hieu_luc` → tự resume run |
| $.refs | `$.input.X` = run input_data; `$.<node_uuid>.X` = output node trước |
| Run statuses | queued/running → awaiting_approval → completed/failed |

API bodies: `PUT /bpmn {bpmn_xml}` · `POST /run {input_data, trigger_source:'manual'}` · `POST /approve {decision:'approve'|'reject', decision_note?}` · `POST /workflow-form-submissions {form_key, payload, source_channel:'api'}` · `PUT /nodes/{id} {config?, title_vi?, lane_name?}` · `POST /compliance/ai-uses {workflow_id, use_name, risk_tier, rationale}` · `POST /contracts/{id}/sign {party_id}`.

---

### Task 1: Sinh BPMN 2 pool-lane 14 element + PUT + sync

**Files:**
- Create: `scripts/demo/p5_thu_mua_htx/gen_bpmn.py`
- Create (generated): `scripts/demo/p5_thu_mua_htx/bpmn.xml`

**Interfaces:**
- Produces: `workflows.bpmn_xml` đã lưu; workflow_nodes 14 dòng mới (node_id MỚI) với node_type_catalog_key đúng; edges có branch true/false trên 2 nhánh gateway.

- [ ] **Step 1: Viết gen_bpmn.py** (chạy TRONG container ai-orchestrator — import bpmn_mapper). Element ids ổn định để Task 2 map config:

```python
"""Generate BPMN for 'Thu mua nong san tu HTX' v2 — run inside ai-orchestrator container."""
from workflow_runtime.bpmn_mapper import MappedNode, MappedEdge, build_bpmn_xml

def task(cid, title, key, bpmn="bpmn:ServiceTask"):
    return MappedNode(client_id=cid, bpmn_type=bpmn, title=title,
                      node_type=key, structural_type="step", executable=True,
                      kaori_node_type=key)

N = [
    MappedNode(client_id="Start_1", bpmn_type="bpmn:StartEvent", title="Nhận đơn chào bán",
               node_type="noop", structural_type="step", executable=True, is_trigger=True),
    task("Task_ReadForm",  "Đọc đơn chào bán từ HTX",          "read_form_submission"),
    task("Task_Validate",  "Kiểm tra dữ liệu đơn",              "validate"),
    task("Task_Extract",   "Bóc tách lô hàng (AI)",             "extract_entities"),
    task("Task_Rag",       "Đối chiếu QĐ-01 + SOP kiểm QA (KB)", "rag_query"),
    task("Task_Risk",      "Chấm điểm rủi ro lô hàng (AI)",     "call_insight_engine"),
    MappedNode(client_id="GW_Value", bpmn_type="bpmn:ExclusiveGateway", title="Giá trị > 50 triệu?",
               node_type="if_else", structural_type="decision_if_else", executable=True),
    task("Task_AutoLog",   "Dưới ngưỡng — ghi nhận tự duyệt",   "log"),
    task("Task_Approval",  "Giám đốc phê duyệt (QĐ-01)",        "approval_gate", "bpmn:UserTask"),
    task("Task_Contract",  "Lập hợp đồng thu mua (e-sign)",     "contract", "bpmn:UserTask"),
    task("Task_CreateTask","Lệnh nhập kho + kiểm QA (SOP-02)",  "create_task"),
    task("Task_Narrative", "Ghi lý do quyết định (AI)",         "generate_narrative"),
    task("Task_Insight",   "Đăng quyết định lên feed",          "publish_insight"),
    task("Task_Email",     "Thông báo HTX",                     "send_email", "bpmn:SendTask"),
    MappedNode(client_id="End_1", bpmn_type="bpmn:EndEvent", title="Hoàn tất",
               node_type="noop", structural_type="step", executable=True, is_throw=True),
]

def flow(i, s, t, cond=None, label=None, default=False):
    return MappedEdge(client_id=f"Flow_{i}", source_client_id=s, target_client_id=t,
                      condition=cond, label=label, is_default=default)

E = [
    flow(1,  "Start_1",       "Task_ReadForm"),
    flow(2,  "Task_ReadForm", "Task_Validate"),
    flow(3,  "Task_Validate", "Task_Extract"),
    flow(4,  "Task_Extract",  "Task_Rag"),
    flow(5,  "Task_Rag",      "Task_Risk"),
    flow(6,  "Task_Risk",     "GW_Value"),
    flow(7,  "GW_Value",      "Task_Approval", cond="${thanh_tien > 50000000}", label="Trên 50 triệu"),
    flow(8,  "GW_Value",      "Task_AutoLog",  label="Từ 50 triệu trở xuống", default=True),
    flow(9,  "Task_Approval", "Task_Contract"),
    flow(10, "Task_AutoLog",  "Task_Contract"),
    flow(11, "Task_Contract", "Task_CreateTask"),
    flow(12, "Task_CreateTask","Task_Narrative"),
    flow(13, "Task_Narrative","Task_Insight"),
    flow(14, "Task_Insight",  "Task_Email"),
    flow(15, "Task_Email",    "End_1"),
]

LANES = [
    ("Phòng Thu mua",  ["Start_1", "Task_ReadForm", "Task_Validate", "Task_AutoLog",
                         "Task_CreateTask", "Task_Email", "End_1"]),
    ("Kaori AI",       ["Task_Extract", "Task_Rag", "Task_Risk", "GW_Value",
                         "Task_Narrative", "Task_Insight"]),
    ("Ban Giám đốc",   ["Task_Approval", "Task_Contract"]),
]

xml = build_bpmn_xml(N, E, process_id="Process_thu_mua_htx",
                     process_name="Thu mua nông sản từ HTX", lanes=LANES)
print(xml)
```

Lưu ý: 3 lane (thêm lane "Kaori AI" so với spec 2 lane) — kể đúng chuyện "AI làm gì / người làm gì" của đề P5; nếu anh không thích, gộp lane Kaori AI vào Phòng Thu mua.

- [ ] **Step 2: Chạy sinh XML**

```powershell
docker cp "scripts/demo/p5_thu_mua_htx/gen_bpmn.py" kaorisystem-ai-orchestrator-1:/tmp/gen_bpmn.py
docker exec kaorisystem-ai-orchestrator-1 python /tmp/gen_bpmn.py > scripts/demo/p5_thu_mua_htx/bpmn.xml
```
Expected: bpmn.xml bắt đầu `<?xml version=...` chứa `kaori:nodeType="read_form_submission"` v.v. (Nếu import path lỗi → thử `python -c "import sys; sys.path.insert(0,'/app')"` hoặc đường module `ai_orchestrator.workflow_runtime.bpmn_mapper` — kiểm PYTHONPATH container.)

- [ ] **Step 3: PUT bpmn + sync** (PowerShell, JSON body từ file):

```powershell
$ent = "3d1c1a53-f924-41fa-a4ce-defade00e898"
$wf  = "d2f72d21-21af-4351-8c0a-995afe164c74"
$xml = Get-Content -Raw "scripts/demo/p5_thu_mua_htx/bpmn.xml"
$body = @{ bpmn_xml = $xml } | ConvertTo-Json -Depth 4
Invoke-RestMethod -Method Put -Uri "http://localhost:8093/workflows/$wf/bpmn" -Headers @{"X-Enterprise-ID"=$ent} -ContentType "application/json" -Body $body
Invoke-RestMethod -Method Post -Uri "http://localhost:8093/workflows/$wf/bpmn/sync" -Headers @{"X-Enterprise-ID"=$ent}
```
(Chú ý prefix router: nếu 404, kiểm tra prefix thật — `grep include_router` trong main app; có thể là `/api/v1/...`.)
Expected sync: `nodes_created: 15` (14 element + không — đếm theo diagram), `edges_created: 15`, `dangling_branches: []`, design_summary.pools có 3 lanes.

- [ ] **Step 4: Verify DB graph**

```powershell
docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -A -c "SET row_security=off; SELECT bpmn_element_id, node_type_catalog_key, lane_name, config FROM workflow_nodes WHERE workflow_id='d2f72d21-21af-4351-8c0a-995afe164c74' ORDER BY sequence_order;"
```
Expected: 15 dòng; GW_Value có config `{"condition": {...}}` tự lift; edges Flow_7 condition/branch `true`, Flow_8 `false` + is_default.

- [ ] **Step 5: Commit artifacts** (`git add scripts/demo/p5_thu_mua_htx + commit "feat(demo): BPMN thu mua HTX v2 12-node"`)

---

### Task 2: Ghi config 12 node (sau sync, dùng node_id mới)

**Files:**
- Create: `scripts/demo/p5_thu_mua_htx/set_configs.ps1` (hoặc .py chạy host — gọi API)

**Interfaces:**
- Consumes: node_id mới từ `GET /workflows/{wf}/tree` (map theo `bpmn_element_id`).
- Produces: config từng node như bảng dưới; `<UUID:X>` = node_id của element X.

- [ ] **Step 1: Lấy map bpmn_element_id → node_id** qua GET tree (hoặc SQL trên). Script hoá để chạy lại được sau mỗi lần re-sync.

- [ ] **Step 2: PUT config từng node** — bảng config chính xác:

| Element | config JSON |
|---|---|
| Task_ReadForm | `{"form_key": "don_chao_ban_htx", "latest_for_form": true}` |
| Task_Validate | `{"data": "$.<UUID:Task_ReadForm>.payload", "strict": true, "schema": {"type": "object", "required": ["ma_phieu", "htx_nong_ho", "items", "thanh_tien"], "properties": {"thanh_tien": {"type": "number", "exclusiveMinimum": 0}, "items": {"type": "array", "minItems": 1}, "htx_nong_ho": {"type": "string", "minLength": 3}}}}` |
| Task_Extract | `{"text": "$.<UUID:Task_ReadForm>.payload", "entity_types": ["mặt hàng", "khối lượng", "đơn giá", "chứng nhận"]}` |
| Task_Rag | `{"query": "Đơn thu mua nông sản giá trị trên 50 triệu đồng cần ai phê duyệt theo QĐ-01, và khi nhận hàng phải kiểm QA theo tiêu chuẩn nào?", "top_k": 4}` |
| Task_Risk | `{"subject": "$.<UUID:Task_ReadForm>.payload", "dimensions": ["chất lượng nguồn hàng", "độ tin cậy HTX", "biến động giá", "rủi ro công nợ"], "score_range": [0, 100], "composite_method": "mean"}` |
| GW_Value | `{"condition": {"left": "$.<UUID:Task_ReadForm>.payload.thanh_tien", "op": ">", "right": 50000000}}` (GHI ĐÈ config sync — để chạy từ UI không cần input_data) |
| Task_AutoLog | `{"level": "info", "event": "thu_mua.auto_approve_duoi_nguong", "payload": {"ma_phieu": "$.<UUID:Task_ReadForm>.payload.ma_phieu", "thanh_tien": "$.<UUID:Task_ReadForm>.payload.thanh_tien"}}` |
| Task_Approval | `{"approver_role": "MANAGER", "sla_minutes": 240, "reason_prompt": "Lô hàng vượt 50 triệu — theo QĐ-01 bắt buộc Giám đốc phê duyệt (SLA 240 phút). Xem điểm rủi ro AI và trích dẫn KB ở các bước trước khi quyết định."}` |
| Task_Contract | `{"title": "Hợp đồng thu mua nông sản — HTX Đơn Dương (demo P5)", "contract_type": "thu_mua", "value_vnd": 82700000, "sign_mode": "threshold", "required_signatures": 1, "parties": [{"party_role": "Bên mua — Đồng Xanh", "internal_user_id": "4ebbb853-8aaf-4f0c-9e86-e5180337ee63", "sign_order": 1}, {"party_role": "Bên bán — HTX Đơn Dương", "external_name": "HTX Đơn Dương", "external_email": "htxdonduong@lamdong.coop.vn", "sign_order": 2}]}` |
| Task_CreateTask | `{"task_key": "nhap-kho-{$.<UUID:Task_ReadForm>.payload.ma_phieu}", "title": "Nhập kho + kiểm QA lô HTX Đơn Dương theo SOP-02", "description": "Kiểm VietGAP, tỷ lệ hao hụt, nhiệt độ bảo quản theo SOP-02 trước khi nhập kho.", "assignee_role": "OPERATOR", "priority": "high"}` |
| Task_Narrative | `{"template": "Viết 3-4 câu tiếng Việt ghi lại LÝ DO quyết định thu mua: đơn {ma_phieu} của {htx}, tổng giá trị {thanh_tien} VND, điểm rủi ro tổng hợp {risk_composite}/100 (band {risk_band}). Nêu rõ căn cứ QĐ-01 (trên 50 triệu do Giám đốc duyệt) và điều kiện kiểm QA theo SOP-02.", "variables": {"ma_phieu": "$.<UUID:Task_ReadForm>.payload.ma_phieu", "htx": "$.<UUID:Task_ReadForm>.payload.htx_nong_ho", "thanh_tien": "$.<UUID:Task_ReadForm>.payload.thanh_tien", "risk_composite": "$.<UUID:Task_Risk>.composite", "risk_band": "$.<UUID:Task_Risk>.band"}, "max_tokens": 400}` |
| Task_Insight | `{"title": "Quyết định thu mua lô HTX Đơn Dương đã được phê duyệt", "body": "$.<UUID:Task_Narrative>.text", "severity": "info", "tags": ["thu_mua", "htx", "p5_demo"], "source_data": {"workflow": "Thu mua nông sản từ HTX", "quy_dinh": "QĐ-01"}}` |
| Task_Email | `{"to": "htxdonduong@lamdong.coop.vn", "subject": "Đồng Xanh xác nhận thu mua — đơn chào bán đã được duyệt", "body": "Kính gửi HTX Đơn Dương,\n\nĐơn chào bán của quý HTX đã được Giám đốc Đồng Xanh phê duyệt. Hợp đồng thu mua sẽ được gửi ký điện tử. Lịch giao hàng và kiểm QA thực hiện theo SOP-02.\n\nTrân trọng,\nPhòng Thu mua — Thực phẩm Đồng Xanh"}` |

Đồng thời PUT `title_vi` = title VN cho từng node (builder hiển thị tiếng Việt).

- [ ] **Step 3: Verify config đã ghi** — chạy lại SQL Task 1 Step 4, không còn node executable nào config `{}` (Start/End noop được phép `{}`).

- [ ] **Step 4: Commit script**

---

### Task 3: Seed form submission + đăng ký risk tier (K-22)

- [ ] **Step 1: POST form submission** — payload số liệu thật (giá tham chiếu xlsx TM-501/504/507/510, HTX Đơn Dương):

```json
{
  "form_key": "don_chao_ban_htx",
  "source_channel": "api",
  "payload": {
    "ma_phieu": "TM-520",
    "ngay_giao_du_kien": "2026-07-12",
    "htx_nong_ho": "HTX Đơn Dương",
    "dat_vietgap": "Có",
    "items": [
      {"mat_hang": "Rau cải ngọt", "san_luong_kg": 2000, "gia_mua": 12000, "thanh_tien": 24000000},
      {"mat_hang": "Xà lách",      "san_luong_kg": 1500, "gia_mua": 14000, "thanh_tien": 21000000},
      {"mat_hang": "Bắp cải",      "san_luong_kg": 3000, "gia_mua": 6500,  "thanh_tien": 19500000},
      {"mat_hang": "Hành lá",      "san_luong_kg": 1400, "gia_mua": 13000, "thanh_tien": 18200000}
    ],
    "thanh_tien": 82700000,
    "ghi_chu": "Đơn mùa vụ tháng 7. Công nợ kỳ trước còn 12.000.000. Giá xà lách thị trường đang biến động ±10%."
  }
}
```
Headers: X-Enterprise-ID + X-User-ID (giám đốc). Expected 201, lưu submission_id.

- [ ] **Step 2: POST /compliance/ai-uses** `{"workflow_id": "<wf>", "use_name": "Thu mua nông sản từ HTX — AI hỗ trợ thẩm định", "risk_tier": "limited", "rationale": "AI chỉ chấm điểm rủi ro + trích dẫn KB hỗ trợ; quyết định cuối cùng do Giám đốc (human-in-the-loop theo QĐ-01)."}` Expected 201.

---

### Task 4: Smoke run API end-to-end (checkpoint chính)

- [ ] **Step 1: Start run** `POST /workflows/{wf}/run` body `{"input_data": {}, "trigger_source": "api"}` + Idempotency-Key mới. Expected 202, status queued/running.
- [ ] **Step 2: Poll** `GET /workflow-runs/{run_id}` mỗi ~5s (LLM local có thể 1-3 phút qua 3 node AI). Expected: `awaiting_approval`. `GET /workflow-runs/{run_id}/nodes`: ReadForm→Risk `completed`, AutoLog `skipped` (branch false không chạy), Approval `awaiting_approval`.
- [ ] **Step 3: Kiểm output trung gian** (run nodes): Task_Rag output có `citations` ≥1 trỏ tới QĐ-01/SOP; Task_Risk có `composite`+`band`. Nếu Rag 0 citation → debug /rag/answer trực tiếp trước khi đi tiếp.
- [ ] **Step 4: Approve** `POST /workflow-runs/{run_id}/approve` `{"decision": "approve", "decision_note": "Duyệt theo QĐ-01 — rủi ro chấp nhận được, HTX uy tín."}` headers X-User-ID=giamdoc + X-User-Role=MANAGER. Expected: chạy tiếp → pause lần 2 tại Task_Contract (`awaiting_approval`), bảng contracts có dòng mới `cho_ky`.
- [ ] **Step 5: Ký hợp đồng** — `GET /contracts?...` hoặc SQL lấy contract_id + party_id (Bên mua, sign_order 1); `POST /contracts/{id}/sign {"party_id": "<party bên mua>"}`. Expected: `hieu_luc` (threshold 1 chữ ký) → run tự resume → poll đến `completed`.
- [ ] **Step 6: Verify hậu kiện** (SQL): run status completed + 0 node failed; insights có dòng title "Quyết định thu mua..."; notification_outbox có email queued; ai_decision_audit có bản ghi các call LLM của run. Ghi các số liệu này ra để dùng cho video.
- [ ] **Step 7: Sửa vòng lặp** — bất kỳ node fail: đọc `error_message` ở run nodes + log container, sửa config (Task 2 script), re-run. KHÔNG sync lại BPMN trừ khi đổi cấu trúc (sync xoá node_id → phải chạy lại toàn bộ Task 2).

---

### Task 5: Verify UI (đường demo thật) + để sẵn 1 run đang chờ duyệt

- [ ] **Step 1** (browser): login `giamdoc@dongxanh.vn` / `DongXanh@2026` → mở workflow builder canvas: 3 lane + 15 element hiển thị đúng, node có icon/label VN.
- [ ] **Step 2**: bấm Chạy từ UI (không input) → xem run pause ở cổng phê duyệt trong UI; màn phê duyệt hiện reason_prompt.
- [ ] **Step 3**: duyệt trong UI → màn contract (nếu FE có) ký → run completed; insight feed hiện quyết định; Nhật ký AI (decisions) có bản ghi mới. Nếu FE thiếu màn ký contract → ký qua API là fallback demo (ghi vào runbook).
- [ ] **Step 4**: `/p2/compliance` hiện dòng risk register "Thu mua... — limited".
- [ ] **Step 5**: seed thêm 1 form submission thứ hai + start 1 run mới để **đứng sẵn ở awaiting_approval** — cảnh quay mở màn Hồi 2.
- [ ] **Step 6**: viết `scripts/demo/p5_thu_mua_htx/README.md` (runbook: cách re-seed, re-run, các URL màn hình) + commit.

---

## Self-review

- Spec coverage: flow 12 node (Task 1-2) ✓; seed thật (Task 3) ✓; risk_tier limited K-22 (Task 3.2) ✓; acceptance 1-3 (Task 4) ✓; acceptance 4-5 UI (Task 5) ✓; contract pause xử lý bằng e-sign threshold=1 (quyết định: GIỮ contract trong main path — sign→auto resume đã wired, xác minh ở Task 4 Step 5) ✓.
- Deviation ghi rõ: 3 lane thay vì 2 (nêu ở Task 1 Step 1); node 5 = call_insight_engine (Global Constraints).
- Không placeholder: mọi config/payload/lệnh đầy đủ; `<UUID:X>` là tham số runtime có nguồn xác định (GET tree sau sync).
