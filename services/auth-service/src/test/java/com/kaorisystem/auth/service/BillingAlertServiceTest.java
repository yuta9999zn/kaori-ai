package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.repository.AlertEventRepository;
import com.kaorisystem.auth.repository.AlertEventRepository.AlertEventRow;
import com.kaorisystem.auth.repository.NotificationOutboxRepository;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.service.BillingAggregationService.AggregateResult;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Instant;
import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * F-037 — unit tests for {@link BillingAlertService}.
 *
 * <p>Mocks the four collaborators (alertEvents repo, outbox repo, user
 * repo, jdbc) and asserts the decision tree:
 * <ul>
 *   <li>First crossing 80% → outbox enqueued + non-suppressed event recorded</li>
 *   <li>Already-fired 80% (prior=true) → no enqueue, no event</li>
 *   <li>Within cooldown → suppressed event recorded, no enqueue</li>
 *   <li>No MANAGER → suppressed (no_recipient) event, no enqueue</li>
 *   <li>Cross-95 takes precedence over cross-80 in the same tick</li>
 *   <li>skipped result short-circuits</li>
 * </ul>
 */
@DisplayName("BillingAlertService — F-037 dispatch policy")
class BillingAlertServiceTest {

    private AlertEventRepository alertEvents;
    private NotificationOutboxRepository outbox;
    private UserRepository userRepo;
    private NamedParameterJdbcTemplate jdbc;
    private BillingAlertService svc;

    private static final UUID ENT = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final LocalDate MONTH = LocalDate.of(2026, 4, 1);

    @BeforeEach
    void setup() throws java.sql.SQLException {
        alertEvents = mock(AlertEventRepository.class);
        outbox      = mock(NotificationOutboxRepository.class);
        userRepo    = mock(UserRepository.class);
        jdbc        = mock(NamedParameterJdbcTemplate.class);

        svc = new BillingAlertService(alertEvents, outbox, userRepo, jdbc);
        // Wire @Value field manually for tests.
        ReflectionTestUtils.setField(svc, "frontendBaseUrl", "http://localhost:3000");

        // Default enterprise meta lookup — invoke the actual RowMapper
        // against a tiny stub ResultSet so the production code path
        // produces its private EnterpriseMeta record. We can't construct
        // that record from the test (it's private), so we have to let
        // the mapper do it.
        java.sql.ResultSet rs = mock(java.sql.ResultSet.class);
        when(rs.getString("enterprise_name")).thenReturn("Acme JSC");
        when(rs.getString("plan_code")).thenReturn("ENT_BASIC");
        when(jdbc.queryForObject(contains("enterprises"),
                                  any(MapSqlParameterSource.class),
                                  any(org.springframework.jdbc.core.RowMapper.class)))
                .thenAnswer(inv -> {
                    org.springframework.jdbc.core.RowMapper<?> mapper = inv.getArgument(2);
                    return mapper.mapRow(rs, 1);
                });

        // Default: no prior fires (cooldown clear).
        when(alertEvents.latestNonSuppressedFiredAt(any(UUID.class), any(UUID.class)))
                .thenReturn(null);

        // Default: enterprise has one MANAGER active.
        User mgr = new User();
        mgr.setUserId(UUID.randomUUID());
        mgr.setEmail("manager@acme.test");
        mgr.setRole("MANAGER");
        mgr.setStatus("active");
        when(userRepo.findByEnterpriseFiltered(any(UUID.class), eq("MANAGER"), eq("active"), anyInt(), anyInt()))
                .thenReturn(List.of(mgr));

        // Outbox + alert event return synthetic IDs.
        when(outbox.enqueue(any(UUID.class), anyString(), anyString(), anyMap(), anyString()))
                .thenReturn(UUID.randomUUID());
        when(alertEvents.record(any(AlertEventRow.class)))
                .thenReturn(UUID.randomUUID());
    }

    private AggregateResult result(int pct, boolean a80, boolean a95) {
        return new AggregateResult(ENT, MONTH, 850, 1000, pct, a80, a95, false, null);
    }

    // -------------------------------------------------------------------------

