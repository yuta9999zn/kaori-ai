package com.kaorisystem.auth.repository;

import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

/**
 * Issue #6 — unit tests for {@link NotificationOutboxRepository}.
 *
 * <p>JdbcTemplate is mocked. Three contracts under test:
 * <ol>
 *   <li>The INSERT carries the expected SQL shape + every column the
 *       caller supplied (status defaults from migration 026, not from
 *       Java).</li>
 *   <li>{@code context} reaches Postgres as a JSON string with a JSONB
 *       cast in the SQL — required because asyncpg/JdbcTemplate cannot
 *       infer JSONB from a Java Map.</li>
 *   <li>Best-effort: a JDBC error returns null and is logged, never
 *       propagated. The caller (auth-service inside an
 *       {@code @Transactional} method) must not see the trigger row
 *       roll back because the outbox INSERT bumped a constraint.</li>
 * </ol>
 */
@DisplayName("NotificationOutboxRepository — INSERT shape + best-effort")
class NotificationOutboxRepositoryTest {

    private final NamedParameterJdbcTemplate jdbc = mock(NamedParameterJdbcTemplate.class);
    private final NotificationOutboxRepository repo = new NotificationOutboxRepository(jdbc);

    @Test
    @DisplayName("enqueue inserts a row with all caller-supplied columns")
    void enqueue_buildsCompleteInsert() {
        when(jdbc.update(anyString(), any(MapSqlParameterSource.class))).thenReturn(1);

        UUID enterpriseId = UUID.randomUUID();
        Map<String, Object> context = Map.of(
                "reset_url", "https://kaori.io/reset?token=abc",
                "full_name", "Nguyễn Văn A");

        UUID outboxId = repo.enqueue(enterpriseId, "reset-password",
                "user@example.com", context, "password_reset");

        assertThat(outboxId).isNotNull();

        ArgumentCaptor<String> sqlCap = ArgumentCaptor.forClass(String.class);
        ArgumentCaptor<MapSqlParameterSource> paramsCap =
                ArgumentCaptor.forClass(MapSqlParameterSource.class);
        verify(jdbc).update(sqlCap.capture(), paramsCap.capture());

        String sql = sqlCap.getValue();
        assertThat(sql).contains("INSERT INTO notification_outbox");
        // CAST(:context AS JSONB) is the only way to flow a JSON string
        // into a JSONB column via JdbcTemplate without registering a
        // custom converter.
        assertThat(sql.replace("\n", " ").replaceAll("\\s+", " "))
                .contains("CAST(:context AS JSONB)");

        MapSqlParameterSource p = paramsCap.getValue();
        assertThat(p.getValue("outboxId")).isEqualTo(outboxId);
        assertThat(p.getValue("enterpriseId")).isEqualTo(enterpriseId);
        assertThat(p.getValue("template")).isEqualTo("reset-password");
        assertThat(p.getValue("recipient")).isEqualTo("user@example.com");
        assertThat(p.getValue("sourceRef")).isEqualTo("password_reset");

        // Context is serialised to JSON before INSERT — verify the
        // shape rather than the byte-exact string (Jackson key ordering
        // is stable but explicit ordering would over-pin).
        String contextJson = (String) p.getValue("context");
        assertThat(contextJson).contains("\"reset_url\":\"https://kaori.io/reset?token=abc\"");
        assertThat(contextJson).contains("Nguyễn Văn A");
    }

    @Test
    @DisplayName("null enterprise_id is allowed for system-wide notifications")
    void enqueue_nullEnterpriseIdInserted() {
        when(jdbc.update(anyString(), any(MapSqlParameterSource.class))).thenReturn(1);

        UUID outboxId = repo.enqueue(null, "reset-password",
                "u@k.io", Map.of("reset_url", "x"), null);

        assertThat(outboxId).isNotNull();

        ArgumentCaptor<MapSqlParameterSource> cap =
                ArgumentCaptor.forClass(MapSqlParameterSource.class);
        verify(jdbc).update(anyString(), cap.capture());
        assertThat(cap.getValue().getValue("enterpriseId")).isNull();
        assertThat(cap.getValue().getValue("sourceRef")).isNull();
    }

