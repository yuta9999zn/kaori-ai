# `kaori-vault` Helm chart — Vault HA on K8s

> **Status:** Phase 1.5 P15-S9 D2 scaffold (Helm values + policies, not deployed)
> **Reference:** `docs/archive/sprint/p15-s9/P15-S9_PLAN.md` D2
> **Invariant:** K-18 (Phase 1.5+ — Vault is the only secret store)

## What this chart deploys

3-node Vault Raft cluster on K8s with:
- TLS-encrypted listener (K-18)
- KMS auto-unseal (FPT Cloud KMS via AWS-compatible API in production)
- Pod anti-affinity → replicas on 3 different nodes
- Audit log to PV → sidecar tails into Loki
- Vault Agent Injector enabled for future sidecar pattern adoption
- Service registration via K8s API (active/standby reflected on Service)

## Layout

```
infrastructure/vault/
├── docker-compose.yml          ← Phase 1 dev mode (still here for laptop testing)
├── helm/                       ← THIS FOLDER (Phase 1.5+)
│   ├── Chart.yaml
│   ├── values.yaml
│   └── README.md
├── policies/                   ← .hcl policies applied via init job after first unseal
│   ├── platform-admin.hcl
│   ├── tenant-template.hcl
│   └── service-readonly.hcl
└── auth-methods/
    ├── approle.json            ← service-to-Vault auth bootstrap
    └── jwt.hcl                 ← JWT bind to Kaori RS256 (Phase 1.5)
```

## Bootstrap flow

```
1. helm install kaori-vault ./infrastructure/vault/helm
2. Wait for first pod ready: kubectl wait --for=condition=ready pod/vault-0 -n vault
3. Init: kubectl exec vault-0 -- vault operator init -key-shares=5 -key-threshold=3
   → Save 5 unseal keys + initial root token to KMS-encrypted file (off-cluster)
4. Auto-unseal kicks in via KMS — vault-0 should report Sealed=false
5. Join vault-1, vault-2 to Raft: kubectl exec vault-1 -- vault operator raft join https://vault-0.vault-internal:8200
6. Apply policies: vault policy write platform-admin policies/platform-admin.hcl (× 3 policies)
7. Enable approle: vault auth enable approle
8. Configure approle from auth-methods/approle.json
9. Run scripts/vault_import.py to migrate Phase 1 .env secrets into Vault paths
10. Roll auth-service + Python services to read from Vault (Vault env wiring already in
    deployments via _helpers.tpl vaultEnv include — see kaori-services chart)
```

Steps 1-9 belong in a runbook; Phase 1.5 D2 ships the values + policies, not
the runbook proper. `docs/runbooks/vault-rotation.md` is its companion.

## Smoke verify locally

```powershell
helm dependency update infrastructure/vault/helm
helm template kaori-vault infrastructure/vault/helm > rendered.yaml
helm lint infrastructure/vault/helm
```

(Same caveat as kaori-services — helm CLI not installed locally yet.
YAML scaffold lints clean by Python `yaml.safe_load_all`.)

## Why HA + Raft (not Consul backend)?

- Raft is built into Vault — no extra HA layer to operate.
- Consul as Vault backend was the old standard; HashiCorp now recommends
  Raft for new deployments (smaller blast radius, simpler ops).
- 3 replicas survives 1 node loss; 5 replicas Phase 2 if we need
  cross-AZ tolerance.

## Why KMS auto-unseal (not Shamir manual)?

- Manual Shamir = 3 humans need to be online whenever Vault restarts.
  That's a single-point-of-human bottleneck and incompatible with K8s
  autoscaling rollovers.
- KMS unseal = restart safely without human in the loop. Trust shifts
  from "humans hold key shares" to "cloud KMS holds wrapping key" —
  acceptable tradeoff for SaaS.
- For air-gapped self-hosted (Phase 3), KMS unseal won't be available;
  Shamir is the only option there. Different deployment profile.

## What's NOT here

- **Vault Agent sidecar templates** — Phase 2; for Phase 1.5 we read via
  the Python `kaori_vault.py` wrapper directly.
- **Tenant policies** — generated dynamically per-tenant on onboard,
  templated from `policies/tenant-template.hcl`.
- **Disaster recovery replication** — Vault Enterprise feature; not in
  scope until self-hosted enterprise tier (Phase 3).

## See also

- `infrastructure/vault/policies/*.hcl` — applied policies
- `infrastructure/vault/auth-methods/approle.json` — service auth config
- `scripts/vault_import.py` — Phase 1 env-var → Vault path migration
- `services/*/shared/kaori_vault.py` — Python client wrapper (P1-S2 contract surface)
- `docs/runbooks/vault-rotation.md` — rotation procedure (Phase 1.5+)
- ADR-0010 / ADR-0013 — secrets management context
