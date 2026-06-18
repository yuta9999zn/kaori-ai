package com.kaorisystem.auth.service;

import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import javax.crypto.Cipher;
import javax.crypto.Mac;
import javax.crypto.SecretKey;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.spec.SecretKeySpec;
import java.net.URLEncoder;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.SecureRandom;
import java.time.Duration;
import java.time.Instant;
import java.util.Base64;

/**
 * RFC 6238 TOTP (HMAC-SHA1, 30s step, 6 digits) — Google Authenticator
 * compatible. Pure Java; no external library.
 *
 * <p>Also bundles the at-rest secret encryption used by the platform admin
 * MFA flow:
 * <pre>
 *   stored = base64( IV(12B) || AES-256-GCM-ciphertext(secret_bytes) )
 * </pre>
 *
 * <p>Key sourced from the {@code kaori.mfa-key} property (Base64-encoded
 * 32 bytes). When unset and the {@code spring.profiles.active} contains
 * {@code dev}/{@code test}/empty, a deterministic dev key derived from a
 * fixed string is used so {@code mvn test} passes in clean checkouts. In
 * production the property MUST be set; absence is logged as a warning.
 */
@Service
@Slf4j
public class TotpService {

    /** Fixed parameters for Google Authenticator compatibility. */
    private static final int    STEP_SECONDS = 30;
    private static final int    DIGITS       = 6;
    private static final int    SKEW_STEPS   = 1;   // ±30s tolerance — enough for clock drift
    private static final String HMAC_ALG     = "HmacSHA1";
    private static final String AES_ALG      = "AES";
    private static final String AES_TRANSFORM = "AES/GCM/NoPadding";
    private static final int    GCM_IV_BYTES  = 12;
    private static final int    GCM_TAG_BITS  = 128;

    private static final SecureRandom RNG = new SecureRandom();

    @Value("${kaori.mfa-key:}")
    private String mfaKeyB64;

    /**
     * Used to gate the dev-key fallback. When the active profile contains
     * {@code prod} or {@code production} and {@code kaori.mfa-key} is blank,
     * we refuse to start — mirrors the operator expectation set by
     * CLAUDE.md §15 ("MFA Key Management").
     */
    @Value("${spring.profiles.active:}")
    private String activeProfiles;

    private SecretKey aesKey;

    @PostConstruct
    void initKey() {
        byte[] keyBytes;
        if (mfaKeyB64 == null || mfaKeyB64.isBlank()) {
            if (isProductionProfile(activeProfiles)) {
                throw new IllegalStateException(
                        "kaori.mfa-key (env KAORI_MFA_KEY) is required when spring.profiles.active "
                      + "includes 'prod' or 'production'. Generate one with "
                      + "`openssl rand -base64 32` and inject it via your secret manager. "
                      + "See CLAUDE.md §15 'MFA Key Management'. "
                      + "Active profile: " + activeProfiles);
            }
            log.warn("kaori.mfa-key is not set — using a deterministic dev key. "
                    + "Acceptable only for tests / local dev. Set KAORI_MFA_KEY in production. "
                    + "(active profiles: '{}')", activeProfiles);
            // Deterministic 32-byte key derived from a fixed dev string. Distinct
            // per-deploy keys MUST be used in production; this default is just
            // so the test suite + first-run dev experience does not require
            // operator setup.
            keyBytes = sha256("kaori-dev-mfa-key-do-not-use-in-prod".getBytes(StandardCharsets.UTF_8));
        } else {
            keyBytes = Base64.getDecoder().decode(mfaKeyB64);
            if (keyBytes.length != 32) {
                throw new IllegalStateException(
                        "kaori.mfa-key must be Base64 of exactly 32 bytes (AES-256). "
                      + "Got " + keyBytes.length + " bytes. Regenerate with `openssl rand -base64 32`.");
            }
        }
        this.aesKey = new SecretKeySpec(keyBytes, AES_ALG);
    }

    /** {@code prod} / {@code production} (any case) anywhere in the comma-separated profile list. */
    static boolean isProductionProfile(String activeProfiles) {
        if (activeProfiles == null || activeProfiles.isBlank()) return false;
        for (String p : activeProfiles.split(",")) {
            String n = p.trim().toLowerCase();
            if ("production".equals(n) || "prod".equals(n)) return true;
        }
        return false;
    }

    // =========================================================================
    // Public API
    // =========================================================================

    /** 20 random bytes — the standard size used by Google Authenticator. */
    public byte[] generateSecret() {
        byte[] s = new byte[20];
        RNG.nextBytes(s);
        return s;
    }

    /** Base32 (RFC 4648, no padding) encoding for the otpauth URL. */
    public String base32(byte[] bytes) {
        final char[] ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567".toCharArray();
        StringBuilder out = new StringBuilder((bytes.length * 8 + 4) / 5);
        int buf = 0, bits = 0;
        for (byte b : bytes) {
            buf = (buf << 8) | (b & 0xFF);
            bits += 8;
            while (bits >= 5) {
                bits -= 5;
                out.append(ALPHABET[(buf >> bits) & 0x1F]);
            }
        }
        if (bits > 0) out.append(ALPHABET[(buf << (5 - bits)) & 0x1F]);
        return out.toString();
    }

