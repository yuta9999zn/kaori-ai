"""
Rebuild the VinFast Inbound-to-Dealer Vehicle Distribution workflow as 22
BIG step cards — one card per business step — instead of the current
mixture of `decision_if_else` and `approval_gate` mini-nodes.

Anh's directive 2026-05-17 (paraphrase):

    "Tôi muốn tạo các card khác nhau theo workflow khác nhau, một card to —
     ví dụ card to về S02 với Actor: RPA bot LCT-MDV-01 + LCT Operations
     Analyst (exception). Không phải các card nhỏ if/else."

Per the test bundle's workflow_dataset.json the workflow has 22 unique step
codes grouped into 6 swimlanes:

    S01-S04 — Dealer & Sales / Master Data & Inventory (intake → reserve)
    S05-S07 — Logistics Operations                       (plan → booking)
    S08-S09 — Customs & Compliance                       (export docs / clearance)
    S10-S15 — Logistics Operations / Customs             (yard → in-transit → import)
    S16-S17 — Dealer & Sales                             (delivery confirmation)
    S18-S20 — Finance & Revenue                          (revenue / invoice / AR)
    S21-S22 — Audit & Governance                         (audit / close-out)

Each card carries the Actor + Swimlane + SLA + Systems + Validation + KPI
+ AI opportunity. All cards are `node_type='step'` (the user-facing label is
"Bước nghiệp vụ"); routing nuance lives inside the note, not as a separate
if-else child node — the FE tree viewer renders it as a chain of single
cards rather than a branchy graph.

What this script does (idempotent — safe to re-run):

  1. Deletes the current workflow_nodes + workflow_edges + relinked
     workflow_step_documents for this workflow (cascade).
  2. Inserts 22 new step cards with structured notes.
  3. Inserts 21 sequential edges S01 → S02 → ... → S22.
  4. Re-attaches the 5 existing bronze_files (already uploaded —
     orders.csv, step_timings.csv, 3 sheets from vinfast_workflow_dataset.xlsx)
     to the new node IDs:
        orders.csv  + Orders sheet           → S01
        step_timings.csv + StepTimings sheet → S02
        Dashboard sheet                      → S22

Run after Postgres + ai-orchestrator are up:

    python scripts/rebuild_vinfast_distribution_workflow.py
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import uuid


WORKFLOW_ID    = "a167bf64-be0e-4703-980b-0ae88cc49f07"
ENTERPRISE_ID  = "566bdd08-b4e5-4680-9e7f-9f2840d95ecf"
DEPARTMENT_ID  = "80ef98e3-2618-40f2-b260-352b2588f7fb"
WORKSPACE_ID   = "76a1ee8b-b401-42df-bf69-bb61724348b8"

# bronze_file_id → target step code (existing uploads from
# scripts/import_vinfast_fake_data.py runs).
EXISTING_FILE_ATTACHMENTS = {
    "9f62ef96-0716-4855-8c19-416294a073b4": "S01",  # orders.csv
    "a0313ed0-4127-4df6-9cca-3433c75b0d8c": "S01",  # Orders sheet
    "dc4c0c2c-3a6c-4be8-a92b-6347cb3b1ed0": "S02",  # step_timings.csv
    "a74c55de-bd3d-423d-9ce2-957b59e51690": "S02",  # StepTimings sheet
    "b3a9224a-879f-4b74-b987-4d066acec4c6": "S22",  # Dashboard sheet (closeout KPIs)
}


def _hashtag(swimlane: str) -> str:
    """Stable hashtag from swimlane name."""
    return swimlane.lower().replace(" & ", "_").replace(" ", "_")


# 22-step catalogue. Each entry produces one BIG card. Notes are
# multi-line so the FE renders Actor / Swimlane / SLA / Systems / KPI /
# AI Opportunity each on its own line.
STEPS: list[dict] = [
    {
        "code":     "S01",
        "title":    "Vehicle Request Intake",
        "title_vi": "Tiếp nhận yêu cầu đặt xe",
        "swimlane": "Dealer & Sales",
        "actor":    "Dealer Sales Rep / Fleet Account Manager / Auto-API Client",
        "sla_h":    3.2,
        "input":    "Dealer PO, VIN preference, model/trim, delivery window, destination yard",
        "output":   "VDO-{YYYYMMDD}-{seq} record in queue",
        "systems":  "SAP S/4HANA SD, Salesforce CRM, VinFast Dealer Portal, Kafka topic vdo.intake.v1",
        "docs":     "Purchase Order PDF, Dealer Allocation Contract",
        "validation": "Dealer KYC active, credit line ≥ order value, model homologated for destination",
        "kpi":      "Intake-to-validation < 5 minutes; rejection rate < 2%",
        "ai":       "NLP extraction from unstructured email/fax orders; duplicate detection via embedding similarity",
        "required_docs": [
            {"kind": "pdf", "name": "Purchase Order (Dealer PO)", "required": True},
            {"kind": "csv", "name": "Order intake log", "required": False},
        ],
    },
    {
        "code":     "S02",
        "title":    "Order Enrichment & MDM Validation",
        "title_vi": "Làm giàu dữ liệu & kiểm tra master",
        "swimlane": "Master Data & Inventory",
        "actor":    "RPA bot LCT-MDV-01 + LCT Operations Analyst (exception)",
        "sla_h":    6.8,
        "input":    "Raw VDO record from S01",
        "output":   "Enriched VDO with master vehicle spec + sanctioned-party clearance",
        "systems":  "SAP MDG, Informatica IDQ, Snowflake dim_vehicle_master",
        "docs":     "Master data delta report, OFAC / EU sanctions snapshot",
        "validation": "Spec consistency, sanctions OFAC/EU, homologation matrix per destination country",
        "kpi":      "Bot cycle < 90s; data-quality score ≥ 99%; analyst exception rate < 1%",
        "ai":       "Auto-classify exceptions; suggest spec corrections from historical fixes",
        "required_docs": [
            {"kind": "csv", "name": "Master data snapshot", "required": False},
        ],
    },
    {
        "code":     "S03",
        "title":    "Inventory Availability Check",
        "title_vi": "Kiểm tra tồn kho sẵn có",
        "swimlane": "Master Data & Inventory",
        "actor":    "Inventory Planner",
        "sla_h":    4.0,
        "input":    "Enriched VDO from S02",
        "output":   "Inventory status: AVAILABLE | PARTIAL | STOCKOUT (routing decided in S04)",
        "systems":  "SAP IBP, Manhattan Active Warehouse, Kaori Inventory Cube",
        "docs":     "ATP snapshot, allocation candidate list",
        "validation": "Reservation horizon ≤ 30 days, no double-book against existing reservations",
        "kpi":      "ATP response P99 < 2 seconds; backorder rate < 12%",
        "ai":       "Predictive ATP using production forecast + inbound shipping schedule",
        "required_docs": [],
    },
    {
        "code":     "S04",
        "title":    "VIN Reservation & Allocation",
        "title_vi": "Đặt giữ / phân bổ VIN",
        "swimlane": "Master Data & Inventory",
        "actor":    "Inventory Planner",
        "sla_h":    5.4,
        "input":    "Inventory status + allocation candidates",
        "output":   "VIN(s) reserved or split allocation across yards (partial)",
        "systems":  "SAP S/4HANA MM, Manhattan WMS, Kaori Allocation Engine",
        "docs":     "Reservation slip, allocation plan",
        "validation": "VIN status = AVAILABLE; quality-hold flag = false; export-eligible for destination",
        "kpi":      "Allocation lock time < 4h; allocation-to-dispatch leakage < 0.5%",
        "ai":       "Pick optimization: minimize cross-yard moves + carrier deadhead",
        "required_docs": [],
    },
    {
        "code":     "S05",
        "title":    "Logistics Plan Drafting",
        "title_vi": "Lập kế hoạch logistics",
        "swimlane": "Logistics Operations",
        "actor":    "Logistics Planner",
        "sla_h":    9.0,
        "input":    "Allocated VINs + destination + delivery window",
        "output":   "Multi-modal logistics plan (truck + ocean + last-mile) + cost model + carbon estimate",
        "systems":  "Oracle TMS, Blue Yonder OTM, Project44 visibility",
        "docs":     "Logistics plan PDF, lane-rate quote, carbon footprint sheet",
        "validation": "Lane available; cost within budget envelope; transit time meets delivery SLA",
        "kpi":      "Plan draft < 8h; cost variance vs benchmark ≤ 5%",
        "ai":       "Lane suggestion + carrier mix optimization from historical OTIF",
        "required_docs": [
            {"kind": "pdf", "name": "Logistics plan draft", "required": False},
        ],
    },
    {
        "code":     "S06",
        "title":    "Logistics Plan Approval",
        "title_vi": "Phê duyệt kế hoạch logistics",
        "swimlane": "Logistics Operations",
        "actor":    "Logistics Ops Manager (L2) → Regional Director (L3 if order value > $2M)",
        "sla_h":    12.0,
        "input":    "Drafted logistics plan, cost model, carbon footprint",
        "output":   "Approved (proceed) or Rejected with reason (loop back to S05)",
        "systems":  "SAP Ariba, ServiceNow Approval, Kaori Workflow Engine",
        "docs":     "Approval ticket, signed-off plan",
        "validation": "Segregation-of-duties check; budget envelope; carbon target compliance",
        "kpi":      "Approval cycle time < 4h (L2); < 12h (L3); auto-approve low-risk rate ≥ 60%",
        "ai":       "Co-pilot recommends approve/reject; auto-approve low-risk (cost ≤ benchmark, lane proven)",
        "required_docs": [],
    },
    {
        "code":     "S07",
        "title":    "Carrier Booking",
        "title_vi": "Đặt hãng vận chuyển",
        "swimlane": "Logistics Operations",
        "actor":    "Logistics Coordinator",
        "sla_h":    8.0,
        "input":    "Approved plan + carrier shortlist",
        "output":   "Carrier confirmed, booking number, pickup window",
        "systems":  "Oracle TMS, EDI 204/990 carrier portals",
        "docs":     "Carrier confirmation, booking number",
        "validation": "Carrier KPI score ≥ 85; insurance current; equipment available at origin",
        "kpi":      "Booking confirmation < 6h; reject rate < 3%",
        "ai":       "Auto-tender to next-best carrier on rejection",
        "required_docs": [],
    },
    {
        "code":     "S08",
        "title":    "Export Documentation Preparation",
        "title_vi": "Chuẩn bị chứng từ xuất khẩu",
        "swimlane": "Customs & Compliance",
        "actor":    "Trade Compliance Officer",
        "sla_h":    15.0,
        "input":    "Booking + VIN list + commercial terms",
        "output":   "Commercial Invoice, Packing List, Certificate of Origin, Export Declaration",
        "systems":  "SAP GTS, Descartes Global Trade, eDoc Repository",
        "docs":     "Commercial Invoice (INV), Packing List, Certificate of Origin (CoO)",
        "validation": "HS code correct; dual-use screening; FTA preference claim valid",
        "kpi":      "Doc-ready before vessel ETA - 48h ≥ 95%",
        "ai":       "Auto-classify HS code; pre-fill from past shipments",
        "required_docs": [
            {"kind": "pdf", "name": "Commercial Invoice", "required": True},
            {"kind": "pdf", "name": "Certificate of Origin", "required": False},
        ],
    },
    {
        "code":     "S09",
        "title":    "Export Customs Clearance",
        "title_vi": "Thông quan xuất khẩu",
        "swimlane": "Customs & Compliance",
        "actor":    "Customs Broker (Export)",
        "sla_h":    61.4,
        "input":    "Export docs + cargo at port",
        "output":   "Export clearance number, cleared to load",
        "systems":  "VNACCS (Vietnam Customs), broker portal, SAP GTS",
        "docs":     "Export declaration accepted, exit endorsement",
        "validation": "No red-channel flag; duty paid; permits attached if required",
        "kpi":      "Clearance < 72h (P95); red-channel hit rate < 4%",
        "ai":       "Risk-score declaration before submission; pre-warn red-channel likelihood",
        "required_docs": [],
    },
    {
        "code":     "S10",
        "title":    "Yard Loading & Departure",
        "title_vi": "Xếp hàng & khởi hành",
        "swimlane": "Logistics Operations",
        "actor":    "Yard Operations",
        "sla_h":    9.0,
        "input":    "Cleared cargo + loaded carrier",
        "output":   "Loaded onto vessel/truck; gate-out timestamp",
        "systems":  "Yard Management System, port terminal API",
        "docs":     "Bill of Lading draft, gate-out slip, mate's receipt",
        "validation": "VIN matches BOL; seal intact; photo evidence captured",
        "kpi":      "Cut-off compliance ≥ 98%; damage incidents < 0.2%",
        "ai":       "Computer-vision damage detection pre-load",
        "required_docs": [],
    },
    {
        "code":     "S11",
        "title":    "In-Transit Monitoring",
        "title_vi": "Theo dõi vận chuyển",
        "swimlane": "Logistics Operations",
        "actor":    "Control Tower",
        "sla_h":    540.0,
        "input":    "Carrier tracking events + AIS / GPS / EDI 214",
        "output":   "Visibility timeline + ETA + exception flags",
        "systems":  "Project44, FourKites, MarineTraffic, Kaori Visibility",
        "docs":     "Bill of Lading (BOL), tracking log",
        "validation": "Event freshness ≤ 6h; ETA drift alert > 24h",
        "kpi":      "Visibility coverage ≥ 95%; ETA accuracy ± 1 day at vessel berth",
        "ai":       "ETA prediction from port congestion + weather; auto-reroute suggestion",
        "required_docs": [
            {"kind": "pdf", "name": "Bill of Lading", "required": True},
        ],
    },
    {
        "code":     "S12",
        "title":    "Import Customs Clearance",
        "title_vi": "Thông quan nhập khẩu",
        "swimlane": "Customs & Compliance",
        "actor":    "Customs Broker (Import)",
        "sla_h":    76.8,
        "input":    "Arrival notice + import docs + BOL",
        "output":   "Import clearance, duty paid, release order",
        "systems":  "Destination customs portal (per country), SAP GTS, broker portal",
        "docs":     "Import declaration, duty receipt, release order",
        "validation": "HTS code valid in destination; permits if required; landed cost reconciled",
        "kpi":      "Clearance P95 < 96h; storage demurrage spend < $X / order",
        "ai":       "Pre-arrival declaration filing; auto-classify HTS",
        "required_docs": [],
    },
    {
        "code":     "S13",
        "title":    "Port Discharge & Yard Receipt",
        "title_vi": "Cập cảng / về bãi",
        "swimlane": "Logistics Operations",
        "actor":    "Yard Operations",
        "sla_h":    12.0,
        "input":    "Released cargo at destination port",
        "output":   "Cargo at destination yard, intake confirmed",
        "systems":  "Destination YMS, terminal API",
        "docs":     "Yard intake slip, damage report (if any)",
        "validation": "Count matches BOL; condition inspection passed",
        "kpi":      "Port-to-yard transit < 24h; damage incidents < 0.3%",
        "ai":       "CV damage assessment at intake gate",
        "required_docs": [],
    },
    {
        "code":     "S14",
        "title":    "Pre-Delivery Inspection (PDI)",
        "title_vi": "Kiểm tra trước giao (PDI)",
        "swimlane": "Logistics Operations",
        "actor":    "PDI Technician",
        "sla_h":    9.6,
        "input":    "Vehicle at PDI station",
        "output":   "PDI pass certificate or rework ticket",
        "systems":  "VinFast PDI Checklist, defect tracker",
        "docs":     "PDI report, rework order (if defects)",
        "validation": "100-point checklist passed; OTA firmware latest; recall list cleared",
        "kpi":      "First-pass yield ≥ 97%; PDI cycle < 8h",
        "ai":       "Defect pattern detection across batches",
        "required_docs": [],
    },
    {
        "code":     "S15",
        "title":    "Final-Mile Dispatch",
        "title_vi": "Điều phối chặng cuối",
        "swimlane": "Logistics Operations",
        "actor":    "Final-Mile Carrier",
        "sla_h":    19.2,
        "input":    "PDI-cleared vehicle + dealer destination",
        "output":   "Vehicle delivered to dealer location",
        "systems":  "Final-mile TMS, dealer portal",
        "docs":     "POD signed by dealer, condition photos",
        "validation": "Dealer ready to receive; delivery window confirmed",
        "kpi":      "On-time dealer delivery ≥ 96%",
        "ai":       "Route optimization; dynamic ETA SMS to dealer",
        "required_docs": [],
    },
    {
        "code":     "S16",
        "title":    "Dealer Delivery Confirmation",
        "title_vi": "Xác nhận giao hàng",
        "swimlane": "Dealer & Sales",
        "actor":    "Dealer Sales Rep",
        "sla_h":    3.6,
        "input":    "Vehicle at dealer + POD",
        "output":   "Confirmed delivery + acceptance signed",
        "systems":  "VinFast Dealer Portal, Salesforce",
        "docs":     "Acceptance form, POD",
        "validation": "VIN match; condition acceptable; documents handed over",
        "kpi":      "Confirmation < 2h after physical delivery",
        "ai":       "Auto-extract POD photo; OCR signature confirmation",
        "required_docs": [],
    },
    {
        "code":     "S17",
        "title":    "Delivery Document Capture",
        "title_vi": "Ghi nhận chứng từ giao hàng",
        "swimlane": "Dealer & Sales",
        "actor":    "Dealer Sales Rep",
        "sla_h":    4.0,
        "input":    "Signed POD + dealer acceptance",
        "output":   "Documents archived in DMS, ready for revenue recognition",
        "systems":  "DocuSign, SharePoint DMS, SAP DMS",
        "docs":     "Final POD, acceptance form, condition photos",
        "validation": "All required docs scanned; metadata complete",
        "kpi":      "Doc complete-before-billing rate ≥ 99%",
        "ai":       "OCR + auto-classify documents",
        "required_docs": [],
    },
    {
        "code":     "S18",
        "title":    "Revenue Recognition",
        "title_vi": "Ghi nhận doanh thu",
        "swimlane": "Finance & Revenue",
        "actor":    "Revenue Accountant",
        "sla_h":    6.4,
        "input":    "POD + dealer acceptance + commercial terms",
        "output":   "Revenue booked under IFRS 15 / VAS",
        "systems":  "SAP FI-CO, Revenue Recognition module",
        "docs":     "Revenue journal entry, supporting POD",
        "validation": "Control transfer satisfied; price allocated; deferred revenue treated correctly",
        "kpi":      "Book-by-T+1 rate ≥ 98%",
        "ai":       "Auto-suggest journal lines; flag unusual price discounts",
        "required_docs": [],
    },
    {
        "code":     "S19",
        "title":    "Invoice Issuance",
        "title_vi": "Phát hành hóa đơn",
        "swimlane": "Finance & Revenue",
        "actor":    "Billing Specialist",
        "sla_h":    5.1,
        "input":    "Revenue booking + dealer billing terms",
        "output":   "E-invoice issued + sent to dealer",
        "systems":  "VNPT e-Invoice, SAP SD",
        "docs":     "Tax invoice, debit note (if any)",
        "validation": "Tax code valid; serial assigned; VAT calc correct",
        "kpi":      "Issuance T+1 ≥ 99%; rejection rate < 1%",
        "ai":       "Auto-fill from sales order; pre-validate tax fields",
        "required_docs": [],
    },
    {
        "code":     "S20",
        "title":    "Payment Reconciliation",
        "title_vi": "Đối soát thanh toán",
        "swimlane": "Finance & Revenue",
        "actor":    "AR Analyst",
        "sla_h":    20.4,
        "input":    "Bank statements + open invoices",
        "output":   "Cash matched to invoice; AR aged correctly",
        "systems":  "SAP FI-AR, BlackLine reconciliation, bank feeds",
        "docs":     "Reconciliation report, exception list",
        "validation": "100% cash matched; aging bucket correct",
        "kpi":      "Auto-match rate ≥ 85%; unapplied cash < 1% of AR",
        "ai":       "Auto-match using payment reference fuzz logic",
        "required_docs": [],
    },
    {
        "code":     "S21",
        "title":    "Audit Reconciliation",
        "title_vi": "Đối soát kiểm toán",
        "swimlane": "Audit & Governance",
        "actor":    "Internal Audit",
        "sla_h":    14.4,
        "input":    "Complete order trail S01 → S20",
        "output":   "Audit pass / variance report",
        "systems":  "GRC platform, Kaori Audit Log, SAP Audit Trail",
        "docs":     "Audit checklist signed, variance memo",
        "validation": "End-to-end documents complete; controls test passed; SoD respected",
        "kpi":      "Variance rate < 3%; control-test pass ≥ 98%",
        "ai":       "Continuous control monitoring; anomaly detection on cycle time + cost",
        "required_docs": [],
    },
    {
        "code":     "S22",
        "title":    "Workflow Close-Out",
        "title_vi": "Kết thúc quy trình",
        "swimlane": "Audit & Governance",
        "actor":    "Logistics Governance",
        "sla_h":    4.0,
        "input":    "Audit-passed order",
        "output":   "Order closed; KPI metrics emitted to dashboard",
        "systems":  "Kaori NOV dashboard, SAP BW",
        "docs":     "Close-out summary, KPI snapshot",
        "validation": "All open exceptions resolved; OTIF computed; lessons learned captured",
        "kpi":      "Close-out within T+2; lessons-learned capture ≥ 90% on exception orders",
        "ai":       "Pattern mining for repeat exceptions; auto-suggest playbook updates",
        "required_docs": [
            {"kind": "csv", "name": "Close-out KPI snapshot", "required": False},
        ],
    },
]


def _note(step: dict) -> str:
    """Render the multi-line big-card note."""
    lines = [
        f"**Swimlane:** {step['swimlane']}",
        f"**Actor:** {step['actor']}",
        f"**SLA target:** {step['sla_h']}h",
        f"**Input:** {step['input']}",
        f"**Output:** {step['output']}",
        f"**Systems:** {step['systems']}",
        f"**Documents:** {step['docs']}",
        f"**Validation:** {step['validation']}",
        f"**KPI:** {step['kpi']}",
        f"**AI Opportunity:** {step['ai']}",
    ]
    return "\n".join(lines)


def _sql_literal(s: str) -> str:
    """Postgres dollar-quoted literal — survives single quotes inside notes."""
    return f"$kaori${s}$kaori$"


def build_sql() -> str:
    """Generate the full transaction as a SQL string."""
    out: list[str] = []
    out.append("BEGIN;")
    out.append("")
    out.append("-- 1. Wipe current nodes + edges + step-doc links")
    out.append(
        f"DELETE FROM workflow_nodes WHERE workflow_id = '{WORKFLOW_ID}';"
    )
    out.append("")
    out.append("-- 2. Insert 22 big-card step nodes")
    node_ids: dict[str, str] = {}
    for idx, step in enumerate(STEPS, start=1):
        node_id = str(uuid.uuid4())
        node_ids[step["code"]] = node_id
        title    = f"{step['code']} {step['title']}"
        title_vi = f"{step['code']} {step['title_vi']}"
        note     = _note(step)
        hashtag  = _hashtag(step["swimlane"])
        # Each row gets x = idx (slot), y constant — FE renders sequentially.
        out.append(
            "INSERT INTO workflow_nodes "
            "(node_id, workflow_id, enterprise_id, workspace_id, department_id, "
            " node_type, category, side_effect_class, position_x, position_y, "
            " title, title_vi, note, hashtags, required_document_types, "
            " config, sequence_order, decision_config) VALUES ("
            f"'{node_id}', '{WORKFLOW_ID}', '{ENTERPRISE_ID}', '{WORKSPACE_ID}', '{DEPARTMENT_ID}', "
            "'step', 'processing', 'read_only', "
            f"{100 + (idx - 1) * 220}, 100, "
            f"{_sql_literal(title)}, {_sql_literal(title_vi)}, {_sql_literal(note)}, "
            f"ARRAY['{hashtag}', '{step['code'].lower()}']::text[], "
            f"{_sql_literal(json.dumps(step['required_docs']))}::jsonb, "
            "'{}'::jsonb, "
            f"{idx}, '{{}}'::jsonb"
            ");"
        )
    out.append("")
    out.append("-- 3. Insert 21 sequential edges S01 → S02 → ... → S22")
    for i in range(len(STEPS) - 1):
        src_code = STEPS[i]["code"]
        dst_code = STEPS[i + 1]["code"]
        edge_id  = str(uuid.uuid4())
        out.append(
            "INSERT INTO workflow_edges "
            "(edge_id, workflow_id, enterprise_id, workspace_id, "
            " source_node_id, target_node_id, label) VALUES ("
            f"'{edge_id}', '{WORKFLOW_ID}', '{ENTERPRISE_ID}', '{WORKSPACE_ID}', "
            f"'{node_ids[src_code]}', '{node_ids[dst_code]}', 'next');"
        )
    out.append("")
    out.append("-- 4. Re-attach existing bronze_files to new node IDs")
    for file_id, target_code in EXISTING_FILE_ATTACHMENTS.items():
        node_id = node_ids[target_code]
        out.append(
            "INSERT INTO workflow_step_documents "
            "(workflow_id, node_id, file_id, enterprise_id, "
            " department_id, workspace_id, document_kind, uploaded_at) "
            "SELECT "
            f"'{WORKFLOW_ID}', '{node_id}', bf.file_id, bf.enterprise_id, "
            "bf.department_id, "
            f"'{WORKSPACE_ID}', bf.file_format, NOW() "
            f"FROM bronze_files bf WHERE bf.file_id = '{file_id}' "
            "ON CONFLICT (workflow_id, node_id, file_id) DO NOTHING;"
        )
    out.append("")
    out.append("COMMIT;")
    out.append("")
    return "\n".join(out)


def main() -> int:
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

    sql = build_sql()
    print(f"[gen] SQL size: {len(sql):,} chars · 22 step inserts · 21 edges · "
          f"{len(EXISTING_FILE_ATTACHMENTS)} doc relinks")

    print("[run] piping SQL into kaorisystem-postgres-1 (psql -v ON_ERROR_STOP=1) …")
    # Windows-safe: feed bytes so subprocess doesn't translate \n → \r\n
    # (which would land literal CRs inside the dollar-quoted note text).
    res = subprocess.run(
        ["docker", "exec", "-i", "kaorisystem-postgres-1",
         "psql", "-U", "kaori", "-d", "kaori", "-v", "ON_ERROR_STOP=1", "-q"],
        input=sql.encode("utf-8"),
        capture_output=True,
    )
    stderr_text = res.stderr.decode("utf-8", errors="replace")
    if res.returncode != 0:
        print("[err] psql failed:")
        print(stderr_text[-2000:])
        return 1
    if stderr_text.strip():
        print("[psql stderr]:")
        print(stderr_text[-800:])
    print("[ok] transaction committed.")

    # Verify
    verify = subprocess.run(
        ["docker", "exec", "kaorisystem-postgres-1",
         "psql", "-U", "kaori", "-d", "kaori", "-tA", "-F|", "-c",
         f"""
         SELECT n.sequence_order, n.title, n.node_type,
                (SELECT COUNT(*) FROM workflow_step_documents d
                 WHERE d.node_id = n.node_id) AS docs
         FROM workflow_nodes n
         WHERE n.workflow_id = '{WORKFLOW_ID}'
         ORDER BY n.sequence_order;
         """],
        capture_output=True, text=True, encoding="utf-8",
    )
    print("\n[verify] cards in workflow:")
    print(verify.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
