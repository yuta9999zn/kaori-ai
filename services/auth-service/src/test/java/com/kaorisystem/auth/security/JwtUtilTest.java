package com.kaorisystem.auth.security;

import io.jsonwebtoken.Claims;
import io.jsonwebtoken.JwtException;
import org.junit.jupiter.api.*;

import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Base64;
import java.util.UUID;

import static org.assertj.core.api.Assertions.*;

@DisplayName("JwtUtil — RSA RS256 token lifecycle")
class JwtUtilTest {

    // Shared across all tests — generated once per test class run
    private static JwtUtil jwtUtil;

    // Fixed identifiers reused across individual tests
    private static final UUID USER_ID       = UUID.randomUUID();
    private static final UUID ENTERPRISE_ID = UUID.randomUUID();
    private static final String ROLE        = "MANAGER";

    @BeforeAll
    static void generateKeyPairAndBuildJwtUtil() throws Exception {
        // given — a fresh RSA-2048 key pair generated in-memory
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair pair = gen.generateKeyPair();

        String privateB64 = Base64.getEncoder()
                .encodeToString(pair.getPrivate().getEncoded());
        String publicB64 = Base64.getEncoder()
                .encodeToString(pair.getPublic().getEncoded());

        // JwtUtil constructor accepts base64 strings + TTL parameters
        jwtUtil = new JwtUtil(privateB64, publicB64, 15L, 7L);
    }

    // -------------------------------------------------------------------------
    // generateAccessToken
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("generateAccessToken: subject=userId, enterprise_id, role, and type='access' are present in claims")
    void generateAccessToken_containsCorrectClaims() {
        // when
        String token = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);

