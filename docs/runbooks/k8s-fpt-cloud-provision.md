# Kubernetes cluster on FPT Cloud — first-time provisioning

> **Status:** Helm charts + Kustomize overlays ready since P15-S9 D1 (commit `783a9ac` 2026-04-XX). Cluster deploy deferred since pilot Olist runs fine on docker-compose; anh provisions FPT Cloud when pilot scales OR customer #2 onboards. This runbook is the activation procedure.
> **Decision:** ADR-0016 (FPT/Viettel VN hosting — data residency) · ADR-0010 (K8s onboarded Phase 1.5 to avoid pilot disruption)
> **Sprint reference:** `docs/archive/sprint/p15-s9/P15-S9_PLAN.md` D1 + D8

## What's currently shipped

| Component | State | Where |
|---|---|---|
| `kaori-services` umbrella Helm chart (6 apps) | Ready | `infrastructure/k8s/helm-charts/kaori-services/` |
| `kaori-infra` umbrella (Postgres CNPG, Redis cluster, Kafka, Ollama) | Ready | `infrastructure/k8s/helm-charts/kaori-infra/` |
| Per-system charts (Vault HA, Temporal, ClickHouse, MinIO, otel-stack) | Ready (skeleton or wrapper) | same dir, sibling folders |
| Kustomize overlays (dev / staging / production) | Ready | `infrastructure/k8s/kustomize/overlays/` |
| Image build → GHCR push CI | Ready (`docker-smoke` workflow) | `.github/workflows/docker-smoke.yml` |
| Network policies (Calico cross-tenant deny) | **Phase 2 — disabled in base** | `network-policies/` (planned) |
| FPT Cloud Container Registry credentials | **Not provisioned** | Vault path `platform/fpt-cloud/cr-credentials` (target) |
| Production kubeconfig | **Not provisioned** | Vault path `platform/fpt-cloud/kubeconfig-prod` (target) |
| `cert-manager` for Let's Encrypt | **Not provisioned** | install via separate Helm chart |
| `ingress-nginx` controller | **Not provisioned** | install via separate Helm chart |

## When to provision

Trigger any of:
- Pilot Olist load > **20 concurrent users** during peak — docker-compose on anh's laptop saturates CPU
- Customer #2 onboards — em can't run two pilot tenants on one local stack without IP / DNS collisions
- SOC 2 readiness clock starts (Phase 2 prep) — auditors want isolated infrastructure with documented controls
- Vault HA needed (Phase 2 secret-rotation cadence requires HA, not the dev container live since 2026-05-18)

If none apply, **keep running docker-compose**. Every cluster em don't run is one less thing to debug on-call.

## Step 1 — FPT Cloud commercial contract

1. Anh contacts FPT Smart Cloud sales: <https://fptsmartcloud.com> → "Liên hệ tư vấn"
   - Em recommend: ask for the **Managed Kubernetes (FKE)** product + **Object Storage** + **Container Registry** bundle, HCM region (Phase 1 customer = Olist HCM-based; data residency satisfied)
2. Sign-up requires VN business registration (giấy phép kinh doanh). Pilot-mode billing ~5-10M VND/tháng for 3-node cluster + 100 GB block storage.
3. Wait for tenant ID + IAM admin credentials email (typically 1-3 business days)
4. Save credentials in 1Password / Vault target paths:
   - `platform/fpt-cloud/iam/admin_email`
   - `platform/fpt-cloud/iam/admin_password` (rotate immediately on receipt)
   - `platform/fpt-cloud/tenant_id`

## Step 2 — Cluster provisioning (FPT FKE portal)

