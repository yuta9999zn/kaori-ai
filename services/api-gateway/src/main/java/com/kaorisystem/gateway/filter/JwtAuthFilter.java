package com.kaorisystem.gateway.filter;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import io.jsonwebtoken.Jwts;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

@Component
@Slf4j
public class JwtAuthFilter implements GlobalFilter, Ordered {

    private static final List<String> PUBLIC_PATHS = List.of(
            "/auth/login", "/auth/forgot-password", "/auth/reset-password",
            "/auth/platform/login",
            // Token refresh authenticates via the refresh token in the BODY, not
            // an access-token Bearer — it's called precisely when the access
            // token has expired. Gating it behind the JWT filter made refresh
            // impossible (401 missing-bearer), so sessions died at the 15-min
            // access TTL with no recovery. auth-service validates the refresh token.
            "/auth/refresh", "/auth/platform/refresh",
            // B3 PR #8 — second leg of the platform 2-step login. The caller
            // presents an mfa_challenge_token, NOT a full session bearer; the
            // auth-service handles its own validation. Public from the
            // gateway's perspective.
            "/auth/platform/mfa/verify",
            // Sprint 7 PR D — F-013 onboarding page POSTs to /workspace/activate
            // with the activation key + initial admin credentials. No JWT yet.
            "/auth/workspace/activate",
            // P2-AUTH-001 SSO — pre-auth OAuth dance. /start issues the
            // authorize URL, /callback consumes the provider code, and
            // /auth/sso/exchange swaps the resulting one-shot sso_code
            // for a real JWT. None of these can carry a Bearer header —
            // the user is by definition not yet authenticated.
            "/api/v1/p2/auth/sso/",
            "/auth/sso/exchange",
            "/health", "/actuator/health"
    );

    /**
     * Roles allowed to call /api/v1/platform/**.
     * Mirrors the SUPER_ADMIN/ADMIN/SUPPORT staff tier in
     * services/auth-service/.../SecurityConfig.java — defence in depth.
     */
    private static final Set<String> PLATFORM_ROLES = Set.of("SUPER_ADMIN", "ADMIN", "SUPPORT");

    /** 3.2.b — token_kind required on /api/v1/platform/**. */
    private static final String PLATFORM_PATH_PREFIX = "/api/v1/platform/";
    private static final String TOKEN_KIND_PLATFORM  = "platform";

    /** Phase 2 #12 (clock skew) — same value as JwtUtil in auth-service. */
    private static final long CLOCK_SKEW_SECONDS = 30L;

    /**
     * Phase 2 #1 — canonical machine-readable error codes mirrored from
     * services/auth-service/.../common/ErrorCodes.java + the four Python
     * error_codes.py copies. Every short-circuit RFC 7807 response carries
     * the matching code so the FE can map it to one i18n bundle regardless
     * of which service authored the failure.
     */
    private static final String CODE_MISSING_BEARER   = "AUTH.MISSING_BEARER";
    private static final String CODE_TOKEN_REVOKED    = "AUTH.TOKEN_REVOKED";
    private static final String CODE_TOKEN_INVALID    = "AUTH.TOKEN_INVALID";
    private static final String CODE_FORBIDDEN_ROLE   = "AUTH.FORBIDDEN_ROLE";
    private static final String CODE_WRONG_TOKEN_KIND = "AUTH.WRONG_TOKEN_KIND";

    /**
     * Headers we inject for downstream services. We strip these from
     * incoming requests first so a malicious client cannot spoof them.
     *
     * <p>3.2.b — added {@code X-Session-Id}. The header is only ever
     * populated from the JWT's {@code session_id} claim (platform tokens),
     * never from the client.
     */
    private static final List<String> TRUSTED_HEADERS = List.of(
            "X-User-ID", "X-Enterprise-ID", "X-User-Role", "X-Session-Id"
    );

    private final PublicKey publicKey;
    private final ReactiveStringRedisTemplate redis;

    public JwtAuthFilter(
            @Value("${jwt.public-key}") String publicKeyBase64,
            ReactiveStringRedisTemplate redis) {
        try {
            KeyFactory kf = KeyFactory.getInstance("RSA");
            byte[] pubBytes = Base64.getDecoder().decode(publicKeyBase64.replaceAll("\\s", ""));
            this.publicKey = kf.generatePublic(new X509EncodedKeySpec(pubBytes));
        } catch (Exception e) {
            throw new IllegalStateException("Failed to load JWT public key", e);
        }
        this.redis = redis;
    }

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        String path = exchange.getRequest().getPath().value();

