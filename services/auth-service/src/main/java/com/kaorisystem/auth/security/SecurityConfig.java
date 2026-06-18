package com.kaorisystem.auth.security;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configurers.AbstractHttpConfigurer;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.security.web.authentication.UsernamePasswordAuthenticationFilter;

@Configuration
@EnableWebSecurity
@RequiredArgsConstructor
public class SecurityConfig {

    private final TrustedGatewayAuthFilter trustedGatewayAuthFilter;

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        http
            .csrf(AbstractHttpConfigurer::disable)
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            // Run the gateway-trust filter so that, by the time the
            // authorisation matchers below evaluate, SecurityContextHolder
            // has an Authentication populated from X-User-* headers.
            .addFilterBefore(trustedGatewayAuthFilter,
                             UsernamePasswordAuthenticationFilter.class)
            .authorizeHttpRequests(auth -> auth
                // Public endpoints — gateway forwards without JWT.
                .requestMatchers("/auth/**",
                                 "/actuator/health",
                                 "/actuator/info",
                                 // Sprint 6.5 — OpenAPI / Swagger UI for the FE
                                 // codegen pipeline. Internal-network only in
                                 // production (rely on gateway routing + network
                                 // policy); permitAll so dev workflow is friction-
                                 // free. Production deployment must NOT expose
                                 // these via the public ingress.
                                 "/v3/api-docs/**",
                                 "/swagger-ui/**",
                                 "/swagger-ui.html").permitAll()

                // Platform admin endpoints — restricted to staff roles.
                // SUPER_ADMIN: full power; ADMIN: ops; SUPPORT: read.
                .requestMatchers("/api/v1/platform/**")
                    .hasAnyRole("SUPER_ADMIN", "ADMIN", "SUPPORT")

                // Enterprise-scoped endpoints — any authenticated tenant role.
                // /api/v1/enterprises/** (plural) covers /enterprises/me/* used
                // by F-016 settings; the singular form stays for legacy paths.
                .requestMatchers("/api/v1/enterprise/**",
                                 "/api/v1/enterprises/**",
                                 "/api/v1/users/**",
                                 "/api/v1/workspaces/**",
                                 "/api/v1/settings/**")
                    .hasAnyRole("MANAGER", "OPERATOR", "ANALYST", "VIEWER",
                                "SUPER_ADMIN", "ADMIN", "SUPPORT")

                // Anything else: deny by default. Previously this was
                // anyRequest().authenticated() with no auth provider, which
                // returned 403 to /api/v1/platform/* in production
                // (ARCHITECTURE_REVIEW.md §2.1). Now those paths are
                // explicitly authorised above; everything else is rejected.
                .anyRequest().denyAll()
            );
        return http.build();
    }

    @Bean
    public PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder(12);
    }
}
