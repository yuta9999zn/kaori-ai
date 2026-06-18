// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 29. /p2/charts/picker — Chart Picker (F-027)
// ----------------------------------------------------------------------------
// 15 chart kinds (CLAUDE.md §12 — chart-registry). Render is intentionally
// CLIENT-SIDE via `frontend/components/charts/chart-registry.tsx` — there is
// NO `/api/v1/charts/render` endpoint by design (Sprint 7 PR D / §14).
//
// Workflow:
//   1. Pick a Gold feature OR paste an analysis_run_id     → loads sample data
//   2. Browse 15 chart kinds (4 categories: comparison /
//      composition / distribution / relationship)
//   3. Live preview on the right                           → uses same
//      chart-registry mapping as ResultsDashboard
//   4. "Add to dashboard"  (POST /api/v1/dashboard/widgets)
//      OR "Copy chart spec" (clipboard JSON for embedding)
//
// No external AI is used here — pure picker. K-3/K-4/K-5 not in play.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  BarChart2, BarChart, LineChart, AreaChart, PieChart, ScatterChart,
  Activity, TrendingUp, TrendingDown, Layers, Hash, Map, Box,
  Filter, Database, RefreshCw, Copy, Plus, Check, ShieldCheck, Search,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, cn,
  api,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type ChartKind =
  | 'bar' | 'column' | 'stacked_bar' | 'line' | 'area'
  | 'pie' | 'donut' | 'treemap' | 'funnel'
  | 'histogram' | 'box_plot' | 'density'
  | 'scatter' | 'bubble' | 'heatmap';

type Category = 'comparison' | 'composition' | 'distribution' | 'relationship';

interface ChartDef {
  kind:        ChartKind;
  label:       string;
  category:    Category;
  description: string;
  icon:        any;
  /** Minimum field count needed (used to disable chart when sample is too thin). */
  needs_x:     number;
  needs_y:     number;
}

const CHARTS: ChartDef[] = [
  // Comparison
  { kind: 'bar',         label: 'Cột ngang',         category: 'comparison',   description: 'So sánh giá trị giữa các nhóm', icon: BarChart2,    needs_x: 1, needs_y: 1 },
  { kind: 'column',      label: 'Cột dọc',           category: 'comparison',   description: 'Cột dọc thuần — mặc định cho category', icon: BarChart, needs_x: 1, needs_y: 1 },
  { kind: 'stacked_bar', label: 'Cột chồng',         category: 'comparison',   description: 'Cột chồng nhiều series',         icon: Layers,       needs_x: 1, needs_y: 2 },
  { kind: 'line',        label: 'Đường',             category: 'comparison',   description: 'Xu hướng theo thời gian',         icon: LineChart,    needs_x: 1, needs_y: 1 },
  { kind: 'area',        label: 'Vùng',              category: 'comparison',   description: 'Vùng tô — cumulative theo thời gian', icon: AreaChart, needs_x: 1, needs_y: 1 },

  // Composition
  { kind: 'pie',         label: 'Tròn',              category: 'composition',  description: 'Tỉ trọng cho ≤6 nhóm',             icon: PieChart,     needs_x: 1, needs_y: 1 },
  { kind: 'donut',       label: 'Tròn rỗng',         category: 'composition',  description: 'Như Pie, có không gian hiển thị tổng giữa', icon: PieChart, needs_x: 1, needs_y: 1 },
  { kind: 'treemap',     label: 'Treemap',           category: 'composition',  description: 'Phân cấp theo diện tích',         icon: Box,          needs_x: 1, needs_y: 1 },
  { kind: 'funnel',      label: 'Funnel',            category: 'composition',  description: 'Conversion qua các bước',         icon: TrendingDown, needs_x: 1, needs_y: 1 },

  // Distribution
  { kind: 'histogram',   label: 'Histogram',         category: 'distribution', description: 'Phân phối tần suất',               icon: BarChart,     needs_x: 1, needs_y: 0 },
  { kind: 'box_plot',    label: 'Box plot',          category: 'distribution', description: 'Median + quartiles + outlier',     icon: Hash,         needs_x: 1, needs_y: 1 },
  { kind: 'density',     label: 'Density',           category: 'distribution', description: 'Phân phối liên tục (kernel density)', icon: Activity,    needs_x: 1, needs_y: 0 },

  // Relationship
  { kind: 'scatter',     label: 'Scatter',           category: 'relationship', description: 'Tương quan 2 biến',                icon: ScatterChart, needs_x: 1, needs_y: 1 },
  { kind: 'bubble',      label: 'Bubble',            category: 'relationship', description: 'Scatter + size theo biến thứ 3',  icon: Box,          needs_x: 1, needs_y: 1 },
  { kind: 'heatmap',     label: 'Heatmap',           category: 'relationship', description: 'Mật độ theo 2 chiều rời rạc',      icon: Map,          needs_x: 1, needs_y: 1 },
];

