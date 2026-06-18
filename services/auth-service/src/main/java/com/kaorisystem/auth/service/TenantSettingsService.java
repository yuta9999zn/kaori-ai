package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.TenantSettings;
import com.kaorisystem.auth.repository.TenantSettingsRepository;
import com.kaorisystem.auth.repository.TenantSettingsRepository.EnterpriseDescriptor;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.UUID;

/**
 * F-016 — Enterprise Settings (Phase 1 close-out, Ghost fix).
 *
 * Backed by Spring Data JPA via {@link TenantSettingsRepository}. Lazy-creates
 * a row with default values on first GET so existing tenants don't need a
 * migration backfill — the row appears the moment a MANAGER opens the page.
 *
 * <p>K-12 invariant: callers MUST pass {@code enterpriseId} extracted from
 * the JWT (X-Enterprise-ID header injected by the gateway), never from a
 * request body or query string.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class TenantSettingsService {

    private final TenantSettingsRepository repository;

    @Transactional
    public SettingsView get(UUID enterpriseId) {
        TenantSettings entity = repository.findById(enterpriseId)
                .orElseGet(() -> lazyCreate(enterpriseId));
        return toView(entity, descriptor(enterpriseId));
    }

    @Transactional
    public SettingsView patch(UUID enterpriseId, PatchRequest req) {
        TenantSettings entity = repository.findById(enterpriseId)
                .orElseGet(() -> lazyCreate(enterpriseId));

        if (req.theme() != null) {
            String theme = req.theme().trim().toLowerCase();
            if (!theme.equals("light") && !theme.equals("dark")) {
                throw new InvalidThemeException("theme must be 'light' or 'dark'");
            }
            entity.setTheme(theme);
        }
        if (req.consentExternalAi() != null) {
            entity.setConsentExternalAi(req.consentExternalAi());
        }
        if (req.notificationEmail() != null) {
            entity.setNotificationEmail(req.notificationEmail());
        }
        if (req.brandingLogoUrl() != null) {
            String trimmed = req.brandingLogoUrl().trim();
            entity.setBrandingLogoUrl(trimmed.isEmpty() ? null : trimmed);
        }
        if (req.brandingAccentColor() != null) {
            String trimmed = req.brandingAccentColor().trim();
            entity.setBrandingAccentColor(trimmed.isEmpty() ? null : trimmed);
        }

        TenantSettings saved = repository.save(entity);
        log.info("enterprise.settings.updated enterprise_id={} consent_external_ai={}",
                enterpriseId, saved.isConsentExternalAi());
        return toView(saved, descriptor(enterpriseId));
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private TenantSettings lazyCreate(UUID enterpriseId) {
        // Verify enterprise exists before creating settings — FK would catch it
        // anyway but we want a 404 instead of a 500.
        if (repository.findEnterpriseDescriptor(enterpriseId).isEmpty()) {
            throw new EnterpriseNotFoundException("Enterprise not found: " + enterpriseId);
        }
        TenantSettings fresh = new TenantSettings();
        fresh.setEnterpriseId(enterpriseId);
        // PrePersist fills theme/createdAt/updatedAt; consent + notification stay
        // at their primitive false defaults so K-4 starts opt-in.
        return repository.save(fresh);
    }

    private EnterpriseDescriptor descriptor(UUID enterpriseId) {
        return repository.findEnterpriseDescriptor(enterpriseId)
                .orElseThrow(() -> new EnterpriseNotFoundException(
                        "Enterprise not found: " + enterpriseId));
    }

    private static SettingsView toView(TenantSettings e, EnterpriseDescriptor d) {
        return new SettingsView(
                e.getEnterpriseId(),
                d.getName(),
                d.getLocale(),
                e.getTheme(),
                e.isConsentExternalAi(),
                e.isNotificationEmail(),
                e.getBrandingLogoUrl(),
                e.getBrandingAccentColor(),
                e.getCreatedAt().toString(),
                e.getUpdatedAt().toString()
        );
    }

    // =========================================================================
    // DTOs + exceptions (kept inside the service so the controller doesn't
    // grow another dto/ subpackage just for one endpoint pair)
    // =========================================================================

    public record SettingsView(
            UUID    enterpriseId,
            String  enterpriseName,
            String  locale,
            String  theme,
            boolean consentExternalAi,
            boolean notificationEmail,
            String  brandingLogoUrl,
            String  brandingAccentColor,
            String  createdAt,
            String  updatedAt
    ) {}

    public record PatchRequest(
            String  theme,
            Boolean consentExternalAi,
            Boolean notificationEmail,
            String  brandingLogoUrl,
            String  brandingAccentColor
    ) {
        public boolean isEmpty() {
            return theme == null
                && consentExternalAi == null
                && notificationEmail == null
                && brandingLogoUrl == null
                && brandingAccentColor == null;
        }
    }

    public static class EnterpriseNotFoundException extends RuntimeException {
        public EnterpriseNotFoundException(String msg) { super(msg); }
    }

    public static class InvalidThemeException extends RuntimeException {
        public InvalidThemeException(String msg) { super(msg); }
    }
}
