// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 65. /p2/auto-db/schema-suggestion — Schema Suggestion (F-057 🔵 Phase 2)
// ----------------------------------------------------------------------------
// AI quét file/dataset upload → đề xuất schema (table + columns + types):
//   - Upload file CSV/Excel hoặc chọn Bronze dataset đã có.
//   - Kaori AI phân tích → đề xuất 1+ table với columns + types + nullable
//     + foreign key + index.
//   - User accept/reject từng cột; có thể đổi tên + type trước khi commit.
//   - ER diagram preview thuần SVG (Phase 2 sẽ vẽ realtime).
//
// Wire (Phase 2): `POST /api/v1/auto-db/schema/suggest` (LLM K-3) →
// `POST /api/v1/auto-db/schema/commit`.
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  Database, ArrowLeft, Sparkles, UploadCloud, RefreshCw, Check, X,
  ShieldCheck, Hash, Type, Calendar, ToggleLeft, FileBadge,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useT } from '@/lib/i18n/provider';
// ============================================================================
// Types
// ============================================================================

type ColumnType = 'integer' | 'numeric' | 'varchar' | 'date' | 'timestamp' | 'boolean';

interface SuggestedColumn {
  name:       string;
  type:       ColumnType;
  nullable:   boolean;
  is_pk:      boolean;
  fk_to?:     string | null;
  reasoning:  string;
  confidence: number;  // 0-1
  accepted:   boolean;
}

interface SuggestedTable {
  name:    string;
  rows:    number;
  columns: SuggestedColumn[];
}

const TYPE_META: Record<ColumnType, { label: string; icon: any }> = {
  integer:   { label: 'INTEGER',   icon: Hash },
  numeric:   { label: 'NUMERIC',   icon: Hash },
  varchar:   { label: 'VARCHAR',   icon: Type },
  date:      { label: 'DATE',      icon: Calendar },
  timestamp: { label: 'TIMESTAMP', icon: Calendar },
  boolean:   { label: 'BOOLEAN',   icon: ToggleLeft },
};

// Mock fixture: AI đã phân tích file orders_2026.csv → đề xuất 2 bảng.
const INITIAL_TABLES: SuggestedTable[] = [
  {
    name: 'orders',
    rows: 12_540,
    columns: [
      { name: 'order_id',     type: 'integer',   nullable: false, is_pk: true,  reasoning: 'Cột số nguyên duy nhất, chỉ tăng — phù hợp PK.',                       confidence: 0.98, accepted: true },
      { name: 'customer_id',  type: 'integer',   nullable: false, is_pk: false, fk_to: 'customers.customer_id', reasoning: 'Match 100% với customer_id trong customers.', confidence: 0.95, accepted: true },
      { name: 'order_date',   type: 'date',      nullable: false, is_pk: false, reasoning: 'Format YYYY-MM-DD nhất quán, không có giờ phút.',                       confidence: 0.92, accepted: true },
      { name: 'total_amount', type: 'numeric',   nullable: false, is_pk: false, reasoning: 'Tiền VND, có 0-2 chữ số thập phân — chọn NUMERIC(14,4) theo K-9.',     confidence: 0.91, accepted: true },
      { name: 'status',       type: 'varchar',   nullable: false, is_pk: false, reasoning: '5 giá trị enum: pending/paid/shipped/delivered/cancelled.',             confidence: 0.88, accepted: true },
      { name: 'note',         type: 'varchar',   nullable: true,  is_pk: false, reasoning: '32% null. Free-text dưới 200 ký tự — VARCHAR(200) đủ.',                  confidence: 0.74, accepted: false },
    ],
  },
  {
    name: 'customers',
    rows: 4_220,
    columns: [
      { name: 'customer_id', type: 'integer',  nullable: false, is_pk: true,  reasoning: 'Số nguyên unique — PK.',                                  confidence: 0.99, accepted: true },
      { name: 'full_name',   type: 'varchar',  nullable: false, is_pk: false, reasoning: 'Tên người, max 64 ký tự — VARCHAR(100).',                  confidence: 0.94, accepted: true },
      { name: 'email',       type: 'varchar',  nullable: true,  is_pk: false, reasoning: '12% null. Format email hợp lệ — VARCHAR(120) + index unique.', confidence: 0.93, accepted: true },
      { name: 'created_at',  type: 'timestamp', nullable: false, is_pk: false, reasoning: 'Có giờ phút giây — TIMESTAMP WITH TIME ZONE.',           confidence: 0.96, accepted: true },
    ],
  },
];

// ============================================================================
// Page
// ============================================================================

