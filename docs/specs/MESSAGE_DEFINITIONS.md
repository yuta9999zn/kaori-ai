# Message Definition — Error / Warning / Success / Info / Confirmation / Helper

> **Source:** `D:\Kaori Document\Message Definition.pdf` v1.0.3 (28 Aug 2025)
> **Last imported:** 2026-05-12 — full PDF extract retained at `.claude/scratch_Message_Definition.txt` (gitignored)
> **Audience:** Frontend (toast component + inline form errors + i18n catalog), Backend (RFC 7807 problem-detail `type` URI + `errcode` field)
> **Maintenance:** when PDF version bumps, re-extract via `pypdf` and refresh below tables.

This spec replaces ad-hoc error strings in code. Every user-visible error MUST map to one row below. New error scenarios → add a row, do not invent a new code on the fly.

---

## 1. System Errors (technical / infra) — `SYS-ERR*`

Generic toast: **"Hệ thống đang trong quá trình bảo trì. Vui lòng quay lại sau ít phút."**

| Code | Type | Description | UI action |
|---|---|---|---|
| `SYS-ERR1` | Connection / Network Error | Không kết nối được máy chủ | Toast cảnh báo |
| `SYS-ERR2` | Resource Not Found / Server Timeout | Hết thời gian chờ tới server | Toast cảnh báo |
| `SYS-ERR3` | Internal Server Error / Timeout | Máy chủ nội bộ gặp sự cố | Toast cảnh báo |
| `SYS-ERR4` | Runtime Error | Lỗi không xác định khi xử lý | Toast cảnh báo |
| `SYS-ERR5` | Memory / Resource Error | Cạn kiệt bộ nhớ / tài nguyên | Toast cảnh báo |

**FE implementation note:** map RFC 7807 `status` ∈ `{500, 502, 503, 504}` → `SYS-ERR*`. Do not surface server stack trace. Always log full trace id from `X-Request-ID` header for support escalation.

---

## 2. User Errors (input / auth / business) — `USR-ERR*`

Inline message dưới trường tương ứng, KHÔNG dùng toast (toast chỉ cho system error).

| Code | Type | Information | Display message | HTTP | Note |
|---|---|---|---|---|---|
| `USR-ERR1` | Authentication Error | Nhập sai thông tin đăng nhập | "Thông tin đăng nhập không chính xác" | — | Login page error region |
| `USR-ERR2` | Data Not Found | Truy vấn dữ liệu không tồn tại | "Không tìm thấy dữ liệu phù hợp." | 400 (`errcode: data.invalid`) | Inline |
| `USR-ERR3` | Input Error — Required field missing | Bỏ trống trường bắt buộc | "Vui lòng nhập [Tên Field]." | 400 | Inline |
| `USR-ERR4` | Input Error — Invalid format | Sai định dạng dữ liệu | "[Tên Field] Định dạng dữ liệu không hợp lệ." | 400 | Inline |
| `USR-ERR5` | Length out of range (Min/Max) | Số ký tự ngoài phạm vi limit | • Khi `min > 0`: "[Tên Field] phải có độ dài từ [min] đến [max] ký tự"<br>• Khi `min = 0`: "[Tên Field] không được vượt quá [max] ký tự" | 400 | Inline |
| `USR-ERR6` | Duplicate input | Nhập trùng dữ liệu đã có | "[Tên Field] đã tồn tại trong hệ thống" | 409 | Inline |
| `USR-ERR7` | Value out of allowed range | Giá trị ngoài phạm vi | "Giá trị nhập vào [Tên Field] nằm ngoài phạm vi cho phép." | 400 | Inline |
| `USR-ERR8` | Date-range error (start > end) | Ngày bắt đầu > ngày kết thúc | "[Tên field bắt đầu] phải diễn ra trước [Tên field kết thúc]" | — | Inline |
| `USR-ERR9` | Data changed during edit | Dữ liệu thực thể đã thay đổi trước khi Lưu | "[Tên Field] đã được cập nhật!" | — | Inline; force user reload |
| `USR-ERR10` | Invalid whitespace in string | Khoảng trống không được phép | "Không được phép nhập khoảng trống" | — | Inline |

**FE i18n key convention:** `errors.user.{code}` → maps to message template. Bind field name + min/max programmatically (do not hard-code).

---

## 3. Business Logic Errors (`BIZ-ERR*`) — Round 5 N6 catalog filled

Business signal khác với pure input validation (USR-ERR). BIZ-ERR cover: quota, plan-gating, K-rule policy violations, manager-approval workflow gates.

