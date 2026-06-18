package com.kaorisystem.auth.it;

import org.junit.jupiter.api.Assumptions;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.Resource;
import org.springframework.core.io.support.PathMatchingResourcePatternResolver;
import org.testcontainers.containers.PostgreSQLContainer;

import javax.sql.DataSource;
import java.io.IOException;
import java.sql.Connection;
import java.sql.ResultSet;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Objects;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * Batch 3.2.a — Flyway integration tests.
 *
 * <p>Two scenarios:
 * <ol>
 *   <li><b>Hot path</b> (extends AbstractIntegrationIT): the auth-service Spring
 *       context already booted Flyway against the IT Postgres. Asserts
 *       {@code flyway_schema_history} exists and has the BASELINE row at v14.
 *       This proves Flyway is wired into the application startup path.</li>
 *
 *   <li><b>Cold path</b> (standalone, fresh TC container): runs Flyway from
 *       scratch with {@code baselineOnMigrate=false} against an empty Postgres,
 *       verifies every migration file under {@code classpath:db/migration}
 *       applies cleanly, and that the resulting schema contains the
 *       load-bearing tables. The expected migration count is derived from
 *       the classpath at test time, so adding a new migration file
 *       auto-updates the assertion. This is the "migration runs on clean DB"
 *       verification the spec asked for.</li>
 * </ol>
 */
@DisplayName("Flyway 3.2.a — schema history baseline + cold-boot")
class FlywayMigrationIT extends AbstractIntegrationIT {

    @Autowired private DataSource dataSource;

    // -------------------------------------------------------------------------
    // Hot path — Flyway baselined inside the running application context
    // -------------------------------------------------------------------------

    @Test
    @DisplayName("hot path: flyway_schema_history exists with BASELINE row at version 14")
    void baselineRowPresent() throws Exception {
        try (Connection conn = dataSource.getConnection();
             Statement stmt  = conn.createStatement();
             ResultSet rs    = stmt.executeQuery("""
                     SELECT installed_rank, version, type, description, success
                       FROM flyway_schema_history
                      ORDER BY installed_rank
                     """)) {
            List<String> rows = new ArrayList<>();
            while (rs.next()) {
                rows.add(rs.getString("version") + ":" + rs.getString("type")
                        + ":" + rs.getBoolean("success"));
            }
            assertThat(rows)
                    .as("Flyway must have at least the baseline row recorded")
                    .isNotEmpty();
            // First row should be the baseline at version 14
            assertThat(rows.get(0))
                    .contains("14")
                    .contains("BASELINE")
                    .contains("true");
        }
    }

    @Test
    @DisplayName("hot path: load-bearing tables from migrations 001-014 are visible")
    void coreTablesExist() throws Exception {
        // Smoke check that Flyway didn't accidentally wipe / fail to baseline
        // on a schema that contains the tables our app depends on.
        try (Connection conn = dataSource.getConnection();
             Statement stmt  = conn.createStatement()) {
            for (String table : new String[]{
                    "workspaces", "enterprises", "subscription_plans",
                    "platform_admins", "admin_sessions", "platform_admin_audit_log",
                    "workspace_audit_log", "workspace_keys"}) {
                try (ResultSet rs = stmt.executeQuery(
                        "SELECT to_regclass('public." + table + "') IS NOT NULL AS present")) {
                    rs.next();
                    assertThat(rs.getBoolean("present"))
                            .as("table %s must exist after Flyway baseline", table)
                            .isTrue();
                }
            }
        }
    }

    // -------------------------------------------------------------------------
    // Cold path — Flyway runs all migrations on a brand-new Postgres
    // -------------------------------------------------------------------------

    /** Number of `*.sql` files on the classpath under `db/migration/`. Single
     * source of truth for cold-boot count assertions — bumps automatically
     * each time a new migration file lands, so tests don't need a hand-edit. */
    private static int classpathMigrationCount() throws IOException {
        return new PathMatchingResourcePatternResolver()
                .getResources("classpath:db/migration/*.sql").length;
    }

