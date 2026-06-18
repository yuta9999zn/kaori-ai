# `infrastructure/k8s/` — Kubernetes manifests (P15-S9 onwards)

> **Status:** D1 scaffolding landed 2026-05-08 (kaori-services umbrella chart + Kustomize overlays). Cluster deploy pending FPT Cloud commercial contract activation.
> **Sprint:** P15-S9 (Phase 1.5 Sprint 9) — see `docs/archive/sprint/p15-s9/P15-S9_PLAN.md` D1.
> **Decision:** ADR-0016 (FPT/Viettel VN hosting); ADR-0010 (modular monolith Phase 1 — K8s onboard Phase 1.5 to avoid pilot disruption).

## Why deferred to Phase 1.5

Phase 1 (M1-M4) chạy docker-compose trên laptop pilot anh. Onboard K8s ngay Sprint 1-2 = phá pilot Olist + 1 dev không vận hành kịp. Phase 1.5 P15-S9 mới triển khi ổn định + có khách thứ 2-3.

## Layout

```
infrastructure/k8s/
├── README.md                     ← this file
├── helm-charts/                  (P15-S9)
│   ├── kaori-platform/           ← umbrella chart dependency-link tới sub-charts
│   ├── kaori-services/           ← api-gateway, auth-service, data-pipeline, ai-orchestrator, llm-gateway, notification-service
│   ├── kaori-infra/              ← postgres (CloudNativePG), redis-cluster, kafka, ollama
│   ├── temporal/                 ← Temporal Helm chart wrapper
│   ├── clickhouse/               ← Altinity Operator wrapper
│   ├── minio/                    ← MinIO Operator wrapper
│   ├── vault/                    ← HashiCorp Vault HA chart
│   └── otel-stack/               ← Collector + Jaeger + Tempo + Prometheus + Loki + Grafana
├── kustomize/                    (P15-S9) — env overlays
│   ├── base/
│   ├── overlays/dev/
│   ├── overlays/staging/
│   └── overlays/production/
├── network-policies/             (P15-S9 + P2) — Calico CNI per-tenant deny-cross
└── ci/                           (P15-S9) — argocd / flux config
```

## Cluster topology (FPT Cloud HCM)

Theo `docs/strategic/SAD_SKELETON_V2.md` Phần 5.1:
- **Production:**
  - 6 nodes general (8 CPU, 32 GB)
  - 4 nodes compute (16 CPU, 64 GB) cho heavy workload (Process Mining, training)
  - 3 nodes storage (4 CPU, 64 GB, large SSD)
- **Staging:** 3 nodes general (smaller).
- **Development:** local minikube hoặc shared dev cluster.

CNI: Calico (network policies for tenant isolation Phase 2). Ingress: NGINX Ingress Controller.

## Deployment strategy

- **Image registry:** GitHub Container Registry hoặc FPT Cloud Container Registry.
- **CI/CD:** GitHub Actions build + push image → ArgoCD/Flux pull + deploy to cluster.
- **Config:** Kustomize overlay per env; secrets via Vault Agent Injector (sidecar).
- **Rollout:** RollingUpdate default; canary cho high-risk service (ai-orchestrator, workflow-engine).

## Observability bootstrap

OTel Collector DaemonSet trên mỗi node. Jaeger / Prometheus / Loki / Grafana chạy stateful. Phase 1.5 same cluster; Phase 2 đánh giá managed observability (Grafana Cloud) nếu chi phí < self-host.

## DR (Phase 2+)

- Region 2 Hà Nội (FPT Cloud HN) hoặc Viettel IDC active-active Phase 2.
- Cross-region backup MinIO → MinIO replication.
- Postgres streaming replication cross-region.

## References

- ADR-0010 (`docs/adr/0010-modular-monolith-then-microservices.md`)
- ADR-0016 (`docs/adr/0016-fpt-viettel-vn-hosting.md`)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.1 + Phần 39-40
- `docs/BACKLOG_V4.md` P15-S9 (K8s deploy)
- Memory `project_pilot_deployment.md` (laptop pilot Option C — không touch Phase 1)

## D1 progress (2026-05-08)

- [x] `helm-charts/kaori-services/` umbrella chart — Chart.yaml, values.yaml, 4 templates, _helpers.tpl, README
- [x] `kustomize/base/kustomization.yaml` placeholder
- [x] `kustomize/overlays/{dev,staging,production}/kustomization.yaml`
- [ ] Per-chart smoke test `helm lint` + `helm template` (deferred until helm CLI installed locally)
- [ ] Sub-charts for kaori-infra (Postgres/Redis/Kafka), Vault, Temporal, ClickHouse, OTel stack — D2/D3/D8 of P15-S9
- [ ] ArgoCD app-of-apps wiring — later

See `helm-charts/kaori-services/README.md` for chart-specific docs and acceptance checklist.