| Code | Type | Description | Display message | HTTP | RFC 7807 `type` URI |
|---|---|---|---|---|---|
| `BIZ-ERR1` | Quota exceeded — daily LLM tokens | Tenant đã dùng hết quota LLM tokens hôm nay | "Quota LLM hôm nay đã dùng hết. Reset sau [X giờ]. Nâng plan để tăng quota?" | 429 + `Retry-After` | `https://kaori.ai/errors/biz-quota-exceeded` |
| `BIZ-ERR2` | Quota exceeded — concurrent workflows | Quá 20 workflow chạy đồng thời | "Quá nhiều workflow đang chạy. Đợi workflow hoàn tất hoặc upgrade plan." | 429 | `.../biz-concurrent-limit` |
| `BIZ-ERR3` | Plan does not allow feature | Feature X cần plan ENT_MID+ | "Tính năng [Y] có sẵn từ plan [Z]. [Nâng plan]" | 403 (`errcode: plan.gate`) | `.../biz-plan-gated` |
| `BIZ-ERR4` | Manager approval required | Action threshold-exceeded cần Manager approve | "Hành động vượt ngưỡng [N] cần Manager duyệt. Đã gửi request to [Manager-name]." | 202 (queued) | `.../biz-approval-required` |
| `BIZ-ERR5` | CFO approval required | Discount >25% OR amount >100M VND | "Hành động này cần CFO duyệt do giá trị lớn. SLA: 24 giờ." | 202 | `.../biz-cfo-approval-required` |
| `BIZ-ERR6` | K-4 consent_external denied | External LLM call nhưng consent_external=false | "Tenant chưa consent dùng AI bên ngoài. Liên hệ admin." (Backend fallback Qwen local; warn UI) | 403 | `.../biz-consent-external-required` |
| `BIZ-ERR7` | data_residency_strict policy | Tenant `data_residency_strict=true` chặn external | "Tenant này yêu cầu data residency. Mọi xử lý chạy local Qwen." | — | `.../biz-data-residency-strict` |
| `BIZ-ERR8` | Workflow status conflict | POST /publish on already-active workflow | "Workflow đã active. Tạo version mới để thay đổi." | 409 | `.../biz-workflow-already-active` |
| `BIZ-ERR9` | Workflow version conflict (K-2 immutable) | UPDATE snapshot version | "Phiên bản workflow đã lưu (K-2). Tạo version mới." | 409 | `.../biz-version-immutable` |
| `BIZ-ERR10` | Lock conflict (workflow editor) | User B đang lock workflow, User A try edit | "Workflow đang được [User B] chỉnh. Vui lòng đợi hoặc liên hệ." | 423 (locked) | `.../biz-edit-locked` |
| `BIZ-ERR11` | Bootstrap already done | Tenant đã bootstrap industry, re-run without force | "Workspace đã được tạo từ ngành [X]. Để đổi: tạo Change Request hoặc force redo (destructive)." | 409 | `.../biz-already-bootstrapped` |
| `BIZ-ERR12` | Idempotency replay | Same Idempotency-Key returned cached | (Transparent — return cached response 200) | 200 (re-issued) | — |
| `BIZ-ERR13` | Last Manager protection | Try demote/disable last MANAGER role user | "Phải có ≥1 MANAGER active. Cấp role mới cho user khác trước." | 409 | `.../biz-last-manager-protection` |
| `BIZ-ERR14` | Workflow YAML invalid | Workflow import YAML không pass schema validate (K-17 missing side_effect_class, etc.) | "Workflow YAML không hợp lệ: [chi tiết]. Xem CLAUDE.md §4 K-17." | 422 | `.../biz-workflow-yaml-invalid` |
| `BIZ-ERR15` | Confidence too low (AI gating) | Insight confidence <0.40 — block actionable | "AI tin cậy thấp. Vui lòng review thủ công trước action." | — | (informational, not error) |

> **Reserve numbering từ `BIZ-ERR16`. Khi feature mới có business gate mới, add row tiếp theo.**

---

## 4. Warning / Success / Info / Confirmation / Helper — Round 5 N6 filled

### 4.1 Warning (`WRN-*`) — cảnh báo nhưng vẫn cho phép tiếp tục

| Code | Description | Display message |
|---|---|---|
| `WRN-1` | Deprecated value used | "Giá trị '[X]' đã deprecated, dùng '[Y]' thay thế. Sẽ remove ở Phase 3." |
| `WRN-2` | Quota soft warning (>80% used) | "Đã dùng 80% quota [Y]. Cân nhắc upgrade plan." |
| `WRN-3` | Low AI confidence | "AI tin cậy [X]% — review trước khi action." |
| `WRN-4` | Pipeline runs slow | "Pipeline chậm hơn baseline 20% — kiểm tra dependency hoặc data size." |
| `WRN-5` | Workflow run partial success | "[N]/[M] cards completed. [M-N] cards skipped với reason: [...]." |
| `WRN-6` | OCR confidence borderline | "OCR confidence [X]% (threshold 60%). Verify text trước khi promote." |
| `WRN-7` | PII smoke alarm | "Phát hiện PII chưa mask trong input. K-5 redact step recommended." |
| `WRN-8` | Snapshot stale | "Snapshot cập nhật lúc [HH:MM hôm qua]. Cron lỗi — kiểm tra ops." |

### 4.2 Success (`SUC-*`) — xác nhận hành động hoàn thành

