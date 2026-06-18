package com.kaorisystem.gateway.filter;

import io.jsonwebtoken.Jwts;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.mock.http.server.reactive.MockServerHttpRequest;
import org.springframework.mock.web.server.MockServerWebExchange;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.security.PublicKey;
import java.time.Instant;
import java.util.Base64;
import java.util.Date;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicReference;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.mock;

/**
 * Unit tests for JwtAuthFilter — gateway-side authentication and RBAC.
 *
 * Scope:
 *   - JWT signature verification + access-token type check
 *   - Public-path bypass
 *   - Blacklist short-circuit
 *   - G3: RBAC for /api/v1/platform/** paths
 *   - Header strip + inject (anti-spoof)
 */
@DisplayName("JwtAuthFilter — gateway authentication + RBAC")
class JwtAuthFilterTest {

    private static KeyPair keyPair;
    private static String publicKeyB64;

    private ReactiveStringRedisTemplate redis;
    private JwtAuthFilter filter;
    private GatewayFilterChain chain;
    private AtomicReference<ServerWebExchange> capturedExchange;

    @BeforeAll
    static void generateKeys() throws Exception {
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        keyPair = gen.generateKeyPair();
        publicKeyB64 = Base64.getEncoder().encodeToString(keyPair.getPublic().getEncoded());
    }

    @BeforeEach
    void setUp() {
        redis = mock(ReactiveStringRedisTemplate.class);
        // Default: nothing is blacklisted.
        given(redis.hasKey(anyString())).willReturn(Mono.just(false));

        filter = new JwtAuthFilter(publicKeyB64, redis);

        capturedExchange = new AtomicReference<>();
        chain = exchange -> {
            capturedExchange.set(exchange);
            return Mono.empty();
        };
    }

    // ─── Public path bypass ──────────────────────────────────────────────

