# VinFast Distribution Workflow — Test Data Bundle

Synthetic but internally consistent test data for the **"Quản lý vòng đời phân phối xe VinFast"** workflow (22 steps, 6 swimlanes, OTIF SLA target ≥ 98.5%). Use it to exercise document upload, insight calculation, and chart rendering.

## Contents

| File | Purpose |
|---|---|
| `vinfast_workflow_dataset.xlsx` | Main workbook — 4 sheets, 7,900+ live formulas, 4 native charts. Open the **Dashboard** sheet first. |
| `orders.csv` | 280 work orders, one row each (order facts + OTIF outcome). |
| `step_timings.csv` | 6,160 rows — every order × 22 steps with start/end, duration, SLA target. Use for bottleneck analysis. |
| `workflow_dataset.json` | Same data, nested JSON, for API ingestion. |
| `sample_documents/*.pdf` | 5 upload-test documents (real, text-extractable PDFs) linked to real work-order IDs. |

## Dataset shape

- **280 work orders**, May 2025 – Apr 2026 (12 months of trend).
- **6 regions**: Vietnam, Southeast Asia, India, Middle East, Europe, North America.
- **7 models**: VF 3 / 5 / 6 / 7 / 8 / 9 / e34.
- **22 workflow steps** across 6 swimlanes (full catalogue in the `Reference` sheet).
- Channels: Manual / Auto-API. Approval routes L2 / L3 (L3 auto-triggered when order value > $2M).
- Inventory decision per order: AVAILABLE / PARTIAL / BACKORDER (drives the S03 decision gate and In-Full).

The data is deliberately **under the 98.5% SLA target** so your insight/alerting layer has real signals to surface (regional weak spots, slow steps, monthly dips).

## Ground-truth KPIs (validate your engine against these)

| Metric | Expected value |
|---|---|
| Total work orders | 280 |
| Total order value | ≈ $71.35M |
| OTIF rate | ≈ 83.2% (target ≥ 98.5% → **breach**) |
| On-time rate | ≈ 89.6% |
| In-full rate | ≈ 89.6% |
| Backorder rate | ≈ 10.4% |
| Audit variance rate | ≈ 6.8% |
| Avg cycle time | ≈ 30.4 days |
| Slowest steps (avg hrs) | S11 In-Transit ≈ 551 · S12 Import Customs ≈ 40 · S09 Export Customs ≈ 32 · S20 Payment Recon ≈ 12 |

Numbers are computed by live Excel formulas, so they recalculate if you edit source rows.

## Suggested insights & charts to test

- **OTIF % trend by month** (line) — already built on the Dashboard.
- **Step bottleneck** (bar of avg duration) — S11/S12/S09 dominate; good for "biểu đồ" rendering.
- **Inventory decision mix** (pie).
- **Revenue / OTIF by region** (bar) — Europe & India underperform; Middle East best.
- Drill-downs you can derive: OTIF by model, exceptions vs cycle time, L2 vs L3 approval impact, Auto-API vs Manual cycle time, SLA compliance per swimlane.

## Document upload test

The 5 PDFs map to real work orders so you can test the document tree + per-step "Tài liệu cần nộp":

| File | Doc type | Step it belongs to | Work order |
|---|---|---|---|
| `PO_VF-WO-26057_DealerPurchaseOrder.pdf` | Dealer PO | S01 Intake | VF-WO-26057 |
| `PO_VF-WO-26003_DealerPurchaseOrder.pdf` | Dealer PO | S01 Intake | VF-WO-26003 |
| `PO_VF-WO-26201_DealerPurchaseOrder.pdf` | Dealer PO | S01 Intake | VF-WO-26201 |
| `INV_VF-WO-26057_CommercialInvoice.pdf` | Commercial Invoice | S08 Export Doc | VF-WO-26057 |
| `BOL_VF-WO-26057_BillOfLading.pdf` | Bill of Lading | S11/S12 Transit & Import | VF-WO-26057 |

All PDFs contain selectable text (key/value fields + line-item tables), so they also work for testing parsing/OCR and field extraction.
