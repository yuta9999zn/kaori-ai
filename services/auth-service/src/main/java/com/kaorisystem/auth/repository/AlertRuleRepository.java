package com.kaorisystem.auth.repository;

import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * F-037 alert_rules CRUD repository — per-tenant custom rules.
 *
 * <p>Implicit billing defaults (80% / 95%) are NOT stored here; the
 * {@link com.kaorisystem.auth.service.BillingAlertService} dispatcher
 * uses hardcoded sentinel UUIDs for those (kept off the table to avoid
 * per-enterprise seed bloat). This repo only handles tenant-customised
 * rules surfaced through the {@code /api/v1/enterprise/alerts} CRUD.
 *
 * <p>Plain {@link NamedParameterJdbcTemplate} component (matches
 * {@link BillingAggregationRepository}, {@link NotificationOutboxRepository})
 * because the alert_rules row maps cleanly to a record without JPA
 * lifecycle benefits.
 */
@Component
@RequiredArgsConstructor
public class AlertRuleRepository {

    private final NamedParameterJdbcTemplate jdbc;

    private static final ObjectMapper JSON = new ObjectMapper();

    // -------------------------------------------------------------------------
    // CRUD
    // -------------------------------------------------------------------------

    /** Insert a new rule. Returns the generated rule_id. */
    public UUID insert(AlertRuleRow row) {
        UUID ruleId = row.ruleId() != null ? row.ruleId() : UUID.randomUUID();
        String sql = """
            INSERT INTO alert_rules
                (rule_id, enterprise_id, name, description,
                 metric_type, operator, threshold_value,
                 channel, target_email, cooldown_seconds, is_active)
            VALUES
                (:ruleId, :eid, :name, :description,
                 :metricType, :operator, :threshold,
                 :channel, :targetEmail, :cooldown, :isActive)
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("ruleId",       ruleId)
                .addValue("eid",          row.enterpriseId())
                .addValue("name",         row.name())
                .addValue("description",  row.description())
                .addValue("metricType",   row.metricType())
                .addValue("operator",     row.operator())
                .addValue("threshold",    row.thresholdValue())
                .addValue("channel",      row.channel())
                .addValue("targetEmail",  row.targetEmail())
                .addValue("cooldown",     row.cooldownSeconds())
                .addValue("isActive",     row.isActive());
        jdbc.update(sql, p);
        return ruleId;
    }

    /** Cursor / offset list for the FE table. Soft-deleted rows excluded. */
    public List<AlertRuleRow> findByEnterprise(UUID enterpriseId, int limit, int offset) {
        String sql = """
            SELECT rule_id, enterprise_id, name, description,
                   metric_type, operator, threshold_value,
                   channel, target_email, cooldown_seconds,
                   is_active, created_at, updated_at
              FROM alert_rules
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
             ORDER BY created_at DESC
             LIMIT :lim OFFSET :off
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId)
                .addValue("lim", limit)
                .addValue("off", offset);
        return jdbc.query(sql, p, AlertRuleRepository::mapRow);
    }

    public long countByEnterprise(UUID enterpriseId) {
        String sql = """
            SELECT COUNT(*) FROM alert_rules
             WHERE enterprise_id = :eid AND deleted_at IS NULL
            """;
        Long c = jdbc.queryForObject(sql, new MapSqlParameterSource("eid", enterpriseId), Long.class);
        return c == null ? 0L : c;
    }

    public Optional<AlertRuleRow> findByIdAndEnterprise(UUID ruleId, UUID enterpriseId) {
        String sql = """
            SELECT rule_id, enterprise_id, name, description,
                   metric_type, operator, threshold_value,
                   channel, target_email, cooldown_seconds,
                   is_active, created_at, updated_at
              FROM alert_rules
             WHERE rule_id = :ruleId AND enterprise_id = :eid AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("ruleId", ruleId)
                .addValue("eid",    enterpriseId);
        try {
            return Optional.ofNullable(jdbc.queryForObject(sql, p, AlertRuleRepository::mapRow));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    /**
     * Partial update — only non-null fields in {@code patch} are applied.
     * Uses COALESCE in SQL so we don't have to dynamically build the
     * UPDATE statement; null fields fall back to the existing column
     * value. Returns rows affected.
     */
    public int update(UUID ruleId, UUID enterpriseId, AlertRulePatch patch) {
        String sql = """
            UPDATE alert_rules SET
                name             = COALESCE(:name,        name),
                description      = COALESCE(:description, description),
                operator         = COALESCE(:operator,    operator),
                threshold_value  = COALESCE(:threshold,   threshold_value),
                target_email     = COALESCE(:targetEmail, target_email),
                cooldown_seconds = COALESCE(:cooldown,    cooldown_seconds),
                is_active        = COALESCE(:isActive,    is_active),
                updated_at       = NOW()
              WHERE rule_id = :ruleId
                AND enterprise_id = :eid
                AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("ruleId",      ruleId)
                .addValue("eid",         enterpriseId)
                .addValue("name",        patch.name())
                .addValue("description", patch.description())
                .addValue("operator",    patch.operator())
                .addValue("threshold",   patch.thresholdValue())
                .addValue("targetEmail", patch.targetEmail())
                .addValue("cooldown",    patch.cooldownSeconds())
                .addValue("isActive",    patch.isActive());
        return jdbc.update(sql, p);
    }

    /** Soft delete — sets deleted_at = NOW(). Returns rows affected. */
    public int softDelete(UUID ruleId, UUID enterpriseId) {
        String sql = """
            UPDATE alert_rules
               SET deleted_at = NOW(), updated_at = NOW(), is_active = FALSE
             WHERE rule_id = :ruleId
               AND enterprise_id = :eid
               AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("ruleId", ruleId)
                .addValue("eid",    enterpriseId);
        return jdbc.update(sql, p);
    }

    // -------------------------------------------------------------------------
    // Mapper
    // -------------------------------------------------------------------------

    private static AlertRuleRow mapRow(ResultSet rs, int n) throws SQLException {
        return new AlertRuleRow(
                rs.getObject("rule_id",       UUID.class),
                rs.getObject("enterprise_id", UUID.class),
                rs.getString("name"),
                rs.getString("description"),
                rs.getString("metric_type"),
                rs.getString("operator"),
                rs.getBigDecimal("threshold_value"),
                rs.getString("channel"),
                rs.getString("target_email"),
                rs.getInt("cooldown_seconds"),
                rs.getBoolean("is_active"),
                rs.getTimestamp("created_at") == null ? null : rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at") == null ? null : rs.getTimestamp("updated_at").toInstant()
        );
    }

    // -------------------------------------------------------------------------
    // DTOs
    // -------------------------------------------------------------------------

    /**
     * A full alert_rules row. {@code threshold_value} kept as
     * {@link BigDecimal} to match the NUMERIC(14,4) column without
     * precision loss (K-9).
     */
    public record AlertRuleRow(
            UUID       ruleId,
            UUID       enterpriseId,
            String     name,
            String     description,
            String     metricType,
            String     operator,
            BigDecimal thresholdValue,
            String     channel,
            String     targetEmail,
            int        cooldownSeconds,
            boolean    isActive,
            Instant    createdAt,
            Instant    updatedAt
    ) {}

    /**
     * Partial update payload — fields that are null are NOT modified.
     * Boxed types so a null Boolean / Integer is distinguishable from
     * an explicit false / 0.
     */
    public record AlertRulePatch(
            String     name,
            String     description,
            String     operator,
            BigDecimal thresholdValue,
            String     targetEmail,
            Integer    cooldownSeconds,
            Boolean    isActive
    ) {}
}
