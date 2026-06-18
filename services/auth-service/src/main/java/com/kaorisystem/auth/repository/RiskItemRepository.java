package com.kaorisystem.auth.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

/**
 * F-039 risk_items CRUD repository — per-tenant risk register.
 *
 * <p>JdbcTemplate-based to match the F-037 alerts pattern. Score +
 * severity are computed by the migration-033 trigger; the repo
 * doesn't have to recompute them on the Java side.
 *
 * <p>Soft-delete only — the migration grants no DELETE to kaori_app.
 * ``softDelete`` sets ``deleted_at = NOW()``; the list query filters
 * ``WHERE deleted_at IS NULL`` so the FE never sees tombstones.
 */
@Component
@RequiredArgsConstructor
public class RiskItemRepository {

    private final NamedParameterJdbcTemplate jdbc;

    // -------------------------------------------------------------------------
    // CRUD
    // -------------------------------------------------------------------------

    public UUID insert(RiskItemRow row) {
        UUID riskId = row.riskId() != null ? row.riskId() : UUID.randomUUID();
        String sql = """
            INSERT INTO risk_items
                (risk_id, enterprise_id, title, description, category,
                 likelihood, impact, status,
                 mitigation_plan, mitigation_progress,
                 owner_user_id, due_date, source, created_by_user)
            VALUES
                (:riskId, :eid, :title, :description, :category,
                 :likelihood, :impact, :status,
                 :mitigationPlan, :mitigationProgress,
                 :ownerUserId, :dueDate, :source, :createdByUser)
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("riskId",             riskId)
                .addValue("eid",                row.enterpriseId())
                .addValue("title",              row.title())
                .addValue("description",        row.description())
                .addValue("category",           row.category())
                .addValue("likelihood",         row.likelihood())
                .addValue("impact",             row.impact())
                .addValue("status",             row.status())
                .addValue("mitigationPlan",     row.mitigationPlan())
                .addValue("mitigationProgress", row.mitigationProgress())
                .addValue("ownerUserId",        row.ownerUserId())
                .addValue("dueDate",            row.dueDate() == null ? null : java.sql.Date.valueOf(row.dueDate()))
                .addValue("source",             row.source())
                .addValue("createdByUser",      row.createdByUser());
        jdbc.update(sql, p);
        return riskId;
    }

    public List<RiskItemRow> findByEnterprise(
            UUID enterpriseId,
            String statusFilter,
            String severityFilter,
            String categoryFilter,
            int limit, int offset) {
        StringBuilder sql = new StringBuilder("""
            SELECT risk_id, enterprise_id, title, description, category,
                   likelihood, impact, score, severity, status,
                   mitigation_plan, mitigation_progress,
                   owner_user_id, due_date, source, created_by_user,
                   created_at, updated_at
              FROM risk_items
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
            """);
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId);
        if (statusFilter != null && !statusFilter.isBlank()) {
            sql.append(" AND status = :status");
            p.addValue("status", statusFilter);
        }
        if (severityFilter != null && !severityFilter.isBlank()) {
            sql.append(" AND severity = :severity");
            p.addValue("severity", severityFilter);
        }
        if (categoryFilter != null && !categoryFilter.isBlank()) {
            sql.append(" AND category = :category");
            p.addValue("category", categoryFilter);
        }
        sql.append("""
              ORDER BY score DESC, risk_id DESC
              LIMIT :lim OFFSET :off
            """);
        p.addValue("lim", limit).addValue("off", offset);
        return jdbc.query(sql.toString(), p, RiskItemRepository::mapRow);
    }

    public long countByEnterprise(
            UUID enterpriseId, String statusFilter, String severityFilter,
            String categoryFilter) {
        StringBuilder sql = new StringBuilder("""
            SELECT COUNT(*) FROM risk_items
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
            """);
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId);
        if (statusFilter != null && !statusFilter.isBlank()) {
            sql.append(" AND status = :status");
            p.addValue("status", statusFilter);
        }
        if (severityFilter != null && !severityFilter.isBlank()) {
            sql.append(" AND severity = :severity");
            p.addValue("severity", severityFilter);
        }
        if (categoryFilter != null && !categoryFilter.isBlank()) {
            sql.append(" AND category = :category");
            p.addValue("category", categoryFilter);
        }
        Long c = jdbc.queryForObject(sql.toString(), p, Long.class);
        return c == null ? 0L : c;
    }

    /**
     * Severity rollup — heat map header tile uses this to render
     * "X critical, Y high, Z medium" without paginating the table.
     */
    public List<SeverityCount> severityRollup(UUID enterpriseId) {
        String sql = """
            SELECT severity, COUNT(*) AS c
              FROM risk_items
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
               AND status != 'closed'
             GROUP BY severity
            """;
        MapSqlParameterSource p = new MapSqlParameterSource("eid", enterpriseId);
        return jdbc.query(sql, p, (rs, n) ->
                new SeverityCount(rs.getString("severity"), rs.getLong("c")));
    }

    public Optional<RiskItemRow> findByIdAndEnterprise(UUID riskId, UUID enterpriseId) {
        String sql = """
            SELECT risk_id, enterprise_id, title, description, category,
                   likelihood, impact, score, severity, status,
                   mitigation_plan, mitigation_progress,
                   owner_user_id, due_date, source, created_by_user,
                   created_at, updated_at
              FROM risk_items
             WHERE risk_id = :riskId
               AND enterprise_id = :eid
               AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("riskId", riskId)
                .addValue("eid",    enterpriseId);
        try {
            return Optional.ofNullable(jdbc.queryForObject(sql, p, RiskItemRepository::mapRow));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public int update(UUID riskId, UUID enterpriseId, RiskItemPatch patch) {
        // COALESCE pattern — same as F-037 alerts. Null fields fall
        // back to existing values. The score+severity trigger fires
        // when likelihood/impact change.
        String sql = """
            UPDATE risk_items SET
                title               = COALESCE(:title, title),
                description         = COALESCE(:description, description),
                category            = COALESCE(:category, category),
                likelihood          = COALESCE(:likelihood, likelihood),
                impact              = COALESCE(:impact, impact),
                status              = COALESCE(:status, status),
                mitigation_plan     = COALESCE(:mitigationPlan, mitigation_plan),
                mitigation_progress = COALESCE(:mitigationProgress, mitigation_progress),
                owner_user_id       = COALESCE(:ownerUserId, owner_user_id),
                due_date            = COALESCE(:dueDate, due_date)
              WHERE risk_id = :riskId
                AND enterprise_id = :eid
                AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("riskId",             riskId)
                .addValue("eid",                enterpriseId)
                .addValue("title",              patch.title())
                .addValue("description",        patch.description())
                .addValue("category",           patch.category())
                .addValue("likelihood",         patch.likelihood())
                .addValue("impact",             patch.impact())
                .addValue("status",             patch.status())
                .addValue("mitigationPlan",     patch.mitigationPlan())
                .addValue("mitigationProgress", patch.mitigationProgress())
                .addValue("ownerUserId",        patch.ownerUserId())
                .addValue("dueDate",            patch.dueDate() == null ? null : java.sql.Date.valueOf(patch.dueDate()));
        return jdbc.update(sql, p);
    }

    public int softDelete(UUID riskId, UUID enterpriseId) {
        String sql = """
            UPDATE risk_items
               SET deleted_at = NOW()
             WHERE risk_id = :riskId
               AND enterprise_id = :eid
               AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("riskId", riskId)
                .addValue("eid",    enterpriseId);
        return jdbc.update(sql, p);
    }

    // -------------------------------------------------------------------------
    // Mapper + DTOs
    // -------------------------------------------------------------------------

    private static RiskItemRow mapRow(ResultSet rs, int n) throws SQLException {
        return new RiskItemRow(
                rs.getObject("risk_id",       UUID.class),
                rs.getObject("enterprise_id", UUID.class),
                rs.getString("title"),
                rs.getString("description"),
                rs.getString("category"),
                rs.getInt("likelihood"),
                rs.getInt("impact"),
                rs.getInt("score"),
                rs.getString("severity"),
                rs.getString("status"),
                rs.getString("mitigation_plan"),
                rs.getInt("mitigation_progress"),
                rs.getObject("owner_user_id",   UUID.class),
                rs.getDate("due_date") == null ? null : rs.getDate("due_date").toLocalDate(),
                rs.getString("source"),
                rs.getObject("created_by_user", UUID.class),
                rs.getTimestamp("created_at") == null ? null : rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at") == null ? null : rs.getTimestamp("updated_at").toInstant()
        );
    }

    public record RiskItemRow(
            UUID      riskId,
            UUID      enterpriseId,
            String    title,
            String    description,
            String    category,
            int       likelihood,
            int       impact,
            int       score,
            String    severity,
            String    status,
            String    mitigationPlan,
            int       mitigationProgress,
            UUID      ownerUserId,
            LocalDate dueDate,
            String    source,
            UUID      createdByUser,
            Instant   createdAt,
            Instant   updatedAt
    ) {}

    public record RiskItemPatch(
            String    title,
            String    description,
            String    category,
            Integer   likelihood,
            Integer   impact,
            String    status,
            String    mitigationPlan,
            Integer   mitigationProgress,
            UUID      ownerUserId,
            LocalDate dueDate
    ) {}

    public record SeverityCount(String severity, long count) {}
}
