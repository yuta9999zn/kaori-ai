# UAT-EN-009 · Upload File (Step 1)

| | |
|---|---|
| **Mã test** | UAT-EN-009 |
| **Portal** | P2 Enterprise |
| **Route** | `/p2/pipelines/new/upload` |
| **Source FE** | `frontend/components/p2/templates/20-data-pipeline-step-1-upload-file.tsx` |
| **Endpoint** | `POST /api/v1/upload` (multipart) |
| **Auth required** | Có |
| **Phase** | Phase 1 ✅ |

---

## Mục tiêu test

Step 1 pipeline 5-step wizard: dropzone upload CSV/Excel + Department / Branch / Source headers (mig 051 Silver per-domain). BE return `run_id` → navigate step-2.

## Pre-condition

| # | Điều kiện |
|---|---|
| P1 | Login enterprise role. |
| P2 | Có file CSV / XLSX test (vd 100KB Olist orders). |

## Test cases

### TC-1 · Render dropzone

**Expected**
- ✅ PageHeader "Tải file lên".
- ✅ Stepper 5 pills (1 active gold).
- ✅ Dropzone với icon UploadCloud + text "Kéo thả file vào đây hoặc click chọn" + helper "CSV / XLSX, tối đa 100MB".
- ✅ Form bổ sung: dropdown Department / Branch / Source / Workflow step (optional).

### TC-2 · Drop file + upload

**Steps**
1. Drag CSV vào dropzone.
2. Chọn Department "Sales" + Branch "HCM" + Source "Olist".
3. Click "Tải lên".

**Expected**
- ✅ Progress bar 0→100%.
- ✅ `POST /upload` 200 body `{run_id, sha256, status: "schema_detection"}`.
- ✅ Navigate `/p2/pipelines/{run_id}/step-2-columns` (UAT-EN-010).

### TC-3 · File invalid (wrong type)

**Steps**
1. Drop file `.txt`.

**Expected**
- ✅ ErrorBanner: "Định dạng file không hỗ trợ. Chỉ chấp nhận CSV / XLSX.".

### TC-4 · File too large (> 100MB)

**Steps**
1. Drop file 200MB.

**Expected**
- ✅ FE block + ErrorBanner.

### TC-5 · SHA-256 dedupe

**Steps**
1. Upload file đã upload trước (cùng SHA).

**Expected**
- ✅ BE return existing run_id (K-8 idempotent).
- ✅ Navigate sang run_id cũ thay vì tạo mới.

### TC-6 · Required document type mismatch (mig 065)

**Steps**
1. Workflow step yêu cầu document type "invoice" nhưng upload file không match.

**Expected**
- ✅ BE 400, ErrorBanner: "File không khớp loại tài liệu yêu cầu".

### TC-7 · Cancel mid-upload

**Steps**
1. Trong khi progress chạy, click "Hủy".

**Expected**
- ✅ Abort fetch + Reset form.

## Known issues

| # | Issue | Workaround |
|---|---|---|
| (none) | | |

## Related screens

- **UAT-EN-010** /p2/pipelines/{id}/step-2-columns — next step.
- **UAT-EN-007** /p2/pipelines — return.
