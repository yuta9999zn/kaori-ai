# Spec — Workflow demo P5: "Thu mua nông sản từ HTX" v2 (AABW 2026)

**Date:** 2026-07-10 · **Deadline phục vụ:** submit AABW 12/07 9:00
**Mục tiêu:** nâng workflow demo Đồng Xanh thành flow 12 node chạy thật end-to-end,
pause ở cổng phê duyệt giám đốc, khớp 3 trục đề P5 (capture / reuse / govern).

## Bối cảnh

- Đề P5 "Organizational AI Memory: The Capability Layer for the AI Enterprise" —
  giám khảo chấm production-readiness + business impact. Kịch bản demo 3 phút:
  "Nhân viên rời đi — tri thức ở lại" (Hồi 2 CAPTURE cần workflow chạy → dừng
  awaiting_approval → giám đốc duyệt → chạy tiếp).
- Workflow hiện có `d2f72d21-21af-4351-8c0a-995afe164c74` (ent Đồng Xanh
  `3d1c1a53-f924-41fa-a4ce-defade00e898`) chỉ có 4 node `log` + 1 `approval_gate`
  config rỗng — không đủ phức tạp, không kể được chuyện.
- Stack pilot localhost đang chạy đủ 13 container; DB có đủ bảng
  (approval_chains, contracts, workflow_approvals.gate_kind, ai_use_risk_register).

## Quyết định đã chốt (với anh)

1. **Nâng cấp in-place** workflow hiện có — giữ tên + lịch sử, không tạo bản mới.
2. **Governance demo:** 1 cổng `approval_gate` nghiệp vụ duy nhất; đăng ký
   `ai_use_risk_register` với `risk_tier=limited` (badge K-22 cho Hồi 4 demo,
   KHÔNG bật high để tránh double-pause oversight K-23).
3. **Thiết kế A — 12 node** (dưới).

## Flow 12 node

```
1  read_form_submission  Nhận đơn chào bán từ HTX          read_only
2  validate              Kiểm tra đơn (schema)              pure
3  extract_entities      Bóc tách lô hàng (LLM)             read_only
4  rag_query             Đối chiếu SOP QA + HĐ khung (KB)   read_only   ← REUSE, citations
5  call_risk_detection   Rủi ro công nợ HTX                 read_only
6  if_else               Tổng giá trị > 50.000.000₫?        pure
   ├─ false → log        "Dưới ngưỡng — duyệt tự động"      read_only
   └─ true  → 7 approval_gate  GIÁM ĐỐC PHÊ DUYỆT ⭐        write_idempotent  ← pause demo
8  contract              Lập HĐ thu mua (e-sign)            write_idempotent
9  create_task           Lệnh nhập kho + kiểm QA theo SOP   write_idempotent
10 generate_narrative    Ghi LÝ DO quyết định (LLM)         read_only   ← context capture
11 publish_insight       Đăng quyết định lên feed (K-6)     write_idempotent
12 send_email            Thông báo HTX                      external
```

Điểm khớp P5: 4 điểm chạm AI qua llm-gateway (K-3, Qwen local); rag_query trả
citation từ KB thật; generate_narrative ghi "vì sao"; đủ 4 loại side_effect_class (K-17).

## Đường tạo (authoring)

- Builder đọc `workflows.bpmn_xml` (bpmn-js) + sync BPMN→nodes (mig 116).
  Soạn BPMN XML **2 lane** (Phòng Thu mua / Ban Giám đốc) rồi đẩy qua API builder
  để nodes + edges sync; sau đó set config từng node qua node-update API.
- **Config runner ghi vào cột `config`** (runner đọc `config`; builder ghi
  `decision_config`; state_store merge cả hai — tránh bẫy config rỗng cũ).
- approval_gate: `approver_role='MANAGER'`, `sla_minutes=240`, `reason_prompt`
  tham chiếu tóm tắt rủi ro từ node 5.
- if_else: condition trên `workflow_edges` (flow_kind / is_default cho nhánh false).

## Data seed (thật, không mock)

| Seed | Chi tiết |
|---|---|
| `workflow_form_submissions` 1 dòng | Đơn chào bán HTX, số liệu từ `thu_mua_nong_san.xlsx` (Downloads\Kaori_Test_DongXanh), tổng giá trị **> 50 triệu** để rẽ vào nhánh phê duyệt |
| KB documents | SOP kiểm QA + `hop_dong_thu_mua_HTX.docx` — kiểm tra đã ingest chưa, thiếu thì upload qua DMS |
| `ai_use_risk_register` 1 dòng | `POST /compliance/ai-uses`, risk_tier=limited |

## Rủi ro & xử lý

- **Contract node** tạo HĐ trạng thái `cho_ky` — có thể pause chờ ký. Kiểm chứng
  hành vi thật khi implement: nếu pause → hoặc ký nhanh qua UI (beat e-sign đẹp),
  hoặc chuyển contract ra nhánh phụ để run chính completes. Acceptance = run hoàn tất.
- **LLM node chậm** (Qwen local trên laptop): text input ngắn, timeout node rộng.
- **BPMN sync có thể không mang config**: nếu sync xoá/regenerate node, set config
  SAU bước sync, verify bằng SELECT trước khi chạy.
- Approve bằng `giamdoc@dongxanh.vn` (MANAGER) — đúng nhân vật kịch bản.

## Acceptance

1. Bấm chạy trong UI → run **pause `awaiting_approval`**; màn phê duyệt hiện
   reason_prompt kèm tóm tắt rủi ro AI.
2. Giám đốc duyệt trong UI → run resume → **hoàn tất end-to-end**, 0 node lỗi.
3. `rag_query` output có citation từ tài liệu KB thật; Nhật ký AI (decisions)
   có bản ghi mới kèm model + confidence + lý do.
4. Canvas builder hiển thị đúng đồ thị 12 node 2 lane (bpmn_xml khớp nodes DB).
5. `/p2/compliance` có dòng risk register "Thu mua HTX — limited".

## Ngoài phạm vi

- Chạy analysis pipeline `thu_mua_nong_san.xlsx` đến done (nửa còn lại việc #1
  demo prep) — làm ngay sau spec này, không cần design riêng.
- Quay video / chụp màn hình / điền form portal (việc #3-#6 kế hoạch demo).
