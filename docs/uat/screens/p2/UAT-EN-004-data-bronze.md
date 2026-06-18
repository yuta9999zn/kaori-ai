# UAT-EN-004 · Data Bronze Tier

| | |
|---|---|
| **Mã test** | UAT-EN-004 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/data/bronze` |
| **Source FE** | `frontend/components/p2/templates/fnew3v1-bronze.tsx` |
| **Endpoint** | `GET /api/v1/data/bronze` |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Liệt kê raw files (Bronze tier — MinIO append-only K-2). Mỗi file: name, size, SHA-256 fingerprint, upload time, source connector.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Workspace có ≥ 1 file Bronze (từ upload hoặc connector ingest). |

## Test cases

### TC-1 · Render table

**Steps**
1. Vào `/p2/data/bronze`.

**Expected**
- ✅ PageHeader "Bronze — Dữ liệu thô".
- ✅ Table columns: Tên file · Nguồn · Kích thước · SHA-256 (mask) · Tạo lúc · (Eye/Download icons).

### TC-2 · Click file → preview

**Steps**
1. Click row file CSV.

**Expected**
- ✅ Modal/drawer hiện preview 10 dòng đầu.

### TC-3 · Download

**Steps**
1. Click icon Download.

**Expected**
- ✅ `GET /data/bronze/{file_id}/download` blob → browser download.

### TC-4 · Filter source

**Steps**
1. Dropdown filter source (manual upload / Gmail / Calendar / S3).

**Expected**
- ✅ Table filter.

### TC-5 · Empty state

**Expected**
- ✅ "Chưa có file Bronze nào." + CTA upload.

### TC-6 · K-2 enforcement note

**Expected**
- ✅ Info banner: "Bronze tier là append-only. Không thể xoá file đã upload."

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-005** /p2/data/silver.
- **UAT-EN-009** /p2/pipelines/new/upload.
