# Microsoft Entra ID SSO provisioning

> **Status:** Adapter code ready since 2026-05-18 (commit `53421b7` + `fa58712`). FE login button is **holstered** (array-driven SSO providers list in `frontend/src/p2/auth/Login.tsx` skips Microsoft until `MICROSOFT_CLIENT_ID` env reports configured). This runbook is the activation procedure when anh provisions an M365 Developer Program tenant.

## What's currently shipped

| Component | State | Where |
|---|---|---|
| Microsoft adapter (multi-tenant + single-tenant authority routing) | Ready | `services/ai-orchestrator/shared/sso_providers/microsoft.py` |
| `/p2/auth/sso/microsoft/{authorize,callback}` routes | Ready (503 until env set) | `services/ai-orchestrator/routers/sso.py` |
| Java SsoController routing | Ready (provider-agnostic) | `services/auth-service/.../sso/SsoController.java` |
| `sso_identities` table (Google + Microsoft sub keys) | Live | mig `083_sso_identities.sql` |
| FE callback page | Live for both providers | `frontend/src/p2/auth/sso-callback/page.tsx` |
| FE login button | Microsoft entry holstered behind config-presence gate | `frontend/src/p2/auth/Login.tsx` |
| Env vars | `MICROSOFT_CLIENT_ID` / `MICROSOFT_CLIENT_SECRET` / `MICROSOFT_REDIRECT_URI` / `MICROSOFT_TENANT_ID` | `.env.example` |
| Tests | 8 unit tests pass | `services/ai-orchestrator/tests/test_sso.py` Microsoft section |

Google SSO has been live + browser-tested since 2026-05-18 with `nguyentruongan25051997@gmail.com` (commit `6c92b69`). Microsoft is the structurally-identical sibling.

## When to provision

Trigger any of:
- A pilot customer requires Microsoft 365 SSO as a procurement gate
- Anh wants to validate the multi-provider plumbing end-to-end before customer demo
- M365 Developer Program tenant is free (90-day renewable) — no cost to keep dormant

## Step 1 — Join M365 Developer Program (one-time, free)

1. Go to <https://developer.microsoft.com/en-us/microsoft-365/dev-program>
2. Sign in with any Microsoft account (personal or work)
3. Click **Join now** → fill the form (country: Vietnam; primary purpose: "Identity & SSO development for SaaS")
4. Choose **Instant sandbox** at the provisioning screen
   - Em recommend Instant over Configurable — the sandbox provisions in ~2 minutes with 25 seed users; Configurable takes 24+ hours and adds Teams/SharePoint complexity em don't need for SSO
