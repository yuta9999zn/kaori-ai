package com.kaorisystem.auth.repository;

import lombok.RequiredArgsConstructor;
import org.springframework.dao.EmptyResultDataAccessException;
import org.springframework.jdbc.core.namedparam.MapSqlParameterSource;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

/**
 * F-040 OKR repository — JdbcTemplate-based, mirrors the F-039 risk
 * repository structure. Two tables (okr_objectives + okr_key_results)
 * with parent-child cascade.
 *
 * <p>The KR set on an objective is treated as an atomic collection:
 * {@link #replaceKeyResults} deletes existing KRs and re-inserts the
 * provided list inside one transaction. Diffing + merging a typically
 * 3-row collection is more code than it's worth.
 */
@Component
@RequiredArgsConstructor
public class OkrRepository {

    private final NamedParameterJdbcTemplate jdbc;

    // -------------------------------------------------------------------------
    // Objectives — CRUD
    // -------------------------------------------------------------------------

    public UUID insertObjective(ObjectiveRow row) {
        UUID id = row.objectiveId() != null ? row.objectiveId() : UUID.randomUUID();
        String sql = """
            INSERT INTO okr_objectives
                (objective_id, enterprise_id, quarter, title,
                 owner_user_id, status, created_by_user)
            VALUES
                (:id, :eid, :quarter, :title,
                 :owner, :status, :createdBy)
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("id",        id)
                .addValue("eid",       row.enterpriseId())
                .addValue("quarter",   row.quarter())
                .addValue("title",     row.title())
                .addValue("owner",     row.ownerUserId())
                .addValue("status",    row.status())
                .addValue("createdBy", row.createdByUser());
        jdbc.update(sql, p);
        return id;
    }

    public List<ObjectiveRow> findByEnterprise(
            UUID enterpriseId, String quarter, int limit, int offset) {
        StringBuilder sql = new StringBuilder("""
            SELECT objective_id, enterprise_id, quarter, title,
                   owner_user_id, status, created_by_user,
                   created_at, updated_at
              FROM okr_objectives
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
            """);
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId);
        if (quarter != null && !quarter.isBlank()) {
            sql.append(" AND quarter = :quarter");
            p.addValue("quarter", quarter);
        }
        sql.append("""
              ORDER BY quarter DESC, status DESC, objective_id DESC
              LIMIT :lim OFFSET :off
            """);
        p.addValue("lim", limit).addValue("off", offset);
        return jdbc.query(sql.toString(), p, OkrRepository::mapObjective);
    }

    public long countByEnterprise(UUID enterpriseId, String quarter) {
        StringBuilder sql = new StringBuilder("""
            SELECT COUNT(*) FROM okr_objectives
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
            """);
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId);
        if (quarter != null && !quarter.isBlank()) {
            sql.append(" AND quarter = :quarter");
            p.addValue("quarter", quarter);
        }
        Long c = jdbc.queryForObject(sql.toString(), p, Long.class);
        return c == null ? 0L : c;
    }

    public Optional<ObjectiveRow> findByIdAndEnterprise(UUID objectiveId, UUID enterpriseId) {
        String sql = """
            SELECT objective_id, enterprise_id, quarter, title,
                   owner_user_id, status, created_by_user,
                   created_at, updated_at
              FROM okr_objectives
             WHERE objective_id = :id
               AND enterprise_id = :eid
               AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("id",  objectiveId)
                .addValue("eid", enterpriseId);
        try {
            return Optional.ofNullable(jdbc.queryForObject(sql, p, OkrRepository::mapObjective));
        } catch (EmptyResultDataAccessException e) {
            return Optional.empty();
        }
    }

    public int updateObjective(UUID objectiveId, UUID enterpriseId, ObjectivePatch patch) {
        String sql = """
            UPDATE okr_objectives SET
                quarter       = COALESCE(:quarter, quarter),
                title         = COALESCE(:title, title),
                owner_user_id = COALESCE(:owner, owner_user_id),
                status        = COALESCE(:status, status)
              WHERE objective_id = :id
                AND enterprise_id = :eid
                AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("id",      objectiveId)
                .addValue("eid",     enterpriseId)
                .addValue("quarter", patch.quarter())
                .addValue("title",   patch.title())
                .addValue("owner",   patch.ownerUserId())
                .addValue("status",  patch.status());
        return jdbc.update(sql, p);
    }

    public int softDelete(UUID objectiveId, UUID enterpriseId) {
        String sql = """
            UPDATE okr_objectives
               SET deleted_at = NOW()
             WHERE objective_id = :id
               AND enterprise_id = :eid
               AND deleted_at IS NULL
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("id",  objectiveId)
                .addValue("eid", enterpriseId);
        return jdbc.update(sql, p);
    }

    // -------------------------------------------------------------------------
    // Key Results — child collection
    // -------------------------------------------------------------------------

    public List<KeyResultRow> findKeyResultsByObjective(UUID objectiveId) {
        String sql = """
            SELECT kr_id, objective_id, enterprise_id, title, unit,
                   target, current_value, display_order,
                   created_at, updated_at
              FROM okr_key_results
             WHERE objective_id = :id
             ORDER BY display_order, kr_id
            """;
        return jdbc.query(sql,
                new MapSqlParameterSource("id", objectiveId),
                OkrRepository::mapKr);
    }

