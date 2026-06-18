# `infrastructure/vault/` — HashiCorp Vault (P1-S2 dev, P15-S9 prod)

> **Status:** skeleton folder. **Sprint P1-S2** dev mode; **P15-S9** HA prod.
> **Invariant:** K-18 (Phase 1.5+ — Vault is the only secret store).

## Why Vault

Phase 1 v3 dùng env vars + `KAORI_MFA_KEY` rotation thủ công. v4 chuyển sang Vault để:
- Centralised rotation (90-day API keys, 365-day encryption keys).
- Audit trail mọi access (auth-service đọc `mfa_secret_enc` key cũng audit).
- Per-tenant secret path → tenant API keys + OAuth tokens + DB credentials không trộn lẫn.

## Phase 1 dev (P1-S2)

```
infrastructure/vault/
├── README.md                     ← this file
├── docker-compose.yml            (P1-S2) — Vault dev mode (in-memory, single node)
├── policies/                     (P1-S2) — Vault policy templates
│   ├── platform-admin.hcl        ← platform admin secrets
│   ├── tenant-template.hcl       ← per-tenant template (interpolated when tenant onboard)
│   └── service-readonly.hcl      ← workflow worker read-only access
├── auth-methods/                 (P1-S2)
│   ├── approle.json              ← service auth via AppRole
│   └── jwt.hcl                   ← JWT auth bind to Kaori RS256 (Phase 1.5)
└── helm/                         (P15-S9) — Vault HA 3-node Raft consensus prod
```

## Path layout

```
secret/
├── platform/
│   ├── llm/                      ← Anthropic key, OpenAI key (admin manage)
│   ├── notification/             ← SMTP, Twilio, SendGrid
│   └── infra/                    ← S3 root creds, Postgres root, Temporal admin
├── tenant/{tenant_id}/
│   ├── api_keys/                 ← tenant's external API keys (CRM, ERP, ...)
│   ├── oauth_tokens/             ← Google/Microsoft tokens for connectors
│   ├── db_credentials/           ← per-tenant Postgres creds (Phase 2 if needed)
│   └── connectors/               ← Misa, Fast, Zalo Business credentials
└── service/
    ├── auth-service/
    ├── data-pipeline/
    └── workflow-engine/
```

## Migration path từ env vars

- Phase 1 v4 (P1-S2): deploy Vault dev mode + viết wrapper `kaori_vault.get(path)`. Existing env vars **vẫn dùng**, KHÔNG migrate ngay.
- Phase 1.5 (P15-S9): production Vault cluster + migrate platform secrets (LLM keys, SMTP). Tenant secrets onboard khi connector new ship.
- Phase 2: tất cả env-var secrets retire; `SPRING_PROFILES_ACTIVE=production` block start nếu Vault unreachable.

## MFA key rotation (current K-18 path)

`KAORI_MFA_KEY` đang là env var (CLAUDE.md §15 v2.5.0). Phase 1.5 migrate sang Vault path `secret/platform/infra/mfa-master-key`. Rotation procedure không đổi — chỉ source thay.

## Operational notes

- **Unseal:** Phase 1 dev = auto-unsealed; Phase 1.5+ = AWS KMS / FPT Cloud KMS auto-unseal. Manual unseal là red flag (single point of human bottleneck).
- **Audit log:** ship sang Loki (separate stream `vault-audit`). Retention 2 năm.
- **Performance:** Vault throughput ~1000 req/s mỗi node. Phase 1 không phải bottleneck.

## References

- ADR-0010 (`docs/adr/0010-modular-monolith-then-microservices.md`)
- `docs/strategic/SAD_SKELETON_V2.md` Phần 5.3 (Secrets Management)
- CLAUDE.md K-18 + §15 (MFA Key Management — current state)
- Runbook (Phase 1.5): `docs/runbooks/vault-rotation.md` (TBD)
- `docs/BACKLOG_V4.md` P1-S2 (Vault setup)
