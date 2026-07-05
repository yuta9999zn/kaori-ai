# Workflow Builder FE — Redesign Spec (Hybrid Lane + Canvas)

> **⚠ PIVOT 2026-05-29:** anh chốt **builder FE = BPMN THẬT** (không phải card-chain). Dùng **`bpmn-js`** (engine bpmn.io / Camunda Modeler): palette kéo-thả đầy đủ ký hiệu BPMN + đọc/ghi **BPMN 2.0 XML** native. → Hướng card-chain P0/P1/P2 (lane/canvas tự vẽ) **bị thay** bởi bpmn-js. P0 đã ship (branch→edge) vẫn còn giá trị ở tầng BE (port_type/validator) nhưng UI sẽ là bpmn-js. palette ký hiệu: `docs/sprint/bpmn-elements-palette.html` · catalog: `frontend/lib/bpmn/bpmn-elements.ts`. (POC HTML `bpmn-builder-poc.html` đã gỡ sau khi bpmn-js lên production.) Chi tiết → §11 cuối file.
>
> **Status:** P0 SHIPPED 2026-05-29 (template `60-workflow-detail.tsx` + BE `workflow_builder.py`) · PIVOT sang bpmn-js (§11).
> **Author:** Kaori (em) per anh's request "review FE workflow, người dùng vẫn khó dùng".
> **Decision locked:** Hướng **C — Hybrid** (lane view mặc định cho SME + canvas nâng cao cho analyst). P0 làm trên template hiện tại theo chỉ đạo anh 2026-05-29.
> **Screen:** P2-26 `/p2/workflows/[id]` · file `frontend/components/p2/templates/60-workflow-detail.tsx`.
> **Demo trao đổi:** `docs/sprint/workflow-builder-p0-cases.html` — tái hiện tĩnh cách FE P0 render từng case (fork + selector + gallery 10 node-type), mở browser để bàn.
> **Liên quan:** `docs/sprint/workflow-builder-ux.html` (mockup n8n-style) · ADR-0035 typed ports · mig 053/114.

---

## 1. Vấn đề gốc (vì sao "khó dùng")

FE builder hiện tại render workflow như **một list dọc 1 cột** sort theo `sequence_order`
(`BuilderView` :757-819). Giữa các card là `Connector` (:1098-1294) — với node quyết định
nó vẽ **chip nhãn** IF/ELSE/CASE rồi **luôn chụm về 1 mũi tên xuống đúng 1 card kế tiếp**.

Hệ quả — đối chiếu thực tế:

| # | Triệu chứng | Nguyên nhân code |
|---|---|---|
| ① | Doc có mũi tên chia nhánh, FE không | `Connector` không bao giờ vẽ edge tỏa sang nhiều node đích; nhánh chỉ là metadata trang trí |
| ② | Tạo node "Quyết định" → bị chặn activate "cần 2 nhánh" nhưng **không có nút tạo nhánh** | Edge chỉ tạo tự động tuyến tính `prev→new` (:191-203); `IfElseBranchesEditor`/`SwitchCasesEditor` chỉ lưu `decision_config`, **không bind branch → target node** qua edge |
| ③ | Reorder up/down vô nghĩa khi có nhánh | `moveCard` đảo `sequence_order` 1-D (:383-403); schema đã có `position_x/y` nhưng FE bỏ không dùng |

**Kết luận:** mô hình "list thẳng" không thể biểu diễn DAG có nhánh mà BE (mig 053 + ADR-0035)
và HTML mockup đã hỗ trợ. Phải đổi mô hình FE, không vá vặt.

---

## 2. Quyết định kiến trúc — Hybrid (C)

Hai view trên cùng một workflow, cùng một nguồn dữ liệu (`edges` là source-of-truth, KHÔNG phải `sequence_order`):

- **Lane view (mặc định, SME manager).** Đọc dọc top-down. Node quyết định **fork thật** ra
  các lane thụt lề có nhãn (IF / ELSE IF / ELSE / CASE / nhánh song song); mỗi lane là mini-chain
  riêng dẫn tới node đích thật. Mobile-friendly, "rõ vật thể", hợp ngôn ngữ nghiệp vụ.
- **Canvas view (nâng cao, analyst).** Node-graph tự do (React Flow): node đặt trên canvas x/y,
  edge là bezier, node quyết định có **nhiều output handle có nhãn**, kéo-thả tới node đích.
  Khớp 100% mockup `workflow-builder-ux.html` + ADR-0035 typed ports.

Gating khớp SIMPLE/ADVANCED mode mockup đã định (`workflow-builder-ux.html:1113,1181`):
canvas + sửa topology = quyền analyst; SME chỉ sửa nội dung trong lane view.

---

## 3. BE gaps phải vá TRƯỚC (block FE)

| # | Gap | File | Việc |
|---|---|---|---|
| BE-1 | `EdgeOut` + `EdgeCreate` chưa có `port_type` (mig 114/ADR-0035 đã thêm cột, runner đã đọc — chỉ API chưa expose) | `routers/workflow_builder.py:180-185`, `EdgeCreate`, `_row_to_edge:325` | Thêm `port_type: str = "main"` vào cả 2 schema + `_row_to_edge` + INSERT (:843-853). Default `'main'` để back-compat. |
| BE-2 | Không có PUT edge | router | **Không cần** — `create_edge` đã `ON CONFLICT (workflow_id,source,target) DO UPDATE` (:847) nên sửa condition/label = POST lại; reroute = DELETE + POST. ⚠️ unique key là (source,target) → 2 nhánh cùng cặp source→target không cùng tồn tại (OK cho if/else vì khác target). |
| BE-3 | Dangling-branch validator đã có nhưng FE re-derive cục bộ | router :346-395 (`expected_edges`/`actual_edges`) | FE nên **đọc validator BE làm source-of-truth** thay vì tự tính `activationBlockers` (:357-380) — tránh lệch luật. |

