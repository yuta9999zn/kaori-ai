// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 49. /p2/reports/builder — Report Builder (F-038 🔵 Phase 2 — UI mock only)
// ----------------------------------------------------------------------------
// Editor 2-pane:
//   - Trái: bộ block (Heading · Text · Chart · Table · KPI · Insight ref) +
//     danh sách section đang dựng. Mỗi section có order — tăng/giảm bằng nút.
//   - Phải: preview render. Đổi block ở trái → preview ở phải update ngay.
//
// Wiring deferred: builder needs `POST /api/v1/reports/builder` (BE-EU-221) +
// `POST /api/v1/reports/{id}/save-as-template`. Auto-generate path is wired in
// 48-report-auto.tsx (PR #113). Preview render here is FE-only placeholder.
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  Heading1, AlignLeft, BarChart3, Table2, Gauge, Lightbulb, Plus,
  Trash2, ArrowUp, ArrowDown, Save, BookMarked, FileBadge, Eye,
  GripVertical, Sparkles, ArrowLeft, ShieldCheck,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Block schema
// ============================================================================

type BlockKind = 'heading' | 'text' | 'chart' | 'table' | 'kpi' | 'insight_ref';

interface BlockMeta {
  kind:        BlockKind;
  label:       string;
  icon:        any;
  description: string;
}

// NOTE: label/description below store i18n KEYS (not display text) because this
// array lives at module scope, outside any component — the `useT()` hook can't
// run here. Call sites (Palette / Outline / Inspector) resolve them via `t(...)`.
const BLOCK_PALETTE: BlockMeta[] = [
  { kind: 'heading',     label: 'templates49ReportBuilder.blockHeadingLabel',    icon: Heading1,  description: 'templates49ReportBuilder.blockHeadingDesc' },
  { kind: 'text',        label: 'templates49ReportBuilder.blockTextLabel',       icon: AlignLeft, description: 'templates49ReportBuilder.blockTextDesc' },
  { kind: 'chart',       label: 'templates49ReportBuilder.blockChartLabel',      icon: BarChart3, description: 'templates49ReportBuilder.blockChartDesc' },
  { kind: 'table',       label: 'templates49ReportBuilder.blockTableLabel',      icon: Table2,    description: 'templates49ReportBuilder.blockTableDesc' },
  { kind: 'kpi',         label: 'templates49ReportBuilder.blockKpiLabel',        icon: Gauge,     description: 'templates49ReportBuilder.blockKpiDesc' },
  { kind: 'insight_ref', label: 'templates49ReportBuilder.blockInsightRefLabel', icon: Lightbulb, description: 'templates49ReportBuilder.blockInsightRefDesc' },
];

interface ReportBlock {
  id:    string;
  kind:  BlockKind;
  title?:        string;
  body?:         string;
  chart_kind?:   string;
  dataset_id?:   string;
  insight_id?:   string;
  metric?:       string;
  delta_pct?:    number;
}

let _seq = 0;
// `t` is threaded in from the calling component — this factory lives at module
// scope so it cannot call the `useT()` hook itself.
function newBlock(kind: BlockKind, t: (key: string, params?: Record<string, any>) => string): ReportBlock {
  _seq += 1;
  const id = `blk_${Date.now()}_${_seq}`;
  switch (kind) {
    case 'heading':     return { id, kind, title: t('templates49ReportBuilder.defaultHeadingTitle') };
    case 'text':        return { id, kind, body: t('templates49ReportBuilder.defaultTextBody') };
    case 'chart':       return { id, kind, title: t('templates49ReportBuilder.defaultChartTitle'), chart_kind: 'bar', dataset_id: 'monthly_revenue_gold' };
    case 'table':       return { id, kind, title: t('templates49ReportBuilder.defaultTableTitle'), dataset_id: 'monthly_revenue_gold' };
    case 'kpi':         return { id, kind, title: t('templates49ReportBuilder.defaultKpiTitle'), metric: '1.245.300.000₫', delta_pct: 12 };
    case 'insight_ref': return { id, kind, insight_id: 'ins_42', title: t('templates49ReportBuilder.defaultInsightRefTitle') };
  }
}

