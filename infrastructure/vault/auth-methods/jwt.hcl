# Vault JWT auth method config — binds Kaori RS256 JWT (auth-service
# issued) to Vault tokens. Phase 1.5 P15-S9 D2 stub; full wiring lands
# when the P3 Studio + tenant Vault portal ships (later sprint).
#
# Why JWT auth: tenant users who authenticate to Kaori already hold a
# JWT. Reusing that JWT as Vault auth lets them read their tenant
# secret tree without a separate Vault token exchange. AppRole stays
# for backend services; JWT is for human users via UI.
#
# Reference: docs/archive/sprint/p15-s9/P15-S9_PLAN.md D2

auth "jwt" {
  type = "jwt"

  config = {
    # Public key set served by auth-service for JWT verification.
    # Phase 1.5 D2: hardcoded JWKS URL pointing at the cluster-internal
    # auth-service. Phase 2 we expose at api.kaori.ai/jwks.json public
    # for cross-cluster verification.
    jwks_url = "http://auth-service.kaori.svc.cluster.local:8091/.well-known/jwks.json"

    # The "kaori-issuer" string the auth-service sets in JWT iss claim.
    # auth-service uses "https://api.kaori.ai" Phase 1.5+; this stays
    # constant across env via JWT_ISS env var.
    jwt_supported_algs = ["RS256"]
    bound_issuer = "https://api.kaori.ai"

    # Default role applied if JWT has no explicit role claim. We set
    # this to a deny-by-default so a malformed JWT never grants access.
    default_role = "deny-default"
  }
}

# Role: tenant-user — bound to JWT claim shape from auth-service.
#
# JWT claim shape (auth-service issues):
# {
#   "sub": "<user_id>",
#   "iss": "https://api.kaori.ai",
#   "aud": ["kaori-vault"],
#   "tenant_id": "<uuid>",     ← used to interpolate policy path
#   "role": "MANAGER" | "ANALYST" | ...
# }
#
# Vault binds tenant_id to the policy template via user_claim, so the
# resulting token can only access secret/data/tenant/<bound_id>/*.

role "tenant-user" {
  user_claim = "tenant_id"
  bound_audiences = ["kaori-vault"]
  bound_claims = {
    role = ["MANAGER", "ANALYST"]
  }
  token_policies = ["tenant-{{user_claim}}"]
  token_ttl = "30m"
  token_max_ttl = "2h"
  token_no_default_policy = true
}

# Role: deny-default — explicit deny if JWT shape unexpected.

role "deny-default" {
  user_claim = "sub"
  bound_audiences = ["kaori-vault"]
  token_policies = ["default"]  # default = empty after we strip it
  token_ttl = "5m"
  token_max_ttl = "5m"
  token_no_default_policy = true
}
