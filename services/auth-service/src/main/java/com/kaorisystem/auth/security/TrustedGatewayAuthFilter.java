package com.kaorisystem.auth.security;

import com.kaorisystem.auth.service.SessionValidator;
import com.kaorisystem.auth.service.SessionValidator.Result;
import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * Translates trusted gateway-injected headers into a Spring Security
 * {@link org.springframework.security.core.Authentication}.
 *
 * <p>The api-gateway validates JWTs and forwards three headers on every
 * authenticated request:
 *
 * <pre>
 *   X-User-ID         the user UUID
 *   X-Enterprise-ID   the tenant UUID (enterprise users only)
 *   X-User-Role       one of SUPER_ADMIN / ADMIN / SUPPORT / MANAGER /
 *                     OPERATOR / ANALYST / VIEWER
 *   X-Session-Id      (3.1.a) the platform admin session id; absent for
 *                     enterprise users
 * </pre>
 *
 * <p>This filter populates {@link SecurityContextHolder} so that
 * {@code requestMatchers(...).hasAnyRole(...)} rules in
 * {@link SecurityConfig} can fire correctly.
 *
 * <h3>Session enforcement (Batch 3.1.a)</h3>
 * When a session_id is resolvable for the request — either from the
 * {@code X-Session-Id} header (gateway-supplied) or extracted from the
 * Bearer token's {@code session_id} claim (fallback path until the
 * gateway routing change in 3.2.b lands) — the filter calls
 * {@link SessionValidator#validateAndTouch} once. If the verdict is not
 * {@code VALID}, the filter writes an RFC 7807 401 response and aborts
 * the chain. Successful validations also touch {@code last_active_at}
 * (subject to a Redis-backed 60s cooldown so we don't write per-request).
 *
 * <p><b>Trust model:</b> auth-service trusts the gateway implicitly. The
 * gateway is responsible for stripping any X-User-* headers that arrive
 * from outside before re-injecting its own. In production, auth-service
 * must NOT be reachable directly from the public network (network policy
 * / service mesh enforcement).
 *
 * <p>Public paths (configured as {@code permitAll} in SecurityConfig)
 * still work because no Authentication is required there. This filter
 * leaves SecurityContextHolder empty when headers are absent.
 */
@Component
@Slf4j
public class TrustedGatewayAuthFilter extends OncePerRequestFilter {

    public static final String HDR_USER_ID       = "X-User-ID";
    public static final String HDR_ENTERPRISE_ID = "X-Enterprise-ID";
    public static final String HDR_USER_ROLE     = "X-User-Role";
    public static final String HDR_SESSION_ID    = "X-Session-Id";

    /**
     * {@link SessionValidator} is a circular dep when the auth-service boots:
     * filter → service → repo → datasource → security autoconfig → filter.
     * Using {@link ObjectProvider} defers the lookup until first use and lets
     * tests run with a stub or no validator at all (e.g. WebMvcTest slices
     * that don't load the full context).
     */
    private final ObjectProvider<SessionValidator> sessionValidatorProvider;
    private final ObjectProvider<JwtUtil>          jwtUtilProvider;

    public TrustedGatewayAuthFilter(
            ObjectProvider<SessionValidator> sessionValidatorProvider,
            ObjectProvider<JwtUtil>          jwtUtilProvider) {
        this.sessionValidatorProvider = sessionValidatorProvider;
        this.jwtUtilProvider          = jwtUtilProvider;
    }

    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                    HttpServletResponse response,
                                    FilterChain chain) throws ServletException, IOException {
        String userId = request.getHeader(HDR_USER_ID);
        String role   = request.getHeader(HDR_USER_ROLE);

        // Both headers required to attempt authentication. If either is
        // missing this is either a public endpoint (e.g. /auth/login) or
        // a request that bypassed the gateway — let SecurityConfig's
        // matchers decide what to do (permitAll vs denyAll).
        if (userId == null || userId.isBlank() || role == null || role.isBlank()) {
            chain.doFilter(request, response);
            return;
        }

        // Resolve session_id for platform admin requests. Header wins; fall
        // back to JWT claim. Enterprise users have no session, so this stays
        // null for them and the validator step is skipped.
        UUID sessionId = resolveSessionId(request);
        if (sessionId != null) {
            SessionValidator validator = sessionValidatorProvider.getIfAvailable();
            if (validator != null) {
                Result vr = validator.validateAndTouch(sessionId, clientIp(request));
                if (vr.status() != SessionValidator.Status.VALID) {
                    writeProblem401(response, vr);
                    return;
                }
            }
        }

        // Spring Security expects role authorities to be prefixed with
        // "ROLE_" so that hasRole("X") / hasAnyRole("X", "Y") matchers
        // work without the prefix in configuration.
        var authority = new SimpleGrantedAuthority("ROLE_" + role.trim());

        UsernamePasswordAuthenticationToken auth =
                new UsernamePasswordAuthenticationToken(
                        userId,                 // principal
                        null,                   // credentials (already validated upstream)
                        List.of(authority));
        auth.setDetails(request.getHeader(HDR_ENTERPRISE_ID));

        SecurityContextHolder.getContext().setAuthentication(auth);
        log.debug("trusted-gateway.auth principal={} role={} session={}",
                userId, role, sessionId);

        chain.doFilter(request, response);
    }

    // =========================================================================
    // session_id resolution
    // =========================================================================

    private UUID resolveSessionId(HttpServletRequest request) {
        String header = request.getHeader(HDR_SESSION_ID);
        if (header != null && !header.isBlank()) {
            try { return UUID.fromString(header.trim()); }
            catch (IllegalArgumentException e) { /* fall through to JWT */ }
        }

        // Fallback: parse the Bearer token's session_id claim. Used while the
        // gateway is not yet promoting session_id into the X-Session-Id header
        // (3.2.b). Enterprise tokens have no session_id, so this returns null
        // for them.
        String authz = request.getHeader("Authorization");
        if (authz == null || !authz.startsWith("Bearer ")) return null;

        JwtUtil jwt = jwtUtilProvider.getIfAvailable();
        if (jwt == null) return null;

        try {
            Claims claims = jwt.validateAndParse(authz.substring(7));
            Object sid = claims.get("session_id");
            if (sid == null) return null;
            return UUID.fromString(sid.toString());
        } catch (JwtException | IllegalArgumentException e) {
            // Don't reject on parse failures — the request might still match a
            // public endpoint. Let SecurityConfig decide.
            return null;
        }
    }

    // =========================================================================
    // 401 short-circuit
    // =========================================================================

    private void writeProblem401(HttpServletResponse response, Result vr) throws IOException {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type",   problemType(vr.status()));
        body.put("title",  problemTitle(vr.status()));
        body.put("status", 401);
        body.put("detail", problemDetail(vr.status()));
        if (vr.reason() != null) body.put("reason", vr.reason());

        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/problem+json");
        response.getWriter().write(toJson(body));
    }

    private static String problemType(SessionValidator.Status s) {
        return switch (s) {
            case IDLE_EXPIRED     -> "/docs/errors/session-idle-timeout";
            case ABSOLUTE_EXPIRED -> "/docs/errors/session-absolute-timeout";
            case REVOKED          -> "/docs/errors/session-revoked";
            default               -> "/docs/errors/session-invalid";
        };
    }

    private static String problemTitle(SessionValidator.Status s) {
        return switch (s) {
            case IDLE_EXPIRED     -> "Session expired (idle)";
            case ABSOLUTE_EXPIRED -> "Session expired (max duration)";
            case REVOKED          -> "Session revoked";
            default               -> "Session invalid";
        };
    }

    private static String problemDetail(SessionValidator.Status s) {
        return switch (s) {
            case IDLE_EXPIRED     -> "No activity within the idle window. Please sign in again.";
            case ABSOLUTE_EXPIRED -> "Maximum session duration reached. Please sign in again.";
            case REVOKED          -> "This session was revoked. Please sign in again.";
            default               -> "Session not found. Please sign in again.";
        };
    }

    /** Tiny hand-rolled JSON encoder — avoids dragging Jackson into the filter chain. */
    private static String toJson(Map<String, Object> m) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (var e : m.entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(escape(e.getKey())).append("\":");
            Object v = e.getValue();
            if (v == null)              sb.append("null");
            else if (v instanceof Number || v instanceof Boolean) sb.append(v);
            else                        sb.append('"').append(escape(v.toString())).append('"');
        }
        return sb.append('}').toString();
    }

    private static String escape(String s) {
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n");
    }

    /** Same X-Forwarded-For-aware extraction as the controllers. */
    private static String clientIp(HttpServletRequest req) {
        String forwarded = req.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            int comma = forwarded.indexOf(',');
            return comma > 0 ? forwarded.substring(0, comma).trim() : forwarded.trim();
        }
        return req.getRemoteAddr();
    }
}
