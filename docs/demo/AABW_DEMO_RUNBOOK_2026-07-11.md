# Runbook Demo AABW — 11/07/2026 (P5 Organizational AI Memory)

> Tenant demo: **Thực phẩm Đồng Xanh** — login `giamdoc@dongxanh.vn / DongXanh@2026` tại `http://localhost:3000/login`
> Dữ liệu + tài liệu: `C:\Users\nguye\Downloads\Kaori_Test_DongXanh\`
> Đã diễn tập trọn vòng 10/07 (run demo `5b7af81d` 15/15 node qua UI; pipeline `9e7dc45c` 108 dòng).

## ⚠️ Trước demo 30 phút (bắt buộc)

1. **Pre-warm model** (không làm: node AI đầu tiên mất 6-7 phút thay vì ~1 phút):
   ```
   curl http://localhost:11434/api/generate -d "{\"model\":\"qwen2.5:7b\",\"prompt\":\"ok\",\"keep_alive\":\"60m\",\"options\":{\"num_predict\":1}}"
   ```
   (chạy mất ~75 giây lần đầu; demo dài quá 60 phút thì chạy lại giữa giờ)
2. Đóng app ngốn CPU/RAM (Chrome tab thừa, Teams...). Stack cần ~11GB WSL.
3. Nếu vừa restart stack: model bị unload → warm lại. Check `curl http://localhost:11434/api/ps` phải thấy `qwen2.5:7b`.
4. Xoá "Phòng QA Test (Claude)" trong Phòng ban nếu chưa xoá (rác test).

---

## Kịch bản 8 chặng

### Chặng 1 — Phòng ban & nghiệp vụ
- **Workflow → Phòng ban**: 8 phòng, mỗi phòng có mô tả nghiệp vụ + số workflow (Thu mua: 1).
- Lời thoại: "Kaori tổ chức theo đúng cách DN vận hành — phòng ban → nghiệp vụ → quy trình."

### Chặng 2 — Quy trình nghiệp vụ
- **Workflow → Tất cả workflow → "Thu mua nông sản từ HTX"** — tab Builder: 15 bước, 3 làn (Thu mua / Kaori AI / Ban Giám đốc).
- Giải thích từng bước: xem tài liệu thuyết trình riêng (đã soạn 10/07 — form nhận đơn → validate → 3 bước AI → gateway 50 triệu → Giám đốc duyệt → e-sign → nhập kho → narrative → feed → email).

### Chặng 3 — BPMN
- Tab **BPMN**: sơ đồ chuẩn bpmn-js 3 lane; có nút "Tải .bpmn" (chuẩn công nghiệp, mang sang tool khác đọc được).

