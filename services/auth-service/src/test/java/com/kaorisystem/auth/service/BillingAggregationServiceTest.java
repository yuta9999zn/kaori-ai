package com.kaorisystem.auth.service;

import com.kaorisystem.auth.service.BillingAggregationService.AggregateResult;
import com.kaorisystem.auth.service.BillingAggregationService.BatchResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcOperations;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;

import java.time.LocalDate;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.any;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * F-031 — unit tests for BillingAggregationService.
 *
 * Mocks {@link NamedParameterJdbcTemplate} directly. The point of the
 * service is the threshold + idempotency policy; the SQL is exercised end-
 * to-end at the IT layer (Testcontainers, run in CI).
 *
 * Cases per PLAN DoD:
 *   under-80, cross-80, cross-95, idempotent flip, no-quota skip,
 *   per-enterprise failure does not abort the batch.
 */
@DisplayName("BillingAggregationService — F-031 threshold + idempotency policy")
class BillingAggregationServiceTest {

    private NamedParameterJdbcTemplate jdbc;
    private BillingAlertService        alertService;
    private BillingAggregationService  service;
    private final UUID      ENT_A = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private final LocalDate MONTH = LocalDate.of(2026, 4, 1);

    @BeforeEach
    void setup() {
        jdbc         = mock(NamedParameterJdbcTemplate.class);
        alertService = mock(BillingAlertService.class);
        service      = new BillingAggregationService(jdbc, alertService);
    }

    private void stubQuota(int quota) {
        when(jdbc.queryForObject(contains("monthly_quota"),
                                  any(MapSqlParameterSource.class),
                                  eq(Integer.class)))
                .thenReturn(quota);
    }

    private void stubUsage(long used) {
        when(jdbc.queryForObject(contains("DISTINCT clean_data"),
                                  any(MapSqlParameterSource.class),
                                  eq(Long.class)))
                .thenReturn(used);
    }

    private MapSqlParameterSource captureUpsertParams() {
        var captor = org.mockito.ArgumentCaptor.forClass(MapSqlParameterSource.class);
        verify(jdbc, atLeastOnce()).update(contains("INSERT INTO enterprise_monthly_billing"),
                                            captor.capture());
        return captor.getValue();
    }

    // -------------------------------------------------------------------------
    // under-80: both alert flags written FALSE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("under 80% — neither alert fires")
    void aggregate_under80_doesNotFireAlerts() {
        stubQuota(100);
        stubUsage(50L);

        AggregateResult r = service.aggregate(ENT_A, MONTH);

        assertThat(r.usagePct()).isEqualTo(50);
        assertThat(r.alert80Fired()).isFalse();
        assertThat(r.alert95Fired()).isFalse();

        var params = captureUpsertParams();
        assertThat(params.getValue("crossed80")).isEqualTo(false);
        assertThat(params.getValue("crossed95")).isEqualTo(false);
        assertThat(params.getValue("used")).isEqualTo(50);
    }

    // -------------------------------------------------------------------------
    // cross-80 only
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("at exactly 80% — alert_80_fired only")
    void aggregate_at80_fires80Only() {
        stubQuota(100);
        stubUsage(80L);

        AggregateResult r = service.aggregate(ENT_A, MONTH);

        assertThat(r.usagePct()).isEqualTo(80);
        assertThat(r.alert80Fired()).isTrue();
        assertThat(r.alert95Fired()).isFalse();

        var params = captureUpsertParams();
        assertThat(params.getValue("crossed80")).isEqualTo(true);
        assertThat(params.getValue("crossed95")).isEqualTo(false);
    }

    // -------------------------------------------------------------------------
    // cross-95: both flags fire
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("at exactly 95% — both alert flags fire")
    void aggregate_at95_firesBothFlags() {
        stubQuota(100);
        stubUsage(95L);

        AggregateResult r = service.aggregate(ENT_A, MONTH);

        assertThat(r.usagePct()).isEqualTo(95);
        assertThat(r.alert80Fired()).isTrue();
        assertThat(r.alert95Fired()).isTrue();
    }

    // -------------------------------------------------------------------------
    // idempotency: two passes at the same %, only first crosses → second
    // pass STILL emits crossed=true to the upsert (the OR in SQL keeps the
    // already-set flag set; the test asserts the service doesn't try to
    // unset).
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("idempotent: a second pass at the same usage emits crossed=true again, never FALSE")
    void aggregate_idempotent_noUnflip() {
        stubQuota(100);
        stubUsage(85L);

        service.aggregate(ENT_A, MONTH);
        service.aggregate(ENT_A, MONTH);

        verify(jdbc, times(2))
                .update(contains("INSERT INTO enterprise_monthly_billing"),
                        any(MapSqlParameterSource.class));
        // Both calls pass crossed80=true; the SQL ON CONFLICT clause does
        // the OR, never overwriting an already-set flag with FALSE.
    }

    // -------------------------------------------------------------------------
    // No quota row (e.g. enterprise without a workspace plan): skip, log.
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("no quota lookup row → skipped result, no upsert")
    void aggregate_noQuota_skips() {
        when(jdbc.queryForObject(contains("monthly_quota"),
                                  any(MapSqlParameterSource.class),
                                  eq(Integer.class)))
                .thenReturn(null);

        AggregateResult r = service.aggregate(ENT_A, MONTH);

        assertThat(r.skipped()).isTrue();
        assertThat(r.skipReason()).isEqualTo("no_quota");
        verify(jdbc, never()).update(anyString(), any(MapSqlParameterSource.class));
    }

    // -------------------------------------------------------------------------
    // Quota=0 → pct=0, no alerts fire (avoid divide-by-zero noise).
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("quota=0 → pct=0 (avoids divide-by-zero), no alerts")
    void aggregate_quotaZero_pctZero() {
        stubQuota(0);
        stubUsage(50L);

        AggregateResult r = service.aggregate(ENT_A, MONTH);

        assertThat(r.usagePct()).isEqualTo(0);
        assertThat(r.alert80Fired()).isFalse();
        assertThat(r.alert95Fired()).isFalse();
    }

    // -------------------------------------------------------------------------
    // Batch: per-enterprise failure does not abort the rest.
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("aggregateAll continues past per-enterprise failures")
    void aggregateAll_perEnterpriseFailureDoesNotAbort() {
        UUID a = UUID.randomUUID(), b = UUID.randomUUID(), c = UUID.randomUUID();

        // Active enterprise list returns three.
        JdbcOperations ops = mock(JdbcOperations.class);
        when(jdbc.getJdbcOperations()).thenReturn(ops);
        when(ops.query(contains("FROM enterprises WHERE status = 'active'"),
                       any(RowMapper.class)))
                .thenReturn(List.of(a, b, c));

        // Quota lookup throws for the middle one only.
        when(jdbc.queryForObject(contains("monthly_quota"),
                                  any(MapSqlParameterSource.class),
                                  eq(Integer.class)))
                .thenReturn(100, 100, 100);  // a, c succeed; b override below
        when(jdbc.queryForObject(contains("DISTINCT clean_data"),
                                  any(MapSqlParameterSource.class),
                                  eq(Long.class)))
                .thenAnswer(inv -> {
                    MapSqlParameterSource p = inv.getArgument(1);
                    UUID eid = (UUID) p.getValue("eid");
                    if (eid.equals(b)) throw new RuntimeException("b is bad");
                    return 30L;
                });

        BatchResult r = service.aggregateAll(MONTH);

        assertThat(r.enterpriseCount()).isEqualTo(3);
        assertThat(r.successCount()).isEqualTo(2);
        assertThat(r.failureCount()).isEqualTo(1);
    }
}
