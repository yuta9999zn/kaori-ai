-- =====================================================================
-- 103_industry_templates_seed.sql — Phase 2.8 D3 — Industry seed
--
-- Seeds 3 of 8 industries with full org config to prove shape:
--   • retail         — bán lẻ, 6 dept, 17 workflow link, 8 KPI, 6 schema
--   • finance        — tài chính, 5 dept, 7 workflow link, 7 KPI, 4 schema
--   • generic_sme    — SME chung, 4 dept, 5 workflow link, 4 KPI, 3 schema
--
-- Deferred (Phase 3 — seed when first customer in that industry signs):
--   fnb / logistics / healthcare / manufacturing / education
--
-- Workflow links reference workflow_templates from mig 054 + mig 069
-- by display_name (LIMIT 1 because workflow_templates lacks UNIQUE on
-- display_name).
-- =====================================================================

BEGIN;

-- ─── 1. industry_templates rows ──────────────────────────────────────

INSERT INTO industry_templates (
    industry_key, display_name, display_name_vi, description_vi,
    icon_key, accent_color, primary_kpis,
    ai_confidence_threshold, suggested_pricing_plan, compliance_notes_vi
) VALUES
    ('retail', 'Retail', 'Bán lẻ',
     'Bán lẻ đa kênh, online + offline. Tập trung adoption + churn + tồn kho.',
     'shopping-bag', '#FF6B6B',
     ARRAY['revenue_monthly','gross_margin','repeat_purchase_rate','churn_risk','stockout_risk','inventory_turnover','campaign_roi','complaint_resolution_time'],
     0.7000, 'ENT_MID',
     'Bán lẻ ít compliance đặc thù. PDPL Vietnam khi giữ dữ liệu khách >12 tháng.'),

    ('finance', 'Finance', 'Tài chính',
     'Tài chính nội bộ doanh nghiệp (treasury + AP/AR + risk). Compliance cao.',
     'banknotes', '#4ECDC4',
     ARRAY['cash_runway_days','dso_days','dpo_days','accounts_receivable','accounts_payable','budget_variance','payment_delay_rate'],
     0.8500, 'ENT_MAX',
     'Audit retention 7 năm (Luật kế toán 2015). Audit trail mọi quyết định >50M VND.'),

    ('generic_sme', 'Generic SME', 'Doanh nghiệp vừa và nhỏ',
     'Cấu hình tổng quát cho SME chưa rõ ngành. Có thể đổi sang ngành cụ thể sau.',
     'briefcase', '#95A5A6',
     ARRAY['revenue_monthly','expenses_monthly','headcount','customer_count'],
     0.7000, 'ENT_BASIC',
     NULL)
ON CONFLICT (industry_key) DO NOTHING;


-- ─── 2. industry_department_templates ────────────────────────────────

-- Retail: 6 phòng ban
INSERT INTO industry_department_templates (
    industry_id, dept_key, dept_type, display_name, display_name_vi,
    description_vi, sequence_order, is_required, suggested_headcount
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'sales', 'sales', 'Sales', 'Kinh doanh',
     'Lead → báo giá → chốt đơn → theo dõi thanh toán.', 1, TRUE,
     '{"manager":1,"operator":3,"analyst":1}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'marketing', 'marketing', 'Marketing', 'Tiếp thị',
     'Chiến dịch, segment, ROI campaign.', 2, TRUE,
     '{"manager":1,"operator":2,"analyst":1}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'warehouse', 'warehouse', 'Warehouse', 'Kho vận',
     'Tồn kho, nhập hàng, kiểm tra chất lượng.', 3, TRUE,
     '{"manager":1,"operator":4}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'finance', 'finance', 'Finance', 'Tài chính kế toán',
     'Hoá đơn, AR/AP, dòng tiền.', 4, TRUE,
     '{"manager":1,"operator":2,"analyst":1}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'customer_service', 'customer_service', 'Customer Service', 'Chăm sóc khách hàng',
     'Ticket, khiếu nại, hoàn tiền, NPS.', 5, TRUE,
     '{"manager":1,"operator":3}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'management', 'custom', 'Management', 'Ban điều hành',
     'OKR, dashboard tổng, báo cáo HĐQT. (dept_type=custom — chưa có enum management trong departments mig 046; xử lý sau Phase 2.)', 6, TRUE,
     '{"executive":2}'::jsonb)
