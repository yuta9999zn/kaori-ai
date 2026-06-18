'use client';

// ============================================================================
// 48. /p2/reports/auto — Auto Report Configuration (F-038 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Cấu hình báo cáo tự động: chọn Gold dataset, mục tiêu báo cáo, lịch chạy,
// người nhận → Kaori AI sinh narrative + biểu đồ qua llm_router (K-3 + K-4
// + K-5).
//
// Wires `POST /api/v1/reports/generate` (PR #113) using the built-in
// monthly_summary template. Goal/cadence/dataset are packed into `params{}`
// for the template's system prompt (Issue #3 output_schema enforces the
// kpi_overview/trends/top_risks/recommendations shape). Single recipient v0
// — fan-out distribution is a follow-up PR.
//
// Gold dataset picker still calls `/api/v1/data/gold/datasets` which 404s in
// dev — it falls back to MOCK_DATASETS. That endpoint belongs to a separate
// data-exploration feature surface (Phase 2).
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Sparkles, Activity, TrendingUp, LayoutGrid, Crown, Users, Clock,
  CalendarCheck, Mail, Save, Play, ArrowLeft, ShieldCheck, Loader2,
  CheckCircle2, AlertTriangle,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

interface GoldDataset {
  id:     string;
  name:   string;
  domain: string;
  rows:   number;
}

// Stable id of the built-in monthly_summary template seeded by migration 027.
const BUILT_IN_MONTHLY_SUMMARY_ID = '00000000-0000-0000-0000-000000000001';

type ReportGoal = 'performance' | 'trend' | 'segment' | 'executive';

interface GoalMeta {
  code:        ReportGoal;
  label:       string;
  description: string;
  icon:        any;
}

const GOALS: GoalMeta[] = [
  { code: 'performance', label: 'Tổng hợp KPI',         description: 'Snapshot KPI chính + delta so kỳ trước.',          icon: Activity },
  { code: 'trend',       label: 'Phân tích xu hướng',   description: 'Trend dài hạn + dự báo đơn giản (linear).',         icon: TrendingUp },
  { code: 'segment',     label: 'So sánh phân khúc',     description: 'Biến thiên theo vùng / nhóm khách / kênh.',         icon: LayoutGrid },
  { code: 'executive',   label: 'Tóm tắt cho ban GĐ',   description: 'Narrative ngắn + 3 đề xuất hành động.',             icon: Crown },
];

type Cadence = 'daily' | 'weekly' | 'monthly';

interface CadenceMeta {
  code:    Cadence;
  label:   string;
  cron:    string;
  helper:  string;
}

const CADENCES: CadenceMeta[] = [
  { code: 'daily',   label: 'Hàng ngày',  cron: '0 7 * * *',  helper: 'Mỗi sáng 07:00 ICT.' },
  { code: 'weekly',  label: 'Hàng tuần',  cron: '0 7 * * 1',  helper: 'Mỗi sáng thứ Hai 07:00 ICT.' },
  { code: 'monthly', label: 'Hàng tháng', cron: '0 7 1 * *',  helper: 'Ngày 1 hàng tháng, 07:00 ICT.' },
];

const MOCK_DATASETS: GoldDataset[] = [
  { id: 'ds_revenue',  name: 'monthly_revenue_gold',       domain: 'Tài chính',  rows: 124_530 },
  { id: 'ds_customer', name: 'customer_behavior_metrics',  domain: 'Sản phẩm',   rows:  68_242 },
  { id: 'ds_market',   name: 'marketing_roi_performance',  domain: 'Marketing',  rows:  41_088 },
  { id: 'ds_ops',      name: 'operations_kpi_daily',       domain: 'Vận hành',   rows: 312_104 },
];

// ============================================================================
// Page
// ============================================================================

