package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.dto.AuthDtos.ErrorResponse;
import com.kaorisystem.auth.dto.AuthDtos.LoginResponse;
import com.kaorisystem.auth.dto.AuthDtos.SsoExchangeRequest;
import com.kaorisystem.auth.service.SsoExchangeService;
import com.kaorisystem.auth.service.SsoExchangeService.SsoExchangeError;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * P2-AUTH-001 SSO — FE-facing exchange endpoint.
 *
 * <p>Sits next to {@link AuthController}. FE POSTs the one-shot
 * {@code sso_code} (returned by ai-orchestrator's
 * {@code /p2/auth/sso/{provider}/callback} 302 redirect) and gets
 * back the same {@link LoginResponse} shape as password login. From
 * the FE's perspective, SSO is just a different way to acquire a
 * normal Kaori JWT.
 *
 * <p>See {@code docs/specs/SSO_AUTH_SERVICE_CONTRACT.md} for the
 * end-to-end flow.
 */
@RestController
@RequestMapping("/auth/sso")
@RequiredArgsConstructor
@Slf4j
public class SsoController {

    private final SsoExchangeService ssoExchangeService;

    @PostMapping("/exchange")
    public ResponseEntity<?> exchange(@Valid @RequestBody SsoExchangeRequest req) {
        try {
            LoginResponse resp = ssoExchangeService.exchange(req.getSsoCode());
            return ResponseEntity.ok(resp);
        } catch (SsoExchangeError e) {
            return ResponseEntity.status(e.getStatus())
                .body(new ErrorResponse(e.getStatus(), "SSO_EXCHANGE_FAILED", e.getMessage()));
        }
    }
}
