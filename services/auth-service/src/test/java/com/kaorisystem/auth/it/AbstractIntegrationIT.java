package com.kaorisystem.auth.it;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
import org.junit.jupiter.api.BeforeEach;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Import;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.data.redis.core.ValueOperations;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.security.web.FilterChainProxy;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.context.WebApplicationContext;
import org.testcontainers.containers.PostgreSQLContainer;
import org.testcontainers.utility.MountableFile;

import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;

import java.nio.file.Files;
import java.nio.file.Path;
import java.security.KeyPair;
import java.security.KeyPairGenerator;
import java.util.Base64;
import java.util.Comparator;
import java.util.stream.Stream;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

/**
 * Base class for end-to-end integration tests.
 *
 * <p>Boots the full Spring application context against a real PostgreSQL.
 * Two backends are supported:
 *
 * <ol>
 *   <li><strong>Testcontainers (preferred):</strong> spins up a fresh
 *       {@code pgvector/pgvector:pg15} container and copies migrations
 *       001–011 into {@code /docker-entrypoint-initdb.d}. Selected by default.
 *   </li>
 *   <li><strong>External Postgres:</strong> connects to an already-running
 *       Postgres at {@code localhost:5432} (the docker-compose stack).
 *       Selected when env var {@code KAORI_IT_USE_LOCAL_DB=1} OR when
 *       Testcontainers cannot reach Docker. The user must have already
 *       run migrations 001–011 against this DB.
 *   </li>
 * </ol>
 *
 * <p>Why the fallback exists: Docker Desktop with "containerd image store"
 * enabled (Settings → General) returns HTTP 400 to Testcontainers' Docker
 * client probes. Until that toggle is disabled, TC cannot provision
 * containers. The fallback lets the IT suite run today against the same
 * Postgres used by the running services, so the tests still exercise real
 * SQL, real JPA, real migrations.
 *
 * <p>Redis + Mail are mocked — the F-008/F-010 endpoints under test do not
 * exercise auth login or email content; we only verify the side-effect
 * (mailSender.send was called).
 */
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.MOCK)
@Import(AbstractIntegrationIT.IntegrationTestBeans.class)
public abstract class AbstractIntegrationIT {

    /**
     * Default trusted-gateway headers attached to every IT request. Mirrors
     * what api-gateway forwards to auth-service after JWT validation. Without
     * these, SecurityConfig's role check on /api/v1/platform/** returns 403.
     */
    protected static final String IT_USER_ID    = "00000000-0000-0000-0000-000000000001";
    protected static final String IT_USER_ROLE  = "ADMIN";
    protected static final String IT_USER_EMAIL = "it-admin@kaori.io";

    // -------------------------------------------------------------------------
    // Backend selection: Testcontainers vs. external compose Postgres
    // -------------------------------------------------------------------------

    private static final boolean USE_LOCAL_DB =
            "1".equals(System.getenv("KAORI_IT_USE_LOCAL_DB"))
            || "true".equalsIgnoreCase(System.getenv("KAORI_IT_USE_LOCAL_DB"));

    /** Set on first IT init — points at whichever backend is in use. */
    private static String JDBC_URL;
    private static String DB_USER;
    private static String DB_PASS;

    private static PostgreSQLContainer<?> CONTAINER;

    static {
        // Two paths, both EXPLICIT — there is no silent fallback. CI must
        // reflect real integration behaviour (CI = Testcontainers; local-dev
        // workaround = explicit env var), so a Docker hiccup never quietly
        // re-routes tests to a different Postgres.
        //
        //   1. KAORI_IT_USE_LOCAL_DB=1 (or "true") — opt in to a pre-running
        //      Postgres at localhost:5433. Useful when Docker Desktop's
        //      containerd image-store mode breaks Testcontainers (TC's
        //      Docker-client probe gets HTTP 400 from /info). Operator must
        //      have applied migrations 001-NNN to that DB beforehand.
        //
        //   2. Default — Testcontainers spins a fresh pgvector/pgvector:pg15
        //      and copies the migrations dir into docker-entrypoint-initdb.d.
        //      If TC cannot start, the JVM crashes here and ALL ITs error
        //      with the underlying exception — exactly what we want CI to
        //      surface. Previously a try/catch routed to local-DB which
        //      doesn't exist in CI, masking the real cause behind 30+
        //      "connection refused to localhost:5433" messages.
        if (USE_LOCAL_DB) {
            useLocalDocker();
        } else {
            useTestcontainers();
        }
    }

