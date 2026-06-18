package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.dto.AuthDtos.LoginRequest;
import com.kaorisystem.auth.dto.AuthDtos.MfaVerifyRequest;
import com.kaorisystem.auth.dto.AuthDtos.RefreshRequest;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.AuthService.LockoutException;
import com.kaorisystem.auth.service.PlatformAuthService;
import com.kaorisystem.auth.service.PlatformAuthService.MfaChallengeExpiredException;
import com.kaorisystem.auth.service.PlatformAuthService.PlatformLoginResult;
import com.kaorisystem.auth.service.PlatformAuthService.TokenReplayException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Batch 3.1.a + B3 PR #8 — Platform admin authentication endpoints.
 *
 * <pre>
 *   POST /auth/platform/login         { email, password }
 *   POST /auth/platform/mfa/verify    { mfa_challenge_token, code }
 *   POST /auth/platform/refresh       { refresh_token }
 * </pre>
 *
 * Logout reuses the existing {@code POST /auth/logout} which now also
 * revokes the {@code admin_sessions} row when the bearer token's
 * {@code token_kind=platform} (see {@code AuthService.logout}).
 */
@RestController
@RequestMapping("/auth/platform")
@RequiredArgsConstructor
@Slf4j
public class PlatformAuthController {

    private final PlatformAuthService authService;

    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest req,
                                   HttpServletRequest http) {
        try {
            PlatformLoginResult r = authService.login(req, clientIp(http), http.getHeader("User-Agent"));
            return ResponseEntity.ok(toResponse(r));
        } catch (LockoutException e) {
            // RFC 7807 Problem Details — preserves the seconds-remaining hint
            // the FE shows in the lockout banner. Keeps the same 423 status as
            // the existing /auth/login.
            Map<String, Object> body = new LinkedHashMap<>();
            body.put("type",   "/docs/errors/account-locked");
            body.put("title",  "Account locked");
            body.put("status", 423);
            body.put("code",   com.kaorisystem.auth.common.ErrorCodes.AUTH_LOCKED);
            body.put("detail", e.getMessage());
            body.put("lockout_remaining_seconds", e.getRemainingSeconds());
            return ResponseEntity.status(423).body(body);
        } catch (InvalidCredentialsException e) {
            return problem(401, "/docs/errors/invalid-credentials",
                    "Invalid credentials", e.getMessage(),
                    com.kaorisystem.auth.common.ErrorCodes.AUTH_INVALID_CREDENTIALS);
        }
    }

    /**
     * B3 PR #8 — second leg of the 2-step platform login.
     *
     * <p>Accepts the {@code mfa_challenge_token} returned by /login (when
     * {@code mfa_required=true}) plus the 6-digit TOTP code. On success
     * returns the same envelope shape as a no-MFA login. Maps each failure
     * mode to a distinct {@code code} so the FE can drive copy:
     *
     * <ul>
     *   <li>{@code AUTH.MFA_CHALLENGE_EXPIRED} → 401, FE shows "session timed
     *       out, please sign in again" + redirect to /platform/login.</li>
     *   <li>{@code AUTH.MFA_INVALID_CODE} → 401, FE shakes the OTP inputs.</li>
     *   <li>{@code AUTH.MFA_CHALLENGE_INVALID} → 401, malformed/missing
     *       challenge — same redirect-to-login as expired.</li>
     * </ul>
     */
    @PostMapping("/mfa/verify")
    public ResponseEntity<?> verifyMfa(@Valid @RequestBody MfaVerifyRequest req,
                                       HttpServletRequest http) {
        try {
            PlatformLoginResult r = authService.verifyMfaChallenge(
                    req, clientIp(http), http.getHeader("User-Agent"));
            return ResponseEntity.ok(toResponse(r));
        } catch (MfaChallengeExpiredException e) {
            return problem(401, "/docs/errors/mfa-challenge-expired",
                    "MFA challenge expired", e.getMessage(),
                    com.kaorisystem.auth.common.ErrorCodes.AUTH_MFA_CHALLENGE_EXPIRED);
        } catch (InvalidCredentialsException e) {
            // Distinguish "wrong code" from "wrong/missing/used challenge" via
            // the message keyword. Both are 401 — the code differentiates them
            // for FE copy. No-leak: never returns admin email or challenge id
            // in the body.
            String msg = e.getMessage();
            String code = (msg != null && msg.toLowerCase().contains("invalid mfa code"))
                    ? com.kaorisystem.auth.common.ErrorCodes.AUTH_MFA_INVALID_CODE
                    : com.kaorisystem.auth.common.ErrorCodes.AUTH_MFA_CHALLENGE_INVALID;
            return problem(401, "/docs/errors/mfa-verify-failed",
                    "MFA verification failed", msg, code);
        }
    }

    @PostMapping("/refresh")
    public ResponseEntity<?> refresh(@Valid @RequestBody RefreshRequest req) {
        try {
            return ResponseEntity.ok(toResponse(authService.refresh(req)));
        } catch (TokenReplayException e) {
            // B3 PR #8 — refresh token reused (jti SETNX dedup). Distinct
            // ``code`` so the FE can warn "your session was used elsewhere"
            // rather than the generic invalid-token toast.
            return problem(401, "/docs/errors/token-replayed",
                    "Refresh token reused", e.getMessage(),
                    com.kaorisystem.auth.common.ErrorCodes.AUTH_TOKEN_REPLAYED);
        } catch (InvalidCredentialsException e) {
            return problem(401, "/docs/errors/invalid-token",
                    "Invalid token", e.getMessage(),
                    com.kaorisystem.auth.common.ErrorCodes.AUTH_TOKEN_INVALID);
        }
    }

    // =========================================================================
    // helpers
    // =========================================================================

    private static Map<String, Object> toResponse(PlatformLoginResult r) {
        Map<String, Object> data = new LinkedHashMap<>();
        if (r.mfaRequired()) {
            // First leg of MFA-enabled login. NO session / access / refresh — the
            // FE must POST back to /auth/platform/mfa/verify with the challenge
            // token + a fresh TOTP code to receive the real session envelope.
            data.put("mfa_required",                 true);
            data.put("mfa_challenge_token",          r.mfaChallengeToken());
            data.put("mfa_challenge_expires_in_sec", r.mfaChallengeExpiresInSec());
            data.put("admin_id",                     r.adminId());
            return Map.of("data", data);
        }
        data.put("access_token",  r.accessToken());
        data.put("refresh_token", r.refreshToken());
        data.put("session_id",    r.sessionId());
        data.put("admin_id",      r.adminId());
        data.put("role",          r.role());
        data.put("mfa_enabled",   r.mfaEnabled());
        data.put("mfa_required",  false);
        data.put("expires_in_sec", r.expiresInSec());
        return Map.of("data", data);
    }

    private static String clientIp(HttpServletRequest req) {
        String forwarded = req.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            int comma = forwarded.indexOf(',');
            return comma > 0 ? forwarded.substring(0, comma).trim() : forwarded.trim();
        }
        return req.getRemoteAddr();
    }

    private static ResponseEntity<Map<String, Object>> problem(
            int status, String type, String title, String detail, String code) {
        // Phase 2 #1 — every RFC 7807 envelope now carries ``code`` so the
        // FE maps it to one i18n bundle. LinkedHashMap to keep field order
        // stable in JSON output (status / code / detail are easier to scan
        // when log-greppers see them in the same place every time).
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("type",   type);
        body.put("title",  title);
        body.put("status", status);
        body.put("code",   code);
        body.put("detail", detail);
        return ResponseEntity.status(status).body(body);
    }
}
