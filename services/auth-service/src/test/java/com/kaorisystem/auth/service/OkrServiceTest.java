package com.kaorisystem.auth.service;

import com.kaorisystem.auth.repository.OkrRepository;
import com.kaorisystem.auth.repository.OkrRepository.KeyResultRow;
import com.kaorisystem.auth.repository.OkrRepository.ObjectiveRow;
import com.kaorisystem.auth.service.OkrService.CreateRequest;
import com.kaorisystem.auth.service.OkrService.EmptyUpdateException;
import com.kaorisystem.auth.service.OkrService.InvalidOkrException;
import com.kaorisystem.auth.service.OkrService.KrUpsert;
import com.kaorisystem.auth.service.OkrService.ObjectiveNotFoundException;
import com.kaorisystem.auth.service.OkrService.UpdateRequest;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
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
 * F-040 — unit tests for {@link OkrService} CRUD validation
 * + status auto-recompute logic.
 */
@DisplayName("OkrService — F-040 OKR CRUD + status compute")
class OkrServiceTest {

    private OkrRepository repo;
    private OkrService    svc;

    private static final UUID ENT  = UUID.fromString("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa");
    private static final UUID OBJ  = UUID.fromString("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb");
    private static final UUID KR   = UUID.fromString("cccccccc-cccc-cccc-cccc-cccccccccccc");
    private static final UUID USER = UUID.fromString("dddddddd-dddd-dddd-dddd-dddddddddddd");

    @BeforeEach
    void setup() {
        repo = mock(OkrRepository.class);
        svc  = new OkrService(repo);
    }

    private static ObjectiveRow stubObjective() {
        return new ObjectiveRow(
                OBJ, ENT, "Q2 2026", "Tăng doanh thu SME 5 tỷ/tháng",
                USER, "on_track", USER,
                Instant.now(), Instant.now());
    }

    private static KeyResultRow stubKr(BigDecimal target, BigDecimal current) {
        return new KeyResultRow(
                KR, OBJ, ENT,
                "Số khách SME mới", "khách",
                target, current, 0,
                Instant.now(), Instant.now());
    }

    private static KrUpsert kr(String title, double target, double current) {
        return new KrUpsert(title, "khách",
                BigDecimal.valueOf(target),
                BigDecimal.valueOf(current));
    }

    private static CreateRequest validCreate() {
        return new CreateRequest(
                "Q2 2026",
                "Tăng doanh thu SME 5 tỷ/tháng",
                USER,
                List.of(
                        kr("Số khách SME mới", 60, 28),
                        kr("ARPU SME",         3_500_000, 2_800_000),
                        kr("Giữ chân SME",     85, 72)
                ));
    }

