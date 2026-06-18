# `services/economics/` — skeleton (Phase 2 extract target)

> **Status:** skeleton. Phase 1 v4 implementation tại `services/ai-orchestrator/org_intel/economics/`.
> Phase 2 extract sprint TBD.

## NOV — Net Operational Value

Triết lý v4: mọi capability đều quy ra **VND**. Manager hỏi "Kaori đang tiết kiệm bao nhiêu/tháng?" → có số. Phase 1 sprint P1-S7 implement:

**Revenue (3 methods):**
- `NOV-REV-001` Pre/Post comparison (30 days before vs after deploy)
- `NOV-REV-003` Industry benchmark fallback (ví dụ: 5% revenue uplift retail churn intervention)
- `NOV-REV-004/005` KPI-to-revenue mapper + confidence scoring

Phase 1.5 thêm `NOV-REV-002` A/B attribution method.

**Cost (4 components):**
- `NOV-CST-007` People cost (time saved × rate)
- `NOV-CST-008` Infrastructure compute + storage per-tenant
- `NOV-CST-009` AI call cost tracking (token-based — depends on `llm-gateway` token tracker)
- `NOV-CST-010` Integration cost (3rd-party API calls)

**Core (6 outputs):**
- `NOV-CORE-013` Monthly NOV = revenue - cost
- `NOV-CORE-014` Time-to-payback projection
- `NOV-CORE-015` Cumulative NOV tracking
- `NOV-CORE-016` Negative NOV alerts (CSM trigger)
- `NOV-CORE-017` Per-department rollup
- `NOV-CORE-018` Per-tenant total

**Reports (Phase 1 P1-S8):**
- `NOV-RPT-019` Monthly manager email digest
- `NOV-RPT-021` ROI dashboard real-time
- `NOV-RPT-022` Workflow ROI ranking (top performers)

## Relationship with v3 F-031

F-031 v3 (`enterprise_monthly_billing` cron) là **billing aggregator**, không phải NOV. NOV là khái niệm khác — value to customer, không phải revenue to Kaori. v4 keep both:

- `SH-M51-*` (cũ F-031) = billing per Kaori plan (DISTINCT customer counts).
- `NOV-*` = customer's ROI from using Kaori.

## VND format (memory `feedback_vnd_currency_format`)

UI luôn `1.000.000₫` hoặc `1 triệu VNĐ`, KHÔNG `1M`/`2M`. Phase 1 economics dashboard tuân thủ.

## Phase 1 path

P1-S7 code → `services/ai-orchestrator/org_intel/economics/`. Đây chỉ skeleton.

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` PART XI
- `docs/BACKLOG_V4.md` P1-S7 + P1-S8
- `docs/_v4_extract/operational_economics.json`
