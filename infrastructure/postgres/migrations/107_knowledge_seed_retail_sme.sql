-- =====================================================================
-- 107_knowledge_seed_retail_sme.sql — Seed domain knowledge (CR-0017)
--
-- Seeds GLOBAL (tenant_id NULL) retail-SME analytics knowledge ported from the
-- NNL-Harness prototype RAG set. These are general, widely-accepted industry
-- principles (definitions + advisory ranges) — NOT proprietary "validated"
-- statistics. Authority tiers (REASONING_LAYER Phần 10):
--   tier 2 (Kaori-curated) — definitional/formula principles (RFM, Pareto, NOV)
--   tier 3 (Market/Industry, advisory) — heuristic ranges (churn window, tactics)
--
-- embedding is left NULL here (SQL can't call the embed service). Run
-- `scripts/reembed_knowledge.py` (admin-scoped, llm-gateway reachable) once
-- after this migration to fill BGE-M3 vectors → then RAG retrieves them.
--
-- RLS: this table FORCEs RLS with a tenant-pin WITH CHECK, so inserting
-- NULL-tenant (global) rows requires the admin bypass — we SET LOCAL
-- app.is_admin for this transaction (mirrors RlsBypassHelper).
-- Idempotent: guarded by NOT EXISTS on (title) so re-running is a no-op.
-- =====================================================================

BEGIN;

SET LOCAL app.is_admin = 'true';

INSERT INTO knowledge_documents (tenant_id, tier, category, title, content, source, lang, status, tags)
SELECT v.tenant_id, v.tier, v.category, v.title, v.content, v.source, 'vi', 'active', v.tags::jsonb
FROM (VALUES
  (NULL::uuid, 2, 'rfm',
   'Phân khúc RFM — Recency, Frequency, Monetary',
   'RFM chấm điểm khách theo 3 trục: Recency (số ngày kể từ lần mua gần nhất — càng nhỏ càng tốt), Frequency (số lần mua trong kỳ), Monetary (tổng chi tiêu / giá trị vòng đời LTV). Cách dùng phổ biến: chia mỗi trục theo ngũ phân vị (quintile 1–5) trên CHÍNH tập khách của doanh nghiệp (không dùng ngưỡng cứng tuyệt đối — mỗi ngành/khách khác nhau). Nhóm thường gặp: "VIP" (R cao, F cao, M cao), "Đang rời bỏ / at-risk" (M cao nhưng R thấp = từng giá trị nhưng lâu không quay lại), "Mới" (R cao, F thấp), "Đã mất / lost" (R rất thấp). Quyết định ngưỡng nên DẪN XUẤT từ phân phối dữ liệu thực, không gán sẵn.',
   'Nguyên lý phân tích bán lẻ SME (tổng hợp)',
   '["rfm","segmentation","vip","at-risk"]'),

  (NULL::uuid, 2, 'pareto',
   'Pareto 80/20 và AOV trong bán lẻ',
   'Quy tắc Pareto: thường ~20% khách (hoặc SKU) tạo ~80% doanh thu — tỷ lệ chính xác phải ĐO trên dữ liệu thật, 80/20 chỉ là điểm khởi đầu. Hệ quả hành động: tập trung nguồn lực giữ chân nhóm giá trị cao (đóng góp doanh thu lớn) trước khi đi rộng. AOV (Average Order Value = tổng doanh thu / số đơn) là đòn bẩy: tăng AOV qua bán kèm/bán nâng cấp thường rẻ hơn thâu tóm khách mới. Lưu ý đơn vị tiền và phân biệt đơn-giá vs thành-tiền khi tính (xem CR-0016).',
   'Nguyên lý phân tích bán lẻ SME (tổng hợp)',
   '["pareto","aov","80-20","upsell"]'),

  (NULL::uuid, 3, 'churn',
   'Cửa sổ rời bỏ và dấu hiệu churn (bán lẻ SME — advisory)',
   'Heuristic tham khảo (KHÔNG phải hằng số tuyệt đối — hãy hiệu chỉnh theo chu kỳ mua của ngành): khách không mua quá ~90 ngày thường bắt đầu có nguy cơ rời bỏ; "cửa sổ cứu" hiệu quả thường nằm trong ~90–270 ngày kể từ lần mua cuối — recency càng sâu thì xác suất cứu càng giảm. Với hàng tiêu dùng nhanh, ngưỡng ngắn hơn; với hàng giá trị cao/mua thưa, ngưỡng dài hơn. Nên kết hợp recency với giá trị (LTV) để ưu tiên: khách LTV cao + còn trong cửa sổ cứu = ưu tiên can thiệp cao nhất.',
   'Heuristic ngành bán lẻ (tham khảo, cần hiệu chỉnh theo dữ liệu)',
   '["churn","recency","retention-window"]'),

  (NULL::uuid, 3, 'retention',
   'Playbook giữ chân theo giá trị + recency (advisory)',
   'Chọn chiến thuật win-back theo giá trị khách và độ sâu recency: (1) Khách LTV cao + recency còn nông (mới chớm rời) → CSM gọi/nhắn 1-1 cá nhân hoá thường hiệu quả nhất, chi phí cao nhưng đáng cho VIP. (2) Recency sâu hơn hoặc giá trị trung bình → voucher/ưu đãi CÓ ĐIỀU KIỆN (giảm % cho đơn kế tiếp trong N ngày) để kích hoạt mà không bào mòn biên lợi nhuận. (3) Recency quá sâu / đã mất → chiến dịch tái kích hoạt diện rộng chi phí thấp, kỳ vọng tỷ lệ hồi thấp. Luôn ước tính chi phí ưu đãi so với giá trị kỳ vọng cứu được.',
   'Heuristic ngành bán lẻ (tham khảo)',
   '["retention","win-back","voucher","csm"]'),

  (NULL::uuid, 2, 'nov',
   'NOV / ROI ước tính của hành động giữ chân',
   'NOV (Net Operational Value) của một hành động cứu khách ước tính ≈ LTV_kỳ_vọng × P(cứu) × (1 − chi_phí_ưu_đãi_tỷ_lệ) − chi_phí_thực_hiện. Trong đó P(cứu) nên suy giảm theo recency (càng lâu không mua, xác suất cứu càng thấp) — trình bày minh bạch là HEURISTIC, không phải xác suất đo được, trừ khi có dữ liệu A/B. Ưu tiên hành động có NOV dương cao nhất. Mọi con số đưa ra cần kèm cảnh báo "ước tính, cần kiểm chứng" (BR-9) và nêu rõ đơn vị tiền.',
   'Nguyên lý NOV/ROI (tổng hợp)',
   '["nov","roi","ltv","payback"]')
) AS v(tenant_id, tier, category, title, content, source, tags)
WHERE NOT EXISTS (
    SELECT 1 FROM knowledge_documents kd WHERE kd.title = v.title AND kd.tenant_id IS NULL
);

COMMIT;
