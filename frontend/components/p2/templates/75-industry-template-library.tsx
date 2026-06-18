// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-31 — Industry Template Library
// ----------------------------------------------------------------------------
// Phase 2.8. ADR-0026 Industry Template 3-Tier Bootstrap. Catalog of 8 ngành;
// 3 seeded (Retail / Finance / Generic SME). The BE only returns *active*
// (seeded) industries from GET /api/v1/industries — deferred ones are simply
// absent, so there is no "deferred" card state to render in v0.
//
// Route:        /p2/templates/industries
// Permission:   VIEWER+ xem; MANAGER+ click "Bootstrap với ngành này".
// BE routes (services/ai-orchestrator/routers/industry_bootstrap.py):
//   GET  /api/v1/industries
//   GET  /api/v1/industries/{id}
// ============================================================================

import React, { useState, useEffect } from 'react';
import { Search, Building2, ChevronRight, Loader2 } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

// ─── Types mirror BE IndustryOut ─────────────────────────────────────

interface IndustryOut {
  industry_id:          string;
  industry_key:         string;
  display_name:         string;
  display_name_vi:      string;
  description_vi?:      string | null;
  icon_key?:            string | null;
  accent_color?:        string | null;
  primary_kpis:         string[];
  ai_confidence_threshold: number;
  suggested_pricing_plan?: string | null;
  compliance_notes_vi?: string | null;
  dept_count:           number;
  core_workflow_count:  number;
  total_workflow_count: number;
  kpi_count:            number;
}

// industry_key → emoji (presentational only — BE icon_key may be null).
const ICON_BY_KEY: Record<string, string> = {
  retail:      '🛍️',
  finance:     '🏦',
  generic_sme: '🏢',
  fnb:         '🍜',
  logistics:   '🚚',
  healthcare:  '🏥',
  manufacturing: '🏭',
  education:   '🎓',
};

export default function IndustryTemplateLibraryPage() {
  const [search, setSearch]       = useState('');
  const [industries, setIndustries] = useState<IndustryOut[]>([]);
  const [loading, setLoading]     = useState(true);
  const [problem, setProblem]     = useState<ProblemDetails | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const rows = await api<IndustryOut[]>('/api/v1/industries');
      setIndustries(Array.isArray(rows) ? rows : []);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  const filtered = industries.filter((i) => {
    if (!search.trim()) return true;
    const q = search.trim().toLowerCase();
    return `${i.display_name_vi} ${i.display_name}`.toLowerCase().includes(q);
  });

  return (
    <>
      <PageHeader
        title="Thư viện ngành"
        description="Chọn ngành phù hợp với doanh nghiệp anh để bootstrap nhanh phòng ban + workflow mẫu."
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <Loader2 className={cn('w-4 h-4 mr-2', loading && 'animate-spin')} />
            Làm mới
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        <ErrorBanner problem={problem} />

        {/* Filter bar */}
        <div className="flex items-center gap-3 rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-card)] px-4 py-3 shadow-soft-sm">
          <Search className="w-4 h-4 text-[var(--text-secondary)]" />
          <input
            className="flex-1 bg-transparent outline-none text-sm"
            placeholder="Tìm theo tên ngành..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        {loading ? (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-44 animate-pulse rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)]" />
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-lg-custom border border-dashed border-[var(--border-color)] p-12 text-center text-[var(--text-secondary)]">
            <Building2 className="w-10 h-10 mx-auto mb-2 opacity-40" />
            {industries.length === 0
              ? 'Chưa có ngành nào được kích hoạt. Liên hệ Kaori để bật thêm ngành cho doanh nghiệp anh.'
              : 'Không có ngành nào khớp bộ lọc.'}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map((industry) => (
              <IndustryCardView
                key={industry.industry_id}
                industry={industry}
                onClick={() => setSelectedId(industry.industry_id)}
              />
            ))}
          </div>
        )}

        {selectedId && (
          <IndustryDetailDrawer
            industryId={selectedId}
            onClose={() => setSelectedId(null)}
          />
        )}
      </div>
    </>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function IndustryCardView({ industry, onClick }: { industry: IndustryOut; onClick: () => void }) {
  const icon = ICON_BY_KEY[industry.industry_key] ?? '🏢';
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-start gap-3 rounded-lg-custom border border-[var(--border-color)] bg-[var(--bg-card)] p-4 text-left transition hover:border-[var(--primary-gold)] shadow-soft-sm"
    >
      <div className="flex w-full items-center justify-between">
        <span className="text-2xl">{icon}</span>
        {industry.suggested_pricing_plan && (
          <Badge variant="current">{industry.suggested_pricing_plan}</Badge>
        )}
      </div>
      <div>
        <div className="font-medium text-[var(--text-primary)]">{industry.display_name_vi}</div>
        <div className="text-xs text-[var(--text-secondary)]">{industry.display_name}</div>
      </div>
      <div className="text-xs text-[var(--text-secondary)]">
        {industry.dept_count} phòng ban · {industry.total_workflow_count} workflow · {industry.kpi_count} KPI
      </div>
    </button>
  );
}