export default function ReportAutoPage() {
  const [datasets, setDatasets] = useState<GoldDataset[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [success,  setSuccess]  = useState<string | null>(null);

  // Form state
  const [name,      setName]      = useState('Báo cáo doanh thu hàng tuần');
  const [datasetId, setDatasetId] = useState<string>('');
  const [goal,      setGoal]      = useState<ReportGoal>('performance');
  const [cadence,   setCadence]   = useState<Cadence>('weekly');
  const [recipients, setRecipients] = useState('manager@acme.vn');
  const [allowExternal, setAllowExternal] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: GoldDataset[] }>('/api/v1/data/gold/datasets');
        if (!cancelled) {
          setDatasets(data.items ?? []);
          if ((data.items ?? []).length > 0) setDatasetId(data.items[0].id);
        }
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          setDatasets(MOCK_DATASETS);
          setDatasetId(MOCK_DATASETS[0].id);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const cadenceMeta = useMemo(() => CADENCES.find((c) => c.code === cadence)!, [cadence]);
  const recipientList = useMemo(
    () => recipients.split(/[,\n]/).map((s) => s.trim()).filter(Boolean),
    [recipients],
  );
  const formValid = name.trim().length >= 3 && datasetId !== '' && recipientList.length > 0;

  async function onSubmit(action: 'save' | 'run') {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      // BE accepts a single owner_email per report (v0). Use the first recipient
      // and pack the rest into params for the template prompt; fan-out is a
      // follow-up PR per the F-038 spec (notification dispatcher → multi-channel).
      const [primaryRecipient, ...additionalRecipients] = recipientList;
      const resp = await api<{ report_id: string; status: string }>(
        '/api/v1/reports/generate',
        {
          method: 'POST',
          body: JSON.stringify({
            template_id:  BUILT_IN_MONTHLY_SUMMARY_ID,
            title:        name,
            owner_email:  primaryRecipient,
            params: {
              goal,
              cadence,
              schedule_cron:           cadenceMeta.cron,
              dataset_id:              datasetId,
              consent_external:        allowExternal,
              additional_recipients:   additionalRecipients,
              triggered_via:           action === 'run' ? 'auto_form_run_now' : 'auto_form_save',
            },
          }),
        },
      );
      // 'save' acts identically to 'run' under v0 — no scheduler service exists
      // yet, so every submission queues one report immediately. Phase 2 follow-up
      // wires schedule_cron to a runner.
      setSuccess(
        `Đã xếp hàng báo cáo (id: ${resp.report_id}). Trạng thái sẽ chuyển ` +
        `queued → running → ready trong 10–30 giây. Email gửi tới ${primaryRecipient}` +
        (additionalRecipients.length > 0
          ? ` (fan-out tới ${additionalRecipients.length} người nhận khác sẽ wire ở PR phân phối kế tiếp).`
          : '.'),
      );
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Báo cáo tự động"
        description="Cấu hình AI sinh báo cáo định kỳ. Phase 2 (F-038)."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-038</Badge>
            <a href="/p2/reports">
              <Button variant="tertiary" size="md">
                <ArrowLeft className="w-4 h-4 mr-2" /> Về danh sách
              </Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  problem.status && problem.status >= 500 ? 'Lỗi máy chủ' : problem.title,
              detail: `${problem.detail ?? ''} (Form vẫn hoạt động — gold dataset picker fallback dùng MOCK_DATASETS; submit sẽ thử lại endpoint thật.)`.trim(),
            }}
          />
        )}
        {success && <SuccessBanner message={success} />}

        {/* Section 1 — Tên báo cáo + nguồn */}
        <Section
          step={1}
          title="Nguồn dữ liệu"
          description="Chọn Gold dataset làm cơ sở. Bronze/Silver không dùng được — cần đã đi qua engineering Gold (K-2)."
        >
          <Input
            label="Tên báo cáo"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="VD: Doanh thu tuần khu vực miền Nam"
            helperText="Tối thiểu 3 ký tự."
            error={name.length > 0 && name.length < 3}
          />
          <div className="mt-4 space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">Gold dataset</label>
            {loading ? (
              <div className="flex items-center text-sm text-[var(--text-secondary)] py-3">
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Đang tải dataset...
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {datasets.map((d) => (
                  <DatasetCard
                    key={d.id}
                    dataset={d}
                    selected={datasetId === d.id}
                    onSelect={() => setDatasetId(d.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </Section>

        {/* Section 2 — Mục tiêu */}
        <Section step={2} title="Mục tiêu báo cáo" description="Kaori AI sẽ chọn template narrative + chart phù hợp.">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {GOALS.map((g) => (
              <GoalCard key={g.code} goal={g} selected={goal === g.code} onSelect={() => setGoal(g.code)} />
            ))}
          </div>
        </Section>

        {/* Section 3 — Lịch chạy */}
        <Section step={3} title="Lịch chạy" description="Cron expression hiển thị bên dưới. Kaori cron-runner xử lý lúc 02:00-08:00 ICT (idle window).">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {CADENCES.map((c) => (
              <button
                key={c.code}
                onClick={() => setCadence(c.code)}
                className={cn(
                  'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
                  cadence === c.code
                    ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
                    : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
                )}
              >
                <div className="flex items-center gap-2 mb-1">
                  <Clock className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  <span className="font-medium text-sm text-[var(--text-primary)]">{c.label}</span>
                </div>
                <p className="text-xs text-[var(--text-secondary)]">{c.helper}</p>
                <p className="text-[11px] text-[var(--text-secondary)]/80 font-mono mt-2">{c.cron}</p>
              </button>
            ))}
          </div>
        </Section>

        {/* Section 4 — Người nhận */}
        <Section step={4} title="Người nhận" description="Email cá nhân cách nhau bởi dấu phẩy hoặc xuống dòng.">
          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">Danh sách email</label>
            <textarea
              value={recipients}
              onChange={(e) => setRecipients(e.target.value)}
              rows={3}
              placeholder="manager@acme.vn, ops@acme.vn"
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-primary)] placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
            />
            {recipientList.length > 0 && (
              <p className="text-xs text-[var(--text-secondary)]">
                <Mail className="w-3.5 h-3.5 inline mr-1" />
                Sẽ gửi tới {recipientList.length} người: {recipientList.join(', ')}
              </p>
            )}
          </div>
        </Section>

        {/* Section 5 — Consent */}
        <Section
          step={5}
          title="Quyền truy cập AI ngoài"
          description="Mặc định Qwen 2.5 nội bộ — không gửi dữ liệu ra ngoài. Chỉ bật khi cần narrative chất lượng cao."
        >
          <label className="flex items-start gap-3 p-3 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] cursor-pointer hover:border-[var(--primary-gold)]/40 transition-colors">
            <input
              type="checkbox"
              checked={allowExternal}
              onChange={(e) => setAllowExternal(e.target.checked)}
              className="mt-0.5 w-4 h-4 accent-[var(--primary-gold)]"
            />
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">
                Cho phép gọi AI ngoài (Claude / GPT-4o) sau khi che PII
              </p>
              <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
                K-4: workspace cần bật <code>consent_external=true</code>. K-5: PII (email · số ĐT · CCCD)
                được mask thành <span className="font-mono">&lt;EMAIL_1&gt;</span> trước khi gửi. K-3: mọi
                call vẫn đi qua <span className="font-mono">llm_router.py</span> để audit.
              </p>
            </div>
          </label>
        </Section>

        {/* Action footer */}
        <div className="sticky bottom-0 bg-[var(--bg-card)]/95 backdrop-blur-sm border-t border-[var(--border-color)] -mx-6 lg:-mx-8 px-6 lg:px-8 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
            <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            Đã ký theo K-13 Idempotency-Key — gửi lại an toàn.
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="md"
              onClick={() => onSubmit('save')}
              disabled={!formValid || submitting}
              isLoading={submitting}
            >
              <Save className="w-4 h-4 mr-2" /> Lưu cấu hình
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={() => onSubmit('run')}
              disabled={!formValid || submitting}
              isLoading={submitting}
            >
              <Play className="w-4 h-4 mr-2" /> Lưu + chạy ngay
            </Button>
          </div>
        </div>

        {/* Recent runs preview */}
        <RecentRunsPreview />
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function Section({
  step, title, description, children,
}: { step: number; title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm">
      <div className="flex items-start gap-3 mb-4">
        <div className="w-7 h-7 rounded-full bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center shrink-0">
          <span className="text-xs font-semibold text-[var(--primary-gold-dark)]">{step}</span>
        </div>
        <div>
          <h3 className="font-serif text-lg text-[var(--text-primary)]">{title}</h3>
          <p className="text-xs text-[var(--text-secondary)] mt-0.5 leading-relaxed">{description}</p>
        </div>
      </div>
      <div>{children}</div>
    </section>
  );
}

function DatasetCard({
  dataset, selected, onSelect,
}: { dataset: GoldDataset; selected: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'text-left p-3 rounded-md-custom border transition-all',
        selected
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-mono text-sm text-[var(--text-primary)]">{dataset.name}</p>
          <p className="text-xs text-[var(--text-secondary)] mt-1">
            {dataset.domain} · {dataset.rows.toLocaleString('vi-VN')} dòng
          </p>
        </div>
        {selected && <CheckCircle2 className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />}
      </div>
    </button>
  );
}

function GoalCard({
  goal, selected, onSelect,
}: { goal: GoalMeta; selected: boolean; onSelect: () => void }) {
  const Icon = goal.icon;
  return (
    <button
      onClick={onSelect}
      className={cn(
        'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
        selected
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center mb-3">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
      </div>
      <p className="font-medium text-sm text-[var(--text-primary)]">{goal.label}</p>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{goal.description}</p>
    </button>
  );
}

function RecentRunsPreview() {
  const RUNS = [
    { id: 'run_99', cadence: 'weekly', status: 'success', when: '2026-04-29 07:00', delivered: 4 },
    { id: 'run_98', cadence: 'weekly', status: 'success', when: '2026-04-22 07:00', delivered: 4 },
    { id: 'run_97', cadence: 'weekly', status: 'failed',  when: '2026-04-15 07:00', delivered: 0 },
  ];
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-3">
        <CalendarCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">Lần chạy gần đây</h3>
        <Badge variant="default">3 lần</Badge>
      </div>
      <div className="divide-y divide-[var(--border-color)]/60">
        {RUNS.map((r) => (
          <div key={r.id} className="py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3 min-w-0">
              {r.status === 'success' ? (
                <CheckCircle2 className="w-4 h-4 text-[var(--state-success)] shrink-0" />
              ) : (
                <AlertTriangle className="w-4 h-4 text-[var(--state-error)] shrink-0" />
              )}
              <div className="min-w-0">
                <p className="text-sm text-[var(--text-primary)]">{r.when}</p>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                  {r.cadence === 'weekly' ? 'Hàng tuần' : r.cadence}
                  {r.status === 'success' && ` · gửi tới ${r.delivered} người nhận`}
                </p>
              </div>
            </div>
            <Badge variant={r.status === 'success' ? 'success' : 'error'}>
              {r.status === 'success' ? 'Thành công' : 'Thất bại'}
            </Badge>
          </div>
        ))}
      </div>
      <p className="text-xs text-[var(--text-secondary)] mt-3">
        <Sparkles className="w-3.5 h-3.5 inline mr-1 text-[var(--primary-gold-dark)]" />
        Mọi lần chạy ghi vào <span className="font-mono">decision_audit_log</span> theo K-6 (cấu hình + output hash + tokens).
      </p>
    </section>
  );
}