export default function SchemaSuggestionPage() {
  const t = useT();
  const [tables, setTables] = useState<SuggestedTable[]>(INITIAL_TABLES);
  const [submitting, setSubmitting] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [allowExternal, setAllowExternal] = useState(false);

  function patchColumn(tableName: string, colName: string, patch: Partial<SuggestedColumn>) {
    setTables((prev) => prev.map((t) =>
      t.name !== tableName ? t : {
        ...t,
        columns: t.columns.map((c) => c.name === colName ? { ...c, ...patch } : c),
      },
    ));
  }

  const stats = useMemo(() => {
    const all = tables.flatMap((t) => t.columns);
    return {
      total:     all.length,
      accepted:  all.filter((c) => c.accepted).length,
      lowConf:   all.filter((c) => c.confidence < 0.8).length,
    };
  }, [tables]);

  async function onRegenerate() {
    setRegenerating(true);
    setProblem(null);
    setSuccess(null);
    try {
      // Phase 2 wire LLM here
      await new Promise((r) => setTimeout(r, 1500));
      setSuccess(t('templates65AutodbSchemaSuggestion.successRegenerate'));
    } catch (e: any) {
      setProblem(e);
    } finally {
      setRegenerating(false);
    }
  }

  async function onCommit() {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      const acceptedTables = tables.map((t) => ({
        ...t,
        columns: t.columns.filter((c) => c.accepted),
      })).filter((t) => t.columns.length > 0);

      await api('/api/v1/auto-db/schema/commit', {
        method: 'POST',
        body: JSON.stringify({ tables: acceptedTables, consent_external: allowExternal }),
      });
      setSuccess(t('templates65AutodbSchemaSuggestion.successCommit', { tables: acceptedTables.length, cols: stats.accepted }));
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates65AutodbSchemaSuggestion.title')}
        description={t('templates65AutodbSchemaSuggestion.description')}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-057</Badge>
            <a href="/p2/auto-db">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Auto DB</Button>
            </a>
            <Button variant="secondary" size="md" onClick={onRegenerate} isLoading={regenerating} disabled={regenerating}>
              <RefreshCw className="w-4 h-4 mr-2" /> {t('templates65AutodbSchemaSuggestion.btnRegenerate')}
            </Button>
            <Button variant="primary" size="md" onClick={onCommit} disabled={stats.accepted === 0 || submitting} isLoading={submitting}>
              <Check className="w-4 h-4 mr-2" /> {t('templates65AutodbSchemaSuggestion.btnCommit', { count: stats.accepted })}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {/* Source + summary */}
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4 items-stretch">
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
            <div className="flex items-center gap-2 mb-3">
              <UploadCloud className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <h3 className="font-serif text-base text-[var(--text-primary)]">{t('templates65AutodbSchemaSuggestion.sourceHeading')}</h3>
            </div>
            <div className="flex items-center gap-3 p-3 rounded-md-custom bg-[var(--bg-app)] border border-[var(--border-color)]">
              <FileBadge className="w-5 h-5 text-[var(--primary-gold-dark)]" />
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-[var(--text-primary)]">orders_2026.csv</p>
                <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
                  {t('templates65AutodbSchemaSuggestion.sourceMeta', { rows: '16.760', cols: '10', uploadedAt: '2026-04-30 14:18', hash: 'a3f8c…b21d' })}
                </p>
              </div>
              <Badge variant="success">Bronze ready</Badge>
            </div>
          </div>
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm flex flex-col justify-center">
            <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] font-medium">{t('templates65AutodbSchemaSuggestion.summaryHeading')}</p>
            <p className="font-serif text-2xl text-[var(--text-primary)] mt-1">
              {t('templates65AutodbSchemaSuggestion.summaryAcceptedCols', { accepted: stats.accepted, total: stats.total })}
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-1">
              {stats.lowConf > 0 && (
                <span className="text-[var(--state-warning)]">{t('templates65AutodbSchemaSuggestion.summaryLowConf', { count: stats.lowConf })}</span>
              )}
              {t('templates65AutodbSchemaSuggestion.summaryReviewNote')}
            </p>
          </div>
        </div>

        {/* Consent */}
        <label className="flex items-start gap-3 p-3 rounded-md-custom border border-[var(--border-color)] bg-[var(--bg-card)] cursor-pointer hover:border-[var(--primary-gold)]/40 transition-colors shadow-soft-sm">
          <input
            type="checkbox"
            checked={allowExternal}
            onChange={(e) => setAllowExternal(e.target.checked)}
            className="mt-0.5 w-4 h-4 accent-[var(--primary-gold)]"
          />
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)]">
              {t('templates65AutodbSchemaSuggestion.consentLabel')}
            </p>
            <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">
              {t('templates65AutodbSchemaSuggestion.consentDetail')}
            </p>
          </div>
        </label>

        {/* Tables */}
        {tables.map((t) => (
          <TableCard
            key={t.name}
            table={t}
            onPatchColumn={(colName, patch) => patchColumn(t.name, colName, patch)}
          />
        ))}

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templates65AutodbSchemaSuggestion.footerNotePart1')} <span className="font-mono">decision_audit_log</span>{' '}
            {t('templates65AutodbSchemaSuggestion.footerNotePart2')}
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function TableCard({
  table: t, onPatchColumn,
}: { table: SuggestedTable; onPatchColumn: (colName: string, patch: Partial<SuggestedColumn>) => void }) {
  const tt = useT();
  const acceptedCount = t.columns.filter((c) => c.accepted).length;
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between bg-[var(--bg-app)]">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
            <Database className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          </div>
          <div>
            <p className="font-mono text-base font-medium text-[var(--text-primary)]">{t.name}</p>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
              {tt('templates65AutodbSchemaSuggestion.tableRowsCols', { rows: t.rows.toLocaleString('vi-VN'), accepted: acceptedCount, total: t.columns.length })}
            </p>
          </div>
        </div>
        <Badge variant="info">{tt('templates65AutodbSchemaSuggestion.tableColsBadge', { count: t.columns.length })}</Badge>
      </div>
      <div className="overflow-auto">
        <table className="w-full text-sm text-left">
          <thead className="border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)] bg-[var(--bg-card)]">
            <tr>
              <th className="px-5 py-3 w-10">{tt('templates65AutodbSchemaSuggestion.colSelect')}</th>
              <th className="px-5 py-3">{tt('templates65AutodbSchemaSuggestion.colName')}</th>
              <th className="px-5 py-3">{tt('templates65AutodbSchemaSuggestion.colType')}</th>
              <th className="px-5 py-3">Null?</th>
              <th className="px-5 py-3">{tt('templates65AutodbSchemaSuggestion.colKey')}</th>
              <th className="px-5 py-3">Confidence</th>
              <th className="px-5 py-3">{tt('templates65AutodbSchemaSuggestion.colReasoning')}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-color)]/60">
            {t.columns.map((c) => <ColumnRow key={c.name} column={c} onPatch={(p) => onPatchColumn(c.name, p)} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ColumnRow({
  column: c, onPatch,
}: { column: SuggestedColumn; onPatch: (p: Partial<SuggestedColumn>) => void }) {
  const t = useT();
  const typeMeta = TYPE_META[c.type];
  const TypeIcon = typeMeta.icon;
  const confVariant: 'success' | 'info' | 'warning' | 'error' =
    c.confidence >= 0.9 ? 'success' :
    c.confidence >= 0.8 ? 'info' :
    c.confidence >= 0.7 ? 'warning' : 'error';

  return (
    <tr className={cn(
      'transition-colors',
      c.accepted ? 'hover:bg-[var(--bg-app)]/40' : 'bg-[var(--state-error)]/4 opacity-60',
    )}>
      <td className="px-5 py-3">
        <button
          onClick={() => onPatch({ accepted: !c.accepted })}
          className={cn(
            'w-6 h-6 rounded-sm-custom border flex items-center justify-center transition-colors',
            c.accepted
              ? 'bg-[var(--state-success)] border-[var(--state-success)]'
              : 'border-[var(--border-color)] hover:border-[var(--primary-gold)]',
          )}
          aria-label={c.accepted ? t('templates65AutodbSchemaSuggestion.ariaDeselect') : t('templates65AutodbSchemaSuggestion.ariaSelect')}
        >
          {c.accepted ? <Check className="w-4 h-4 text-white" /> : <X className="w-3 h-3 text-[var(--text-secondary)]" />}
        </button>
      </td>
      <td className="px-5 py-3">
        <input
          value={c.name}
          onChange={(e) => onPatch({ name: e.target.value })}
          className="font-mono text-sm text-[var(--text-primary)] bg-transparent border-0 focus:outline-none focus:ring-0 p-0 w-full"
          disabled={!c.accepted}
        />
      </td>
      <td className="px-5 py-3">
        <select
          value={c.type}
          onChange={(e) => onPatch({ type: e.target.value as ColumnType })}
          disabled={!c.accepted}
          className="text-xs font-mono text-[var(--text-primary)] bg-[var(--bg-app)] border border-[var(--border-color)] rounded-sm-custom px-2 py-1 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
        >
          {(['integer', 'numeric', 'varchar', 'date', 'timestamp', 'boolean'] as ColumnType[]).map((t) => (
            <option key={t} value={t}>{TYPE_META[t].label}</option>
          ))}
        </select>
      </td>
      <td className="px-5 py-3">
        <input
          type="checkbox"
          checked={c.nullable}
          onChange={(e) => onPatch({ nullable: e.target.checked })}
          disabled={!c.accepted}
          className="w-4 h-4 accent-[var(--primary-gold)]"
        />
      </td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-1">
          {c.is_pk && <Badge variant="current">PK</Badge>}
          {c.fk_to && <Badge variant="info">FK → {c.fk_to}</Badge>}
        </div>
      </td>
      <td className="px-5 py-3">
        <Badge variant={confVariant}>{Math.round(c.confidence * 100)}%</Badge>
      </td>
      <td className="px-5 py-3 text-xs text-[var(--text-secondary)] max-w-md leading-relaxed">{c.reasoning}</td>
    </tr>
  );
}
