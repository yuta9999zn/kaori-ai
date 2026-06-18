package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.OkrRepository;
import com.kaorisystem.auth.repository.OkrRepository.KeyResultRow;
import com.kaorisystem.auth.repository.OkrRepository.ObjectivePatch;
import com.kaorisystem.auth.repository.OkrRepository.ObjectiveRow;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.Month;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;

/**
 * F-040 OKR service — validation + objective/KR orchestration.
 *
 * <p>Same thin-validation-layer pattern as F-039 RiskItemService. The
 * controller has already enforced the MANAGER role; this layer trusts
 * inputs and just validates shapes + ranges + enum membership.
 *
 * <p>Status auto-recompute mirrors the FE template's logic (file 53):
 * lag = (quarter elapsed) - (avg KR progress). ≤5% → on_track,
 * ≤15% → at_risk, &gt;15% → off_track. Done on every save so the
 * indexed status column stays trustworthy for the rollup tile.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class OkrService {

    public static final Set<String> ALLOWED_STATUS = Set.of(
            "on_track", "at_risk", "off_track");

    private static final Pattern QUARTER_PATTERN = Pattern.compile("^Q[1-4] \\d{4}$");

    private static final int TITLE_MAX = 200;
    private static final int UNIT_MAX  = 40;
    private static final int LIST_LIMIT_MAX = 200;

    private final OkrRepository repo;

    // -------------------------------------------------------------------------
    // Public API — Objectives
    // -------------------------------------------------------------------------

    public ObjectivePage list(
            UUID enterpriseId, String quarter, int page, int limit) {
        int safePage  = Math.max(1, page);
        int safeLimit = Math.max(1, Math.min(limit, LIST_LIMIT_MAX));
        int offset    = (safePage - 1) * safeLimit;

        if (quarter != null && !quarter.isBlank()) validateQuarter(quarter);

        long total = repo.countByEnterprise(enterpriseId, quarter);
        List<ObjectiveRow> objs = repo.findByEnterprise(
                enterpriseId, quarter, safeLimit, offset);

        List<ObjectiveWithKrs> hydrated = objs.stream()
                .map(o -> new ObjectiveWithKrs(o,
                        repo.findKeyResultsByObjective(o.objectiveId())))
                .toList();
        return new ObjectivePage(hydrated, total, safePage, safeLimit);
    }

    public ObjectiveWithKrs getOrThrow(UUID enterpriseId, UUID objectiveId) {
        ObjectiveRow obj = repo.findByIdAndEnterprise(objectiveId, enterpriseId)
                .orElseThrow(() -> new ObjectiveNotFoundException(
                        "objective not found: " + objectiveId));
        return new ObjectiveWithKrs(obj,
                repo.findKeyResultsByObjective(objectiveId));
    }

    public ObjectiveWithKrs create(
            UUID enterpriseId, UUID createdByUser, CreateRequest req) {
        validateTitle(req.title());
        validateQuarter(req.quarter());
        validateKrList(req.keyResults());

        // Status: derive from KR initial values + quarter progress.
        String initialStatus = computeStatus(req.quarter(), req.keyResults());

        ObjectiveRow row = new ObjectiveRow(
                null,
                enterpriseId,
                req.quarter(),
                req.title().trim(),
                req.ownerUserId(),
                initialStatus,
                createdByUser,
                null,
                null);
        UUID id = repo.insertObjective(row);

        // Insert KRs in submitted order.
        List<KeyResultRow> krRows = req.keyResults().stream()
                .map(kr -> new KeyResultRow(
                        null, id, enterpriseId,
                        kr.title().trim(),
                        kr.unit() == null ? "" : kr.unit().trim(),
                        kr.target(),
                        kr.currentValue() == null ? BigDecimal.ZERO : kr.currentValue(),
                        0, null, null))
                .toList();
        repo.replaceKeyResults(id, enterpriseId, krRows);

        log.info("okr.create enterprise_id={} objective_id={} kr_count={} status={}",
                enterpriseId, id, krRows.size(), initialStatus);

        return getOrThrow(enterpriseId, id);
    }

    public ObjectiveWithKrs update(
            UUID enterpriseId, UUID objectiveId, UpdateRequest req) {
        ObjectiveWithKrs current = getOrThrow(enterpriseId, objectiveId);

        if (req.isEmpty()) {
            throw new EmptyUpdateException("at least one field must be provided");
        }
        if (req.title() != null) validateTitle(req.title());
        if (req.quarter() != null) validateQuarter(req.quarter());
        if (req.status() != null) validateStatus(req.status());
        if (req.keyResults() != null) validateKrList(req.keyResults());

        String quarterAfter = req.quarter() != null ? req.quarter() : current.objective().quarter();
        List<KrUpsert> krsAfter = req.keyResults() != null
                ? req.keyResults()
                : current.keyResults().stream()
                    .map(k -> new KrUpsert(k.title(), k.unit(), k.target(), k.currentValue()))
                    .toList();

        // Auto-recompute status when KRs change OR quarter changes — but
        // honour an explicit status override from the caller.
        String statusAfter = req.status() != null
                ? req.status()
                : computeStatus(quarterAfter, krsAfter);

        repo.updateObjective(objectiveId, enterpriseId, new ObjectivePatch(
                req.quarter(), req.title(), req.ownerUserId(), statusAfter));

        if (req.keyResults() != null) {
            List<KeyResultRow> krRows = req.keyResults().stream()
                    .map(kr -> new KeyResultRow(
                            null, objectiveId, enterpriseId,
                            kr.title().trim(),
                            kr.unit() == null ? "" : kr.unit().trim(),
                            kr.target(),
                            kr.currentValue() == null ? BigDecimal.ZERO : kr.currentValue(),
                            0, null, null))
                    .toList();
            repo.replaceKeyResults(objectiveId, enterpriseId, krRows);
        }

        log.info("okr.update enterprise_id={} objective_id={} status={}",
                enterpriseId, objectiveId, statusAfter);
        return getOrThrow(enterpriseId, objectiveId);
    }

    public ObjectiveWithKrs updateKeyResultProgress(
            UUID enterpriseId, UUID objectiveId, UUID krId, BigDecimal currentValue) {
        ObjectiveWithKrs current = getOrThrow(enterpriseId, objectiveId);

        if (currentValue == null || currentValue.signum() < 0) {
            throw new InvalidOkrException("current_value must be ≥ 0");
        }
        boolean krBelongs = current.keyResults().stream()
                .anyMatch(k -> k.krId().equals(krId));
        if (!krBelongs) {
            throw new ObjectiveNotFoundException("kr not found in objective: " + krId);
        }

        int rows = repo.updateKeyResultCurrent(krId, objectiveId, currentValue);
        if (rows == 0) {
            throw new ObjectiveNotFoundException("kr not found: " + krId);
        }

        // Status follows KR progress — bump it now so the rollup tile
        // reflects this update without waiting for a full objective save.
        List<KrUpsert> krsAfter = current.keyResults().stream()
                .map(k -> new KrUpsert(
                        k.title(), k.unit(), k.target(),
                        k.krId().equals(krId) ? currentValue : k.currentValue()))
                .toList();
        String statusAfter = computeStatus(current.objective().quarter(), krsAfter);
        repo.updateObjective(objectiveId, enterpriseId, new ObjectivePatch(
                null, null, null, statusAfter));

        log.info("okr.kr_update enterprise_id={} objective_id={} kr_id={} -> status={}",
                enterpriseId, objectiveId, krId, statusAfter);
        return getOrThrow(enterpriseId, objectiveId);
    }

    public void softDelete(UUID enterpriseId, UUID objectiveId) {
        getOrThrow(enterpriseId, objectiveId);
        int rows = repo.softDelete(objectiveId, enterpriseId);
        if (rows == 0) {
            throw new ObjectiveNotFoundException("objective not found: " + objectiveId);
        }
        log.info("okr.soft_delete enterprise_id={} objective_id={}",
                enterpriseId, objectiveId);
    }

    /**
     * Status rollup for the /strategy/summary tile. Backfills missing
     * buckets with 0 so the FE doesn't need null checks.
     */
    public StatusRollup rollup(UUID enterpriseId, String quarter) {
        if (quarter != null && !quarter.isBlank()) validateQuarter(quarter);

        Map<String, Long> raw = repo.statusRollup(enterpriseId, quarter);
        Map<String, Long> backfilled = new LinkedHashMap<>();
        backfilled.put("on_track",  raw.getOrDefault("on_track",  0L));
        backfilled.put("at_risk",   raw.getOrDefault("at_risk",   0L));
        backfilled.put("off_track", raw.getOrDefault("off_track", 0L));
        long total = backfilled.values().stream().mapToLong(Long::longValue).sum();
        return new StatusRollup(backfilled, total, quarter);
    }

    // -------------------------------------------------------------------------
    // Status auto-compute (mirrors FE template 53 logic)
    // -------------------------------------------------------------------------

    /**
     * Returns the status bucket given the quarter and a list of KRs.
     * lag = quarter elapsed fraction - avg KR progress fraction.
     *   lag ≤ 0.05 → on_track
     *   lag ≤ 0.15 → at_risk
     *   else        → off_track
     *
     * <p>If no KRs, defaults to on_track (nothing to be lagging on yet).
     */
    static String computeStatus(String quarter, List<KrUpsert> krs) {
        if (krs == null || krs.isEmpty()) return "on_track";

        double quarterProgress = quarterElapsedFraction(quarter);
        double krAvg = krs.stream()
                .mapToDouble(OkrService::krProgressFraction)
                .average().orElse(0.0);
        double lag = quarterProgress - krAvg;

        if (lag <= 0.05) return "on_track";
        if (lag <= 0.15) return "at_risk";
        return "off_track";
    }

    private static double krProgressFraction(KrUpsert kr) {
        if (kr.target() == null || kr.target().signum() <= 0) return 0.0;
        BigDecimal current = kr.currentValue() == null ? BigDecimal.ZERO : kr.currentValue();
        double ratio = current.doubleValue() / kr.target().doubleValue();
        return Math.max(0.0, Math.min(1.0, ratio));
    }

    /**
     * Fraction of the named quarter that has elapsed as of today,
     * clamped to [0, 1]. Future quarters → 0, past quarters → 1.
     */
    static double quarterElapsedFraction(String quarter) {
        // quarter is already validated upstream — Q[1-4] YYYY.
        int qNum = Character.getNumericValue(quarter.charAt(1));
        int year = Integer.parseInt(quarter.substring(3));
        Month start = Month.of((qNum - 1) * 3 + 1);
        LocalDate qStart = LocalDate.of(year, start, 1);
        LocalDate qEnd   = qStart.plusMonths(3).minusDays(1);
        LocalDate today  = LocalDate.now();

        if (today.isBefore(qStart)) return 0.0;
        if (today.isAfter(qEnd))    return 1.0;

        long total   = qEnd.toEpochDay() - qStart.toEpochDay() + 1;
        long elapsed = today.toEpochDay() - qStart.toEpochDay() + 1;
        return (double) elapsed / total;
    }

    // -------------------------------------------------------------------------
    // Validation
    // -------------------------------------------------------------------------

    private static void validateTitle(String title) {
        if (title == null || title.isBlank()) {
            throw new InvalidOkrException("title is required");
        }
        if (title.length() > TITLE_MAX) {
            throw new InvalidOkrException("title must be ≤ " + TITLE_MAX + " characters");
        }
    }

    private static void validateQuarter(String q) {
        if (q == null || !QUARTER_PATTERN.matcher(q).matches()) {
            throw new InvalidOkrException("quarter must match 'Q[1-4] YYYY' (e.g. 'Q2 2026')");
        }
    }

    private static void validateStatus(String s) {
        if (!ALLOWED_STATUS.contains(s)) {
            throw new InvalidOkrException("status must be one of " + ALLOWED_STATUS);
        }
    }

    private static void validateKrList(List<KrUpsert> krs) {
        if (krs == null || krs.isEmpty()) {
            throw new InvalidOkrException("at least one key result is required");
        }
        if (krs.size() > 10) {
            throw new InvalidOkrException("max 10 key results per objective");
        }
        for (int i = 0; i < krs.size(); i++) {
            KrUpsert kr = krs.get(i);
            if (kr.title() == null || kr.title().isBlank()) {
                throw new InvalidOkrException("kr[" + i + "].title is required");
            }
            if (kr.title().length() > TITLE_MAX) {
                throw new InvalidOkrException("kr[" + i + "].title must be ≤ " + TITLE_MAX);
            }
            if (kr.unit() != null && kr.unit().length() > UNIT_MAX) {
                throw new InvalidOkrException("kr[" + i + "].unit must be ≤ " + UNIT_MAX);
            }
            if (kr.target() == null || kr.target().signum() <= 0) {
                throw new InvalidOkrException("kr[" + i + "].target must be > 0");
            }
            if (kr.currentValue() != null && kr.currentValue().signum() < 0) {
                throw new InvalidOkrException("kr[" + i + "].current_value must be ≥ 0");
            }
        }
    }

    // -------------------------------------------------------------------------
    // DTOs
    // -------------------------------------------------------------------------

    public record CreateRequest(
            String         quarter,
            String         title,
            UUID           ownerUserId,
            List<KrUpsert> keyResults
    ) {}

    public record UpdateRequest(
            String         quarter,
            String         title,
            UUID           ownerUserId,
            String         status,
            List<KrUpsert> keyResults
    ) {
        boolean isEmpty() {
            return quarter == null && title == null && ownerUserId == null
                && status == null && keyResults == null;
        }
    }

    /** Caller-supplied KR shape. krId omitted because we re-create on every save. */
    public record KrUpsert(
            String     title,
            String     unit,
            BigDecimal target,
            BigDecimal currentValue
    ) {}

    public record ObjectiveWithKrs(
            ObjectiveRow         objective,
            List<KeyResultRow>   keyResults
    ) {}

    public record ObjectivePage(
            List<ObjectiveWithKrs> items,
            long                   total,
            int                    page,
            int                    limit
    ) {}

    public record StatusRollup(
            Map<String, Long> byStatus,
            long              total,
            String            quarter
    ) {}

    public static class ObjectiveNotFoundException extends RuntimeException {
        public ObjectiveNotFoundException(String m) { super(m); }
    }
    public static class InvalidOkrException extends RuntimeException {
        public InvalidOkrException(String m) { super(m); }
    }
    public static class EmptyUpdateException extends RuntimeException {
        public EmptyUpdateException(String m) { super(m); }
    }
}
