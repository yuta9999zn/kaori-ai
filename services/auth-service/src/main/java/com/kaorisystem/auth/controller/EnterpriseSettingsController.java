package com.kaorisystem.auth.controller;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.kaorisystem.auth.service.TenantSettingsService;
import com.kaorisystem.auth.service.TenantSettingsService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.TenantSettingsService.InvalidThemeException;
import com.kaorisystem.auth.service.TenantSettingsService.PatchRequest;
import com.kaorisystem.auth.service.TenantSettingsService.SettingsView;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;
import java.util.UUID;

/**
 * F-016 — Enterprise Settings (Phase 1 close-out, Ghost fix).
 *
 * <pre>
 *   GET   /api/v1/enterprises/me/settings   any enterprise role (read)
 *   PATCH /api/v1/enterprises/me/settings   MANAGER only        (write)
 * </pre>
 *
 * <p>tenant_id is taken from the gateway-trusted {@code X-Enterprise-ID}
 * header — never from a query string or request body (K-12). The header
 * is forwarded by {@code JwtAuthFilter} after JWT validation; if it is
 * absent the request never reaches a handler that requires it.
 *
 * <p>K-4 enforcement happens in ai-orchestrator's llm_router which reads
 * {@code consent_external_ai} from this same row before any external LLM
 * call. The PATCH here is the user-facing toggle for that switch.
 */
@RestController
@RequestMapping("/api/v1/enterprises/me/settings")
@RequiredArgsConstructor
@Slf4j
public class EnterpriseSettingsController {

    private final TenantSettingsService settingsService;

    @GetMapping
    public ResponseEntity<?> get(@RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader) {
        UUID enterpriseId = parseEnterpriseHeader(enterpriseHeader);
        if (enterpriseId == null) {
            return problem(401, "/docs/errors/missing-enterprise-id",
                    "Missing tenant context",
                    "X-Enterprise-ID header is required for enterprise endpoints");
        }
        try {
            SettingsView view = settingsService.get(enterpriseId);
            return ResponseEntity.ok(Map.of("data", toJson(view)));
        } catch (EnterpriseNotFoundException e) {
            return problem(404, "/docs/errors/enterprise-not-found",
                    "Enterprise not found", e.getMessage());
        }
    }

    @PatchMapping
    public ResponseEntity<?> patch(
            @RequestHeader(value = "X-Enterprise-ID", required = false) String enterpriseHeader,
            @RequestHeader(value = "X-User-Role",     required = false) String role,
            @Valid @RequestBody PatchRequestBody body) {

        UUID enterpriseId = parseEnterpriseHeader(enterpriseHeader);
        if (enterpriseId == null) {
            return problem(401, "/docs/errors/missing-enterprise-id",
                    "Missing tenant context",
                    "X-Enterprise-ID header is required for enterprise endpoints");
        }
        if (!"MANAGER".equalsIgnoreCase(role)) {
            return problem(403, "/docs/errors/forbidden",
                    "Forbidden",
                    "Only MANAGER can modify enterprise settings");
        }

        PatchRequest req = body.toServiceRequest();
        if (req.isEmpty()) {
            return problem(400, "/docs/errors/invalid-request", "Empty update",
                    "At least one settings field must be provided");
        }

        try {
            SettingsView view = settingsService.patch(enterpriseId, req);
            return ResponseEntity.ok(Map.of("data", toJson(view)));
        } catch (EnterpriseNotFoundException e) {
            return problem(404, "/docs/errors/enterprise-not-found",
                    "Enterprise not found", e.getMessage());
        } catch (InvalidThemeException e) {
            return problem(400, "/docs/errors/invalid-theme",
                    "Invalid theme", e.getMessage());
        }
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private static UUID parseEnterpriseHeader(String s) {
        if (s == null || s.isBlank()) return null;
        try { return UUID.fromString(s.trim()); }
        catch (IllegalArgumentException e) { return null; }
    }

    private static Map<String, Object> toJson(SettingsView v) {
        Map<String, Object> m = new LinkedHashMap<>();
        m.put("enterprise_id",         v.enterpriseId());
        m.put("enterprise_name",       v.enterpriseName());
        m.put("locale",                v.locale());
        m.put("theme",                 v.theme());
        m.put("consent_external_ai",   v.consentExternalAi());
        m.put("notification_email",    v.notificationEmail());
        m.put("branding_logo_url",     v.brandingLogoUrl());
        m.put("branding_accent_color", v.brandingAccentColor());
        m.put("created_at",            v.createdAt());
        m.put("updated_at",            v.updatedAt());
        return m;
    }

    private static ResponseEntity<Map<String, Object>> problem(
            int status, String type, String title, String detail) {
        return ResponseEntity.status(status)
                .header("Content-Type", "application/problem+json")
                .body(Map.of(
                        "type",   type,
                        "title",  title,
                        "status", status,
                        "detail", detail
                ));
    }

    // =========================================================================
    // Request DTO — Jackson-friendly snake_case binding so FE doesn't need
    // a separate camelCase serialiser.
    // =========================================================================

    @Data
    public static class PatchRequestBody {
        private String theme;

        @JsonProperty("consent_external_ai")
        private Boolean consentExternalAi;

        @JsonProperty("notification_email")
        private Boolean notificationEmail;

        @JsonProperty("branding_logo_url")
        private String brandingLogoUrl;

        @JsonProperty("branding_accent_color")
        private String brandingAccentColor;

        public PatchRequest toServiceRequest() {
            return new PatchRequest(
                    theme, consentExternalAi, notificationEmail,
                    brandingLogoUrl, brandingAccentColor);
        }
    }
}