5. Wait for the green "Your subscription is ready" banner. Save:
   - Admin user: `admin@<your-domain>.onmicrosoft.com`
   - Admin password (one-time view — store in 1Password / Bitwarden)
   - Tenant ID (GUID, visible at <https://portal.azure.com> → Microsoft Entra ID → Overview)

## Step 2 — Register the Kaori app in Entra ID

1. Open <https://entra.microsoft.com> → sign in as the admin from Step 1
2. **Identity** → **Applications** → **App registrations** → **+ New registration**
3. Fill the form:
   - **Name**: `Kaori — Local Dev` (or whatever fits anh's naming)
   - **Supported account types**: choose **Multitenant + personal Microsoft accounts** (matches the default `tenant="common"` in the adapter)
     - Alternative: **Single tenant** if anh wants strict isolation — then set `MICROSOFT_TENANT_ID=<GUID>` in env
   - **Redirect URI**: select **Web** + paste `http://localhost:8080/api/v1/p2/auth/sso/microsoft/callback`
     - For production swap to `https://api.kaori.io/api/v1/p2/auth/sso/microsoft/callback`
4. Click **Register**
5. From the new app's overview page, copy:
   - **Application (client) ID** → goes into `MICROSOFT_CLIENT_ID`
   - **Directory (tenant) ID** → goes into `MICROSOFT_TENANT_ID` only if single-tenant mode chosen above
6. **Certificates & secrets** → **Client secrets** → **+ New client secret**
   - Description: `kaori-local-dev` · Expiry: **6 months** (re-rotate per `mfa-key-rotation.md` cadence — see also "Rotation" section below)
   - Click **Add** → **immediately** copy the secret **Value** (NOT the Secret ID). Once anh leaves the page it's masked permanently. Paste into `MICROSOFT_CLIENT_SECRET`.

## Step 3 — Configure ID token claims (required for email)

Microsoft v2.0 token endpoint omits `email` by default unless explicitly requested. The adapter already requests scope `openid profile email offline_access`, but anh must also enable the optional claim on the app:

1. Same app's page → **Token configuration** → **+ Add optional claim**
2. Token type: **ID** → check **email** → **Add**
3. If prompted "Turn on the Microsoft Graph email permission" — click **Yes** (grants `User.Read` + `email` scope)

Without this, `/p2/auth/sso/microsoft/callback` returns a 422 "Microsoft userinfo missing sub/email" — the adapter's `exchange_code_for_profile` raises `OAuthExchangeError` when email isn't on the profile.

## Step 4 — Wire env vars

Edit `.env` (NOT committed — `.env.example` already lists the keys without values):

```bash
MICROSOFT_CLIENT_ID=<paste from Step 2.5>
MICROSOFT_CLIENT_SECRET=<paste from Step 2.6 — Value, not Secret ID>
MICROSOFT_REDIRECT_URI=http://localhost:8080/api/v1/p2/auth/sso/microsoft/callback
# MICROSOFT_TENANT_ID=<GUID>  # only set for single-tenant restriction; leave commented for multi-tenant
```

Restart ai-orchestrator + auth-service to pick up the env:

```bash
docker compose restart ai-orchestrator auth-service
```

## Step 5 — Smoke test

```bash
# 1. Confirm adapter loaded — should return JSON, NOT 503
curl -fsS http://localhost:8080/api/v1/p2/auth/sso/microsoft/authorize?return_to=/

# Expected: 200 with {"authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize?..."}
# If 503: env not picked up → check `docker exec kaori-ai-orchestrator-1 env | grep MICROSOFT_`
```

```bash
# 2. Browser flow
#    Open http://localhost:3000/login → click the Microsoft button
#    (it appears automatically after env is set — the FE polls
#    /p2/auth/sso/providers and conditionally renders).
#    Sign in with the admin@<your-domain>.onmicrosoft.com account.
#    Expected: redirect back to /sso-callback?code=... → JWT issued
#    → land on /p2/dashboard with the Microsoft user visible in
#    "My account" → "Linked identities" section.
```

## Step 6 — Verify DB row landed

```bash
docker exec -it kaori-postgres-1 psql -U kaori -d kaori_dev -c \
  "SELECT user_id, provider, provider_sub, email, created_at
   FROM sso_identities WHERE provider='microsoft' ORDER BY created_at DESC LIMIT 5;"
```

Expected: 1 row per Microsoft sign-in, `provider_sub` is the Entra `oid` claim (stable per user per tenant; safe to use as foreign-key target).

## Activation done — what changes

- FE login screen shows the Microsoft button next to the existing Google button (array order preserved in `Login.tsx` SSO_PROVIDERS_ORDER constant — Microsoft sits between Google and any future LinkedIn / Apple).
- `/p2/auth/sso/providers` endpoint now lists `["google", "microsoft"]`. (Holstered state: just `["google"]`.)
- Tests in `services/ai-orchestrator/tests/test_sso.py::TestMicrosoftAdapter` flip from skip-when-no-env to actively hitting the Microsoft graph mock.

## Rotation

Client secret expires 6 months from issue. Calendar reminder at `<expiry-30>` days:

1. Step 2.6 again with description `kaori-local-dev-v2`
2. Update `.env` with new secret value
3. `docker compose restart ai-orchestrator auth-service`
4. Smoke test (Step 5) — confirm new secret accepted
5. Delete the old secret from Entra portal (Step 2.6 page → trash icon next to old entry)

Em recommend a tag in <https://1password.com> or anh's secrets vault: `kaori/sso/microsoft/client_secret` with expiry date in metadata so the rotation alert surfaces.

## Holster procedure (if anh ever wants to disable Microsoft after activation)

```bash
# Remove env vars (or leave them empty)
sed -i '/^MICROSOFT_CLIENT_ID=/d; /^MICROSOFT_CLIENT_SECRET=/d' .env

# Restart — adapter will raise ProviderNotConfigured → router returns 503
# FE button auto-hides on next /p2/auth/sso/providers refresh
docker compose restart ai-orchestrator auth-service
```

Code stays in tree — no rollback needed. Holstering is a config change, not a code change.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `/p2/auth/sso/microsoft/authorize` returns 503 "SSO provider not configured" | Env vars missing or empty | `docker exec ... env | grep MICROSOFT_`; re-set in `.env`; restart services |
| Callback returns 422 "Microsoft userinfo missing sub/email" | Optional `email` claim not enabled on the app registration | Re-do Step 3 |
| Callback returns 401 "Microsoft token exchange failed (400): AADSTS50011" | Redirect URI mismatch | Confirm Entra portal Step 2.3 redirect URI EXACTLY matches `MICROSOFT_REDIRECT_URI` env (including trailing slash absence + http vs https + port) |
| Callback returns 401 "AADSTS7000215: Invalid client secret" | Secret expired or copied wrong (used Secret ID instead of Value) | Re-do Step 2.6, copy the Value field |
| Browser flow loops back to login | JWT not issued because email link to existing user failed | Check `sso_identities` table — if a row exists for this `provider_sub` linked to a DIFFERENT user_id, anh has an account collision; delete the row or merge users |
| `AADSTS900561: ... tenant id 'common' but the resource was configured for 'organizations'` | Adapter using `common` authority but app registration restricted to org accounts | Either: (a) set `MICROSOFT_TENANT_ID=<your-GUID>` env to match single-tenant config; OR (b) re-do Step 2.3 changing account types to multi-tenant |

## What this runbook does NOT cover

- **Production Entra ID provisioning** — when anh's first customer needs SSO, they bring their OWN tenant ID. Em accept it via the `MICROSOFT_TENANT_ID` env var per environment (or via a future per-tenant config table). The multi-tenant `common` authority handles the heterogeneous case if anh leave the env unset.
- **Group / role provisioning via Entra** — Microsoft Graph supports SCIM 2.0 for auto-provisioning users into RBAC groups. Out of scope for SSO sign-in; tracked as a Phase 3 enhancement.
- **Conditional Access policies** — large enterprise customers may require MFA / device compliance / IP allowlist via Entra Conditional Access. Em get that for free — the access token issued already encodes the policy decision. No Kaori-side work.

## Related

- Google SSO is the structurally-identical sibling and has been live since 2026-05-18 (commit `6c92b69`); refer to `services/ai-orchestrator/shared/sso_providers/google.py` for the parallel implementation.
- Auth-service Java side: `SsoController` + `SsoExchangeService` are provider-agnostic; the activation work happens entirely on the Python adapter + env side.
- mig `083_sso_identities.sql` schema docs the `(user_id, provider, provider_sub)` triple — both Google and Microsoft write to the same table.
