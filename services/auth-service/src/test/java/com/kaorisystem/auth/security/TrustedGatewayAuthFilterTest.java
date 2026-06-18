package com.kaorisystem.auth.security;

import com.kaorisystem.auth.service.SessionValidator;
import jakarta.servlet.FilterChain;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;

import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@DisplayName("TrustedGatewayAuthFilter — gateway-trust authentication mapping")
class TrustedGatewayAuthFilterTest {

    private TrustedGatewayAuthFilter filter;
    private MockHttpServletRequest request;
    private MockHttpServletResponse response;
    private FilterChain chain;
    private ObjectProvider<SessionValidator> validatorProvider;
    private ObjectProvider<JwtUtil>          jwtProvider;

    @BeforeEach
    void setUp() {
        // Default providers return null from getIfAvailable() — preserves the
        // pre-3.1.a behaviour for tests that don't supply session_id.
        @SuppressWarnings("unchecked")
        ObjectProvider<SessionValidator> sv = mock(ObjectProvider.class);
        validatorProvider = sv;
        @SuppressWarnings("unchecked")
        ObjectProvider<JwtUtil> jp = mock(ObjectProvider.class);
        jwtProvider = jp;
        when(validatorProvider.getIfAvailable()).thenReturn(null);
        when(jwtProvider.getIfAvailable()).thenReturn(null);

        filter = new TrustedGatewayAuthFilter(validatorProvider, jwtProvider);
        request = new MockHttpServletRequest();
        response = new MockHttpServletResponse();
        chain = mock(FilterChain.class);
        SecurityContextHolder.clearContext();
    }

    @AfterEach
    void tearDown() {
        SecurityContextHolder.clearContext();
    }

    // ─── Happy path ──────────────────────────────────────────────────────

    @Test
    @DisplayName("populates SecurityContext when X-User-ID + X-User-Role are present")
    void buildsAuthenticationFromHeaders() throws Exception {
        String userId = UUID.randomUUID().toString();
        String enterpriseId = UUID.randomUUID().toString();
        request.addHeader("X-User-ID", userId);
        request.addHeader("X-Enterprise-ID", enterpriseId);
        request.addHeader("X-User-Role", "MANAGER");

        filter.doFilter(request, response, chain);

        Authentication auth = SecurityContextHolder.getContext().getAuthentication();
        assertThat(auth).isNotNull();
        assertThat(auth.getPrincipal()).isEqualTo(userId);
        assertThat(auth.getDetails()).isEqualTo(enterpriseId);
        assertThat(auth.getAuthorities())
                .extracting(Object::toString)
                .containsExactly("ROLE_MANAGER");
        verify(chain).doFilter(request, response);
    }

    @Test
    @DisplayName("ROLE_ prefix is added so Spring Security hasRole(\"X\") matches")
    void rolePrefixIsAddedToAuthority() throws Exception {
        request.addHeader("X-User-ID", "u1");
        request.addHeader("X-User-Role", "SUPER_ADMIN");

        filter.doFilter(request, response, chain);

        // hasAnyRole("SUPER_ADMIN") resolves to authority "ROLE_SUPER_ADMIN"
        assertThat(SecurityContextHolder.getContext().getAuthentication().getAuthorities())
                .extracting(Object::toString)
                .containsExactly("ROLE_SUPER_ADMIN");
    }

    @Test
    @DisplayName("trims whitespace around the role header value")
    void trimsRoleHeader() throws Exception {
        request.addHeader("X-User-ID", "u1");
        request.addHeader("X-User-Role", "  ADMIN  ");

        filter.doFilter(request, response, chain);

        assertThat(SecurityContextHolder.getContext().getAuthentication().getAuthorities())
                .extracting(Object::toString)
                .containsExactly("ROLE_ADMIN");
    }

    // ─── Skip cases — no Authentication populated ────────────────────────

    @Test
    @DisplayName("no headers present — context stays empty, chain still continues")
    void noHeadersLeavesContextEmpty() throws Exception {
        filter.doFilter(request, response, chain);

        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        verify(chain).doFilter(request, response);
    }

    @Test
    @DisplayName("X-User-ID without X-User-Role — context stays empty (incomplete)")
    void userIdWithoutRoleSkips() throws Exception {
        request.addHeader("X-User-ID", "u1");
        // intentionally no X-User-Role

        filter.doFilter(request, response, chain);

        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        verify(chain).doFilter(request, response);
    }

    @Test
    @DisplayName("X-User-Role without X-User-ID — context stays empty (incomplete)")
    void roleWithoutUserIdSkips() throws Exception {
        request.addHeader("X-User-Role", "ADMIN");

        filter.doFilter(request, response, chain);

        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        verify(chain).doFilter(request, response);
    }

    @Test
    @DisplayName("blank header values are treated as missing")
    void blankHeadersSkip() throws Exception {
        request.addHeader("X-User-ID", "");
        request.addHeader("X-User-Role", "   ");

        filter.doFilter(request, response, chain);

        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
        verify(chain).doFilter(request, response);
    }

