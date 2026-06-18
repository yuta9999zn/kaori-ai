package com.kaorisystem.auth.repository;

import java.time.Instant;
import java.util.UUID;

/**
 * Spring Data interface projection for the F-011 enterprise billing rows.
 * Returned by {@link BillingAggregationRepository#findOne} and
 * {@link BillingAggregationRepository#findPage}. Field names match the
 * SQL column aliases in those queries.
 */
public interface EnterpriseBillingProjection {
    UUID    getEnterpriseId();
    String  getEnterpriseName();
    UUID    getWorkspaceId();
    String  getPlanCode();
    Integer getUniqueCustomers();
    Integer getQuota();
    Integer getOverageUnits();
    Double  getBasePriceVnd();
    Instant getCreatedAt();
}
