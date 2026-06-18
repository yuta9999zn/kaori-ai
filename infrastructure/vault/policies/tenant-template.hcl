# Vault policy template: tenant-{{tenant_id}}
#
# Generated PER TENANT on onboard — `{{tenant_id}}` is interpolated by
# the tenant provisioning script (Phase 1.5 P15-S9 follow-up). Granted
# to tenant MANAGER and ANALYST roles via JWT auth method binding.
#
# K-1 spirit: a tenant can ONLY access its own secret tree.
# Cross-tenant read is impossible at the Vault layer (deeper than
# Postgres RLS — even root token can't bypass without policy change).
#
# Reference: docs/archive/sprint/p15-s9/P15-S9_PLAN.md D2; ADR-0013

# ---------------- Own tenant secrets — full CRUD ----------------

path "secret/data/tenant/{{tenant_id}}/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/tenant/{{tenant_id}}/*" {
  capabilities = ["list", "read", "delete"]
}

# ---------------- Cross-tenant — explicit deny ----------------

# Belt-and-suspenders: even if a misconfigured upstream policy granted
# blanket read, this explicit deny would override.
path "secret/data/tenant/+/+" {
  capabilities = ["deny"]
}

path "secret/data/platform/*" {
  capabilities = ["deny"]
}

path "secret/data/service/*" {
  capabilities = ["deny"]
}

# ---------------- Self-token operations ----------------

# Tenant can renew + revoke its own token (lease management).
path "auth/token/renew-self" {
  capabilities = ["update"]
}
path "auth/token/revoke-self" {
  capabilities = ["update"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

# ---------------- No sys access ----------------

# Tenants have no business poking at sys/ paths. Explicit deny.
path "sys/*" {
  capabilities = ["deny"]
}