    /**
     * Atomic: delete all existing KRs for this objective, then insert the
     * provided list. Wrapped in a transaction so a half-write can't
     * leave the parent pointing at a phantom KR set.
     *
     * <p>Returns the inserted KRs in the order they were submitted.
     */
    @Transactional
    public List<KeyResultRow> replaceKeyResults(
            UUID objectiveId, UUID enterpriseId, List<KeyResultRow> krs) {

        jdbc.update(
                "DELETE FROM okr_key_results WHERE objective_id = :id",
                new MapSqlParameterSource("id", objectiveId));

        List<KeyResultRow> inserted = new ArrayList<>(krs.size());
        int order = 0;
        String insertSql = """
            INSERT INTO okr_key_results
                (kr_id, objective_id, enterprise_id, title, unit,
                 target, current_value, display_order)
            VALUES
                (:id, :objId, :eid, :title, :unit,
                 :target, :current, :order)
            """;
        for (KeyResultRow kr : krs) {
            UUID krId = kr.krId() != null ? kr.krId() : UUID.randomUUID();
            MapSqlParameterSource p = new MapSqlParameterSource()
                    .addValue("id",      krId)
                    .addValue("objId",   objectiveId)
                    .addValue("eid",     enterpriseId)
                    .addValue("title",   kr.title())
                    .addValue("unit",    kr.unit())
                    .addValue("target",  kr.target())
                    .addValue("current", kr.currentValue())
                    .addValue("order",   order++);
            jdbc.update(insertSql, p);
            inserted.add(new KeyResultRow(
                    krId, objectiveId, enterpriseId,
                    kr.title(), kr.unit(),
                    kr.target(), kr.currentValue(), order - 1,
                    null, null));
        }
        return inserted;
    }

    /**
     * Update only the current_value of a single KR (the most common
     * "I made progress this week" mutation). Returns rows-affected
     * so the service can 404 a missing KR.
     */
    public int updateKeyResultCurrent(
            UUID krId, UUID objectiveId, BigDecimal currentValue) {
        String sql = """
            UPDATE okr_key_results
               SET current_value = :current
             WHERE kr_id = :id
               AND objective_id = :objId
            """;
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("id",      krId)
                .addValue("objId",   objectiveId)
                .addValue("current", currentValue);
        return jdbc.update(sql, p);
    }

    // -------------------------------------------------------------------------
    // Rollups
    // -------------------------------------------------------------------------

    /**
     * Summary tile — groups by status across all undeleted objectives in
     * a quarter (or all quarters if {@code quarter} is null). Returns
     * one row per present status; service backfills missing buckets.
     */
    public Map<String, Long> statusRollup(UUID enterpriseId, String quarter) {
        StringBuilder sql = new StringBuilder("""
            SELECT status, COUNT(*) AS c
              FROM okr_objectives
             WHERE enterprise_id = :eid
               AND deleted_at IS NULL
            """);
        MapSqlParameterSource p = new MapSqlParameterSource()
                .addValue("eid", enterpriseId);
        if (quarter != null && !quarter.isBlank()) {
            sql.append(" AND quarter = :quarter");
            p.addValue("quarter", quarter);
        }
        sql.append(" GROUP BY status");

        Map<String, Long> out = new LinkedHashMap<>();
        jdbc.query(sql.toString(), p, (rs) -> {
            out.put(rs.getString("status"), rs.getLong("c"));
        });
        return out;
    }

    // -------------------------------------------------------------------------
    // Mappers + record types
    // -------------------------------------------------------------------------

    private static ObjectiveRow mapObjective(ResultSet rs, int n) throws SQLException {
        return new ObjectiveRow(
                rs.getObject("objective_id",    UUID.class),
                rs.getObject("enterprise_id",   UUID.class),
                rs.getString("quarter"),
                rs.getString("title"),
                rs.getObject("owner_user_id",   UUID.class),
                rs.getString("status"),
                rs.getObject("created_by_user", UUID.class),
                rs.getTimestamp("created_at") == null ? null : rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at") == null ? null : rs.getTimestamp("updated_at").toInstant()
        );
    }

    private static KeyResultRow mapKr(ResultSet rs, int n) throws SQLException {
        return new KeyResultRow(
                rs.getObject("kr_id",          UUID.class),
                rs.getObject("objective_id",   UUID.class),
                rs.getObject("enterprise_id",  UUID.class),
                rs.getString("title"),
                rs.getString("unit"),
                rs.getBigDecimal("target"),
                rs.getBigDecimal("current_value"),
                rs.getInt("display_order"),
                rs.getTimestamp("created_at") == null ? null : rs.getTimestamp("created_at").toInstant(),
                rs.getTimestamp("updated_at") == null ? null : rs.getTimestamp("updated_at").toInstant()
        );
    }

    public record ObjectiveRow(
            UUID    objectiveId,
            UUID    enterpriseId,
            String  quarter,
            String  title,
            UUID    ownerUserId,
            String  status,
            UUID    createdByUser,
            Instant createdAt,
            Instant updatedAt
    ) {}

    public record ObjectivePatch(
            String quarter,
            String title,
            UUID   ownerUserId,
            String status
    ) {}

    public record KeyResultRow(
            UUID       krId,
            UUID       objectiveId,
            UUID       enterpriseId,
            String     title,
            String     unit,
            BigDecimal target,
            BigDecimal currentValue,
            int        displayOrder,
            Instant    createdAt,
            Instant    updatedAt
    ) {}
}
