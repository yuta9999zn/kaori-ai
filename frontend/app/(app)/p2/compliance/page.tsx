'use client';

/**
 * P2 — Tuân thủ EU AI Act (K-22 risk classification register).  S5 moat UI.
 *
 * Trust-first, conformity-ready (ADR-0041): make every registered AI-use's
 * risk tier + required controls visible, and let a manager classify a new
 * AI-use. `prohibited` is blocked at publish/run (status='blocked').
 *
 * Wired to ai-orchestrator compliance_risk.py via the existing
 * /api/v1/compliance/** gateway route. Follows the dashboard/overview
 * reference pattern (loading/error/empty, explicit types, VN language).
 * NOTE: the K-26 incident console is admin-gated (SUPER_ADMIN/ADMIN) and
 * lives in the platform portal — not here.
 */
import { useState } from 'react';
import { ShieldCheck, ShieldAlert, RefreshCw, AlertTriangle, CheckCircle2 } from 'lucide-react';

import {
  useRiskRegister, classifyAiUse,
  type RiskTier, type RiskUse, type ClassifyInput,
} from '@/lib/hooks';
import type { ApiError } from '@/lib/api';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { EmptyState } from '@/components/ui/empty-state';
import { Skeleton } from '@/components/ui/skeleton';
import { Badge, type BadgeTone } from '@/components/ui/badge';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';

type Translate = (key: string, params?: Record<string, string | number>) => string;

function buildTierMeta(t: Translate): Record<RiskTier, { label: string; tone: BadgeTone; desc: string }> {
  return {
    prohibited: { label: t('compliancePage.tierProhibitedLabel'), tone: 'danger', desc: t('compliancePage.tierProhibitedDesc') },
    high: { label: t('compliancePage.tierHighLabel'), tone: 'warning', desc: t('compliancePage.tierHighDesc') },
    limited: { label: t('compliancePage.tierLimitedLabel'), tone: 'info', desc: t('compliancePage.tierLimitedDesc') },
    minimal: { label: t('compliancePage.tierMinimalLabel'), tone: 'success', desc: t('compliancePage.tierMinimalDesc') },
  };
}
const TIER_ORDER: RiskTier[] = ['prohibited', 'high', 'limited', 'minimal'];

// Keys are the exact control codes the BE returns (compliance_controls.py).
function controlLabel(t: Translate, c: string): string {
  const map: Record<string, string> = {
    'K-23_HUMAN_OVERSIGHT': t('compliancePage.controlHumanOversight'),
    'K-24_TRANSPARENCY': t('compliancePage.controlTransparency'),
    'K-25_MODEL_CARD': t('compliancePage.controlModelCard'),
    'K-26_MONITORING': t('compliancePage.controlMonitoring'),
    'K-6_AUDIT_LOG': t('compliancePage.controlAuditLog'),
  };
  return map[c] ?? c;
}

export default function CompliancePage() {
  const t = useT();
  const registerQ = useRiskRegister();
  const tierMeta = buildTierMeta(t);

  return (
    <>
      <PageHeader
        title={t('compliancePage.title')}
        description={t('compliancePage.description')}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {/* Tier reference */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TIER_ORDER.map((tier) => (
            <div key={tier} className="rounded-lg border border-subtle/60 p-3">
              <Badge tone={tierMeta[tier].tone}>{tierMeta[tier].label}</Badge>
              <p className="mt-2 text-xs text-ink-muted">{tierMeta[tier].desc}</p>
            </div>
          ))}
        </div>

        {/* Classify form */}
        <ClassifyForm onClassified={() => registerQ.refetch()} />

        {/* Register */}
        <Card>
          <CardHeader><CardTitle>{t('compliancePage.registerTitle')}</CardTitle></CardHeader>
          <CardContent>
            {registerQ.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 w-full rounded" />)}
              </div>
            ) : registerQ.isError ? (
              <div className="flex flex-col items-start gap-2 py-4">
                <p className="text-sm text-danger-700">{t('compliancePage.loadError', { message: registerQ.error.message })}</p>
                <button onClick={() => registerQ.refetch()} className="inline-flex items-center gap-1.5 rounded-lg border border-subtle px-3 py-1.5 text-sm hover:bg-canvas">
                  <RefreshCw className="h-4 w-4" /> {t('compliancePage.retry')}
                </button>
              </div>
            ) : !registerQ.data?.length ? (
              <EmptyState
                icon={ShieldCheck}
                title={t('compliancePage.emptyTitle')}
                description={t('compliancePage.emptyDesc')}
              />
            ) : (
              <RegisterTable rows={registerQ.data} />
            )}
          </CardContent>
        </Card>
      </div>
    </>
  );
}

// ── Subcomponents ──────────────────────────────────────────────────────

