# AWS EKS Readiness — Kaori AI

> **Status:** manifests hardened + validated 2026-07-05 (helm lint + `helm template` + kubeconform strict on k8s 1.28; base 20/20, AWS overlay 37/37 valid). Cluster NOT provisioned — this is "AWS-ready", not "on AWS". A live smoke test needs anh's AWS account creds.
> **Scope:** application layer (`infrastructure/k8s/helm-charts/kaori-services`). Data plane is managed (RDS/ElastiCache/MSK/S3), not in-cluster.
> **Supersedes for AWS target:** the FPT-only assumption in ADR-0016 — see "Open decisions" D1 below; a new ADR is required before a real cutover.

This runbook is the output of a review + premortem + red-team + feasibility pass. It records what was wrong, what got fixed in the chart, what the operator still must do per-account, and the business decisions that are anh's to make (not engineering's).

---

## 1. What changed in this pass (chart remediation)

All additive + gated (default OFF) → the existing dev/staging/prod render is byte-identical; `values-aws-eks.yaml` turns the cloud features on.

| Area | Before | After |
|---|---|---|
| Service wiring | `env:` had only `LOG_LEVEL` — pods would start "healthy" but reach nothing (premortem A2) | Full datastore + service-URL + secret wiring ported from `docker-compose.yml` via `global.datastore` + per-service `env`/`extraEnv`; repoint Postgres/Redis/Kafka/blob by overriding globals once |
| Secrets | `{svc}-secrets` referenced but never created; plaintext temptation in `values.yaml` | Shared `kaori-shared-secret` via `secretKeyRef`; chart never commits values (create=false → External Secrets Operator syncs from AWS Secrets Manager). `optional=false` in prod → missing key fails loud (C1) |
| Pod security | containers ran as root, no securityContext (rejected by PSA `restricted`) | `runAsNonRoot`, drop ALL caps, `seccompProfile: RuntimeDefault`, `allowPrivilegeEscalation: false` — PSA-restricted compliant |
| IAM | none | IRSA ServiceAccounts (shared + narrower S3 roles for data-pipeline/ai-orchestrator) — keyless S3/Secrets Manager access |
| Autoscaling | fixed replicas | HPA per service (CPU+mem); notification-service excluded on purpose (single-instance outbox poller — A5) |
| Availability | none | PodDisruptionBudget (survive node-group upgrades) + topologySpread across AZs |
| Network | flat pod network (B1/B2) | deny-by-default NetworkPolicy + DNS/intra-ns/datastore/443 allows; 169.254.0.0/16 (IMDS) egress denied |
| Migrations | Flyway on every auth-service replica boot — races the lock (A4); nothing applies the 138 migrations to RDS (B1) | pre-install/pre-upgrade Helm-hook Job runs Flyway once; `SPRING_FLYWAY_ENABLED=false` on auth in prod |
| Blob store | shared RWX volume (impossible on EBS/RWO — A3) | `BLOB_STORE_BACKEND=s3` (S3BlobStore already in `shared/blob_store.py`) |
| notification rollout | default RollingUpdate → 2 pollers overlap → double-send | `strategy: Recreate` |

Validated with: `helm lint`, `helm template` (base + `-f values-aws-eks.yaml`), `kubeconform -strict -kubernetes-version 1.28.0`, and a semantic pass (no duplicate env keys, PSA-restricted on every workload).

---

## 2. Premortem — why an AWS deploy could still fail (ranked)

⚠️ = "dies on day 1 if deployed as-is"; these must be closed before a real cutover.

**⚠️ A1 — App images don't bake `config/`, `etl/`, `utils/`, `kafka/schemas/`.**
The Python Dockerfiles volume-mount these from the repo root in compose; on EKS there is no repo root, so `LANGUAGE_DICT_PATH=/app/config/language_dictionary.json` is absent and the schema registry can't load → CrashLoop / silent ingest failure. **Fix is a Dockerfile/CI change, not a manifest one** (bake the dirs into the image, or ship them as a ConfigMap/initContainer). Blocks image build for EKS. *Owner: build/CI.*

