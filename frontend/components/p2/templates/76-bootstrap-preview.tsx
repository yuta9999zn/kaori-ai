// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-32 — Bootstrap Preview (dry-run before commit)
// ----------------------------------------------------------------------------
// Phase 2.8. ADR-0026 Industry Template 3-Tier Bootstrap step 2/2.
// Khách xem trước những gì hệ thống sẽ tạo trước khi confirm, with a 2-step
// type-to-confirm gate.
//
// Route:        /p2/onboarding/bootstrap-preview?industry_id=<uuid>
// Permission:   MANAGER+ only.
// BE routes (services/ai-orchestrator/routers/industry_bootstrap.py):
//   GET  /api/v1/industries/{id}                              — names for panels
//   POST /api/v1/enterprises/{eid}/bootstrap-from-industry    — body {industry_id, dry_run, dept_keys_to_skip[]}
//        dry_run=true  → preview counts (depts_created / workflows_created / warning)
//        dry_run=false → final write (409 if already bootstrapped)
//   enterprise_id comes from the JWT (auth-store); the gateway re-checks it
//   against X-Enterprise-ID (K-12) so a forged path id is rejected server-side.
// ============================================================================

import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams } from 'next/navigation';
import { AlertTriangle, FolderTree, Workflow, BarChart3, Database, Loader2 } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, Input, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useAuth } from '@/lib/auth-store';

// ─── Types ───────────────────────────────────────────────────────────

interface PreviewEntity {
  key:                  string;
  name_vi:              string;
  recommendation_level: 'core' | 'suggested' | 'advanced' | string;
  required:             boolean;
}

interface DryRunResult {
  depts_created:     number;
  workflows_created: number;
  skipped_dept_keys: string[];
  warning?:          string | null;
}

// ─── Page component ──────────────────────────────────────────────────

