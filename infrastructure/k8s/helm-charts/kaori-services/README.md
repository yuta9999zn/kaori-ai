# `kaori-services` — Helm umbrella chart for application layer

> **Status:** Phase 1.5 P15-S9 D1 scaffold (no production deploy yet)
> **Owner:** anh
> **Reference:** `docs/archive/sprint/p15-s9/P15-S9_PLAN.md` D1

This chart deploys the 6 application services (api-gateway, auth-service,
data-pipeline, ai-orchestrator, llm-gateway, notification-service) onto a
Kubernetes cluster. Infrastructure (Postgres, Redis, Kafka, Vault, Temporal,
ClickHouse) deploys via separate charts under `infrastructure/k8s/helm-charts/`
and `infrastructure/{vault,temporal,clickhouse}/helm/`.

## Layout

```
kaori-services/
├── Chart.yaml             ← chart metadata
├── values.yaml            ← per-service config (the "what" — image, replicas, env, probes, ingress)
├── templates/
│   ├── _helpers.tpl       ← label generators, image string composer, OTel/Vault env injectors
│   ├── deployments.yaml   ← one Deployment per services.<name>.enabled=true
│   ├── services.yaml      ← matching ClusterIP Service
│   ├── configmaps.yaml    ← common ConfigMap (KAORI_ENV, service name, tracing on/off)
│   └── ingress.yaml       ← Ingress when services.<name>.ingress.enabled=true
└── README.md              ← this file
```

## Design choice: 1 umbrella chart, not 6 sub-charts

Each service shares the same shape (Deployment + Service + ConfigMap +
optional Ingress). 6 sub-charts = 6 × the same template + 6 × `helm install`.
Umbrella iterates over `services.*` in values, so adding a service =
add a values entry, no template change.

When a service grows specific needs (StatefulSet, init containers, custom
volumes), peel it off into a sub-chart at that point — not pre-emptively.

## Smoke verify locally (no cluster needed)

```bash
cd infrastructure/k8s/helm-charts/kaori-services
helm template kaori . > /tmp/rendered.yaml
# Should produce ~6 Deployments + 6 Services + 6 ConfigMaps + 2 Ingresses
# (api-gateway + notification-service are the only ingress-enabled).

# Lint:
helm lint .
```

If `helm` isn't installed locally, the charts are still pure-text YAML
templates, anh review by reading `templates/*.yaml` + cross-checking with
`values.yaml`.

## Per-environment overrides via Kustomize

Helm renders the base manifests; Kustomize overlays at
`infrastructure/k8s/kustomize/overlays/{dev,staging,production}/` patch
per-env values:

- `dev` — replicas=1, debug log level, in-cluster Postgres
- `staging` — replicas=2, sample tenants only, NetworkPolicy in audit mode
- `production` — replicas=3+ for gateway/auth/data, NetworkPolicy enforced

Render pipeline (Phase 1.5+ ArgoCD):

```
kustomize build kustomize/overlays/production
  | helm-template-hook (passes through `helm template kaori-services` first)
  | kubectl apply -f -
```

Phase 1.5 D1 starts simpler — `helm install` directly with `-f overlays/<env>/values.yaml`.

## What's NOT in this chart

- **Stateful infra** — Postgres, Redis, Kafka belong in `kaori-infra/`
- **Vault** — separate chart (`infrastructure/vault/helm/`)
- **Temporal** — separate chart (`infrastructure/temporal/helm/`)
- **ClickHouse** — separate chart (`infrastructure/clickhouse/helm/`)
- **OpenTelemetry collector + Jaeger + Prometheus + Loki + Grafana** — `infrastructure/k8s/helm-charts/otel-stack/`
- **Frontend** — `frontend` directory; deploys via separate static-site chart Phase 2 when frontend resumes

Each service includes its OTel env vars + Vault env vars via the
`_helpers.tpl` includes (K-19 — every service must export traces with
tenant_id span attribute; K-18 — secrets via Vault Phase 1.5+).

## Image source

Default registry: `ghcr.io/yuta9999zn` (GitHub Container Registry, free
for public repos). Production overlay swaps to FPT Cloud Container Registry
when commercial contract active.

Image tag pinned to `v4.0-phase1-complete` in base; overlays bump tag
per release.

## Acceptance for D1

- ☐ `helm lint kaori-services` clean
- ☐ `helm template kaori-services` renders 6 Deployments + 6 Services + 6 ConfigMaps + 2 Ingresses without error
- ☐ Each rendered Deployment has all required pod fields (image, ports, probes, resources, env)
- ☐ K-19 OTel env vars present in every pod
- ☐ K-18 Vault env vars present in every pod
- ☐ Per-service replicas + resources match `values.yaml` (no copy-paste errors)
- ☐ Documented per ADR (will write `docs/adr/0020-fpt-cloud-deployment-topology.md` next)

## See also

- `docs/archive/sprint/p15-s9/P15-S9_PLAN.md` D1 deliverable
- `docs/adr/0010-modular-monolith-then-microservices.md` — extraction strategy (Phase 2 microservices live separately, this chart is for Phase 1 modular monolith)
- `docs/adr/0016-fpt-viettel-vn-hosting.md` — VN region hosting choice
- `infrastructure/k8s/README.md` — overall K8s plan
- `infrastructure/temporal/README.md` — Temporal chart (deploys separately)
- `infrastructure/vault/README.md` — Vault chart
- `infrastructure/clickhouse/README.md` — ClickHouse chart
