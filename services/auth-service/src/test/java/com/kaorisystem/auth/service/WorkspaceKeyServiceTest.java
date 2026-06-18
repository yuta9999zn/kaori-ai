package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.WorkspaceKey;
import com.kaorisystem.auth.repository.WorkspaceKeyRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.service.PlatformKeyService.GeneratedKey;
import com.kaorisystem.auth.service.PlatformKeyService.KeyNotFoundException;
import com.kaorisystem.auth.service.WorkspaceKeyService.RevokedKey;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

/**
 * Unit tests for the F-009 orchestration layer. Pure Mockito — no Spring,
 * no DB, no Redis. Verifies:
 *
 *  - workspace existence is checked before delegating;
 *  - cross-workspace revoke (IDOR) is rejected with KeyNotFoundException;
 *  - already-revoked keys are rejected;
 *  - audit-log entries are written exactly once per success path
 *    (matches WorkspaceMemberService event-emission pattern).
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("WorkspaceKeyService — F-009 orchestration")
class WorkspaceKeyServiceTest {

    @Mock private PlatformKeyService     keyService;
    @Mock private WorkspaceKeyRepository keyRepository;
    @Mock private WorkspaceRepository    workspaceRepository;
    @Mock private WorkspaceService       workspaceService;

    @InjectMocks private WorkspaceKeyService underTest;

    // -------------------------------------------------------------------------
    // list
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("list — unknown workspace → WorkspaceNotFoundException, no repo call")
    void list_unknownWorkspace() {
        UUID wsId = UUID.randomUUID();
        given(workspaceRepository.existsById(wsId)).willReturn(false);

        assertThatThrownBy(() -> underTest.list(wsId))
                .isInstanceOf(WorkspaceNotFoundException.class);
        verify(keyService, never()).listActive(any());
    }

    @Test
    @DisplayName("list — happy path delegates to PlatformKeyService.listActive")
    void list_happyPath() {
        UUID wsId = UUID.randomUUID();
        WorkspaceKey k = newKey(wsId, "prod");
        given(workspaceRepository.existsById(wsId)).willReturn(true);
        given(keyService.listActive(wsId)).willReturn(List.of(k));

        List<WorkspaceKey> out = underTest.list(wsId);
        assertThat(out).containsExactly(k);
    }

    // -------------------------------------------------------------------------
    // generate
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("generate — unknown workspace → 404, no key minted")
    void generate_unknownWorkspace() {
        UUID wsId = UUID.randomUUID();
        given(workspaceRepository.existsById(wsId)).willReturn(false);

        assertThatThrownBy(() -> underTest.generate(wsId, "prod", "a@x", "ADMIN", "127.0.0.1"))
                .isInstanceOf(WorkspaceNotFoundException.class);
        verify(keyService, never()).generate(any(), any());
        verify(workspaceService, never())
                .recordAudit(any(), anyString(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("generate — happy path emits exactly one audit row")
    void generate_writesAudit() {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        Instant now = Instant.parse("2026-04-26T08:00:00Z");
        given(workspaceRepository.existsById(wsId)).willReturn(true);
        given(keyService.generate(wsId, "prod"))
                .willReturn(new GeneratedKey(keyId, "KAORI-XX-XX-XX-XX", "prod", now));

        GeneratedKey r = underTest.generate(wsId, "prod", "a@x", "ADMIN", "127.0.0.1");

        assertThat(r.keyId()).isEqualTo(keyId);
        assertThat(r.rawKey()).isEqualTo("KAORI-XX-XX-XX-XX");
        verify(workspaceService, times(1)).recordAudit(
                eq(wsId), eq("key.generated"),
                eq("a@x"), eq("ADMIN"),
                eq("prod"), eq("key_id=" + keyId),
                eq("127.0.0.1"));
    }

    @Test
    @DisplayName("generate — null/blank label is normalised in audit row")
    void generate_blankLabelAuditFallback() {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        given(workspaceRepository.existsById(wsId)).willReturn(true);
        given(keyService.generate(wsId, null))
                .willReturn(new GeneratedKey(keyId, "raw", null, Instant.now()));

        underTest.generate(wsId, null, "a@x", "ADMIN", "1.1.1.1");
        verify(workspaceService).recordAudit(
                eq(wsId), eq("key.generated"),
                any(), any(),
                eq("(no label)"), eq("key_id=" + keyId),
                any());
    }

    // -------------------------------------------------------------------------
    // revoke — happy + IDOR + already-revoked + missing
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("revoke — key in another workspace returns KeyNotFoundException (IDOR guard)")
    void revoke_crossWorkspaceRejected() {
        UUID wsA  = UUID.randomUUID();
        UUID wsB  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        WorkspaceKey k = newKey(wsB, "label-b");

        given(workspaceRepository.existsById(wsA)).willReturn(true);
        given(keyRepository.findById(keyId)).willReturn(Optional.of(k));

        assertThatThrownBy(() -> underTest.revoke(wsA, keyId, "a@x", "ADMIN", "1.1.1.1"))
                .isInstanceOf(KeyNotFoundException.class);
        verify(keyService, never()).revoke(any());
        verify(workspaceService, never())
                .recordAudit(any(), anyString(), any(), any(), any(), any(), any());
    }

    @Test
    @DisplayName("revoke — already-revoked key returns KeyNotFoundException")
    void revoke_alreadyRevokedRejected() {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        WorkspaceKey k = newKey(wsId, "old");
        k.setRevokedAt(Instant.now().minusSeconds(60));

        given(workspaceRepository.existsById(wsId)).willReturn(true);
        given(keyRepository.findById(keyId)).willReturn(Optional.of(k));

        assertThatThrownBy(() -> underTest.revoke(wsId, keyId, "a@x", "ADMIN", "1.1.1.1"))
                .isInstanceOf(KeyNotFoundException.class);
        verify(keyService, never()).revoke(any());
    }

    @Test
    @DisplayName("revoke — happy path delegates and writes audit")
    void revoke_happyPath() {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        WorkspaceKey k = newKey(wsId, "prod");
        given(workspaceRepository.existsById(wsId)).willReturn(true);
        given(keyRepository.findById(keyId)).willReturn(Optional.of(k));

        RevokedKey r = underTest.revoke(wsId, keyId, "a@x", "ADMIN", "127.0.0.1");

        assertThat(r.keyId()).isEqualTo(keyId);
        assertThat(r.revokedAt()).isNotNull();
        verify(keyService, times(1)).revoke(keyId);
        verify(workspaceService, times(1)).recordAudit(
                eq(wsId), eq("key.revoked"),
                eq("a@x"), eq("ADMIN"),
                eq("prod"), eq("key_id=" + keyId),
                eq("127.0.0.1"));
    }

    @Test
    @DisplayName("revoke — unknown key id returns KeyNotFoundException")
    void revoke_missingKey() {
        UUID wsId  = UUID.randomUUID();
        UUID keyId = UUID.randomUUID();
        given(workspaceRepository.existsById(wsId)).willReturn(true);
        given(keyRepository.findById(keyId)).willReturn(Optional.empty());

        assertThatThrownBy(() -> underTest.revoke(wsId, keyId, "a@x", "ADMIN", "1.1.1.1"))
                .isInstanceOf(KeyNotFoundException.class);
    }

    // -------------------------------------------------------------------------
    // helpers
    // -------------------------------------------------------------------------

    private static WorkspaceKey newKey(UUID workspaceId, String label) {
        WorkspaceKey k = new WorkspaceKey();
        k.setKeyId(UUID.randomUUID());
        k.setWorkspaceId(workspaceId);
        k.setKeyHash("0".repeat(64));
        k.setLabel(label);
        k.setCreatedAt(Instant.parse("2026-04-26T08:00:00Z"));
        return k;
    }
}
