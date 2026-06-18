package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.Workspace;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository.WorkspaceListRow;
import com.kaorisystem.auth.service.WorkspaceService.InvalidCursorException;
import com.kaorisystem.auth.service.WorkspaceService.InvalidPlanCodeException;
import com.kaorisystem.auth.service.WorkspaceService.InvalidStatusException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspacePage;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
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
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

@ExtendWith(MockitoExtension.class)
@DisplayName("WorkspaceService — business logic unit tests (T-F008-02)")
class WorkspaceServiceTest {

    @Mock private WorkspaceRepository workspaceRepository;
    @Mock private com.kaorisystem.auth.repository.WorkspaceAuditLogRepository auditLogRepository;
    @Mock private com.kaorisystem.auth.service.RlsBypassHelper rlsBypass;

    @InjectMocks
    private WorkspaceService workspaceService;

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

    private static WorkspaceListRow row(UUID id, String name, String plan,
                                        String status, String industry, Instant ts) {
        return new WorkspaceListRow() {
            @Override public UUID    getWorkspaceId() { return id; }
            @Override public String  getName()        { return name; }
            @Override public String  getPlanCode()    { return plan; }
            @Override public String  getStatus()      { return status; }
            @Override public Instant getCreatedAt()   { return ts; }
            @Override public Instant getUpdatedAt()   { return ts; }
            @Override public String  getIndustry()    { return industry; }
        };
    }

    private static Workspace ws(UUID id, String name, String plan, String status) {
        Workspace w = new Workspace();
        w.setWorkspaceId(id);
        w.setName(name);
        w.setPlanCode(plan);
        w.setStatus(status);
        Instant t = Instant.parse("2026-04-25T10:00:00Z");
        w.setCreatedAt(t);
        w.setUpdatedAt(t);
        return w;
    }

    // =========================================================================
    // list()
    // =========================================================================

    @Test
    @DisplayName("list — null cursor calls findFirstPage and returns mapped views + total")
    void list_firstPage_callsFindFirstPage() {
        UUID id = UUID.randomUUID();
        Instant ts = Instant.parse("2026-04-25T10:00:00Z");
        given(workspaceRepository.findFirstPage(50))
                .willReturn(List.of(row(id, "Acme", "TRIAL", "active", "Retail", ts)));
        given(workspaceRepository.count()).willReturn(1L);

        WorkspacePage page = workspaceService.list(null, 50);

        assertThat(page.items()).hasSize(1);
        assertThat(page.items().get(0).workspaceId()).isEqualTo(id);
        assertThat(page.items().get(0).industry()).isEqualTo("Retail");
        assertThat(page.total()).isEqualTo(1L);
        // Returned 1 of 50 → end of list → no next cursor
        assertThat(page.nextCursor()).isNull();
        verify(workspaceRepository, never()).findPageAfter(any(), any(), eq(50));
    }

    @Test
    @DisplayName("list — full page returned ⇒ nextCursor is set (encoded keyset of last row)")
    void list_fullPage_emitsNextCursor() {
        UUID id1 = UUID.randomUUID();
        UUID id2 = UUID.randomUUID();
        Instant ts = Instant.parse("2026-04-25T10:00:00Z");
        given(workspaceRepository.findFirstPage(2))
                .willReturn(List.of(
                        row(id1, "A", "TRIAL", "active", null, ts),
                        row(id2, "B", "TRIAL", "active", null, ts)
                ));
        given(workspaceRepository.count()).willReturn(7L);

        WorkspacePage page = workspaceService.list(null, 2);

        assertThat(page.items()).hasSize(2);
        assertThat(page.nextCursor()).isNotBlank();
        assertThat(page.total()).isEqualTo(7L);
    }

    @Test
    @DisplayName("list — non-null cursor calls findPageAfter with decoded (ts, id)")
    void list_withCursor_callsFindPageAfter() {
        UUID lastId = UUID.fromString("11111111-2222-3333-4444-555555555555");
        Instant lastTs = Instant.parse("2026-04-20T08:30:00Z");

        // Encode using the same pipe-then-base64 scheme the service emits.
        String raw = lastTs.toString() + "|" + lastId;
        String cursor = java.util.Base64.getUrlEncoder().withoutPadding()
                .encodeToString(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8));

        given(workspaceRepository.findPageAfter(eq(lastTs), eq(lastId), eq(20)))
                .willReturn(List.of());
        given(workspaceRepository.count()).willReturn(0L);

        workspaceService.list(cursor, 20);