ON CONFLICT (industry_id, dept_key) DO NOTHING;

-- Finance industry: 5 phòng ban
INSERT INTO industry_department_templates (
    industry_id, dept_key, dept_type, display_name, display_name_vi,
    description_vi, sequence_order, is_required, suggested_headcount
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'treasury', 'finance', 'Treasury', 'Ngân quỹ',
     'Dòng tiền, hedge FX, cash positioning.', 1, TRUE,
     '{"manager":1,"analyst":2}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'accounting', 'finance', 'Accounting', 'Kế toán',
     'Sổ sách, đóng kỳ, thuế.', 2, TRUE,
     '{"manager":1,"operator":3}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'ap', 'finance', 'Accounts Payable', 'Phải trả',
     'Hóa đơn nhà cung cấp, duyệt thanh toán.', 3, TRUE,
     '{"manager":1,"operator":2}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'ar', 'finance', 'Accounts Receivable', 'Phải thu',
     'Hóa đơn khách, đốc thúc thu nợ.', 4, TRUE,
     '{"manager":1,"operator":2}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'risk', 'finance', 'Risk & Compliance', 'Rủi ro & Tuân thủ',
     'Audit trail, compliance, fraud detection.', 5, FALSE,
     '{"manager":1,"analyst":1}'::jsonb)
ON CONFLICT (industry_id, dept_key) DO NOTHING;

-- Generic SME: 4 phòng ban
INSERT INTO industry_department_templates (
    industry_id, dept_key, dept_type, display_name, display_name_vi,
    description_vi, sequence_order, is_required, suggested_headcount
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'sales', 'sales', 'Sales', 'Kinh doanh',
     'Lead → chốt đơn → thu tiền.', 1, TRUE,
     '{"manager":1,"operator":2}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'ops', 'custom', 'Operations', 'Vận hành',
     'Quy trình nội bộ, dự án, công việc. (dept_type=custom — chưa có enum operations trong departments mig 046.)', 2, TRUE,
     '{"manager":1,"operator":2}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'finance', 'finance', 'Finance', 'Tài chính',
     'Sổ sách, AR, AP.', 3, TRUE,
     '{"manager":1,"operator":1}'::jsonb),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'hr', 'hr', 'HR', 'Nhân sự',
     'Tuyển dụng, onboarding, lương.', 4, FALSE,
     '{"manager":1,"operator":1}'::jsonb)
ON CONFLICT (industry_id, dept_key) DO NOTHING;


-- ─── 3. industry_workflow_links ──────────────────────────────────────
--
-- Reference existing workflow_templates from mig 054 + mig 069 by name.
-- LIMIT 1 because workflow_templates display_name is not UNIQUE.
-- Each INSERT filters out rows where the subquery returns NULL so
-- missing-template rows are silently skipped (forward-compatible if
-- a future mig retires a template name).