    // -------------------------------------------------------------------------
    // CREATE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("create with valid payload → objective + KRs persisted")
    void create_valid() {
        when(repo.insertObjective(any())).thenReturn(OBJ);
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ)))
                .thenReturn(List.of(stubKr(BigDecimal.valueOf(60), BigDecimal.valueOf(28))));

        var result = svc.create(ENT, USER, validCreate());
        assertThat(result.objective().objectiveId()).isEqualTo(OBJ);
        assertThat(result.keyResults()).isNotEmpty();
        verify(repo, times(1)).insertObjective(any());
        verify(repo, times(1)).replaceKeyResults(eq(OBJ), eq(ENT), any());
    }

    @Test
    @DisplayName("create with blank title → InvalidOkrException")
    void create_blankTitle() {
        CreateRequest req = new CreateRequest("Q2 2026", "  ", USER,
                List.of(kr("KR1", 100, 0)));
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidOkrException.class)
                .hasMessageContaining("title");
    }

    @Test
    @DisplayName("create with malformed quarter → InvalidOkrException")
    void create_invalidQuarter() {
        CreateRequest req = new CreateRequest("2026Q2", "Tăng doanh thu", USER,
                List.of(kr("KR1", 100, 0)));
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidOkrException.class)
                .hasMessageContaining("quarter");
    }

    @Test
    @DisplayName("create with KR target=0 → InvalidOkrException")
    void create_krTargetZero() {
        CreateRequest req = new CreateRequest("Q2 2026", "Tăng doanh thu", USER,
                List.of(kr("KR1", 0, 0)));
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidOkrException.class)
                .hasMessageContaining("target");
    }

    @Test
    @DisplayName("create with empty KR list → InvalidOkrException")
    void create_emptyKrList() {
        CreateRequest req = new CreateRequest("Q2 2026", "Tăng doanh thu", USER, List.of());
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidOkrException.class)
                .hasMessageContaining("at least one key result");
    }

    @Test
    @DisplayName("create with negative KR current → InvalidOkrException")
    void create_negativeCurrent() {
        CreateRequest req = new CreateRequest("Q2 2026", "Tăng doanh thu", USER,
                List.of(kr("KR1", 100, -5)));
        assertThatThrownBy(() -> svc.create(ENT, USER, req))
                .isInstanceOf(InvalidOkrException.class)
                .hasMessageContaining("current_value");
    }

    // -------------------------------------------------------------------------
    // UPDATE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("update with no fields → EmptyUpdateException")
    void update_empty() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ)))
                .thenReturn(List.of());

        UpdateRequest req = new UpdateRequest(null, null, null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, OBJ, req))
                .isInstanceOf(EmptyUpdateException.class);
    }

    @Test
    @DisplayName("update on missing objective → ObjectiveNotFoundException")
    void update_notFound() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.empty());

        UpdateRequest req = new UpdateRequest(null, "new title", null, null, null);
        assertThatThrownBy(() -> svc.update(ENT, OBJ, req))
                .isInstanceOf(ObjectiveNotFoundException.class);
        verify(repo, never()).updateObjective(any(), any(), any());
    }

    @Test
    @DisplayName("update with title only → repo.updateObjective called with patch")
    void update_titleOnly() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ))).thenReturn(List.of());

        UpdateRequest req = new UpdateRequest(null, "new title", null, null, null);
        svc.update(ENT, OBJ, req);
        verify(repo, times(1)).updateObjective(eq(OBJ), eq(ENT), any());
    }

    // -------------------------------------------------------------------------
    // KR PROGRESS
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("updateKr — progress update on owned KR succeeds")
    void updateKr_ok() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ)))
                .thenReturn(List.of(stubKr(BigDecimal.valueOf(100), BigDecimal.valueOf(20))));
        when(repo.updateKeyResultCurrent(eq(KR), eq(OBJ), any()))
                .thenReturn(1);

        var result = svc.updateKeyResultProgress(ENT, OBJ, KR, BigDecimal.valueOf(50));
        assertThat(result.objective()).isNotNull();
        verify(repo, times(1)).updateKeyResultCurrent(eq(KR), eq(OBJ), eq(BigDecimal.valueOf(50)));
    }

    @Test
    @DisplayName("updateKr — KR not in objective → ObjectiveNotFoundException")
    void updateKr_notInObjective() {
        UUID otherKr = UUID.fromString("ffffffff-ffff-ffff-ffff-ffffffffffff");
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ)))
                .thenReturn(List.of(stubKr(BigDecimal.valueOf(100), BigDecimal.valueOf(20))));

        assertThatThrownBy(() ->
                svc.updateKeyResultProgress(ENT, OBJ, otherKr, BigDecimal.valueOf(50)))
                .isInstanceOf(ObjectiveNotFoundException.class)
                .hasMessageContaining("kr not found");
        verify(repo, never()).updateKeyResultCurrent(any(), any(), any());
    }

    @Test
    @DisplayName("updateKr — negative current rejected")
    void updateKr_negativeCurrent() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ)))
                .thenReturn(List.of(stubKr(BigDecimal.valueOf(100), BigDecimal.valueOf(20))));

        assertThatThrownBy(() ->
                svc.updateKeyResultProgress(ENT, OBJ, KR, BigDecimal.valueOf(-1)))
                .isInstanceOf(InvalidOkrException.class)
                .hasMessageContaining("current_value");
    }

    // -------------------------------------------------------------------------
    // SOFT DELETE
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("softDelete on existing → repo.softDelete called")
    void softDelete_ok() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.of(stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ))).thenReturn(List.of());
        when(repo.softDelete(eq(OBJ), eq(ENT))).thenReturn(1);

        svc.softDelete(ENT, OBJ);
        verify(repo, times(1)).softDelete(eq(OBJ), eq(ENT));
    }

    @Test
    @DisplayName("softDelete on missing → ObjectiveNotFoundException")
    void softDelete_notFound() {
        when(repo.findByIdAndEnterprise(eq(OBJ), eq(ENT)))
                .thenReturn(Optional.empty());
        assertThatThrownBy(() -> svc.softDelete(ENT, OBJ))
                .isInstanceOf(ObjectiveNotFoundException.class);
        verify(repo, never()).softDelete(any(), any());
    }

    // -------------------------------------------------------------------------
    // LIST + ROLLUP
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("list clamps page+limit and forwards to repo")
    void list_clamps() {
        when(repo.countByEnterprise(eq(ENT), eq(null))).thenReturn(7L);
        when(repo.findByEnterprise(eq(ENT), eq(null), anyInt(), anyInt()))
                .thenReturn(List.of(stubObjective(), stubObjective()));
        when(repo.findKeyResultsByObjective(eq(OBJ))).thenReturn(List.of());

        var p = svc.list(ENT, null, 0, 5000);
        assertThat(p.page()).isEqualTo(1);             // clamped from 0
        assertThat(p.limit()).isEqualTo(200);           // clamped from 5000
        assertThat(p.items()).hasSize(2);
        assertThat(p.total()).isEqualTo(7L);
    }

    @Test
    @DisplayName("rollup backfills missing status buckets")
    void rollup_backfills() {
        when(repo.statusRollup(eq(ENT), eq("Q2 2026")))
                .thenReturn(Map.of("on_track", 4L, "at_risk", 3L));
        // off_track absent in raw — should appear as 0 in output

        var r = svc.rollup(ENT, "Q2 2026");
        assertThat(r.byStatus()).containsEntry("on_track",  4L);
        assertThat(r.byStatus()).containsEntry("at_risk",   3L);
        assertThat(r.byStatus()).containsEntry("off_track", 0L);
        assertThat(r.total()).isEqualTo(7L);
        assertThat(r.quarter()).isEqualTo("Q2 2026");
    }

    // -------------------------------------------------------------------------
    // STATUS COMPUTE (pure logic — covers the auto-recompute math)
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("computeStatus — empty KRs → on_track")
    void computeStatus_emptyKrs() {
        assertThat(OkrService.computeStatus("Q2 2026", List.of())).isEqualTo("on_track");
    }

    @Test
    @DisplayName("computeStatus — KRs at 100% always on_track regardless of quarter")
    void computeStatus_fullProgress() {
        var krs = List.of(kr("a", 100, 100), kr("b", 50, 50));
        assertThat(OkrService.computeStatus("Q2 2026", krs)).isEqualTo("on_track");
    }

    @Test
    @DisplayName("computeStatus — past quarter (elapsed=1) with 0 progress → off_track")
    void computeStatus_pastQuarterNoProgress() {
        // Q1 2020 is well in the past, elapsed = 1.0. Avg progress = 0.
        // lag = 1.0 - 0 = 1.0 > 0.15 → off_track.
        var krs = List.of(kr("a", 100, 0));
        assertThat(OkrService.computeStatus("Q1 2020", krs)).isEqualTo("off_track");
    }

    @Test
    @DisplayName("computeStatus — future quarter (elapsed=0) → on_track")
    void computeStatus_futureQuarter() {
        // Q4 2099 hasn't started; elapsed = 0. lag negative → on_track.
        var krs = List.of(kr("a", 100, 0));
        assertThat(OkrService.computeStatus("Q4 2099", krs)).isEqualTo("on_track");
    }
}