    @Test
    @DisplayName("public path /auth/login — no JWT required, X-User-* headers stripped")
    void publicPathBypass_stripsTrustedHeaders() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.post("/auth/login")
                        .header("X-User-ID",     "spoofed-id")
                        .header("X-User-Role",   "SUPER_ADMIN")
                        .header("X-Enterprise-ID","spoofed-tenant")
        );

        filter.filter(exchange, chain).block();

        // chain was invoked (no 401)
        assertThat(capturedExchange.get()).isNotNull();
        // Spoofed headers were stripped before forwarding
        var forwarded = capturedExchange.get().getRequest().getHeaders();
        assertThat(forwarded.getFirst("X-User-ID")).isNull();
        assertThat(forwarded.getFirst("X-User-Role")).isNull();
        assertThat(forwarded.getFirst("X-Enterprise-ID")).isNull();
    }

    @Test
    @DisplayName("P2-AUTH-001 — /api/v1/p2/auth/sso/google/start bypasses JWT (pre-auth)")
    void ssoStartBypassesJwt() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/p2/auth/sso/google/start")
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
    }

    @Test
    @DisplayName("P2-AUTH-001 — /auth/sso/exchange bypasses JWT (FE has sso_code, not JWT yet)")
    void ssoExchangeBypassesJwt() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.post("/auth/sso/exchange")
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
    }

    // ─── 401 paths ───────────────────────────────────────────────────────

    @Test
    @DisplayName("missing Authorization header → 401")
    void missingAuthHeader_returns401() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(capturedExchange.get()).isNull();  // chain NOT invoked
    }

    @Test
    @DisplayName("malformed Authorization (not Bearer) → 401")
    void notBearerScheme_returns401() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Basic abc=")
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    @DisplayName("invalid JWT signature → 401")
    void invalidSignature_returns401() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer not.a.valid.jwt")
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    @DisplayName("refresh token presented as access → 401")
    void refreshTokenRejected() {
        String refreshToken = signToken("MANAGER", UUID.randomUUID().toString(), "refresh");
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + refreshToken)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    @Test
    @DisplayName("blacklisted token (logout) → 401")
    void blacklistedToken_returns401() {
        String token = signToken("MANAGER", UUID.randomUUID().toString(), "access");
        given(redis.hasKey("blacklist:" + token)).willReturn(Mono.just(true));

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
    }

    // ─── G3: Platform-path RBAC ─────────────────────────────────────────

    @Test
    @DisplayName("G3: SUPER_ADMIN platform token can call /api/v1/platform/keys")
    void superAdminAllowedOnPlatform() {
        String token = signPlatformToken("SUPER_ADMIN", UUID.randomUUID().toString(),
                UUID.randomUUID().toString());

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/keys")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isNull();  // not set → forwarded
        assertThat(capturedExchange.get()).isNotNull();
    }

    @Test
    @DisplayName("G3: ADMIN platform token can call /api/v1/platform/keys")
    void adminAllowedOnPlatform() {
        String token = signPlatformToken("ADMIN", UUID.randomUUID().toString(),
                UUID.randomUUID().toString());

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/keys")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
    }

    @Test
    @DisplayName("G3: SUPPORT platform token can call /api/v1/platform/keys (read-tier)")
    void supportAllowedOnPlatform() {
        String token = signPlatformToken("SUPPORT", UUID.randomUUID().toString(),
                UUID.randomUUID().toString());

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/keys")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
    }

    @Test
    @DisplayName("G3: MANAGER tries /api/v1/platform/keys → 403 Forbidden (not 401)")
    void managerForbiddenOnPlatform() {
        String token = signToken("MANAGER", UUID.randomUUID().toString(), "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/keys")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(capturedExchange.get()).isNull();  // chain blocked at gateway
    }

    @Test
    @DisplayName("G3: VIEWER tries /api/v1/platform/workspaces → 403 (covers F-008 path)")
    void viewerForbiddenOnPlatformWorkspaces() {
        String token = signToken("VIEWER", UUID.randomUUID().toString(), "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.post("/api/v1/platform/workspaces")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
    }

    @Test
    @DisplayName("G3: enterprise paths are NOT gated by platform check (MANAGER allowed)")
    void enterprisePathNotGatedByPlatformCheck() {
        String token = signToken("MANAGER", UUID.randomUUID().toString(), "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
    }

    // ─── Header strip + inject (anti-spoof) ─────────────────────────────

    @Test
    @DisplayName("client-supplied X-User-* headers are dropped before forwarding")
    void incomingTrustedHeadersAreStripped() {
        String userId = UUID.randomUUID().toString();
        String token = signToken("MANAGER", userId, "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + token)
                        .header("X-User-ID",     "spoofed-user-id")
                        .header("X-User-Role",   "SUPER_ADMIN")
                        .header("X-Enterprise-ID","spoofed-tenant-id")
        );

        filter.filter(exchange, chain).block();

        var forwarded = capturedExchange.get().getRequest().getHeaders();
        // Spoofed values replaced by JWT-derived values
        assertThat(forwarded.getFirst("X-User-ID")).isEqualTo(userId);
        assertThat(forwarded.getFirst("X-User-Role")).isEqualTo("MANAGER");
        // Trace ID was generated
        assertThat(forwarded.getFirst("X-Trace-ID")).isNotBlank();
    }

    @Test
    @DisplayName("X-Trace-ID is preserved when caller provides one (correlation)")
    void traceIdPropagatedIfProvided() {
        String token = signToken("MANAGER", UUID.randomUUID().toString(), "access");
        String upstreamTraceId = UUID.randomUUID().toString();

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + token)
                        .header("X-Trace-ID",    upstreamTraceId)
        );

        filter.filter(exchange, chain).block();

        var forwarded = capturedExchange.get().getRequest().getHeaders();
        assertThat(forwarded.getFirst("X-Trace-ID")).isEqualTo(upstreamTraceId);
    }

    // ─── 3.2.b — token_kind gate + X-Session-Id propagation ─────────────

    @Test
    @DisplayName("3.2.b: platform token forwards X-Session-Id header to downstream")
    void platformTokenInjectsSessionId() {
        String adminId   = UUID.randomUUID().toString();
        String sessionId = UUID.randomUUID().toString();
        String token = signPlatformToken("ADMIN", adminId, sessionId);

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/security/sessions")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
        var headers = capturedExchange.get().getRequest().getHeaders();
        assertThat(headers.getFirst("X-Session-Id")).isEqualTo(sessionId);
        assertThat(headers.getFirst("X-User-ID")).isEqualTo(adminId);
        assertThat(headers.getFirst("X-User-Role")).isEqualTo("ADMIN");
        // Platform tokens have no enterprise_id — header must NOT be set.
        assertThat(headers.getFirst("X-Enterprise-ID")).isNull();
    }

    @Test
    @DisplayName("3.2.b: enterprise token does NOT propagate X-Session-Id")
    void enterpriseTokenDoesNotInjectSessionId() {
        String token = signToken("MANAGER", UUID.randomUUID().toString(), "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(capturedExchange.get()).isNotNull();
        var headers = capturedExchange.get().getRequest().getHeaders();
        assertThat(headers.getFirst("X-Session-Id")).isNull();
        // Enterprise headers still flow through
        assertThat(headers.getFirst("X-Enterprise-ID")).isNotBlank();
    }

    @Test
    @DisplayName("3.2.b: spoofed X-Session-Id from client is stripped before forwarding")
    void spoofedSessionIdStripped() {
        // Enterprise token cannot legitimately carry session_id. A malicious
        // client tries to inject one as a header.
        String token = signToken("MANAGER", UUID.randomUUID().toString(), "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/analytics/templates")
                        .header("Authorization", "Bearer " + token)
                        .header("X-Session-Id", "spoofed-session-id")
        );

        filter.filter(exchange, chain).block();

        var headers = capturedExchange.get().getRequest().getHeaders();
        assertThat(headers.getFirst("X-Session-Id")).isNull();   // stripped
    }

    @Test
    @DisplayName("3.2.b: enterprise token + platform path → 403 token_kind_mismatch RFC 7807")
    void enterpriseTokenOnPlatformPath_rejected() {
        // Issue an enterprise token but with role=ADMIN — simulates a
        // hypothetical role-escalation flaw the gate must defend against.
        Instant now = Instant.now();
        String token = Jwts.builder()
                .subject(UUID.randomUUID().toString())
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(900)))
                .claims(Map.of(
                        "type",           "access",
                        "role",           "ADMIN",
                        "token_kind",     "enterprise",          // wrong kind
                        "enterprise_id",  UUID.randomUUID().toString()))
                .signWith(keyPair.getPrivate())
                .compact();

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/security/sessions")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(exchange.getResponse().getHeaders().getContentType().toString())
                .isEqualTo("application/problem+json");
        assertThat(capturedExchange.get()).isNull();   // chain never reached downstream
    }

    @Test
    @DisplayName("3.2.b: pre-3.1.a token (no token_kind) on platform path → 403")
    void preBatchTokenOnPlatformPath_rejected() {
        // signToken() — no token_kind claim — simulates a JWT issued before
        // 3.1.a added the claim.
        String token = signToken("ADMIN", UUID.randomUUID().toString(), "access");

        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/billing/overview")
                        .header("Authorization", "Bearer " + token)
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.FORBIDDEN);
        assertThat(capturedExchange.get()).isNull();
    }

    @Test
    @DisplayName("3.2.b: missing-bearer 401 also returns RFC 7807 problem+json")
    void missingBearer_returnsProblemJson() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.get("/api/v1/platform/billing/overview")
        );

        filter.filter(exchange, chain).block();

        assertThat(exchange.getResponse().getStatusCode()).isEqualTo(HttpStatus.UNAUTHORIZED);
        assertThat(exchange.getResponse().getHeaders().getContentType().toString())
                .isEqualTo("application/problem+json");
    }

    @Test
    @DisplayName("3.2.b: /auth/platform/login is treated as public (no JWT required, headers stripped)")
    void platformLoginIsPublic() {
        ServerWebExchange exchange = MockServerWebExchange.from(
                MockServerHttpRequest.post("/auth/platform/login")
                        .header("X-Session-Id", "spoofed")
                        .header("X-User-ID",    "spoofed")
        );

        filter.filter(exchange, chain).block();

        // Forwarded (no auth required); spoofed headers stripped
        assertThat(capturedExchange.get()).isNotNull();
        var headers = capturedExchange.get().getRequest().getHeaders();
        assertThat(headers.getFirst("X-Session-Id")).isNull();
        assertThat(headers.getFirst("X-User-ID")).isNull();
    }

    // ─── helpers ─────────────────────────────────────────────────────────

    private String signToken(String role, String userId, String type) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(userId)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(900)))
                .claims(Map.of(
                        "type", type,
                        "role", role,
                        "enterprise_id", UUID.randomUUID().toString()))
                .signWith(keyPair.getPrivate())
                .compact();
    }

    /**
     * 3.2.b — platform-style token: carries {@code token_kind=platform},
     * {@code session_id}, and (deliberately) no {@code enterprise_id}.
     * Mirrors {@code JwtUtil.generatePlatformAccessToken} in auth-service.
     */
    private String signPlatformToken(String role, String adminId, String sessionId) {
        Instant now = Instant.now();
        return Jwts.builder()
                .subject(adminId)
                .issuedAt(Date.from(now))
                .expiration(Date.from(now.plusSeconds(900)))
                .claims(Map.of(
                        "type",       "access",
                        "role",       role,
                        "token_kind", "platform",
                        "session_id", sessionId))
                .signWith(keyPair.getPrivate())
                .compact();
    }
}
