package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.WorkspaceKey;
import com.kaorisystem.auth.repository.WorkspaceKeyRepository;
import com.kaorisystem.auth.repository.WorkspaceRepository;
import com.kaorisystem.auth.service.PlatformKeyService.GeneratedKey;
import com.kaorisystem.auth.service.PlatformKeyService.KeyNotFoundException;
import com.kaorisystem.auth.service.WorkspaceService.WorkspaceNotFoundException;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

/**
 * F-009 — workspace-scoped key management for the nested
 * {@code /api/v1/platform/workspaces/{id}/keys} routes (Batch 2).
 *
 * <p>This is a thin orchestrator over {@link PlatformKeyService}: it adds the
 * cross-workspace ownership check needed when a caller addresses a key by id
 * inside a workspace path (IDOR protection — a malicious admin must not be
 * able to revoke another workspace's keys via the nested URL), and it emits
 * audit-log entries into {@code workspace_audit_log} the same way
 * {@link WorkspaceMemberService} does for member events.
 *
 * <p>The original flat endpoints in {@code PlatformController} continue to
 * call {@link PlatformKeyService} directly — they retain their existing
 * behaviour (no audit log, no workspace path check) for backward compatibility
 * and for the {@code AuthService.activateWorkspace} consumer.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class WorkspaceKeyService {

    private final PlatformKeyService     keyService;
    private final WorkspaceKeyRepository keyRepository;
    private final WorkspaceRepository    workspaceRepository;
    private final WorkspaceService       workspaceService;

    // =========================================================================
    // List
    // =========================================================================
    @Transactional(readOnly = true)
    public List<WorkspaceKey> list(UUID workspaceId) {
        ensureWorkspaceExists(workspaceId);
        return keyService.listActive(workspaceId);
    }

    // =========================================================================
    // Generate
    // =========================================================================
    @Transactional
    public GeneratedKey generate(UUID workspaceId, String label,
                                 String actorEmail, String actorRole, String ipAddress) {
        ensureWorkspaceExists(workspaceId);
        GeneratedKey result = keyService.generate(workspaceId, label);

        workspaceService.recordAudit(
                workspaceId, "key.generated",
                actorEmail, actorRole,
                label == null || label.isBlank() ? "(no label)" : label,
                "key_id=" + result.keyId(),
                ipAddress);

        return result;
    }

    // =========================================================================
    // Revoke (workspace-scoped — verifies the key actually belongs here)
    // =========================================================================
    @Transactional
    public RevokedKey revoke(UUID workspaceId, UUID keyId,
                             String actorEmail, String actorRole, String ipAddress) {
        ensureWorkspaceExists(workspaceId);

        // Cross-workspace ownership check. We treat "wrong workspace" the same
        // as "not found" so the endpoint never confirms the existence of keys
        // outside the caller's scope. Already-revoked keys also return 404 —
        // matches PlatformKeyService.revoke()'s contract.
        WorkspaceKey key = keyRepository.findById(keyId)
                .orElseThrow(() -> new KeyNotFoundException("Key not found: " + keyId));
        if (!workspaceId.equals(key.getWorkspaceId())) {
            throw new KeyNotFoundException("Key not found in workspace " + workspaceId + ": " + keyId);
        }
        if (key.getRevokedAt() != null) {
            throw new KeyNotFoundException("Key already revoked: " + keyId);
        }

        // Delegate to existing atomic UPDATE — protects against the tiny race
        // between the read above and the write here (a concurrent revoke would
        // make this return 0 and we still throw 404).
        keyService.revoke(keyId);
        Instant revokedAt = Instant.now();

        workspaceService.recordAudit(
                workspaceId, "key.revoked",
                actorEmail, actorRole,
                key.getLabel() == null || key.getLabel().isBlank() ? "(no label)" : key.getLabel(),
                "key_id=" + keyId,
                ipAddress);

        return new RevokedKey(keyId, revokedAt);
    }

    // =========================================================================
    // Helpers
    // =========================================================================

    private void ensureWorkspaceExists(UUID workspaceId) {
        if (!workspaceRepository.existsById(workspaceId)) {
            throw new WorkspaceNotFoundException("Workspace not found: " + workspaceId);
        }
    }

    public record RevokedKey(UUID keyId, Instant revokedAt) {}
}