export default function BootstrapPreviewPage() {
  const searchParams = useSearchParams();
  const industryId   = searchParams?.get('industry_id') ?? '';
  const enterpriseId = useAuth((s) => s.user?.enterprise_id ?? '');
  const enterpriseName = useAuth((s) => s.user?.enterprise_name ?? '');

  const [industryName, setIndustryName] = useState('');
  const [depts, setDepts]         = useState<PreviewEntity[]>([]);
  const [workflows, setWorkflows] = useState<PreviewEntity[]>([]);
  const [kpis, setKpis]           = useState<PreviewEntity[]>([]);
  const [schemas, setSchemas]     = useState<PreviewEntity[]>([]);
  const [dryRun, setDryRun]       = useState<DryRunResult | null>(null);

  const [loading, setLoading]   = useState(true);
  const [problem, setProblem]   = useState<ProblemDetails | null>(null);

  const [selectedSkips, setSelectedSkips] = useState<Set<string>>(new Set());
  const [confirmStep, setConfirmStep] = useState<0 | 1 | 2>(0);
  const [typedName, setTypedName] = useState('');
  const [committing, setCommitting] = useState(false);
  const [done, setDone] = useState(false);

  const toggleSkip = (key: string) =>
    setSelectedSkips((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });

  // Load industry detail (names) + a dry-run (counts). The detail call gives
  // us entity names for the panels; the dry-run gives the authoritative
  // created-count + any BE warning.
  async function loadPreview(skips: string[] = []) {
    if (!industryId) {
      setProblem({ title: 'Thiếu ngành', detail: 'Không có industry_id trong URL. Quay lại Thư viện ngành để chọn ngành.' });
      setLoading(false);
      return;
    }
    setLoading(true);
    setProblem(null);
    try {
      const detail = await api<any>(`/api/v1/industries/${industryId}`);
      setIndustryName(detail?.industry?.display_name_vi ?? detail?.industry?.display_name ?? '');
      setDepts((detail?.departments ?? []).map((d: any) => ({
        key: d.dept_key, name_vi: d.display_name_vi ?? d.display_name ?? d.dept_key,
        recommendation_level: d.is_required ? 'core' : 'suggested', required: !!d.is_required,
      })));
      setWorkflows((detail?.workflows ?? []).map((w: any) => ({
        key: String(w.link_id ?? w.workflow_template_id), name_vi: w.display_name_vi ?? w.display_name,
        recommendation_level: w.recommendation_level ?? 'core', required: w.recommendation_level === 'core',
      })));
      setKpis((detail?.kpis ?? []).map((k: any, i: number) => ({
        key: String(k.kpi_key ?? i), name_vi: k.display_name_vi ?? k.display_name ?? k.kpi_key,
        recommendation_level: 'core', required: true,
      })));
      setSchemas((detail?.data_schemas ?? []).map((s: any, i: number) => ({
        key: String(s.schema_key ?? i), name_vi: s.display_name_vi ?? s.display_name ?? s.schema_key,
        recommendation_level: 'core', required: true,
      })));

      if (enterpriseId) {
        const dr = await api<DryRunResult>(
          `/api/v1/enterprises/${enterpriseId}/bootstrap-from-industry`,
          { method: 'POST', body: JSON.stringify({ industry_id: industryId, dry_run: true, dept_keys_to_skip: skips }) },
        );
        setDryRun(dr);
      }
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadPreview([]); /* eslint-disable-next-line */ }, [industryId, enterpriseId]);

  async function commit() {
    if (!enterpriseId) {
      setProblem({ title: 'Thiếu phiên đăng nhập', detail: 'Không xác định được doanh nghiệp. Đăng nhập lại.' });
      return;
    }
    setCommitting(true);
    setProblem(null);
    try {
      await api(
        `/api/v1/enterprises/${enterpriseId}/bootstrap-from-industry`,
        { method: 'POST', body: JSON.stringify({ industry_id: industryId, dry_run: false, dept_keys_to_skip: Array.from(selectedSkips) }) },
      );
      setDone(true);
      setConfirmStep(0);
      window.location.href = '/p2';
    } catch (err: any) {
      // 409 = already bootstrapped → surface BE detail.
      setProblem(err);
      setConfirmStep(0);
    } finally {
      setCommitting(false);
    }
  }

  const skipCount = selectedSkips.size;
  const confirmTarget = (enterpriseName || industryName || '').trim();
  // Bootstrap only clones `core` workflows (industry_bootstrap.py filters
  // recommendation_level='core'); `suggested` ones are listed for awareness
  // but NOT auto-created. Reconcile the summary count (core) with the panel
  // list (core+suggested) so the customer isn't misled by "10 vs 15".
  const coreWfCount = workflows.filter((w) => w.recommendation_level === 'core').length;
  const suggestedWfCount = workflows.length - coreWfCount;

  if (loading) {
    return (
      <>
        <PageHeader title="Xem trước bootstrap" description="Đang tải cấu hình ngành…" />
        <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto">
          <div className="h-64 animate-pulse rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)]" />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Xem trước bootstrap"
        description={industryName ? `Ngành: ${industryName} — xem trước hệ thống sẽ tạo gì cho doanh nghiệp anh.` : 'Xem trước cấu hình ngành.'}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        {/* Header summary — counts come from the dry-run when available. */}
        <div className="rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-card)] p-4 shadow-soft-sm">
          <div className="flex flex-wrap gap-6 text-sm text-[var(--text-primary)]">
            <div><FolderTree className="inline w-4 h-4 mr-1" /><strong>{dryRun?.depts_created ?? depts.length}</strong> phòng ban</div>
            <div>
              <Workflow className="inline w-4 h-4 mr-1" />
              <strong>{dryRun?.workflows_created ?? coreWfCount}</strong> workflow lõi (tự tạo)
              {suggestedWfCount > 0 && (
                <span className="text-[var(--text-secondary)]"> · {suggestedWfCount} gợi ý (thêm sau)</span>
              )}
            </div>
            <div><BarChart3 className="inline w-4 h-4 mr-1" /><strong>{kpis.length}</strong> KPI</div>
            <div><Database className="inline w-4 h-4 mr-1" /><strong>{schemas.length}</strong> data schema</div>
          </div>
        </div>

        {/* Caution banner */}
        <div className="flex gap-3 rounded-lg-custom border border-[var(--state-warning)]/30 bg-[var(--state-warning)]/10 p-4 text-sm">
          <AlertTriangle className="w-5 h-5 shrink-0 text-[#9E814D]" />
          <div>
            <div className="font-medium text-[var(--text-primary)]">Lưu ý không thể hoàn tác</div>
            <div className="text-[var(--text-secondary)]">
              Sau khi tạo, không thể bootstrap lại trừ khi admin chạy lại với chế độ ghi đè.
              Toàn bộ phòng ban + workflow + KPI + schema sẽ được khởi tạo cho doanh nghiệp anh.
            </div>
          </div>
        </div>

        {/* 4-panel preview grid */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <PreviewPanel title="Phòng ban" icon={<FolderTree className="w-4 h-4" />}
            entities={depts} selectedSkips={selectedSkips} toggleSkip={toggleSkip} canSkip />
          <PreviewPanel title="Workflow mẫu" icon={<Workflow className="w-4 h-4" />}
            entities={workflows} selectedSkips={selectedSkips} toggleSkip={toggleSkip} />
          <PreviewPanel title="KPI" icon={<BarChart3 className="w-4 h-4" />}
            entities={kpis} selectedSkips={selectedSkips} toggleSkip={toggleSkip} />
          <PreviewPanel title="Data schema" icon={<Database className="w-4 h-4" />}
            entities={schemas} selectedSkips={selectedSkips} toggleSkip={toggleSkip} />
        </div>

        {/* Action footer */}
        <div className="sticky bottom-0 -mx-6 border-t border-[var(--border-color)] bg-[var(--bg-card)] px-6 py-4 shadow-lg">
          <div className="flex items-center justify-between">
            <div className="text-sm text-[var(--text-secondary)]">
              {skipCount > 0 ? `${skipCount} mục đã bỏ chọn` : 'Bootstrap với cấu hình mặc định'}
            </div>
            <Button onClick={() => setConfirmStep(1)} disabled={!enterpriseId}>Tiếp tục → Xác nhận</Button>
          </div>
        </div>
      </div>

      {/* 2-step confirm modal */}
      {confirmStep === 1 && (
        <ConfirmModalStep1 onCancel={() => setConfirmStep(0)} onNext={() => setConfirmStep(2)} />
      )}
      {confirmStep === 2 && (
        <ConfirmModalStep2
          enterpriseName={confirmTarget}
          typedName={typedName}
          onTypedNameChange={setTypedName}
          committing={committing}
          onCancel={() => setConfirmStep(0)}
          onConfirm={commit}
        />
      )}
    </>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function PreviewPanel({
  title, icon, entities, selectedSkips, toggleSkip, canSkip = false,
}: {
  title: string; icon: React.ReactNode; entities: PreviewEntity[];
  selectedSkips: Set<string>; toggleSkip: (k: string) => void; canSkip?: boolean;
}) {
  return (
    <div className="rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-card)]">
      <div className="flex items-center gap-2 border-b border-[var(--border-color)] px-4 py-3">
        {icon}
        <span className="font-medium text-[var(--text-primary)]">{title}</span>
        <Badge variant="default">{entities.length}</Badge>
      </div>
      {entities.length === 0 ? (
        <p className="px-4 py-3 text-sm text-[var(--text-secondary)]">Không có mục nào.</p>
      ) : (
        <ul className="divide-y divide-[var(--border-color)]/60">
          {entities.map((e) => {
            const skipped = selectedSkips.has(e.key);
            return (
              <li key={e.key} className={cn('flex items-center justify-between px-4 py-2', skipped && 'opacity-50')}>
                <div className="flex items-center gap-2">
                  {canSkip && !e.required && (
                    <input type="checkbox" checked={!skipped} onChange={() => toggleSkip(e.key)} />
                  )}
                  <span className="text-sm text-[var(--text-primary)]">{e.name_vi}</span>
                  <Badge variant={e.recommendation_level === 'core' ? 'success' : 'default'}>
                    {e.recommendation_level === 'core' ? 'lõi' : 'gợi ý'}
                  </Badge>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function ConfirmModalStep1({ onCancel, onNext }: { onCancel: () => void; onNext: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg-custom bg-[var(--bg-card)] p-6 shadow-lg">
        <h3 className="text-lg font-medium text-[var(--text-primary)]">Xác nhận hành động</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Bước 1/2 — Em sẽ tạo toàn bộ phòng ban + workflow + KPI + schema cho doanh nghiệp anh.
          Hành động này không thể hoàn tác. Tiếp tục?
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="tertiary" onClick={onCancel}>Huỷ</Button>
          <Button onClick={onNext}>Tiếp →</Button>
        </div>
      </div>
    </div>
  );
}

function ConfirmModalStep2({
  enterpriseName, typedName, onTypedNameChange, onCancel, onConfirm, committing,
}: {
  enterpriseName: string; typedName: string;
  onTypedNameChange: (v: string) => void;
  onCancel: () => void; onConfirm: () => void; committing: boolean;
}) {
  const match = !!enterpriseName && typedName.trim() === enterpriseName.trim();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-md rounded-lg-custom bg-[var(--bg-card)] p-6 shadow-lg">
        <h3 className="text-lg font-medium text-[var(--text-primary)]">Gõ tên doanh nghiệp</h3>
        <p className="mt-2 text-sm text-[var(--text-secondary)]">
          Bước 2/2 — Gõ chính xác tên <strong>{enterpriseName || '(doanh nghiệp)'}</strong> để xác nhận.
        </p>
        <Input
          className="mt-4"
          value={typedName}
          onChange={(e) => onTypedNameChange(e.target.value)}
          placeholder={enterpriseName}
        />
        <div className="mt-6 flex justify-end gap-2">
          <Button variant="tertiary" onClick={onCancel}>Huỷ</Button>
          <Button disabled={!match || committing} isLoading={committing} onClick={onConfirm}>
            Xác nhận Bootstrap
          </Button>
        </div>
      </div>
    </div>
  );
}
