package com.kaorisystem.auth.service;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.Duration;
import java.time.Instant;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * Pure unit tests for the TOTP / encryption helpers — no Spring context.
 * The service is instantiated directly and {@code initKey()} is called via
 * reflection so we exercise the real fall-back-to-dev-key path.
 */
@DisplayName("TotpService — RFC 6238 + AES-GCM round-trip")
class TotpServiceTest {

    private TotpService svc;

    @BeforeEach
    void setUp() {
        svc = new TotpService();
        ReflectionTestUtils.setField(svc, "mfaKeyB64", "");
        svc.initKey();   // package-private — uses deterministic dev key
    }

    // -------------------------------------------------------------------------
    // Base32 encoding (matches Google Authenticator's encoding)
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("base32 — known RFC 4648 vectors")
    void base32_knownVectors() {
        // "f"     → MY======   (no-padding form: MY)
        // "fo"    → MZXQ
        // "foob"  → MZXW6YQ → no-pad: MZXW6YQ (7 chars)
        assertThat(svc.base32("f".getBytes()))    .isEqualTo("MY");
        assertThat(svc.base32("fo".getBytes()))   .isEqualTo("MZXQ");
        assertThat(svc.base32("foo".getBytes()))  .isEqualTo("MZXW6");
        assertThat(svc.base32("foob".getBytes())) .isEqualTo("MZXW6YQ");
        assertThat(svc.base32("foobar".getBytes())).isEqualTo("MZXW6YTBOI");
    }

    // -------------------------------------------------------------------------
    // generateCode + verify
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("verify — accepts the freshly-generated code")
    void verify_currentCode() {
        byte[] secret = svc.generateSecret();
        Instant now = Instant.parse("2026-04-26T12:00:00Z");
        String code = svc.generateCode(secret, now);

        assertThat(code).hasSize(6).matches("\\d{6}");
        assertThat(svc.verify(secret, code, now)).isTrue();
    }

    @Test
    @DisplayName("verify — accepts code from previous and next 30s window (clock skew)")
    void verify_skewWindow() {
        byte[] secret = svc.generateSecret();
        Instant t   = Instant.parse("2026-04-26T12:00:00Z");
        Instant minus30 = t.minusSeconds(30);
        Instant plus30  = t.plusSeconds(30);

        String prev   = svc.generateCode(secret, minus30);
        String curr   = svc.generateCode(secret, t);
        String future = svc.generateCode(secret, plus30);

        assertThat(svc.verify(secret, prev,   t)).as("previous step within tolerance").isTrue();
        assertThat(svc.verify(secret, curr,   t)).isTrue();
        assertThat(svc.verify(secret, future, t)).as("next step within tolerance").isTrue();
    }

    @Test
    @DisplayName("verify — rejects codes from outside the ±30s window")
    void verify_outsideWindow() {
        byte[] secret = svc.generateSecret();
        Instant t  = Instant.parse("2026-04-26T12:00:00Z");
        String old = svc.generateCode(secret, t.minusSeconds(120));   // 2 min ago = 4 steps
        String far = svc.generateCode(secret, t.plusSeconds(120));    // 2 min from now

        assertThat(svc.verify(secret, old, t)).isFalse();
        assertThat(svc.verify(secret, far, t)).isFalse();
    }

    @Test
    @DisplayName("verify — null/wrong-length codes return false (no exceptions)")
    void verify_invalidShape() {
        byte[] secret = svc.generateSecret();
        Instant t = Instant.parse("2026-04-26T12:00:00Z");

        assertThat(svc.verify(secret, null,    t)).isFalse();
        assertThat(svc.verify(secret, "",      t)).isFalse();
        assertThat(svc.verify(secret, "12345", t)).isFalse();
        assertThat(svc.verify(secret, "1234567", t)).isFalse();
        assertThat(svc.verify(secret, "abcdef", t)).isFalse();   // not digits
    }

    @Test
    @DisplayName("verify — wrong secret rejects valid-shape code")
    void verify_wrongSecret() {
        Instant t = Instant.parse("2026-04-26T12:00:00Z");
        byte[] s1 = svc.generateSecret();
        byte[] s2 = svc.generateSecret();
        String code = svc.generateCode(s1, t);
        assertThat(svc.verify(s2, code, t)).isFalse();
    }

    // -------------------------------------------------------------------------
    // otpauth URL
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("otpauthUrl — emits Google Authenticator format with SHA1+6+30s")
    void otpauthUrl_format() {
        byte[] secret = "12345678901234567890".getBytes();   // RFC 6238 example secret
        String url = svc.otpauthUrl("Kaori", "admin@example.com", secret);

        // The colon between issuer and account is the otpauth label separator,
        // intentionally NOT URL-encoded — it's how Google Authenticator parses
        // out the issuer prefix on the entry it shows.
        assertThat(url)
                .startsWith("otpauth://totp/")
                .contains("Kaori:admin%40example.com")
                .contains("&issuer=Kaori")
                .contains("&algorithm=SHA1")
                .contains("&digits=6")
                .contains("&period=30");
        // Embedded secret is the Base32 of the byte array
        assertThat(url).contains("secret=" + svc.base32(secret));
    }

