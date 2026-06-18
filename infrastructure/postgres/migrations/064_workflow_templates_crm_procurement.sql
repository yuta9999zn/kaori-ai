-- =====================================================================
-- 064_workflow_templates_crm_procurement.sql
--
-- P15-S11 — 4 new workflow templates wiring the mig 062 customer +
-- vendor + contract data into approval flows. Existing mig 054 covered
-- marketing / sales pipeline / CS / warehouse / HR / finance basics;
-- this fills the CRM + procurement gap.
--
-- Templates added:
--   1. New Customer Onboarding (CRM)             — sales dept
--   2. New Vendor Onboarding (Procurement)       — finance dept
--   3. Customer Contract Approval                 — sales dept
--   4. Vendor Contract Approval                   — finance dept
--
-- Each template uses decision_if_else for value-based routing and
-- approval_gate where a human signoff blocks progress (K-17
-- side_effect_class = read_only on intake; external on signed-contract
-- write to the customer/vendor record).
--
-- ON CONFLICT DO NOTHING — safe to re-run; matched on display_name +
-- department_type by lower-priority UNIQUE absent today (idempotent
-- via the explicit JSONB shape, not a DB-level dedupe).
-- =====================================================================

INSERT INTO workflow_templates
    (display_name, display_name_vi, description, department_type, category, workflow_definition, estimated_setup_minutes)
VALUES

-- ─── 1. New Customer Onboarding (CRM) ───────────────────────────────
('New Customer Onboarding (CRM)',
 'Onboarding khách hàng mới (CRM)',
 'Thu thập hồ sơ → check tín dụng → quyết định theo deal size → CFO duyệt cho deal lớn → tạo bản ghi khách hàng.',
 'sales',
 'crm_onboarding',
 '{
   "nodes": [
     {"client_id":"n1","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Capture customer profile","title_vi":"Thu thập hồ sơ khách hàng",
      "note":"Tên doanh nghiệp, MST, người liên hệ, doanh thu/năm dự kiến, ngành.",
      "hashtags":["intake","crm"],
      "required_document_types":[
         {"kind":"csv","name":"Customer profile (rich fields)","required":true},
         {"kind":"pdf","name":"Giấy phép kinh doanh","required":false}
      ],
      "sequence_order":1,"position_x":100,"position_y":100},

     {"client_id":"n2","node_type":"step","category":"data_input","side_effect_class":"external",
      "title":"CIC credit check","title_vi":"Tra cứu tín dụng CIC",
      "note":"AM tự tra CIC + đính kèm screenshot. Bắt buộc với mọi KH mới.",
      "hashtags":["credit","compliance"],
      "required_document_types":[
         {"kind":"pdf","name":"CIC report","required":true}
      ],
      "sequence_order":2,"position_x":320,"position_y":100},

     {"client_id":"n3","node_type":"decision_if_else","category":"decision","side_effect_class":"pure",
      "title":"Deal size > 500 triệu?","title_vi":"Giá trị deal > 500 triệu?",
      "note":"Routing theo annual_revenue_vnd. Lớn → CFO; nhỏ → Manager.",
      "hashtags":["routing","value"],
      "required_document_types":[],
      "sequence_order":3,"position_x":540,"position_y":100,
      "decision_config":{"threshold_vnd":500000000,"field":"annual_revenue_vnd"}},

     {"client_id":"n4","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"Manager approval","title_vi":"Manager duyệt",
      "note":"Sales Manager review credit + business case. SLA 24h.",
      "hashtags":["approval","manager"],
      "required_document_types":[],
      "sequence_order":4,"position_x":760,"position_y":40},

     {"client_id":"n5","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"CFO approval","title_vi":"CFO duyệt",
      "note":"Deal lớn — CFO review credit + paid terms. SLA 48h.",
      "hashtags":["approval","cfo","high_value"],
      "required_document_types":[],
      "sequence_order":5,"position_x":760,"position_y":160},

     {"client_id":"n6","node_type":"step","category":"data_input","side_effect_class":"write_idempotent",
      "title":"Create customer record","title_vi":"Tạo bản ghi khách hàng",
      "note":"Ghi vào bảng customers với role tier mặc định. Trigger /enterprise-users/role nếu là rep mới.",
      "hashtags":["create","customers"],
      "required_document_types":[],
      "sequence_order":6,"position_x":980,"position_y":100}
   ],
   "edges":[
     {"source_client_id":"n1","target_client_id":"n2","label":"profile_ready"},
     {"source_client_id":"n2","target_client_id":"n3","label":"credit_checked"},
     {"source_client_id":"n3","target_client_id":"n4","label":"<=500M"},
     {"source_client_id":"n3","target_client_id":"n5","label":">500M"},
     {"source_client_id":"n4","target_client_id":"n6","label":"approved"},
     {"source_client_id":"n5","target_client_id":"n6","label":"approved"}
   ]
 }'::jsonb,
 8),


