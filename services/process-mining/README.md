# `services/process-mining/` — skeleton (Phase 2 extract target)

> **Status:** skeleton — folder + service.yaml. No code yet.
> Phase 1 v4 sprint **P1-S7**: implementation lives at `services/ai-orchestrator/org_intel/process_mining/` (embedded module).
> Phase 2 v4 sprint **P2-S20**: extract to standalone service.

## Why moat (anh đọc 1 lần)

Vietnamese SMEs **don't know their workflow**. Anh hỏi "quy trình hiện tại của anh thế nào?" → nhận câu trả lời nhiễu. Process Mining đảo ngược: **AI nhìn log của khách (Postgres CDC, Excel revisions, Zalo metadata, Gmail audit) để dựng workflow thực sự**, sau đó cho khách review + chỉnh.

Đây là moat vì:
1. Cạnh tranh quốc tế (Pega, Celonis) chưa support Vietnamese sources — Zalo, Misa, Fast.
2. SME không tự dựng workflow → khách stay vì có "compass" mỗi tháng.
3. PII redaction phải Vietnamese-aware (tên, số CCCD, biển số) — không phải vendor nào cũng có.

Chi tiết: `docs/strategic/WORKFLOW_SYSTEM.md` PART IV.

## What goes here Phase 2

```
services/process-mining/
├── service.yaml                    ← already here
├── README.md                       ← already here
├── Dockerfile                      (Phase 2)
├── pyproject.toml                  (Phase 2)
├── process_mining/                 (Phase 2 — moved from ai-orchestrator/org_intel/process_mining/)
│   ├── __init__.py
│   ├── main.py                     ← FastAPI entrypoint
│   ├── connectors/                 ← per-source connectors (postgres_cdc, excel_history, zalo, gmail, misa, fast, outlook, slack_teams)
│   ├── normalizer.py               ← common event log schema (PM-PII-009)
│   ├── pii.py                      ← Vietnamese-aware redaction (PM-PII-010..012)
│   ├── algorithms/                 ← Heuristic Miner (P1) + Inductive Miner (P2) + Fuzzy Miner (P2)
│   ├── detectors/                  ← bottleneck (PM-ANM-021), shadow process (PM-ANM-022), bypass risk
│   └── output/                     ← findings report (PM-OUT-028..033) + workflow YAML auto-gen
└── tests/
```

## Phase 1 implementation path

Anh implement từ P1-S7 (Sprint 7 of Phase 1) trong `services/ai-orchestrator/org_intel/process_mining/`. Phase 1 scope:
- 3 connectors: PM-EVT-001 (Postgres CDC), PM-EVT-002 (Excel revisions), PM-EVT-003 (Zalo metadata)
- PII detection + redaction Vietnamese-aware
- Common event log schema normalization
- Case ID inference + Heuristic Miner
- Variant analysis + temporal pattern + bottleneck detection
- Findings report + workflow YAML auto-gen + off-system steps tagging + bottleneck flagging

Phase 2 P2-S13/S14 mở rộng: 5 sources thêm + Inductive + Fuzzy + bypass risk + shadow process.
Phase 2 P2-S20 extract sang service riêng cùng service mesh + Istio.

## Do not commit code here Phase 1

P1-S7 code → `services/ai-orchestrator/org_intel/process_mining/`. Đây chỉ skeleton.

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` PART IV
- `docs/strategic/SAD_SKELETON_V2.md` Phần 22
- `docs/BACKLOG_V4.md` P1-S7 (PM-EVT-001..PM-OUT-033) + P2-S13/S14
- `docs/_v4_extract/process_mining.json` — raw feature dump
