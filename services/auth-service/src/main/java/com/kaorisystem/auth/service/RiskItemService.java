package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.RiskItemRepository;
import com.kaorisystem.auth.repository.RiskItemRepository.RiskItemPatch;
import com.kaorisystem.auth.repository.RiskItemRepository.RiskItemRow;
import com.kaorisystem.auth.repository.RiskItemRepository.SeverityCount;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.time.LocalDate;
import java.util.List;
import java.util.Set;
import java.util.UUID;

/**
 * F-039 Risk Item — CRUD service.
 *
 * <p>Same pattern as F-037 AlertRuleService: thin validation layer
 * over the JdbcTemplate repo. MANAGER role gating happens at the
 * controller; the service trusts inputs from there.
 *
 * <p>Score + severity are computed by the migration-033 trigger
 * (likelihood × impact → score 1..25 → severity tier). The service
 * never sets either — the DB is authoritative.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class RiskItemService {

    public static final Set<String> ALLOWED_STATUS = Set.of("open", "mitigating", "closed");
    public static final Set<String> ALLOWED_SEVERITY = Set.of("low", "medium", "high", "critical");
    public static final Set<String> ALLOWED_CATEGORY = Set.of(
            "operational", "financial", "regulatory",
            "reputational", "strategic", "technical");
    public static final String DEFAULT_CATEGORY = "operational";

    private static final int LIKELIHOOD_MIN = 1;
    private static final int LIKELIHOOD_MAX = 5;
    private static final int IMPACT_MIN = 1;
    private static final int IMPACT_MAX = 5;
    private static final int PROGRESS_MIN = 0;
    private static final int PROGRESS_MAX = 100;

    private final RiskItemRepository repo;

    // -------------------------------------------------------------------------
    // Public API
    // -------------------------------------------------------------------------

    public RiskItemPage list(
            UUID enterpriseId, String status, String severity, String category,
            int page, int limit) {
        int safePage  = Math.max(1, page);
        int safeLimit = Math.max(1, Math.min(limit, 200));
        int offset    = (safePage - 1) * safeLimit;

        if (status != null && !status.isBlank()) {
            validateStatus(status);
        }
        if (severity != null && !severity.isBlank()) {
            validateSeverity(severity);
        }
        if (category != null && !category.isBlank()) {
            validateCategory(category);
        }

        long total = repo.countByEnterprise(enterpriseId, status, severity, category);
        List<RiskItemRow> items = repo.findByEnterprise(
                enterpriseId, status, severity, category, safeLimit, offset);
        return new RiskItemPage(items, total, safePage, safeLimit);
    }

    public List<SeverityCount> severityRollup(UUID enterpriseId) {
        return repo.severityRollup(enterpriseId);
    }

    public RiskItemRow getOrThrow(UUID enterpriseId, UUID riskId) {
        return repo.findByIdAndEnterprise(riskId, enterpriseId)
                .orElseThrow(() -> new RiskItemNotFoundException(
                        "risk item not found: " + riskId));
    }

    public RiskItemRow create(UUID enterpriseId, UUID createdByUser, CreateRequest req) {
        validateTitle(req.title());
        validateLikelihoodImpact(req.likelihood(), req.impact());
        if (req.status() != null) validateStatus(req.status());
        if (req.category() != null) validateCategory(req.category());
        if (req.mitigationProgress() != null) validateProgress(req.mitigationProgress());

        RiskItemRow row = new RiskItemRow(
                null,
                enterpriseId,
                req.title().trim(),
                req.description() == null ? null : req.description().trim(),
                req.category() == null ? DEFAULT_CATEGORY : req.category(),
                req.likelihood(),
                req.impact(),
                0,                    // score — recomputed by trigger
                "low",                // severity — recomputed by trigger
                req.status() == null ? "open" : req.status(),
                req.mitigationPlan() == null ? null : req.mitigationPlan().trim(),
                req.mitigationProgress() == null ? 0 : req.mitigationProgress(),
                req.ownerUserId(),
                req.dueDate(),
                "manual",
                createdByUser,
                null,
                null);
        UUID id = repo.insert(row);
        log.info("risk_item.create enterprise_id={} risk_id={} severity_input={}x{}",
                enterpriseId, id, req.likelihood(), req.impact());
        return repo.findByIdAndEnterprise(id, enterpriseId)
                .orElseThrow(() -> new IllegalStateException(
                        "risk_items not found after insert: " + id));
    }

    public RiskItemRow update(UUID enterpriseId, UUID riskId, UpdateRequest req) {
        getOrThrow(enterpriseId, riskId);

        if (req.isEmpty()) {
            throw new EmptyUpdateException("at least one field must be provided");
        }
        if (req.title() != null) validateTitle(req.title());
        if (req.category() != null) validateCategory(req.category());
        if (req.likelihood() != null) validateLikelihood(req.likelihood());
        if (req.impact() != null) validateImpact(req.impact());
        if (req.status() != null) validateStatus(req.status());
        if (req.mitigationProgress() != null) validateProgress(req.mitigationProgress());

        int rows = repo.update(riskId, enterpriseId, new RiskItemPatch(
                req.title(),
                req.description(),
                req.category(),
                req.likelihood(),
                req.impact(),
                req.status(),
                req.mitigationPlan(),
                req.mitigationProgress(),
                req.ownerUserId(),
                req.dueDate()));
        if (rows == 0) {
            throw new RiskItemNotFoundException("risk item not found: " + riskId);
        }
        log.info("risk_item.update enterprise_id={} risk_id={}", enterpriseId, riskId);
        return repo.findByIdAndEnterprise(riskId, enterpriseId)
                .orElseThrow(() -> new IllegalStateException(
                        "risk_items disappeared after update: " + riskId));
    }

    public void softDelete(UUID enterpriseId, UUID riskId) {
        getOrThrow(enterpriseId, riskId);
        int rows = repo.softDelete(riskId, enterpriseId);
        if (rows == 0) {
            throw new RiskItemNotFoundException("risk item not found: " + riskId);
        }
        log.info("risk_item.soft_delete enterprise_id={} risk_id={}", enterpriseId, riskId);
    }

    // -------------------------------------------------------------------------
    // Validation
    // -------------------------------------------------------------------------

    private static void validateTitle(String title) {
        if (title == null || title.isBlank()) {
            throw new InvalidRiskItemException("title is required");
        }
        if (title.length() > 200) {
            throw new InvalidRiskItemException("title must be ≤ 200 characters");
        }
    }

    private static void validateLikelihoodImpact(Integer likelihood, Integer impact) {
        validateLikelihood(likelihood);
        validateImpact(impact);
    }

    private static void validateLikelihood(Integer v) {
        if (v == null || v < LIKELIHOOD_MIN || v > LIKELIHOOD_MAX) {
            throw new InvalidRiskItemException(
                    "likelihood must be " + LIKELIHOOD_MIN + ".." + LIKELIHOOD_MAX);
        }
    }

    private static void validateImpact(Integer v) {
        if (v == null || v < IMPACT_MIN || v > IMPACT_MAX) {
            throw new InvalidRiskItemException(
                    "impact must be " + IMPACT_MIN + ".." + IMPACT_MAX);
        }
    }

    private static void validateStatus(String status) {
        if (!ALLOWED_STATUS.contains(status)) {
            throw new InvalidRiskItemException(
                    "status must be one of " + ALLOWED_STATUS);
        }
    }

    private static void validateSeverity(String severity) {
        if (!ALLOWED_SEVERITY.contains(severity)) {
            throw new InvalidRiskItemException(
                    "severity must be one of " + ALLOWED_SEVERITY);
        }
    }

    private static void validateCategory(String category) {
        if (!ALLOWED_CATEGORY.contains(category)) {
            throw new InvalidRiskItemException(
                    "category must be one of " + ALLOWED_CATEGORY);
        }
    }

    private static void validateProgress(int progress) {
        if (progress < PROGRESS_MIN || progress > PROGRESS_MAX) {
            throw new InvalidRiskItemException(
                    "mitigation_progress must be " + PROGRESS_MIN + ".." + PROGRESS_MAX);
        }
    }

    // -------------------------------------------------------------------------
    // DTOs
    // -------------------------------------------------------------------------

    public record CreateRequest(
            String     title,
            String     description,
            String     category,
            Integer    likelihood,
            Integer    impact,
            String     status,
            String     mitigationPlan,
            Integer    mitigationProgress,
            UUID       ownerUserId,
            LocalDate  dueDate
    ) {}

    public record UpdateRequest(
            String     title,
            String     description,
            String     category,
            Integer    likelihood,
            Integer    impact,
            String     status,
            String     mitigationPlan,
            Integer    mitigationProgress,
            UUID       ownerUserId,
            LocalDate  dueDate
    ) {
        boolean isEmpty() {
            return title == null && description == null && category == null
                && likelihood == null && impact == null
                && status == null && mitigationPlan == null
                && mitigationProgress == null && ownerUserId == null
                && dueDate == null;
        }
    }

    public record RiskItemPage(List<RiskItemRow> items, long total, int page, int limit) {}

    public static class RiskItemNotFoundException extends RuntimeException {
        public RiskItemNotFoundException(String m) { super(m); }
    }
    public static class InvalidRiskItemException extends RuntimeException {
        public InvalidRiskItemException(String m) { super(m); }
    }
    public static class EmptyUpdateException extends RuntimeException {
        public EmptyUpdateException(String m) { super(m); }
    }
}
