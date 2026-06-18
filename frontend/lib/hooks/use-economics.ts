'use client';
/**
 * Economics domain hooks (S3 moat UI) — NOV (Net Operating Value: the net
 * VND the AI generates = revenue attributed − cost to run) + ROI-Hybrid
 * subscription state. Built on useApiQuery. Types mirror ai-orchestrator
 * economics.py / roi_billing.py exactly.
 *
 * Money is Decimal-as-str on the wire (precision-safe, see economics.py) —
 * parse with Number() only at display time via fmtVND/fmtVNDShort.
 *
 * Backend (ai-orchestrator, via gateway :8080 — needs the /economics route):
 *   GET /api/v1/economics/nov/current        latest digest + classification
 *   GET /api/v1/economics/nov/trend?months=N last N months (oldest→newest)
 *   GET /api/v1/economics/roi/subscription   ROI-Hybrid opt-in state
 */
import { useApiQuery } from './use-api-query';

/** One month's NOV digest (all VND fields are Decimal-as-str). */
export interface NovMonthEntry {
  month_start: string; // 'YYYY-MM-01'
  revenue_vnd: string;
  cost_vnd: string;
  nov_vnd: string;
  revenue_method: string;
  revenue_confidence: string;
  people_cost_vnd: string;
  ai_cost_vnd: string;
  infra_cost_vnd: string;
  integration_cost_vnd: string;
  is_negative: boolean;
  revision: number;
}

export interface NovCurrent {
  current: NovMonthEntry | null;
  classification: 'positive' | 'negative' | 'no_data';
}

export interface NovTrend {
  months: NovMonthEntry[];
}

export interface RoiSubscription {
  enterprise_id: string;
  opted_in: boolean;
  opted_in_at: string | null;
  opted_out_at: string | null;
  eligibility_confirmed_at: string | null;
  months_of_data: number;
  eligibility_met: boolean;
  notes: string | null;
}

export const useNovCurrent = () =>
  useApiQuery<NovCurrent>(['economics', 'nov', 'current'], '/api/v1/economics/nov/current');

export const useNovTrend = (months = 6) =>
  useApiQuery<NovTrend>(['economics', 'nov', 'trend', months], `/api/v1/economics/nov/trend?months=${months}`);

export const useRoiSubscription = () =>
  useApiQuery<RoiSubscription>(['economics', 'roi', 'subscription'], '/api/v1/economics/roi/subscription');
