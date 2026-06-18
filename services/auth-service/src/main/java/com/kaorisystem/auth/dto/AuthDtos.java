package com.kaorisystem.auth.dto;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

public class AuthDtos {

    @Data
    public static class LoginRequest {
        @NotBlank @Email
        private String email;
        @NotBlank
        private String password;
    }

    @Data
    public static class LoginResponse {
        private String accessToken;
        private String refreshToken;
        private String role;
        private String enterpriseId;
        private String userId;
        /**
         * P1-S1 (P2-M20-007) — TRUE means the user was invited and has not
         * yet changed their initial password. FE should route to a forced-
         * change screen before showing the regular dashboard. Cleared
         * after the first successful password change.
         */
        private Boolean mustChangePassword;
    }

    /**
     * P1-S1 (P2-M20-007) — payload for the logged-in change-password flow.
     * Different from {@link ResetPasswordRequest} which uses a one-shot
     * email token; this one re-verifies the user's CURRENT password to
     * guard against session-hijack-then-rotate attacks.
     */
    @Data
    public static class ChangePasswordRequest {
        @NotBlank
        private String currentPassword;
        @NotBlank @Size(min = 8, max = 100)
        private String newPassword;
    }

    @Data
    public static class RefreshRequest {
        @NotBlank
        private String refreshToken;
    }

    @Data
    public static class ForgotPasswordRequest {
        @NotBlank @Email
        private String email;
    }

    @Data
    public static class ResetPasswordRequest {
        @NotBlank
        private String token;
        @NotBlank @Size(min = 8, max = 100)
        private String newPassword;
    }

    @Data
    public static class ActivateKeyRequest {
        @NotBlank
        private String workspaceKey;
        @NotBlank @Email
        private String adminEmail;
        @NotBlank @Size(min = 8, max = 100)
        private String adminPassword;
        private String adminName;
    }

    @Data
    public static class ErrorResponse {
        private int status;
        private String error;
        private String message;
        private Long lockoutRemainingSeconds;

        public ErrorResponse(int status, String error, String message) {
            this.status = status;
            this.error = error;
            this.message = message;
        }
    }

    @Data
    public static class InviteUserRequest {
        @NotBlank @Email
        private String email;
        @NotBlank
        private String role;
        private String fullName;
        private String tempPassword;
    }

    @Data
    public static class ChangeRoleRequest {
        @NotBlank
        private String role;
    }

    /**
     * B3 PR #8 — second-leg payload of the platform admin 2-step login.
     * Carries the {@code mfa_challenge_token} returned by /auth/platform/login
     * + the 6-digit TOTP code from the admin's authenticator.
     */
    @Data
    public static class MfaVerifyRequest {
        @NotBlank
        private String mfaChallengeToken;
        @NotBlank @Size(min = 6, max = 6)
        private String code;
    }

    /**
     * P2-AUTH-001 SSO — FE → auth-service swap of the one-shot
     * {@code sso_code} (from /p2/auth/sso/{provider}/callback redirect)
     * for a real RS256 JWT.
     */
    @Data
    public static class SsoExchangeRequest {
        @NotBlank
        private String ssoCode;
    }

    /**
     * P2-AUTH-001 SSO — ai-orchestrator's response to the internal
     * {@code POST /p2/auth/sso/exchange-info} call. Used internally by
     * {@code SsoExchangeService}; not exposed on any REST surface.
     *
     * ai-orchestrator returns snake_case JSON (Pydantic default), while
     * Java fields are camelCase — explicit @JsonProperty mappings
     * bridge the two without changing either side's idioms.
     */
    @Data
    public static class SsoExchangeInfoResponse {
        @com.fasterxml.jackson.annotation.JsonProperty("enterprise_id")
        private String enterpriseId;
        @com.fasterxml.jackson.annotation.JsonProperty("user_id")
        private String userId;
        @com.fasterxml.jackson.annotation.JsonProperty("sso_identity_id")
        private String ssoIdentityId;
        @com.fasterxml.jackson.annotation.JsonProperty("provider")
        private String provider;
        @com.fasterxml.jackson.annotation.JsonProperty("email")
        private String email;
        @com.fasterxml.jackson.annotation.JsonProperty("consumed_at")
        private String consumedAt;
    }
}
