package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.model.WorkspaceKey;
import com.kaorisystem.auth.service.PlatformKeyService;
import com.kaorisystem.auth.service.PlatformKeyService.KeyNotFoundException;
import com.kaorisystem.auth.service.PlatformKeyService.RateLimitException;
import jakarta.validation.Valid;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/v1/platform/keys")
@RequiredArgsConstructor
public class PlatformController {

    private final PlatformKeyService keyService;

    /**
     * POST /api/v1/platform/keys
     * Requires: SUPER_ADMIN or ADMIN role (enforced by API Gateway JWT filter).
     * Returns the raw key ONCE — store it; it cannot be retrieved again.
     */
    @PostMapping
    public ResponseEntity<?> generateKey(@Valid @RequestBody GenerateKeyRequest req) {
        try {
            UUID workspaceId = UUID.fromString(req.getWorkspaceId());
            PlatformKeyService.GeneratedKey result = keyService.generate(workspaceId, req.getLabel());

            return ResponseEntity.status(HttpStatus.CREATED).body(Map.of(
                "data", Map.of(
                    "key_id",     result.keyId(),
                    "raw_key",    result.rawKey(),
                    "label",      result.label() != null ? result.label() : "",
                    "created_at", result.createdAt()
                ),
                "meta", Map.of("warning", "Store this key immediately. It will not be shown again.")
            ));
        } catch (RateLimitException e) {
            return ResponseEntity.status(429).body(Map.of(
                "type",   "/docs/errors/rate-limit-exceeded",
                "title",  "Rate limit exceeded",
                "status", 429,
                "detail", e.getMessage()
            ));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                "type",   "/docs/errors/invalid-request",
                "title",  "Invalid workspace_id",
                "status", 400,
                "detail", "workspace_id must be a valid UUID"
            ));
        }
    }

    /**
     * GET /api/v1/platform/keys?workspace_id={uuid}
     * Lists all keys for a workspace — never returns raw keys (hashes only stored).
     */
    @GetMapping
    public ResponseEntity<?> listKeys(@RequestParam("workspace_id") String workspaceIdStr) {
        UUID workspaceId = UUID.fromString(workspaceIdStr);
        List<WorkspaceKey> keys = keyService.listActive(workspaceId);

        List<Map<String, Object>> items = keys.stream().map(k -> Map.<String, Object>of(
            "key_id",     k.getKeyId(),
            "label",      k.getLabel() != null ? k.getLabel() : "",
            "status",     k.isActive() ? "active" : "revoked",
            "revoked_at", k.getRevokedAt() != null ? k.getRevokedAt() : "",
            "created_at", k.getCreatedAt()
        )).toList();

        return ResponseEntity.ok(Map.of("data", items));
    }

    /**
     * DELETE /api/v1/platform/keys/{id}
     * Soft-revoke: sets revoked_at, does not delete the row (audit trail).
     */
    @DeleteMapping("/{id}")
    public ResponseEntity<?> revokeKey(@PathVariable("id") String keyIdStr) {
        try {
            UUID keyId = UUID.fromString(keyIdStr);
            keyService.revoke(keyId);
            return ResponseEntity.ok(Map.of(
                "data", Map.of("key_id", keyId, "status", "revoked", "revoked_at", Instant.now())
            ));
        } catch (KeyNotFoundException e) {
            return ResponseEntity.status(404).body(Map.of(
                "type",   "/docs/errors/key-not-found",
                "title",  "Key not found",
                "status", 404,
                "detail", e.getMessage()
            ));
        } catch (IllegalArgumentException e) {
            return ResponseEntity.badRequest().body(Map.of(
                "type",   "/docs/errors/invalid-id",
                "title",  "Invalid key ID",
                "status", 400,
                "detail", "key_id must be a valid UUID"
            ));
        }
    }

    // ---- Request DTOs ----

    @Data
    public static class GenerateKeyRequest {
        @NotNull
        private String workspaceId;

        @Size(max = 100)
        private String label;
    }
}
