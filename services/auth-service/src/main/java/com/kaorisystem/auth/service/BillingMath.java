package com.kaorisystem.auth.service;

/**
 * Pure helpers shared by F-008 ({@link WorkspaceService#getBillingSummary})
 * and F-011 ({@link PlatformBillingService}). Extracting these constants and
 * the status-classification function gives both modules a single source of
 * truth for "is this enterprise warn / critical / overage?" — a discrepancy
 * here would surface as the dashboard reporting a different colour than the
 * per-workspace billing tab for the same numbers.
 *
 * <p>Thresholds align with the alert policy in CLAUDE.md §10:
 * <ul>
 *   <li>≥80% utilisation → email + in-app warning</li>
 *   <li>≥95% utilisation → extra alert + suggest upgrade</li>
 *   <li>any overage     → "overage" wins regardless of utilisation</li>
 * </ul>
 *
 * <p>No Spring, no DB. Final + private constructor so it is not subclassed
 * or instantiated.
 */
public final class BillingMath {

    public static final int WARN_PCT     = 80;
    public static final int CRITICAL_PCT = 95;

    private BillingMath() {}

    /** {@code overage|critical|warn|normal} — matches the F-008 contract. */
    public static String computeStatus(int used, int quota, int overage) {
        if (overage > 0) return "overage";
        if (quota   <= 0) return "normal";
        int pct = (int) Math.round(used * 100.0 / quota);
        if (pct >= CRITICAL_PCT) return "critical";
        if (pct >= WARN_PCT)     return "warn";
        return "normal";
    }
}