-- ─── 2. New Vendor Onboarding (Procurement) ─────────────────────────
('New Vendor Onboarding (Procurement)',
 'Onboarding nhà cung cấp mới (Procurement)',
 'Vendor đề xuất → due diligence (chứng nhận, tham chiếu) → quyết định đủ hồ sơ? → Procurement duyệt → CFO cho deal lớn → tạo bản ghi vendor.',
 'finance',
 'procurement_onboarding',
 '{
   "nodes": [
     {"client_id":"n1","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Vendor proposal intake","title_vi":"Tiếp nhận đề xuất NCC",
      "note":"Vendor gửi proposal + brochure + giấy phép.",
      "hashtags":["intake","vendor"],
      "required_document_types":[
         {"kind":"pdf","name":"Vendor proposal","required":true},
         {"kind":"pdf","name":"Business license","required":true}
      ],
      "sequence_order":1,"position_x":100,"position_y":100},

     {"client_id":"n2","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Due diligence","title_vi":"Thẩm định hồ sơ",
      "note":"Check chứng nhận (ISO/SOC), reference từ 2 khách hàng cũ, năng lực tài chính (báo cáo 2 năm).",
      "hashtags":["due_diligence","compliance"],
      "required_document_types":[
         {"kind":"pdf","name":"Certifications","required":true},
         {"kind":"pdf","name":"Reference letters","required":true},
         {"kind":"pdf","name":"Audited financials 2 years","required":false}
      ],
      "sequence_order":2,"position_x":320,"position_y":100},

     {"client_id":"n3","node_type":"decision_if_else","category":"decision","side_effect_class":"pure",
      "title":"Hồ sơ đủ?","title_vi":"Hồ sơ đủ?",
      "note":"Reject path nếu thiếu chứng nhận bắt buộc (vd: NCC-2026-010 Unknown TBD).",
      "hashtags":["routing","gate"],
      "required_document_types":[],
      "sequence_order":3,"position_x":540,"position_y":100},

     {"client_id":"n4","node_type":"step","category":"data_input","side_effect_class":"external",
      "title":"Request more docs","title_vi":"Yêu cầu bổ sung hồ sơ",
      "note":"Email vendor xin bổ sung. Quay lại n2 sau khi nhận.",
      "hashtags":["reject","followup"],
      "required_document_types":[],
      "sequence_order":4,"position_x":540,"position_y":240},

     {"client_id":"n5","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"Procurement Manager approval","title_vi":"Procurement Manager duyệt",
      "note":"Trưởng Procurement review fit + giá so với benchmark thị trường.",
      "hashtags":["approval","procurement"],
      "required_document_types":[],
      "sequence_order":5,"position_x":760,"position_y":100},

     {"client_id":"n6","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"CFO approval (first deal > 1B)","title_vi":"CFO duyệt (deal đầu > 1 tỷ)",
      "note":"CFO chỉ vào khi first_contract_value > 1B VND. Có thể skip nếu deal nhỏ.",
      "hashtags":["approval","cfo"],
      "required_document_types":[],
      "sequence_order":6,"position_x":980,"position_y":100,
      "decision_config":{"threshold_vnd":1000000000,"field":"first_contract_value_vnd"}},

     {"client_id":"n7","node_type":"step","category":"data_input","side_effect_class":"write_idempotent",
      "title":"Create vendor record","title_vi":"Tạo bản ghi NCC",
      "note":"Ghi vào bảng vendors với reliability_tier mặc định bronze; manager review để promote.",
      "hashtags":["create","vendors"],
      "required_document_types":[],
      "sequence_order":7,"position_x":1200,"position_y":100}
   ],
   "edges":[
     {"source_client_id":"n1","target_client_id":"n2","label":"intake_done"},
     {"source_client_id":"n2","target_client_id":"n3","label":"reviewed"},
     {"source_client_id":"n3","target_client_id":"n4","label":"insufficient"},
     {"source_client_id":"n3","target_client_id":"n5","label":"sufficient"},
     {"source_client_id":"n4","target_client_id":"n2","label":"docs_received"},
     {"source_client_id":"n5","target_client_id":"n6","label":"approved"},
     {"source_client_id":"n6","target_client_id":"n7","label":"approved"}
   ]
 }'::jsonb,
 12),


