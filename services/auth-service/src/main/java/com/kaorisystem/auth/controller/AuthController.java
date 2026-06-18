package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.dto.AuthDtos.*;
import com.kaorisystem.auth.service.AuthService;
import com.kaorisystem.auth.service.AuthService.InvalidCredentialsException;
import com.kaorisystem.auth.service.AuthService.LockoutException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/auth")
@RequiredArgsConstructor
@Slf4j
public class AuthController {

    private final AuthService authService;

    @PostMapping("/login")
    public ResponseEntity<?> login(@Valid @RequestBody LoginRequest req) {
        try {
            return ResponseEntity.ok(authService.login(req));
        } catch (LockoutException e) {
            ErrorResponse err = new ErrorResponse(423, "LOCKED", e.getMessage());
            err.setLockoutRemainingSeconds(e.getRemainingSeconds());
            return ResponseEntity.status(423).body(err);
        } catch (InvalidCredentialsException e) {
            return ResponseEntity.status(401)
                    .body(new ErrorResponse(401, "INVALID_CREDENTIALS", e.getMessage()));
        }
    }

    @PostMapping("/logout")
    public ResponseEntity<Void> logout(HttpServletRequest request) {
        String bearer = request.getHeader("Authorization");
        if (bearer != null && bearer.startsWith("Bearer ")) {
            authService.logout(bearer.substring(7), clientIp(request));
        }
        return ResponseEntity.noContent().build();
    }

    /** X-Forwarded-For-aware IP extraction; same shape as PlatformSecurityController. */
    private static String clientIp(HttpServletRequest req) {
        String forwarded = req.getHeader("X-Forwarded-For");
        if (forwarded != null && !forwarded.isBlank()) {
            int comma = forwarded.indexOf(',');
            return comma > 0 ? forwarded.substring(0, comma).trim() : forwarded.trim();
        }
        return req.getRemoteAddr();
    }

    @PostMapping("/refresh")
    public ResponseEntity<?> refresh(@Valid @RequestBody RefreshRequest req) {
        try {
            return ResponseEntity.ok(authService.refresh(req));
        } catch (InvalidCredentialsException e) {
            return ResponseEntity.status(401)
                    .body(new ErrorResponse(401, "INVALID_TOKEN", e.getMessage()));
        }
    }

    @PostMapping("/forgot-password")
    public ResponseEntity<Void> forgotPassword(@Valid @RequestBody ForgotPasswordRequest req) {
        authService.forgotPassword(req);
        return ResponseEntity.ok().build();  // Always 200 (anti-enumeration)
    }

    @PostMapping("/reset-password")
    public ResponseEntity<?> resetPassword(@Valid @RequestBody ResetPasswordRequest req) {
        try {
            authService.resetPassword(req);
            return ResponseEntity.ok().build();
        } catch (InvalidCredentialsException e) {
            return ResponseEntity.status(400)
                    .body(new ErrorResponse(400, "INVALID_TOKEN", e.getMessage()));
        }
    }

    /**
     * P1-S1 (P2-M20-007) — logged-in change-password flow. Re-verifies
     * the caller's current password before rotating to the new one and
     * clears the {@code must_change_password} flag (closing the invite
     * loop for users who skipped the email-token reset path).
     *
     * <p>Caller is identified by the {@code X-User-ID} header that the
     * gateway forwards from the validated JWT (K-7 / K-12 — never trust
     * a user_id from the request body).
     *
     * <p>Returns 204 on success (FE keeps the existing JWT — only the
     * password hash changed; refresh tokens are invalidated downstream
     * via Redis so other sessions must re-auth).
     */
    @PostMapping("/users/me/change-password")
    public ResponseEntity<?> changeOwnPassword(
            @Valid @RequestBody ChangePasswordRequest req,
            @RequestHeader(value = "X-User-ID", required = false) String userIdHeader) {
        if (userIdHeader == null || userIdHeader.isBlank()) {
            return ResponseEntity.status(401)
                    .body(new ErrorResponse(401, "UNAUTHENTICATED",
                            "Missing X-User-ID — request did not pass the gateway."));
        }
        try {
            java.util.UUID userId = java.util.UUID.fromString(userIdHeader);
            authService.changeOwnPassword(userId, req.getCurrentPassword(), req.getNewPassword());
            return ResponseEntity.noContent().build();
        } catch (IllegalArgumentException e) {
            return ResponseEntity.status(400)
                    .body(new ErrorResponse(400, "INVALID_USER_ID",
                            "X-User-ID must be a valid UUID."));
        } catch (InvalidCredentialsException e) {
            return ResponseEntity.status(400)
                    .body(new ErrorResponse(400, "INVALID_PASSWORD", e.getMessage()));
        }
    }

    @GetMapping("/health")
    public ResponseEntity<String> health() {
        return ResponseEntity.ok("OK");
    }

    @PostMapping("/workspace/activate")
    public ResponseEntity<?> activateWorkspace(@Valid @RequestBody ActivateKeyRequest req) {
        try {
            return ResponseEntity.ok(authService.activateWorkspace(req));
        } catch (AuthService.InvalidCredentialsException e) {
            return ResponseEntity.status(400)
                    .body(new ErrorResponse(400, "INVALID_KEY", e.getMessage()));
        } catch (com.kaorisystem.auth.service.PlatformKeyService.KeyNotFoundException e) {
            // Without this catch, Spring Security's ExceptionTranslationFilter
            // treats the uncaught exception as access-denied and returns 403
            // with an empty body — opaque to the FE register form. Map to a
            // typed 400 so callers can show "key invalid / revoked / used".
            return ResponseEntity.status(400)
                    .body(new ErrorResponse(400, "INVALID_KEY", e.getMessage()));
        }
    }
}
