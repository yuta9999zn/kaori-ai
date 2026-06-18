package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.AlertEventRepository;
import com.kaorisystem.auth.repository.AlertRuleRepository;
import com.kaorisystem.auth.repository.AlertRuleRepository.AlertRuleRow;
import com.kaorisystem.auth.service.AlertRuleService.AlertRuleNotFoundException;
import com.kaorisystem.auth.service.AlertRuleService.CreateRequest;
import com.kaorisystem.auth.service.AlertRuleService.EmptyUpdateException;
import com.kaorisystem.auth.service.AlertRuleService.InvalidAlertRuleException;
import com.kaorisystem.auth.service.AlertRuleService.UpdateRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * F-037 — unit tests for {@link AlertRuleService} CRUD validation.
 */
@DisplayName("AlertRuleService — F-037 CRUD validation policy")
class AlertRuleServiceTest {

    private AlertRuleRepository ruleRepo;
    private AlertEventRepository eventRepo;
    private AlertRuleService svc;

    private static final UUID ENT  = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID RULE = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");

    @BeforeEach
    void setup() {
        ruleRepo  = mock(AlertRuleRepository.class);
        eventRepo = mock(AlertEventRepository.class);
        svc       = new AlertRuleService(ruleRepo, eventRepo);
    }

    private AlertRuleRow stubRow() {
        return new AlertRuleRow(
                RULE, ENT,
                "Quota 90%", "fire when usage >= 90",
                "billing_quota_pct", "gte", new BigDecimal("90.0000"),
                "email", null, 300, true,
                Instant.now(), Instant.now());
    }

    private CreateRequest validCreate() {
        return new CreateRequest(
                "Quota 90%", "fire when usage >= 90",
                "billing_quota_pct", "gte", new BigDecimal("90.0000"),
                "email", null, 300, true);
    }

    // -------------------------------------------------------------------------
    // CREATE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("create with valid payload → row inserted, returns hydrated row")
    void create_valid() {
        when(ruleRepo.insert(any())).thenReturn(RULE);
        when(ruleRepo.findByIdAndEnterprise(eq(RULE), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        AlertRuleRow result = svc.create(ENT, validCreate());
        assertThat(result.ruleId()).isEqualTo(RULE);
        verify(ruleRepo, times(1)).insert(any());
    }

    @Test
    @DisplayName("create with unknown metric_type → InvalidAlertRuleException")
    void create_invalidMetric() {
        CreateRequest req = new CreateRequest(
                "x", null, "invalid_metric", "gte",
                new BigDecimal("80.0"), "email", null, 300, true);
        assertThatThrownBy(() -> svc.create(ENT, req))
                .isInstanceOf(InvalidAlertRuleException.class)
                .hasMessageContaining("metric_type");
    }

    @Test
    @DisplayName("create with unknown operator → InvalidAlertRuleException")
    void create_invalidOperator() {
        CreateRequest req = new CreateRequest(
                "x", null, "billing_quota_pct", "BAD",
                new BigDecimal("80.0"), "email", null, 300, true);
        assertThatThrownBy(() -> svc.create(ENT, req))
                .isInstanceOf(InvalidAlertRuleException.class)
                .hasMessageContaining("operator");
    }

    @Test
    @DisplayName("create with negative threshold → InvalidAlertRuleException")
    void create_negativeThreshold() {
        CreateRequest req = new CreateRequest(
                "x", null, "billing_quota_pct", "gte",
                new BigDecimal("-1"), "email", null, 300, true);
        assertThatThrownBy(() -> svc.create(ENT, req))
                .isInstanceOf(InvalidAlertRuleException.class)
                .hasMessageContaining("threshold");
    }

    @Test
    @DisplayName("create with cooldown > 24h → InvalidAlertRuleException")
    void create_cooldownTooLarge() {
        CreateRequest req = new CreateRequest(
                "x", null, "billing_quota_pct", "gte",
                new BigDecimal("80"), "email", null, 999999, true);
        assertThatThrownBy(() -> svc.create(ENT, req))
                .isInstanceOf(InvalidAlertRuleException.class)
                .hasMessageContaining("cooldown");
    }

    @Test
    @DisplayName("create with blank name → InvalidAlertRuleException")
    void create_blankName() {
        CreateRequest req = new CreateRequest(
                "  ", null, "billing_quota_pct", "gte",
                new BigDecimal("80"), "email", null, 300, true);
        assertThatThrownBy(() -> svc.create(ENT, req))
                .isInstanceOf(InvalidAlertRuleException.class)
                .hasMessageContaining("name");
    }

    // -------------------------------------------------------------------------
    // UPDATE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("update with no fields → EmptyUpdateException")
    void update_empty() {
        when(ruleRepo.findByIdAndEnterprise(eq(RULE), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        UpdateRequest req = new UpdateRequest(null, null, null, null, null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, RULE, req))
                .isInstanceOf(EmptyUpdateException.class);
    }

    @Test
    @DisplayName("update with valid threshold → repo.update called")
    void update_valid() {
        when(ruleRepo.findByIdAndEnterprise(eq(RULE), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));
        when(ruleRepo.update(eq(RULE), eq(ENT), any())).thenReturn(1);

        UpdateRequest req = new UpdateRequest(
                null, null, null, new BigDecimal("85"), null, null, null);
        AlertRuleRow result = svc.update(ENT, RULE, req);
        assertThat(result).isNotNull();
        verify(ruleRepo, times(1)).update(eq(RULE), eq(ENT), any());
    }

    @Test
    @DisplayName("update on missing rule → AlertRuleNotFoundException")
    void update_notFound() {
        when(ruleRepo.findByIdAndEnterprise(eq(RULE), eq(ENT)))
                .thenReturn(Optional.empty());

        UpdateRequest req = new UpdateRequest(
                null, null, null, new BigDecimal("85"), null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, RULE, req))
                .isInstanceOf(AlertRuleNotFoundException.class);
        verify(ruleRepo, never()).update(any(), any(), any());
    }

    // -------------------------------------------------------------------------
    // SOFT DELETE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("softDelete on existing → repo.softDelete called")
    void softDelete_ok() {
        when(ruleRepo.findByIdAndEnterprise(eq(RULE), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));
        when(ruleRepo.softDelete(eq(RULE), eq(ENT))).thenReturn(1);

        svc.softDelete(ENT, RULE);
        verify(ruleRepo, times(1)).softDelete(eq(RULE), eq(ENT));
    }

    @Test
    @DisplayName("softDelete on missing → AlertRuleNotFoundException")
    void softDelete_notFound() {
        when(ruleRepo.findByIdAndEnterprise(eq(RULE), eq(ENT)))
                .thenReturn(Optional.empty());
        assertThatThrownBy(() -> svc.softDelete(ENT, RULE))
                .isInstanceOf(AlertRuleNotFoundException.class);
        verify(ruleRepo, never()).softDelete(any(), any());
    }

    // -------------------------------------------------------------------------
    // LIST
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("list clamps page+limit and forwards to repo")
    void list_clamps() {
        when(ruleRepo.countByEnterprise(eq(ENT))).thenReturn(7L);
        when(ruleRepo.findByEnterprise(eq(ENT), anyInt(), anyInt()))
                .thenReturn(List.of(stubRow(), stubRow()));

        AlertRuleService.AlertRulePage p = svc.list(ENT, 0, 5000);
        assertThat(p.page()).isEqualTo(1);            // clamped from 0
        assertThat(p.limit()).isEqualTo(100);         // clamped from 5000
        assertThat(p.items()).hasSize(2);
        assertThat(p.total()).isEqualTo(7L);
    }
}