        verify(workspaceRepository).findPageAfter(eq(lastTs), eq(lastId), eq(20));
        verify(workspaceRepository, never()).findFirstPage(eq(20));
    }

    @Test
    @DisplayName("list — malformed cursor raises InvalidCursorException")
    void list_malformedCursor_throws() {
        assertThatThrownBy(() -> workspaceService.list("!!!not-base64!!!", 50))
                .isInstanceOf(InvalidCursorException.class);
        assertThatThrownBy(() -> workspaceService.list("aGVsbG8=", 50))   // base64 of "hello", no pipe
                .isInstanceOf(InvalidCursorException.class);
    }

    // =========================================================================
    // create()
    // =========================================================================

    @Test
    @DisplayName("create — valid plan, no industry → saves workspace, no enterprise seed")
    void create_validPlanNoIndustry_savesWorkspace() {
        given(workspaceRepository.findPlanCode("TRIAL")).willReturn(Optional.of("TRIAL"));
        UUID newId = UUID.randomUUID();
        given(workspaceRepository.save(any(Workspace.class)))
                .willAnswer(inv -> {
                    Workspace w = inv.getArgument(0);
                    w.setWorkspaceId(newId);
                    w.setCreatedAt(Instant.now());
                    w.setUpdatedAt(Instant.now());
                    return w;
                });

        WorkspaceView v = workspaceService.create("Acme", "TRIAL", null);

        assertThat(v.workspaceId()).isEqualTo(newId);
        assertThat(v.name()).isEqualTo("Acme");
        assertThat(v.planCode()).isEqualTo("TRIAL");
        assertThat(v.status()).isEqualTo("active");
        assertThat(v.industry()).isNull();
        verify(workspaceRepository, never()).seedEnterprise(any(), any(), any());
    }

    @Test
    @DisplayName("create — industry supplied → seedEnterprise called with workspace id + industry")
    void create_withIndustry_seedsEnterprise() {
        given(workspaceRepository.findPlanCode("STARTER")).willReturn(Optional.of("STARTER"));
        UUID newId = UUID.randomUUID();
        given(workspaceRepository.save(any(Workspace.class)))
                .willAnswer(inv -> {
                    Workspace w = inv.getArgument(0);
                    w.setWorkspaceId(newId);
                    w.setCreatedAt(Instant.now());
                    w.setUpdatedAt(Instant.now());
                    return w;
                });

        WorkspaceView v = workspaceService.create("Beta Co", "STARTER", "Manufacturing");

        assertThat(v.industry()).isEqualTo("Manufacturing");
        ArgumentCaptor<UUID>   widCap  = ArgumentCaptor.forClass(UUID.class);
        ArgumentCaptor<String> nameCap = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<String> indCap  = ArgumentCaptor.forClass(String.class);
        verify(workspaceRepository).seedEnterprise(widCap.capture(), nameCap.capture(), indCap.capture());
        assertThat(widCap.getValue()).isEqualTo(newId);
        assertThat(nameCap.getValue()).isEqualTo("Beta Co");
        assertThat(indCap.getValue()).isEqualTo("Manufacturing");
    }

    @Test
    @DisplayName("create — unknown plan_code → InvalidPlanCodeException, no save")
    void create_unknownPlan_throws() {
        given(workspaceRepository.findPlanCode("MADE_UP")).willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.create("X", "MADE_UP", null))
                .isInstanceOf(InvalidPlanCodeException.class);
        verify(workspaceRepository, never()).save(any(Workspace.class));
        verify(workspaceRepository, never()).seedEnterprise(any(), any(), any());
    }

    // =========================================================================
    // update()
    // =========================================================================

    @Test
    @DisplayName("update — partial (name only) leaves plan_code and status unchanged")
    void update_partialNameOnly_keepsOthers() {
        UUID id = UUID.randomUUID();
        Workspace existing = ws(id, "OldName", "TRIAL", "active");
        given(workspaceRepository.findById(id)).willReturn(Optional.of(existing));
        given(workspaceRepository.save(any(Workspace.class))).willAnswer(inv -> inv.getArgument(0));
        given(workspaceRepository.findIndustryByWorkspaceId(id)).willReturn(Optional.of("Retail"));

        WorkspaceView v = workspaceService.update(id, "NewName", null, null);

        assertThat(v.name()).isEqualTo("NewName");
        assertThat(v.planCode()).isEqualTo("TRIAL");
        assertThat(v.status()).isEqualTo("active");
        assertThat(v.industry()).isEqualTo("Retail");
    }

    @Test
    @DisplayName("update — unknown id → WorkspaceNotFoundException")
    void update_unknownId_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.update(id, "X", null, null))
                .isInstanceOf(WorkspaceNotFoundException.class);
        verify(workspaceRepository, never()).save(any(Workspace.class));
    }

    @Test
    @DisplayName("update — bad plan_code → InvalidPlanCodeException, workspace unchanged")
    void update_badPlan_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.of(ws(id, "X", "TRIAL", "active")));
        given(workspaceRepository.findPlanCode("BOGUS")).willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.update(id, null, "BOGUS", null))
                .isInstanceOf(InvalidPlanCodeException.class);
        verify(workspaceRepository, never()).save(any(Workspace.class));
    }

    @Test
    @DisplayName("update — invalid status → InvalidStatusException")
    void update_invalidStatus_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.of(ws(id, "X", "TRIAL", "active")));

        assertThatThrownBy(() -> workspaceService.update(id, null, null, "banana"))
                .isInstanceOf(InvalidStatusException.class);
        verify(workspaceRepository, never()).save(any(Workspace.class));
    }

    // =========================================================================
    // softDelete()
    // =========================================================================

    @Test
    @DisplayName("softDelete — sets status='inactive' and saves")
    void softDelete_setsInactiveAndSaves() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id))
                .willReturn(Optional.of(ws(id, "X", "TRIAL", "active")));
        given(workspaceRepository.save(any(Workspace.class))).willAnswer(inv -> inv.getArgument(0));
        given(workspaceRepository.findIndustryByWorkspaceId(id)).willReturn(Optional.empty());

        WorkspaceView v = workspaceService.softDelete(id);

        assertThat(v.status()).isEqualTo("inactive");
        verify(workspaceRepository, times(1)).save(any(Workspace.class));
    }

    @Test
    @DisplayName("softDelete — already inactive is idempotent (no second save)")
    void softDelete_alreadyInactive_noSave() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id))
                .willReturn(Optional.of(ws(id, "X", "TRIAL", "inactive")));
        given(workspaceRepository.findIndustryByWorkspaceId(id)).willReturn(Optional.empty());

        WorkspaceView v = workspaceService.softDelete(id);

        assertThat(v.status()).isEqualTo("inactive");
        verify(workspaceRepository, never()).save(any(Workspace.class));
    }

    @Test
    @DisplayName("softDelete — unknown id → WorkspaceNotFoundException")
    void softDelete_unknownId_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.softDelete(id))
                .isInstanceOf(WorkspaceNotFoundException.class);
    }
}
