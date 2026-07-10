# AABW Demo Runbook — khởi động stack 15 phút trước giờ demo

> Máy pilot: laptop 16GB, Docker Desktop trên WSL (`.wslconfig` 11GB + 8GB swap, data ở `D:\DockerData`).
> Đã thực chiến 2026-07-02: các bước dưới là thứ tự đúng + fix cho từng gotcha đã gặp thật.

## 0. Trước khi demo 1 ngày

- [ ] `git -C "D:\Kaori System" pull` — main là canonical.
- [ ] Nếu có commit mới chạm `services/ai-orchestrator` hoặc `frontend`: `docker compose build ai-orchestrator frontend` (image bake source — restart KHÔNG đủ).
- [ ] Kiểm tra model Ollama còn đó: `docker exec kaorisystem-ollama-1 ollama list` → cần `qwen2.5:7b` + `bge-m3`.
- [ ] Diễn tập golden path (xem `AABW_DE5_DEMO_SCRIPT.md`) ít nhất 1 lần.

## 1. Khởi động (T-15 phút)

```powershell
cd "D:\Kaori System"
docker compose up -d
```

**Gotcha #1 — Kafka exit(1) `NodeExists registerBroker` (stale ZK node sau reboot):**
```powershell
docker restart kaorisystem-zookeeper-1
Start-Sleep 5
docker start kaorisystem-kafka-1
# rồi chạy lại: docker compose up -d   (để up nốt các service phụ thuộc kafka)
```

**Gotcha #2 — Vault unhealthy:** đã fix vĩnh viễn trong compose (healthcheck `127.0.0.1` thay `localhost`). Nếu tái phát → kiểm tra healthcheck có bị revert về `localhost` không.

**Gotcha #3 — auth-service Flyway "password authentication failed for user kaori":** volume Postgres cũ có password khác `.env`. KHÔNG wipe volume — fix qua socket:
```powershell
docker exec kaorisystem-postgres-1 psql -U kaori -d kaori -c "ALTER ROLE kaori PASSWORD '<pw trong .env>';"
```

## 2. Verify healthy (T-10 phút)

```powershell
docker compose ps --format "table {{.Service}}\t{{.Status}}"
```
Cần healthy: `postgres, redis, kafka, vault, ollama, api-gateway, auth-service, data-pipeline, ai-orchestrator, llm-gateway, notification-service`. Frontend `Up` là đủ (không có healthcheck).

Smoke nhanh:
```powershell
curl.exe -s -o NUL -w "frontend:%{http_code}`n" http://localhost:3000
curl.exe -s -o NUL -w "gateway:%{http_code}`n"  http://localhost:8080/actuator/health
```

## 3. Verify dữ liệu demo (T-5 phút)

- [ ] Login demo tenant: `giamdoc@dongxanh.vn` / `DongXanh@2026` (enterprise Đồng Xanh, role MANAGER).
- [ ] `/p2/dashboard` render, sidebar đủ section.
- [ ] `/p2/insights/knowledge-base` có entries (KB đã seed).
- [ ] `/p2/workflows` có workflow demo với approval gate.
- [ ] `/p2/compliance` load (risk register + model card — cần bảng `ai_model_card`, đã apply mig 137 vào pilot DB 2026-07-02).

## 4. Trạng thái DB pilot (để khỏi ngạc nhiên)

- Flyway max ghi nhận = **105**; các bảng mig 106+ được apply tay chọn lọc (KB, memory trust, approval chains, contracts, ai_use_risk_register, ai_incident, gate_kind, **ai_model_card**).
- Còn CHƯA apply: `workflow_doc_requirements` (mig 119-120) — không nằm trên golden path đề 5.
- LLM local: **Qwen 7B** — JSON output yếu hơn 14B; narrative token cap đã env-configurable để summary chạy trọn trên 7B. Đừng demo tính năng đòi JSON phức tạp từ LLM nếu chưa diễn tập.

## 4b. Đã diễn tập + seed (2026-07-02)

**Golden beat governance — ĐÃ CHẠY THẬT:** workflow "Thu mua nông sản từ HTX" (`d2f72d21…`) → node "Ký hợp đồng (duyệt > 50tr)" là `approval_gate` role MANAGER → run dừng `awaiting_approval` → duyệt ở `/p2/approvals` (Hộp duyệt) → run `completed`, approval `approved` (verify trong `workflow_runs` + `workflow_approvals`). Đây là beat đáng giá nhất cho đề 5/đề 4.

- ⚠️ **Node config phải có sẵn trước khi chạy** (đã sửa trong pilot DB): các node `log` cần `config.event`, `read_api`/`call_api` cần `url`. Template gốc để `config={}` nên run **fail ngay bước 1**. Đã set: Báo giá→`log{event}`, Thanh toán/Nhận hàng/Nhập kho→`log{event}`. Nếu reset DB phải set lại (script: `scratchpad/fix_htx_nodes.sql`).
- **KB seed (LIVE):** 3 tri thức workspace tier-4 riêng Đồng Xanh (QĐ-01 phê duyệt, SOP-01 thu mua, SOP-02 kiểm QA) — hiển thị badge "Workspace của bạn", tách khỏi 5 tri thức "Toàn hệ thống". Story đề 5: tri thức thuộc công ty, không lẫn tri thức nền.
- ⚠️ **bge-m3 cold-start:** lần embed đầu >30s → gateway 504. Warm-up trước demo: gọi 1 lần KB search (hoặc `/api/v1/embed`) rồi mới demo. Lần 2 trở đi <1s.
- ✅ **Doc-tree upload — FIXED 2026-07-02** (branch `fix/doctree-tabular-dms-filing`): trước đây upload `.txt`/`.csv`/`.xlsx` với `X-Folder-ID` không tạo row `document_repository_file` (chỉ nhánh unstructured file vào kho; nhánh tabular không truyền `folder_id`, file .txt văn xuôi parse 0 sheet cũng rơi). Đã fix cả 3 nhánh (tabular + 0-sheet + K-8 duplicate fallback), 6 test mới, suite 799 pass, verify live qua UI: Kho → 2026 → Quý 2 → Quy trình & SOP có đủ 3 SOP. **Demo cần image data-pipeline build từ branch này trở đi.**
- **Demo seed hiện có trong Kho tài liệu:** `SOP-01-Thu-mua-nong-san-HTX.txt`, `SOP-02-Kiem-QA-nhap-kho.txt`, `QD-01-Phan-quyen-phe-duyet.txt` (nội dung khớp workflow HTX + 3 tri thức KB).

## 5. Nếu phải demo mà một service chết

- Nguyên tắc: mọi degrade phải là **per-item failure ≠ abort run** — pipeline vẫn chạy, insight narrative có thể "best-effort".
- LLM chậm/timeout: gate 30s + skip noise đã wire — demo vẫn trôi, chỉ thiếu đoạn văn tường thuật.
- Tuyệt đối không `docker compose down -v` (mất volume = mất demo data).