function IndustryDetailDrawer({ industryId, onClose }: { industryId: string; onClose: () => void }) {
  const [detail, setDetail] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setProblem(null);
      try {
        const d = await api<any>(`/api/v1/industries/${industryId}`);
        if (!cancelled) setDetail(d);
      } catch (err: any) {
        if (!cancelled) setProblem(err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [industryId]);

  const departments = detail?.departments ?? [];
  const workflows   = detail?.workflows ?? [];
  const kpis        = detail?.kpis ?? [];
  const schemas     = detail?.data_schemas ?? [];

  return (
    <div className="fixed inset-y-0 right-0 z-50 w-full max-w-2xl border-l border-[var(--border-color)] bg-[var(--bg-card)] shadow-lg overflow-y-auto">
      <div className="flex items-center justify-between border-b border-[var(--border-color)] px-6 py-4">
        <h2 className="text-lg font-medium text-[var(--text-primary)]">
          {detail?.industry?.display_name_vi ?? 'Chi tiết ngành'}
        </h2>
        <Button variant="tertiary" onClick={onClose}>Đóng</Button>
      </div>
      <div className="space-y-6 px-6 py-4">
        <ErrorBanner problem={problem} />
        {loading ? (
          <div className="space-y-3">
            {[1,2,3].map((i) => <div key={i} className="h-20 rounded-md-custom bg-[var(--bg-app)] animate-pulse" />)}
          </div>
        ) : (
          <>
            <DetailSection title={`Phòng ban (${departments.length})`}>
              {departments.length === 0 ? <Muted>Không có phòng ban mẫu.</Muted> : (
                <ul className="space-y-1 text-sm text-[var(--text-primary)]">
                  {departments.map((d: any) => (
                    <li key={d.template_id ?? d.dept_key}>{d.display_name_vi ?? d.display_name ?? d.dept_key}</li>
                  ))}
                </ul>
              )}
            </DetailSection>
            <DetailSection title={`Workflow mẫu (${workflows.length})`}>
              {workflows.length === 0 ? <Muted>Không có workflow mẫu.</Muted> : (
                <ul className="space-y-1 text-sm text-[var(--text-primary)]">
                  {workflows.map((w: any) => (
                    <li key={w.link_id ?? w.workflow_template_id} className="flex items-center gap-2">
                      <span>{w.display_name_vi ?? w.display_name}</span>
                      {w.recommendation_level && (
                        <Badge variant={w.recommendation_level === 'core' ? 'success' : 'default'}>
                          {w.recommendation_level}
                        </Badge>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </DetailSection>
            <DetailSection title={`KPI (${kpis.length})`}>
              {kpis.length === 0 ? <Muted>Không có KPI mẫu.</Muted> : (
                <ul className="space-y-1 text-sm text-[var(--text-primary)]">
                  {kpis.map((k: any, i: number) => (
                    <li key={k.kpi_key ?? i}>{k.display_name_vi ?? k.display_name ?? k.kpi_key}</li>
                  ))}
                </ul>
              )}
            </DetailSection>
            <DetailSection title={`Data schema (${schemas.length})`}>
              {schemas.length === 0 ? <Muted>Không có schema mẫu.</Muted> : (
                <ul className="space-y-1 text-sm text-[var(--text-primary)]">
                  {schemas.map((s: any, i: number) => (
                    <li key={s.schema_key ?? i}>{s.display_name_vi ?? s.display_name ?? s.schema_key}</li>
                  ))}
                </ul>
              )}
            </DetailSection>
            <Button onClick={() => (window.location.href = `/p2/onboarding/bootstrap-preview?industry_id=${industryId}`)}>
              Bootstrap với ngành này <ChevronRight className="w-4 h-4 ml-1" />
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function DetailSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-sm font-medium text-[var(--text-secondary)]">{title}</h3>
      <div className="mt-2 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-app)]/40 p-4">{children}</div>
    </section>
  );
}

function Muted({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-[var(--text-secondary)]">{children}</p>;
}