    /**
     * Build the standard otpauth URL embedded in the QR code.
     * Format: {@code otpauth://totp/{issuer}:{account}?secret={base32}&issuer={issuer}}.
     */
    public String otpauthUrl(String issuer, String account, byte[] secret) {
        String label = urlEncode(issuer) + ":" + urlEncode(account);
        return "otpauth://totp/" + label
                + "?secret=" + base32(secret)
                + "&issuer=" + urlEncode(issuer)
                + "&algorithm=SHA1&digits=" + DIGITS + "&period=" + STEP_SECONDS;
    }

    /** Generate the current TOTP code for the given secret. */
    public String generateCode(byte[] secret, Instant now) {
        return formatCode(hotp(secret, now.getEpochSecond() / STEP_SECONDS));
    }

    /**
     * Constant-time verify of a 6-digit code against the secret. Accepts
     * codes from the previous, current, or next 30s window (handles client
     * clock drift up to ±30s).
     */
    public boolean verify(byte[] secret, String code, Instant now) {
        if (code == null || code.length() != DIGITS) return false;
        long counter = now.getEpochSecond() / STEP_SECONDS;
        for (int delta = -SKEW_STEPS; delta <= SKEW_STEPS; delta++) {
            String candidate = formatCode(hotp(secret, counter + delta));
            if (constantTimeEquals(candidate, code)) return true;
        }
        return false;
    }

    public boolean verify(byte[] secret, String code) {
        return verify(secret, code, Instant.now());
    }

    /** AES-256-GCM encrypt; returns Base64({@code IV || ciphertext}). */
    public String encrypt(byte[] plaintext) {
        try {
            byte[] iv = new byte[GCM_IV_BYTES];
            RNG.nextBytes(iv);
            Cipher c = Cipher.getInstance(AES_TRANSFORM);
            c.init(Cipher.ENCRYPT_MODE, aesKey, new GCMParameterSpec(GCM_TAG_BITS, iv));
            byte[] ct = c.doFinal(plaintext);
            ByteBuffer buf = ByteBuffer.allocate(iv.length + ct.length);
            buf.put(iv).put(ct);
            return Base64.getEncoder().encodeToString(buf.array());
        } catch (Exception e) {
            throw new IllegalStateException("MFA encrypt failed", e);
        }
    }

    public byte[] decrypt(String envelopeB64) {
        try {
            byte[] envelope = Base64.getDecoder().decode(envelopeB64);
            if (envelope.length <= GCM_IV_BYTES) {
                throw new IllegalArgumentException("Ciphertext envelope too short");
            }
            byte[] iv = new byte[GCM_IV_BYTES];
            System.arraycopy(envelope, 0, iv, 0, GCM_IV_BYTES);
            byte[] ct = new byte[envelope.length - GCM_IV_BYTES];
            System.arraycopy(envelope, GCM_IV_BYTES, ct, 0, ct.length);
            Cipher c = Cipher.getInstance(AES_TRANSFORM);
            c.init(Cipher.DECRYPT_MODE, aesKey, new GCMParameterSpec(GCM_TAG_BITS, iv));
            return c.doFinal(ct);
        } catch (Exception e) {
            throw new IllegalStateException("MFA decrypt failed", e);
        }
    }

    // =========================================================================
    // Internals
    // =========================================================================

    /** RFC 4226 dynamic truncation → 31-bit number → keep last DIGITS digits. */
    private int hotp(byte[] secret, long counter) {
        byte[] counterBytes = ByteBuffer.allocate(8).putLong(counter).array();
        try {
            Mac mac = Mac.getInstance(HMAC_ALG);
            mac.init(new SecretKeySpec(secret, HMAC_ALG));
            byte[] hash = mac.doFinal(counterBytes);
            int offset = hash[hash.length - 1] & 0x0F;
            int bin = ((hash[offset]     & 0x7F) << 24)
                    | ((hash[offset + 1] & 0xFF) << 16)
                    | ((hash[offset + 2] & 0xFF) << 8)
                    |  (hash[offset + 3] & 0xFF);
            return bin % POW10[DIGITS];
        } catch (Exception e) {
            throw new IllegalStateException("HOTP failed", e);
        }
    }

    private static final int[] POW10 = { 1, 10, 100, 1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000 };

    private static String formatCode(int v) {
        return String.format("%0" + DIGITS + "d", v);
    }

    /** Length-checked constant-time string compare. */
    private static boolean constantTimeEquals(String a, String b) {
        if (a == null || b == null || a.length() != b.length()) return false;
        int diff = 0;
        for (int i = 0; i < a.length(); i++) diff |= a.charAt(i) ^ b.charAt(i);
        return diff == 0;
    }

    private static byte[] sha256(byte[] in) {
        try { return MessageDigest.getInstance("SHA-256").digest(in); }
        catch (Exception e) { throw new IllegalStateException(e); }
    }

    private static String urlEncode(String s) {
        return URLEncoder.encode(s, StandardCharsets.UTF_8);
    }

    /** Sanity-check: total period covered by the verifier (used by tests). */
    public static Duration acceptanceWindow() {
        return Duration.ofSeconds((long) STEP_SECONDS * (1 + 2 * SKEW_STEPS));
    }
}