### Chặng 4 — Tài liệu theo bước (Cây tài liệu)
- **Bộ file import đánh số theo bước: `Downloads\Kaori_Test_DongXanh\tai_lieu_theo_buoc_workflow\`** (xem README trong folder — tên file ghi rõ Bước + ĐẦU-VÀO/ĐẦU-RA/THAM-CHIẾU).
- **Beat "Kiểm tra sạch (AI)"** — file BẢNG (csv/xlsx) nộp vào cây tài liệu có nút **Kiểm tra sạch** (cạnh nút Phân tích):
  - Nộp `Buoc10_DAU-VAO_ket_qua_kiem_QA_15lo_DIRTY.csv` → bấm → panel vàng "CHƯA SẠCH" liệt kê lỗi (ngày lẫn format, `2tr7`, âm, trống) + CTA **"Chạy 5 bước làm sạch →"** (mở wizard).
  - Nộp `Buoc10_DAU-RA_ton_kho_sau_nhap_SACH.csv` → panel xanh "SẠCH" + CTA **"Phân tích ngay"**.
  - Verdict là heuristics tất định (mirror quy tắc Bước 3); Qwen chỉ viết nhận xét — model lạnh thì nhận xét tự ẩn, verdict vẫn về ngay.
- Tab **Cây tài liệu**: 5 mục đã cấu hình:
  | Bước | Loại | Tài liệu | File trong Downloads |
  |---|---|---|---|
  | 2. Đọc đơn chào bán | đầu vào | Đơn chào bán HTX | `don_chao_ban_HTX_DonDuong_2026-07.docx` (**đã nộp sẵn** — DocSage bóc 678 ký tự) |
  | 9. Hợp đồng | đầu ra | Hợp đồng đã ký | `hop_dong_thu_mua_HTX.docx` (nộp live) |
  | 10. Nhập kho + QA | đầu vào | Biên bản kiểm QA SOP-02 | `bien_ban_kiem_QA_SOP02_DCB-2026-071.docx` (nộp live) |
  | 10. Nhập kho + QA | đầu ra | Phiếu nhập kho | `phieu_nhap_kho_PNK-2026-205.docx` (nộp live) |
  | 13. Thông báo HTX | tham chiếu | Hóa đơn VAT | `hoa_don_VAT_mau.pdf` (nộp live) |
- Beat: bấm **Nộp file** 1-2 slot live → badge đổi "Đã nộp"; bấm "Phân tích AI" trên file đã nộp nếu muốn khoe doc-analysis.

### Chặng 5 — (Tuỳ chọn) Chạy workflow sống
- Nút **Chạy ngay** trên trang workflow → theo dõi tới cổng duyệt (~5-6 phút với model warm — trám thời gian bằng chặng 6).
- **Duyệt & Phân quyền → Inbox** → Approve → **Hợp đồng** → HD mới "Chờ ký" → mở → **Ký** → Hiệu lực → run tự chạy nốt 15/15.

### Chặng 6 — Upload 5 bước làm sạch (pipeline)
- **Pipelines → Tạo mới** → tên "Phân tích doanh số 6 tháng" → **Bắt đầu**.
- Bước 1 Upload: kéo `doanh_so_khach_hang_6thang_DEMO.csv` → "108 hàng" → Tải lên Bronze (SHA-256 chống trùng, K-8; **nếu báo trùng file** thì đã upload hôm 10/07 — dùng lại pipeline cũ hoặc thêm 1 dòng vào csv để đổi SHA).
- Bước 2 Cột: AI map kèm confidence. **PHẢI SỬA 2 CHỖ**:
  - `mat_hang` → **Sản phẩm** (AI đoán nhầm "Tiền mặt")
  - `khach_hang` → **Mã khách hàng** (auto-match ra "Tên" → thiếu cột khách thì template Churn không chạy!)
  - Các cột khác: ma_don=Mã đơn hàng, ngay_dat=Ngày, so_luong_kg=Số lượng, don_gia_vnd=Đơn giá, thanh_tien_vnd=**Doanh thu**, kenh_ban=Kênh, so_ngay_tre=Thời gian xử lý, trang_thai_thanh_toan=Đạt SLA.
- Bước 3 Làm sạch: giữ mặc định (6 quy tắc) → nhấn mạnh "mỗi rule ghi vào decision_audit_log (K-6), Bronze giữ nguyên (K-2)".
- Bước 4 Phân tích: banner "Qwen nội bộ — dữ liệu không rời workspace" (K-4). Chọn **Thống kê tổng quan + Chuỗi thời gian + Nguy cơ rời bỏ (Churn)** → Bắt đầu.
- Bước 5 Kết quả: chờ ~1-2 phút — chỉ số + biểu đồ + nhận xét AI tiếng Việt.
- **Insight cài sẵn trong data**: "Chuỗi Cửa Hàng Sạch 5S" doanh thu rơi 6,3tr→0,9tr (churn HIGH); WinMart trễ hạn 5→28 ngày (công nợ); Bách Hóa Xanh +75%.

### Chặng 7 — Đối chiếu KB/RAG
- **Insight → Knowledge Base**: hỏi "Đơn thu mua trên 50 triệu cần ai phê duyệt theo QĐ-01?" → trả lời kèm trích dẫn văn bản. Nhấn: không đủ căn cứ thì AI TỪ CHỐI trả lời (không bịa).
- Nối: "chính node 'Đối chiếu QĐ-01' trong workflow gọi đúng engine này."

### Chặng 8 — Phân tích khung (6W2H, SWOT, xương cá)
- **Phân tích → Tổng quan** (`/p2/analysis` — trang MỚI 10/07): mọi phân tích từ trước đến giờ theo 3 nhóm (pipeline template / theo tầng / khung) + 4 card mở tầng. Đây là beat "xem lại lịch sử".
- **Trung cấp** (`/p2/analysis/intermediate`): chọn 2 nguồn Silver + 1 khung (SWOT/6W/2H/Fishbone) + câu hỏi → chạy. **Nâng cao** (`/p2/analysis/advanced`): cohort + consent AI ngoài (chỉ show màn, đừng chạy live — Qwen mất ~5 phút/khung, mở kết quả SWOT đã chạy sẵn từ Tổng quan).
- Kết: "Từ dữ liệu thô → quy trình có kiểm soát → quyết định có căn cứ + có vết — và tri thức ở lại công ty."

---

## Sự cố & cách thoát

| Triệu chứng | Xử lý |
|---|---|
| Node AI quay >3 phút | Model chưa warm — nói chuyện tiếp, không refresh; hoặc mở `docker logs kaorisystem-ollama-1` xem generate đang chạy |
| Run kẹt 'running' bất thường | `POST /workflow-runs/{id}/stop` (K-23) rồi chạy lại — hardening 949ce17 đã chống mồ côi |
| Upload báo trùng SHA-256 | Đã upload trước đó — mở pipeline cũ trong "Lịch sử chạy" |
| Template báo "chưa đủ điều kiện" dù data ổn | Đã fix 10/07 (coerce ngày + run-aware eligibility) — nếu còn: kiểm tra bước 2 đã map cột Ngày/Mã khách hàng chưa |
| Trang trắng / 401 | Token hết hạn — F5, login lại |

## File dữ liệu (Downloads\Kaori_Test_DongXanh)

- ⭐ `doanh_so_khach_hang_6thang_DEMO.csv` — demo chính (sạch, có câu chuyện churn/công nợ)
- `thu_mua_htx_kiem_qa_DIRTY.csv` — dự phòng demo LÀM SẠCH (ngày 3 format, tiền `2tr7`, trùng dòng, outlier 9999, âm)
- `ton_kho_kho_lanh.csv` — dự phòng demo cảnh báo tồn kho (quá HSD, nhiệt lệch 3,6°C)
- 3 docx demo tài liệu + `hop_dong_thu_mua_HTX.docx` + `hoa_don_VAT_mau.pdf`