    @Test
    @DisplayName("first crossing 80% (prior=false) → outbox enqueued, event recorded")
    void firstCrossing80_dispatches() {
        AggregateResult r = result(82, true, false);

        svc.dispatchOnAggregate(r, /*prior80=*/false, /*prior95=*/false);

        verify(outbox, times(1)).enqueue(eq(ENT), eq("quota-alert"),
                eq("manager@acme.test"), anyMap(), contains("alert:"));
        verify(alertEvents, times(1)).record(any(AlertEventRow.class));
    }

    @Test
    @DisplayName("prior 80% already fired → no enqueue, no event")
    void prior80AlreadyFired_skips() {
        AggregateResult r = result(82, true, false);

        svc.dispatchOnAggregate(r, /*prior80=*/true, /*prior95=*/false);

        verify(outbox, never()).enqueue(any(), any(), any(), any(), any());
        verify(alertEvents, never()).record(any());
    }

    @Test
    @DisplayName("within cooldown → suppressed event, no enqueue")
    void cooldownActive_suppressed() {
        when(alertEvents.latestNonSuppressedFiredAt(any(UUID.class), eq(ENT)))
                .thenReturn(Instant.now().minusSeconds(60)); // 1 min ago, 6h cooldown

        AggregateResult r = result(82, true, false);
        svc.dispatchOnAggregate(r, false, false);

        verify(outbox, never()).enqueue(any(), any(), any(), any(), any());
        // One alert_events row inserted with suppressed=true.
        var captor = org.mockito.ArgumentCaptor.forClass(AlertEventRow.class);
        verify(alertEvents, times(1)).record(captor.capture());
        assertThat(captor.getValue().suppressed()).isTrue();
        assertThat(captor.getValue().outboxId()).isNull();
    }

    @Test
    @DisplayName("no MANAGER user → suppressed (no_recipient), no enqueue")
    void noManager_noRecipient() {
        when(userRepo.findByEnterpriseFiltered(any(UUID.class), eq("MANAGER"), eq("active"), anyInt(), anyInt()))
                .thenReturn(Collections.emptyList());

        AggregateResult r = result(82, true, false);
        svc.dispatchOnAggregate(r, false, false);

        verify(outbox, never()).enqueue(any(), any(), any(), any(), any());
        var captor = org.mockito.ArgumentCaptor.forClass(AlertEventRow.class);
        verify(alertEvents, times(1)).record(captor.capture());
        assertThat(captor.getValue().suppressed()).isTrue();
        assertThat(captor.getValue().context().get("suppress_reason")).isEqualTo("no_recipient");
    }

    @Test
    @DisplayName("cross 95 + cross 80 in same tick → only 95 fires (precedence)")
    void cross95_takesPrecedence_over_80() {
        AggregateResult r = result(96, true, true);

        svc.dispatchOnAggregate(r, false, false);

        // Exactly one outbox enqueue + one event.
        verify(outbox, times(1)).enqueue(any(), any(), any(), any(), any());
        verify(alertEvents, times(1)).record(any());
    }

    @Test
    @DisplayName("skipped result → no work")
    void skippedResult_shortCircuits() {
        AggregateResult skipped = AggregateResult.skipped(ENT, "no_quota");

        svc.dispatchOnAggregate(skipped, false, false);

        verify(outbox, never()).enqueue(any(), any(), any(), any(), any());
        verify(alertEvents, never()).record(any());
    }

    @Test
    @DisplayName("planLabel covers known + unknown plans")
    void planLabel_mapping() {
        assertThat(BillingAlertService.planLabel("PILOT")).isEqualTo("Pilot");
        assertThat(BillingAlertService.planLabel("ENT_BASIC")).isEqualTo("Enterprise Basic");
        assertThat(BillingAlertService.planLabel("ENT_MAX")).isEqualTo("Enterprise Max");
        assertThat(BillingAlertService.planLabel("UNKNOWN_CODE")).isEqualTo("UNKNOWN_CODE");
        assertThat(BillingAlertService.planLabel(null)).isEqualTo("—");
    }
}