    private static void useTestcontainers() {
        CONTAINER = new PostgreSQLContainer<>("pgvector/pgvector:pg15")
                .withDatabaseName("kaori")
                .withUsername("kaori")
                .withPassword("kaori_dev_password");
        copyMigrations(CONTAINER);
        CONTAINER.start();
        JDBC_URL = CONTAINER.getJdbcUrl();
        DB_USER  = CONTAINER.getUsername();
        DB_PASS  = CONTAINER.getPassword();
    }

    private static void useLocalDocker() {
        // Defaults target the dedicated IT Postgres container on port 5433.
        // Port 5432 is shadowed on Windows by a native postgres.exe service;
        // 5433 is reserved for the IT container so the two never collide.
        // Bring up: docker run --rm -d --name kaori-it-postgres \
        //   -e POSTGRES_USER=kaori -e POSTGRES_PASSWORD=kaori_dev_password \
        //   -e POSTGRES_DB=kaori -p 5433:5432 \
        //   -v "/d/Kaori System/infrastructure/postgres/migrations:/docker-entrypoint-initdb.d:ro" \
        //   pgvector/pgvector:pg15
        JDBC_URL = System.getenv().getOrDefault(
                "KAORI_IT_DB_URL", "jdbc:postgresql://localhost:5433/kaori");
        DB_USER  = System.getenv().getOrDefault(
                "KAORI_IT_DB_USER", "kaori");
        DB_PASS  = System.getenv().getOrDefault(
                "KAORI_IT_DB_PASS", "kaori_dev_password");
    }

    /**
     * Copy {@code NNN_*.sql} files 001-014 from infrastructure/postgres/migrations/
     * into the container's init dir so PostgreSQL runs them in order on first boot.
     *
     * <p>Only 001-014 because that matches the production baseline contract
     * (see application.yml: flyway.baseline-version=14). PG init handles the
     * pre-baseline migrations; Flyway then runs 015+ against the resulting
     * schema on Spring Boot startup. Copying ALL migrations into init would
     * cause Flyway to re-run 015+ a second time, triggering duplicate-object
     * errors (ADD CONSTRAINT without IF NOT EXISTS, etc.).
     *
     * <p>Only used in TC mode; in local-db mode the migrations are already
     * applied by the operator.
     */
    private static final int PRE_FLYWAY_BASELINE_VERSION = 14;

    private static void copyMigrations(PostgreSQLContainer<?> pg) {
        Path migrations = Path.of("..", "..", "infrastructure", "postgres", "migrations")
                .toAbsolutePath().normalize();
        if (!Files.isDirectory(migrations)) {
            throw new IllegalStateException(
                    "Migrations dir not found at " + migrations
                            + " — IT must be run from the auth-service module dir");
        }
        try (Stream<Path> files = Files.list(migrations)) {
            files.filter(p -> p.getFileName().toString().endsWith(".sql"))
                 .filter(AbstractIntegrationIT::isPreBaselineMigration)
                 .sorted(Comparator.comparing(p -> p.getFileName().toString()))
                 .forEach(p -> pg.withCopyFileToContainer(
                         MountableFile.forHostPath(p),
                         "/docker-entrypoint-initdb.d/" + p.getFileName()));
        } catch (Exception e) {
            throw new RuntimeException("Failed to enumerate migrations: " + e.getMessage(), e);
        }
    }

    /**
     * True for {@code NNN_*.sql} files where NNN ≤ baseline-version (14).
     * Files that don't match the NNN_ prefix are skipped (safer than copying
     * unrecognised files into init).
     */
    private static boolean isPreBaselineMigration(Path p) {
        String name = p.getFileName().toString();
        if (name.length() < 4 || name.charAt(3) != '_') return false;
        try {
            int n = Integer.parseInt(name.substring(0, 3));
            return n <= PRE_FLYWAY_BASELINE_VERSION;
        } catch (NumberFormatException ex) {
            return false;
        }
    }

    // -------------------------------------------------------------------------
    // Property wiring — JDBC URL, JWT keys, Redis/Mail off
    // -------------------------------------------------------------------------

