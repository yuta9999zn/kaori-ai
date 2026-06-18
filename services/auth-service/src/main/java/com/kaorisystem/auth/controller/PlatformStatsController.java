package com.kaorisystem.auth.controller;

import com.kaorisystem.auth.service.PlatformStatsService;
import com.kaorisystem.auth.service.PlatformStatsService.PlatformStats;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * F-012 — `GET /api/v1/platform/stats`.
 *
 * <p>Read-only KPI roll-up for the platform dashboard landing page.
 * Gateway already enforces SUPER_ADMIN/ADMIN/SUPPORT on
 * `/api/v1/platform/**`; no extra authz needed here.
 *
 * <p>Response shape mirrors the MSW mock the FE has been consuming since
 * PR #69 — keeping the contract identical means flipping
 * `NEXT_PUBLIC_USE_MSW` off doesn't change the dashboard.
 */
@RestController
@RequestMapping("/api/v1/platform/stats")
@RequiredArgsConstructor
public class PlatformStatsController {

    private final PlatformStatsService statsService;

    @GetMapping
    public ResponseEntity<?> getStats() {
        PlatformStats s = statsService.getStats();
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("total_workspaces",  s.totalWorkspaces());
        data.put("active_workspaces", s.activeWorkspaces());
        data.put("total_users",       s.totalUsers());
        data.put("total_runs",        s.totalRuns());
        data.put("runs_today",        s.runsToday());
        data.put("ollama_online",     s.ollamaOnline());
        data.put("kafka_lag",         s.kafkaLag());
        data.put("p95_latency_ms",    s.p95LatencyMs());
        return ResponseEntity.ok(Map.of("data", data));
    }
}
