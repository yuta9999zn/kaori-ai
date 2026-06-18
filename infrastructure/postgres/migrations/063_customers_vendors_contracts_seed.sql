-- =====================================================================
-- 063_customers_vendors_contracts_seed.sql
--
-- Seed demo data for customers + vendors + their contracts under the
-- Vingroup demo enterprise (mig 056). Mirrors the 4 CSVs at
-- `data/sample/{customers-profile, vendors-profile, customer-contracts,
-- vendor-contracts}.csv` so anh can verify FE pages render the same
-- rows as the spreadsheet.
--
-- enterprise_id is resolved by joining on the well-known seed user
-- vingroup@kaori.local (mig 007). If that user is absent, the WITH CTE
-- returns NULL and the inserts are no-op (ON CONFLICT DO NOTHING +
-- guard CTE drops the row). Safe to re-run.
-- =====================================================================

DO $$
DECLARE
    v_eid UUID;
BEGIN
    SELECT enterprise_id INTO v_eid
      FROM enterprise_users
     WHERE email = 'vingroup@kaori.local'
     LIMIT 1;

    IF v_eid IS NULL THEN
        RAISE NOTICE 'mig 063: vingroup@kaori.local seed user absent — skipping demo seed.';
        RETURN;
    END IF;

    -- ── 1. customers ────────────────────────────────────────────────
    INSERT INTO customers
        (enterprise_id, code, customer_name, contact_person, phone, email,
         tax_code, address, city, customer_type, industry,
         years_in_business, employees_count, annual_revenue_vnd, credit_rating,
         titles_awards, certifications, experience_summary,
         relationship_tier, first_contact_date, assigned_account_manager, note)
    VALUES
    (v_eid, 'KH-2026-001', 'Vinhomes Riverside HCM', 'Nguyễn Văn An', '0901234567', 'an.nguyen@vhrs.vn',
     '0301234001', 'Số 7 Bằng Lăng 1 Vinhomes Riverside Hà Nội', 'Hà Nội', 'strategic', 'Bất động sản',
     12, 2500, 5800000000000, 'AAA',
     'Top 50 BĐS VN 2023; Sao vàng Đất Việt 2024',
     'ISO 9001:2015; LEED Gold 5 dự án',
     'Khách hàng chiến lược 5 năm — sử dụng Kaori cho 4 phòng ban.',
     'platinum', DATE '2021-03-15', 'sales1@kaori.local',
     'Anchor cho gói ENT MAX. Renew tự động hàng năm.'),

    (v_eid, 'KH-2026-002', 'VinMart Quận 1 (TP.HCM)', 'Trần Thị Bình', '0912345678', 'binh.tran@vinmart.vn',
     '0301234002', '68 Lý Thường Kiệt Quận 1 TP.HCM', 'TP.HCM', 'enterprise', 'Bán lẻ',
     8, 12000, 42000000000000, 'AA',
     'Top 10 Retail Asia 2023', 'HACCP; ISO 22000',
     'Chuỗi siêu thị lớn nhất VN. Phân tích doanh thu theo cửa hàng.',
     'gold', DATE '2022-08-20', 'sales1@kaori.local',
     'Đang đàm phán upsell ENT MAX — Manager duyệt.'),

    (v_eid, 'KH-2026-003', 'Vinpearl Phú Quốc Resort', 'Phạm Quốc Cường', '0923456789', 'cuong.pham@vinpearl.vn',
     '0301234003', 'Khu 5 Phú Quốc Kiên Giang', 'Phú Quốc', 'enterprise', 'Du lịch',
     15, 4500, 3200000000000, 'AA',
     'Best Luxury Resort Vietnam 2022', 'ISO 14001; Green Globe',
     'Khu nghỉ dưỡng 5 sao 800 phòng. Phân tích RevPAR.',
     'gold', DATE '2021-06-10', 'sales2@kaori.local',
     'Mở rộng sang Booking + CSKH.'),

    (v_eid, 'KH-2026-004', 'ABC Trading JSC', 'Lê Thị Diễm', '0934567890', 'diem.le@abctrading.vn',
     '0301234004', '12 Nguyễn Văn Linh Quận 7 TP.HCM', 'TP.HCM', 'SMB', 'Xuất nhập khẩu',
     4, 180, 890000000000, 'B',
     NULL, NULL,
     'Khách hàng mới. Yêu cầu credit 90 ngày — vượt policy max 60.',
     'bronze', DATE '2026-04-22', 'sales3@kaori.local',
     'BẮT BUỘC duyệt CFO. Check tín dụng CIC.'),

    (v_eid, 'KH-2026-005', 'Vingroup HQ', 'Hoàng Văn Em', '0945678901', 'em.hoang@vingroup.net',
     '0301234005', 'Bà Triệu Hai Bà Trưng Hà Nội', 'Hà Nội', 'strategic', 'Tập đoàn',
     32, 18000, 250000000000000, 'AAA',
     'Top 1 Tập đoàn tư nhân VN 2024; Forbes Global 2000',
     'Multi-cert (ISO 9001/14001/27001/45001)',
     'Tập đoàn mẹ. MSA phủ toàn group.',
     'platinum', DATE '2020-01-15', 'sales1@kaori.local',
     'Đại diện hợp đồng khung — coordinate CIO Vingroup.'),

    (v_eid, 'KH-2026-007', 'Beta Logistics JSC', 'Vũ Đình Giang', '0967890123', 'giang.vu@beta-log.vn',
     '0301234007', 'KCN Đình Vũ Hải Phòng', 'Hải Phòng', 'SMB', 'Logistics',
     7, 420, 1400000000000, 'B+',
     'Top 50 Logistics VN 2024', NULL,
     'Đội xe 200 đầu kéo. Tracking + route optimization.',
     'silver', DATE '2025-11-12', 'sales3@kaori.local',
     'Credit 120 ngày — vượt policy. PHÊ DUYỆT đặc biệt CFO.'),

    (v_eid, 'KH-2026-009', 'XYZ Group', 'Ngô Văn Inh', '0989012345', 'inh.ngo@xyzgroup.vn',
     '0301234009', 'Tower XYZ Quận 1 TP.HCM', 'TP.HCM', 'enterprise', 'Đầu tư',
     18, 3200, 28000000000000, 'A',
     'Top 100 Forbes Vietnam', 'ISO 9001; SOC 2 Type 1',
     'Tập đoàn đa ngành. Đang sáp nhập 3 công ty con.',
     'gold', DATE '2026-03-08', 'sales3@kaori.local',
     'DEAL LỚN — CFO + Legal duyệt. Subsidiary KH-012.'),

    (v_eid, 'KH-2026-014', 'Delta Finance Co. Ltd', 'Lý Thị Oanh', '0934444555', 'oanh.ly@delta.vn',
     '0301234014', 'Tower Bitexco Quận 1 TP.HCM', 'TP.HCM', 'SMB', 'Tài chính',
     5, 75, 520000000000, 'B+',
     NULL, NULL,
     'Môi giới chứng khoán. Custom analytics riêng.',
     'silver', DATE '2025-08-30', 'sales2@kaori.local',
     'Sales tự custom giá. Manager review.'),

    (v_eid, 'KH-2026-015', 'VinMart Đồng Nai (Pilot)', 'Cao Văn Phú', '0945555666', 'phu.cao@vinmart.vn',
     '0301234015', 'Biên Hòa Đồng Nai', 'Đồng Nai', 'SMB', 'Bán lẻ',
     2, 45, 180000000000, 'B',
     NULL, NULL,
     'Pilot 3 tháng trước khi scale toàn chuỗi.',
     'bronze', DATE '2026-02-14', 'sales1@kaori.local',
     'Pilot tier — auto-approve.')
    ON CONFLICT (enterprise_id, code) DO NOTHING;


    -- ── 2. vendors ──────────────────────────────────────────────────
    INSERT INTO vendors
        (enterprise_id, code, vendor_name, contact_person, phone, email,
         tax_code, address, city, country, vendor_type,
         services_offered, industries_served,
         years_in_business, employees_count, annual_revenue_vnd, credit_rating,
         certifications, titles_awards, experience_summary,
         reliability_tier, first_contract_date, managed_by, note)
    VALUES
    (v_eid, 'NCC-2026-001', 'FPT Software JSC', 'Nguyễn Quốc Bảo', '0901100001', 'bao.nguyen@fpt-software.com',
     '0100002001', 'Bldg FPT Cầu Giấy Hà Nội', 'Hà Nội', 'VN', 'supplier',
     'Phần mềm; gia công; cloud', 'BĐS; Bán lẻ; Tài chính',
     37, 40000, 15000000000000, 'AAA',
     'CMMI L5; ISO 27001; ISO 9001', 'Forbes Top 1 IT VN',
     'Đối tác phần mềm 10+ năm. Triển khai RAG + DocSage.',
     'platinum', DATE '2018-04-12', 'proc1@kaori.local',
     'Đối tác dài hạn — bundled SOW.'),

    (v_eid, 'NCC-2026-003', 'Anthropic PBC', NULL, NULL, 'sales@anthropic.com',
     NULL, '548 Market St San Francisco CA', 'San Francisco', 'US', 'platform',
     'LLM API (Claude)', 'All',
     4, 800, 180000000000000, NULL,
     'SOC 2 Type 2', NULL,
     'Vendor cho Claude 4.7 API. Pay-per-token billing.',
     'gold', DATE '2025-10-01', 'proc2@kaori.local',
     'Foreign vendor — billing USD wire.'),

    (v_eid, 'NCC-2026-005', 'VinAI Research', 'Phạm Thanh Long', '0945500005', 'long.pham@vinai.ai',
     '0100002005', 'Times City T18 Hà Nội', 'Hà Nội', 'VN', 'supplier',
     'AI research; model fine-tuning; LLM hosting', 'Vingroup nội bộ',
     6, 180, 950000000000, 'AA',
     'ISO 27001', 'NeurIPS 2023 Best Paper',
     'Đơn vị nghiên cứu AI nội bộ Vingroup.',
     'gold', DATE '2024-09-20', 'proc1@kaori.local',
     'Strategic partner — pricing internal.'),

    (v_eid, 'NCC-2026-008', 'Maritime Bank Corporate', 'Hoàng Văn Phú', '0967700008', 'phu.hoang@msb.com.vn',
     '0100002008', 'Khâm Thiên Đống Đa Hà Nội', 'Hà Nội', 'VN', 'supplier',
     'Banking; trade finance; FX', 'Tập đoàn',
     30, 8500, 18000000000000, 'AAA',
     'Basel III compliant', 'Top 10 Bank Vietnam 2024',
     'Bank đối tác thanh toán quốc tế + FX hedging.',
     'platinum', DATE '2020-04-30', 'proc1@kaori.local',
     'Banking partner.'),

    (v_eid, 'NCC-2026-010', 'Unknown Vendor TBD', NULL, NULL, 'unknown@tbd.vn',
     NULL, 'Chưa cập nhật', NULL, 'VN', 'contractor',
     'Chưa rõ', 'Chưa rõ',
     NULL, NULL, NULL, NULL,
     NULL, NULL,
     'Hồ sơ vendor thiếu — Procurement cần bổ sung.',
     NULL, NULL, 'proc2@kaori.local',
     'HỒ SƠ THIẾU — không sign cho đến khi đầy đủ.'),

    (v_eid, 'NCC-2026-011', 'KPMG Vietnam', 'Vũ Tuấn Hùng', '0989900011', 'hung.vu@kpmg.com.vn',
     '0100002011', 'Keangnam Landmark Hà Nội', 'Hà Nội', 'VN', 'consultant',
     'Audit; tax; advisory', 'All',
     30, 1800, 8400000000000, 'AAA',
     'Big-4 global brand', 'Best Big-4 VN 2024',
     'Audit 2025 + tư vấn SOC 2 Type 1.',
     'platinum', DATE '2024-12-10', 'proc1@kaori.local',
     'Tier-1 consultant.')
    ON CONFLICT (enterprise_id, code) DO NOTHING;


    -- ── 3. customer_contracts ───────────────────────────────────────
    INSERT INTO customer_contracts
        (enterprise_id, customer_id, contract_no, contract_type, description,
         signed_at, start_at, end_at, value_vnd, payment_terms_days,
         payment_schedule, status, signed_by_customer, customer_signer_title,
         signed_by_us, us_signer_title, attachment_uri, renewal_type, note)
    SELECT v_eid, c.customer_id, x.contract_no, x.contract_type, x.description,
           x.signed_at, x.start_at, x.end_at, x.value_vnd, x.payment_terms_days,
           x.payment_schedule, x.status, x.signed_by_customer, x.customer_signer_title,
           x.signed_by_us, x.us_signer_title, x.attachment_uri, x.renewal_type, x.note
    FROM (VALUES
        ('KH-2026-001', 'KH-VHRS-2024-005', 'license_enterprise',
         'Gói ENT MAX 24 tháng — 4 phòng ban × 10000 customers/tháng',
         DATE '2024-04-10', DATE '2024-05-01', DATE '2026-04-30', 192000000::NUMERIC, 30,
         'monthly', 'active', 'Nguyễn Văn An', 'CMO', 'Hoàng Văn Em', 'COO',
         's3://kaori-contracts/HD-KH-2026-001.pdf', 'auto_renew',
         'Anchor. Renew tự động.'),

        ('KH-2026-002', 'KH-VMT-2025-011', 'license_enterprise',
         'Gói ENT MID 12 tháng',
         DATE '2025-09-15', DATE '2025-10-01', DATE '2026-09-30', 60000000::NUMERIC, 30,
         'quarterly', 'active', 'Trần Thị Bình', 'CIO', 'Hoàng Văn Em', 'COO',
         's3://kaori-contracts/HD-KH-2026-002.pdf', 'manual',
         'Đàm phán upsell ENT MAX.'),

        ('KH-2026-005', 'KH-VG-MSA-2024-001', 'framework_msa',
         'Hợp đồng khung tập đoàn 2024-2027',
         DATE '2024-01-15', DATE '2024-02-01', DATE '2027-01-31', 2400000000::NUMERIC, 45,
         'quarterly', 'active', 'Hoàng Văn Em', 'COO', 'Đại diện Kaori', 'CEO',
         's3://kaori-contracts/HD-KH-2026-005.pdf', 'manual',
         'MSA — subsidiaries đính kèm dưới đây.'),

        ('KH-2026-007', 'KH-BETA-2025-009', 'license_enterprise',
         'Gói ENT BASIC + module Logistics Adoption',
         DATE '2025-11-15', DATE '2025-12-01', DATE '2026-11-30', 30000000::NUMERIC, 120,
         'bi_monthly', 'active', 'Vũ Đình Giang', 'COO', 'Hoàng Văn Em', 'COO',
         's3://kaori-contracts/HD-KH-2026-007.pdf', 'manual',
         'Credit 120 ngày — CFO approval đặc biệt.'),

        ('KH-2026-009', 'KH-XYZ-2026-001', 'license_enterprise',
         'Gói ENT ROI — 8M + 1.5% revenue saved',
         DATE '2026-04-10', DATE '2026-05-01', DATE '2027-04-30', 240000000::NUMERIC, 45,
         'monthly', 'under_review', NULL, NULL, NULL, NULL, NULL, 'manual',
         'Deal lớn nhất tháng. Pending CFO + Legal + CEO.'),

        ('KH-2026-014', 'KH-DELTA-2025-005', 'custom_solution',
         'Custom analytics module — không qua price book',
         DATE '2025-09-30', DATE '2025-10-15', DATE '2026-10-14', 48000000::NUMERIC, 30,
         'monthly', 'active', 'Lý Thị Oanh', 'COO', 'Hoàng Văn Em', 'COO',
         's3://kaori-contracts/HD-KH-2026-014.pdf', 'manual',
         'Custom — margin lower than standard.'),

        ('KH-2026-015', 'KH-VMTDN-2026-001', 'license_pilot',
         'Pilot 3 tháng — gói PILOT 1M/tháng',
         DATE '2026-02-20', DATE '2026-03-01', DATE '2026-05-31', 3000000::NUMERIC, 30,
         'upfront', 'active', 'Cao Văn Phú', 'Branch Manager', 'Hoàng Văn Em', 'COO',
         's3://kaori-contracts/HD-KH-2026-015.pdf', 'manual',
         'Pilot — sẽ scale ENT BASIC.')
    ) AS x(customer_code, contract_no, contract_type, description,
           signed_at, start_at, end_at, value_vnd, payment_terms_days,
           payment_schedule, status, signed_by_customer, customer_signer_title,
           signed_by_us, us_signer_title, attachment_uri, renewal_type, note)
    JOIN customers c ON c.enterprise_id = v_eid AND c.code = x.customer_code
    ON CONFLICT (enterprise_id, contract_no) DO NOTHING;


    -- ── 4. vendor_contracts ─────────────────────────────────────────
    INSERT INTO vendor_contracts
        (enterprise_id, vendor_id, contract_no, contract_type, description,
         signed_at, start_at, end_at, value_vnd, currency, payment_terms_days,
         payment_schedule, status, signed_by_vendor, vendor_signer_title,
         signed_by_us, us_signer_title, attachment_uri, renewal_type, note)
    SELECT v_eid, vd.vendor_id, x.contract_no, x.contract_type, x.description,
           x.signed_at, x.start_at, x.end_at, x.value_vnd, x.currency, x.payment_terms_days,
           x.payment_schedule, x.status, x.signed_by_vendor, x.vendor_signer_title,
           x.signed_by_us, x.us_signer_title, x.attachment_uri, x.renewal_type, x.note
    FROM (VALUES
        ('NCC-2026-001', 'NCC-FPT-MSA-2018-001', 'framework_msa',
         'Master Service Agreement — gia công phần mềm dài hạn',
         DATE '2018-04-15', DATE '2018-05-01', DATE '2028-04-30', NULL::NUMERIC, 'VND', 45,
         'quarterly', 'active', 'Nguyễn Quốc Bảo', 'Managing Partner',
         'Đại diện Kaori', 'CEO',
         's3://kaori-vendors/NCC-FPT-MSA-2018-001.pdf', 'manual',
         'MSA — SOW đính kèm dưới đây.'),

        ('NCC-2026-001', 'NCC-FPT-SOW-2026-007', 'sow_under_msa',
         'SOW #7 — Module RAG + DocSage',
         DATE '2026-04-01', DATE '2026-04-15', DATE '2026-09-15', 840000000::NUMERIC, 'VND', 45,
         'milestone', 'active', 'Nguyễn Quốc Bảo', 'Managing Partner',
         'Hoàng Văn Em', 'COO',
         's3://kaori-vendors/NCC-FPT-SOW-2026-007.pdf', 'manual',
         'SOW dưới MSA-2018-001. 4 milestones × 210M.'),

        ('NCC-2026-003', 'NCC-ANTH-2025-001', 'api_subscription',
         'Claude API — Tier 3 enterprise commit',
         DATE '2025-10-05', DATE '2025-10-15', DATE '2026-10-14', NULL::NUMERIC, 'USD', 15,
         'monthly', 'active', 'Anthropic Sales', 'Sales Director',
         'Hoàng Văn Em', 'COO',
         's3://kaori-vendors/NCC-ANTH-2025-001.pdf', 'manual',
         'Billed USD. ~50K USD/tháng.'),

        ('NCC-2026-005', 'NCC-VINAI-2024-002', 'saas_subscription',
         'Qwen Vietnamese fine-tune hosting',
         DATE '2024-09-25', DATE '2024-10-01', DATE '2026-09-30', 360000000::NUMERIC, 'VND', 30,
         'monthly', 'active', 'Phạm Thanh Long', 'Head of Engineering',
         'Hoàng Văn Em', 'COO',
         's3://kaori-vendors/NCC-VINAI-2024-002.pdf', 'manual',
         'Strategic — internal pricing.'),

        ('NCC-2026-008', 'NCC-MSB-2020-001', 'banking_services',
         'Corporate banking + FX hedging',
         DATE '2020-05-10', DATE '2020-06-01', DATE '2030-05-31', NULL::NUMERIC, 'VND', NULL,
         'as_needed', 'active', 'Hoàng Văn Phú', 'Corporate Banking Head',
         'Hoàng Văn Em', 'COO',
         's3://kaori-vendors/NCC-MSB-2020-001.pdf', 'manual',
         'Banking partner — long-term.'),

        ('NCC-2026-011', 'NCC-KPMG-2024-001', 'consulting',
         'Audit năm 2025 + SOC 2 Type 1 advisory',
         DATE '2024-12-15', DATE '2025-01-01', DATE '2025-12-31', 1200000000::NUMERIC, 'VND', 45,
         'quarterly', 'active', 'Vũ Tuấn Hùng', 'Partner',
         'Hoàng Văn Em', 'COO',
         's3://kaori-vendors/NCC-KPMG-2024-001.pdf', 'manual',
         'Tier-1 audit. Renew Q4 2025.')
    ) AS x(vendor_code, contract_no, contract_type, description,
           signed_at, start_at, end_at, value_vnd, currency, payment_terms_days,
           payment_schedule, status, signed_by_vendor, vendor_signer_title,
           signed_by_us, us_signer_title, attachment_uri, renewal_type, note)
    JOIN vendors vd ON vd.enterprise_id = v_eid AND vd.code = x.vendor_code
    ON CONFLICT (enterprise_id, contract_no) DO NOTHING;

    RAISE NOTICE 'mig 063: seeded customers/vendors/contracts for enterprise %', v_eid;
END $$;
