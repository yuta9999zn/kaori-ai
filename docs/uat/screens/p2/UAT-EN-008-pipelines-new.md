# UAT-EN-008 · New Pipeline (chooser)

| | |
|---|---|
| **Mã test** | UAT-EN-008 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines/new` |
| **Source FE** | `frontend/components/p2/templates/19-data-pipeline-news.tsx` |
| **Endpoint** | (chooser only — không gọi BE) |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Chooser page: chọn cách tạo pipeline mới — Upload file / Connect Gmail / Connect Calendar / Connect S3 / etc.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |

## Test cases

### TC-1 · Render chooser

**Expected**
- ✅ PageHeader "Tạo pipeline mới".
- ✅ Grid cards methods: Upload file (CSV/Excel) / Gmail / Outlook / Calendar / S3 / Webhook.
- ✅ Mỗi card: icon + title + "Chọn →".

### TC-2 · Click "Upload file"

**Expected**
- ✅ Navigate `/p2/pipelines/new/upload` (UAT-EN-009).

### TC-3 · Click Gmail connector

**Expected**
- ✅ OAuth flow start (BE return redirect URL) hoặc modal "Coming soon" tuỳ wire-status.

### TC-4 · Back link

**Expected**
- ✅ "← Lịch sử chạy" → `/p2/pipelines`.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| K-001 | Một số connector (S3, webhook) BE chưa wire fully. | Modal "Coming soon". |

## Related screens

- **UAT-EN-007** /p2/pipelines.
- **UAT-EN-009** /p2/pipelines/new/upload.
