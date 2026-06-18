# Vault policy: platform-admin
#
# Granted to Kaori platform staff (P1 portal SUPER_ADMIN role) for
# managing platform-wide secrets (vendor LLM keys, SMTP creds, infra
# DB roots, MFA master key).
#
# NOT granted: tenant-specific paths (tenant admins use their own
# scoped policy). NOT granted: sys/* root operations (use root token
# checked out from KMS-encrypted vault for that, audited separately).
#
# Reference: docs/archive/sprint/p15-s9/P15-S9_PLAN.md D2; ADR-0013

# ---------------- Platform secrets — full CRUD ----------------

path "secret/data/platform/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

path "secret/metadata/platform/*" {
  capabilities = ["list", "read", "delete"]
}

# ---------------- Tenant + service secrets — read-only audit ----

# Platform admin can READ tenant secrets for break-glass support
# (tenant requests help, admin reads connector creds to debug).
# Cannot WRITE — tenant secrets always provisioned via tenant-scoped
# policy or service auth. K-1 spirit applied to Vault: scope read,
# never blanket write.

path "secret/data/tenant/*" {
  capabilities = ["read", "list"]
}

path "secret/data/service/*" {
  capabilities = ["read", "list"]
}

# ---------------- Auth method admin ----------------

path "auth/approle/role/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}

# ---------------- Sys (limited) ----------------

# Health + metrics — needed for monitoring dashboards.
path "sys/health" { capabilities = ["read", "sudo"] }
path "sys/metrics" { capabilities = ["read"] }

# Policy management — admin can manage non-root policies.
path "sys/policies/acl/*" {
  capabilities = ["create", "read", "update", "delete", "list"]
}
# But cannot tamper with the root or admin policies themselves.
path "sys/policies/acl/root" {
  capabilities = ["deny"]
}
path "sys/policies/acl/platform-admin" {
  capabilities = ["deny"]
}

# Audit device read (for verifying audit log is shipping).
path "sys/audit" {
  capabilities = ["read", "list"]
}