**⚠️ A2 — Service wiring.** Closed in this pass (§1).

**⚠️ B1 — No data plane.** Closed by decision: managed RDS/ElastiCache/MSK/S3 (§3). The chart no longer expects in-cluster Postgres/Kafka.

**⚠️ C1 — Secrets silently missing.** Closed: prod overlay sets `secrets.optional=false`.

**B2 — RLS + RDS Proxy.** K-1 tenant isolation uses a per-connection GUC (`acquire_for_tenant`). RDS Proxy multiplexes sessions and can leak/reset that GUC → cross-tenant read or empty results. **Do NOT put RDS Proxy in front of the RLS path** without session-pinning tests. Run the RLS integration suite against an RDS staging instance before cutover.

**B4 — Vault dev-mode = data loss.** Compose runs `vault server -dev` (in-memory). Lifting that to prod means one pod restart wipes every tenant field key → all column-encrypted data (TOTP, K-18 field crypto) becomes undecryptable. Prod needs Vault HA Raft + KMS auto-unseal, or replace the Vault wrapper's backend with AWS Secrets Manager. This is real data loss, not downtime.

**A6 — Ollama/Qwen needs a GPU.** Qwen 2.5 14B needs ~10–12 GB VRAM. CPU-only inference times out (the pilot 7B box already cuts `NARRATIVE_MAX_TOKENS` to 128). The AWS overlay points `OLLAMA_HOST` at an in-cluster `ollama.llm` service you must back with a **GPU node group** (g5, Karpenter scale-to-zero when idle) — or accept the vendor path per tenant consent. Cost note in §4.

**D5 — Probe paths.** `values.yaml` probes `/health/ready` (Python) and `/actuator/health/readiness` (auth). Confirm each exists in the live router (compose only probed `/health`) before trusting readiness gating.

---

## 3. Managed data plane (feasibility posture)

A 1-dev team should not self-run stateful services on EKS. Map:

| Compose service | AWS managed | Notes |
|---|---|---|
| postgres (pgvector) | **RDS PostgreSQL 15** + `pgvector` | Enable extension; match HNSW index version (mig 067). Avoid RDS Proxy on the RLS path (B2). |
| redis | **ElastiCache Redis 7** | TLS (`rediss://`). |
| kafka + zookeeper | **MSK** (or MSK Serverless) | Turn OFF auto-create; create topics as a Job (naming in `EVENT_BACKBONE.md`). Or drop Kafka this phase — Redis Streams is already the v4 backbone (B3). |
| minio | **S3** | `BLOB_STORE_BACKEND=s3`; bucket `kaori-prod-blobs`; access via IRSA. |
| vault (dev) | **Vault HA + KMS unseal** or **Secrets Manager** | See B4. |
| prometheus/tempo/grafana | **AMP + AMG** or ADOT + CloudWatch | Managed observability > self-host for a small team (D4). |

Secrets flow: **AWS Secrets Manager → External Secrets Operator → `kaori-shared-secret`**. The chart consumes it; it never creates it in prod.

---

## 4. Cost & the "don't turn it on yet" line

Rough monthly baseline (ap-southeast-1, on-demand): EKS control plane ~$73 + 3× m5.large ~$210 + RDS ~$60 + ElastiCache ~$25 + MSK ~$150 + NAT ~$35 = **~$550/mo**, before a GPU node (~$700/mo for one g5). That is ~14–33M VNĐ/mo against a PILOT plan of 1M VNĐ/customer with 1–3 customers today.

