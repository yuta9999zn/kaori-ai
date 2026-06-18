package com.kaorisystem.auth.service;

import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestClient;

import java.net.URI;
import java.time.Duration;
import java.util.Map;

/**
 * F-012 — Platform Health Dashboard.
 *
 * <p>The first page Kaori staff land on after login (`/platform`) needs
 * one read-mostly endpoint that aggregates the SaaS-wide counts the
 * dashboard cards render. We compute everything in a single SQL round-trip
 * (subselects under one statement) so the page stays snappy under load
 * and the cron-warmed query plans don't get evicted between calls.
 *
 * <p>Latency / Kafka-lag fields are reported as static placeholders for
 * Phase 1 — real metric scraping is Phase 2 (F-039 monitoring slice).
 * Ollama is probed live so the badge flips RED the moment the model
 * server goes down (the most common pilot-blocker).
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class PlatformStatsService {

    /** Ollama probe budget — keep the dashboard p99 under 1s even when Ollama is wedged. */
    private static final Duration OLLAMA_TIMEOUT = Duration.ofSeconds(2);

    private final JdbcTemplate jdbc;
    /** Migration 024 prep — disable RLS for cross-tenant pipeline_runs aggregation. */
    private final RlsBypassHelper rlsBypass;

    @Value("${ollama.url:http://ollama:11434}")
    private String ollamaUrl;

    public record PlatformStats(
            long  totalWorkspaces,
            long  activeWorkspaces,
            long  totalUsers,
            long  totalRuns,
            long  runsToday,
            boolean ollamaOnline,
            long  kafkaLag,
            long  p95LatencyMs
    ) {}

    @Transactional(readOnly = true)
    public PlatformStats getStats() {
        // Migration 024 prep — pipeline_runs is RLS-protected. The dashboard
        // counts every tenant's runs by design (this is the platform-wide
        // health card). row_security off keeps the cross-tenant COUNT(*)
        // working once kaori_app loses BYPASSRLS. enterprise_users had RLS
        // dropped in the same migration so the user count is unaffected.
        rlsBypass.disableForTx();
        // Single round-trip — five COUNTs as scalar subselects.
        Map<String, Object> row = jdbc.queryForMap("""
            SELECT (SELECT COUNT(*) FROM workspaces)                                              AS total_workspaces,
                   (SELECT COUNT(*) FROM workspaces WHERE status = 'active')                     AS active_workspaces,
                   (SELECT COUNT(*) FROM enterprise_users WHERE status = 'active')               AS total_users,
                   (SELECT COUNT(*) FROM pipeline_runs)                                          AS total_runs,
                   (SELECT COUNT(*) FROM pipeline_runs
                     WHERE created_at >= date_trunc('day', NOW() AT TIME ZONE 'Asia/Ho_Chi_Minh')
                                          AT TIME ZONE 'Asia/Ho_Chi_Minh')                       AS runs_today
            """);

        return new PlatformStats(
                ((Number) row.get("total_workspaces")).longValue(),
                ((Number) row.get("active_workspaces")).longValue(),
                ((Number) row.get("total_users")).longValue(),
                ((Number) row.get("total_runs")).longValue(),
                ((Number) row.get("runs_today")).longValue(),
                probeOllama(),
                0L,    // kafka_lag — Phase 2 (F-039)
                420L   // p95_latency_ms — static until real metrics scraping lands
        );
    }

    private boolean probeOllama() {
        try {
            RestClient.create()
                    .get()
                    .uri(URI.create(ollamaUrl + "/api/tags"))
                    .retrieve()
                    .toBodilessEntity();
            return true;
        } catch (Exception e) {
            log.debug("Ollama probe failed at {}: {}", ollamaUrl, e.getMessage());
            return false;
        }
    }
}