    // ─── Filter never blocks the chain when no session is involved ──────

    @Test
    @DisplayName("chain.doFilter continues when no X-Session-Id is resolvable")
    void chainContinuesWithoutSession() throws Exception {
        // No headers
        filter.doFilter(request, response, chain);
        // With headers but no X-Session-Id and no Bearer (validator skipped)
        request.addHeader("X-User-ID", "u1");
        request.addHeader("X-User-Role", "MANAGER");
        filter.doFilter(request, response, chain);

        verify(chain, org.mockito.Mockito.times(2)).doFilter(request, response);
    }

    // ─── 3.1.a — session validation + 401 short-circuit ─────────────────

    @Test
    @DisplayName("X-Session-Id present + validator says VALID → chain continues, auth set")
    void sessionValid_chainContinues() throws Exception {
        UUID sessionId = UUID.randomUUID();
        com.kaorisystem.auth.service.SessionValidator validator =
                mock(com.kaorisystem.auth.service.SessionValidator.class);
        when(validatorProvider.getIfAvailable()).thenReturn(validator);
        when(validator.validateAndTouch(org.mockito.ArgumentMatchers.eq(sessionId),
                                         org.mockito.ArgumentMatchers.any()))
                .thenReturn(com.kaorisystem.auth.service.SessionValidator.Result.valid());

        request.addHeader("X-User-ID",     UUID.randomUUID().toString());
        request.addHeader("X-User-Role",   "ADMIN");
        request.addHeader("X-Session-Id",  sessionId.toString());

        filter.doFilter(request, response, chain);

        verify(chain).doFilter(request, response);
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNotNull();
    }

    @Test
    @DisplayName("X-Session-Id + IDLE_EXPIRED → 401 application/problem+json, chain NOT continued")
    void sessionIdleExpired_writes401() throws Exception {
        UUID sessionId = UUID.randomUUID();
        com.kaorisystem.auth.service.SessionValidator validator =
                mock(com.kaorisystem.auth.service.SessionValidator.class);
        when(validatorProvider.getIfAvailable()).thenReturn(validator);
        when(validator.validateAndTouch(org.mockito.ArgumentMatchers.eq(sessionId),
                                         org.mockito.ArgumentMatchers.any()))
                .thenReturn(com.kaorisystem.auth.service.SessionValidator.Result.idleExpired());

        request.addHeader("X-User-ID",     UUID.randomUUID().toString());
        request.addHeader("X-User-Role",   "ADMIN");
        request.addHeader("X-Session-Id",  sessionId.toString());

        filter.doFilter(request, response, chain);

        org.mockito.Mockito.verifyNoInteractions(chain);
        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(response.getContentType()).contains("application/problem+json");
        String body = response.getContentAsString();
        assertThat(body)
                .contains("\"title\":\"Session expired (idle)\"")
                .contains("\"status\":401")
                .contains("\"reason\":\"idle_timeout\"");
        // SecurityContext not populated when chain is short-circuited
        assertThat(SecurityContextHolder.getContext().getAuthentication()).isNull();
    }

    @Test
    @DisplayName("X-Session-Id + ABSOLUTE_EXPIRED → 401 with absolute_timeout reason")
    void sessionAbsoluteExpired_writes401() throws Exception {
        UUID sessionId = UUID.randomUUID();
        com.kaorisystem.auth.service.SessionValidator validator =
                mock(com.kaorisystem.auth.service.SessionValidator.class);
        when(validatorProvider.getIfAvailable()).thenReturn(validator);
        when(validator.validateAndTouch(org.mockito.ArgumentMatchers.eq(sessionId),
                                         org.mockito.ArgumentMatchers.any()))
                .thenReturn(com.kaorisystem.auth.service.SessionValidator.Result.absoluteExpired());

        request.addHeader("X-User-ID",     UUID.randomUUID().toString());
        request.addHeader("X-User-Role",   "ADMIN");
        request.addHeader("X-Session-Id",  sessionId.toString());

        filter.doFilter(request, response, chain);

        assertThat(response.getStatus()).isEqualTo(401);
        assertThat(response.getContentAsString())
                .contains("\"title\":\"Session expired (max duration)\"")
                .contains("\"reason\":\"absolute_timeout\"");
    }

    @Test
    @DisplayName("invalid X-Session-Id UUID + no Bearer → falls through to no-validation path")
    void invalidSessionHeader_fallsThrough() throws Exception {
        request.addHeader("X-User-ID",    UUID.randomUUID().toString());
        request.addHeader("X-User-Role",  "ADMIN");
        request.addHeader("X-Session-Id", "not-a-uuid");
        // validatorProvider returns null in setUp() — validation step is skipped

        filter.doFilter(request, response, chain);

        verify(chain).doFilter(request, response);
        assertThat(response.getStatus()).isEqualTo(200);  // default — no 401 written
    }
}