        // then
        Claims claims = jwtUtil.validateAndParse(token);
        assertThat(claims.getSubject())
                .as("subject must equal userId")
                .isEqualTo(USER_ID.toString());
        assertThat(claims.get("enterprise_id", String.class))
                .as("enterprise_id claim")
                .isEqualTo(ENTERPRISE_ID.toString());
        assertThat(claims.get("role", String.class))
                .as("role claim")
                .isEqualTo(ROLE);
        assertThat(claims.get("type", String.class))
                .as("type claim must be 'access'")
                .isEqualTo("access");
    }

    @Test
    @DisplayName("generateAccessToken: expiration is within [14, 16] minutes of now")
    void generateAccessToken_expiresIn15Min() {
        // given
        long before = System.currentTimeMillis();

        // when
        String token = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);
        Claims claims = jwtUtil.validateAndParse(token);

        // then
        long expMs    = claims.getExpiration().getTime();
        long issuedMs = claims.getIssuedAt().getTime();
        long diffMin  = (expMs - issuedMs) / 60_000;

        assertThat(diffMin)
                .as("access token TTL should be ~15 minutes (between 14 and 16)")
                .isBetween(14L, 16L);
        // Also confirm expiry is in the future relative to test start
        assertThat(expMs).isGreaterThan(before);
    }

    // -------------------------------------------------------------------------
    // generateRefreshToken
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("generateRefreshToken: type='refresh' and jti claim exists")
    void generateRefreshToken_typeIsRefresh() {
        // when
        String token = jwtUtil.generateRefreshToken(USER_ID, ENTERPRISE_ID);
        Claims claims = jwtUtil.validateAndParse(token);

        // then
        assertThat(claims.get("type", String.class))
                .as("type claim must be 'refresh'")
                .isEqualTo("refresh");
        assertThat(claims.get("jti", String.class))
                .as("jti claim must be present")
                .isNotBlank();
    }

    @Test
    @DisplayName("generateRefreshToken: two successive calls produce different jti values")
    void generateRefreshToken_hasUniqueJti() {
        // when
        String tokenA = jwtUtil.generateRefreshToken(USER_ID, ENTERPRISE_ID);
        String tokenB = jwtUtil.generateRefreshToken(USER_ID, ENTERPRISE_ID);

        Claims claimsA = jwtUtil.validateAndParse(tokenA);
        Claims claimsB = jwtUtil.validateAndParse(tokenB);

        // then
        assertThat(claimsA.get("jti", String.class))
                .as("jti values must be unique across calls")
                .isNotEqualTo(claimsB.get("jti", String.class));
    }

    // -------------------------------------------------------------------------
    // validateAndParse
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("validateAndParse: valid token returns claims matching original inputs")
    void validateAndParse_validToken_returnsClaims() {
        // given
        String token = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);

        // when
        Claims claims = jwtUtil.validateAndParse(token);

        // then
        assertThat(claims.getSubject()).isEqualTo(USER_ID.toString());
        assertThat(claims.get("enterprise_id", String.class)).isEqualTo(ENTERPRISE_ID.toString());
        assertThat(claims.get("role", String.class)).isEqualTo(ROLE);
        assertThat(claims.getIssuedAt()).isNotNull();
        assertThat(claims.getExpiration()).isNotNull();
    }

    @Test
    @DisplayName("validateAndParse: token expired beyond the 30s skew window throws JwtException")
    void validateAndParse_expiredToken_throwsJwtException() throws Exception {
        // given — build a JwtUtil with NEGATIVE access TTL so generated tokens
        // are issued already-expired. Phase 2 #12 added 30s of clock-skew
        // tolerance to validateAndParse; we need expiry well beyond that
        // window to still trip the rejection. -2 minutes → exp = NOW - 120s,
        // which is 90s past the skew boundary.
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair shortLivedPair = gen.generateKeyPair();

        String privB64 = Base64.getEncoder().encodeToString(shortLivedPair.getPrivate().getEncoded());
        String pubB64  = Base64.getEncoder().encodeToString(shortLivedPair.getPublic().getEncoded());

        JwtUtil shortLivedUtil = new JwtUtil(privB64, pubB64, -2L, 7L);

        String expiredToken = shortLivedUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);

        // then
        assertThatThrownBy(() -> shortLivedUtil.validateAndParse(expiredToken))
                .as("Parsing a token expired beyond the 30s skew window must throw JwtException")
                .isInstanceOf(JwtException.class);
    }

    @Test
    @DisplayName("validateAndParse: token expired within the 30s skew window is still accepted (#12)")
    void validateAndParse_recentlyExpiredWithinSkew_isAccepted() throws Exception {
        // Phase 2 #12 — NTP drift tolerance. A token that expired 5 seconds
        // ago must still validate so a downstream pod with a slightly-behind
        // clock doesn't reject a freshly-rotated token.
        KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
        gen.initialize(2048);
        KeyPair pair = gen.generateKeyPair();

        String privB64 = Base64.getEncoder().encodeToString(pair.getPrivate().getEncoded());
        String pubB64  = Base64.getEncoder().encodeToString(pair.getPublic().getEncoded());

        // Build a token whose exp is 5 seconds in the past — well inside the
        // 30s skew window, so validation should still succeed.
        String tokenExpired5sAgo = io.jsonwebtoken.Jwts.builder()
                .subject(USER_ID.toString())
                .claim("role", ROLE)
                .issuedAt(new java.util.Date(System.currentTimeMillis() - 60_000))
                .expiration(new java.util.Date(System.currentTimeMillis() - 5_000))
                .signWith(pair.getPrivate())
                .compact();

        JwtUtil util = new JwtUtil(privB64, pubB64, 15L, 7L);
        // Should not throw — the 30s skew lets a 5-seconds-ago expiry through.
        util.validateAndParse(tokenExpired5sAgo);
    }

    @Test
    @DisplayName("validateAndParse: token with tampered signature throws JwtException")
    void validateAndParse_tamperedToken_throwsJwtException() {
        // given
        String token = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);

        // Flip one character in the signature segment (last dot-delimited part)
        int lastDot    = token.lastIndexOf('.');
        String header  = token.substring(0, lastDot + 1);
        String sig     = token.substring(lastDot + 1);

        // Replace first character of signature with a different character
        char replacement = (sig.charAt(0) == 'A') ? 'B' : 'A';
        String tamperedToken = header + replacement + sig.substring(1);

        // when / then
        assertThatThrownBy(() -> jwtUtil.validateAndParse(tamperedToken))
                .as("Tampered signature must throw JwtException")
                .isInstanceOf(JwtException.class);
    }

    // -------------------------------------------------------------------------
    // isValid
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("isValid: returns true for a freshly generated valid token")
    void isValid_validToken_returnsTrue() {
        // given
        String token = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);

        // when / then
        assertThat(jwtUtil.isValid(token))
                .as("Fresh token must be valid")
                .isTrue();
    }

    @Test
    @DisplayName("isValid: returns false for a token with a tampered signature")
    void isValid_invalidToken_returnsFalse() {
        // given
        String token  = jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE);
        int lastDot   = token.lastIndexOf('.');
        String header = token.substring(0, lastDot + 1);
        String sig    = token.substring(lastDot + 1);
        char bad      = (sig.charAt(0) == 'A') ? 'B' : 'A';
        String broken = header + bad + sig.substring(1);

        // when / then
        assertThat(jwtUtil.isValid(broken))
                .as("Tampered token must be invalid")
                .isFalse();
    }

    @Test
    @DisplayName("isValid: returns false for blank string and null")
    void isValid_nullOrEmptyToken_returnsFalse() {
        // when / then — empty string
        assertThat(jwtUtil.isValid(""))
                .as("Empty string must be invalid")
                .isFalse();

        // when / then — null
        assertThat(jwtUtil.isValid(null))
                .as("null must be invalid")
                .isFalse();
    }

    // -------------------------------------------------------------------------
    // B3 PR #8 — jti on every token + MFA challenge token
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("generateAccessToken: each call has a unique jti claim (B3 PR #8 replay protection)")
    void generateAccessToken_hasUniqueJti() {
        Claims a = jwtUtil.validateAndParse(jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE));
        Claims b = jwtUtil.validateAndParse(jwtUtil.generateAccessToken(USER_ID, ENTERPRISE_ID, ROLE));

        assertThat(a.get("jti", String.class)).as("access tokens must carry jti").isNotBlank();
        assertThat(a.get("jti", String.class))
                .as("two access tokens must have distinct jti values")
                .isNotEqualTo(b.get("jti", String.class));
    }

    @Test
    @DisplayName("generatePlatformAccessToken: jti present and unique across calls")
    void generatePlatformAccessToken_hasUniqueJti() {
        UUID sessionA = UUID.randomUUID();
        UUID sessionB = UUID.randomUUID();
        Claims a = jwtUtil.validateAndParse(jwtUtil.generatePlatformAccessToken(USER_ID, ROLE, sessionA));
        Claims b = jwtUtil.validateAndParse(jwtUtil.generatePlatformAccessToken(USER_ID, ROLE, sessionB));

        assertThat(a.get("jti", String.class)).isNotBlank();
        assertThat(a.get("jti", String.class)).isNotEqualTo(b.get("jti", String.class));
        assertThat(a.get("token_kind", String.class)).isEqualTo("platform");
    }

    @Test
    @DisplayName("generatePlatformMfaChallengeToken: token_kind=mfa_challenge + challenge_id claim")
    void generatePlatformMfaChallengeToken_carriesChallengeIdClaim() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        long ttlMs       = 5L * 60 * 1000;

        String token = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, ttlMs);
        Claims claims = jwtUtil.validateAndParse(token);

        assertThat(claims.getSubject()).isEqualTo(adminId.toString());
        assertThat(claims.get("challenge_id", String.class)).isEqualTo(challengeId.toString());
        assertThat(claims.get("token_kind",   String.class)).isEqualTo("mfa_challenge");
        assertThat(claims.get("type",         String.class)).isEqualTo("mfa_challenge");
        assertThat(claims.get("jti",          String.class)).isNotBlank();
    }

    @Test
    @DisplayName("generatePlatformMfaChallengeToken: TTL respected within ±2s")
    void generatePlatformMfaChallengeToken_ttlIsHonoured() {
        UUID adminId     = UUID.randomUUID();
        UUID challengeId = UUID.randomUUID();
        long ttlMs       = 5L * 60 * 1000;     // 5 minutes

        String token = jwtUtil.generatePlatformMfaChallengeToken(adminId, challengeId, ttlMs);
        Claims claims = jwtUtil.validateAndParse(token);

        long lifetime = claims.getExpiration().getTime() - claims.getIssuedAt().getTime();
        assertThat(lifetime)
                .as("challenge token lifetime must be within 2 seconds of the requested TTL")
                .isBetween(ttlMs - 2000, ttlMs + 2000);
    }
}