INSERT INTO industry_workflow_links (industry_id, industry_dept_id, workflow_template_id, recommendation_level, sequence_order)
SELECT
    (SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
    (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key=dk),
    (SELECT template_id FROM workflow_templates WHERE display_name=tn ORDER BY template_id LIMIT 1),
    rec, seq
FROM (VALUES
    -- Retail / Sales
    ('sales', 'Lead Qualification Workflow', 'core',      1),
    ('sales', 'Quote-to-Cash',               'core',      2),
    ('sales', 'Deal Risk Assessment',        'suggested', 3),
    -- Retail / Marketing
    ('marketing', 'Email Campaign with Segmentation', 'core',      1),
    ('marketing', 'Customer Onboarding Sequence',     'core',      2),
    ('marketing', 'Abandoned Cart Recovery',          'suggested', 3),
    -- Retail / Warehouse
    ('warehouse', 'Inventory Reorder Trigger', 'core',      1),
    ('warehouse', 'Stock-out Risk Alert',      'core',      2),
    ('warehouse', 'Quality Issue Resolution',  'suggested', 3),
    -- Retail / Finance
    ('finance', 'Invoice Processing',     'core',      1),
    ('finance', 'AR Collection Reminder', 'core',      2),
    ('finance', 'Cash Flow Forecasting',  'suggested', 3),
    -- Retail / Customer Service
    ('customer_service', 'Complaint Resolution', 'core',      1),
    ('customer_service', 'Refund Request',       'core',      2),
    ('customer_service', 'Escalation Path',      'suggested', 3)
) AS x(dk, tn, rec, seq)
WHERE (SELECT template_id FROM workflow_templates WHERE display_name=tn ORDER BY template_id LIMIT 1) IS NOT NULL
ON CONFLICT (industry_id, industry_dept_id, workflow_template_id) DO NOTHING;

-- Finance industry workflow links
INSERT INTO industry_workflow_links (industry_id, industry_dept_id, workflow_template_id, recommendation_level, sequence_order)
SELECT
    (SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
    (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key=dk),
    (SELECT template_id FROM workflow_templates WHERE display_name=tn ORDER BY template_id LIMIT 1),
    rec, seq
FROM (VALUES
    ('ap',         'Invoice Processing',     'core', 1),
    ('ar',         'AR Collection Reminder', 'core', 1),
    ('treasury',   'Cash Flow Forecasting',  'core', 1),
    ('accounting', 'Invoice Processing',     'suggested', 2)
) AS x(dk, tn, rec, seq)
WHERE (SELECT template_id FROM workflow_templates WHERE display_name=tn ORDER BY template_id LIMIT 1) IS NOT NULL
ON CONFLICT (industry_id, industry_dept_id, workflow_template_id) DO NOTHING;

-- Generic SME workflow links
INSERT INTO industry_workflow_links (industry_id, industry_dept_id, workflow_template_id, recommendation_level, sequence_order)
SELECT
    (SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
    (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme') AND dept_key=dk),
    (SELECT template_id FROM workflow_templates WHERE display_name=tn ORDER BY template_id LIMIT 1),
    rec, seq
FROM (VALUES
    ('sales',   'Lead Qualification Workflow', 'core',      1),
    ('sales',   'Quote-to-Cash',               'suggested', 2),
    ('finance', 'Invoice Processing',          'core',      1),
    ('hr',      'Hiring Funnel',               'core',      1),
    ('hr',      'Onboarding New Employee',     'core',      2)
) AS x(dk, tn, rec, seq)
WHERE (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme') AND dept_key=dk) IS NOT NULL
  AND (SELECT template_id FROM workflow_templates WHERE display_name=tn ORDER BY template_id LIMIT 1) IS NOT NULL
ON CONFLICT (industry_id, industry_dept_id, workflow_template_id) DO NOTHING;


-- ─── 4. industry_kpi_templates ───────────────────────────────────────

-- Retail KPIs
INSERT INTO industry_kpi_templates (
    industry_id, industry_dept_id, kpi_key, display_name, display_name_vi,
    computation_hint, unit, threshold_warning, threshold_critical,
    higher_is_better, sequence_order, is_primary
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'revenue_monthly', 'Monthly Revenue', 'Doanh thu tháng',
     'SUM(orders.amount) WHERE month=current', 'VND',
     50000000.0000, 30000000.0000, TRUE, 1, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'gross_margin', 'Gross Margin', 'Lợi nhuận gộp',
     '(revenue - cogs)/revenue', 'pct',
     0.2500, 0.1500, TRUE, 2, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'churn_risk', 'Churn Risk', 'Rủi ro rời bỏ',
     'COUNT(customers WHERE last_purchase > 90 days)/COUNT(customers)', 'pct',
     0.1500, 0.2500, FALSE, 3, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='warehouse'),
     'stockout_risk', 'Stockout Risk', 'Nguy cơ hết hàng',
     'COUNT(sku WHERE days_of_stock < 7)/COUNT(sku)', 'pct',
     0.0500, 0.1000, FALSE, 4, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='warehouse'),
     'inventory_turnover', 'Inventory Turnover', 'Vòng quay tồn kho',
     'cogs_yearly / avg_inventory', 'count',
     6.0000, 4.0000, TRUE, 5, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='marketing'),
     'campaign_roi', 'Campaign ROI', 'ROI chiến dịch',
     'revenue_attributed / campaign_cost', 'count',
     3.0000, 1.5000, TRUE, 6, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='customer_service'),
     'complaint_resolution_time', 'Complaint Resolution Time', 'Thời gian giải quyết khiếu nại',
     'AVG(ticket_close_ts - ticket_open_ts)', 'days',
     2.0000, 5.0000, FALSE, 7, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'repeat_purchase_rate', 'Repeat Purchase Rate', 'Tỷ lệ mua lại',
     'COUNT(repeat_customers)/COUNT(customers)', 'pct',
     0.3000, 0.2000, TRUE, 8, FALSE)
ON CONFLICT (industry_id, industry_dept_id, kpi_key) DO NOTHING;

-- Finance KPIs
INSERT INTO industry_kpi_templates (
    industry_id, industry_dept_id, kpi_key, display_name, display_name_vi,
    computation_hint, unit, threshold_warning, threshold_critical,
    higher_is_better, sequence_order, is_primary
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     NULL, 'cash_runway_days', 'Cash Runway (days)', 'Số ngày dòng tiền',
     'cash_balance / avg_daily_burn', 'days',
     90.0000, 60.0000, TRUE, 1, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='ar'),
     'dso_days', 'Days Sales Outstanding', 'DSO',
     'AR_balance / (revenue/365)', 'days',
     45.0000, 60.0000, FALSE, 2, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='ap'),
     'dpo_days', 'Days Payable Outstanding', 'DPO',
     'AP_balance / (cogs/365)', 'days',
     30.0000, 45.0000, TRUE, 3, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='ar'),
     'accounts_receivable', 'Accounts Receivable', 'Phải thu',
     'SUM(invoices WHERE status=open)', 'VND',
     500000000.0000, 1000000000.0000, FALSE, 4, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='ap'),
     'accounts_payable', 'Accounts Payable', 'Phải trả',
     'SUM(bills WHERE status=open)', 'VND',
     300000000.0000, 800000000.0000, FALSE, 5, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     NULL, 'budget_variance', 'Budget Variance', 'Chênh ngân sách',
     '(actual - budget)/budget', 'pct',
     0.0500, 0.1000, FALSE, 6, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     NULL, 'payment_delay_rate', 'Payment Delay Rate', 'Tỷ lệ thanh toán trễ',
     'COUNT(payments WHERE days_late>0)/COUNT(payments)', 'pct',
     0.1000, 0.2000, FALSE, 7, FALSE)
