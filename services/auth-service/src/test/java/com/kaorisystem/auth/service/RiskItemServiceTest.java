package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.RiskItemRepository;
import com.kaorisystem.auth.repository.RiskItemRepository.RiskItemRow;
import com.kaorisystem.auth.repository.RiskItemRepository.SeverityCount;
import com.kaorisystem.auth.service.RiskItemService.CreateRequest;
import com.kaorisystem.auth.service.RiskItemService.EmptyUpdateException;
import com.kaorisystem.auth.service.RiskItemService.InvalidRiskItemException;
import com.kaorisystem.auth.service.RiskItemService.RiskItemNotFoundException;
import com.kaorisystem.auth.service.RiskItemService.UpdateRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * F-039 — unit tests for {@link RiskItemService} CRUD validation.
 */
@DisplayName("RiskItemService — F-039 CRUD validation policy")
class RiskItemServiceTest {

    private RiskItemRepository repo;
    private RiskItemService    svc;

    private static final UUID ENT  = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID RISK = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    private static final UUID USER = UUID.fromString("cccccccc-cccc-cccc-cccc-cccccccccccc");

    @BeforeEach
    void setup() {
        repo = mock(RiskItemRepository.class);
        svc  = new RiskItemService(repo);
    }

    private RiskItemRow stubRow() {
        return new RiskItemRow(
                RISK, ENT,
                "Tồn kho phụ kiện cao", "120 ngày tồn kho", "operational",
                3, 4, 12, "high", "open",
                "Thanh lý 30% tháng 5", 25,
                USER, LocalDate.of(2026, 6, 30), "manual", USER,
                Instant.now(), Instant.now());
    }

    private CreateRequest validCreate() {
        return new CreateRequest(
                "Tồn kho phụ kiện cao", "120 ngày tồn kho", "operational",
                3, 4, "open",
                "Thanh lý 30% tháng 5", 25,
                USER, LocalDate.of(2026, 6, 30));
    }

    // -------------------------------------------------------------------------
    // CREATE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("create with valid payload → row inserted, returns hydrated row")
    void create_valid() {
        when(repo.insert(any())).thenReturn(RISK);
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        RiskItemRow result = svc.create(ENT, USER, validCreate());
        assertThat(result.riskId()).isEqualTo(RISK);
        verify(repo, times(1)).insert(any());
    }

    @Test
    @DisplayName("create with blank title → InvalidRiskItemException")
    void create_blankTitle() {
        CreateRequest req = new CreateRequest(
                "  ", null, null, 3, 3, "open", null, null, null, null);
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("title");
    }

    @Test
    @DisplayName("create with likelihood=0 → InvalidRiskItemException")
    void create_likelihoodTooLow() {
        CreateRequest req = new CreateRequest(
                "x", null, null, 0, 3, "open", null, null, null, null);
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("likelihood");
    }

    @Test
    @DisplayName("create with impact=6 → InvalidRiskItemException")
    void create_impactTooHigh() {
        CreateRequest req = new CreateRequest(
                "x", null, null, 3, 6, "open", null, null, null, null);
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("impact");
    }

    @Test
    @DisplayName("create with unknown status → InvalidRiskItemException")
    void create_invalidStatus() {
        CreateRequest req = new CreateRequest(
                "x", null, null, 3, 3, "WIP", null, null, null, null);
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("status");
    }

    @Test
    @DisplayName("create with mitigation_progress=150 → InvalidRiskItemException")
    void create_progressOver100() {
        CreateRequest req = new CreateRequest(
                "x", null, null, 3, 3, "open", null, 150, null, null);
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("mitigation_progress");
    }