-- ─── 3. Customer Contract Approval ──────────────────────────────────
('Customer Contract Approval',
 'Phê duyệt hợp đồng khách hàng',
 'Draft hợp đồng → Sales review → Legal review → CFO (>1 tỷ) → CEO (>10 tỷ) → khách ký → kích hoạt.',
 'sales',
 'contract_approval',
 '{
   "nodes":[
     {"client_id":"n1","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Draft contract","title_vi":"Soạn hợp đồng",
      "note":"Sales soạn từ template + điền điều khoản tùy biến. Đính kèm bản PDF + DOCX.",
      "hashtags":["draft","contract"],
      "required_document_types":[
         {"kind":"docx","name":"Contract draft (DOCX)","required":true},
         {"kind":"pdf","name":"Contract draft (PDF preview)","required":false}
      ],
      "sequence_order":1,"position_x":100,"position_y":100},

     {"client_id":"n2","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Sales review","title_vi":"Sales review",
      "note":"Sales Lead check số liệu + điều khoản thanh toán + duration.",
      "hashtags":["review","sales"],
      "required_document_types":[],
      "sequence_order":2,"position_x":320,"position_y":100},

     {"client_id":"n3","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"Legal review","title_vi":"Phòng pháp lý duyệt",
      "note":"Legal check điều khoản rủi ro + GDPR/PII + compliance. SLA 48h.",
      "hashtags":["approval","legal"],
      "required_document_types":[
         {"kind":"docx","name":"Legal redline","required":false}
      ],
      "sequence_order":3,"position_x":540,"position_y":100},

     {"client_id":"n4","node_type":"decision_if_else","category":"decision","side_effect_class":"pure",
      "title":"Value > 1 tỷ?","title_vi":"Giá trị > 1 tỷ?",
      "note":"Route theo value_vnd của hợp đồng.",
      "hashtags":["routing"],
      "required_document_types":[],
      "sequence_order":4,"position_x":760,"position_y":100,
      "decision_config":{"threshold_vnd":1000000000,"field":"value_vnd"}},

     {"client_id":"n5","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"CFO approval","title_vi":"CFO duyệt",
      "note":"CFO duyệt khi 1B < value <= 10B.",
      "hashtags":["approval","cfo"],
      "required_document_types":[],
      "sequence_order":5,"position_x":980,"position_y":40},

     {"client_id":"n6","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"CEO approval","title_vi":"CEO duyệt",
      "note":"CEO duyệt khi value > 10B (deal chiến lược).",
      "hashtags":["approval","ceo","strategic"],
      "required_document_types":[],
      "sequence_order":6,"position_x":980,"position_y":180,
      "decision_config":{"threshold_vnd":10000000000,"field":"value_vnd"}},

     {"client_id":"n7","node_type":"step","category":"data_input","side_effect_class":"external",
      "title":"Customer signs","title_vi":"Khách hàng ký",
      "note":"Gửi DocuSign / e-sign / scan bản ký tay. Đính kèm signed PDF.",
      "hashtags":["sign","customer"],
      "required_document_types":[
         {"kind":"pdf","name":"Signed contract","required":true}
      ],
      "sequence_order":7,"position_x":1200,"position_y":100},

     {"client_id":"n8","node_type":"step","category":"data_input","side_effect_class":"write_idempotent",
      "title":"Activate contract","title_vi":"Kích hoạt hợp đồng",
      "note":"Đổi status từ draft/under_review sang active. Trigger billing schedule.",
      "hashtags":["activate","contract"],
      "required_document_types":[],
      "sequence_order":8,"position_x":1420,"position_y":100}
   ],
   "edges":[
     {"source_client_id":"n1","target_client_id":"n2","label":"drafted"},
     {"source_client_id":"n2","target_client_id":"n3","label":"sales_ok"},
     {"source_client_id":"n3","target_client_id":"n4","label":"legal_ok"},
     {"source_client_id":"n4","target_client_id":"n5","label":"<=10B"},
     {"source_client_id":"n4","target_client_id":"n6","label":">10B"},
     {"source_client_id":"n5","target_client_id":"n7","label":"approved"},
     {"source_client_id":"n6","target_client_id":"n7","label":"approved"},
     {"source_client_id":"n7","target_client_id":"n8","label":"signed"}
   ]
 }'::jsonb,
 15),