    private static final String JWT_PRIVATE_KEY_B64;
    private static final String JWT_PUBLIC_KEY_B64;

    static {
        try {
            KeyPairGenerator gen = KeyPairGenerator.getInstance("RSA");
            gen.initialize(2048);
            KeyPair pair = gen.generateKeyPair();
            JWT_PRIVATE_KEY_B64 = Base64.getEncoder().encodeToString(pair.getPrivate().getEncoded());
            JWT_PUBLIC_KEY_B64  = Base64.getEncoder().encodeToString(pair.getPublic().getEncoded());
        } catch (Exception e) {
            throw new IllegalStateException("Failed to generate test JWT keys", e);
        }
    }

    @DynamicPropertySource
    static void registerProperties(DynamicPropertyRegistry registry) {
        registry.add("spring.datasource.url",      () -> JDBC_URL);
        registry.add("spring.datasource.username", () -> DB_USER);
        registry.add("spring.datasource.password", () -> DB_PASS);
        registry.add("spring.jpa.hibernate.ddl-auto", () -> "validate");

        // Disable Redis + Mail autoconfig — stub beans below
        registry.add("spring.autoconfigure.exclude", () -> String.join(",",
                "org.springframework.boot.autoconfigure.data.redis.RedisAutoConfiguration",
                "org.springframework.boot.autoconfigure.data.redis.RedisRepositoriesAutoConfiguration",
                "org.springframework.boot.autoconfigure.mail.MailSenderAutoConfiguration"));

        registry.add("jwt.private-key", () -> JWT_PRIVATE_KEY_B64);
        registry.add("jwt.public-key",  () -> JWT_PUBLIC_KEY_B64);
        registry.add("kaori.frontend-url", () -> "http://test.local");
    }

    // -------------------------------------------------------------------------
    // Stub beans for excluded auto-configuration
    // -------------------------------------------------------------------------

    @TestConfiguration(proxyBeanMethods = false)
    static class IntegrationTestBeans {

        @Bean
        public StringRedisTemplate stringRedisTemplate() {
            StringRedisTemplate t = mock(StringRedisTemplate.class);
            when(t.opsForValue()).thenReturn(mock(ValueOperations.class));
            return t;
        }

        @Bean
        public JavaMailSender javaMailSender() {
            JavaMailSender m = mock(JavaMailSender.class);
            when(m.createMimeMessage()).thenReturn(new MimeMessage((Session) null));
            return m;
        }

        @Bean
        public RedisConnectionFactory redisConnectionFactory() {
            return mock(RedisConnectionFactory.class);
        }
    }

    @Autowired private WebApplicationContext webContext;
    @Autowired private FilterChainProxy       springSecurityFilter;
    @Autowired protected ObjectMapper         objectMapper;
    @Autowired private org.springframework.jdbc.core.JdbcTemplate jdbc;

    /**
     * Built fresh per test so the Spring Security filter chain (and the
     * trusted-gateway filter inside it) is wired in. Default request headers
     * authenticate every request as ADMIN — individual tests can override
     * by passing different headers if they want to test 403 paths.
     */
    protected MockMvc mockMvc;

    @BeforeEach
    void buildMockMvc() {
        mockMvc = MockMvcBuilders
                .webAppContextSetup(webContext)
                .addFilters(springSecurityFilter)
                .defaultRequest(get("/")
                        .header("X-User-ID",       IT_USER_ID)
                        .header("X-User-Role",     IT_USER_ROLE)
                        .header("X-User-Email",    IT_USER_EMAIL)
                        .header("X-Enterprise-ID", IT_USER_ID))
                .build();

        seedItPlatformAdmin();
    }

    /**
     * Pre-seed a platform_admins row matching {@link #IT_USER_ID} so any
     * audit/invited_by FK that references it is satisfied. Idempotent via
     * {@code ON CONFLICT DO NOTHING}.
     */
    private void seedItPlatformAdmin() {
        jdbc.update("""
                INSERT INTO platform_admins
                    (admin_id, email, full_name, role, is_active, mfa_enabled, password_hash)
                VALUES (?::uuid, ?, ?, 'ADMIN', true, false, '$bcrypt$placeholder')
                ON CONFLICT (admin_id) DO NOTHING
                """, IT_USER_ID, IT_USER_EMAIL, "IT Test Admin");
    }
}