    @Test
    @DisplayName("null context is treated as empty map (never crashes Jackson)")
    void enqueue_nullContextSerialisedAsEmptyObject() {
        when(jdbc.update(anyString(), any(MapSqlParameterSource.class))).thenReturn(1);

        repo.enqueue(UUID.randomUUID(), "invite", "u@k.io", null, "x");

        ArgumentCaptor<MapSqlParameterSource> cap =
                ArgumentCaptor.forClass(MapSqlParameterSource.class);
        verify(jdbc).update(anyString(), cap.capture());
        assertThat((String) cap.getValue().getValue("context")).isEqualTo("{}");
    }

    @Test
    @DisplayName("DB failure returns null and DOES NOT propagate (best-effort)")
    void enqueue_dbFailureReturnsNullAndSwallowsException() {
        // Simulate a connection-pool exhaustion. Caller sits inside an
        // @Transactional method that committed the trigger row earlier
        // — we MUST NOT throw or that commit gets rolled back.
        doThrow(new DataAccessResourceFailureException("pool exhausted"))
                .when(jdbc).update(anyString(), any(MapSqlParameterSource.class));

        UUID result = repo.enqueue(UUID.randomUUID(), "reset-password",
                "u@k.io", Map.of(), "x");

        assertThat(result)
                .as("DB failure must surface as null, not as a thrown exception")
                .isNull();
    }

    @Test
    @DisplayName("non-serialisable context returns null without ever calling jdbc")
    void enqueue_nonSerialisableContext_skipsInsert() {
        // A Map containing a value Jackson can't serialise (e.g., a
        // raw Object handle). The repo should log + return null, NOT
        // attempt the INSERT with garbage.
        Map<String, Object> bad = new HashMap<>();
        bad.put("unserialisable", new Object() {
            // Lambda field forces Jackson into the "no serialiser found"
            // path; same effect as passing a raw class with no getters.
            @SuppressWarnings("unused")
            Runnable r = () -> {};
        });

        UUID result = repo.enqueue(UUID.randomUUID(), "reset-password",
                "u@k.io", bad, "x");

        assertThat(result).isNull();
        verify(jdbc, never()).update(anyString(), any(MapSqlParameterSource.class));
    }

    @Test
    @DisplayName("sql does NOT mention status / attempts / created_at — those default in migration 026")
    void enqueue_doesNotOverrideTableDefaults() {
        when(jdbc.update(anyString(), any(MapSqlParameterSource.class))).thenReturn(1);

        repo.enqueue(UUID.randomUUID(), "reset-password",
                "u@k.io", Map.of(), "x");

        ArgumentCaptor<String> sqlCap = ArgumentCaptor.forClass(String.class);
        verify(jdbc).update(sqlCap.capture(), any(MapSqlParameterSource.class));
        String sql = sqlCap.getValue();
        // The migration sets status='pending', attempts=0, created_at=NOW()
        // by DEFAULT. Letting the table default keeps Java oblivious to
        // schema-level invariants and means a future change ("backoff
        // start at attempts=1 instead of 0") only touches one place.
        assertThat(sql).doesNotContain("status").doesNotContain("attempts")
                .doesNotContain("created_at").doesNotContain("last_attempt_at");
    }

    @Test
    @DisplayName("repeated enqueue calls produce distinct outbox_ids (UUIDv4)")
    void enqueue_returnsFreshUuidEachTime() {
        when(jdbc.update(anyString(), any(MapSqlParameterSource.class))).thenReturn(1);

        UUID a = repo.enqueue(null, "reset-password", "u@k.io", Map.of(), null);
        UUID b = repo.enqueue(null, "reset-password", "u@k.io", Map.of(), null);

        assertThat(a).isNotNull().isNotEqualTo(b);
    }

    @Test
    @DisplayName("caller-thread safety: synchronous and best-effort means no exception bubbles")
    void enqueue_isSafeToCallFromTransactionalMethod() {
        // Even when EVERY single dependency misbehaves (jdbc throws,
        // mapper would crash if reached), the caller's transactional
        // method should keep running.
        doThrow(new RuntimeException("boom"))
                .when(jdbc).update(anyString(), any(MapSqlParameterSource.class));

        assertThatCode(() ->
                repo.enqueue(UUID.randomUUID(), "reset-password",
                        "u@k.io", Map.of("reset_url", "x"), "x"))
                .doesNotThrowAnyException();
    }
}