        // Pass public endpoints through. We still strip incoming X-User-* headers
        // so an unauthenticated caller cannot pre-set tenant identity for
        // downstream services that trust the gateway.
        if (PUBLIC_PATHS.stream().anyMatch(path::startsWith)) {
            return chain.filter(stripTrustedHeaders(exchange));
        }

        String bearer = exchange.getRequest().getHeaders().getFirst("Authorization");
        if (bearer == null || !bearer.startsWith("Bearer ")) {
            return writeProblem(exchange, HttpStatus.UNAUTHORIZED,
                    "/docs/errors/missing-bearer", "Missing bearer token",
                    "Authorization: Bearer <token> header is required.",
                    CODE_MISSING_BEARER);
        }

        String token = bearer.substring(7);

        // Check blacklist (logout invalidation)
        return redis.hasKey("blacklist:" + token)
                .flatMap(blacklisted -> {
                    if (Boolean.TRUE.equals(blacklisted)) {
                        return writeProblem(exchange, HttpStatus.UNAUTHORIZED,
                                "/docs/errors/token-revoked", "Token revoked",
                                "This token has been signed out. Please sign in again.",
                                CODE_TOKEN_REVOKED);
                    }

                    try {
                        // 30s leeway on iat/exp/nbf — Phase 2 error-handling
                        // group #12 (clock skew). Mirrors JwtUtil in
                        // auth-service so the gateway and the issuer never
                        // disagree about freshness on a token that's a few
                        // seconds either side of NTP drift.
                        Claims claims = Jwts.parser()
                                .verifyWith(publicKey)
                                .clockSkewSeconds(CLOCK_SKEW_SECONDS)
                                .build()
                                .parseSignedClaims(token)
                                .getPayload();

                        if (!"access".equals(claims.get("type"))) {
                            return writeProblem(exchange, HttpStatus.UNAUTHORIZED,
                                    "/docs/errors/wrong-token-type", "Wrong token type",
                                    "Endpoint requires an access token; got type=" + claims.get("type") + ".",
                                    CODE_TOKEN_INVALID);
                        }

                        String role      = claims.get("role",       String.class);
                        String tokenKind = claims.get("token_kind", String.class);
                        String sessionId = claims.get("session_id", String.class);

                        // G3 — gateway-side RBAC for platform admin paths.
                        // Defence in depth: auth-service's SecurityConfig
                        // also enforces this, but we reject early at the
                        // edge so non-staff JWTs cannot probe platform
                        // endpoints or burn rate-limit budget reaching them.
                        if (path.startsWith(PLATFORM_PATH_PREFIX)) {
                            if (role == null || !PLATFORM_ROLES.contains(role)) {
                                log.warn("rbac.deny path={} role={} reason=role_not_platform", path, role);
                                return writeProblem(exchange, HttpStatus.FORBIDDEN,
                                        "/docs/errors/forbidden-role",
                                        "Platform endpoint requires staff role",
                                        "Allowed roles: SUPER_ADMIN, ADMIN, SUPPORT.",
                                        CODE_FORBIDDEN_ROLE);
                            }
                            // 3.2.b — token_kind=platform required on top of role check.
                            // Closes the case where some future bug issued an enterprise
                            // token with a staff role; the role gate alone wouldn't
                            // catch it. WARN-level so the security team gets visibility
                            // on attempts (e.g. a leaked enterprise token being probed
                            // against /api/v1/platform/**).
                            if (!TOKEN_KIND_PLATFORM.equals(tokenKind)) {
                                log.warn("rbac.deny path={} role={} token_kind={} reason=token_kind_mismatch",
                                        path, role, tokenKind);
                                return writeProblem(exchange, HttpStatus.FORBIDDEN,
                                        "/docs/errors/wrong-token-kind",
                                        "Wrong token kind for platform endpoint",
                                        "Platform endpoints accept only platform-issued tokens "
                                              + "(token_kind=platform). Sign in via /auth/platform/login.",
                                        CODE_WRONG_TOKEN_KIND);
                            }
                        }

                        // Inject tenant headers for downstream services (K-7).
                        // We mutate via a fresh request: removeIf strips any
                        // incoming X-User-* before set() writes our trusted
                        // values, so a malicious client cannot pre-set them.
                        //
                        // 3.2.b — X-Session-Id is forwarded ONLY when the JWT
                        // carries a session_id claim (i.e. platform tokens).
                        // For enterprise tokens the strip-list above ensures
                        // the header is also removed if a client sent it.
                        String traceId = getOrCreateTraceId(exchange);
                        ServerWebExchange mutated = exchange.mutate()
                                .request(r -> r.headers(headers -> {
                                    TRUSTED_HEADERS.forEach(headers::remove);
                                    headers.set("X-User-ID", claims.getSubject());
                                    String enterpriseId = claims.get("enterprise_id", String.class);
                                    if (enterpriseId != null) {
                                        headers.set("X-Enterprise-ID", enterpriseId);
                                    }
                                    headers.set("X-User-Role", role);
                                    if (sessionId != null && !sessionId.isBlank()) {
                                        headers.set("X-Session-Id", sessionId);
                                    }
                                    headers.set("X-Trace-ID", traceId);
                                }))
                                .build();

                        return chain.filter(mutated);

                    } catch (JwtException | IllegalArgumentException e) {
                        log.debug("JWT validation failed: {}", e.getMessage());
                        return writeProblem(exchange, HttpStatus.UNAUTHORIZED,
                                "/docs/errors/invalid-token", "Invalid token",
                                e.getMessage(),
                                CODE_TOKEN_INVALID);
                    }
                });
    }

    /**
     * Strips X-User-* headers before forwarding a public-path request.
     * Public endpoints don't need them and must not let clients spoof them.
     * Includes X-Session-Id (3.2.b) — only the gateway is allowed to set it.
     */
    private ServerWebExchange stripTrustedHeaders(ServerWebExchange exchange) {
        return exchange.mutate()
                .request(r -> r.headers(h -> TRUSTED_HEADERS.forEach(h::remove)))
                .build();
    }

    private String getOrCreateTraceId(ServerWebExchange exchange) {
        String existing = exchange.getRequest().getHeaders().getFirst("X-Trace-ID");
        return (existing != null && !existing.isBlank()) ? existing : UUID.randomUUID().toString();
    }

    /**
     * Write an RFC 7807 application/problem+json response and complete the
     * exchange. Used for every 4xx short-circuit so clients see a consistent
     * error shape across missing-token, blacklisted-token, wrong-type,
     * wrong-role, and wrong-kind cases.
     */
    private static Mono<Void> writeProblem(
            ServerWebExchange exchange, HttpStatus status,
            String type, String title, String detail, String code) {
        ServerHttpResponse resp = exchange.getResponse();
        resp.setStatusCode(status);
        resp.getHeaders().setContentType(MediaType.parseMediaType("application/problem+json"));

        // Phase 2 #1 — every short-circuit response now carries a
        // machine-readable ``code`` (DOMAIN.NAME) so the FE maps it to one
        // i18n bundle entry. Order matches the canonical envelope shape.
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type",     type);
        body.put("title",    title);
        body.put("status",   status.value());
        body.put("code",     code);
        body.put("detail",   detail);
        body.put("instance", exchange.getRequest().getPath().value());

        byte[] bytes = toJson(body).getBytes(StandardCharsets.UTF_8);
        DataBuffer buf = resp.bufferFactory().wrap(bytes);
        resp.getHeaders().setContentLength(bytes.length);
        return resp.writeWith(Mono.just(buf));
    }

    /**
     * Tiny hand-rolled JSON encoder — Spring Cloud Gateway's filter chain
     * runs before MVC's JSON converters are wired, and we don't want to
     * pull Jackson into a hot-path filter for a 5-field error envelope.
     */
    static String toJson(Map<String, Object> m) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (var e : m.entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(escape(e.getKey())).append("\":");
            Object v = e.getValue();
            if (v == null)                                       sb.append("null");
            else if (v instanceof Number || v instanceof Boolean) sb.append(v);
            else                                                  sb.append('"').append(escape(v.toString())).append('"');
        }
        return sb.append('}').toString();
    }

    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
    }

    @Override
    public int getOrder() {
        return -200;  // Run before other filters
    }
}
