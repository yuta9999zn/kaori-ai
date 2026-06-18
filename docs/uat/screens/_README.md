# UAT Per-Screen Test Cards

> Format: 1 file `.md` cho 1 màn hình. Mỗi file là 1 thẻ test độc lập,
> có thể chạy riêng lẻ (manual hoặc Claude Edge).
> Prepared: 2026-05-18 (Plan B re-skin done, P1 + P2 shell consolidation)

## Cấu trúc

```
docs/uat/screens/
├── _README.md            ← file này
├── _SETUP.md             ← setup chung 1 lần / session
├── p1/                   ← Platform Manager (Kaori staff), /platform/*
│   ├── UAT-PL-001-login.md
│   ├── UAT-PL-002-login-mfa.md
│   ├── UAT-PL-003-dashboard.md
│   ├── UAT-PL-004-workspaces-list.md
│   ├── ...
│   └── UAT-PL-021-security-sessions.md
└── p2/                   ← Enterprise User, /p2/*
    ├── UAT-EN-001-dashboard-overview.md
    ├── UAT-EN-002-dashboard-customize.md
    ├── ...
    └── UAT-EN-075-...md
```

## Quy ước đặt tên

`UAT-{PORTAL}-{NUM}-{slug-tiếng-anh}.md`

- `PORTAL` = `PL` (Platform) hoặc `EN` (Enterprise).
- `NUM` = 3 chữ số, tăng dần theo navigation order (sidebar trong shell).
- `slug` = kebab-case tiếng Anh, ngắn (≤ 30 ký tự).

Ví dụ:
- `UAT-PL-001-login.md` cho `/platform/login`
- `UAT-PL-004-workspaces-list.md` cho `/platform/workspaces`
- `UAT-EN-001-dashboard-overview.md` cho `/p2/dashboard/overview`

## Format mỗi file

Mỗi file UAT phải có 6 phần (theo thứ tự):

| # | Section | Mục đích |
|---|---|---|
| 1 | **Front matter table** | Metadata (mã test, portal, route, source file, BE, auth, roles, phase, re-skin commit). |
| 2 | **Mục tiêu test** | 1-2 câu mô tả business goal. |
| 3 | **Pre-condition** | Bảng các điều kiện cần có TRƯỚC khi test (stack chạy, seed data, login state...). |
| 4 | **Test cases** | TC-1 ... TC-N. Mỗi TC có **Steps** (đánh số) + **Expected** (checkbox ✅). |
| 5 | **Known issues** | Bảng bug đã biết (nếu có). Không có → ghi "(none)". |
| 6 | **Related screens** | Link các màn hình liên kết qua flow. |

## Cách Claude Edge chạy

Mỗi file UAT là 1 task độc lập. Workflow:

1. Đọc file UAT.
2. Apply pre-condition (login đúng role, seed data nếu cần).
3. Run từng TC theo thứ tự.
4. Output dòng tóm tắt mỗi TC: `[FILE] [TC-N] [PASS|FAIL] [ghi chú]`.
5. Aggregate report: total PASS/FAIL ratio.

Ví dụ output:
```
UAT-PL-001  TC-1  PASS
UAT-PL-001  TC-2  PASS  (admin_id=...)
UAT-PL-001  TC-3  SKIP  (admin chưa MFA, không reproduce được)
UAT-PL-001  TC-4  PASS  (ErrorBanner đúng text)
UAT-PL-001  TC-5  FAIL  (countdown không show — Network thấy 423 OK)
...
```

## Setup chung

Xem `_SETUP.md`.

## Coverage hiện tại

| Portal | Route count | UAT file count | Status |
|---|---|---|---|
| P1 Platform `/platform/*` | 21 | 21 | (TBD — anh OK format thì em bulk-generate) |
| P2 Enterprise `/p2/*` | 75 | 75 | (TBD — sau P1) |
| Auth (`/login`, `/forgot-password`, ...) | ~5 | 5 | (TBD — defer) |
| **Total** | **101** | **101** | |