⚠️ **Drift checklist (K rule):** sửa `EdgeOut` → phải regen OpenAPI + FE types + cập nhật
`docs/specs/UI_SCREENS_INVENTORY.md` P2-26 + `docs/sprint/workflow-builder-ux.html` cùng PR
(per anh's 2026-05-23 rule "update related docs").

---

## 4. Data model FE (đổi mental model)

```
Nguồn sự thật topology   = edges[]  (source_node_id, target_node_id, condition, label, port_type)
sequence_order           = CHỈ dùng để xếp thứ tự render trong 1 lane tuyến tính, KHÔNG định nghĩa luồng
position_x / position_y   = toạ độ canvas (đang bị FE bỏ; canvas view dùng, lane view ignore)
decision_config.branches  = nhãn + điều kiện hiển thị; MỖI branch phải map tới 1 edge thật (bằng label/condition)
```

**Quy tắc bind branch ↔ edge:** mỗi row trong `IfElseBranchesEditor`/`SwitchCasesEditor` mang
`condition` + `label`. Khi user chọn "→ đi tới bước X", FE POST một edge
`{source: node, target: X, condition: branch.condition, label: branch.label, port_type: 'main'}`.
Branch chưa gán target = "dangling" → hiện cảnh báo (khớp BE validator BE-3).

---

## 5. Lane view — spec (P1)

- Thay `BuilderView` list-phẳng bằng **layout đệ quy theo edges**: từ node "Bắt đầu", duyệt edge
  `main` ra; node có >1 out-edge `main` → render N lane song song thụt lề, mỗi lane đệ quy tiếp.
- Mỗi lane header = nhãn branch (IF/ELSE/CASE/«song song i»), màu theo `NODE_TYPE_STYLES` (đã có).
- Lane hội tụ (parallel_join / nhiều nhánh về cùng node) → vẽ đường gộp về 1 node, không nhân bản card.
- Cycle/độ sâu: dùng `topological_order` mirror của runner (`workflow_runtime/runner.py:100`) để phát hiện
  cycle + giới hạn độ sâu render; gặp lại node đã vẽ → vẽ "đi tới «Tên bước»" link thay vì lặp.
- CardEditor (drawer phải) **giữ nguyên** — đã tốt; chỉ thêm mục §6.

## 6. Branch → target selector (P0, dùng cho cả 2 view)

Trong `IfElseBranchesEditor` (:1675) và `SwitchCasesEditor` (:1813), mỗi branch/case row thêm:

```
[ nhãn ] [ điều kiện ] [ → đi tới: «dropdown các node trong workflow» ]
```

- Chọn target → POST edge (condition+label của branch). Đổi target → DELETE edge cũ + POST mới.
- Hiển thị trạng thái: ✅ đã nối / ⚠️ chưa nối (dangling).
- `approval_gate`/`parallel_split`/`wait_event`... cũng cần selector "bước kế tiếp" tương tự
  (hiện chỉ auto-edge tuyến tính).

→ Riêng P0 này đã **gỡ được dead-end ② + cho thấy nhánh thật**, kể cả khi chưa có canvas.

## 7. Canvas view — spec (P2)

- Lib: `@xyflow/react` (React Flow v12). **CHƯA cài** trong `frontend/package.json`.
  ⚠️ `frontend/AGENTS.md`: Next.js bản này có breaking changes — đọc `node_modules/next/dist/docs/`
  + kiểm SSR/`'use client'` compat trước khi thêm dep.
- Node custom render theo `node_type` (tái dùng `NODE_TYPE_STYLES`); output handle có nhãn theo branch.
- Edge kéo-thả tạo/xoá → gọi POST/DELETE edge (mục §3). `onNodeDragStop` → PUT `position_x/y`.
- Auto-layout gợi ý: `dagre` hoặc `elkjs` cho "sắp xếp gọn" (optional).
- Typed ports ADR-0035: handle riêng cho `ai_tool`/`ai_memory`/`ai_model` (màu khác `main`),
  cho agent node — chỉ hiện ở canvas + quyền analyst.

---

## 8. Task breakdown (theo thứ tự ship)

**P0 — Unblock (nhỏ, gỡ đúng phàn nàn, không đổi layout) — ✅ SHIPPED 2026-05-29:**
- [x] BE-1 thêm `port_type` vào EdgeOut/EdgeCreate/_row_to_edge/INSERT (`workflow_builder.py`).
      Default 'main', `row.get()` back-compat cho DB chưa apply mig 114. 51 test edge xanh.
      (Repo không có openapi snapshot; FE types sửa tay trong template @ts-nocheck.)
- [x] FE: mỗi if/else branch + switch case/default có `BranchTargetSelect` "→ đi tới bước" →
      tạo/xoá **edge thật** qua `setBranchEdge` (POST upsert / DELETE). Hiện "✓ đã nối / ⚠ chưa nối".
      `target_node_id` lưu trên branch config làm UI-mirror; **edge là source-of-truth** topology.
- [x] FE: `Connector` vẽ **fork thật** khi node có ≥2 out-edge `main` — tỏa N nhánh kèm **tên node đích**.
- [x] FE: `activationBlockers` chỉ đếm port `main` + bám luật BE (if_else ≥2, switch ≥cases+default,
      split ≥branch_count); BE validator vẫn là cổng chốt cuối qua PUT state `.issues[]`.

**P1 — Lane view (đổi mental model, SME-facing) — DECISIONS LOCKED 2026-05-29:**
- [ ] **Lane DỌC THỤT LỀ (top-down)**, KHÔNG cột cạnh nhau. Lý do: SME đọc quy trình theo chiều
      dọc tự nhiên (như flowchart giấy); cột song song kiểu n8n để toggle ở P2. → `LaneView` đệ quy
      theo edges, mỗi nhánh = block thụt lề có header nhãn (§5).
- [ ] **KHOÁ nhãn nhánh sau khi nối.** Nhãn là khế ước node Quyết định ↔ node đích ↔ BE validator;
      đổi tên tự do = bug âm thầm + lệch edge-match. Muốn đổi → **ngắt nối → đổi → nối lại** (UX đúng).
      Bỏ luôn rủi ro label-match ở P0.
- [ ] **BỎ HẲN up/down.** Trong mô hình lane, "lên/xuống" vô nghĩa. Thay bằng: thêm bước = append
      vào cuối nhánh (auto-position theo nhánh đang chọn).
- [ ] **Disclaimer runtime NGAY TRÊN UI** — badge nhỏ `⚙ Thiết kế — chưa thực thi` (hoặc banner đầu
      trang) để khách/stakeholder không hiểu nhầm flow đẹp = chạy thật. Runtime thật chờ Phase 2/Temporal.
- [ ] **MERGE/hội tụ nhánh → ĐẨY SANG P2** (không làm ở P1). Join cần xử lý race / chờ-tất-cả-hay-1 /
      timeout + BE support → P1 chỉ làm fork (1→nhiều), merge đợi canvas trưởng thành.
- [ ] Cập nhật `workflow-builder-ux.html` + `workflow-builder-p0-cases.html` + UI_SCREENS_INVENTORY P2-26.

**P2 — Canvas nâng cao (analyst-facing):**
- [ ] Cài `@xyflow/react` (sau khi kiểm AGENTS.md compat).
- [ ] `CanvasView` + custom node/edge + drag-to-connect + lưu `position_x/y`.
- [ ] Typed ports handle (ADR-0035) cho agent node.
- [ ] SIMPLE/ADVANCED gating theo quyền (analyst).

---

## 9. Rủi ro & câu hỏi mở

1. ✅ RESOLVED 2026-05-29 — **làm trên template hiện tại** (anh chốt); port sang nền mới khi restructure.
2. **Next.js bản modified** — React Flow (P2) có thể vướng SSR; cần spike nhỏ trước khi cam kết P2.
3. ✅ RESOLVED 2026-05-29 — **CÓ, ghi ngay trên UI** badge `⚙ Thiết kế — chưa thực thi` (P1, không chỉ trong doc).
4. **2-edge-cùng-cặp:** nếu sau này cần nhiều edge cùng (source→target) khác điều kiện, unique key
   (workflow,source,target) sẽ chặn — cần nới constraint (thêm port_type/condition vào key). Chưa cấp bách.

## 10. Test plan (khi code)

- BE: edge port_type round-trip; dangling validator cho if/else/switch/parallel.
- FE: branch selector tạo đúng edge; reroute xoá+tạo; fork render N đường; lane đệ quy không cycle-loop.
- E2E (Playwright, mirror `step5-charts` spec): dựng if/else 2 nhánh tới 2 node → activate pass.

---

## 11. PIVOT — Builder = BPMN thật (bpmn-js) · 2026-05-29

anh chốt: workflow builder phải là **BPMN chuẩn** (như ảnh "duyệt 2 cấp" Camunda), dùng đúng ký hiệu +
nối đúng (sequence trong pool, message giữa pool), chia rõ **pool/lane/nghiệp vụ** từ yêu cầu khách.
→ Không tự vẽ lane/canvas; **nhúng `bpmn-js`** (bpmn.io modeler, cùng engine Camunda Modeler).

**Vì sao bpmn-js:** palette kéo-thả đầy đủ BPMN 2.0 · context-pad nối/đổi loại element · đọc/ghi
**BPMN 2.0 XML** native (đúng nhu cầu export ưu tiên sớm) · chuẩn ngành, không phải reinvent.
(POC CDN ban đầu `docs/sprint/bpmn-builder-poc.html` đã gỡ — bpmn-js nay chạy trong FE thật, xem `frontend/components/bpmn/BpmnEditor.tsx`.)

**Tích hợp vào FE thật (Next.js bản modified — AGENTS.md):**
1. `npm i bpmn-js` (+ `bpmn-js-properties-panel` + `@bpmn-io/properties-panel` cho panel thuộc tính;
   + `camunda-bpmn-moddle` nếu cần thuộc tính thực thi). bpmn-js là **client-only** → import động
   `ssr:false` (Next): `const Modeler = dynamic(()=>import('./BpmnEditor'), {ssr:false})`. Cần spike compat trước.
2. Component `BpmnEditor` bọc `BpmnJS({container})`; load/save XML; nút Xuất `.bpmn`.
3. ⚠ **License:** bpmn-js theo **bpmn.io license** — cho dùng nhưng **yêu cầu giữ credit/logo bpmn.io**;
   SaaS thương mại cần review (giữ attribution hoặc license riêng với Camunda). **Phải xác nhận trước khi ship.**

**Mô hình dữ liệu — BPMN XML ↔ engine Kaori:**
- **Nguồn sự thật diagram = BPMN 2.0 XML** (lưu trên workflow, cột mới `bpmn_xml TEXT`).
- Engine chạy (runner hiện tại) ăn `workflow_nodes/edges`. → cần **mapper 2 chiều**: parse BPMN XML →
  nodes/edges (map `bpmnType` → `node_type_catalog_key`; `sequenceFlow`→edge `main`; pool/lane → cột mới).
- **Subset thực thi:** không phải mọi ký hiệu BPMN đều chạy được ngay. Định nghĩa **BPMN subset Kaori hỗ trợ**
  (start/end none+message+timer, task types map sang executor, exclusive/parallel gateway, sub-process) →
  validator cảnh báo ký hiệu "vẽ được nhưng chưa thực thi" (gắn badge `⚙ Thiết kế — chưa thực thi`).
- `port_type` (ADR-0035, P0) + dangling validator vẫn dùng ở tầng BE sau khi map.

**Catalog ký hiệu (nơi lưu trữ, phục vụ palette):** `frontend/lib/bpmn/bpmn-elements.ts` — toàn bộ element
BPMN 2.0 (metadata + base/marker để render icon), mirror ở `docs/sprint/bpmn-elements-palette.html`.
bpmn-js đã có palette riêng; catalog này dùng cho: palette tuỳ biến VN, lọc subset hỗ trợ, mapping bpmnType↔node_type.

**Quy trình dựng từ yêu cầu khách (anh nhấn mạnh):** yêu cầu nghiệp vụ → xác định participant (Pool/Lane theo
role; bên ngoài tổ chức = pool riêng + message flow) → liệt kê nghiệp vụ thành Task đúng loại → điểm rẽ = Gateway
→ sự kiện đầu/cuối = Event → nối. (Chi tiết §C trong `bpmn-elements-palette.html`.)

**Việc tiếp theo — 2026-05-29:**
- [x] anh xác nhận hướng bpmn-js (a=OK) · [x] research license bpmn.io (§11.1) · [x] chốt model A · [x] catalog backbone `bpmn-elements.ts`.
- [x] **#8** cột `bpmn_xml` TEXT (mig 115) + endpoint `GET`/`PUT /workflows/{id}/bpmn` (`workflow_builder.py`). GET tolerant pre-mig (`row.get`); PUT validate parse → 400 `WORKFLOW.INVALID_BPMN`, trả `design_summary`. 6 router test.
- [x] **#9** mapper BPMN XML ↔ nodes/edges — `workflow_runtime/bpmn_mapper.py` (pure, no DB). 45 action key KHÔNG hardcode — caller truyền `known_node_types` từ DB.
- [x] **#9b FULL-FIDELITY** (anh chốt option 2, đối chiếu OMG BPMN 2.0.2 `formal/2013-12-09`): parse đầy đủ **Pool/Participant + Lane (role)** §9.3/§10.8, **Message Flow** cross-pool §9.4, **nested Sub-Process** recursion, **Boundary event** (`attachedToRef`), gateway **`default` flow**, đủ **event-definition** (timer/message/error/escalation/compensation/cancel/terminate/signal/conditional/link/multiple) §10.5.5, Exclusive/Inclusive/Parallel/Complex/Event-Based gateway §10.6. Ngoài subset thực thi (vẫn vẽ được trong bpmn-js): Conversation §9.5, Choreography §11, data object/artifact. `summarize` trả pools/lanes/message_flow_count/boundary_count/design_only.
- [x] **mig 116** — cột BPMN-origin trên `workflow_nodes` (`bpmn_element_id`/`bpmn_type`/`kaori_node_type`/`pool_name`/`lane_name`/`event_definition`/`attached_to_ref`) + `workflow_edges` (`flow_kind` sequence|message, `is_default`). Additive, nullable. `NodeOut` expose (tolerant pre-mig). Pool/lane = **"phân chia theo role"** anh yêu cầu.
- [x] **`POST /workflows/{id}/bpmn/sync`** — chiếu BPMN đã lưu → **replace** `workflow_nodes`/`workflow_edges` (model A: BPMN là nguồn sự thật) → tree view + builder thấy step kèm pool/lane/event-def. `structural_type_for` map BPMN type → enum `node_type` (mig 060) trong CHECK; `kaori_node_type` giữ executor intent. Idempotent. **30 mapper test + 9 router test (sync/bpmn) — 400 workflow test xanh.**
- [x] **NỐI RUNNER + làm rõ schema (anh 2026-05-29 "hardcode/không rõ ràng → làm rõ, sửa, test"):** phát hiện **3 cột phantom** runner SELECT mà KHÔNG migration nào tạo — `workflow_nodes.node_type_catalog_key`, `workflow_nodes.config_json`, `workflow_edges.condition_expr` (cột thật: `config`, `condition`; executor-key thiếu hẳn). Run-path xưa nay chỉ pass vì test mock DB. **Fix (mig 117, 1 nguồn sự thật, KHÔNG cột trùng):** rename `kaori_node_type`(mig 116)→**`node_type_catalog_key`** (đúng tên catalog 068/template 069/runner); state_store alias `config AS config_json` + `condition AS condition_expr`. Sync ghi `node_type_catalog_key = key đã resolve` (n.node_type, không phải attr thô None ở gateway); `clone_from_template` + `create_node` cũng populate → workflow clone/builder chạy được trên runner. Sync trả thêm `dangling_branches` (reuse `_check_dangling_branches`). Guard test `test_workflow_runtime_schema_alignment.py` chốt SELECT dùng cột thật. **Full suite 2743 pass.**
- [x] **#11 watermark — anh CHỐT BỎ 2026-05-29:** giữ watermark bpmn.io, không lo bản quyền → KHÔNG cần liên hệ Camunda OEM.
- [x] **#7 nhúng bpmn-js + #10 properties panel — DONE 2026-05-30 (FE resume):** chi tiết §13.
- [x] **control-flow executor — ĐÃ KIỂM 2026-05-29: đủ cả 4.** `if_else`/`switch` (`executors/pure.py`), `split`/`join` (`executors/utility.py`) — đều có trong `register_builtin_executors()` → `REGISTRY.has()` = True. Gateway-synced node route bằng `node_type_catalog_key` khớp executor, KHÔNG rơi design-only. Guard test `test_control_flow_executors_registered` + `test_every_mapper_emitted_key_has_executor`. 45/45 catalog coverage giữ nguyên.
- [x] **RẼ NHÁNH end-to-end — FIX + test sâu 2026-05-29 (anh yêu cầu):** phát hiện runner **chạy MỌI node theo topo order, KHÔNG prune nhánh** — `condition_expr` load vào snapshot nhưng vô dụng; if_else chỉ emit `branch` signal mà không ai dùng. **Fix:** thêm **branch-gating** trong run loop (`runner.py`): node có incoming `main` edge chỉ chạy nếu ≥1 edge "live" = nhánh được chọn của decision phía trên (if_else→`output.branch`, switch→`output.matched_case`), khớp qua token `condition_expr`/`label`/`is_default`. Nhánh không đi → node `skipped` + lan truyền xuống (node chỉ reachable qua nhánh chết cũng skip); merge-point sống nếu ≥1 nhánh vào còn live. **Back-compat:** token không nhận diện / source không phải decision → edge giữ live (không prune bừa) → workflow tuyến tính + 2751 test cũ không đổi. state_store edge SELECT thêm `label`/`is_default`. **e2e `test_workflow_branching_e2e.py` (6 case):** if_else true/false đi đúng nhánh + skip nhánh kia + transitive, merge-point, switch matched + default fallthrough, linear không prune. **Full suite 2751 pass.**
- [x] **BPMN gateway → if_else config — DONE 2026-05-29 (anh yêu cầu):** mapper `_derive_gateway_conditions` nâng điều kiện trên *conditional flow* của exclusive gateway (2 nhánh) vào **`if_else` node config** (`{condition:{left,op,right}}`) + gắn **token nhánh** lên edge (conditional→`true`, default→`false`). `parse_condition_expression` best-effort: bóc `${…}`/`#{…}`, 1 phép so sánh (`==`/`!=`/`>=`/`<=`/`>`/`<`/`=`→`==`), coerce literal (số/bool/chuỗi), **bare identifier `score` → `$.input.score`**. Compound and/or / hàm / không op → trả None + warn (giữ raw, chỉnh tay ở properties panel). `_resolve` (pure.py) **thêm `$.input.<field>`** → đọc từ run input → if_else đánh giá được. Sync ghi `config` thật + `condition` = token nhánh (raw expr nằm ở bpmn_xml — nguồn thiết kế). Tests: `TestConditionExpressionParse`(5) + `TestGatewayConditionLift`(2) + e2e `test_if_else_condition_from_run_input` (score 90→true / 50→false). **Full suite 2759 pass.**
- [x] **>2 nhánh → switch + compound condition — DONE 2026-05-30 (anh yêu cầu):**
  - **Compound (and/or):** `parse_condition_expression` giờ parse `and`/`or` (`&&`/`||`) → `{and:[…]}`/`{or:[…]}` (OR bind lỏng hơn AND), đệ quy; `IfElseExecutor._eval_condition` đã hỗ trợ sẵn. Leaf không parse được → cả cụm None + warn.
  - **Switch từ gateway nhiều nhánh:** `_derive_gateway_conditions` — gateway (exclusive >2 / inclusive / complex) có ≥2 conditional flow mà điều kiện đều `x == v` trên **cùng 1 biến** → map `switch` config `{input, cases:[{when,then}], default}`, node_type→`switch`, mỗi case edge token = `str(v)`, default edge token `default`. Điều kiện không đồng nhất (range, khác biến) / event-based không điều kiện → warn "cấu hình ở properties panel" (honest — switch value-match không biểu diễn được N điều kiện boolean tùy ý).
  - Tests: `TestGatewaySwitchLift` (uniform→switch, non-uniform→warn, inclusive→switch) + compound parse units + e2e `test_if_else_compound_and_condition` + `test_switch_three_way_from_input`. **Full suite 2767 pass.**
- [ ] (còn lại) gateway điều kiện boolean N-way KHÁC biến / range (vd `score>80` / `score>50`) → cần node "chained elif" hoặc decision-table; hiện warn + chỉnh tay. event-based gateway (chờ sự kiện) ngoài phạm vi value-switch.

Commit chốt: `7fab6a3` (P0) · `09a619c` (pivot+catalog) · **#8+#9** (mig 115 + bpmn_mapper + endpoints + tests) — local main.

### 11.1 License bpmn-js (kết quả nghiên cứu 2026-05-29)
- **Miễn phí + cho phép thương mại** (dùng/sửa/bán). NHƯNG **bắt buộc giữ watermark "bpmn.io"** —
  license cấm gỡ/che; watermark phải hiển thị đầy đủ, không bị element khác đè.
- Trang license **không** nêu bản OEM/white-label → muốn gỡ watermark cho SaaS phải **liên hệ Camunda** (trả phí).
- Không có lib editable-BPMN FOSS nào ngang bpmn-js. **Khuyến nghị:** dùng bpmn-js (chấp nhận watermark) cho
  POC/nội bộ ngay; **đàm phán OEM với Camunda trước khi GA thương mại** nếu watermark không chấp nhận được.

### 11.2 Mô hình 2 tầng (anh chốt 2026-05-29) — BPMN (thiết kế) → engine Kaori (vận hành)
anh: workflow xây theo doanh nghiệp; cần "một chỗ nữa như n8n" — từ BPMN chuẩn **cover sang** workflow
doanh nghiệp dùng được (đính kèm file / gửi mail / đánh giá). **Đánh giá: rất hợp lý — và tầng vận hành Kaori ĐÃ CÓ.**

- **Tầng 1 — BPMN (blueprint/thiết kế):** bpmn-js. Analyst/stakeholder thiết kế quy trình chuẩn, chia pool/lane/role.
- **Tầng 2 — Vận hành (n8n-like, ĐÃ TỒN TẠI):** `node_type_catalog` + ~30 executor + runner (Phase 6, ADR-0034/0035):
  - `send_email` ✅ (gửi mail, side_effect=external) · `create_task` · `publish_alert` · `publish_insight`
  - `classify_text`/`call_risk_detection`/`call_insight_engine`/`call_forecasting` ✅ (= "đánh giá"/scoring)
  - file: `workflow_nodes.attached_documents` + Phase 2.5 extract/classify/OCR trên file đính kèm
  - `approval_gate` · `read_form_submission` · `save_to_database` · if_else/gateway…
- **"Cover sang" = mapper** BPMN task → executor (`bpmnType`/task-type → `node_type_catalog_key`). Subset thực thi
  = các BPMN task có executor; ngoài subset → badge `⚙ Thiết kế — chưa thực thi`.
- **Theo doanh nghiệp:** Kaori đã có **template → clone per-enterprise** (industry templates Phase 2.8, `customer_workflow_versions` mig 102). BPMN template chuẩn ngành → doanh nghiệp clone + cấu hình connector thật.

**Quyết định kiến trúc: ✅ anh chốt (A) 2026-05-29 — 1 model + config panel.**
- BPMN XML là model duy nhất; mỗi task gắn config Kaori (mail nào, file nào, tiêu chí đánh giá) qua extension
  `kaori:nodeType` + properties panel. Runner map task→executor. KHÔNG drift, không maintain 2 nơi.
- (B 2-artifact "cover" — loại; rủi ro 2 model lệch nhau.)

**Catalog backbone đã tạo:** `frontend/lib/bpmn/bpmn-elements.ts` — 45 `KAORI_ACTIONS` (khớp executor BE) +
`BPMN_TO_NODETYPE` + `EXECUTABLE_BPMN_TYPES` + `resolveNodeType()`/`isExecutable()`/`actionsForBpmnType()`.
Đây là nguồn cho properties panel (gán action vào task) + mapper BE (BPMN element → node_type) + badge subset.

---

## 12. Engine logic audit + fixes — 2026-05-30

anh: "tổ hợp các loại workflow, test thực thi hết item, soi lỗi logic." Chạy audit đa-agent (38 agent, adversarial verify) → **21 bug logic confirmed**. Đã **sửa + test** nhóm ảnh hưởng workflow thật; ghi follow-up nhóm robustness.

**ĐÃ SỬA (có regression test):**
| # | Bug | Fix |
|---|---|---|
| 15/16 | **Start/End event → `node_type_catalog_key=None` → run fail ngay** ("No executor for None"), chặn MỌI workflow BPMN | `NoopExecutor` mới + `BPMN_TO_NODETYPE` map start/end/intermediate/boundary event → `noop` (pass-through). Start có kaori:nodeType vẫn ưu tiên. |
| 7 | **Message flow** (cross-pool) có `port_type='main'` → bị tính vào topo + gating → sai thứ tự / **false cycle → run fail** | state_store SELECT thêm `flow_kind`; runner loại `flow_kind='message'` khỏi topo + gating |
| 10 | Exclusive gateway **2 nhánh cùng có điều kiện** (không default) → mapper không set token → runner thấy token lạ → **cả 2 nhánh fire** | `_derive_gateway_conditions`: mọi 2-way exclusive → conditional=true arm, nhánh kia=false arm |
| 1/2 | Token lạ ('truee' typo) / edge không token trên nhánh decision → **catch-all fire cả 2** | `_edge_is_live`: source là decision + token None/không nhận diện → **DEAD** (không còn fallthrough True) |
| 12 | `is_default` bị bỏ qua khi edge cũng có `condition_expr` | `_edge_branch_token`: check `is_default` TRƯỚC |
| 3 | Decision executor lỗi không emit `branch`/`matched_case` → runner coi như non-decision → fire hết | Guard: if_else/switch thiếu signal → **fail loud** (DecisionContractError) |
| 5 | **Parallel join** dùng `any()` → chạy với input thiếu khi 1 nhánh bị prune | join (`node_type='join'`) dùng `all()` incoming live; node khác giữ `any()` (merge) |
| 9 | Toán tử trong **chuỗi nháy** (`name == "a > b"`) bị split sai | `_parse_comparison` mask quoted regions trước khi tìm op |
| (I) | approval_gate nhận role toàn khoảng trắng → resume không match | strip + drop role rỗng |

Test: `test_workflow_combinations_e2e.py` (BPMN→mapper→runner end-to-end + data pipeline filter→sort→aggregate + 6 regression) · units trong `test_bpmn_mapper.py`. **Full suite 2779 pass.**

**FOLLOW-UP robustness — ĐÃ SỬA 2026-05-30 (anh: "xử tiếp"):**
- **skipped-vs-missing:** runner lưu `{"__skipped__":True}` vào prior_outputs cho node bị skip; `_resolve` trả sentinel `SKIPPED`; helper `require_rows()` → executor data (aggregate/filter/sort/split/join/transform/merge/deduplicate) **fail loud** khi đọc từ nhánh chết, thay vì âm thầm `[]`. None (absent) vẫn → `[]`. `_edge_is_live` coi sentinel là dead (giữ skip propagation). e2e `test_node_reading_skipped_branch_fails_loud`.
- **filter** log + đếm row bị drop do predicate lỗi (`filter.row_predicate_failed` kèm row_index/error) — typo op không còn âm thầm xoá sạch.
- **aggregate** coerce numeric-string (`'100'+'200'=300`, không còn `sum=0`); log khi bỏ value non-numeric. `_extract_values` dùng `_to_number`.
- **JSONB-as-string:** `_eval_condition` coerce numeric-string cho ordering ops (`>` `>=` `<` `<=`) → `'90' >= 80` đúng số. `_coerce_numeric_pair`.
- **switch** match case-insensitive (str) + numeric-aware (`'Gold'~'gold'`, `5~'5'`) khớp gating; `matched_case` ép primitive-safe. `_case_matches`.
- **CÒN LẠI (ghi nhận, không sửa):** bare dotted identifier `a.b` trong điều kiện → luôn `$.input.a.b` (parser thuần, không có node-id để suy prior-node ref) — quy ước BPMN var = run input; nếu cần ref node thì dùng `$.nodeId.field` tường minh.
Tests: `test_workflow_robustness.py` (14 case) + e2e. **Full suite 2793 pass.**

---

## 13. FE embed bpmn-js + properties panel — 2026-05-30 (#7 + #10)

anh: "FE resume: nhúng bpmn-js ssr:false + properties panel." Đã ship.

**Stack:** `bpmn-js@18.16.1` (chỉ core modeler — KHÔNG dùng `bpmn-js-properties-panel`; panel VN tự viết). Next 16.2.6 / React 19.

**Files:**
- `frontend/lib/bpmn/kaori-moddle.ts` — moddle extension cho `kaori:nodeType` (extends `bpmn:FlowElement`, `isAttr`) → bpmn-js serialise đúng attribute vào XML để BE mapper đọc.
- `frontend/components/bpmn/BpmnEditor.tsx` (`'use client'`) — `new BpmnModeler({container, moddleExtensions:{kaori}})`; import CSS `diagram-js.css`+`bpmn-js.css`+`bpmn-font`; canvas + **panel VN bên phải**: chọn element → sửa tên (`modeling.updateProperties name`) + dropdown **Hành động Kaori** (group theo `ACTION_GROUP_LABEL`, lọc `actionsForBpmnType(bpmnType)`) set `kaori:nodeType`; badge ✓ thực thi / ⚙ thiết kế (`isExecutable`). Diagram trống mặc định = 1 start event. `commandStack.changed`→`saveXML`→onChange (debounce qua ready flag).
- `frontend/components/bpmn/BpmnPanel.tsx` (`'use client'`) — `dynamic(()=>import('./BpmnEditor'),{ssr:false})` (đúng Next 16 lazy-loading: ssr:false chỉ trong Client Component). Load `GET /api/v1/workflows/{id}/bpmn`; giữ XML hiện tại; nút **Tải lại / Lưu sơ đồ** (`PUT /bpmn`) / **Lưu & Đồng bộ bước** (`PUT` rồi `POST /bpmn/sync`); hiện `design_summary` (bước/luồng/executable/trigger/pool/lane/warnings) + `dangling_branches`. Remount editor bằng `key` khi Load (tránh re-import vào modeler sống).
- `frontend/components/p2/templates/60-workflow-detail.tsx` — thêm tab **"BPMN"** (icon Network) cạnh Builder/Cây/Báo cáo → render `<BpmnPanel workflowId>`.

**Auth/API:** dùng wrapper `@/lib/api` (JWT `kaori.access_token` + Idempotency-Key tự gắn). Endpoints qua gateway `/api/v1/workflows/{id}/bpmn[/sync]`.

**License:** giữ watermark "bpmn.io" (anh chốt — không cần Camunda OEM). typecheck 0 lỗi.

**Còn lại (tùy chọn):** nút Export `.bpmn` (download XML); auto-layout (dagre) cho diagram synced-từ-nodes; full `bpmn-js-properties-panel` nếu cần sửa thuộc tính BPMN nâng cao (hiện panel VN đủ cho gán action + tên).

---

## Builder constructs — SHIPPED 2026-05-31 → 06-01 (PRs #306–#311)

Tất cả trong `frontend/components/p2/workflow/LinearBuilderView.tsx` (builder ĐANG CHẠY — KHÔNG phải `CardEditor` trong 60-workflow-detail.tsx, đã chết) + `routers/workflow_builder.py` + `workflow_runtime/`. Mỗi mục verified qua UI thật trên tenant Natural Beauty (anh test trực tiếp từng cái).

- **Rẽ nhánh thật (if/else).** Action điều khiển (`group:'control'`) hết bị lọc khỏi dropdown "Hành động Kaori"; chọn → `node_type` ← `CATALOG_TO_NODETYPE` (decision_if_else…). `IfElseEditor`: *trường · op · giá trị* → `decision_config.condition {left,op,right}`, 2 nhánh **Đúng/Sai** (token 'có'/'không' runner nhận). `IfElseExecutor` + fork render đã có sẵn.
- **Switch theo khoảng.** `SwitchEditor`: cases `{label,min,max}` + mặc định; `SwitchExecutor` match khoảng số (`min ≤ v < max` → matched_case=label). Input rộng + hint VNĐ.
- **Dry-run.** `POST /workflows/{id}/dry-run` đi đồ thị tĩnh (if_else/switch/loop) → visited nodes + taken edges + trace, KHÔNG side-effect. FE panel "▶ Chạy thử" tự dò trường input (scalar + loop-list "số phần tử"), tô sáng đường đi (xanh visited / mờ unreached).
- **Reroute bước thường.** "Đi tới bước tiếp theo" cho node không-decision (vd Từ chối skip Ghi sổ).
- **Loop/for-each.** Node `loop_foreach`/`loop_end` (mig 128 catalog + 129 chk_node_type + pydantic regex). `LoopEditor` (items + item_var). Dry-run mô phỏng "lặp N lần". **Runner thật (B2):** `_find_loop_regions` (BFS thân loop_foreach↔loop_end), main-loop skip thân, `_execute_loop` chạy thân N lần/item inject `prior_outputs[item_var]=item`, emit event/vòng, upsert run_node 1 lần/node. Verified run thật: `{iterations:3}`, body executor chạy 3×.
- **Field picker.** `<datalist id="kaori-fields">` từ `GET /api/v1/schema/fields` (40 cột canonical + nhãn VN) cho 3 ô trường (if/else, switch, loop) — gợi ý nhưng vẫn gõ tự do.
- **BPMN swimlane phân quyền.** Ô "Vai trò phụ trách (lane)" mỗi bước → `workflow_nodes.lane_name` (NodeUpdate + PUT). `build_bpmn_xml(lanes=)` viết `collaboration + participant(pool) + laneSet(1 lane/vai trò) + flowNodeRef` + **DI swimlane tự tính** (bpmn-auto-layout không xếp pool); cột = độ sâu luồng (nhánh gộp chia cột, bớt chéo). `from-steps` nhóm theo `lane_name` (chưa gán → "Chung"); không lane → vẫn cây phân nhánh.
- **Approval gate ↔ chain.** `ApprovalBind` picker (`GET /approval-chains`) + role fallback; `_check_approval_gates` chặn TESTING/ACTIVE cổng rỗng. Chi tiết → `docs/adr/0037-…`.

**BPMN từ bước (nodes→BPMN):** `POST /workflows/{id}/bpmn/from-steps` — `build_bpmn_xml(include_di=False)` → FE `bpmn-auto-layout` xếp cây phân nhánh; tự dựng khi mở tab BPMN; điều kiện if_else hiện trên cạnh ĐÚNG.

**Sửa nền tảng phát hiện dọc đường:** (a) runtime đọc cột `config` còn builder ghi `decision_config` → `state_store` MERGE cả hai; (b) FE state clobber/refetch race → `updateCard` tích full merged config vào `pendingPatchesRef`, `flushPatch` không re-read tree; (c) JWT auto-refresh (gateway PUBLIC_PATHS thiếu `/auth/refresh` + P2 fetch helper không refresh) → fix gateway + foundation/lib api + upload XHR (PR #308); (d) pilot run-path (migs 094/099/100 stubbed) → áp lên pilot DB, run thật ghi event + quota (PR #311).

**Lưu ý / polish sau:** loop body chạy tuần tự (chưa branch-gating trong thân); NodeCreate chưa nhận lane_name (chỉ PUT — đường tạo-rồi-sửa chạy OK); HTML mockup `docs/sprint/*.html` chưa sync (mockup tĩnh, giá trị thấp).
