package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.BillingAggregationRepository;
import com.kaorisystem.auth.repository.BillingAggregationRepository.OverviewRow;
import com.kaorisystem.auth.repository.EnterpriseBillingProjection;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.service.PlatformBillingService.EnterpriseNotFoundException;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidMonthException;
import com.kaorisystem.auth.service.PlatformBillingService.InvalidStatusException;
import com.kaorisystem.auth.service.PlatformBillingService.QuotaPage;
import com.kaorisystem.auth.service.WorkspaceService.InvalidPlanCodeException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.BDDMockito.given;

/**
 * Mockito-only orchestration tests for {@link PlatformBillingService}: filter
 * normalisation, error mapping, status classification feedthrough.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("PlatformBillingService — orchestration + filter validation")
class PlatformBillingServiceTest {

    @Mock private BillingAggregationRepository billingRepo;
    @Mock private WorkspaceRepository          workspaceRepo;
    /** Migration 024 prep — service now calls disableForTx() at the top of
     *  every read method. Mock so the no-op call doesn't NPE. */
    @Mock private RlsBypassHelper              rlsBypass;

    @InjectMocks private PlatformBillingService underTest;

    // -------------------------------------------------------------------------
    // getEnterprise
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("getEnterprise — unknown id throws EnterpriseNotFoundException")
    void getEnterprise_notFound() {
        UUID eid = UUID.randomUUID();
        given(billingRepo.findOne(eq(eid), any())).willReturn(Optional.empty());

        assertThatThrownBy(() -> underTest.getEnterprise(eid))
                .isInstanceOf(EnterpriseNotFoundException.class);
    }

    @Test
    @DisplayName("getEnterprise — happy path classifies status via BillingMath")
    void getEnterprise_classifiesStatus() {
        UUID eid = UUID.randomUUID();
        UUID wid = UUID.randomUUID();
        given(billingRepo.findOne(eq(eid), any()))
                .willReturn(Optional.of(projection(eid, wid, "Acme",
                        "BUSINESS", 1900, 2000, 0, 1_490_000.0)));

        var s = underTest.getEnterprise(eid);
        assertThat(s.status()).isEqualTo("critical");      // 1900/2000 = 95%
        assertThat(s.totalAmountVnd()).isEqualTo(1_490_000.0);
        assertThat(s.quotaWarnAtPct()).isEqualTo(BillingMath.WARN_PCT);
    }

    // -------------------------------------------------------------------------
    // listQuota — filter validation
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("listQuota — unknown plan filter → InvalidPlanCodeException")
    void listQuota_unknownPlan() {
        given(workspaceRepo.findPlanCode("NOPE")).willReturn(Optional.empty());
        assertThatThrownBy(() ->
                underTest.listQuota("nope", null, null, 50))
                .isInstanceOf(InvalidPlanCodeException.class);
    }

    @Test
    @DisplayName("listQuota — bad status filter → InvalidStatusException")
    void listQuota_badStatus() {
        assertThatThrownBy(() ->
                underTest.listQuota(null, "fancy", null, 50))
                .isInstanceOf(InvalidStatusException.class);
    }

    @Test
    @DisplayName("listQuota — empty filters pass through as null to the repo")
    void listQuota_emptyFiltersAsNull() {
        given(billingRepo.findPage(any(), isNull(), isNull(), isNull(), isNull(), anyInt()))
                .willReturn(List.of());
        given(billingRepo.countMatching(any(), isNull(), isNull())).willReturn(0L);

        QuotaPage page = underTest.listQuota("", "  ", null, 50);
        assertThat(page.items()).isEmpty();
        assertThat(page.total()).isEqualTo(0);
        assertThat(page.nextCursor()).isNull();
    }

    @Test
    @DisplayName("listQuota — uppercases plan filter, lowercases status filter")
    void listQuota_normalisation() {
        given(workspaceRepo.findPlanCode("BUSINESS")).willReturn(Optional.of("BUSINESS"));
        given(billingRepo.findPage(any(), eq("BUSINESS"), eq("warn"), any(), any(), anyInt()))
                .willReturn(List.of());
        given(billingRepo.countMatching(any(), eq("BUSINESS"), eq("warn"))).willReturn(0L);

        QuotaPage page = underTest.listQuota("business", "WARN", null, 50);
        assertThat(page.items()).isEmpty();
    }

    @Test
    @DisplayName("listQuota — emits next cursor when page is full")
    void listQuota_cursorEmittedOnFullPage() {
        UUID eid = UUID.randomUUID();
        UUID wid = UUID.randomUUID();
        given(billingRepo.findPage(any(), any(), any(), any(), any(), eq(1)))
                .willReturn(List.of(projection(eid, wid, "X", "STARTER", 0, 100, 0, 0.0)));
        given(billingRepo.countMatching(any(), any(), any())).willReturn(2L);

        QuotaPage page = underTest.listQuota(null, null, null, 1);
        assertThat(page.nextCursor()).isNotNull();
        assertThat(page.total()).isEqualTo(2L);
    }

    // -------------------------------------------------------------------------
    // export — month parsing
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("export — bad month string → InvalidMonthException")
    void export_invalidMonth() {
        assertThatThrownBy(() -> underTest.export("2026-13", null, null))
                .isInstanceOf(InvalidMonthException.class);
        assertThatThrownBy(() -> underTest.export("not-a-month", null, null))
                .isInstanceOf(InvalidMonthException.class);
        assertThatThrownBy(() -> underTest.export("2026", null, null))
                .isInstanceOf(InvalidMonthException.class);
    }

    @Test
    @DisplayName("export — empty month defaults to current and returns rows")
    void export_defaultMonth() {
        given(billingRepo.findPage(any(), any(), any(), any(), any(), anyInt()))
                .willReturn(List.of());

        var res = underTest.export(null, null, null);
        assertThat(res.rows()).isEmpty();
        assertThat(res.truncated()).isFalse();
        // billingMonth should be in YYYY-MM shape
        assertThat(res.billingMonth()).matches("\\d{4}-\\d{2}");
    }

    // -------------------------------------------------------------------------
    // overview — null-safe sums
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("getOverview — empty rollup returns zeroes (no enterprises)")
    void overview_emptyRollup() {
        given(billingRepo.findOverview(any()))
                .willReturn(new OverviewRow(0, 0, 0, 0, 0, 0, 0, 0, 0.0, null, 0L));

        var o = underTest.getOverview();
        assertThat(o.enterpriseCount()).isZero();
        assertThat(o.totalRevenueVnd()).isZero();
        assertThat(o.byStatus().normal()).isZero();
    }

    // =========================================================================
    // helpers
    // =========================================================================

    private static EnterpriseBillingProjection projection(
            UUID eid, UUID wid, String name, String plan,
            int used, int quota, int overage, double price) {
        return new EnterpriseBillingProjection() {
            @Override public UUID    getEnterpriseId()    { return eid; }
            @Override public String  getEnterpriseName()  { return name; }
            @Override public UUID    getWorkspaceId()     { return wid; }
            @Override public String  getPlanCode()        { return plan; }
            @Override public Integer getUniqueCustomers() { return used; }
            @Override public Integer getQuota()           { return quota; }
            @Override public Integer getOverageUnits()    { return overage; }
            @Override public Double  getBasePriceVnd()    { return price; }
            @Override public Instant getCreatedAt()       { return Instant.parse("2026-04-01T00:00:00Z"); }
        };
    }

}
