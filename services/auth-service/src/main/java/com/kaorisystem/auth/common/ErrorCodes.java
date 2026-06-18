package com.kaorisystem.auth.common;

import java.util.Map;

/**
 * Canonical error_code registry — Phase 2 error-handling group #1.
 *
 * <p>Mirror of {@code services/{ai-orchestrator,data-pipeline,llm-gateway,notification-service}/.../error_codes.py}.
 * Codes carry the same string spelling across languages so the FE can
 * map ``DOMAIN.NAME`` to a single i18n bundle entry regardless of which
 * service responded.
 *
 * <p>Every RFC 7807 (K-14) response should include a {@code code} field
 * alongside the standard ``type/title/status/detail`` envelope. Routes
 * that don't pick an explicit code can fall back to
 * {@link #defaultCodeFor(int)} which maps an HTTP status to the closest
 * canonical code.
 *
 * <p>Adding a new code:
 * <ol>
 *   <li>Append a constant in the matching domain section below.</li>
 *   <li>Mirror the same constant string in the four Python error_codes.py
 *       mirrors.</li>
 *   <li>Document the user-facing text in the FE i18n bundle when a route
 *       starts emitting it.</li>
 * </ol>
 */
public final class ErrorCodes {

    private ErrorCodes() {}

    // =========================================================================
    // AUTH — login / session / token errors (auth-service domain)
    // =========================================================================
    public static final String AUTH_INVALID_CREDENTIALS = "AUTH.INVALID_CREDENTIALS";
    public static final String AUTH_LOCKED              = "AUTH.LOCKED";
    public static final String AUTH_TOKEN_REVOKED       = "AUTH.TOKEN_REVOKED";
    public static final String AUTH_TOKEN_INVALID       = "AUTH.TOKEN_INVALID";
    public static final String AUTH_TOKEN_EXPIRED       = "AUTH.TOKEN_EXPIRED";
    public static final String AUTH_WRONG_TOKEN_KIND    = "AUTH.WRONG_TOKEN_KIND";
    public static final String AUTH_FORBIDDEN_ROLE      = "AUTH.FORBIDDEN_ROLE";
    public static final String AUTH_MISSING_BEARER      = "AUTH.MISSING_BEARER";
    public static final String AUTH_MFA_REQUIRED        = "AUTH.MFA_REQUIRED";
    public static final String AUTH_MFA_INVALID_CODE    = "AUTH.MFA_INVALID_CODE";
    public static final String AUTH_MFA_CHALLENGE_INVALID = "AUTH.MFA_CHALLENGE_INVALID";
    public static final String AUTH_MFA_CHALLENGE_EXPIRED = "AUTH.MFA_CHALLENGE_EXPIRED";
    public static final String AUTH_TOKEN_REPLAYED      = "AUTH.TOKEN_REPLAYED";
    public static final String AUTH_SESSION_EXPIRED     = "AUTH.SESSION_EXPIRED";

    // =========================================================================
    // VALIDATION — request shape, field types, business rules
    // =========================================================================
    public static final String VALIDATION_GENERIC           = "VALIDATION.GENERIC";
    public static final String VALIDATION_MISSING_FIELD     = "VALIDATION.MISSING_FIELD";
    public static final String VALIDATION_INVALID_EMAIL     = "VALIDATION.INVALID_EMAIL";
    public static final String VALIDATION_INVALID_UUID      = "VALIDATION.INVALID_UUID";
    public static final String VALIDATION_INVALID_DATE      = "VALIDATION.INVALID_DATE";
    public static final String VALIDATION_INVALID_ENUM      = "VALIDATION.INVALID_ENUM";
    public static final String VALIDATION_PAYLOAD_TOO_LARGE = "VALIDATION.PAYLOAD_TOO_LARGE";

    // =========================================================================
    // BILLING
    // =========================================================================
    public static final String BILLING_QUOTA_EXCEEDED      = "BILLING.QUOTA_EXCEEDED";
    public static final String BILLING_AGGREGATION_RUNNING = "BILLING.AGGREGATION_RUNNING";
    public static final String BILLING_NO_QUOTA            = "BILLING.NO_QUOTA";
    public static final String BILLING_PLAN_NOT_FOUND      = "BILLING.PLAN_NOT_FOUND";

    // =========================================================================
    // PIPELINE
    // =========================================================================
    public static final String PIPELINE_UPLOAD_REJECTED = "PIPELINE.UPLOAD_REJECTED";
    public static final String PIPELINE_DUPLICATE_FILE  = "PIPELINE.DUPLICATE_FILE";
    public static final String PIPELINE_SCHEMA_INVALID  = "PIPELINE.SCHEMA_INVALID";
    public static final String PIPELINE_RUN_NOT_FOUND   = "PIPELINE.RUN_NOT_FOUND";
    public static final String PIPELINE_INVALID_STATE   = "PIPELINE.INVALID_STATE";

    // =========================================================================
    // LLM
    // =========================================================================
    public static final String LLM_CONSENT_DENIED      = "LLM.CONSENT_DENIED";
    public static final String LLM_GATEWAY_UNAVAILABLE = "LLM.GATEWAY_UNAVAILABLE";
    public static final String LLM_TIMEOUT             = "LLM.TIMEOUT";
    public static final String LLM_QUOTA_EXCEEDED      = "LLM.QUOTA_EXCEEDED";

    // =========================================================================
    // JOB
    // =========================================================================
    public static final String JOB_ALREADY_RUNNING = "JOB.ALREADY_RUNNING";
    public static final String JOB_LEASE_ORPHANED  = "JOB.LEASE_ORPHANED";

    // =========================================================================
    // RATE / SYSTEM
    // =========================================================================
    public static final String RATE_LIMIT_EXCEEDED      = "RATE.LIMIT_EXCEEDED";
    public static final String RATE_IDEMPOTENCY_MISSING = "RATE.IDEMPOTENCY_MISSING";
    public static final String SYSTEM_INTERNAL_ERROR    = "SYSTEM.INTERNAL_ERROR";
    public static final String SYSTEM_UNAVAILABLE       = "SYSTEM.UNAVAILABLE";

    public static final String RESOURCE_NOT_FOUND = "RESOURCE.NOT_FOUND";
    public static final String RESOURCE_CONFLICT  = "RESOURCE.CONFLICT";

    /**
     * Fallback code when a route doesn't pick an explicit one. Maps HTTP
     * status to the closest canonical code so the FE always sees a
     * non-null ``code`` field.
     */
    private static final Map<Integer, String> DEFAULT_BY_STATUS = Map.ofEntries(
            Map.entry(400, VALIDATION_GENERIC),
            Map.entry(401, AUTH_TOKEN_INVALID),
            Map.entry(403, AUTH_FORBIDDEN_ROLE),
            Map.entry(404, RESOURCE_NOT_FOUND),
            Map.entry(409, RESOURCE_CONFLICT),
            Map.entry(422, VALIDATION_GENERIC),
            Map.entry(423, AUTH_LOCKED),
            Map.entry(429, RATE_LIMIT_EXCEEDED),
            Map.entry(500, SYSTEM_INTERNAL_ERROR),
            Map.entry(502, SYSTEM_UNAVAILABLE),
            Map.entry(503, SYSTEM_UNAVAILABLE),
            Map.entry(504, SYSTEM_UNAVAILABLE)
    );

    public static String defaultCodeFor(int status) {
        return DEFAULT_BY_STATUS.getOrDefault(status, SYSTEM_INTERNAL_ERROR);
    }
}