| Code | Description | Display message |
|---|---|---|
| `SUC-1` | Save success | "Đã lưu thay đổi [Name]." |
| `SUC-2` | Upload complete | "Đã upload [N] file thành công." |
| `SUC-3` | Workflow published | "Workflow [Name] đã active từ [time]." |
| `SUC-4` | Run completed | "Workflow run [Run-ID] hoàn tất sau [X phút]." |
| `SUC-5` | Approval approved | "Đã approve. Workflow tiếp tục step kế." |
| `SUC-6` | Bootstrap complete | "Đã tạo workspace cho ngành [X]. Click 'Đi tới Dashboard' để bắt đầu." |
| `SUC-7` | User invited | "Đã gửi email mời tới [email]. Link hết hạn sau 72 giờ." |
| `SUC-8` | Export ready | "Export [filename] sẵn sàng download. Hết hạn sau 7 ngày." |

### 4.3 Info (`INF-*`) — thông tin trung tính

| Code | Description | Display message |
|---|---|---|
| `INF-1` | Pipeline running | "Pipeline đang chạy. ETA: [X phút]. Bạn sẽ nhận notification khi xong." |
| `INF-2` | Background task queued | "Task đã queue. Vị trí: [N]." |
| `INF-3` | Loading more results | "Đang tải [N] thêm…" |
| `INF-4` | Read-only mode | "Bạn đang xem version [X]. Chỉ đọc — không sửa được." |
| `INF-5` | Replay mode | "Đang replay workflow run [Run-ID] từ event store." |
| `INF-6` | New version available | "Phiên bản mới của workflow [Name] đã được publish. [Switch]" |

### 4.4 Confirmation (`CFM-*`) — dialog xác nhận thao tác phá huỷ

| Code | Description | Confirm message |
|---|---|---|
| `CFM-1` | Delete permanent | "Xoá vĩnh viễn [Name]? Không thể hoàn tác." [Hủy] [Xác nhận xoá] |
| `CFM-2` | Force re-bootstrap | "Force re-bootstrap sẽ XOÁ TOÀN BỘ config hiện tại và tạo lại. Tiếp tục?" |
| `CFM-3` | Discard unsaved changes | "Có thay đổi chưa lưu. Rời trang sẽ mất các thay đổi này. Tiếp tục?" |
| `CFM-4` | Promote workflow B (A/B test) | "Promote workflow B làm baseline mới? Workflow A sẽ archive." |
| `CFM-5` | Bulk delete | "Xoá [N] item đã chọn? Không thể hoàn tác." |
| `CFM-6` | Disable user | "Vô hiệu hoá user [name]? User sẽ không login được nhưng dữ liệu giữ lại." |
| `CFM-7` | Cancel subscription | "Huỷ subscription? Tenant sẽ chuyển sang plan PILOT sau [X ngày]." |

### 4.5 Input Helper (`HLP-*`) — tooltip / placeholder

| Code | Field | Helper text |
|---|---|---|
| `HLP-1` | Email | "Nhập email cá nhân, ví dụ: nguyen.an@company.com" |
| `HLP-2` | Phone | "Nhập SĐT VN, có thể có +84 hoặc 0 đầu, ví dụ: 0912345678" |
| `HLP-3` | Tax code | "Mã số thuế 10 số (hoặc 10-3 số cho chi nhánh)" |
| `HLP-4` | VND amount | "Nhập số VND, dấu phẩy phân cách hàng nghìn tự động" |
| `HLP-5` | Discount percent | "Nhập % giảm giá (0-50). >25% sẽ cần CFO duyệt." |
| `HLP-6` | Workflow name | "Tên workflow ngắn gọn, dễ nhận biết. Không quá 50 ký tự." |
| `HLP-7` | Industry picker | "Chọn ngành phù hợp nhất. Có thể đổi sau qua Change Request." |
| `HLP-8` | Confidence threshold | "AI confidence dưới ngưỡng này sẽ chuyển sang human review." |

---

## 5. Backend wiring (RFC 7807 mapping)

Per K-14 (CLAUDE.md §4) backend errors là RFC 7807 `application/problem+json`. Mỗi error payload phải chứa:

```json
{
  "type": "https://kaori.ai/errors/{code-lowercase-kebab}",
  "title": "User-friendly title",
  "status": 400,
  "detail": "Specific instance detail (PII-safe)",
  "instance": "/api/v1/p2/...",
  "errcode": "USR-ERR4",         // ← maps to this catalog
  "trace_id": "...",
  "fields": {                     // optional, for multi-field validation errors
    "email": "USR-ERR4",
    "phone": "USR-ERR5"
  }
}
```

FE reads `errcode` first (canonical). Falls back to `title` if `errcode` missing (legacy endpoint).

---

## 6. Implementation checklist (when wiring an endpoint)

- [ ] Every `raise HTTPException` / `return Problem(...)` MUST include `errcode` matching a row above.
- [ ] FE error boundary catches → maps `errcode` → i18n template → renders toast OR inline (per §1 vs §2 split).
- [ ] Snapshot test compares the rendered template against the table above so PDF/code drift surfaces in CI.
- [ ] When PDF version bumps, regenerate the i18n catalog (FE `messages/{vi,en}/errors.json`) from this MD via codegen.
