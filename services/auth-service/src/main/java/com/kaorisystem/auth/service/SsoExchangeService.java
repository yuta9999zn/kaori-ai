package com.kaorisystem.auth.service;

import com.kaorisystem.auth.dto.AuthDtos.LoginResponse;
import com.kaorisystem.auth.dto.AuthDtos.SsoExchangeInfoResponse;
import com.kaorisystem.auth.model.User;
import com.kaorisystem.auth.repository.UserRepository;
import com.kaorisystem.auth.security.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.HttpClientErrorException;
import org.springframework.web.client.RestClient;
import org.springframework.web.client.RestClientException;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.TimeUnit;

/**
 * P2-AUTH-001 SSO exchange service.
 *
 * <p>Translates the one-shot {@code sso_code} from ai-orchestrator's
 * SSO callback into a real RS256 JWT. The flow keeps the private
 * signing key inside auth-service (per the existing security boundary
 * — JwtUtil holds the only RSA private key).
 *
 * <p>Two-hop handshake:
 * <ol>
 *   <li>FE POSTs {@code /api/v1/auth/sso/exchange} with the sso_code.
 *   <li>This service calls ai-orchestrator's INTERNAL endpoint
 *       {@code POST /p2/auth/sso/exchange-info} with the shared
 *       {@code KAORI_INTERNAL_SVC_TOKEN} header. ai-orchestrator
 *       validates + marks consumed + returns the matched user.
 *   <li>This service loads the user, mints an RS256 JWT identical
 *       to the password-login path, returns to FE.
 * </ol>
 *
 * <p>See {@code docs/specs/SSO_AUTH_SERVICE_CONTRACT.md} for the full
 * protocol.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class SsoExchangeService {

    private final UserRepository userRepository;
    private final JwtUtil jwtUtil;
    private final StringRedisTemplate redis;
    private final RestClient.Builder restClientBuilder;

    @Value("${kaori.orchestrator-base-url:http://ai-orchestrator:8093}")
    private String orchestratorBaseUrl;

    @Value("${kaori.internal-svc-token:}")
    private String internalSvcToken;

    /**
     * Thrown when ai-orchestrator returns 410 (code already consumed or expired)
     * or 404 (unknown code). Mapped to 410 / 404 in the controller.
     */
    public static class SsoExchangeError extends RuntimeException {
        private final int status;
        public SsoExchangeError(int status, String msg) {
            super(msg);
            this.status = status;
        }
        public int getStatus() { return status; }
    }

    @Transactional
    public LoginResponse exchange(String ssoCode) {
        if (internalSvcToken == null || internalSvcToken.isBlank()) {
            throw new SsoExchangeError(
                503,
                "KAORI_INTERNAL_SVC_TOKEN not configured on auth-service"
            );
        }
        if (ssoCode == null || ssoCode.isBlank()) {
            throw new SsoExchangeError(400, "sso_code is required");
        }

        SsoExchangeInfoResponse info = callExchangeInfo(ssoCode);

        UUID userId;
        try {
            userId = UUID.fromString(info.getUserId());
        } catch (IllegalArgumentException e) {
            throw new SsoExchangeError(
                502,
                "ai-orchestrator returned malformed user_id"
            );
        }

        User user = userRepository.findById(userId).orElseThrow(() -> new SsoExchangeError(
            404,
            "SSO matched user not found in auth-service"
        ));
        if (!"active".equals(user.getStatus())) {
            throw new SsoExchangeError(403, "Account is inactive");
        }

        userRepository.updateLastLogin(user.getUserId(), Instant.now());

        String accessToken = jwtUtil.generateAccessToken(
            user.getUserId(), user.getEnterpriseId(), user.getRole());
        String refreshToken = jwtUtil.generateRefreshToken(
            user.getUserId(), user.getEnterpriseId());

        // Store refresh token in Redis — same shape as password login.
        redis.opsForValue().set(
            "refresh:" + user.getUserId(), refreshToken,
            jwtUtil.getRefreshTokenTtlMs(), TimeUnit.MILLISECONDS
        );

        log.info("sso.exchange.success user_id={} enterprise_id={} provider={}",
                  user.getUserId(), user.getEnterpriseId(), info.getProvider());

        LoginResponse resp = new LoginResponse();
        resp.setAccessToken(accessToken);
        resp.setRefreshToken(refreshToken);
        resp.setRole(user.getRole());
        resp.setEnterpriseId(user.getEnterpriseId().toString());
        resp.setUserId(user.getUserId().toString());
        // SSO logins never carry the must-change-password flag — these
        // accounts authenticated via the provider's own credentials,
        // not Kaori's initial-password flow.
        Boolean mustChange = user.getMustChangePassword();
        resp.setMustChangePassword(Boolean.FALSE);
        if (Boolean.TRUE.equals(mustChange)) {
            // Force-clear stale invite flag — SSO success implies the user
            // has a real account-of-record on the provider side. Keeping
            // the flag would create a UX dead-end (forced-change page asks
            // for current password the SSO user never set).
            user.setMustChangePassword(Boolean.FALSE);
            userRepository.save(user);
        }
        return resp;
    }

    private SsoExchangeInfoResponse callExchangeInfo(String ssoCode) {
        RestClient client = restClientBuilder.build();
        try {
            return client.post()
                .uri(orchestratorBaseUrl + "/p2/auth/sso/exchange-info")
                .header("X-Internal-Service-Token", internalSvcToken)
                .body(Map.of("sso_code", ssoCode))
                .retrieve()
                .body(SsoExchangeInfoResponse.class);
        } catch (HttpClientErrorException.NotFound e) {
            throw new SsoExchangeError(404, "Unknown SSO exchange code");
        } catch (HttpClientErrorException.Gone e) {
            throw new SsoExchangeError(410, "SSO exchange code already consumed or expired");
        } catch (HttpClientErrorException.Unauthorized e) {
            log.error("sso.exchange.internal_token_rejected — token mismatch with ai-orchestrator");
            throw new SsoExchangeError(503, "Internal service token misconfigured");
        } catch (HttpClientErrorException e) {
            log.error("sso.exchange.4xx status={} body={}",
                       e.getStatusCode(), e.getResponseBodyAsString());
            throw new SsoExchangeError(502, "ai-orchestrator rejected exchange-info call");
        } catch (RestClientException e) {
            log.error("sso.exchange.network_error", e);
            throw new SsoExchangeError(502, "ai-orchestrator unreachable: " + e.getMessage());
        }
    }
}
