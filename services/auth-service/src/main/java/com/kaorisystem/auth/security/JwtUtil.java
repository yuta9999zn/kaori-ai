package com.kaorisystem.auth.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import java.util.Base64;
import java.util.Date;
import java.util.Map;
import java.util.UUID;

@Component
@Slf4j
public class JwtUtil {

    private final PrivateKey privateKey;
    private final PublicKey publicKey;
    private final long accessTokenTtlMs;
    private final long refreshTokenTtlMs;

    public JwtUtil(
            @Value("${jwt.private-key}") String privateKeyBase64,
            @Value("${jwt.public-key}") String publicKeyBase64,
            @Value("${jwt.access-token-ttl-minutes:15}") long accessTtlMin,
            @Value("${jwt.refresh-token-ttl-days:7}") long refreshTtlDays) {
        try {
            KeyFactory kf = KeyFactory.getInstance("RSA");
            byte[] privBytes = Base64.getDecoder().decode(privateKeyBase64.replaceAll("\\s", ""));
            byte[] pubBytes = Base64.getDecoder().decode(publicKeyBase64.replaceAll("\\s", ""));
            this.privateKey = kf.generatePrivate(new PKCS8EncodedKeySpec(privBytes));
            this.publicKey = kf.generatePublic(new X509EncodedKeySpec(pubBytes));
        } catch (Exception e) {
            throw new IllegalStateException("Failed to load JWT keys: " + e.getMessage(), e);
        }
        this.accessTokenTtlMs = accessTtlMin * 60 * 1000L;
        this.refreshTokenTtlMs = refreshTtlDays * 24 * 60 * 60 * 1000L;
    }

    public String generateAccessToken(UUID userId, UUID enterpriseId, String role) {
        return Jwts.builder()
                .subject(userId.toString())
                .claim("enterprise_id", enterpriseId.toString())
                .claim("role", role)
                .claim("type", "access")
                .claim("token_kind", "enterprise")
                .claim("jti", UUID.randomUUID().toString())
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + accessTokenTtlMs))
                .signWith(privateKey)
                .compact();
    }

    public String generateRefreshToken(UUID userId, UUID enterpriseId) {
        return Jwts.builder()
                .subject(userId.toString())
                .claim("enterprise_id", enterpriseId.toString())
                .claim("type", "refresh")
                .claim("token_kind", "enterprise")
                .claim("jti", UUID.randomUUID().toString())
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + refreshTokenTtlMs))
                .signWith(privateKey)
                .compact();
    }

    /**
     * Platform admin access token. Carries {@code session_id} (so the gateway
     * can forward {@code X-Session-Id}) and {@code token_kind=platform} so
     * downstream filters and the logout flow can distinguish from enterprise
     * tokens. No {@code enterprise_id} claim — platform admins don't belong to
     * one.
     */
    public String generatePlatformAccessToken(UUID adminId, String role, UUID sessionId) {
        return Jwts.builder()
                .subject(adminId.toString())
                .claim("session_id", sessionId.toString())
                .claim("role", role)
                .claim("type", "access")
                .claim("token_kind", "platform")
                .claim("jti", UUID.randomUUID().toString())
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + accessTokenTtlMs))
                .signWith(privateKey)
                .compact();
    }

    /** Platform admin refresh token. Same session_id as the access token it pairs with. */
    public String generatePlatformRefreshToken(UUID adminId, UUID sessionId) {
        return Jwts.builder()
                .subject(adminId.toString())
                .claim("session_id", sessionId.toString())
                .claim("type", "refresh")
                .claim("token_kind", "platform")
                .claim("jti", UUID.randomUUID().toString())
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + refreshTokenTtlMs))
                .signWith(privateKey)
                .compact();
    }

    /**
     * B3 PR #8 — short-lived MFA challenge token issued at /auth/platform/login
     * when {@code admin.mfa_enabled=true}. The 2-step gate exchange this for a
     * real session at /auth/platform/mfa/verify.
     *
     * <p>{@code token_kind=mfa_challenge} so the gateway's PUBLIC_PATHS allow-list
     * for /auth/platform/mfa/verify is authoritative — no {@code role} claim
     * is included because the holder hasn't completed login yet. The
     * {@code challenge_id} claim ties the JWT to the {@code mfa_challenges}
     * row so the verify path can look up by hash AND cross-check that the
     * subject matches.
     *
     * <p>TTL is short (default 5 minutes via the {@code ttlMs} param) — long
     * enough for the user to fish their phone out, short enough that a
     * leaked challenge token is useless within a coffee break.
     */
    public String generatePlatformMfaChallengeToken(UUID adminId, UUID challengeId, long ttlMs) {
        return Jwts.builder()
                .subject(adminId.toString())
                .claim("challenge_id", challengeId.toString())
                .claim("type", "mfa_challenge")
                .claim("token_kind", "mfa_challenge")
                .claim("jti", UUID.randomUUID().toString())
                .issuedAt(new Date())
                .expiration(new Date(System.currentTimeMillis() + ttlMs))
                .signWith(privateKey)
                .compact();
    }

    public long getAccessTokenTtlMs()  { return accessTokenTtlMs;  }

    /**
     * 30 seconds of leeway on iat/exp/nbf — Phase 2 spec, error-handling
     * group #12 (clock skew). NTP drift between pods + auth-service issuing
     * a token + gateway validating it can be a few seconds; without leeway,
     * a freshly-minted token can fail validation on a downstream pod whose
     * clock is half a second behind. RFC 7519 §4.1.4 explicitly suggests a
     * "small leeway, usually no more than a few minutes". 30s matches the
     * TOTP step size already in use by the MFA flow.
     */
    private static final long CLOCK_SKEW_SECONDS = 30L;

    public Claims validateAndParse(String token) {
        return Jwts.parser()
                .verifyWith(publicKey)
                .clockSkewSeconds(CLOCK_SKEW_SECONDS)
                .build()
                .parseSignedClaims(token)
                .getPayload();
    }

    public boolean isValid(String token) {
        try {
            validateAndParse(token);
            return true;
        } catch (JwtException | IllegalArgumentException e) {
            return false;
        }
    }

    public long getRefreshTokenTtlMs() {
        return refreshTokenTtlMs;
    }
}