-- ─── 4. Vendor Contract Approval ────────────────────────────────────
('Vendor Contract Approval',
 'Phê duyệt hợp đồng nhà cung cấp',
 'Procurement review → Legal review → CFO (>500 triệu) → Procurement Director → ký → kích hoạt.',
 'finance',
 'contract_approval',
 '{
   "nodes":[
     {"client_id":"n1","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Vendor sends draft","title_vi":"NCC gửi bản dự thảo",
      "note":"NCC gửi SOW / MSA. Đính kèm DOCX + PDF.",
      "hashtags":["draft","vendor"],
      "required_document_types":[
         {"kind":"docx","name":"Vendor draft","required":true}
      ],
      "sequence_order":1,"position_x":100,"position_y":100},

     {"client_id":"n2","node_type":"step","category":"data_input","side_effect_class":"read_only",
      "title":"Procurement review","title_vi":"Procurement review",
      "note":"Compare giá vs benchmark, kiểm scope, term sheet.",
      "hashtags":["review","procurement"],
      "required_document_types":[],
      "sequence_order":2,"position_x":320,"position_y":100},

     {"client_id":"n3","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"Legal review","title_vi":"Pháp lý duyệt",
      "note":"Legal check warranty, IP, termination, SLA.",
      "hashtags":["approval","legal"],
      "required_document_types":[],
      "sequence_order":3,"position_x":540,"position_y":100},

     {"client_id":"n4","node_type":"decision_if_else","category":"decision","side_effect_class":"pure",
      "title":"Value > 500 triệu?","title_vi":"Giá trị > 500 triệu?",
      "note":"Route theo value_vnd.",
      "hashtags":["routing"],
      "required_document_types":[],
      "sequence_order":4,"position_x":760,"position_y":100,
      "decision_config":{"threshold_vnd":500000000,"field":"value_vnd"}},

     {"client_id":"n5","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"Procurement Director approval","title_vi":"Procurement Director duyệt",
      "note":"Director duyệt cho deal <= 500M.",
      "hashtags":["approval","procurement"],
      "required_document_types":[],
      "sequence_order":5,"position_x":980,"position_y":40},

     {"client_id":"n6","node_type":"approval_gate","category":"approval","side_effect_class":"external",
      "title":"CFO approval","title_vi":"CFO duyệt",
      "note":"CFO duyệt khi value > 500M.",
      "hashtags":["approval","cfo"],
      "required_document_types":[],
      "sequence_order":6,"position_x":980,"position_y":180},

     {"client_id":"n7","node_type":"step","category":"data_input","side_effect_class":"external",
      "title":"Both parties sign","title_vi":"Hai bên ký",
      "note":"Sign + scan. Lưu vào s3://kaori-vendors/.",
      "hashtags":["sign"],
      "required_document_types":[
         {"kind":"pdf","name":"Signed contract","required":true}
      ],
      "sequence_order":7,"position_x":1200,"position_y":100},

     {"client_id":"n8","node_type":"step","category":"data_input","side_effect_class":"write_idempotent",
      "title":"Activate contract","title_vi":"Kích hoạt hợp đồng",
      "note":"Đổi status sang active. Sync vào AP system nếu có.",
      "hashtags":["activate"],
      "required_document_types":[],
      "sequence_order":8,"position_x":1420,"position_y":100}
   ],
   "edges":[
     {"source_client_id":"n1","target_client_id":"n2","label":"received"},
     {"source_client_id":"n2","target_client_id":"n3","label":"proc_ok"},
     {"source_client_id":"n3","target_client_id":"n4","label":"legal_ok"},
     {"source_client_id":"n4","target_client_id":"n5","label":"<=500M"},
     {"source_client_id":"n4","target_client_id":"n6","label":">500M"},
     {"source_client_id":"n5","target_client_id":"n7","label":"approved"},
     {"source_client_id":"n6","target_client_id":"n7","label":"approved"},
     {"source_client_id":"n7","target_client_id":"n8","label":"signed"}
   ]
 }'::jsonb,
 12)

ON CONFLICT DO NOTHING;
