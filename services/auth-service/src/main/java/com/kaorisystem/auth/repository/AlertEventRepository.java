package com.kaorisystem.auth.repository;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/**
 * F-037 alert_events repository — append-only fire history + cooldown
 * lookup.
 *
 * <p>Cooldown semantics:
 * {@link #latestNonSuppressedFiredAt(UUID, UUID)} is the single source
 * of truth for "has this rule fired in the last N seconds?". The
 * dispatcher converts the answer into "now - latest >= cooldown_seconds"
 * before deciding to enqueue. We store cooldown_seconds on the rule
 * (not here) so a rule edit takes effect on the very next aggregation
 * tick.
 *
 * <p>The (rule_id, enterprise_id) pair is required for cooldown lookup
 * because implicit-default rule IDs (the billing-80 / billing-95
 * sentinel UUIDs in {@link com.kaorisystem.auth.service.BillingAlertService})
 * are shared across enterprises — without scoping by enterprise_id, a
 * fire from tenant A would suppress tenant B's fire.
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class AlertEventRepository {

    private final NamedParameterJdbcTemplate jdbc;
    private static final ObjectMapper JSON = new ObjectMapper();

    /**
     * Cooldown lookup: latest non-suppressed fire for this (rule, tenant).
     * Returns null if there's no prior non-suppressed event.
     */
    public Instant latestNonSuppressedFiredAt(UUID ruleId, UUID enterpriseId) {
        String sql = """
            SELECT MAX(fired_at) FROM alert_events
             WHERE rule_id = :ruleId
               AND enterprise_id = :eid
               AND suppressed = FALSE
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("ruleId", ruleId)
                .addValue("eid",    enterpriseId);
        java.sql.Timestamp ts = jdbc.queryForObject(sql, p, java.sql.Timestamp.class);
        return ts == null ? null : ts.toInstant();
    }

    /**
     * Insert a fire row. Returns event_id. Best-effort log+swallow on
     * failure (same rationale as {@link NotificationOutboxRepository#enqueue}):
     * a failed audit row should not abort the surrounding billing
     * aggregation transaction.
     */
    public UUID record(AlertEventRow row) {
        UUID eventId = UUID.randomUUID();
        String contextJson;
        try {
            contextJson = JSON.writeValueAsString(row.context() == null ? Map.of() : row.context());
        } catch (JsonProcessingException e) {
            log.error("alert_event.serialise_failed rule_id={} eid={} error={}",
                    row.ruleId(), row.enterpriseId(), e.getMessage());
            return null;
        }

        String sql = """
            INSERT INTO alert_events
                (event_id, enterprise_id, rule_id,
                 metric_type, metric_value, threshold_value, operator,
                 context, outbox_id, suppressed)
            VALUES
                (:eventId, :eid, :ruleId,
                 :metricType, :metricValue, :threshold, :operator,
                 CAST(:context AS JSONB), :outboxId, :suppressed)
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eventId",     eventId)
                .addValue("eid",         row.enterpriseId())
                .addValue("ruleId",      row.ruleId())
                .addValue("metricType",  row.metricType())
                .addValue("metricValue", row.metricValue())
                .addValue("threshold",   row.thresholdValue())
                .addValue("operator",    row.operator())
                .addValue("context",     contextJson)
                .addValue("outboxId",    row.outboxId())
                .addValue("suppressed",  row.suppressed());
        try {
            jdbc.update(sql, p);
            return eventId;
        } catch (Exception e) {
            log.error("alert_event.insert_failed rule_id={} eid={} error={}",
                    row.ruleId(), row.enterpriseId(), e.getMessage());
            return null;
        }
    }

    /**
     * History list for the FE — bounded to a small recent window.
     * Cursor pagination skipped for v0; the FE renders the most recent
     * 50 by default.
     */
    public List<AlertEventRow> findByEnterprise(UUID enterpriseId, int limit) {
        String sql = """
            SELECT event_id, enterprise_id, rule_id,
                   metric_type, metric_value, threshold_value, operator,
                   context, outbox_id, suppressed, fired_at
              FROM alert_events
             WHERE enterprise_id = :eid
             ORDER BY fired_at DESC
             LIMIT :lim
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId)
                .addValue("lim", Math.max(1, Math.min(limit, 500)));
        return jdbc.query(sql, p, AlertEventRepository::mapRow);
    }

    // -------------------------------------------------------------------------
    // Mapper + DTO
    // -------------------------------------------------------------------------

    private static AlertEventRow mapRow(ResultSet rs, int n) throws SQLException {
        Map<String, Object> ctx;
        String ctxJson = rs.getString("context");
        try {
            ctx = (ctxJson == null || ctxJson.isBlank())
                    ? Map.of()
                    : JSON.readValue(ctxJson, Map.class);
        } catch (Exception e) {
            ctx = Map.of();
        }
        UUID outboxId = rs.getObject("outbox_id") == null
                ? null
                : rs.getObject("outbox_id", UUID.class);
        return new AlertEventRow(
                rs.getObject("event_id",      UUID.class),
                rs.getObject("enterprise_id", UUID.class),
                rs.getObject("rule_id",       UUID.class),
                rs.getString("metric_type"),
                rs.getBigDecimal("metric_value"),
                rs.getBigDecimal("threshold_value"),
                rs.getString("operator"),
                ctx,
                outboxId,
                rs.getBoolean("suppressed"),
                rs.getTimestamp("fired_at") == null ? null : rs.getTimestamp("fired_at").toInstant()
        );
    }

    public record AlertEventRow(
            UUID                eventId,
            UUID                enterpriseId,
            UUID                ruleId,
            String              metricType,
            BigDecimal          metricValue,
            BigDecimal          thresholdValue,
            String              operator,
            Map<String, Object> context,
            UUID                outboxId,
            boolean             suppressed,
            Instant             firedAt
    ) {}
}