ON CONFLICT (industry_id, industry_dept_id, kpi_key) DO NOTHING;

-- Generic SME KPIs
INSERT INTO industry_kpi_templates (
    industry_id, industry_dept_id, kpi_key, display_name, display_name_vi,
    computation_hint, unit, threshold_warning, threshold_critical,
    higher_is_better, sequence_order, is_primary
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     NULL, 'revenue_monthly', 'Monthly Revenue', 'Doanh thu tháng',
     'SUM(orders.amount) WHERE month=current', 'VND',
     20000000.0000, 10000000.0000, TRUE, 1, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     NULL, 'expenses_monthly', 'Monthly Expenses', 'Chi phí tháng',
     'SUM(expenses) WHERE month=current', 'VND',
     15000000.0000, 25000000.0000, FALSE, 2, TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     NULL, 'headcount', 'Headcount', 'Số nhân sự',
     'COUNT(employees WHERE status=active)', 'count',
     NULL, NULL, TRUE, 3, FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     NULL, 'customer_count', 'Customer Count', 'Số khách',
     'COUNT(DISTINCT customers)', 'count',
     NULL, NULL, TRUE, 4, FALSE)
ON CONFLICT (industry_id, industry_dept_id, kpi_key) DO NOTHING;


-- ─── 5. industry_data_schema_templates ───────────────────────────────

