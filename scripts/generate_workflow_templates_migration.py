#!/usr/bin/env python3
"""Generate `054_workflow_templates_seed.sql` from a structured template catalog.

Per anh's directive 2026-05-15:
  "Một phòng ban có 3 workflow (c, d, e). Mỗi workflow 5-7 bước (card)."

The catalog below ships 18 Phase-1 templates (3 per dept × 6 dept_types).
Each template has 5 cards + 4 sequential edges + per-card hashtags +
required_document_types. Phase 2 can expand to docx Phần 17.1's 30 total.

Run from repo root:
    python scripts/generate_workflow_templates_migration.py
    # writes/updates infrastructure/postgres/migrations/054_workflow_templates_seed.sql

The generated SQL is committed to git so Flyway picks it up; the script
itself is committed too so future template adjustments stay reviewable
(edit catalog → re-run → commit both).
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
    note: str
    hashtags: List[str] = field(default_factory=list)
    required_documents: List[dict] = field(default_factory=list)
    # Optional pre-cooked mapping for the demo; FE can leave blank.
    expected_doc_kind: Optional[str] = None


@dataclass
class Template:
    name: str
    name_vi: str
    description: str
    department_type: str
    category: str
    estimated_setup_minutes: int
    cards: List[Card]


# ─────────────────────────────────────────────────────────────────────
# Marketing (3 templates)
# ─────────────────────────────────────────────────────────────────────

MARKETING_TEMPLATES = [
    Template(
        name="Email Campaign with Segmentation",
        name_vi="Chiến dịch email theo phân khúc",
        description="Phân khúc khách hàng → soạn nội dung → gửi → đo ROAS.",
        department_type="marketing",
        category="campaign",
        estimated_setup_minutes=10,
        cards=[
            Card("Define audience", "Xác định tệp khách hàng",
                 "Chọn segment + filter theo LTV / acquisition channel.",
                 hashtags=["segmentation", "audience"],
                 required_documents=[
                     {"kind": "csv", "name": "Customer segment list", "required": True}
                 ]),
            Card("Draft content", "Soạn nội dung",
                 "Subject line + body + CTA. Bản tiếng Việt + tiếng Anh.",
                 hashtags=["content", "creative"],
                 required_documents=[
                     {"kind": "docx", "name": "Email template", "required": True},
                     {"kind": "image", "name": "Hero asset", "required": False},
                 ]),
            Card("Approval gate", "Duyệt nội dung",
                 "Manager review trước khi send.",
                 hashtags=["approval"],
                 required_documents=[]),
            Card("Send + track", "Gửi và theo dõi",
                 "Gửi qua ESP. Track open/click/bounce.",
                 hashtags=["send", "tracking"],
                 required_documents=[
                     {"kind": "csv", "name": "Send log", "required": True}
                 ]),
            Card("Measure ROAS", "Đo ROAS",
                 "Doanh thu attribute từ campaign / chi phí.",
                 hashtags=["roas", "report"],
                 required_documents=[
                     {"kind": "csv", "name": "Revenue attribution", "required": True}
                 ]),
        ],
    ),
    Template(
        name="Customer Onboarding Sequence",
        name_vi="Chuỗi onboarding khách hàng mới",
        description="Welcome → tutorial → activation check → first-value milestone.",
        department_type="marketing",
        category="onboarding",
        estimated_setup_minutes=8,
        cards=[
            Card("Capture new signup", "Tiếp nhận đăng ký mới",
                 "Webhook từ form / signup.",
                 hashtags=["signup", "new_customer"],
                 required_documents=[
                     {"kind": "csv", "name": "Signup log", "required": True}
                 ]),
            Card("Send welcome email", "Gửi email chào mừng",
                 "Trong 5 phút sau signup.",
                 hashtags=["welcome"]),
            Card("Day-3 tutorial nudge", "Nhắc hướng dẫn ngày 3",
                 "Nếu chưa activate trong 72h.",
                 hashtags=["tutorial", "nudge"]),
            Card("Activation check", "Kiểm tra activate",
                 "User đã dùng feature core chưa?",
                 hashtags=["activation"]),
            Card("First-value milestone", "Mốc giá trị đầu tiên",
                 "Đánh dấu retention rủi ro thấp.",
                 hashtags=["milestone", "retention"]),
        ],
    ),
    Template(
        name="Abandoned Cart Recovery",
        name_vi="Phục hồi giỏ hàng bỏ rơi",
        description="Detect cart abandon → 24h reminder → 72h discount → 7d give-up.",
        department_type="marketing",
        category="recovery",
        estimated_setup_minutes=6,
        cards=[
            Card("Detect abandon", "Phát hiện bỏ giỏ",
                 "Cart không checkout sau 60 phút.",
                 hashtags=["abandon", "trigger"],
                 required_documents=[
                     {"kind": "csv", "name": "Cart event log", "required": True}
                 ]),
            Card("24h reminder email", "Email nhắc 24h",
                 "Không có CTA giảm giá.",
                 hashtags=["reminder"]),
            Card("72h discount offer", "Ưu đãi 72h",
                 "Coupon 10% còn hạn 48h.",
                 hashtags=["discount", "coupon"]),
            Card("7d last call", "Lần nhắc cuối 7 ngày",
                 "Free shipping coupon.",
                 hashtags=["last_call"]),
            Card("Conversion report", "Báo cáo chuyển đổi",
                 "Tỷ lệ thu hồi giỏ + doanh thu.",
                 hashtags=["roas", "report"],
                 required_documents=[
                     {"kind": "csv", "name": "Recovery results", "required": True}
                 ]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Sales (3 templates)
# ─────────────────────────────────────────────────────────────────────

SALES_TEMPLATES = [
    Template(
        name="Lead Qualification Workflow",
        name_vi="Quy trình thẩm định lead",
        description="Lead intake → BANT scoring → SQL/MQL split → handoff.",
        department_type="sales",
        category="pipeline",
        estimated_setup_minutes=12,
        cards=[
            Card("Lead intake", "Tiếp nhận lead",
                 "Nhận lead từ web form, Zalo OA, Facebook.",
                 hashtags=["prospect_data", "intake"],
                 required_documents=[
                     {"kind": "csv", "name": "Lead list", "required": True},
                     {"kind": "csv", "name": "Source attribution", "required": False},
                 ]),
            Card("BANT scoring", "Chấm điểm BANT",
                 "Budget / Authority / Need / Timeline. AI gợi ý điểm.",
                 hashtags=["scoring", "bant"]),
            Card("SQL/MQL split", "Phân nhóm SQL/MQL",
                 "Điểm ≥ 80 → SQL; 40-79 → MQL.",
                 hashtags=["sql", "mql"]),
            Card("Sales rep handoff", "Bàn giao cho rep",
                 "Round-robin theo territory.",
                 hashtags=["handoff", "rep"]),
            Card("Conversion track", "Theo dõi chuyển đổi",
                 "Lead → opportunity → deal won.",
                 hashtags=["conversion", "metrics"],
                 required_documents=[
                     {"kind": "csv", "name": "Pipeline snapshot", "required": True}
                 ]),
        ],
    ),
    Template(
        name="Quote-to-Cash",
        name_vi="Báo giá đến thanh toán",
        description="Quote draft → approval → contract → invoice → payment.",
        department_type="sales",
        category="pipeline",
        estimated_setup_minutes=15,
        cards=[
            Card("Draft quote", "Soạn báo giá",
                 "Pricing tier + discount tùy quy mô.",
                 hashtags=["quote", "pricing"],
                 required_documents=[
                     {"kind": "docx", "name": "Quote template", "required": True}
                 ]),
            Card("Manager approval", "Duyệt manager",
                 "Discount > 15% cần duyệt.",
                 hashtags=["approval"]),
            Card("Contract sign", "Ký hợp đồng",
                 "E-sign + counter-sign.",
                 hashtags=["contract", "signature"],
                 required_documents=[
                     {"kind": "pdf", "name": "Signed contract", "required": True}
                 ]),
            Card("Invoice issued", "Xuất hóa đơn",
                 "Đẩy sang Finance.",
                 hashtags=["invoice"]),
            Card("Payment received", "Nhận thanh toán",
                 "Confirm trong 30 ngày.",
                 hashtags=["payment", "ar"],
                 required_documents=[
                     {"kind": "csv", "name": "Payment confirmation", "required": True}
                 ]),
        ],
    ),
    Template(
        name="Deal Risk Assessment",
        name_vi="Đánh giá rủi ro deal",
        description="Pipeline freeze → AI risk score → save plan → close-out.",
        department_type="sales",
        category="risk",
        estimated_setup_minutes=10,
        cards=[
            Card("Pipeline snapshot", "Chụp pipeline",
                 "Lấy deal đang stall > 30 ngày.",
                 hashtags=["pipeline", "stale"],
                 required_documents=[
                     {"kind": "csv", "name": "Pipeline export", "required": True}
                 ]),
            Card("AI risk scoring", "Chấm rủi ro AI",
                 "AI suggest deal risk score 0-100.",
                 hashtags=["ai_score", "risk"]),
            Card("Save plan draft", "Lập kế hoạch cứu",
                 "Rep + manager co-design.",
                 hashtags=["save_plan"]),
            Card("Customer call", "Gọi khách",
                 "Hiểu blocker, propose path.",
                 hashtags=["call"]),
            Card("Close or lose", "Đóng deal hay bỏ",
                 "Quyết định cuối trong 14 ngày.",
                 hashtags=["close", "decision"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Customer Service (3 templates)
# ─────────────────────────────────────────────────────────────────────

CS_TEMPLATES = [
    Template(
        name="Complaint Resolution",
        name_vi="Giải quyết khiếu nại",
        description="Ticket → triage → investigate → resolve → CSAT survey.",
        department_type="customer_service",
        category="ticket",
        estimated_setup_minutes=8,
        cards=[
            Card("Ticket intake", "Tiếp nhận ticket",
                 "Từ Zalo / email / hotline.",
                 hashtags=["intake", "ticket"],
                 required_documents=[
                     {"kind": "csv", "name": "Ticket log", "required": True}
                 ]),
            Card("Priority triage", "Phân loại độ ưu tiên",
                 "Critical / High / Normal / Low.",
                 hashtags=["triage", "priority"]),
            Card("Investigate root cause", "Tìm nguyên nhân",
                 "Agent assign + investigate.",
                 hashtags=["investigate"],
                 required_documents=[
                     {"kind": "pdf", "name": "Evidence attachments", "required": False}
                 ]),
            Card("Resolve + reply", "Xử lý + phản hồi",
                 "Customer reply + close ticket.",
                 hashtags=["resolve", "reply"]),
            Card("CSAT survey", "Khảo sát CSAT",
                 "Gửi survey sau 24h close.",
                 hashtags=["csat", "survey"],
                 required_documents=[
                     {"kind": "csv", "name": "CSAT responses", "required": True}
                 ]),
        ],
    ),
    Template(
        name="Refund Request",
        name_vi="Yêu cầu hoàn tiền",
        description="Refund intake → policy check → approval → process → confirm.",
        department_type="customer_service",
        category="refund",
        estimated_setup_minutes=6,
        cards=[
            Card("Refund intake", "Tiếp nhận yêu cầu",
                 "Form hoặc ticket có tag #refund.",
                 hashtags=["refund", "intake"],
                 required_documents=[
                     {"kind": "csv", "name": "Refund request log", "required": True}
                 ]),
            Card("Policy check", "Kiểm tra chính sách",
                 "Trong thời hạn 14 ngày? Lý do hợp lệ?",
                 hashtags=["policy"]),
            Card("Manager approve", "Manager duyệt",
                 "Trên 5M VND cần duyệt.",
                 hashtags=["approval"]),
            Card("Process refund", "Xử lý hoàn tiền",
                 "Đẩy sang Finance.",
                 hashtags=["process"]),
            Card("Confirm to customer", "Báo khách",
                 "Email + SMS xác nhận.",
                 hashtags=["confirm"]),
        ],
    ),
    Template(
        name="Escalation Path",
        name_vi="Đường leo thang",
        description="Frontline → supervisor → manager → director, theo SLA.",
        department_type="customer_service",
        category="escalation",
        estimated_setup_minutes=5,
        cards=[
            Card("Frontline reply", "Frontline trả lời",
                 "Trong 15 phút làm việc.",
                 hashtags=["frontline", "sla_15m"]),
            Card("Supervisor takeover", "Supervisor tiếp nhận",
                 "Nếu frontline không xử lý trong 1h.",
                 hashtags=["supervisor", "sla_1h"]),
            Card("Manager engage", "Manager vào việc",
                 "Critical / VIP customer.",
                 hashtags=["manager"]),
            Card("Director escalation", "Director can thiệp",
                 "Chỉ khi tổn hại doanh thu.",
                 hashtags=["director", "revenue_risk"]),
            Card("Post-mortem", "Hậu kiểm",
                 "Lessons learned + process update.",
                 hashtags=["postmortem"],
                 required_documents=[
                     {"kind": "docx", "name": "Post-mortem doc", "required": True}
                 ]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Warehouse (3 templates)
# ─────────────────────────────────────────────────────────────────────

WAREHOUSE_TEMPLATES = [
    Template(
        name="Inventory Reorder Trigger",
        name_vi="Tự động đặt lại hàng",
        description="Stock level check → reorder point → PO draft → supplier send.",
        department_type="warehouse",
        category="reorder",
        estimated_setup_minutes=8,
        cards=[
            Card("Stock level scan", "Quét tồn kho",
                 "Daily scan + reorder point.",
                 hashtags=["stock", "scan"],
                 required_documents=[
                     {"kind": "csv", "name": "Stock level export", "required": True}
                 ]),
            Card("Calculate reorder qty", "Tính lượng đặt",
                 "EOQ + safety stock.",
                 hashtags=["eoq"]),
            Card("Draft PO", "Soạn đơn đặt hàng",
                 "Auto-fill supplier + qty.",
                 hashtags=["po", "draft"],
                 required_documents=[
                     {"kind": "docx", "name": "PO template", "required": True}
                 ]),
            Card("Manager approve", "Manager duyệt",
                 "PO > 50M VND cần duyệt.",
                 hashtags=["approval"]),
            Card("Send to supplier", "Gửi nhà cung cấp",
                 "Email + portal.",
                 hashtags=["supplier", "send"]),
        ],
    ),
    Template(
        name="Stock-out Risk Alert",
        name_vi="Cảnh báo nguy cơ hết hàng",
        description="Velocity calc → predicted stock-out date → alert manager.",
        department_type="warehouse",
        category="alert",
        estimated_setup_minutes=5,
        cards=[
            Card("Sales velocity calc", "Tính tốc độ bán",
                 "Trailing 30 ngày.",
                 hashtags=["velocity"]),
            Card("Predict stock-out date", "Dự đoán hết hàng",
                 "Days-of-stock < 7 → alert.",
                 hashtags=["predict", "ai"]),
            Card("Alert manager", "Cảnh báo manager",
                 "Zalo / email + dashboard.",
                 hashtags=["alert"]),
            Card("Emergency reorder", "Đặt khẩn",
                 "Bypass normal reorder.",
                 hashtags=["emergency"]),
            Card("Track recovery", "Theo dõi hồi phục",
                 "Tới khi tồn kho an toàn.",
                 hashtags=["recovery"]),
        ],
    ),
    Template(
        name="Quality Issue Resolution",
        name_vi="Xử lý vấn đề chất lượng",
        description="Defect report → root cause → supplier feedback → process update.",
        department_type="warehouse",
        category="quality",
        estimated_setup_minutes=7,
        cards=[
            Card("Defect intake", "Tiếp nhận khiếu nại lỗi",
                 "Từ CS hoặc QC.",
                 hashtags=["defect", "intake"],
                 required_documents=[
                     {"kind": "csv", "name": "Defect log", "required": True}
                 ]),
            Card("Root cause analysis", "Phân tích nguyên nhân gốc",
                 "5-Why + Fishbone.",
                 hashtags=["rca"]),
            Card("Supplier feedback", "Phản hồi nhà cung cấp",
                 "SLA penalty nếu lỗi từ supplier.",
                 hashtags=["supplier", "feedback"]),
            Card("Process update", "Cập nhật quy trình",
                 "QC checklist + training.",
                 hashtags=["process", "update"]),
            Card("Effectiveness check", "Kiểm chứng hiệu quả",
                 "Defect rate sau 30 ngày.",
                 hashtags=["check", "metric"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# HR (3 templates)
# ─────────────────────────────────────────────────────────────────────

HR_TEMPLATES = [
    Template(
        name="Hiring Funnel",
        name_vi="Phễu tuyển dụng",
        description="JD post → screening → interview → offer → accept.",
        department_type="hr",
        category="hiring",
        estimated_setup_minutes=12,
        cards=[
            Card("JD post", "Đăng tin tuyển",
                 "LinkedIn + TopCV + internal referral.",
                 hashtags=["jd", "post"],
                 required_documents=[
                     {"kind": "docx", "name": "JD template", "required": True}
                 ]),
            Card("CV screening", "Sàng lọc CV",
                 "ATS auto + recruiter manual.",
                 hashtags=["screening", "ats"],
                 required_documents=[
                     {"kind": "csv", "name": "CV inventory", "required": True}
                 ]),
            Card("Interview rounds", "Phỏng vấn",
                 "Screen + tech + culture.",
                 hashtags=["interview"]),
            Card("Offer + negotiation", "Đề xuất + đàm phán",
                 "Salary band + benefits.",
                 hashtags=["offer", "negotiation"]),
            Card("Accept + start date", "Nhận việc + ngày bắt đầu",
                 "Contract sign + onboarding prep.",
                 hashtags=["accept", "onboard"],
                 required_documents=[
                     {"kind": "pdf", "name": "Signed offer", "required": True}
                 ]),
        ],
    ),
    Template(
        name="Onboarding New Employee",
        name_vi="Onboard nhân viên mới",
        description="Day-1 setup → training → 30/60/90 review.",
        department_type="hr",
        category="onboarding",
        estimated_setup_minutes=10,
        cards=[
            Card("Day-1 setup", "Day 1 setup",
                 "Laptop, accounts, badge.",
                 hashtags=["day_1", "setup"]),
            Card("Buddy assigned", "Gán buddy",
                 "Senior cùng team.",
                 hashtags=["buddy"]),
            Card("Training program", "Chương trình đào tạo",
                 "Tech + culture + compliance.",
                 hashtags=["training"]),
            Card("30-day review", "Đánh giá 30 ngày",
                 "Manager + buddy 1-on-1.",
                 hashtags=["review", "30d"]),
            Card("90-day milestone", "Mốc 90 ngày",
                 "Pass probation hoặc gia hạn.",
                 hashtags=["milestone", "90d"],
                 required_documents=[
                     {"kind": "docx", "name": "Probation report", "required": True}
                 ]),
        ],
    ),
    Template(
        name="Exit Interview",
        name_vi="Phỏng vấn nghỉ việc",
        description="Notice → handover → exit interview → final pay.",
        department_type="hr",
        category="exit",
        estimated_setup_minutes=6,
        cards=[
            Card("Resignation notice", "Đơn xin nghỉ",
                 "Văn bản chính thức.",
                 hashtags=["resignation"],
                 required_documents=[
                     {"kind": "pdf", "name": "Resignation letter", "required": True}
                 ]),
            Card("Handover plan", "Bàn giao",
                 "Knowledge + open tasks.",
                 hashtags=["handover"]),
            Card("Exit interview", "Phỏng vấn nghỉ",
                 "Anonymous survey + 1-on-1.",
                 hashtags=["interview", "exit"]),
            Card("Final pay calculation", "Tính lương cuối",
                 "Salary + unused PTO + severance.",
                 hashtags=["payroll", "final"]),
            Card("Access revocation", "Thu hồi quyền",
                 "Last day = revoke all access.",
                 hashtags=["security", "offboard"]),
        ],
    ),
]


# ─────────────────────────────────────────────────────────────────────
# Finance (3 templates)
# ─────────────────────────────────────────────────────────────────────

FINANCE_TEMPLATES = [
    Template(
        name="Invoice Processing",
        name_vi="Xử lý hóa đơn",
        description="Invoice receive → match PO → approval → payment schedule.",
        department_type="finance",
        category="ap",
        estimated_setup_minutes=8,
        cards=[
            Card("Invoice receive", "Nhận hóa đơn",
                 "Email/portal/scan.",
                 hashtags=["invoice", "intake"],
                 required_documents=[
                     {"kind": "pdf", "name": "Invoice PDF", "required": True}
                 ]),
            Card("3-way match", "Khớp 3 chiều",
                 "PO + receipt + invoice.",
                 hashtags=["match", "3way"]),
            Card("Manager approval", "Duyệt manager",
                 "Trên 20M VND cần duyệt.",
                 hashtags=["approval"]),
            Card("Payment schedule", "Lên lịch thanh toán",
                 "Net 30 / net 45.",
                 hashtags=["schedule", "ap"]),
            Card("Payment execute", "Thực hiện thanh toán",
                 "Bank transfer + ghi sổ.",
                 hashtags=["payment", "execute"]),
        ],
    ),
    Template(
        name="AR Collection Reminder",
        name_vi="Nhắc nợ phải thu",
        description="Aging → reminder schedule → escalation → write-off.",
        department_type="finance",
        category="ar",
        estimated_setup_minutes=6,
        cards=[
            Card("AR aging snapshot", "Chụp tuổi nợ",
                 "30 / 60 / 90+ buckets.",
                 hashtags=["ar", "aging"],
                 required_documents=[
                     {"kind": "csv", "name": "AR aging export", "required": True}
                 ]),
            Card("Day-7 polite reminder", "Nhắc nhẹ ngày 7",
                 "Email tự động.",
                 hashtags=["reminder", "7d"]),
            Card("Day-30 firm reminder", "Nhắc cứng ngày 30",
                 "Email + phone call.",
                 hashtags=["reminder", "30d"]),
            Card("Day-60 escalation", "Leo thang ngày 60",
                 "Sales manager + customer success.",
                 hashtags=["escalation", "60d"]),
            Card("Day-90 write-off review", "Xem xóa nợ ngày 90",
                 "Manager + Finance approve.",
                 hashtags=["writeoff", "90d"]),
        ],
    ),
    Template(
        name="Cash Flow Forecasting",
        name_vi="Dự báo dòng tiền",
        description="Inflow estimate → outflow schedule → variance report.",
        department_type="finance",
        category="forecast",
        estimated_setup_minutes=10,
        cards=[
            Card("Inflow forecast", "Dự báo dòng vào",
                 "AR + sales pipeline.",
                 hashtags=["inflow", "forecast"],
                 required_documents=[
                     {"kind": "csv", "name": "Pipeline + AR export", "required": True}
                 ]),
            Card("Outflow schedule", "Lịch dòng ra",
                 "Payroll + AP + capex.",
                 hashtags=["outflow"],
                 required_documents=[
                     {"kind": "csv", "name": "Payroll + AP schedule", "required": True}
                 ]),
            Card("Net cash projection", "Dự báo dòng ròng",
                 "Net + runway tháng.",
                 hashtags=["net", "runway"]),
            Card("Variance review", "Xem chênh lệch",
                 "Actual vs forecast tháng trước.",
                 hashtags=["variance"]),
            Card("Report to CFO", "Báo cáo CFO",
                 "Slide + Q&A.",
                 hashtags=["report", "cfo"]),
        ],
    ),
]


ALL_TEMPLATES = (
    MARKETING_TEMPLATES + SALES_TEMPLATES + CS_TEMPLATES
    + WAREHOUSE_TEMPLATES + HR_TEMPLATES + FINANCE_TEMPLATES
)


# ─────────────────────────────────────────────────────────────────────
# SQL emit
# ─────────────────────────────────────────────────────────────────────


def _esc(value: str) -> str:
    """Single-quote-escape for SQL string literal."""
    return value.replace("'", "''")


def _emit_jsonb(obj) -> str:
    """JSONB literal — single-line, double-quotes preserved, single-quote-safe."""
    return _esc(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))


def template_to_definition(t: Template) -> dict:
    """Convert Template dataclass → workflow_definition JSONB shape.

    `client_id` is a per-template stable id (n1, n2, ...) referenced by
    edges. The CRUD clone-from-template endpoint replaces with real UUIDs.
    """
    nodes = []
    for i, card in enumerate(t.cards, start=1):
        nodes.append({
            "client_id": f"n{i}",
            "node_type": "step",
            "category": "data_input",
            "side_effect_class": "read_only",
            "title": card.title,
            "title_vi": card.title_vi,
            "note": card.note,
            "hashtags": card.hashtags,
            "required_document_types": card.required_documents,
            "sequence_order": i,
            "position_x": 100 + (i - 1) * 220,
            "position_y": 100,
        })
    edges = []
    for i in range(len(t.cards) - 1):
        edges.append({
            "source_client_id": f"n{i+1}",
            "target_client_id": f"n{i+2}",
            "label": "next",
        })
    return {"nodes": nodes, "edges": edges}


def emit_sql() -> str:
    lines = [
        "-- 054_workflow_templates_seed.sql — P15-S11 Tuần 8 Step 5 (workflow pivot).",
        "--",
        "-- AUTO-GENERATED by scripts/generate_workflow_templates_migration.py",
        "-- DO NOT EDIT BY HAND — edit the catalog in the Python script + rerun.",
        "--",
        "-- 18 templates × ~5 cards = 90 cards across 6 dept_types. Phase 2 will",
        "-- expand to docx Phần 17.1's 30 templates.",
        "",
        "INSERT INTO workflow_templates",
        "    (display_name, display_name_vi, description, department_type, category, workflow_definition, estimated_setup_minutes)",
        "VALUES",
    ]
    rows = []
    for t in ALL_TEMPLATES:
        wf_def = template_to_definition(t)
        rows.append(
            f"    ('{_esc(t.name)}', '{_esc(t.name_vi)}', '{_esc(t.description)}', "
            f"'{t.department_type}', '{_esc(t.category)}', '{_emit_jsonb(wf_def)}'::jsonb, "
            f"{t.estimated_setup_minutes})"
        )
    lines.append(",\n".join(rows))
    lines.append("ON CONFLICT DO NOTHING;")
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    out = Path(__file__).resolve().parent.parent / "infrastructure" / "postgres" / "migrations" / "054_workflow_templates_seed.sql"
    sql = emit_sql()
    out.write_text(sql, encoding="utf-8")
    print(f"wrote {out.relative_to(out.parent.parent.parent.parent)} ({len(sql.splitlines())} lines, {len(ALL_TEMPLATES)} templates)")
