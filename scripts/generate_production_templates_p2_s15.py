#!/usr/bin/env python3
"""Generate `069_production_templates_seed.sql` — 25 production-ready
templates for P2-S15 (5 per vertical × 5 verticals).

Per docs/sprint/P2_S15_RESUME_CHECKLIST.md §2 + WORKFLOW_SYSTEM.md §2.2-2.7,
each template:
  - Uses node_type_catalog_key from mig 068 (45 catalog entries)
  - Tagged with industry_vertical for AI-HSC-016 cohort filter
  - 5 cards (matches mig 054 "5-7 bước" anh directive)

Run from repo root:
    python scripts/generate_production_templates_p2_s15.py
    # writes infrastructure/postgres/migrations/069_production_templates_seed.sql
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class Card:
    title: str
    title_vi: str
    node_type_key: str          # FK by key to mig 068 node_type_catalog
    note: str
    hashtags: List[str] = field(default_factory=list)
    required_documents: List[dict] = field(default_factory=list)


@dataclass
class Template:
    name: str
    name_vi: str
    description: str
    department_type: str        # marketing / sales / customer_service / warehouse / finance
    category: str
    industry_vertical: str      # general / retail / fintech / fmcg / logistics / saas / manufacturing / healthcare
    estimated_setup_minutes: int
    cards: List[Card]


# ─────────────────────────────────────────────────────────────────────
# 5 Marketing templates
# ─────────────────────────────────────────────────────────────────────
MARKETING = [
    Template(
        name="Campaign Launch",
        name_vi="Khởi chạy chiến dịch marketing",
        description="Define segment → A/B test content → manager approve → send → measure ROAS.",
        department_type="marketing", category="campaign", industry_vertical="general",
        estimated_setup_minutes=10,
        cards=[
            Card("Define segment", "Xác định segment", "read_table",
                 "Đọc customer table + filter theo segment criteria.",
                 hashtags=["segmentation"],
                 required_documents=[{"kind": "csv", "name": "Segment list", "required": True}]),
            Card("Draft variants", "Soạn 2 variants", "generate_narrative",
                 "Sinh 2 phiên bản subject + body cho A/B test.",
                 hashtags=["content", "ai"]),
            Card("Manager approval", "Duyệt nội dung", "approval_gate",
                 "Marketing manager duyệt cả 2 variants trước khi send.",
                 hashtags=["approval"]),
            Card("Send campaign", "Gửi chiến dịch", "send_email",
                 "Send 50/50 split. idempotency_key = campaign_id+variant.",
                 hashtags=["send", "ab_test"]),
            Card("Measure ROAS", "Đo ROAS", "publish_insight",
                 "Tính revenue attribution / cost → ROAS. Publish vào Insight Hub.",
                 hashtags=["roas", "kpi"],
                 required_documents=[{"kind": "csv", "name": "Revenue attribution", "required": True}]),
        ],
    ),
    Template(
        name="Churn Intervention",
        name_vi="Can thiệp khách rời",
        description="Detect churn risk → classify reason → trigger save flow → measure save rate.",
        department_type="marketing", category="retention", industry_vertical="saas",
        estimated_setup_minutes=12,
        cards=[
            Card("Pull at-risk customers", "Lấy danh sách khách rủi ro", "call_risk_detection",
                 "Risk detection trên 9 adoption signals — output high-risk list.",
                 hashtags=["risk_detection", "churn"]),
            Card("Classify reason", "Phân loại nguyên nhân", "classify_text",
                 "Phân loại từ feedback comments → pricing / feature / support / other.",
                 hashtags=["classification"]),
            Card("Decide save offer", "Chọn save offer", "if_else",
                 "Nếu reason=pricing thì discount offer; nếu feature thì 1-1 demo.",
                 hashtags=["routing"]),
            Card("Send save email", "Gửi email cứu", "send_email",
                 "Personalized email + offer per reason cluster.",
                 hashtags=["save", "personalize"]),
            Card("Track save rate", "Theo dõi save rate", "publish_insight",
                 "30-day save rate per cohort. Promote winning variant.",
                 hashtags=["retention", "kpi"]),
        ],
    ),
    Template(
        name="VIP Onboarding",
        name_vi="Onboarding khách VIP",
        description="VIP detection → CSM assignment → welcome call → activation milestone tracking.",
        department_type="marketing", category="onboarding", industry_vertical="fintech",
        estimated_setup_minutes=15,
        cards=[
            Card("Detect VIP signup", "Phát hiện khách VIP", "read_webhook",
                 "Webhook từ payment system khi LTV > 50M VND ngay từ first transaction.",
                 hashtags=["vip", "intake"]),
            Card("Create CSM task", "Tạo task cho CSM", "create_task",
                 "Assign tới CSM team với SLA 24h.",
                 hashtags=["csm", "assignment"]),
            Card("Schedule welcome call", "Lên lịch welcome call", "send_email",
                 "Gửi link Calendly để khách book 30-min call.",
                 hashtags=["calendar"]),
            Card("Track activation", "Theo dõi activation", "rag_query",
                 "RAG query xem khách đã đạt 3/5 activation milestones chưa.",
                 hashtags=["activation"]),
            Card("Update VIP dashboard", "Cập nhật dashboard VIP", "display_dashboard",
                 "Realtime VIP funnel tile cho Sales Director.",
                 hashtags=["dashboard"]),
        ],
    ),
    Template(
        name="Lead Nurture Sequence",
        name_vi="Chuỗi nuôi dưỡng lead",
        description="Lead intake → score → drip email sequence → handoff to sales when MQL.",
        department_type="marketing", category="lead_gen", industry_vertical="general",
        estimated_setup_minutes=8,
        cards=[
            Card("Lead intake", "Tiếp nhận lead", "read_form_submission",
                 "Webhook từ marketing form / Zalo OA / Facebook lead form.",
                 hashtags=["intake", "lead"]),
            Card("Score lead", "Chấm điểm lead", "call_insight_engine",
                 "AI score 0-100 dựa trên company size / industry / engagement.",
                 hashtags=["scoring", "ai"]),
            Card("Branch by score", "Phân nhánh theo điểm", "switch",
                 "0-30 = cold drip, 31-70 = warm drip, 71+ = MQL handoff.",
                 hashtags=["routing"]),
            Card("Drip email", "Gửi drip email", "send_email",
                 "Email sequence theo cluster. idempotency_key = lead_id+step.",
                 hashtags=["drip", "nurture"]),
            Card("Handoff to sales", "Chuyển sang sales", "trigger_workflow",
                 "Trigger 'Lead Qualification' workflow khi đạt MQL.",
                 hashtags=["handoff"]),
        ],
    ),
    Template(
        name="Email A/B Test",
        name_vi="A/B test email",
        description="Create variants → split audience → send → measure → declare winner.",
        department_type="marketing", category="experiment", industry_vertical="retail",
        estimated_setup_minutes=6,
        cards=[
            Card("Define hypothesis", "Định nghĩa giả thuyết", "read_form_submission",
                 "Form nhập hypothesis + success metric (CTR / conversion / revenue).",
                 hashtags=["experiment"]),
            Card("Generate variants", "Sinh variants", "generate_narrative",
                 "Sinh A vs B (subject line / CTA / hero copy).",
                 hashtags=["content"]),
            Card("Split audience", "Tách audience 50/50", "split",
                 "Random split với seed cố định cho reproducibility.",
                 hashtags=["split"]),
            Card("Send both variants", "Gửi cả 2", "send_email",
                 "Gửi A tới half, B tới half. Idempotency_key per variant.",
                 hashtags=["send"]),
            Card("Declare winner", "Công bố winner", "publish_insight",
                 "Statistical test (p<0.05) + auto-promote winning variant cho lần sau.",
                 hashtags=["winner", "kpi"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# 5 Sales templates
# ─────────────────────────────────────────────────────────────────────
SALES = [
    Template(
        name="Lead Qualification",
        name_vi="Đánh giá lead",
        description="BANT scoring → routing to AE → first-touch follow-up.",
        department_type="sales", category="qualification", industry_vertical="general",
        estimated_setup_minutes=8,
        cards=[
            Card("Read lead pool", "Đọc lead pool", "read_table",
                 "SELECT từ leads WHERE status='new' AND created_at > now()-interval '24h'.",
                 hashtags=["intake"]),
            Card("BANT score", "Chấm BANT", "call_insight_engine",
                 "AI evaluate Budget/Authority/Need/Timeline → score 0-100.",
                 hashtags=["bant", "scoring"]),
            Card("Route by score", "Phân tuyến", "switch",
                 "70+ = senior AE, 40-70 = mid AE, <40 = nurture pool.",
                 hashtags=["routing"]),
            Card("Create AE task", "Tạo task AE", "create_task",
                 "Task với SLA 4h cho senior AE, 24h cho mid AE.",
                 hashtags=["assignment"]),
            Card("Send first-touch", "Gửi first-touch", "send_email",
                 "Personalized intro email từ AE.",
                 hashtags=["first_touch"]),
        ],
    ),
    Template(
        name="Proposal Approval",
        name_vi="Duyệt proposal",
        description="Draft → margin check → manager approval → send to customer → track signature.",
        department_type="sales", category="approval", industry_vertical="general",
        estimated_setup_minutes=10,
        cards=[
            Card("Read deal data", "Đọc dữ liệu deal", "read_table",
                 "Pull deal + customer info từ CRM.",
                 hashtags=["intake"],
                 required_documents=[{"kind": "csv", "name": "Deal data export", "required": True}]),
            Card("Calculate margin", "Tính margin", "aggregate",
                 "Tính gross_margin = (price - cogs) / price. NUMERIC(5,4).",
                 hashtags=["margin", "kpi"]),
            Card("Manager approval", "Duyệt manager", "approval_gate",
                 "Margin >= 25%: auto-approve. <25%: cần sales manager duyệt.",
                 hashtags=["approval", "gate"]),
            Card("Send proposal", "Gửi proposal", "send_email",
                 "Gửi PDF proposal + signing link (DocuSign).",
                 hashtags=["send", "proposal"]),
            Card("Track signature", "Theo dõi ký", "publish_alert",
                 "Alert khi >48h chưa ký → AE follow up.",
                 hashtags=["sla", "tracking"]),
        ],
    ),
    Template(
        name="Contract Renewal",
        name_vi="Gia hạn hợp đồng",
        description="90-day pre-expiry trigger → health check → renewal proposal → close.",
        department_type="sales", category="renewal", industry_vertical="saas",
        estimated_setup_minutes=12,
        cards=[
            Card("Detect expiry", "Phát hiện sắp hết hạn", "scheduled_trigger",
                 "Cron daily 9am: WHERE end_date BETWEEN now()+60d AND now()+90d.",
                 hashtags=["expiry", "schedule"]),
            Card("Account health check", "Health check", "call_risk_detection",
                 "Risk detection trên 9 adoption signals → green/yellow/red.",
                 hashtags=["health", "ai"]),
            Card("Choose play", "Chọn renewal play", "if_else",
                 "Green = auto-renewal email. Yellow = save-flow. Red = exec-led save.",
                 hashtags=["routing"]),
            Card("Send renewal proposal", "Gửi proposal renewal", "send_email",
                 "Tailored per health tier (renewal price / upsell / save offer).",
                 hashtags=["proposal"]),
            Card("Track close", "Theo dõi đóng deal", "create_task",
                 "Task AE follow up 7 ngày sau gửi proposal.",
                 hashtags=["follow_up"]),
        ],
    ),
    Template(
        name="Discount Approval",
        name_vi="Duyệt giảm giá",
        description="Discount request → tiered approval (depth → role) → notify customer.",
        department_type="sales", category="approval", industry_vertical="retail",
        estimated_setup_minutes=6,
        cards=[
            Card("Receive request", "Nhận yêu cầu", "read_form_submission",
                 "Form từ AE với customer + product + discount_pct + reason.",
                 hashtags=["intake"]),
            Card("Validate ceiling", "Kiểm tra trần", "validate",
                 "Schema validate + business rule: discount_pct must be 0-50.",
                 hashtags=["validation"]),
            Card("Route by depth", "Phân tuyến theo độ sâu", "switch",
                 "<10% AE tự duyệt. 10-25% manager. >25% director.",
                 hashtags=["routing"]),
            Card("Manager approval", "Duyệt", "approval_gate",
                 "Approver_role theo switch. SLA 4h. Timeout = reject.",
                 hashtags=["approval"]),
            Card("Notify customer", "Báo khách", "send_email",
                 "Email approved discount + new pricing.",
                 hashtags=["notify"]),
        ],
    ),
    Template(
        name="Pipeline Review",
        name_vi="Review pipeline",
        description="Weekly pipeline aggregation → forecast → manager review → action items.",
        department_type="sales", category="reporting", industry_vertical="general",
        estimated_setup_minutes=5,
        cards=[
            Card("Pull pipeline", "Lấy pipeline", "read_table",
                 "SELECT từ deals WHERE stage NOT IN ('won','lost').",
                 hashtags=["pipeline"]),
            Card("Aggregate by stage", "Group by stage", "aggregate",
                 "Group by stage + count + sum(amount). NUMERIC(14,4) money.",
                 hashtags=["aggregation"]),
            Card("Forecast close", "Dự báo close", "call_forecasting",
                 "Forecast 30-day close revenue (Prophet method).",
                 hashtags=["forecast", "ai"]),
            Card("Generate narrative", "Sinh narrative", "generate_narrative",
                 "Executive-style summary cho Sales Director Monday meeting.",
                 hashtags=["narrative", "ai"]),
            Card("Publish to dashboard", "Publish dashboard", "display_dashboard",
                 "Render Pipeline tile vào Sales Director dashboard.",
                 hashtags=["dashboard"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# 5 Customer Service templates
# ─────────────────────────────────────────────────────────────────────
CS = [
    Template(
        name="Ticket Triage",
        name_vi="Phân loại ticket",
        description="Inbound ticket → AI classify → priority routing → SLA timer.",
        department_type="customer_service", category="triage", industry_vertical="general",
        estimated_setup_minutes=8,
        cards=[
            Card("Read inbound ticket", "Đọc ticket vào", "read_email",
                 "Đọc email support@... + Zalo chat. Stage 2 mapping.",
                 hashtags=["intake"]),
            Card("Classify category", "Phân loại category", "classify_text",
                 "Multi-label: billing / technical / sales / refund / other.",
                 hashtags=["classification", "ai"]),
            Card("Set priority", "Đặt priority", "switch",
                 "Critical = VIP customer + outage word. High = refund. Mid = default.",
                 hashtags=["priority"]),
            Card("Create ticket", "Tạo ticket", "create_task",
                 "Tạo task trong queue, assign tier-1 agent.",
                 hashtags=["assignment"]),
            Card("Start SLA timer", "Bắt đầu SLA", "publish_alert",
                 "Alert nếu Critical >1h, High >4h, Mid >24h chưa first response.",
                 hashtags=["sla"]),
        ],
    ),
    Template(
        name="SLA Escalation",
        name_vi="Escalate khi quá SLA",
        description="Monitor SLA → escalate to tier-2 → notify manager → re-assign.",
        department_type="customer_service", category="escalation", industry_vertical="general",
        estimated_setup_minutes=5,
        cards=[
            Card("Check SLA breach", "Check vi phạm SLA", "scheduled_trigger",
                 "Mỗi 15 phút: WHERE first_response_at IS NULL AND created_at + sla_window < now().",
                 hashtags=["sla", "schedule"]),
            Card("Filter breaches", "Lọc vi phạm", "filter",
                 "Pure filter trên tickets đã breach.",
                 hashtags=["filter"]),
            Card("Notify tier-2", "Thông báo tier-2", "send_chat_message",
                 "Slack/Telegram notification cho tier-2 + manager.",
                 hashtags=["notify", "escalation"]),
            Card("Re-assign", "Re-assign", "update_record",
                 "UPDATE ticket SET assigned_to = tier_2_pool, escalated_at = now().",
                 hashtags=["assignment"]),
            Card("Log incident", "Log sự cố", "log",
                 "Structured log cho post-mortem analysis.",
                 hashtags=["audit"]),
        ],
    ),
    Template(
        name="NPS Follow-up",
        name_vi="Follow-up NPS",
        description="NPS survey response → categorize → promoter outreach / detractor save.",
        department_type="customer_service", category="feedback", industry_vertical="saas",
        estimated_setup_minutes=7,
        cards=[
            Card("Read NPS response", "Đọc phản hồi NPS", "read_form_submission",
                 "Webhook khi customer trả lời survey (score 0-10).",
                 hashtags=["nps", "intake"]),
            Card("Categorize", "Phân loại", "if_else",
                 "Score 9-10 = promoter. 7-8 = passive. 0-6 = detractor.",
                 hashtags=["routing"]),
            Card("Extract reason", "Trích lý do", "extract_entities",
                 "NER trên comment để hiểu specific reason.",
                 hashtags=["nlp", "ai"]),
            Card("Send response", "Gửi phản hồi", "send_email",
                 "Promoter = thank-you + referral ask. Detractor = CSM call schedule.",
                 hashtags=["follow_up"]),
            Card("Update CRM record", "Cập nhật CRM", "update_record",
                 "UPDATE customers SET last_nps = score, nps_updated_at = now().",
                 hashtags=["crm"]),
        ],
    ),
    Template(
        name="Refund Approval",
        name_vi="Duyệt hoàn tiền",
        description="Refund request → policy check → manager approval (if needed) → process.",
        department_type="customer_service", category="approval", industry_vertical="retail",
        estimated_setup_minutes=6,
        cards=[
            Card("Read refund request", "Đọc yêu cầu hoàn tiền", "read_form_submission",
                 "Form với order_id + reason + amount.",
                 hashtags=["intake"]),
            Card("Validate policy", "Kiểm policy", "validate",
                 "Check policy: <30 days + valid reason category.",
                 hashtags=["policy"]),
            Card("Check threshold", "Kiểm threshold", "if_else",
                 "Amount < 500K VND auto-approve. >= 500K cần manager.",
                 hashtags=["routing"]),
            Card("Manager approval", "Duyệt manager", "approval_gate",
                 "CS manager duyệt với SLA 24h. Timeout = escalate.",
                 hashtags=["approval"]),
            Card("Process refund", "Xử lý hoàn tiền", "call_api",
                 "POST /payment/refund với idempotency_key. Saga compensation = stop_refund.",
                 hashtags=["payment"]),
        ],
    ),
    Template(
        name="Churn Save",
        name_vi="Cứu khách rời",
        description="Cancellation request → reason capture → save offer → exec escalation if VIP.",
        department_type="customer_service", category="retention", industry_vertical="saas",
        estimated_setup_minutes=10,
        cards=[
            Card("Receive cancellation", "Nhận yêu cầu hủy", "read_form_submission",
                 "Cancel form từ Portal Settings.",
                 hashtags=["churn", "intake"]),
            Card("Classify reason", "Phân loại lý do", "classify_text",
                 "Reason cluster: pricing / feature / support / business_change.",
                 hashtags=["classification", "ai"]),
            Card("Check VIP", "Check VIP", "if_else",
                 "LTV > 100M VND → exec-led save. Else → standard save.",
                 hashtags=["routing"]),
            Card("Send save offer", "Gửi save offer", "send_email",
                 "Offer per cluster. VIP gets exec-personalized email.",
                 hashtags=["save"]),
            Card("Track save outcome", "Theo dõi kết quả", "publish_insight",
                 "30-day save rate per cluster. Publish Insight Hub.",
                 hashtags=["kpi"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# 5 Operations (warehouse) templates
# ─────────────────────────────────────────────────────────────────────
OPS = [
    Template(
        name="Inventory Restock",
        name_vi="Nhập kho khi sắp hết",
        description="Daily stock check → low-stock detection → auto-PO → vendor notification.",
        department_type="warehouse", category="restock", industry_vertical="retail",
        estimated_setup_minutes=10,
        cards=[
            Card("Read inventory", "Đọc tồn kho", "read_table",
                 "SELECT từ inventory WHERE stock < reorder_threshold.",
                 hashtags=["intake"]),
            Card("Aggregate by SKU", "Gộp theo SKU", "aggregate",
                 "Group by sku + sum(stock) per warehouse.",
                 hashtags=["aggregation"]),
            Card("Generate PO draft", "Sinh PO draft", "generate_narrative",
                 "Sinh PO text + quantity tự động.",
                 hashtags=["ai"]),
            Card("Manager approval", "Duyệt PO", "approval_gate",
                 "Warehouse manager duyệt nếu total PO > 50M VND.",
                 hashtags=["approval"]),
            Card("Send PO to vendor", "Gửi PO vendor", "send_email",
                 "Email PO PDF tới supplier. idempotency_key = po_number.",
                 hashtags=["procurement"]),
        ],
    ),
    Template(
        name="Supplier Audit",
        name_vi="Audit supplier định kỳ",
        description="Quarterly schedule → pull supplier performance → score → flag underperformers.",
        department_type="warehouse", category="audit", industry_vertical="manufacturing",
        estimated_setup_minutes=8,
        cards=[
            Card("Quarterly trigger", "Trigger hàng quý", "scheduled_trigger",
                 "Cron Q1/Q2/Q3/Q4 first business day.",
                 hashtags=["audit", "schedule"]),
            Card("Pull supplier metrics", "Lấy metric supplier", "read_table",
                 "SELECT từ supplier_metrics: on_time_rate, defect_rate, response_time.",
                 hashtags=["supplier"]),
            Card("Score supplier", "Chấm điểm", "call_insight_engine",
                 "AI scoring 0-100 per supplier.",
                 hashtags=["scoring", "ai"]),
            Card("Flag underperformers", "Đánh dấu yếu", "filter",
                 "Filter score < 60 → review queue.",
                 hashtags=["audit"]),
            Card("Notify procurement", "Báo procurement", "send_chat_message",
                 "Slack tới procurement team với underperformer list.",
                 hashtags=["notify"]),
        ],
    ),
    Template(
        name="Quality Check",
        name_vi="QC nhận hàng",
        description="Goods receipt → sample inspection → defect rate → accept / reject / partial.",
        department_type="warehouse", category="quality", industry_vertical="manufacturing",
        estimated_setup_minutes=7,
        cards=[
            Card("Receive goods", "Nhận hàng", "read_form_submission",
                 "Form QC nhập sample size + defects found.",
                 hashtags=["qc", "intake"]),
            Card("Calculate defect rate", "Tính defect rate", "transform",
                 "rate = defects / sample. NUMERIC(5,4).",
                 hashtags=["calc"]),
            Card("Decide action", "Quyết định", "switch",
                 "Rate <1% accept. 1-5% partial. >5% reject.",
                 hashtags=["decision"]),
            Card("Update inventory", "Cập nhật tồn kho", "save_to_database",
                 "INSERT into inventory với status accepted/quarantined.",
                 hashtags=["inventory"]),
            Card("Notify supplier", "Báo supplier", "send_email",
                 "Email kết quả QC. Reject = return + claim.",
                 hashtags=["supplier"]),
        ],
    ),
    Template(
        name="Shipment Dispatch",
        name_vi="Điều phối giao hàng",
        description="Order ready → carrier selection → label generation → handoff → track.",
        department_type="warehouse", category="logistics", industry_vertical="logistics",
        estimated_setup_minutes=8,
        cards=[
            Card("Read ready orders", "Đọc order sẵn", "read_table",
                 "SELECT WHERE pack_status='ready' AND ship_date <= today.",
                 hashtags=["intake"]),
            Card("Choose carrier", "Chọn carrier", "call_recommendation_engine",
                 "AI gợi ý carrier dựa trên zone + size + cost + SLA.",
                 hashtags=["routing", "ai"]),
            Card("Generate label", "Tạo label", "call_api",
                 "POST /carrier/label với idempotency_key = order_id.",
                 hashtags=["label"]),
            Card("Update order status", "Cập nhật status", "update_record",
                 "UPDATE orders SET status='shipped', tracking_no = ...",
                 hashtags=["status"]),
            Card("Notify customer", "Báo khách", "send_email",
                 "Email tracking link cho khách.",
                 hashtags=["notify"]),
        ],
    ),
    Template(
        name="Warranty Claim",
        name_vi="Xử lý bảo hành",
        description="Claim intake → validate → assign technician → process → close.",
        department_type="warehouse", category="warranty", industry_vertical="retail",
        estimated_setup_minutes=9,
        cards=[
            Card("Receive claim", "Nhận claim", "read_form_submission",
                 "Form claim với serial + issue + photos.",
                 hashtags=["intake"]),
            Card("Validate warranty", "Kiểm bảo hành", "validate",
                 "Schema validate + check purchase_date + warranty_period.",
                 hashtags=["validation"]),
            Card("Assign technician", "Phân kỹ thuật viên", "create_task",
                 "Task tới technician pool. SLA 48h.",
                 hashtags=["assignment"]),
            Card("Track resolution", "Theo dõi xử lý", "publish_alert",
                 "Alert manager nếu >SLA chưa resolve.",
                 hashtags=["sla"]),
            Card("Close claim", "Đóng claim", "send_email",
                 "Email khách với resolution + survey link.",
                 hashtags=["close"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# 5 Finance templates
# ─────────────────────────────────────────────────────────────────────
FINANCE = [
    Template(
        name="Invoice Approval",
        name_vi="Duyệt hóa đơn",
        description="Invoice intake → 3-way match → tiered approval → payment scheduling.",
        department_type="finance", category="approval", industry_vertical="general",
        estimated_setup_minutes=10,
        cards=[
            Card("Read incoming invoice", "Đọc hóa đơn vào", "read_email",
                 "Đọc hóa đơn từ AP mailbox + PDF extraction (Stage 6).",
                 hashtags=["intake", "ap"]),
            Card("3-way match", "3-way match", "join",
                 "Join invoice + PO + GR (goods receipt) theo PO number.",
                 hashtags=["match"]),
            Card("Validate amounts", "Kiểm số tiền", "validate",
                 "Validate invoice_amount = po_amount ± 5% tolerance.",
                 hashtags=["validation"]),
            Card("Tiered approval", "Duyệt theo tier", "approval_gate",
                 "<10M tự duyệt. 10-100M finance manager. >100M CFO.",
                 hashtags=["approval"]),
            Card("Schedule payment", "Lên lịch thanh toán", "create_task",
                 "Tạo payment task với due_date = invoice_date + net_terms.",
                 hashtags=["payment"]),
        ],
    ),
    Template(
        name="Expense Reimbursement",
        name_vi="Hoàn ứng chi phí",
        description="Submit expense → policy check → manager approval → reimburse.",
        department_type="finance", category="approval", industry_vertical="general",
        estimated_setup_minutes=6,
        cards=[
            Card("Submit expense", "Nộp expense", "read_form_submission",
                 "Form expense với category + amount + receipt attachment.",
                 hashtags=["intake"]),
            Card("Policy check", "Kiểm policy", "validate",
                 "Per-category caps + receipt required validation.",
                 hashtags=["policy"]),
            Card("Classify category", "Phân loại", "classify_text",
                 "AI classify khi user nhập tự do (travel/meal/supplies/other).",
                 hashtags=["ai"]),
            Card("Manager approval", "Duyệt manager", "approval_gate",
                 "Auto <500K. Manager 500K-5M. Director >5M.",
                 hashtags=["approval"]),
            Card("Reimburse", "Chuyển tiền", "call_api",
                 "POST /payroll/reimburse. idempotency_key = expense_id.",
                 hashtags=["payment"]),
        ],
    ),
    Template(
        name="Monthly Close",
        name_vi="Đóng sổ tháng",
        description="Trigger month-end → aggregate ledger → reconcile → publish report.",
        department_type="finance", category="reporting", industry_vertical="general",
        estimated_setup_minutes=15,
        cards=[
            Card("Month-end trigger", "Trigger cuối tháng", "scheduled_trigger",
                 "Cron last business day of month at 18:00 ICT.",
                 hashtags=["schedule"]),
            Card("Aggregate GL", "Gộp GL", "aggregate",
                 "Sum theo account + cost_center + month. NUMERIC(14,4).",
                 hashtags=["accounting"]),
            Card("Reconcile bank", "Đối chiếu ngân hàng", "join",
                 "Join GL với bank_statements. Flag mismatches.",
                 hashtags=["reconcile"]),
            Card("Generate close report", "Sinh báo cáo close", "generate_report",
                 "PDF với P&L + Balance Sheet + Cash Flow.",
                 hashtags=["report"]),
            Card("Publish to CFO", "Publish CFO", "send_email",
                 "Email CFO + Board với report attached.",
                 hashtags=["publish"]),
        ],
    ),
    Template(
        name="Vendor Payment",
        name_vi="Thanh toán nhà cung cấp",
        description="Payment due → batch invoices → CFO approval → process → reconcile.",
        department_type="finance", category="payment", industry_vertical="general",
        estimated_setup_minutes=10,
        cards=[
            Card("Pull due payments", "Lấy payment đến hạn", "read_table",
                 "WHERE due_date BETWEEN today AND today+7d AND status='approved'.",
                 hashtags=["intake"]),
            Card("Batch by vendor", "Gộp theo vendor", "aggregate",
                 "Group by vendor + sum(amount) → single batch payment per vendor.",
                 hashtags=["batch"]),
            Card("CFO batch approval", "Duyệt CFO batch", "approval_gate",
                 "Single approval cho cả batch để giảm friction.",
                 hashtags=["approval"]),
            Card("Process payments", "Xử lý payment", "call_api",
                 "POST /bank/payment-batch. Saga compensation = void_batch.",
                 hashtags=["payment"]),
            Card("Update AP ledger", "Cập nhật sổ AP", "save_to_database",
                 "INSERT vào ap_payments + UPDATE invoices SET paid_at = now().",
                 hashtags=["ledger"]),
        ],
    ),
    Template(
        name="Budget Approval",
        name_vi="Duyệt ngân sách",
        description="Annual budget submission → finance review → board approval → publish.",
        department_type="finance", category="approval", industry_vertical="general",
        estimated_setup_minutes=12,
        cards=[
            Card("Submit budget", "Nộp ngân sách", "read_form_submission",
                 "Form từ department heads với line items + justification.",
                 hashtags=["intake", "annual"]),
            Card("Validate format", "Kiểm format", "validate",
                 "Schema validate + sum check + variance vs prior year.",
                 hashtags=["validation"]),
            Card("Finance review", "Review finance", "approval_gate",
                 "Finance Director review + comments.",
                 hashtags=["review"]),
            Card("Board approval", "Duyệt board", "approval_gate",
                 "Board vote (anh + co-founders) với SLA 14 ngày.",
                 hashtags=["approval", "board"]),
            Card("Publish approved budget", "Publish budget", "publish_insight",
                 "Publish vào Insight Hub. Department heads notified.",
                 hashtags=["publish"]),
        ],
    ),
]


ALL_TEMPLATES: List[Template] = MARKETING + SALES + CS + OPS + FINANCE
assert len(ALL_TEMPLATES) == 25, f"Expected 25 templates, got {len(ALL_TEMPLATES)}"


def card_to_node_dict(card: Card, idx: int) -> dict:
    return {
        "client_id":                 f"n{idx + 1}",
        "title":                     card.title,
        "title_vi":                  card.title_vi,
        "node_type_catalog_key":     card.node_type_key,
        "note":                      card.note,
        "hashtags":                  card.hashtags,
        "required_document_types":   card.required_documents,
        "sequence_order":            idx + 1,
        "position_x":                100 + (idx * 220),
        "position_y":                100,
    }


def template_to_definition(t: Template) -> dict:
    nodes = [card_to_node_dict(c, i) for i, c in enumerate(t.cards)]
    edges = [
        {
            "source_client_id": f"n{i + 1}",
            "target_client_id": f"n{i + 2}",
            "label":            "next",
        }
        for i in range(len(t.cards) - 1)
    ]
    return {"nodes": nodes, "edges": edges}


def render_sql() -> str:
    lines: List[str] = []
    lines.append("-- =====================================================================")
    lines.append("-- 069_production_templates_seed.sql")
    lines.append("--")
    lines.append("-- P2-S15 D2 — 25 production templates seed (5 per vertical × 5 verticals).")
    lines.append("--")
    lines.append("-- Marketing / Sales / Customer Service / Warehouse (ops) / Finance.")
    lines.append("-- Each template uses node_type_catalog_key from mig 068.")
    lines.append("-- industry_vertical column added for AI-HSC-016 cohort filter.")
    lines.append("--")
    lines.append("-- AUTO-GENERATED by scripts/generate_production_templates_p2_s15.py")
    lines.append("-- Edit the script + re-run to regenerate. Both files committed.")
    lines.append("-- =====================================================================")
    lines.append("")
    lines.append("BEGIN;")
    lines.append("")
    lines.append("-- Add industry_vertical column (idempotent ADD)")
    lines.append("ALTER TABLE workflow_templates")
    lines.append("    ADD COLUMN IF NOT EXISTS industry_vertical VARCHAR(32);")
    lines.append("")
    lines.append("ALTER TABLE workflow_templates")
    lines.append("    DROP CONSTRAINT IF EXISTS chk_industry_vertical;")
    lines.append("ALTER TABLE workflow_templates")
    lines.append("    ADD CONSTRAINT chk_industry_vertical CHECK (")
    lines.append("        industry_vertical IS NULL OR industry_vertical IN (")
    lines.append("            'general', 'retail', 'manufacturing', 'fintech',")
    lines.append("            'logistics', 'healthcare', 'fmcg', 'saas'")
    lines.append("        )")
    lines.append("    );")
    lines.append("")
    lines.append("CREATE INDEX IF NOT EXISTS idx_workflow_templates_industry")
    lines.append("    ON workflow_templates(industry_vertical)")
    lines.append("    WHERE is_active = TRUE;")
    lines.append("")
    lines.append("-- Seed 25 production templates")
    for t in ALL_TEMPLATES:
        definition_json = json.dumps(template_to_definition(t), ensure_ascii=False)
        # Escape single quotes for SQL string literal
        definition_sql = definition_json.replace("'", "''")
        name_sql = t.name.replace("'", "''")
        name_vi_sql = t.name_vi.replace("'", "''")
        desc_sql = t.description.replace("'", "''")
        lines.append("INSERT INTO workflow_templates (")
        lines.append("    display_name, display_name_vi, description,")
        lines.append("    department_type, category, industry_vertical,")
        lines.append("    workflow_definition, estimated_setup_minutes")
        lines.append(") VALUES (")
        lines.append(f"    '{name_sql}',")
        lines.append(f"    '{name_vi_sql}',")
        lines.append(f"    '{desc_sql}',")
        lines.append(f"    '{t.department_type}', '{t.category}', '{t.industry_vertical}',")
        lines.append(f"    '{definition_sql}'::jsonb,")
        lines.append(f"    {t.estimated_setup_minutes}")
        lines.append(");")
        lines.append("")
    lines.append("COMMIT;")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    out_path = repo_root / "infrastructure" / "postgres" / "migrations" / "069_production_templates_seed.sql"
    sql = render_sql()
    out_path.write_text(sql, encoding="utf-8")
    print(f"wrote {out_path}")
    print(f"  - {len(ALL_TEMPLATES)} templates × 5 cards each")
    print(f"  - {len(ALL_TEMPLATES) * 5} total node instances")
    print(f"  - {sum(len(t.cards) - 1 for t in ALL_TEMPLATES)} total edges")


if __name__ == "__main__":
    main()