**Recommendation:** keep the manifests AWS-ready (this sprint's goal) but do **not** stand the cluster up until paying customers cover the burn. An intermediate step — a single EC2 running `docker-compose` — bridges demo/first-customer without EKS ops. The cluster is a Phase-3 move, gated on customer count, not a pilot move.

---

## 5. Red-team highlights (defense-in-depth added / still open)

- **Internal services trust `X-*` JWT headers from the gateway (K-7).** If any internal Service ever gets `type: LoadBalancer`, an attacker forges `X-Tenant-Id` and bypasses K-12. *Mitigated:* NetworkPolicy denies external reach to internal pods; keep all internal services `ClusterIP`. *Still worth doing:* a gateway→service shared signature so header trust isn't purely network-based.
- **SSRF → node IAM role.** Workflow `call_api`/`read_api` nodes (SSRF-hardened in commit b37515f) + EKS IMDS. *Mitigated:* NetworkPolicy egress denies 169.254.0.0/16. *Operator must also:* enforce **IMDSv2 + hop-limit 1** on the node group.
- **Secrets at rest.** Enable **EKS envelope encryption (KMS)** for Secrets; RBAC-restrict `get secret`.
- **Ingress DoS / cost bomb.** 100 MB body + Excel's ~10× in-memory blow-up = guaranteed OOMKill of data-pipeline. *Operator must add:* ingress rate-limiting + WAF + a smaller unauthenticated body cap.
- **Telegram webhook** (`webhook.kaori.ai/webhook/telegram`) is unauthenticated public. Verify the Telegram secret token in-app so forged callbacks can't drive the REL-011 saga.
- **Never ingress-expose** Grafana/Prometheus/Swagger/Kafka-UI (default/no auth → cross-tenant metric + topic leak). Cluster-internal + SSO only.
- **PII residency.** Egress NetworkPolicy allowlists 443 for the consent path; K-4/K-5 masking stays the app-layer guard. Note the residency conflict in D1.

---

## 6. Operator cutover checklist (per AWS account)

1. **Build images incl. config bake (A1)** + push per-service to ECR by git SHA (no mutable tags). Add a `kaori-migrations` image: `FROM flyway/flyway` + `COPY infrastructure/postgres/migrations /flyway/sql`.
2. Provision (Terraform/eksctl): VPC, EKS 1.28+, 3-AZ node group, RDS 15+pgvector, ElastiCache, MSK (or skip), S3 bucket, Secrets Manager entries, KMS key, IRSA roles (`kaori-services`, `kaori-data-pipeline`, `kaori-ai-orchestrator`).
3. Install cluster add-ons: VPC-CNI network-policy, AWS Load Balancer Controller (or ingress-nginx), cert-manager, External Secrets Operator, ADOT/observability, (optional) Karpenter + GPU node group for Ollama.
4. Fill every `<FILL_*>` in `values-aws-eks.yaml` from Terraform outputs (account id, ECR, RDS/ElastiCache/MSK endpoints, VPC CIDR, git SHA, IRSA ARNs).
5. Enable IMDSv2 hop-limit 1 on the node group.
6. `helm upgrade --install kaori . -n kaori -f values.yaml -f values-aws-eks.yaml` — the migration Job runs first (pre-install hook), then app pods.
7. Smoke: RLS integration suite against RDS (B2), auth login + SSO redirect URIs, an upload round-trip (S3 blob), a workflow run, trace visible in observability.

---

## 7. Open decisions (anh's call, not engineering's)

- **D1 — Hosting / data residency.** ADR-0016 chose FPT/Viettel VN for residency (Nghị định 13/2023). AWS ap-southeast-1 (Singapore) puts VN customer data offshore. Decide: AWS for demo/international + FPT for residency-strict tenants? Accept SG with a DPA? Write the superseding ADR **before** a real cutover.
- **D2 — When to turn the cluster on** (customer-count threshold — §4).
- **D3 — Vault mode** (HA Raft+KMS vs Secrets Manager backend — B4).
- **D4 — LLM serving** (GPU node group vs vendor-consent vs smaller model — A6).

---

## References
- Chart: `infrastructure/k8s/helm-charts/kaori-services/` (`values.yaml`, `values-aws-eks.yaml`)
- `docker-compose.yml` (wiring source of truth)
- `services/ai-orchestrator/shared/blob_store.py` (S3 backend)
- ADR-0016 (hosting) · ADR-0037 (blob store) · CLAUDE.md §4 (K-1/K-7/K-12/K-18), §15 (key management)
- Migrations: `infrastructure/postgres/migrations/` (135 files, max 138)
