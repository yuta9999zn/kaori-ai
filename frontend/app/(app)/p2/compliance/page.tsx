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

const TIER_META: Record<RiskTier, { label: string; tone: BadgeTone; desc: string }> = {
  prohibited: { label: 'Bị cấm', tone: 'danger', desc: 'Vi phạm Điều 5 — Kaori chặn xuất bản & chạy.' },
  high: { label: 'Rủi ro cao', tone: 'warning', desc: 'Bật đầy đủ kiểm soát: giám sát con người, model card, giám sát hậu kiểm, nhật ký kiểm toán.' },
  limited: { label: 'Rủi ro hạn chế', tone: 'info', desc: 'Công bố minh bạch (Điều 50) + nhật ký kiểm toán.' },
  minimal: { label: 'Rủi ro tối thiểu', tone: 'success', desc: 'Không ràng buộc bắt buộc.' },
};
const TIER_ORDER: RiskTier[] = ['prohibited', 'high', 'limited', 'minimal'];

// Keys are the exact control codes the BE returns (compliance_controls.py).
const CONTROL_VI: Record<string, string> = {
  'K-23_HUMAN_OVERSIGHT': 'Giám sát con người (Điều 14)',
  'K-24_TRANSPARENCY': 'Công bố minh bạch (Điều 50)',
  'K-25_MODEL_CARD': 'Hồ sơ kỹ thuật / model card (Điều 11)',
  'K-26_MONITORING': 'Giám sát hậu kiểm (Điều 72)',
  'K-6_AUDIT_LOG': 'Nhật ký kiểm toán quyết định (K-6)',
};
const controlLabel = (c: string) => CONTROL_VI[c] ?? c;

export default function CompliancePage() {
  const registerQ = useRiskRegister();

  return (
    <>
      <PageHeader
        title="Tuân thủ EU AI Act"
        description="Phân loại mức rủi ro cho mỗi cách dùng AI và xem các kiểm soát bắt buộc kèm theo. Mức 'Bị cấm' sẽ bị Kaori chặn xuất bản và chạy."
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {/* Tier reference */}
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {TIER_ORDER.map((t) => (
            <div key={t} className="rounded-lg border border-subtle/60 p-3">
              <Badge tone={TIER_META[t].tone}>{TIER_META[t].label}</Badge>
              <p className="mt-2 text-xs text-ink-muted">{TIER_META[t].desc}</p>
            </div>
          ))}
        </div>

        {/* Classify form */}
        <ClassifyForm onClassified={() => registerQ.refetch()} />

        {/* Register */}
        <Card>
          <CardHeader><CardTitle>Sổ đăng ký rủi ro AI</CardTitle></CardHeader>
          <CardContent>
            {registerQ.isLoading ? (
              <div className="space-y-2">
                {[0, 1, 2].map((i) => <Skeleton key={i} className="h-12 w-full rounded" />)}
              </div>
            ) : registerQ.isError ? (
              <div className="flex flex-col items-start gap-2 py-4">
                <p className="text-sm text-danger-700">Không tải được sổ đăng ký — {registerQ.error.message}</p>
                <button onClick={() => registerQ.refetch()} className="inline-flex items-center gap-1.5 rounded-lg border border-subtle px-3 py-1.5 text-sm hover:bg-canvas">
                  <RefreshCw className="h-4 w-4" /> Thử lại
                </button>
              </div>
            ) : !registerQ.data?.length ? (
              <EmptyState
                icon={ShieldCheck}
                title="Chưa có cách dùng AI nào được phân loại"
                description="Dùng biểu mẫu phía trên để phân loại cách dùng AI đầu tiên — Kaori sẽ tự gắn các kiểm soát bắt buộc theo mức rủi ro."
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
  const [useName, setUseName] = useState('');
  const [tier, setTier] = useState<RiskTier>('limited');
  const [annex, setAnnex] = useState('');
  const [rationale, setRationale] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<RiskUse | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (!useName.trim()) { setError('Vui lòng nhập tên cách dùng AI.'); return; }
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
      setError((e as ApiError).message ?? 'Phân loại thất bại.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader><CardTitle>Phân loại cách dùng AI</CardTitle></CardHeader>
      <CardContent className="space-y-3">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-ink-muted">Tên cách dùng AI *</span>
            <input
              value={useName} onChange={(e) => setUseName(e.target.value)}
              placeholder="VD: Chấm điểm tín dụng khách hàng"
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">Mức rủi ro *</span>
            <select
              value={tier} onChange={(e) => setTier(e.target.value as RiskTier)}
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            >
              {TIER_ORDER.map((t) => <option key={t} value={t}>{TIER_META[t].label}</option>)}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">Nhóm Annex III (tuỳ chọn)</span>
            <input
              value={annex} onChange={(e) => setAnnex(e.target.value)}
              placeholder="VD: credit_scoring"
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-ink-muted">Lý do (tuỳ chọn)</span>
            <input
              value={rationale} onChange={(e) => setRationale(e.target.value)}
              placeholder="Vì sao xếp mức này"
              className="mt-1 w-full rounded-lg border border-subtle px-3 py-2 text-sm"
            />
          </label>
        </div>

        {tier === 'prohibited' && (
          <p className="flex items-center gap-1.5 text-xs text-danger-700">
            <AlertTriangle className="h-4 w-4" /> Mức "Bị cấm" sẽ được ghi nhận với trạng thái <strong>blocked</strong> — không thể xuất bản/chạy.
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
                Đã ghi nhận {result.public_ref} — {TIER_META[result.risk_tier]?.label ?? result.risk_tier}
                {result.status === 'blocked' ? ' (BỊ CHẶN)' : ''}
              </span>
            </div>
            {result.controls_required.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {result.controls_required.map((c) => (
                  <Badge key={c} tone="info">{controlLabel(c)}</Badge>
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
            {busy ? 'Đang phân loại…' : 'Phân loại + ghi sổ'}
          </button>
        </div>
      </CardContent>
    </Card>
  );
}

function RegisterTable({ rows }: { rows: RiskUse[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-subtle text-left text-xs text-ink-muted">
            <th className="px-3 py-2 font-medium">Mã</th>
            <th className="px-3 py-2 font-medium">Cách dùng AI</th>
            <th className="px-3 py-2 font-medium">Mức rủi ro</th>
            <th className="px-3 py-2 font-medium">Trạng thái</th>
            <th className="px-3 py-2 font-medium">Kiểm soát bắt buộc</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.ai_use_id} className="border-b border-subtle/50 align-top">
              <td className="px-3 py-2 font-mono text-xs text-ink-muted">{r.public_ref}</td>
              <td className="px-3 py-2 text-[#2E2A24]">{r.use_name}</td>
              <td className="px-3 py-2">
                <Badge tone={TIER_META[r.risk_tier]?.tone ?? 'neutral'}>
                  {TIER_META[r.risk_tier]?.label ?? r.risk_tier}
                </Badge>
              </td>
              <td className="px-3 py-2">
                <Badge tone={r.status === 'blocked' ? 'danger' : 'success'}>
                  {r.status === 'blocked' ? 'Bị chặn' : 'Đang áp dụng'}
                </Badge>
              </td>
              <td className="px-3 py-2">
                {r.controls_required.length ? (
                  <div className="flex flex-wrap gap-1">
                    {r.controls_required.map((c) => (
                      <span key={c} className="rounded bg-canvas px-1.5 py-0.5 text-[11px] text-[#6B6357]">{controlLabel(c)}</span>
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