function ClassifyForm({ onClassified }: { onClassified: () => void }) {
  const t = useT();
  const tierMeta = buildTierMeta(t);
  const [useName, setUseName] = useState('');
  const [tier, setTier] = useState<RiskTier>('limited');
  const [annex, setAnnex] = useState('');
  const [rationale, setRationale] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RiskUse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!useName.trim()) { setError(t('compliancePage.errNameRequired')); return; }
    setBusy(true); setError(null); setResult(null);
    try {
      const body: ClassifyInput = {
        use_name: useName.trim(),
        risk_tier: tier,
        annex_iii_category: annex.trim() || undefined,
        rationale: rationale.trim() || undefined,
      };
      const r = await classifyAiUse(body);
      setResult(r);
      setUseName(''); setAnnex(''); setRationale('');
      onClassified();
    } catch (e) {
      setError((e as ApiError).message ?? t('compliancePage.errClassifyFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>{t('compliancePage.classifyTitle')}</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-ink-muted">{t('compliancePage.useNameLabel')}</span>
            <input
              value={useName} onChange={(e) => setUseName(e.target.value)}
              placeholder={t('compliancePage.useNamePlaceholder')}
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">{t('compliancePage.riskTierLabel')}</span>
            <select
              value={tier} onChange={(e) => setTier(e.target.value as RiskTier)}
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            >
              {TIER_ORDER.map((opt) => <option key={opt} value={opt}>{tierMeta[opt].label}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">{t('compliancePage.annexLabel')}</span>
            <input
              value={annex} onChange={(e) => setAnnex(e.target.value)}
              placeholder={t('compliancePage.annexPlaceholder')}
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">{t('compliancePage.rationaleLabel')}</span>
            <input
              value={rationale} onChange={(e) => setRationale(e.target.value)}
              placeholder={t('compliancePage.rationalePlaceholder')}
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            />
          </label>
        </div>

        {tier === 'prohibited' && (
          <p className="flex items-center gap-1.5 text-xs text-danger-700">
            <AlertTriangle className="h-4 w-4" /> {t('compliancePage.prohibitedWarningPre')} <strong>blocked</strong> {t('compliancePage.prohibitedWarningPost')}
          </p>
        )}

        {error && <p className="text-sm text-danger-700">{error}</p>}

        {result && (
          <div className={`rounded-lg border p-3 ${result.status === 'blocked' ? 'border-danger-200/60 bg-danger-50/40' : 'border-emerald-200/60 bg-emerald-50/40'}`}>
            <div className="flex items-center gap-2 text-sm">
              {result.status === 'blocked'
                ? <ShieldAlert className="h-4 w-4 text-danger-700" />
                : <CheckCircle2 className="h-4 w-4 text-emerald-700" />}
              <span className="font-medium text-[#2E2A24]">
                {t('compliancePage.recordedPrefix', { ref: result.public_ref, tier: tierMeta[result.risk_tier]?.label ?? result.risk_tier })}
                {result.status === 'blocked' ? t('compliancePage.blockedSuffix') : ''}
              </span>
            </div>
            {result.controls_required.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {result.controls_required.map((c) => (
                  <Badge key={c} tone="info">{controlLabel(t, c)}</Badge>
                ))}
              </div>
            )}
          </div>
        )}

        <div>
          <button
            onClick={submit} disabled={busy}
            className="inline-flex items-center gap-1.5 rounded-lg bg-brand-700 px-4 py-2 text-sm font-medium text-white hover:bg-brand-800 disabled:opacity-60"
          >
            {busy ? t('compliancePage.classifying') : t('compliancePage.classifySubmit')}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

function RegisterTable({ rows }: { rows: RiskUse[] }) {
  const t = useT();
  const tierMeta = buildTierMeta(t);
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-subtle text-left text-xs text-ink-muted">
            <th className="px-3 py-2 font-medium">{t('compliancePage.colCode')}</th>
            <th className="px-3 py-2 font-medium">{t('compliancePage.colUseName')}</th>
            <th className="px-3 py-2 font-medium">{t('compliancePage.colRiskTier')}</th>
            <th className="px-3 py-2 font-medium">{t('compliancePage.colStatus')}</th>
            <th className="px-3 py-2 font-medium">{t('compliancePage.colControls')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ai_use_id} className="border-b border-subtle/50 align-top">
              <td className="px-3 py-2 font-mono text-xs text-ink-muted">{r.public_ref}</td>
              <td className="px-3 py-2 text-[#2E2A24]">{r.use_name}</td>
              <td className="px-3 py-2">
                <Badge tone={tierMeta[r.risk_tier]?.tone ?? 'neutral'}>
                  {tierMeta[r.risk_tier]?.label ?? r.risk_tier}
                </Badge>
              </td>
              <td className="px-3 py-2">
                <Badge tone={r.status === 'blocked' ? 'danger' : 'success'}>
                  {r.status === 'blocked' ? t('compliancePage.statusBlocked') : t('compliancePage.statusActive')}
                </Badge>
              </td>
              <td className="px-3 py-2">
                {r.controls_required.length ? (
                  <div className="flex flex-wrap gap-1">
                    {r.controls_required.map((c) => (
                      <span key={c} className="rounded bg-canvas px-1.5 py-0.5 text-[11px] text-[#6B6357]">{controlLabel(t, c)}</span>
                    ))}
                  </div>
                ) : <span className="text-xs text-ink-muted">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
