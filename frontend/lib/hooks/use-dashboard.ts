'use client';
/**
 * Dashboard domain hooks — the first per-domain query hooks built on
 * `useApiQuery` (S0b FE foundation). Each maps 1:1 to an ai-orchestrator
 * endpoint behind the gateway (:8080). Types mirror the routers exactly
 * (no `any`). Independent queries so a slow one (insights → LLM) never
 * blocks the cheap SQL tiles — same contract as the reference page.
 *
 * Backend (via gateway):
 *   GET /api/v1/dashboard/state       — 5-state machine
 *   GET /api/v1/dashboard/north-star  — ROI headline (North Star metric)
 *   GET /api/v1/billing/summary       — K-11 quota usage
 *   GET /api/v1/insights/feed         — AI insight cards (LLM, may be slow)
 */
import { useApiQuery } from './use-api-query';

export type DashboardStateName =
  | 'no_data'
  | 'first_upload'
  | 'pending_review'
  | 'analysis_ready'
  | 'results_ready';

export interface DashboardState {
  state: DashboardStateName;
  run_id: string | null;
  pipeline_status?: string;
  analysis_run_id?: string | null;
  templates_run?: string[];
  kpis?: Array<{ template: string; title: string; data: Record<string, unknown> }>;
}

export interface NorthStar {
  total_at_risk_vnd: number;
  resolved_vnd: number;
  resolution_rate_pct: number;
  actioned_count: number;
  at_risk_count: number;
}

export interface BillingSummary {
  month: string | null;
  unique_customers: number;
  monthly_quota: number | null;
  plan_code: string;
  usage_pct: number;
}

export interface InsightsFeed {
  insights: Array<{ id: string; title: string; body: string; category: string }>;
  note?: string;
}

export const useDashboardState = () =>
  useApiQuery<DashboardState>(['dashboard', 'state'], '/api/v1/dashboard/state');

export const useNorthStar = () =>
  useApiQuery<NorthStar>(['dashboard', 'north-star'], '/api/v1/dashboard/north-star');

export const useBillingSummary = () =>
  useApiQuery<BillingSummary>(['dashboard', 'billing'], '/api/v1/billing/summary');

export const useInsightsFeed = (limit = 5) =>
  useApiQuery<InsightsFeed>(['dashboard', 'insights', limit], `/api/v1/insights/feed?limit=${limit}`);
