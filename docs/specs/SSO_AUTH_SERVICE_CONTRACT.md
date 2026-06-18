# P2-AUTH-001 SSO — auth-service (Java) contract

**Status:** TO BUILD (ai-orchestrator Python side ship 2026-05-18; Java side outstanding)

This doc specs the endpoint anh needs to add to `services/auth-service/` (Spring Boot) so that the SSO flow can mint a real RS256 JWT. Without this endpoint, the FE has no way to convert an `sso_code` into a JWT — the OAuth flow stops at "user matched, exchange code issued" and the user can't actually log in.

## Flow recap

```
1. FE  → GET ai-orchestrator /p2/auth/sso/google/start?return_url=https://app.kaori.ai/cb
   ← { "authorize_url": "https://accounts.google.com/...", "state": "..." }

2. FE redirects browser → Google authorize URL.

3. Google ← user approves → redirects → ai-orchestrator
       /p2/auth/sso/google/callback?code=...&state=...

4. ai-orchestrator
   - verifies state (CSRF)
   - exchanges code with Google for userinfo
   - matches userinfo.email against enterprise_users
   - upserts sso_identities row
   - issues fresh sso_code (random 48-byte token, 60-sec TTL)
   - 302 → return_url + ?sso_code=<X>

5. Browser lands on FE callback page with ?sso_code=<X> query.

6. FE → POST auth-service /api/v1/auth/sso/exchange
   Body: { "sso_code": "<X>" }

7. auth-service (JAVA — TO BUILD):
   a. Receives request from FE.
   b. Calls ai-orchestrator's internal endpoint:
        POST {orchestratorBaseUrl}/p2/auth/sso/exchange-info
        Headers: X-Internal-Service-Token: ${KAORI_INTERNAL_SVC_TOKEN}
        Body: { "sso_code": "<X>" }
      ← { "enterprise_id": "<uuid>", "user_id": "<uuid>",
          "sso_identity_id": "<uuid>", "provider": "google",
          "email": "user@example.com", "consumed_at": "..." }
   c. Loads the user from enterprise_users by user_id.
   d. Generates an RS256 JWT (same shape as password-login JWT).
   e. Returns to FE: { "access_token": "<JWT>", "refresh_token": "<X>",
                       "expires_in": 3600 }

8. FE stores tokens and proceeds as if password login.
```

## Endpoint spec — `POST /api/v1/auth/sso/exchange`

### Request

| Field | Type | Required | Notes |
|---|---|---|---|
| `sso_code` | string | yes | 48-char URL-safe token from `?sso_code=` query |

```json
{ "sso_code": "AbCdEf..." }
```

### Response — 200 OK

Same shape as `POST /api/v1/auth/login`:

```json
{
  "access_token": "<RS256 JWT>",
  "refresh_token": "<opaque>",
  "expires_in": 3600,
  "token_type": "Bearer",
  "user": {
    "user_id": "<uuid>",
    "enterprise_id": "<uuid>",
    "email": "user@example.com",
    "role": "ANALYST"
  }
}
```

### Error responses

| Status | When |
|---|---|
| 400 | Missing `sso_code` in body |
| 401 | ai-orchestrator returned 401 (internal token misconfigured) |
| 404 | ai-orchestrator returned 404 (unknown `sso_code`) |
| 410 | ai-orchestrator returned 410 (code already consumed or expired) |
| 502 | ai-orchestrator unreachable |
| 500 | JWT signing or user-load failure |

## Internal endpoint reference (ai-orchestrator side — ALREADY SHIPPED)

```
POST /p2/auth/sso/exchange-info
Headers:
    X-Internal-Service-Token: <KAORI_INTERNAL_SVC_TOKEN>
Body:
    { "sso_code": "<X>" }
```

Response 200 OK:
```json
{
  "enterprise_id": "<uuid>",
  "user_id": "<uuid>",
  "sso_identity_id": "<uuid>",
  "provider": "google",
  "email": "user@example.com",
  "consumed_at": "2026-05-18T..."
}
```

Error responses:
- 401 — bad internal token (X-Internal-Service-Token mismatch)
- 404 — unknown sso_code
- 410 — already consumed (race) or expired (>60s TTL)
- 503 — KAORI_INTERNAL_SVC_TOKEN env var unset

## Env vars (auth-service)

```properties
# Same value as ai-orchestrator
KAORI_INTERNAL_SVC_TOKEN=<32-byte hex from openssl rand -hex 32>

# ai-orchestrator base URL (for the internal callout)
KAORI_ORCHESTRATOR_BASE_URL=http://ai-orchestrator:8093
```

## Java implementation sketch

```java
@RestController
@RequestMapping("/api/v1/auth/sso")
public class SsoController {

    private final WebClient orchestratorClient;
    private final UserRepository userRepository;
    private final JwtUtil jwtUtil;
    private final String internalToken;

    @PostMapping("/exchange")
    public ResponseEntity<LoginResponse> exchange(@RequestBody SsoExchangeRequest body) {
        // 1. Call ai-orchestrator
        ExchangeInfoResponse info = orchestratorClient.post()
            .uri("/p2/auth/sso/exchange-info")
            .header("X-Internal-Service-Token", internalToken)
            .bodyValue(Map.of("sso_code", body.getSsoCode()))
            .retrieve()
            .bodyToMono(ExchangeInfoResponse.class)
            .block();

        // 2. Load user
        User user = userRepository.findById(info.getUserId())
            .orElseThrow(() -> new UnauthorizedException("User not found"));

        // 3. Mint JWT
        String accessToken = jwtUtil.generateAccessToken(user);
        String refreshToken = jwtUtil.generateRefreshToken(user);

        return ResponseEntity.ok(new LoginResponse(accessToken, refreshToken, 3600, user));
    }
}
```

## Security checklist

- ✅ `X-Internal-Service-Token` must be ≥32 bytes random (no human-typed strings).
- ✅ ai-orchestrator base URL must be HTTPS in production (`https://orchestrator.internal/...`).
- ✅ exchange_info codes are one-shot — auth-service does NOT need to handle reuse.
- ✅ The 60-second TTL is enforced ai-orchestrator-side; auth-service treats 410 as terminal.
- ✅ FE must NOT see the internal token; the exchange happens server-to-server.
- ⚠️ Phase 2.5+: move `KAORI_INTERNAL_SVC_TOKEN` to Vault path `platform/auth/internal_service_token` per K-18.
