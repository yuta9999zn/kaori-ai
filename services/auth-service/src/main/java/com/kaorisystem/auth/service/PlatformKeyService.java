package com.kaorisystem.auth.service;

import com.kaorisystem.auth.model.WorkspaceKey;
import com.kaorisystem.auth.repository.WorkspaceKeyRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Instant;
import java.util.HexFormat;
import java.util.List;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

@Service
@RequiredArgsConstructor
@Slf4j
public class PlatformKeyService {

    private static final String ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"; // no 0/O/1/I confusion
    private static final SecureRandom RNG = new SecureRandom();
    private static final int KEY_GEN_LIMIT_PER_HOUR = 20;

    private final WorkspaceKeyRepository keyRepository;
    private final StringRedisTemplate redis;

    /**
     * Generate a new workspace activation key.
     * Format: KAORI-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX
     * 32 chars × 5 bits (32-symbol alphabet) = 160-bit entropy.
     * Stores only SHA-256 hash; returns raw key ONCE.
     */
    @Transactional
    public GeneratedKey generate(UUID workspaceId, String label) {
        // Rate limit: max KEY_GEN_LIMIT_PER_HOUR key generations per workspace per hour
        String rateKey = "rate:key_gen:" + workspaceId;
        Long count = redis.opsForValue().increment(rateKey);
        if (count != null && count == 1L) {
            redis.expire(rateKey, 1, TimeUnit.HOURS);
        }
        if (count != null && count > KEY_GEN_LIMIT_PER_HOUR) {
            throw new RateLimitException(
                "Key generation limit reached (" + KEY_GEN_LIMIT_PER_HOUR + "/hour per workspace). Try again later."
            );
        }

        String rawKey = buildKey();
        String keyHash = sha256(rawKey);

        WorkspaceKey entity = new WorkspaceKey();
        entity.setWorkspaceId(workspaceId);
        entity.setKeyHash(keyHash);
        entity.setLabel(label);
        keyRepository.save(entity);

        log.info("platform.key.generated workspace={} label={}", workspaceId, label);
        return new GeneratedKey(entity.getKeyId(), rawKey, label, entity.getCreatedAt());
    }

    public List<WorkspaceKey> listActive(UUID workspaceId) {
        return keyRepository.findByWorkspaceIdOrderByCreatedAtDesc(workspaceId);
    }

    @Transactional
    public void revoke(UUID keyId) {
        int updated = keyRepository.revokeById(keyId, Instant.now());
        if (updated == 0) {
            throw new KeyNotFoundException("Key not found or already revoked: " + keyId);
        }
        log.info("platform.key.revoked", keyId);
    }

    // ---- Internal use by AuthService.activateWorkspace() ----

    public boolean isActiveKey(String rawKey) {
        return keyRepository.existsByKeyHashAndRevokedAtIsNull(sha256(rawKey));
    }

    public UUID findWorkspaceIdByKey(String rawKey) {
        return keyRepository.findWorkspaceIdByActiveHash(sha256(rawKey))
                .orElseThrow(() -> new KeyNotFoundException("Invalid or revoked workspace key."));
    }

    public UUID findEnterpriseIdByKey(String rawKey) {
        return keyRepository.findEnterpriseIdByActiveHash(sha256(rawKey))
                .orElseThrow(() -> new KeyNotFoundException("Invalid or revoked workspace key."));
    }

    @Transactional
    public void consumeKey(String rawKey) {
        keyRepository.revokeByHash(sha256(rawKey), Instant.now());
    }

    // ---- Helpers ----

    private String buildKey() {
        // 4 groups of 8 chars = 32 chars × 5 bits = 160-bit entropy
        StringBuilder sb = new StringBuilder("KAORI");
        for (int group = 0; group < 4; group++) {
            sb.append('-');
            for (int i = 0; i < 8; i++) {
                sb.append(ALPHABET.charAt(RNG.nextInt(ALPHABET.length())));
            }
        }
        return sb.toString(); // e.g. KAORI-A3BQ7KXM-2YPC9NHR-DW4T6EJQ-8VFMCBLZ
    }

    private String sha256(String input) {
        try {
            byte[] hash = MessageDigest.getInstance("SHA-256")
                    .digest(input.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hash);
        } catch (Exception e) {
            throw new RuntimeException("SHA-256 failed", e);
        }
    }

    // ---- Return type ----

    public record GeneratedKey(UUID keyId, String rawKey, String label, Instant createdAt) {}

    // ---- Exceptions ----

    public static class KeyNotFoundException extends RuntimeException {
        public KeyNotFoundException(String msg) { super(msg); }
    }

    public static class RateLimitException extends RuntimeException {
        public RateLimitException(String msg) { super(msg); }
    }
}
