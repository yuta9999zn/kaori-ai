# `infrastructure/k8s/` — Kubernetes manifests (P15-S9 onwards)

> **Status:** D1 scaffolding landed 2026-05-08; **AWS-EKS hardening pass 2026-07-05** — chart wired end-to-end + security/autoscaling/network/migration scaffolding added, validated (helm lint + `helm template` + kubeconform strict; base 20/20, AWS overlay 37/37 valid). Cluster still NOT provisioned. **Read `docs/runbooks/aws-eks-readiness.md` first** — it has the premortem, red-team, feasibility, cost line, cutover checklist, and the open hosting/Vault/LLM decisions.
> **Sprint:** P15-S9 (Phase 1.5 Sprint 9) — see `docs/archive/sprint/p15-s9/P15-S9_PLAN.md` D1.
> **Decision:** ADR-0016 (FPT/Viettel VN hosting) — ⚠️ conflicts with an AWS target (data residency); a superseding ADR is required before a real AWS cutover (see runbook §7 D1). ADR-0010 (modular monolith Phase 1 — K8s onboard Phase 1.5 to avoid pilot disruption).
>
> **AWS render:** `helm template kaori helm-charts/kaori-services -f helm-charts/kaori-services/values.yaml -f helm-charts/kaori-services/values-aws-eks.yaml -n kaori`. Everything cloud-specific is gated (default OFF) so the dev/staging/prod render is unchanged; `values-aws-eks.yaml` turns on securityContext, IRSA, HPA, PDB, NetworkPolicy, S3 blobs, and the migration Job.

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

## D1 progress (2026-05-08) + AWS hardening (2026-07-05)

- [x] `helm-charts/kaori-services/` umbrella chart — Chart.yaml, values.yaml, templates, _helpers.tpl, README
- [x] `kustomize/base/kustomization.yaml` placeholder
- [x] `kustomize/overlays/{dev,staging,production}/kustomization.yaml`
- [x] **`helm lint` + `helm template` smoke test** — passes; `kubeconform -strict` (k8s 1.28) base 20/20, AWS 37/37 valid
- [x] **End-to-end service wiring** (datastore + service URLs + secrets ported from docker-compose) — was previously LOG_LEVEL-only
- [x] **Security scaffolding** — PSA-restricted securityContext, IRSA ServiceAccounts, HPA, PDB, deny-by-default NetworkPolicy, topologySpread
- [x] **Pre-upgrade migration Job** (Flyway hook — decouples the 138 migrations from replica boot)
- [x] **`values-aws-eks.yaml`** — AWS overlay (ECR, RDS/ElastiCache/MSK/S3, IRSA, prod profile)
- [x] **`docs/runbooks/aws-eks-readiness.md`** — premortem/red-team/feasibility + cutover checklist
- [ ] Bake `config/etl/utils/kafka-schemas` into Python images (premortem A1 — CI/Dockerfile change, blocks EKS image build)
- [ ] CI build+push per-service to ECR by git SHA + `kaori-migrations` image
- [ ] Sub-charts for kaori-infra — **superseded on AWS by managed RDS/ElastiCache/MSK/S3** (runbook §3)
- [ ] ArgoCD app-of-apps wiring — later

See `helm-charts/kaori-services/README.md` for chart-specific docs and acceptance checklist.