-- Retail data schemas
INSERT INTO industry_data_schema_templates (
    industry_id, industry_dept_id, schema_key, display_name_vi,
    description_vi, column_schema, expected_file_kinds, is_required,
    sequence_order
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'customers', 'Khách hàng',
     'Danh sách khách hàng + thông tin liên hệ.',
     '[{"name":"customer_id","type":"string","required":true},
       {"name":"name","type":"string","required":true},
       {"name":"phone","type":"string","required":false},
       {"name":"email","type":"string","required":false},
       {"name":"first_purchase_date","type":"date","required":false},
       {"name":"last_purchase_date","type":"date","required":false}]'::jsonb,
     ARRAY['csv','xlsx'], TRUE, 1),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'orders', 'Đơn hàng',
     'Bảng giao dịch đơn hàng — bắt buộc cho North Star NOV.',
     '[{"name":"order_id","type":"string","required":true},
       {"name":"customer_id","type":"string","required":true},
       {"name":"order_date","type":"date","required":true},
       {"name":"amount","type":"numeric","required":true},
       {"name":"channel","type":"string","required":false},
       {"name":"product_id","type":"string","required":false}]'::jsonb,
     ARRAY['csv','xlsx'], TRUE, 2),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='warehouse'),
     'inventory', 'Tồn kho',
     'Tồn kho hiện tại + reorder point.',
     '[{"name":"sku","type":"string","required":true},
       {"name":"product_name","type":"string","required":true},
       {"name":"qty_on_hand","type":"numeric","required":true},
       {"name":"reorder_point","type":"numeric","required":false}]'::jsonb,
     ARRAY['csv','xlsx'], TRUE, 3),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     NULL, 'products', 'Sản phẩm',
     'Catalog sản phẩm + giá + danh mục.',
     '[{"name":"product_id","type":"string","required":true},
       {"name":"name","type":"string","required":true},
       {"name":"price","type":"numeric","required":true},
       {"name":"category","type":"string","required":false}]'::jsonb,
     ARRAY['csv','xlsx'], FALSE, 4),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='marketing'),
     'campaigns', 'Chiến dịch',
     'Lịch sử chiến dịch + chi phí + doanh thu attribute.',
     '[{"name":"campaign_id","type":"string","required":true},
       {"name":"channel","type":"string","required":true},
       {"name":"cost","type":"numeric","required":true},
       {"name":"revenue_attributed","type":"numeric","required":false}]'::jsonb,
     ARRAY['csv'], FALSE, 5),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='retail') AND dept_key='customer_service'),
     'support_tickets', 'Ticket hỗ trợ',
     'Ticket khiếu nại + thời gian xử lý.',
     '[{"name":"ticket_id","type":"string","required":true},
       {"name":"customer_id","type":"string","required":true},
       {"name":"opened_at","type":"datetime","required":true},
       {"name":"closed_at","type":"datetime","required":false},
       {"name":"category","type":"string","required":false}]'::jsonb,
     ARRAY['csv'], FALSE, 6)
ON CONFLICT (industry_id, industry_dept_id, schema_key) DO NOTHING;

-- Finance data schemas
INSERT INTO industry_data_schema_templates (
    industry_id, industry_dept_id, schema_key, display_name_vi,
    description_vi, column_schema, expected_file_kinds, is_required,
    sequence_order
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='ap'),
     'invoices', 'Hoá đơn (AP)',
     'Hoá đơn nhà cung cấp.',
     '[{"name":"invoice_id","type":"string","required":true},
       {"name":"vendor_id","type":"string","required":true},
       {"name":"amount","type":"numeric","required":true},
       {"name":"due_date","type":"date","required":true},
       {"name":"status","type":"string","required":true}]'::jsonb,
     ARRAY['csv','xlsx','pdf'], TRUE, 1),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='ar'),
     'ar_aging', 'Tuổi nợ phải thu',
     'Phải thu phân theo bucket 30/60/90.',
     '[{"name":"customer_id","type":"string","required":true},
       {"name":"bucket","type":"string","required":true},
       {"name":"amount","type":"numeric","required":true}]'::jsonb,
     ARRAY['csv','xlsx'], TRUE, 2),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='finance') AND dept_key='treasury'),
     'cash_movements', 'Dòng tiền',
     'Inflow + outflow theo ngày.',
     '[{"name":"date","type":"date","required":true},
       {"name":"inflow","type":"numeric","required":false},
       {"name":"outflow","type":"numeric","required":false},
       {"name":"balance","type":"numeric","required":true}]'::jsonb,
     ARRAY['csv'], TRUE, 3),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     NULL, 'budget_actuals', 'Ngân sách thực tế',
     'Budget vs actual mỗi tháng.',
     '[{"name":"period","type":"string","required":true},
       {"name":"category","type":"string","required":true},
       {"name":"budget","type":"numeric","required":true},
       {"name":"actual","type":"numeric","required":true}]'::jsonb,
     ARRAY['csv','xlsx'], FALSE, 4)