// ============================================================================
// Page
// ============================================================================

export default function ReportBuilderPage() {
  const t = useT();
  const [name, setName] = useState(t('templates49ReportBuilder.defaultReportName'));
  const [blocks, setBlocks] = useState<ReportBlock[]>([
    newBlock('heading', t),
    newBlock('kpi', t),
    newBlock('chart', t),
    newBlock('text', t),
  ]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selected = useMemo(
    () => blocks.find((b) => b.id === selectedId) ?? null,
    [blocks, selectedId],
  );

  function addBlock(kind: BlockKind) {
    const blk = newBlock(kind, t);
    setBlocks((prev) => [...prev, blk]);
    setSelectedId(blk.id);
  }

  function updateBlock(id: string, patch: Partial<ReportBlock>) {
    setBlocks((prev) => prev.map((b) => (b.id === id ? { ...b, ...patch } : b)));
  }

  function deleteBlock(id: string) {
    setBlocks((prev) => prev.filter((b) => b.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  function moveBlock(id: string, dir: -1 | 1) {
    setBlocks((prev) => {
      const idx = prev.findIndex((b) => b.id === id);
      if (idx === -1) return prev;
      const newIdx = idx + dir;
      if (newIdx < 0 || newIdx >= prev.length) return prev;
      const next = [...prev];
      [next[idx], next[newIdx]] = [next[newIdx], next[idx]];
      return next;
    });
  }

  async function onSave(asTemplate: boolean) {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      await api(asTemplate ? '/api/v1/reports/templates' : '/api/v1/reports', {
        method: 'POST',
        body: JSON.stringify({ name, blocks }),
      });
      setSuccess(asTemplate
        ? t('templates49ReportBuilder.saveTemplateSuccess')
        : t('templates49ReportBuilder.saveReportSuccess'),
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
        title={t('templates49ReportBuilder.pageTitle')}
        description={t('templates49ReportBuilder.pageDescription')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-038</Badge>
            <a href="/p2/reports">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templates49ReportBuilder.cancel')}</Button>
            </a>
            <Button
              variant="secondary"
              size="md"
              onClick={() => onSave(true)}
              disabled={submitting || blocks.length === 0}
              isLoading={submitting}
            >
              <BookMarked className="w-4 h-4 mr-2" /> {t('templates49ReportBuilder.saveAsTemplate')}
            </Button>
            <Button
              variant="primary"
              size="md"
              onClick={() => onSave(false)}
              disabled={submitting || blocks.length === 0}
              isLoading={submitting}
            >
              <Save className="w-4 h-4 mr-2" /> {t('templates49ReportBuilder.saveReport')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1500px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <Input
          label={t('templates49ReportBuilder.reportNameLabel')}
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t('templates49ReportBuilder.reportNamePlaceholder')}
        />

        <div className="grid grid-cols-1 xl:grid-cols-[280px_1fr_320px] gap-4 min-h-[600px]">
          {/* Left palette + outline */}
          <div className="space-y-4">
            <Palette onAdd={addBlock} />
            <Outline
              blocks={blocks}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onMoveUp={(id) => moveBlock(id, -1)}
              onMoveDown={(id) => moveBlock(id, 1)}
              onDelete={deleteBlock}
            />
          </div>

          {/* Center preview canvas */}
          <Preview blocks={blocks} selectedId={selectedId} onSelect={setSelectedId} />

          {/* Right inspector */}
          <Inspector block={selected} onChange={(patch) => selected && updateBlock(selected.id, patch)} />
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates49ReportBuilder.insightRefNote')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Palette
// ============================================================================

function Palette({ onAdd }: { onAdd: (kind: BlockKind) => void }) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-3">
        <Plus className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-sm text-[var(--text-primary)]">{t('templates49ReportBuilder.addBlockHeading')}</h3>
      </div>
      <div className="space-y-1.5">
        {BLOCK_PALETTE.map((b) => {
          const Icon = b.icon;
          return (
            <button
              key={b.kind}
              onClick={() => onAdd(b.kind)}
              className="w-full flex items-start gap-2 p-2 rounded-md-custom border border-transparent hover:border-[var(--primary-gold)]/30 hover:bg-[var(--bg-app)] transition-colors text-left"
            >
              <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] mt-0.5 shrink-0" />
              <div className="min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)]">{t(b.label)}</p>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-snug">{t(b.description)}</p>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

// ============================================================================
// Outline (left bottom)
// ============================================================================

function Outline({
  blocks, selectedId, onSelect, onMoveUp, onMoveDown, onDelete,
}: {
  blocks:     ReportBlock[];
  selectedId: string | null;
  onSelect:   (id: string) => void;
  onMoveUp:   (id: string) => void;
  onMoveDown: (id: string) => void;
  onDelete:   (id: string) => void;
}) {
  const t = useT();
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-3">
        <GripVertical className="w-4 h-4 text-[var(--text-secondary)]" />
        <h3 className="font-serif text-sm text-[var(--text-primary)]">{t('templates49ReportBuilder.outlineHeading')}</h3>
        <Badge variant="default">{t('templates49ReportBuilder.blockCount', { count: blocks.length })}</Badge>
      </div>
      {blocks.length === 0 ? (
        <p className="text-xs text-[var(--text-secondary)] py-3 text-center">{t('templates49ReportBuilder.outlineEmpty')}</p>
      ) : (
        <ul className="space-y-1">
          {blocks.map((b, i) => {
            const meta = BLOCK_PALETTE.find((m) => m.kind === b.kind)!;
            const Icon = meta.icon;
            const active = b.id === selectedId;
            return (
              <li
                key={b.id}
                className={cn(
                  'group flex items-center gap-2 p-2 rounded-sm-custom border transition-colors',
                  active
                    ? 'bg-[var(--primary-gold)]/10 border-[var(--primary-gold)]/40'
                    : 'border-transparent hover:bg-[var(--bg-app)]',
                )}
              >
                <button onClick={() => onSelect(b.id)} className="flex-1 flex items-center gap-2 min-w-0 text-left">
                  <Icon className="w-3.5 h-3.5 text-[var(--primary-gold-dark)] shrink-0" />
                  <span className="text-xs text-[var(--text-primary)] truncate">{b.title || t(meta.label)}</span>
                </button>
                <div className="opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-0.5">
                  <button onClick={() => onMoveUp(b.id)} disabled={i === 0} title={t('templates49ReportBuilder.moveUp')} className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30">
                    <ArrowUp className="w-3 h-3" />
                  </button>
                  <button onClick={() => onMoveDown(b.id)} disabled={i === blocks.length - 1} title={t('templates49ReportBuilder.moveDown')} className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] disabled:opacity-30">
                    <ArrowDown className="w-3 h-3" />
                  </button>
                  <button onClick={() => onDelete(b.id)} title={t('templates49ReportBuilder.deleteBlock')} className="p-1 text-[var(--text-secondary)] hover:text-[var(--state-error)]">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

// ============================================================================
// Preview canvas
// ============================================================================

function Preview({
  blocks, selectedId, onSelect,
}: { blocks: ReportBlock[]; selectedId: string | null; onSelect: (id: string) => void }) {
  const t = useT();
  return (
    <div className="bg-white border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="border-b border-[var(--border-color)] px-4 py-2 flex items-center justify-between bg-[var(--bg-app)]">
        <div className="flex items-center gap-2">
          <Eye className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <span className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">{t('templates49ReportBuilder.previewLabel')}</span>
        </div>
        <span className="text-[11px] text-[var(--text-secondary)] flex items-center gap-1">
          <FileBadge className="w-3 h-3" /> {t('templates49ReportBuilder.a4Portrait')}
        </span>
      </div>
      <div className="p-8 lg:p-10 space-y-5 min-h-[500px]">
        {blocks.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-center">
            <Sparkles className="w-12 h-12 text-[var(--text-secondary)]/30 mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">{t('templates49ReportBuilder.previewEmpty')}</p>
          </div>
        ) : (
          blocks.map((b) => (
            <BlockRenderer
              key={b.id}
              block={b}
              active={b.id === selectedId}
              onClick={() => onSelect(b.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function BlockRenderer({
  block: b, active, onClick,
}: { block: ReportBlock; active: boolean; onClick: () => void }) {
  const t = useT();
  return (
    <div
      onClick={onClick}
      className={cn(
        'group cursor-pointer rounded-md-custom border-2 transition-all p-3',
        active ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5' : 'border-transparent hover:border-[var(--primary-gold)]/30',
      )}
    >
      {b.kind === 'heading' && (
        <h2 className="font-serif text-2xl text-[var(--text-primary)]">{b.title}</h2>
      )}
      {b.kind === 'text' && (
        <p className="text-sm text-[var(--text-primary)] leading-relaxed whitespace-pre-line">{b.body}</p>
      )}
      {b.kind === 'chart' && (
        <div>
          <p className="text-sm font-medium text-[var(--text-primary)] mb-2">{b.title}</p>
          <div className="aspect-[16/7] rounded-md-custom bg-gradient-to-br from-[var(--primary-gold)]/15 via-[var(--primary-gold)]/5 to-transparent border border-[var(--border-color)] flex items-center justify-center">
            <div className="flex flex-col items-center gap-2 text-[var(--text-secondary)]">
              <BarChart3 className="w-8 h-8 text-[var(--primary-gold-dark)]" />
              <span className="text-xs">{(b.chart_kind ?? 'CHART').toUpperCase()} · {b.dataset_id}</span>
            </div>
          </div>
        </div>
      )}
      {b.kind === 'table' && (
        <div>
          <p className="text-sm font-medium text-[var(--text-primary)] mb-2">{b.title}</p>
          <div className="rounded-md-custom border border-[var(--border-color)] overflow-hidden text-xs">
            <table className="w-full">
              <thead className="bg-[var(--bg-app)] text-[var(--text-secondary)]">
                <tr><th className="px-3 py-2 text-left">{t('templates49ReportBuilder.tableColA')}</th><th className="px-3 py-2 text-left">{t('templates49ReportBuilder.tableColB')}</th><th className="px-3 py-2 text-right">{t('templates49ReportBuilder.tableColMetric')}</th></tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                <tr><td className="px-3 py-2">Hà Nội</td><td className="px-3 py-2">Q1</td><td className="px-3 py-2 text-right font-mono">812.500.000₫</td></tr>
                <tr><td className="px-3 py-2">TP.HCM</td><td className="px-3 py-2">Q1</td><td className="px-3 py-2 text-right font-mono">1.245.300.000₫</td></tr>
                <tr><td className="px-3 py-2">Đà Nẵng</td><td className="px-3 py-2">Q1</td><td className="px-3 py-2 text-right font-mono">438.900.000₫</td></tr>
              </tbody>
            </table>
          </div>
          <p className="text-[11px] text-[var(--text-secondary)] mt-2">{t('templates49ReportBuilder.datasetPrefix')} <span className="font-mono">{b.dataset_id}</span></p>
        </div>
      )}
      {b.kind === 'kpi' && (
        <div className="bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom p-4 inline-block min-w-[260px]">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">{b.title}</p>
          <p className="font-serif text-3xl text-[var(--text-primary)] mt-1">{b.metric}</p>
          {b.delta_pct != null && (
            <p className={cn('text-xs mt-1', b.delta_pct >= 0 ? 'text-[var(--state-success)]' : 'text-[var(--state-error)]')}>
              {b.delta_pct >= 0 ? '▲' : '▼'} {Math.abs(b.delta_pct)}% {t('templates49ReportBuilder.deltaVsPrev')}
            </p>
          )}
        </div>
      )}
      {b.kind === 'insight_ref' && (
        <div className="flex items-start gap-3 p-3 rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30">
          <Lightbulb className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <div className="min-w-0">
            <p className="text-sm font-medium text-[var(--text-primary)]">{b.title}</p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{t('templates49ReportBuilder.insightIdPrefix')} <span className="font-mono">{b.insight_id}</span></p>
          </div>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Inspector (right pane)
// ============================================================================

function Inspector({
  block, onChange,
}: { block: ReportBlock | null; onChange: (patch: Partial<ReportBlock>) => void }) {
  const t = useT();
  if (!block) {
    return (
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
        <div className="flex flex-col items-center justify-center py-12 text-center">
          <GripVertical className="w-10 h-10 text-[var(--text-secondary)]/30 mb-2" />
          <p className="text-sm text-[var(--text-secondary)]">{t('templates49ReportBuilder.selectBlockPrompt')}</p>
        </div>
      </div>
    );
  }

  const meta = BLOCK_PALETTE.find((m) => m.kind === block.kind)!;
  const Icon = meta.icon;

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-4">
      <div className="flex items-center gap-2 pb-3 border-b border-[var(--border-color)]/60">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-sm text-[var(--text-primary)]">{t(meta.label)}</h3>
      </div>

      {(block.kind === 'heading' || block.kind === 'chart' || block.kind === 'table' || block.kind === 'kpi' || block.kind === 'insight_ref') && (
        <Input
          label={t('templates49ReportBuilder.titleLabel')}
          value={block.title ?? ''}
          onChange={(e) => onChange({ title: e.target.value })}
        />
      )}

      {block.kind === 'text' && (
        <div className="space-y-2">
          <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates49ReportBuilder.contentLabel')}</label>
          <textarea
            value={block.body ?? ''}
            onChange={(e) => onChange({ body: e.target.value })}
            rows={8}
            className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
          />
        </div>
      )}

      {block.kind === 'chart' && (
        <>
          <div className="space-y-2">
            <label className="text-sm font-medium text-[var(--text-primary)]">{t('templates49ReportBuilder.chartTypeLabel')}</label>
            <select
              value={block.chart_kind ?? 'bar'}
              onChange={(e) => onChange({ chart_kind: e.target.value })}
              className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
            >
              <option value="bar">{t('templates49ReportBuilder.chartBar')}</option>
              <option value="line">{t('templates49ReportBuilder.chartLine')}</option>
              <option value="pie">{t('templates49ReportBuilder.chartPie')}</option>
              <option value="scatter">{t('templates49ReportBuilder.chartScatter')}</option>
            </select>
          </div>
          <Input
            label={t('templates49ReportBuilder.datasetGoldLabel')}
            value={block.dataset_id ?? ''}
            onChange={(e) => onChange({ dataset_id: e.target.value })}
            placeholder={t('templates49ReportBuilder.datasetGoldPlaceholder')}
          />
        </>
      )}

      {block.kind === 'table' && (
        <Input
          label={t('templates49ReportBuilder.datasetGoldLabel')}
          value={block.dataset_id ?? ''}
          onChange={(e) => onChange({ dataset_id: e.target.value })}
        />
      )}

      {block.kind === 'kpi' && (
        <>
          <Input
            label={t('templates49ReportBuilder.valueLabel')}
            value={block.metric ?? ''}
            onChange={(e) => onChange({ metric: e.target.value })}
            placeholder={t('templates49ReportBuilder.valuePlaceholder')}
          />
          <Input
            label={t('templates49ReportBuilder.deltaPctLabel')}
            type="number"
            value={block.delta_pct ?? 0}
            onChange={(e) => onChange({ delta_pct: Number(e.target.value) })}
          />
        </>
      )}

      {block.kind === 'insight_ref' && (
        <Input
          label={t('templates49ReportBuilder.insightIdLabel')}
          value={block.insight_id ?? ''}
          onChange={(e) => onChange({ insight_id: e.target.value })}
          placeholder={t('templates49ReportBuilder.insightIdPlaceholder')}
          helperText={t('templates49ReportBuilder.insightIdHelper')}
        />
      )}
    </div>
  );
}
