package com.kaorisystem.auth.repository;

import com.kaorisystem.auth.model.Workspace;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface WorkspaceRepository extends JpaRepository<Workspace, UUID> {

    /**
     * Spring Data interface projection for the cursor-paginated list query.
     * Includes the first matching enterprise's `industry` (subselect) so the
     * controller can render it without a separate Enterprise entity round-trip.
     */
    interface WorkspaceListRow {
        UUID    getWorkspaceId();
        String  getName();
        String  getPlanCode();
        String  getStatus();
        Instant getCreatedAt();
        Instant getUpdatedAt();
        String  getIndustry();
    }

    // First page (no cursor) — newest first.
    @Query(value = """
        SELECT  w.workspace_id AS workspaceId,
                w.name         AS name,
                w.plan_code    AS planCode,
                w.status       AS status,
                w.created_at   AS createdAt,
                w.updated_at   AS updatedAt,
                (SELECT e.industry FROM enterprises e
                  WHERE e.workspace_id = w.workspace_id
                  ORDER BY e.created_at ASC LIMIT 1) AS industry
        FROM workspaces w
        ORDER BY w.created_at DESC, w.workspace_id DESC
        LIMIT :lim
        """, nativeQuery = true)
    List<WorkspaceListRow> findFirstPage(@Param("lim") int limit);

    // Subsequent pages — keyset on (created_at, workspace_id) DESC.
    // Tuple compare keeps ordering stable when several rows share a timestamp.
    @Query(value = """
        SELECT  w.workspace_id AS workspaceId,
                w.name         AS name,
                w.plan_code    AS planCode,
                w.status       AS status,
                w.created_at   AS createdAt,
                w.updated_at   AS updatedAt,
                (SELECT e.industry FROM enterprises e
                  WHERE e.workspace_id = w.workspace_id
                  ORDER BY e.created_at ASC LIMIT 1) AS industry
        FROM workspaces w
        WHERE (w.created_at, w.workspace_id) < (:cursorTs, :cursorId)
        ORDER BY w.created_at DESC, w.workspace_id DESC
        LIMIT :lim
        """, nativeQuery = true)
    List<WorkspaceListRow> findPageAfter(
            @Param("cursorTs") Instant cursorTs,
            @Param("cursorId") UUID    cursorId,
            @Param("lim")      int     limit);

    // Industry for one workspace (used after create/update where the controller
    // returns a single WorkspaceView). Subselect-style — first enterprise wins.
    @Query(value = """
        SELECT e.industry FROM enterprises e
        WHERE e.workspace_id = :wid
        ORDER BY e.created_at ASC LIMIT 1
        """, nativeQuery = true)
    Optional<String> findIndustryByWorkspaceId(@Param("wid") UUID workspaceId);

    // Plan code FK existence check — avoids a 500 from the DB when an unknown
    // plan_code is posted; service maps the empty result to a 4xx instead.
    @Query(value = "SELECT plan_code FROM subscription_plans WHERE plan_code = :code", nativeQuery = true)
    Optional<String> findPlanCode(@Param("code") String planCode);

    // Seed an enterprise on workspace create when industry was supplied.
    // We pick the workspace name as the enterprise name so the row is usable
    // before F-013 onboarding rewrites it via the activation flow.
    @Modifying
    @Query(value = """
        INSERT INTO enterprises (workspace_id, name, industry)
        VALUES (:wid, :name, :industry)
        """, nativeQuery = true)
    void seedEnterprise(
            @Param("wid")      UUID   workspaceId,
            @Param("name")     String name,
            @Param("industry") String industry);

    // -----------------------------------------------------------------------
    // Cross-table lookups for F-008 deep endpoints (detail / members / billing)
    // -----------------------------------------------------------------------

    /**
     * Resolve workspace_id → enterprise_id. Schema permits N enterprises per
     * workspace (FK + index, no UNIQUE), but in practice activation seeds 1:1.
     * We pick the oldest enterprise so the choice is stable across requests.
     */
    @Query(value = """
        SELECT enterprise_id FROM enterprises
        WHERE workspace_id = :wid
        ORDER BY created_at ASC LIMIT 1
        """, nativeQuery = true)
    Optional<UUID> findEnterpriseIdByWorkspaceId(@Param("wid") UUID workspaceId);

    /** Plan rate (price_vnd) for billing money calculations. */
    @Query(value = """
        SELECT price_vnd FROM subscription_plans
        WHERE plan_code = :code
        """, nativeQuery = true)
    Optional<Double> findPlanPriceVnd(@Param("code") String planCode);

    /** Plan quota (monthly_quota) — fallback when enterprise_monthly_billing has no row yet. */
    @Query(value = """
        SELECT monthly_quota FROM subscription_plans
        WHERE plan_code = :code
        """, nativeQuery = true)
    Optional<Integer> findPlanQuota(@Param("code") String planCode);

    /**
     * Current-month billing row for an enterprise (one row per billing_month).
     * Returns null fields when no row exists for the requested month.
     */
    interface BillingRow {
        Integer getUniqueCustomers();
        Integer getQuota();
        Integer getOverageCount();
    }

    @Query(value = """
        SELECT unique_customers AS uniqueCustomers,
               quota            AS quota,
               overage_count    AS overageCount
        FROM enterprise_monthly_billing
        WHERE enterprise_id  = :eid
          AND billing_month  = :month
        """, nativeQuery = true)
    Optional<BillingRow> findBillingForMonth(
            @Param("eid")   UUID            enterpriseId,
            @Param("month") java.sql.Date   billingMonth);
}