    /** Highest numeric prefix among migration files (e.g. `037_foo.sql` → 37).
     * Used to verify Flyway's `targetSchemaVersion` matches the latest file
     * on disk, without hard-coding the version. */
    private static int highestMigrationVersion() throws IOException {
        Resource[] files = new PathMatchingResourcePatternResolver()
                .getResources("classpath:db/migration/*.sql");
        return Arrays.stream(files)
                .map(Resource::getFilename)
                .filter(Objects::nonNull)
                .map(name -> name.split("_", 2)[0])
                .mapToInt(Integer::parseInt)
                .max()
                .orElseThrow(() -> new IllegalStateException(
                        "No migration files found on classpath:db/migration"));
    }

    @Test
    @DisplayName("cold path: Flyway applies every classpath migration on an empty DB and creates expected tables")
    void coldBoot_appliesAllMigrations() throws java.sql.SQLException, IOException {
        // This test deliberately stands up its OWN Postgres container so we
        // can prove Flyway-by-itself does the right thing. Skip with a clear
        // message when Docker / Testcontainers isn't available — same shape
        // as AbstractIntegrationIT's TC fallback.
        PostgreSQLContainer<?> pg;
        try {
            pg = new PostgreSQLContainer<>("pgvector/pgvector:pg15")
                    .withDatabaseName("flyway_cold")
                    .withUsername("kaori")
                    .withPassword("kaori_dev_password");
            pg.start();
        } catch (Throwable startup) {
            Assumptions.abort("Testcontainers / Docker unavailable — skipping cold-boot Flyway test: "
                    + startup.getClass().getSimpleName() + " " + startup.getMessage());
            return;
        }

        try {
            // Run Flyway directly (not via Spring) so we can assert the migration
            // count cleanly without touching the application context.
            org.flywaydb.core.Flyway flyway = org.flywaydb.core.Flyway.configure()
                    .dataSource(pg.getJdbcUrl(), pg.getUsername(), pg.getPassword())
                    .locations("classpath:db/migration")
                    .sqlMigrationPrefix("")
                    .sqlMigrationSeparator("_")
                    .sqlMigrationSuffixes(".sql")
                    .baselineOnMigrate(false)   // start truly empty
                    .validateOnMigrate(true)
                    .cleanDisabled(true)
                    .load();

            int expectedCount = classpathMigrationCount();
            int expectedTopVersion = highestMigrationVersion();

            org.flywaydb.core.api.output.MigrateResult result = flyway.migrate();
            assertThat(result.success).isTrue();
            assertThat(result.migrationsExecuted)
                    .as("every migration file under classpath:db/migration must apply on a clean DB")
                    .isEqualTo(expectedCount);

            // Verify the highest applied version. Flyway preserves the
            // file's version string verbatim (`001_init.sql` → "001"), so
            // we parse to int instead of string-comparing — robust to either
            // zero-padded ("025") or plain ("25") formats.
            assertThat(Integer.parseInt(result.targetSchemaVersion)).isEqualTo(expectedTopVersion);

            // Spot-check that the schema is actually in place
            try (Connection conn = java.sql.DriverManager.getConnection(
                            pg.getJdbcUrl(), pg.getUsername(), pg.getPassword());
                 Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery(
                         "SELECT to_regclass('public.platform_admin_audit_log') IS NOT NULL AS present")) {
                rs.next();
                assertThat(rs.getBoolean("present")).isTrue();
            }

            // Schema history should record every migration file (no baseline row this time)
            try (Connection conn = java.sql.DriverManager.getConnection(
                            pg.getJdbcUrl(), pg.getUsername(), pg.getPassword());
                 Statement stmt = conn.createStatement();
                 ResultSet rs = stmt.executeQuery(
                         "SELECT COUNT(*) AS c FROM flyway_schema_history WHERE success = true AND type='SQL'")) {
                rs.next();
                assertThat(rs.getInt("c")).isEqualTo(expectedCount);
            }
        } finally {
            pg.stop();
        }
    }
}
