/**
 * FE data-hooks barrel (S0b foundation). Import per-domain query hooks from
 * here: `import { useDashboardState } from '@/lib/hooks'`.
 *
 * Add a new domain file (e.g. use-pipeline.ts, use-decisions.ts) built on
 * `useApiQuery` and re-export it below as screens get wired (S1+).
 */
export { useApiQuery } from './use-api-query';
export {
  useDashboardState,
  useNorthStar,
  useBillingSummary,
  useInsightsFeed,
  type DashboardState,
  type DashboardStateName,
  type NorthStar,
  type BillingSummary,
  type InsightsFeed,
} from './use-dashboard';
export {
  useNovCurrent,
  useNovTrend,
  useRoiSubscription,
  type NovMonthEntry,
  type NovCurrent,
  type NovTrend,
  type RoiSubscription,
} from './use-economics';
export {
  useRiskRegister,
  classifyAiUse,
  type RiskTier,
  type RiskUse,
  type ClassifyInput,
} from './use-compliance';
