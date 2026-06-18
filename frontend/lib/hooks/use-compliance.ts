'use client';
/**
 * EU AI Act compliance hooks (S5 moat UI, K-22 risk classification).
 * Built on useApiQuery + api(). Types mirror ai-orchestrator
 * compliance_risk.py. Routed via the existing /api/v1/compliance/** gateway
 * route (ADR-0041 / #347).
 *
 *   GET  /api/v1/compliance/ai-uses/register   tenant risk register (list)
 *   POST /api/v1/compliance/ai-uses            classify an AI-use
 */
import { api } from '@/lib/api';
import { useApiQuery } from './use-api-query';

export type RiskTier = 'prohibited' | 'high' | 'limited' | 'minimal';

export interface RiskUse {
  ai_use_id: string;
  public_ref: string;
  workflow_id: string | null;
  use_name: string;
  risk_tier: RiskTier;
  annex_iii_category: string | null;
  rationale: string | null;
  controls_required: string[];
  status: string; // 'active' | 'blocked'
  classified_at: string | null;
}

export interface ClassifyInput {
  use_name: string;
  risk_tier: RiskTier;
  workflow_id?: string;
  annex_iii_category?: string;
  rationale?: string;
}

export const useRiskRegister = (riskTier?: RiskTier) =>
  useApiQuery<RiskUse[]>(
    ['compliance', 'register', riskTier ?? 'all'],
    `/api/v1/compliance/ai-uses/register${riskTier ? `?risk_tier=${riskTier}` : ''}`,
  );

/** Classify an AI-use (K-22). Returns the registered RiskUse (status
 *  'blocked' when prohibited). Caller refetches the register after. */
export const classifyAiUse = (body: ClassifyInput) =>
  api<RiskUse>('/api/v1/compliance/ai-uses', {
    method: 'POST',
    body: JSON.stringify(body),
  });