ON CONFLICT (industry_id, industry_dept_id, schema_key) DO NOTHING;

-- Generic SME schemas
INSERT INTO industry_data_schema_templates (
    industry_id, industry_dept_id, schema_key, display_name_vi,
    description_vi, column_schema, expected_file_kinds, is_required,
    sequence_order
) VALUES
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     NULL, 'customers', 'Khách hàng',
     'Danh sách khách + thông tin liên hệ.',
     '[{"name":"customer_id","type":"string","required":true},
       {"name":"name","type":"string","required":true}]'::jsonb,
     ARRAY['csv','xlsx'], TRUE, 1),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme') AND dept_key='sales'),
     'orders', 'Đơn hàng',
     'Đơn hàng + số tiền.',
     '[{"name":"order_id","type":"string","required":true},
       {"name":"amount","type":"numeric","required":true},
       {"name":"order_date","type":"date","required":true}]'::jsonb,
     ARRAY['csv','xlsx'], TRUE, 2),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     (SELECT template_id FROM industry_department_templates WHERE industry_id=(SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme') AND dept_key='finance'),
     'invoices', 'Hoá đơn',
     'Hoá đơn ra/vào.',
     '[{"name":"invoice_id","type":"string","required":true},
       {"name":"amount","type":"numeric","required":true},
       {"name":"due_date","type":"date","required":true}]'::jsonb,
     ARRAY['csv','xlsx','pdf'], FALSE, 3)
ON CONFLICT (industry_id, industry_dept_id, schema_key) DO NOTHING;


-- ─── 6. industry_role_permission_templates ───────────────────────────
--
-- Subset of full permission matrix. Phase 2 PDP will expand.

INSERT INTO industry_role_permission_templates (
    industry_id, dept_type, seniority_level, default_role, permission_keys, overridable
) VALUES
    -- Retail / sales
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'sales', 'executive', 'MANAGER',
     ARRAY['approve_discount_25pct','view_all_pipeline','export_customer_data','assign_lead'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'sales', 'senior', 'OPERATOR',
     ARRAY['approve_discount_15pct','view_own_pipeline','edit_lead','export_own_data'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'sales', 'mid', 'OPERATOR',
     ARRAY['approve_discount_10pct','view_own_pipeline','edit_lead'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'sales', 'junior', 'OPERATOR',
     ARRAY['view_own_pipeline','edit_lead'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='retail'),
     'sales', 'entry', 'VIEWER',
     ARRAY['view_own_pipeline'], FALSE),

    -- Finance / accounting
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'finance', 'executive', 'MANAGER',
     ARRAY['approve_invoice_unlimited','approve_payment_unlimited','view_all_books','export_financial_data','close_period'], FALSE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'finance', 'senior', 'OPERATOR',
     ARRAY['approve_invoice_50m','approve_payment_50m','view_all_books','reconcile_bank'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'finance', 'mid', 'OPERATOR',
     ARRAY['approve_invoice_20m','enter_journal','reconcile_bank'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'finance', 'junior', 'OPERATOR',
     ARRAY['enter_journal','view_assigned'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='finance'),
     'finance', 'entry', 'VIEWER',
     ARRAY['view_assigned'], FALSE),

    -- Generic SME / sales + finance
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'sales', 'executive', 'MANAGER',
     ARRAY['approve_discount','view_all_pipeline','export_customer_data'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'sales', 'mid', 'OPERATOR',
     ARRAY['view_own_pipeline','edit_lead'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'finance', 'executive', 'MANAGER',
     ARRAY['approve_invoice','approve_payment','view_books'], TRUE),
    ((SELECT industry_id FROM industry_templates WHERE industry_key='generic_sme'),
     'finance', 'mid', 'OPERATOR',
     ARRAY['view_books'], TRUE)
ON CONFLICT (industry_id, dept_type, seniority_level) DO NOTHING;


COMMIT;
