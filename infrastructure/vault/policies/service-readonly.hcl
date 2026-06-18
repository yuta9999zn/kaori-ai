# Vault policy: service-readonly
#
# Granted to backend services (data-pipeline, ai-orchestrator,
# llm-gateway, notification-service, workflow worker) via AppRole
# auth. Services need to READ secrets to operate but should never
# create/update — secret rotation is a deliberate admin operation,
# not a side effect of regular request handling.
#
# K-18 enforcement: all 4 application services bind this policy by
# default. If a service legitimately needs write access (e.g. the
# tenant onboarding flow writing connector OAuth refresh tokens), it
# requests a SEPARATE policy with narrow write scope, audited
# explicitly.
#
# Reference: docs/archive/sprint/p15-s9/P15-S9_PLAN.md D2; ADR-0013

# ---------------- Platform secrets — read only ----------------

path "secret/data/platform/llm/*" {
  capabilities = ["read"]
}

path "secret/data/platform/notification/*" {
  capabilities = ["read"]
}

path "secret/data/platform/infra/*" {
  capabilities = ["read"]
}

path "secret/data/platform/telegram/*" {
  capabilities = ["read"]
}

# ---------------- Service-specific read ----------------

# Each service reads its own service-scoped path (signing keys,
# encryption-at-rest keys). Service name is bound at the AppRole
# level via metadata so this template applies uniformly across
# services.

path "secret/data/service/{{identity.entity.aliases.service.metadata.service_name}}/*" {
  capabilities = ["read"]
}

# ---------------- Tenant secrets — read only ----------------

# Services need to read tenant connector creds to fulfil pipeline
# runs. Read only — connector creds are written by tenant onboard
# flow (separate policy) or by tenant admin via UI directly hitting
# the Vault Agent injection sidecar.

path "secret/data/tenant/+/oauth_tokens/*" {
  capabilities = ["read"]
}

path "secret/data/tenant/+/connectors/*" {
  capabilities = ["read"]
}

path "secret/data/tenant/+/api_keys/*" {
  capabilities = ["read"]
}

# ---------------- Self-token operations ----------------

path "auth/token/renew-self" {
  capabilities = ["update"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

# ---------------- Explicit deny on writes ----------------

# Services cannot create/update/delete any secret. Explicit deny
# overrides any inherited grant.

path "secret/+/platform/*" {
  capabilities = ["deny"]
  required_parameters = []
}
# Note: HCL doesn't support a single-rule create/update/delete deny
# without spelling each capability; the read-only grants above
# implicitly deny everything else. The two paths above are belt-and-
# suspenders for the most-sensitive paths.