    // -------------------------------------------------------------------------
    // UPDATE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("update with no fields → EmptyUpdateException")
    void update_empty() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        UpdateRequest req = new UpdateRequest(
                null, null, null, null, null, null, null, null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, RISK, req))
                .isInstanceOf(EmptyUpdateException.class);
    }

    @Test
    @DisplayName("update with new likelihood → repo.update called")
    void update_valid() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));
        when(repo.update(eq(RISK), eq(ENT), any())).thenReturn(1);

        UpdateRequest req = new UpdateRequest(
                null, null, null, 5, null, null, null, null, null, null);
        RiskItemRow result = svc.update(ENT, RISK, req);
        assertThat(result).isNotNull();
        verify(repo, times(1)).update(eq(RISK), eq(ENT), any());
    }

    @Test
    @DisplayName("update on missing risk → RiskItemNotFoundException")
    void update_notFound() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.empty());

        UpdateRequest req = new UpdateRequest(
                null, null, null, 5, null, null, null, null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, RISK, req))
                .isInstanceOf(RiskItemNotFoundException.class);
        verify(repo, never()).update(any(), any(), any());
    }

    @Test
    @DisplayName("update with status='closed' → repo.update receives status")
    void update_validStatusTransition() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));
        when(repo.update(eq(RISK), eq(ENT), any())).thenReturn(1);

        UpdateRequest req = new UpdateRequest(
                null, null, null, null, null, "closed", null, null, null, null);
        svc.update(ENT, RISK, req);
        verify(repo, times(1)).update(eq(RISK), eq(ENT), any());
    }

    // -------------------------------------------------------------------------
    // SOFT DELETE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("softDelete on existing → repo.softDelete called")
    void softDelete_ok() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));
        when(repo.softDelete(eq(RISK), eq(ENT))).thenReturn(1);

        svc.softDelete(ENT, RISK);
        verify(repo, times(1)).softDelete(eq(RISK), eq(ENT));
    }

    @Test
    @DisplayName("softDelete on missing → RiskItemNotFoundException")
    void softDelete_notFound() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.empty());
        assertThatThrownBy(() -> svc.softDelete(ENT, RISK))
                .isInstanceOf(RiskItemNotFoundException.class);
        verify(repo, never()).softDelete(any(), any());
    }

    // -------------------------------------------------------------------------
    // LIST + SEVERITY ROLLUP
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("list clamps page+limit and forwards to repo")
    void list_clamps() {
        when(repo.countByEnterprise(eq(ENT), eq(null), eq(null), eq(null))).thenReturn(7L);
        when(repo.findByEnterprise(eq(ENT), eq(null), eq(null), eq(null), anyInt(), anyInt()))
                .thenReturn(List.of(stubRow(), stubRow()));

        RiskItemService.RiskItemPage p = svc.list(ENT, null, null, null, 0, 5000);
        assertThat(p.page()).isEqualTo(1);            // clamped from 0
        assertThat(p.limit()).isEqualTo(200);          // clamped from 5000
        assertThat(p.items()).hasSize(2);
        assertThat(p.total()).isEqualTo(7L);
    }

    @Test
    @DisplayName("list rejects unknown status filter")
    void list_invalidStatus() {
        assertThatThrownBy(() -> svc.list(ENT, "WIP", null, null, 1, 20))
                .isInstanceOf(InvalidRiskItemException.class);
    }

    @Test
    @DisplayName("list rejects unknown severity filter")
    void list_invalidSeverity() {
        assertThatThrownBy(() -> svc.list(ENT, null, "extreme", null, 1, 20))
                .isInstanceOf(InvalidRiskItemException.class);
    }

    @Test
    @DisplayName("severityRollup forwards to repo")
    void severityRollup_forwards() {
        when(repo.severityRollup(eq(ENT))).thenReturn(List.of(
                new SeverityCount("critical", 2L),
                new SeverityCount("high",     5L)
        ));
        var rollup = svc.severityRollup(ENT);
        assertThat(rollup).hasSize(2);
        assertThat(rollup.get(0).count()).isEqualTo(2L);
    }

    // -------------------------------------------------------------------------
    // CATEGORY (migration 034 follow-up)
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("create with valid category → row inserted")
    void create_validCategory() {
        when(repo.insert(any())).thenReturn(RISK);
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        CreateRequest req = new CreateRequest(
                "x", null, "financial", 3, 3, "open", null, null, null, null);
        RiskItemRow result = svc.create(ENT, USER, req);
        assertThat(result).isNotNull();
        verify(repo, times(1)).insert(any());
    }

    @Test
    @DisplayName("create with unknown category → InvalidRiskItemException")
    void create_invalidCategory() {
        CreateRequest req = new CreateRequest(
                "x", null, "weather", 3, 3, "open", null, null, null, null);
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("category");
        verify(repo, never()).insert(any());
    }

    @Test
    @DisplayName("create with null category → defaults to 'operational'")
    void create_nullCategoryDefaults() {
        when(repo.insert(any())).thenReturn(RISK);
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        org.mockito.ArgumentCaptor<RiskItemRow> captor =
                org.mockito.ArgumentCaptor.forClass(RiskItemRow.class);

        CreateRequest req = new CreateRequest(
                "x", null, null, 3, 3, "open", null, null, null, null);
        svc.create(ENT, USER, req);

        verify(repo).insert(captor.capture());
        assertThat(captor.getValue().category()).isEqualTo("operational");
    }

    @Test
    @DisplayName("update changing category → forwarded to repo")
    void update_validCategoryChange() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));
        when(repo.update(eq(RISK), eq(ENT), any())).thenReturn(1);

        UpdateRequest req = new UpdateRequest(
                null, null, "regulatory", null, null, null, null, null, null, null);
        svc.update(ENT, RISK, req);
        verify(repo, times(1)).update(eq(RISK), eq(ENT), any());
    }

    @Test
    @DisplayName("update with unknown category → InvalidRiskItemException")
    void update_invalidCategory() {
        when(repo.findByIdAndEnterprise(eq(RISK), eq(ENT)))
                .thenReturn(Optional.of(stubRow()));

        UpdateRequest req = new UpdateRequest(
                null, null, "vũ trụ", null, null, null, null, null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, RISK, req))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("category");
        verify(repo, never()).update(any(), any(), any());
    }

    @Test
    @DisplayName("list with category filter → forwarded to repo")
    void list_filterByCategory() {
        when(repo.countByEnterprise(eq(ENT), eq(null), eq(null), eq("technical")))
                .thenReturn(3L);
        when(repo.findByEnterprise(eq(ENT), eq(null), eq(null), eq("technical"), anyInt(), anyInt()))
                .thenReturn(List.of(stubRow()));

        RiskItemService.RiskItemPage p = svc.list(ENT, null, null, "technical", 1, 20);
        assertThat(p.total()).isEqualTo(3L);
        assertThat(p.items()).hasSize(1);
    }

    @Test
    @DisplayName("list rejects unknown category filter")
    void list_invalidCategory() {
        assertThatThrownBy(() -> svc.list(ENT, null, null, "weather", 1, 20))
                .isInstanceOf(InvalidRiskItemException.class)
                .hasMessageContaining("category");
    }
}
