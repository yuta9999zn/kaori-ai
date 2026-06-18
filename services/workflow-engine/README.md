# `services/workflow-engine/` — skeleton (Phase 2 extract target)

> **Status:** skeleton — empty folder + service.yaml. **No code yet.**
> Phase 1 v4: implementation lives at `services/ai-orchestrator/workflow_runtime/` (embedded module per ADR-0010 modular monolith).
> Phase 2 v4 sprint **P2-S19**: extract to standalone service. Em sẽ move code from `ai-orchestrator/workflow_runtime/` here, add gRPC API, Helm chart.

## Why this skeleton exists Phase 1

Two reasons:

1. **Service catalog drift check.** Tooling reads `services/*/service.yaml`. Listing `workflow-engine` Phase 1 with `status: skeleton` makes the future extraction less surprising — readers know it's coming.
2. **Sprint planning anchor.** When P2-S19 lands, anh không phải tạo folder + nghĩ tên — folder + yaml đã có; chỉ cần move code + thêm Dockerfile + entrypoint.

## What goes here Phase 2

```
services/workflow-engine/
├── service.yaml                    ← already here
├── README.md                       ← already here
├── Dockerfile                      (Phase 2)
├── pyproject.toml                  (Phase 2)
├── workflow_engine/                (Phase 2 — moved from ai-orchestrator/workflow_runtime/)
│   ├── __init__.py
│   ├── main.py                     ← FastAPI entrypoint (workflow CRUD + dispatch)
│   ├── activities/                 ← Temporal activities per node type
│   ├── nodes/                      ← 45 node types in 6 categories
│   ├── saga/                       ← saga orchestrator + compensation chain
│   ├── temporal_client.py
│   └── shared/                     ← imports from ai-orchestrator/shared/ via internal lib
└── tests/
    ├── unit/
    └── integration/                ← Temporal docker-compose dev cluster fixtures
```

## Contracts (forward-looking)

- **gRPC contract** (Phase 2): `workflow_engine/v1/{Workflow, Run, Saga}` services. Defined in `protos/` — TBD.
- **REST surface (legacy compat):** `/api/v1/workflows/*` proxied through `api-gateway` to gRPC. Phase 1 legacy endpoints in `ai-orchestrator/workflow_runtime/` continue serving same routes during cutover window.
- **Side-effect class** required per node (K-17). Enforced at YAML validation time + activity registration time.

## Do not commit code here Phase 1

If anh sửa workflow logic Phase 1, làm trong `services/ai-orchestrator/workflow_runtime/` — không phải ở đây. P2-S19 mới move.

## References

- `docs/strategic/WORKFLOW_SYSTEM.md` — 45 node types catalog, lifecycle, Process Mining
- `docs/adr/0010-modular-monolith-then-microservices.md` — extraction strategy
- `docs/adr/0011-temporal-for-workflow-orchestration.md` — why Temporal
- `docs/adr/0014-at-least-once-plus-idempotency.md` — 5 side-effect classes
- `docs/BACKLOG_V4.md` — P1-S6 (REL-001..REL-023), P2-S19 (extraction)
