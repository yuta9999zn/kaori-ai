# `infrastructure/temporal/` — Temporal cluster

> **Status:** Phase 1.5 P15-S9 D3 scaffold landed (docker-compose + Helm).
> **Decision:** ADR-0011 — Temporal.io for workflow orchestration.
> **Worker:** runs in `services/ai-orchestrator/workflow_runtime/` Phase 1.5 (modular monolith), extract to `services/workflow-engine/` Phase 2 P2-S19.

## Phase 1.5 dev (P15-S9 D3 — landed)

Single-node Temporal cluster for local dev via the official `temporalio/auto-setup` image. Wires into the existing `kaori-system_default` Docker network so the ai-orchestrator container can reach `temporal:7233`.

```
infrastructure/temporal/
├── README.md                     ← this file
├── docker-compose.yml            ← landed P15-S9 D3 (auto-setup + UI + bootstrap)
├── dynamic-config.yaml           ← landed P15-S9 D3 (rate limits, archival off)
└── helm/                         ← landed P15-S9 D3 (production Helm wrapper)
    ├── Chart.yaml                ← upstream go.temporal.io/helm-charts dep
    └── values.yaml               ← 3-pod tiers, OTel + Postgres wiring
```

To bring up dev locally (alongside the main Kaori stack from repo root):

```
docker compose -f docker-compose.yml \
               -f infrastructure/temporal/docker-compose.yml up -d
```

The `temporal-bootstrap` helper registers the `kaori` namespace on first boot.

### Persistence
- Postgres dedicated DB (separate from `kaori` business DB) — schema `temporal`.
- Don't share with business postgres để Phase 2 extract microservice không phải migrate.

### Visibility
- Phase 1 — dùng default Postgres visibility (ít search attribute).
- Phase 1.5+ evaluate Elasticsearch backend nếu cần fuzzy search workflow_id.

### Network
- Phase 1 — Temporal frontend exposes 7233 (gRPC) cho worker; UI 8088.
- Phase 2 — service mesh (Istio) cho cross-service.

## Phase 1.5+ production (P15-S9)

Helm chart Temporal trên FPT Cloud K8s (ADR-0016):
- 3 frontend pods (HPA)
- 3 history pods
- 3 matching pods
- Worker pod separate (ai-orchestrator hoặc workflow-engine).

## Operational notes

- **Workflow_id naming convention:** `t-{tenant_id}-{run_id}` (K-1 + ADR-0013) — Temporal namespace per environment, không per tenant (chi phí).
- **Activity timeout default:** 5 minutes; long-running activities phải heartbeat (REL-021).
- **Saga compensation:** declared in workflow YAML (REL-012); Temporal saga orchestrator runs compensation chain on failure (REL-013).

## References

- ADR-0011 (`docs/adr/0011-temporal-for-workflow-orchestration.md`)
- ADR-0014 (`docs/adr/0014-at-least-once-plus-idempotency.md`) — 5 side-effect classes + idempotency
- `docs/strategic/SAD_SKELETON_V2.md` Phần 18-21
- `docs/strategic/WORKFLOW_SYSTEM.md` Phần 14 (lifecycle)
- `docs/BACKLOG_V4.md` P1-S6 (REL-001..REL-023, OBS-004/007)
- Runbook (Phase 2): `docs/runbooks/temporal-down.md` (TBD)