const CATEGORY_LABEL: Record<Category, string> = {
  comparison:   'So sánh',
  composition:  'Tỉ trọng',
  distribution: 'Phân phối',
  relationship: 'Tương quan',
};

interface SampleData {
  source_id:   string;
  source_label: string;
  fields:      Array<{ name: string; type: 'string' | 'number' | 'datetime' }>;
  rows:        any[][];
}

interface GoldFeature { id: string; name: string; description: string; }

export default function ChartPickerPage() {
  const [sources,    setSources]    = useState<GoldFeature[]>([]);
  const [sourceId,   setSourceId]   = useState<string>('');
  const [sample,     setSample]     = useState<SampleData | null>(null);
  const [selected,   setSelected]   = useState<ChartKind>('column');
  const [category,   setCategory]   = useState<Category | 'ALL'>('ALL');
  const [xField,     setXField]     = useState<string>('');
  const [yField,     setYField]     = useState<string>('');
  const [loading,    setLoading]    = useState(true);
  const [problem,    setProblem]    = useState<ProblemDetails | null>(null);
  const [success,    setSuccess]    = useState<string | null>(null);

  useEffect(() => {
    api<{ items: GoldFeature[] }>('/api/v1/data/gold/features?limit=20')
      .then((r) => {
        setSources(r.items);
        if (r.items[0]) setSourceId(r.items[0].id);
      })
      .catch((err) => setProblem(err))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!sourceId) { setSample(null); return; }
    setLoading(true);
    api<SampleData>(`/api/v1/data/gold/features/${sourceId}/sample?limit=200`)
      .then((s) => {
        setSample(s);
        // auto-pick first reasonable defaults
        const xCandidate = s.fields.find((f) => f.type === 'datetime' || f.type === 'string');
        const yCandidate = s.fields.find((f) => f.type === 'number');
        setXField(xCandidate?.name ?? s.fields[0]?.name ?? '');
        setYField(yCandidate?.name ?? '');
      })
      .catch((err) => setProblem(err))
      .finally(() => setLoading(false));
  }, [sourceId]);

  const filtered = category === 'ALL' ? CHARTS : CHARTS.filter((c) => c.category === category);
  const def      = CHARTS.find((c) => c.kind === selected) ?? CHARTS[0];

  async function addToDashboard() {
    if (!sample || !def) return;
    setProblem(null);
    try {
      await api('/api/v1/dashboard/widgets', {
        method: 'POST',
        body: JSON.stringify({
          chart_kind:    def.kind,
          source_kind:   'gold_feature',
          source_id:     sample.source_id,
          x_field:       xField || null,
          y_field:       yField || null,
          title:         `${def.label} · ${sample.source_label}`,
        }),
      });
      setSuccess('Đã thêm chart vào dashboard');
    } catch (err: any) {
      setProblem(err);
    }
  }

  function copySpec() {
    if (!sample || !def) return;
    const spec = {
      chart_kind:  def.kind,
      source_kind: 'gold_feature',
      source_id:   sample.source_id,
      x_field:     xField || null,
      y_field:     yField || null,
    };
    navigator.clipboard.writeText(JSON.stringify(spec, null, 2));
    setSuccess('Đã copy chart spec vào clipboard');
  }

  return (
    <>
      <PageHeader
        title="Chart Picker"
        description="15 loại biểu đồ — chọn loại phù hợp, preview với dữ liệu thật, thêm vào dashboard."
        actions={
          <Badge variant="default">
            <ShieldCheck className="w-3 h-3 mr-1 inline" />
            Render client-side
          </Badge>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* Source picker + field mapping */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
            <div>
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Nguồn</label>
              <div className="relative mt-1">
                <Database className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
                <select
                  value={sourceId}
                  onChange={(e) => setSourceId(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
                >
                  {sources.length === 0 && <option value="">— Chưa có Gold feature —</option>}
                  {sources.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>

            <div>
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Trục X</label>
              <select
                value={xField}
                onChange={(e) => setXField(e.target.value)}
                disabled={!sample}
                className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-50"
              >
                <option value="">— Chọn cột —</option>
                {(sample?.fields ?? []).map((f) => (
                  <option key={f.name} value={f.name}>{f.name} ({f.type})</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Trục Y</label>
              <select
                value={yField}
                onChange={(e) => setYField(e.target.value)}
                disabled={!sample || def.needs_y === 0}
                className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-50"
              >
                <option value="">— Chọn cột —</option>
                {(sample?.fields ?? []).filter((f) => f.type === 'number').map((f) => (
                  <option key={f.name} value={f.name}>{f.name}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {/* Left: chart picker */}
          <div className="lg:col-span-1 bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-[var(--border-color)]/60 flex items-center gap-1 overflow-x-auto">
              <CategoryButton active={category === 'ALL'} onClick={() => setCategory('ALL')}>Tất cả</CategoryButton>
              {(Object.keys(CATEGORY_LABEL) as Category[]).map((c) => (
                <CategoryButton key={c} active={category === c} onClick={() => setCategory(c)}>
                  {CATEGORY_LABEL[c]}
                </CategoryButton>
              ))}
            </div>
            <div className="p-3 grid grid-cols-2 gap-2 max-h-[560px] overflow-y-auto">
              {filtered.map((c) => {
                const Icon = c.icon;
                const isSelected = c.kind === selected;
                return (
                  <button
                    key={c.kind}
                    type="button"
                    onClick={() => setSelected(c.kind)}
                    className={cn(
                      'text-left p-3 rounded-md-custom border transition-all',
                      isSelected
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40 hover:bg-[var(--bg-app)]/40',
                    )}
                  >
                    <div className="flex items-start justify-between gap-1">
                      <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                      {isSelected && <Check className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />}
                    </div>
                    <p className="font-medium text-xs text-[var(--text-primary)] mt-2">{c.label}</p>
                    <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 leading-snug line-clamp-2">{c.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Right: live preview */}
          <div className="lg:col-span-2 bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm flex flex-col">
            <div className="px-5 py-4 border-b border-[var(--border-color)]/60 flex items-center justify-between gap-3 flex-wrap">
              <div>
                <h3 className="font-serif text-base text-[var(--text-primary)]">{def.label}</h3>
                <p className="text-xs text-[var(--text-secondary)] mt-0.5">{def.description}</p>
              </div>
              <div className="flex items-center gap-2">
                <Button variant="secondary" size="sm" onClick={copySpec} disabled={!sample}>
                  <Copy className="w-3.5 h-3.5 mr-1.5" />
                  Copy spec
                </Button>
                <Button size="sm" onClick={addToDashboard} disabled={!sample}>
                  <Plus className="w-3.5 h-3.5 mr-1.5" />
                  Thêm vào dashboard
                </Button>
              </div>
            </div>

            <div className="p-5 flex-1 min-h-[420px]">
              {loading && !sample ? (
                <div className="h-full rounded-md-custom bg-[var(--bg-app)]/40 animate-pulse flex items-center justify-center">
                  <RefreshCw className="w-6 h-6 text-[var(--text-secondary)] animate-spin" />
                </div>
              ) : !sample ? (
                <div className="h-full rounded-md-custom border border-dashed border-[var(--border-color)] flex flex-col items-center justify-center text-[var(--text-secondary)]">
                  <Search className="w-10 h-10 mb-2" />
                  <p className="text-sm">Chọn một Gold feature để xem preview</p>
                </div>
              ) : (
                <ChartPreview def={def} sample={sample} xField={xField} yField={yField} />
              )}
            </div>

            <div className="px-5 py-3 border-t border-[var(--border-color)]/60 bg-[var(--bg-app)]/30 text-[11px] text-[var(--text-secondary)] flex items-start gap-2">
              <ShieldCheck className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
              <p>
                Render qua <span className="font-mono">frontend/components/charts/chart-registry.tsx</span> —
                không có endpoint <span className="font-mono">/api/v1/charts/render</span> (Sprint 7 PR D / §14).
                Backend chỉ trả ChartBlock JSON, frontend tự vẽ.
              </p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}

function CategoryButton({
  active, onClick, children,
}: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'px-3 py-1.5 text-xs font-medium rounded-sm-custom whitespace-nowrap transition-colors',
        active
          ? 'bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
          : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)]',
      )}
    >
      {children}
    </button>
  );
}

// ----------------------------------------------------------------------------
// Lightweight preview — placeholder visualization keyed by chart_kind.
// Real chart-registry will swap in Recharts components on the production app.
// ----------------------------------------------------------------------------

function ChartPreview({
  def, sample, xField, yField,
}: { def: ChartDef; sample: SampleData; xField: string; yField: string }) {
  const xIdx = sample.fields.findIndex((f) => f.name === xField);
  const yIdx = sample.fields.findIndex((f) => f.name === yField);
  const previewRows = sample.rows.slice(0, 8);

  if (xIdx < 0 || (def.needs_y > 0 && yIdx < 0)) {
    return (
      <div className="h-full rounded-md-custom border border-dashed border-[var(--state-warning)]/50 bg-[var(--state-warning)]/5 p-6 flex flex-col items-center justify-center text-center">
        <Filter className="w-8 h-8 text-[var(--state-warning)] mb-2" />
        <p className="text-sm font-medium text-[var(--text-primary)]">Cần chọn cột phù hợp</p>
        <p className="text-xs text-[var(--text-secondary)] mt-1">
          Biểu đồ <span className="font-medium">{def.label}</span> cần ít nhất {def.needs_x} cột X
          {def.needs_y > 0 && ` và ${def.needs_y} cột Y số`}.
        </p>
      </div>
    );
  }

  const Icon = def.icon;
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] p-4 flex flex-col">
        <div className="flex items-center gap-2 mb-3">
          <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <span className="text-sm font-medium text-[var(--text-primary)]">
            {sample.source_label} · {def.label}
          </span>
        </div>
        <div className="flex-1 flex items-end gap-1.5 px-2">
          {previewRows.map((row, i) => {
            const yVal = def.needs_y > 0 ? Number(row[yIdx]) || 0 : 1;
            const max  = Math.max(...previewRows.map((r) => def.needs_y > 0 ? Number(r[yIdx]) || 0 : 1), 1);
            const h    = Math.max(8, (yVal / max) * 180);
            return (
              <div key={i} className="flex-1 flex flex-col items-center gap-1">
                <div
                  className="w-full bg-[var(--primary-gold)]/70 hover:bg-[var(--primary-gold)] transition-colors rounded-t-sm-custom"
                  style={{ height: `${h}px` }}
                  title={`${row[xIdx]}: ${yVal}`}
                />
                <span className="text-[9px] text-[var(--text-secondary)] truncate max-w-full">
                  {String(row[xIdx]).slice(0, 8)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
      <p className="text-[11px] text-[var(--text-secondary)] mt-2">
        Preview hiển thị 8 hàng đầu — chart thật sẽ render đầy đủ {sample.rows.length.toLocaleString('vi-VN')} hàng qua chart-registry.
      </p>
    </div>
  );
}