1. Log into <https://hcm-3.console.fptcloud.com> → **Container Service** → **Kubernetes Engine** → **+ Create Cluster**
2. Cluster config:
   - **Name**: `kaori-prod-hcm` (matches `production` Kustomize overlay namespace target)
   - **K8s version**: pick LATEST stable (em test against 1.28 per CLAUDE.md §2; if FPT defaults higher, fine — em are version-agnostic in Helm templates)
   - **Network**: VPC + default subnet 10.0.0.0/16 (em don't peer with anything external Phase 1.5)
   - **CNI**: Calico (matches em's network-policies/ plan for Phase 2 cross-tenant deny)
3. Node pool sizing (3-node minimum for HA, all in same AZ — Phase 2 multi-AZ):

   | Pool | Count | vCPU | RAM | Disk | Purpose |
   |---|---|---|---|---|---|
   | `general` | 3 | 4 | 16 GB | 100 GB SSD | api-gateway, auth, data-pipeline, ai-orch, llm-gateway, notification (6 apps × replicas) |
   | `ollama` (optional) | 1 | 8 | 32 GB | 200 GB SSD | Qwen 2.5:14b + Qwen2.5-VL:7b — heavy, avoid co-tenant noise |
   | `stateful` | 3 | 4 | 16 GB | 500 GB SSD | Postgres CNPG, Redis cluster, Kafka, Vault, ClickHouse (taint = `stateful=true`, schedule via toleration) |

   Total Phase 1.5 cost estimate: ~15-20M VND/tháng (~$600-800 USD) — confirm w/ FPT sales.
4. Click **Create** → wait ~10-15 min for the cluster to provision
5. **Download kubeconfig** from cluster overview page. Store at `~/.kube/configs/fpt-prod.kubeconfig` + add to Vault `platform/fpt-cloud/kubeconfig-prod`

## Step 3 — Local kubectl + helm tooling

```powershell
# Windows / PowerShell — install via Chocolatey (one-time)
choco install kubernetes-cli kubernetes-helm kustomize

# Verify
kubectl version --client
helm version
kustomize version
```

Switch context to the new cluster:

```powershell
$env:KUBECONFIG = "$HOME/.kube/configs/fpt-prod.kubeconfig"
kubectl config use-context kaori-prod-hcm
kubectl get nodes    # expect 6-7 nodes Ready
```

## Step 4 — Install platform add-ons (cert-manager + ingress-nginx)

These are NOT in `kaori-services` chart — they're cluster-level concerns owned per-environment.

```powershell
# cert-manager (Let's Encrypt TLS for ingress)
helm repo add jetstack https://charts.jetstack.io
helm repo update
helm install cert-manager jetstack/cert-manager `
  --namespace cert-manager --create-namespace `
  --set installCRDs=true `
  --version v1.14.0

# ingress-nginx (the Ingress controller behind FPT's external load balancer)
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install ingress-nginx ingress-nginx/ingress-nginx `
  --namespace ingress-nginx --create-namespace `
  --version 4.10.0 `
  --set controller.service.type=LoadBalancer

# Verify ingress controller got a public IP from FPT
kubectl get svc -n ingress-nginx
# Wait for EXTERNAL-IP to populate (5-10 min)
```

Save the EXTERNAL-IP → point anh's DNS `api.kaori.io` + `app.kaori.io` A records at it.

## Step 5 — Deploy infra layer (Postgres + Redis + Kafka + Vault + Ollama)

Two paths — pick based on operational maturity:

**Path A (recommended for Phase 1.5)**: managed services where FPT offers them
- Postgres → FPT Cloud DBaaS Postgres 15 + pgvector extension (request via support ticket)
- Redis → FPT Cloud Redis 7
- Kafka → keep self-managed (Helm `kaori-infra/`) until Phase 2 scale forces escalation

**Path B (P15-S9 D1 default)**: everything via Helm

```powershell
# CloudNativePG operator (Postgres)
helm repo add cnpg https://cloudnative-pg.github.io/charts
helm install cnpg-operator cnpg/cloudnative-pg `
  --namespace cnpg-system --create-namespace

# Then deploy kaori-infra
helm dependency update infrastructure/k8s/helm-charts/kaori-infra
helm install kaori-infra infrastructure/k8s/helm-charts/kaori-infra `
  --namespace kaori --create-namespace `
  --values infrastructure/k8s/kustomize/overlays/production/infra-values.yaml
```

Verify each stateful pod healthy:
```powershell
kubectl get pods -n kaori -l role=stateful
kubectl logs -n kaori statefulset/postgres-primary --tail 50
```

## Step 6 — Vault HA + bootstrap

Vault dev container (commit `d6a1113` 2026-05-18) was single-node; production is HA 3-node:

```powershell
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault hashicorp/vault `
  --namespace vault --create-namespace `
  --values infrastructure/vault/helm/values-prod.yaml `
  --set server.ha.enabled=true `
  --set server.ha.replicas=3
```

After pods up, run the bootstrap script (initialises, unseals each replica, seeds the per-tenant paths em set up in dev):

```powershell
kubectl exec -n vault vault-0 -- /vault/bootstrap.sh
# Outputs root_token + unseal_keys — store in 1Password IMMEDIATELY
# Apply mig 084 grants — same SQL em ran in dev
```

See `docs/runbooks/vault-rotation.md` for per-tenant secret seed cadence.

## Step 7 — Deploy observability stack

```powershell
# Single Helm install brings up otel-collector + Jaeger + Tempo + Prometheus + Loki + Grafana
helm install otel-stack infrastructure/k8s/helm-charts/otel-stack `
  --namespace observability --create-namespace `
  --values infrastructure/k8s/kustomize/overlays/production/observability-values.yaml

# Grafana ingress at grafana.kaori.io — get admin password
kubectl get secret -n observability grafana-admin -o jsonpath='{.data.password}' | base64 -d
```

## Step 8 — Build + push images to FPT Container Registry

Em currently push to GHCR (`ghcr.io/yuta9999zn`). Production prefers FPT CR (lower latency + no public exposure):

```powershell
# Login to FPT CR (credentials from Step 1)
docker login registry.fptcloud.vn -u <username> -p <password>

# Re-tag + push latest GHCR images
foreach ($svc in @("api-gateway","auth-service","data-pipeline","ai-orchestrator","llm-gateway","notification-service")) {
  docker pull "ghcr.io/yuta9999zn/$svc:v4.0-phase1-complete"
  docker tag "ghcr.io/yuta9999zn/$svc:v4.0-phase1-complete" "registry.fptcloud.vn/kaori/$svc:v4.0-phase1-complete"
  docker push "registry.fptcloud.vn/kaori/$svc:v4.0-phase1-complete"
}

# Create imagePullSecret in kaori namespace
kubectl create secret docker-registry fpt-cr-creds `
  --namespace kaori `
  --docker-server=registry.fptcloud.vn `
  --docker-username=<username> `
  --docker-password=<password>
```

## Step 9 — Deploy kaori-services

```powershell
# Production overlay points imageRegistry → registry.fptcloud.vn/kaori
kubectl apply -k infrastructure/k8s/kustomize/overlays/production/

# Watch rollout
kubectl rollout status deployment/api-gateway -n kaori --timeout=5m
kubectl rollout status deployment/auth-service -n kaori --timeout=5m
kubectl rollout status deployment/data-pipeline -n kaori --timeout=5m
kubectl rollout status deployment/ai-orchestrator -n kaori --timeout=5m
kubectl rollout status deployment/llm-gateway -n kaori --timeout=5m
kubectl rollout status deployment/notification-service -n kaori --timeout=5m
```

## Step 10 — Smoke test through ingress

```powershell
# Each service should respond 200 via the public ingress
foreach ($svc in @("api-gateway:8080","auth-service:8091","data-pipeline:8092","ai-orchestrator:8093","llm-gateway:8095","notification-service:8094")) {
  $name, $port = $svc -split ":"
  Invoke-WebRequest "https://api.kaori.io/health/$name" -UseBasicParsing | Select-Object StatusCode
}
```

End-to-end gate: log into `https://app.kaori.io/login` with the admin user → run an upload through Stage 1-6 → see the pipeline_run reach `silver_complete`. If that works, anh's good to migrate the first customer.

## Step 11 — Data migration (dev → prod cutover)

Out of scope for first-time provisioning — see `docs/runbooks/dev-to-prod-data-cutover.md` (TODO em author when anh has staging cluster). Short version:
1. `pg_dump` dev Postgres → `pg_restore` into FPT-managed prod Postgres
2. Re-encrypt tenant field keys with prod Vault keys (`/p2/auth/field-key/reencrypt`)
3. Bronze MinIO bucket migration (MinIO mirror) — read-only freeze on dev during cutover
4. DNS swap + sticky-session drain

## Holster procedure (rollback to docker-compose)

```powershell
# If prod cluster is on fire and em needs to fall back:
# 1. Re-point DNS api.kaori.io → anh's static IP (pilot setup)
# 2. Start docker-compose on the pilot box
docker compose up -d
# 3. Restore latest pg_dump if customer data needs to come back
# 4. Customer-facing impact: 5-15 min outage during DNS TTL flush
```

Em recommend keeping the pilot box running for ~1 week after cluster go-live so the rollback path stays warm.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `kubectl get nodes` returns empty | Wrong kubeconfig context | `kubectl config get-contexts` → `use-context kaori-prod-hcm` |
| Ingress controller stuck Pending external IP | FPT Cloud LB quota | FPT support ticket — quota increase request; typically 1 LB per cluster default |
| `ImagePullBackOff` on services | imagePullSecret not in namespace | Re-run Step 8 final `kubectl create secret` block |
| Pods CrashLoopBackOff with `Connection refused` to Postgres | Postgres pod not ready when app started | `kubectl rollout restart` after Postgres pod becomes Ready; or add `initContainers` waiting on DB |
| Vault pods stuck Sealed | Bootstrap script not run after pod restart | `kubectl exec vault-N -- vault operator unseal <key>` per pod (3 unseal keys per pod) |
| All services 502 via ingress | cert-manager TLS not issued yet | `kubectl describe certificate -n kaori api-kaori-io` — Let's Encrypt rate limit if recently re-issued; wait or use staging issuer |
| ai-orchestrator can't reach llm-gateway | Service name mismatch | `kubectl get svc -n kaori` — em uses `llm-gateway.kaori.svc.cluster.local`; check ConfigMap `LLM_GATEWAY_URL` env |
| Ollama pod OOMKilled | 32 GB node not enough for Qwen 14B + 7B-VL together | Either: (a) drop OCR_MODEL → use llava:7b 4-bit; OR (b) bump ollama node pool to 64 GB |

## What this runbook does NOT cover

- **FPT Cloud commercial pricing negotiation** — sales-side, ask for SaaS discount tier
- **SOC 2 control evidence collection** — separate compliance project, Phase 2
- **Multi-region failover** — Phase 3 (single-region HCM only for Phase 1.5+2)
- **Horizontal Pod Autoscaler tuning** — base values has placeholder HPA configs; tune after baseline load measured for ≥1 week
- **Per-tenant network policies** — Phase 2 enables Calico cross-tenant deny; until then `global.networkPolicy.enabled=false`
- **Disaster recovery (DR) cluster** — Phase 3 cold standby in second AZ (FPT Hà Nội)
- **Custom resource definitions for tenants** — Phase 3 SaaS operator pattern; today em uses Postgres RLS instead

## Related

- ADR-0010 — modular monolith Phase 1, K8s deferred to Phase 1.5 (`docs/adr/0010-modular-monolith-phase-1-microservices-phase-2.md`)
- ADR-0016 — FPT/Viettel VN hosting decision (`docs/adr/0016-vn-hosting-fpt-viettel.md`)
- `docs/runbooks/vault-rotation.md` — per-tenant Vault secret rotation
- `docs/runbooks/temporal-worker-cutover.md` — Temporal worker flip after cluster up
- `docs/runbooks/sso-microsoft-setup.md` — sibling activation pattern (config + restart, no code change)
- `infrastructure/k8s/README.md` — directory map + design decisions
