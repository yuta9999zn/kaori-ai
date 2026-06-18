package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.Workspace;
import com.kaorisystem.auth.model.WorkspaceAuditLog;
import com.kaorisystem.auth.repository.WorkspaceAuditLogRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository.BillingRow;
import com.kaorisystem.auth.service.WorkspaceService.AuditPage;
import com.kaorisystem.auth.service.WorkspaceService.BillingSummary;
import com.kaorisystem.auth.service.WorkspaceService.EnterpriseNotProvisionedException;
import com.kaorisystem.auth.service.WorkspaceService.InvalidCursorException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceView;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.sql.Date;
import java.time.Instant;
import java.time.LocalDate;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

/**
 * F-008 expansion — unit tests for the deep WorkspaceService methods
 * (get, getBillingSummary, listAudit, recordAudit). The original
 * WorkspaceServiceTest covers list/create/update/softDelete.
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("WorkspaceService deep — get / billing / audit unit tests")
class WorkspaceServiceDeepTest {

    @Mock private WorkspaceRepository         workspaceRepository;
    @Mock private WorkspaceAuditLogRepository auditLogRepository;
    /** Migration 024 prep — getBillingSummary() now flips row_security off
     *  at the top of the @Transactional method. Mock so the no-op call
     *  doesn't NPE. */
    @Mock private RlsBypassHelper             rlsBypass;

    @InjectMocks
    private WorkspaceService workspaceService;

    // -------------------------------------------------------------------------
    // Helpers
    // -------------------------------------------------------------------------

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

    private static BillingRow billingRow(int unique, int quota, int overage) {
        return new BillingRow() {
            @Override public Integer getUniqueCustomers() { return unique; }
            @Override public Integer getQuota()           { return quota; }
            @Override public Integer getOverageCount()    { return overage; }
        };
    }

    private static WorkspaceAuditLog auditEvent(UUID id, UUID workspaceId,
                                                 String type, String actor, Instant ts) {
        WorkspaceAuditLog ev = new WorkspaceAuditLog();
        ev.setEventId(id);
        ev.setWorkspaceId(workspaceId);
        ev.setEventType(type);
        ev.setActorEmail(actor);
        ev.setActorRole("ADMIN");
        ev.setResource("res");
        ev.setDetail("d");
        ev.setIpAddress("10.0.0.1");
        ev.setCreatedAt(ts);
        return ev;
    }

    // =========================================================================
    // get()
    // =========================================================================

    @Test
    @DisplayName("get — returns view with industry resolved from enterprises")
    void get_happyPath_returnsViewWithIndustry() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.of(ws(id, "Acme", "ENTERPRISE", "active")));
        given(workspaceRepository.findIndustryByWorkspaceId(id)).willReturn(Optional.of("Bán lẻ"));

        WorkspaceView v = workspaceService.get(id);

        assertThat(v.workspaceId()).isEqualTo(id);
        assertThat(v.name()).isEqualTo("Acme");
        assertThat(v.planCode()).isEqualTo("ENTERPRISE");
        assertThat(v.industry()).isEqualTo("Bán lẻ");
        assertThat(v.status()).isEqualTo("active");
    }

    @Test
    @DisplayName("get — industry absent → industry is null in view")
    void get_noIndustry_returnsNull() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.of(ws(id, "Acme", "TRIAL", "active")));
        given(workspaceRepository.findIndustryByWorkspaceId(id)).willReturn(Optional.empty());

        WorkspaceView v = workspaceService.get(id);

        assertThat(v.industry()).isNull();
    }

    @Test
    @DisplayName("get — unknown id raises WorkspaceNotFoundException")
    void get_unknownId_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.get(id))
                .isInstanceOf(WorkspaceNotFoundException.class);
        verify(workspaceRepository, never()).findIndustryByWorkspaceId(any());
    }

    // =========================================================================
    // getBillingSummary()
    // =========================================================================

    @Test
    @DisplayName("billing — happy path: derives money from plan price + status=normal under 80%")
    void billing_underWarn_statusNormal() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId))
                .willReturn(Optional.of(ws(workspaceId, "Acme", "BUSINESS", "active")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(workspaceRepository.findBillingForMonth(eq(enterpriseId), any(Date.class)))
                .willReturn(Optional.of(billingRow(800, 2000, 0)));     // 40% used
        given(workspaceRepository.findPlanQuota("BUSINESS")).willReturn(Optional.of(2000));
        given(workspaceRepository.findPlanPriceVnd("BUSINESS")).willReturn(Optional.of(1_490_000.0));

        BillingSummary b = workspaceService.getBillingSummary(workspaceId);

        assertThat(b.workspaceId()).isEqualTo(workspaceId);
        assertThat(b.planCode()).isEqualTo("BUSINESS");
        assertThat(b.uniqueCustomers()).isEqualTo(800);
        assertThat(b.quota()).isEqualTo(2000);
        assertThat(b.overageUnits()).isZero();
        assertThat(b.baseAmountVnd()).isEqualTo(1_490_000.0);
        assertThat(b.overageAmountVnd()).isZero();
        assertThat(b.totalAmountVnd()).isEqualTo(1_490_000.0);
        assertThat(b.status()).isEqualTo("normal");
        assertThat(b.quotaWarnAtPct()).isEqualTo(80);
        assertThat(b.billingMonth()).matches("\\d{4}-\\d{2}");
        LocalDate expectedNext = LocalDate.now(ZoneOffset.UTC).withDayOfMonth(1).plusMonths(1);
        assertThat(b.nextInvoiceDate()).isEqualTo(expectedNext);
    }

    @Test
    @DisplayName("billing — usage 80% triggers status=warn")
    void billing_atWarnThreshold_statusWarn() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId))
                .willReturn(Optional.of(ws(workspaceId, "X", "STARTER", "active")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(workspaceRepository.findBillingForMonth(eq(enterpriseId), any()))
                .willReturn(Optional.of(billingRow(400, 500, 0)));      // 80%
        given(workspaceRepository.findPlanQuota("STARTER")).willReturn(Optional.of(500));
        given(workspaceRepository.findPlanPriceVnd("STARTER")).willReturn(Optional.of(490_000.0));

        BillingSummary b = workspaceService.getBillingSummary(workspaceId);

        assertThat(b.status()).isEqualTo("warn");
    }

    @Test
    @DisplayName("billing — usage 95% triggers status=critical")
    void billing_atCriticalThreshold_statusCritical() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId))
                .willReturn(Optional.of(ws(workspaceId, "X", "TRIAL", "active")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(workspaceRepository.findBillingForMonth(eq(enterpriseId), any()))
                .willReturn(Optional.of(billingRow(95, 100, 0)));        // 95%
        given(workspaceRepository.findPlanQuota("TRIAL")).willReturn(Optional.of(100));
        given(workspaceRepository.findPlanPriceVnd("TRIAL")).willReturn(Optional.of(0.0));

        BillingSummary b = workspaceService.getBillingSummary(workspaceId);

        assertThat(b.status()).isEqualTo("critical");
    }

    @Test
    @DisplayName("billing — overage>0 always trumps usage% to status=overage")
    void billing_overage_statusOverage() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId))
                .willReturn(Optional.of(ws(workspaceId, "X", "BUSINESS", "active")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(workspaceRepository.findBillingForMonth(eq(enterpriseId), any()))
                .willReturn(Optional.of(billingRow(2100, 2000, 100)));   // over quota
        given(workspaceRepository.findPlanQuota("BUSINESS")).willReturn(Optional.of(2000));
        given(workspaceRepository.findPlanPriceVnd("BUSINESS")).willReturn(Optional.of(1_490_000.0));

        BillingSummary b = workspaceService.getBillingSummary(workspaceId);

        assertThat(b.overageUnits()).isEqualTo(100);
        assertThat(b.status()).isEqualTo("overage");
    }

    @Test
    @DisplayName("billing — no row for current month synthesizes empty 0/quota summary")
    void billing_noBillingRow_synthesizesZero() {
        UUID workspaceId  = UUID.randomUUID();
        UUID enterpriseId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId))
                .willReturn(Optional.of(ws(workspaceId, "Fresh", "TRIAL", "active")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.of(enterpriseId));
        given(workspaceRepository.findBillingForMonth(eq(enterpriseId), any()))
                .willReturn(Optional.empty());
        given(workspaceRepository.findPlanQuota("TRIAL")).willReturn(Optional.of(100));
        given(workspaceRepository.findPlanPriceVnd("TRIAL")).willReturn(Optional.of(0.0));

        BillingSummary b = workspaceService.getBillingSummary(workspaceId);

        assertThat(b.uniqueCustomers()).isZero();
        assertThat(b.quota()).isEqualTo(100);
        assertThat(b.overageUnits()).isZero();
        assertThat(b.status()).isEqualTo("normal");
    }

    @Test
    @DisplayName("billing — unknown workspace → WorkspaceNotFoundException")
    void billing_unknownWorkspace_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.findById(id)).willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.getBillingSummary(id))
                .isInstanceOf(WorkspaceNotFoundException.class);
    }

    @Test
    @DisplayName("billing — workspace exists but no enterprise yet → EnterpriseNotProvisionedException")
    void billing_noEnterprise_throws() {
        UUID workspaceId = UUID.randomUUID();
        given(workspaceRepository.findById(workspaceId))
                .willReturn(Optional.of(ws(workspaceId, "Bare", "TRIAL", "active")));
        given(workspaceRepository.findEnterpriseIdByWorkspaceId(workspaceId))
                .willReturn(Optional.empty());

        assertThatThrownBy(() -> workspaceService.getBillingSummary(workspaceId))
                .isInstanceOf(EnterpriseNotProvisionedException.class);
    }

    // =========================================================================
    // listAudit()
    // =========================================================================

    @Test
    @DisplayName("audit — null cursor calls findFirstPage and returns mapped views + total")
    void audit_firstPage() {
        UUID workspaceId = UUID.randomUUID();
        UUID eventId = UUID.randomUUID();
        Instant ts = Instant.parse("2026-04-25T10:00:00Z");
        given(workspaceRepository.existsById(workspaceId)).willReturn(true);
        given(auditLogRepository.findFirstPage(workspaceId, 50))
                .willReturn(List.of(auditEvent(eventId, workspaceId, "workspace.updated", "u@x", ts)));
        given(auditLogRepository.countByWorkspaceId(workspaceId)).willReturn(1L);

        AuditPage page = workspaceService.listAudit(workspaceId, null, 50);

        assertThat(page.items()).hasSize(1);
        assertThat(page.items().get(0).eventId()).isEqualTo(eventId);
        assertThat(page.items().get(0).eventType()).isEqualTo("workspace.updated");
        assertThat(page.total()).isEqualTo(1L);
        assertThat(page.nextCursor()).isNull();
        verify(auditLogRepository, never()).findPageAfter(any(), any(), any(), any(Integer.class));
    }

    @Test
    @DisplayName("audit — full page emits nextCursor (encoded keyset of last event)")
    void audit_fullPage_emitsCursor() {
        UUID workspaceId = UUID.randomUUID();
        Instant ts = Instant.parse("2026-04-25T10:00:00Z");
        given(workspaceRepository.existsById(workspaceId)).willReturn(true);
        given(auditLogRepository.findFirstPage(workspaceId, 2))
                .willReturn(List.of(
                        auditEvent(UUID.randomUUID(), workspaceId, "a", "u@x", ts),
                        auditEvent(UUID.randomUUID(), workspaceId, "b", "u@x", ts)
                ));
        given(auditLogRepository.countByWorkspaceId(workspaceId)).willReturn(7L);

        AuditPage page = workspaceService.listAudit(workspaceId, null, 2);

        assertThat(page.items()).hasSize(2);
        assertThat(page.nextCursor()).isNotBlank();
        assertThat(page.total()).isEqualTo(7L);
    }

    @Test
    @DisplayName("audit — non-null cursor calls findPageAfter with decoded ts/id")
    void audit_withCursor() {
        UUID workspaceId = UUID.randomUUID();
        UUID lastId = UUID.fromString("11111111-2222-3333-4444-555555555555");
        Instant lastTs = Instant.parse("2026-04-20T08:30:00Z");
        String raw = lastTs.toString() + "|" + lastId;
        String cursor = java.util.Base64.getUrlEncoder().withoutPadding()
                .encodeToString(raw.getBytes(java.nio.charset.StandardCharsets.UTF_8));

        given(workspaceRepository.existsById(workspaceId)).willReturn(true);
        given(auditLogRepository.findPageAfter(eq(workspaceId), eq(lastTs), eq(lastId), eq(20)))
                .willReturn(List.of());
        given(auditLogRepository.countByWorkspaceId(workspaceId)).willReturn(0L);

        workspaceService.listAudit(workspaceId, cursor, 20);

        verify(auditLogRepository).findPageAfter(eq(workspaceId), eq(lastTs), eq(lastId), eq(20));
        verify(auditLogRepository, never()).findFirstPage(any(), any(Integer.class));
    }

    @Test
    @DisplayName("audit — unknown workspace → WorkspaceNotFoundException (no audit query made)")
    void audit_unknownWorkspace_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.existsById(id)).willReturn(false);

        assertThatThrownBy(() -> workspaceService.listAudit(id, null, 50))
                .isInstanceOf(WorkspaceNotFoundException.class);
        verify(auditLogRepository, never()).findFirstPage(any(), any(Integer.class));
    }

    @Test
    @DisplayName("audit — malformed cursor → InvalidCursorException")
    void audit_malformedCursor_throws() {
        UUID id = UUID.randomUUID();
        given(workspaceRepository.existsById(id)).willReturn(true);

        assertThatThrownBy(() -> workspaceService.listAudit(id, "!!!not-base64!!!", 50))
                .isInstanceOf(InvalidCursorException.class);
    }

    // =========================================================================
    // recordAudit()
    // =========================================================================

    @Test
    @DisplayName("recordAudit — persists event with all fields populated")
    void recordAudit_persistsEvent() {
        UUID workspaceId = UUID.randomUUID();

        workspaceService.recordAudit(
                workspaceId, "workspace.updated",
                "admin@kaori.io", "ADMIN",
                "plan_code", "TRIAL → BUSINESS", "10.0.0.1");

        ArgumentCaptor<WorkspaceAuditLog> cap = ArgumentCaptor.forClass(WorkspaceAuditLog.class);
        verify(auditLogRepository).save(cap.capture());
        WorkspaceAuditLog ev = cap.getValue();
        assertThat(ev.getWorkspaceId()).isEqualTo(workspaceId);
        assertThat(ev.getEventType()).isEqualTo("workspace.updated");
        assertThat(ev.getActorEmail()).isEqualTo("admin@kaori.io");
        assertThat(ev.getActorRole()).isEqualTo("ADMIN");
        assertThat(ev.getResource()).isEqualTo("plan_code");
        assertThat(ev.getDetail()).isEqualTo("TRIAL → BUSINESS");
        assertThat(ev.getIpAddress()).isEqualTo("10.0.0.1");
    }

    @Test
    @DisplayName("recordAudit — repository failure is swallowed (best-effort, doesn't bubble)")
    void recordAudit_repoFailure_swallowed() {
        UUID workspaceId = UUID.randomUUID();
        given(auditLogRepository.save(any(WorkspaceAuditLog.class)))
                .willThrow(new RuntimeException("DB down"));

        // Should not throw — caller decoupled from audit reliability
        workspaceService.recordAudit(workspaceId, "x", null, null, null, null, null);
    }
}