    // -------------------------------------------------------------------------
    // AES-GCM round-trip
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("encrypt/decrypt — round-trip preserves the plaintext")
    void aes_roundTrip() {
        byte[] secret = svc.generateSecret();
        String enc = svc.encrypt(secret);
        byte[] back = svc.decrypt(enc);
        assertThat(back).containsExactly(secret);
    }

    @Test
    @DisplayName("encrypt — distinct IVs per call (ciphertext varies even for the same input)")
    void aes_freshIv() {
        byte[] secret = svc.generateSecret();
        String a = svc.encrypt(secret);
        String b = svc.encrypt(secret);
        assertThat(a).isNotEqualTo(b);
    }

    @Test
    @DisplayName("decrypt — tampered ciphertext throws")
    void aes_tamperRejected() {
        byte[] secret = svc.generateSecret();
        String enc = svc.encrypt(secret);
        // Flip one byte in the middle (well past the IV)
        byte[] raw = java.util.Base64.getDecoder().decode(enc);
        raw[raw.length - 2] ^= 0x01;
        String bad = java.util.Base64.getEncoder().encodeToString(raw);
        assertThatThrownBy(() -> svc.decrypt(bad))
                .isInstanceOf(IllegalStateException.class);
    }

    @Test
    @DisplayName("explicit non-default key — must be exactly 32 bytes (AES-256)")
    void initKey_wrongLength() {
        TotpService bad = new TotpService();
        ReflectionTestUtils.setField(bad, "mfaKeyB64",
                java.util.Base64.getEncoder().encodeToString(new byte[16])); // 128-bit
        assertThatThrownBy(bad::initKey).isInstanceOf(IllegalStateException.class);
    }

    // -------------------------------------------------------------------------
    // 3.1.c — production profile fail-fast
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("3.1.c — production profile + missing key → fail fast at startup")
    void initKey_productionRequiresKey() {
        TotpService prod = new TotpService();
        ReflectionTestUtils.setField(prod, "mfaKeyB64", "");
        ReflectionTestUtils.setField(prod, "activeProfiles", "production");
        assertThatThrownBy(prod::initKey)
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("kaori.mfa-key")
                .hasMessageContaining("production");
    }

    @Test
    @DisplayName("3.1.c — 'prod' alias also triggers fail fast")
    void initKey_prodAliasRequiresKey() {
        TotpService prod = new TotpService();
        ReflectionTestUtils.setField(prod, "mfaKeyB64", "");
        ReflectionTestUtils.setField(prod, "activeProfiles", "prod");
        assertThatThrownBy(prod::initKey).isInstanceOf(IllegalStateException.class);
    }

    @Test
    @DisplayName("3.1.c — multi-profile list with 'production' anywhere triggers fail fast")
    void initKey_multiProfile() {
        TotpService prod = new TotpService();
        ReflectionTestUtils.setField(prod, "mfaKeyB64", "");
        ReflectionTestUtils.setField(prod, "activeProfiles", "metrics,production,observability");
        assertThatThrownBy(prod::initKey).isInstanceOf(IllegalStateException.class);
    }

    @Test
    @DisplayName("3.1.c — non-production profiles allow the dev-key fallback")
    void initKey_devProfileFallsBack() {
        for (String profile : new String[]{"", null, "dev", "test", "staging,test"}) {
            TotpService svc = new TotpService();
            ReflectionTestUtils.setField(svc, "mfaKeyB64", "");
            ReflectionTestUtils.setField(svc, "activeProfiles", profile);
            svc.initKey();   // must not throw
            // Sanity: encrypt round-trip works with the dev key
            byte[] secret = svc.generateSecret();
            assertThat(svc.decrypt(svc.encrypt(secret))).containsExactly(secret);
        }
    }

    @Test
    @DisplayName("3.1.c — production profile with valid 32-byte key starts up")
    void initKey_productionWithValidKey() {
        TotpService prod = new TotpService();
        ReflectionTestUtils.setField(prod, "mfaKeyB64",
                java.util.Base64.getEncoder().encodeToString(new byte[32]));
        ReflectionTestUtils.setField(prod, "activeProfiles", "production");
        prod.initKey();   // must not throw — operator did their job
    }

    @Test
    @DisplayName("3.1.c — isProductionProfile static helper boundary cases")
    void isProductionProfile_boundaries() {
        assertThat(TotpService.isProductionProfile(null)).isFalse();
        assertThat(TotpService.isProductionProfile("")).isFalse();
        assertThat(TotpService.isProductionProfile("dev")).isFalse();
        assertThat(TotpService.isProductionProfile("production")).isTrue();
        assertThat(TotpService.isProductionProfile("Production")).isTrue();
        assertThat(TotpService.isProductionProfile("PROD")).isTrue();
        assertThat(TotpService.isProductionProfile(" prod ")).isTrue();
        assertThat(TotpService.isProductionProfile("dev,prod,test")).isTrue();
        // Substrings of 'production' must NOT match — "approved" shouldn't trigger
        assertThat(TotpService.isProductionProfile("approved")).isFalse();
        assertThat(TotpService.isProductionProfile("preprod")).isFalse();
    }

    @Test
    @DisplayName("acceptanceWindow constant: ±1 step → 90 seconds")
    void acceptanceWindow() {
        assertThat(TotpService.acceptanceWindow()).isEqualTo(Duration.ofSeconds(90));
    }
}
