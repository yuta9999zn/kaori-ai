package com.kaorisystem.auth.service;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.CsvSource;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Boundary-table coverage for {@link BillingMath#computeStatus}. Pinned here
 * so the F-008 + F-011 status colours can never drift apart.
 */
@DisplayName("BillingMath.computeStatus — threshold boundaries")
class BillingMathTest {

    @ParameterizedTest(name = "used={0}, quota={1}, overage={2} → {3}")
    @CsvSource({
        // any overage wins regardless of utilisation
        "  0,    0,  1,  overage",
        "100, 1000,  5,  overage",
        "999, 1000,  1,  overage",

        // quota=0 (e.g. TRIAL with no monthly_quota seeded) → normal unless overage
        "  0,    0,  0,  normal",
        " 50,    0,  0,  normal",

        // ≥95% → critical (Math.round half-up: 94.5%→95, 94.4%→94)
        "950, 1000,  0,  critical",
        "945, 1000,  0,  critical",   // 94.5 rounds to 95
        "100,  100,  0,  critical",   // 100% still critical

        // 80–94% → warn
        "800, 1000,  0,  warn",
        "944, 1000,  0,  warn",       // 94.4 rounds to 94
        "850, 1000,  0,  warn",

        // <80% → normal (Math.round(79.4)=79 stays normal; 79.5 would round to 80→warn)
        "794, 1000,  0,  normal",
        "  0, 1000,  0,  normal",
        "  1, 1000,  0,  normal",
        " 50,  100,  0,  normal",
    })
    void computeStatus_boundary(int used, int quota, int overage, String expected) {
        assertThat(BillingMath.computeStatus(used, quota, overage)).isEqualTo(expected);
    }

    @org.junit.jupiter.api.Test
    @DisplayName("constants pinned: WARN_PCT=80, CRITICAL_PCT=95")
    void constants() {
        assertThat(BillingMath.WARN_PCT).isEqualTo(80);
        assertThat(BillingMath.CRITICAL_PCT).isEqualTo(95);
    }
}
