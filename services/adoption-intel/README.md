# `services/adoption-intel/` — skeleton (Phase 2 extract target)

> **Status:** skeleton. Phase 1 v4 implementation tại `services/ai-orchestrator/org_intel/adoption/`.
> Phase 2 extract sprint TBD (post P2-S20).

## What it does

Khách triển khai Kaori xong → workflow chạy → một số người dùng resist (vẫn dùng Zalo cũ, override AI quyết định, không hoàn thành workflow, etc.). Adoption Intelligence theo dõi 9 signals này:

| # | Signal | Phase 1 | Phase 1.5 |
|---|---|---|---|
| 1 | Workflow execution abandonment | ✅ P1-S7 | |
| 2 | AI decision override rate | ✅ P1-S7 | |
| 3 | Side-channel detection (Zalo/Excel post-deploy) | ✅ P1-S7 | |
| 4 | Login frequency drop | | ✅ P15-S9 |
| 5 | Manager intervention frequency | ✅ P1-S7 | |
| 6 | Workflow completion rate per user/dept | ✅ P1-S7 | |
| 7 | Time-to-action increase | | ✅ P15-S9 |
| 8 | Feature usage skew | | ✅ P15-S9 |
| 9 | Negative feedback rate | | ✅ P15-S9 |

Aggregates → composite health score (0-100) per workflow / dept / tenant + classification (EXCELLENT/HEALTHY/AT_RISK/STRUGGLING) + trend (improving/declining/stable) + CSM alert generation.

## Why moat

Khi khách "im lặng" (không complain nhưng cũng không sử dụng), CSM không biết. Most SaaS chỉ thấy login rate. Adoption Intelligence detect resistance pattern → CSM intervention sớm trước churn.

Vietnamese context: Zalo + Excel side-channel detection là **moat-specific** vì ngoài Vietnam ít công ty xài Zalo cho công việc.

## Phase 1 path

P1-S7 code → `services/ai-orchestrator/org_intel/adoption/`. Đây chỉ skeleton.

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` PART VIII
- `docs/BACKLOG_V4.md` — P1-S7 (AI-SIG/AI-HSC/AI-INT codes) + P15-S9
- `docs/_v4_extract/adoption_intelligence.json`
