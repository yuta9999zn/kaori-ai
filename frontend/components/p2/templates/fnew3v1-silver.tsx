'use client';

// ============================================================================
// /p2/data/silver — Silver drill-down (F-NEW3 v1 BE PR #148)
// ----------------------------------------------------------------------------
// Wires:
//   GET /api/v1/data/silver/datasets?cursor=&limit=
//   GET /api/v1/data/silver/datasets/{file_id}/sample?limit=
//
// Layout:
//   Header  → back link to /p2/data
//   Table   → silver datasets (cursor-paginated): filename · cleaned rows
//             count · quality bar · top-3 applied rule pills · last
//             processed at · "Xem" button
//   Modal   → cleaned-row preview (clean_data + applied_rules + quality
//             score per row) + CSV export of cleaned rows
//
// K-5 reminder: clean_data already has PII redacted by the cleaning
// pipeline; we just render what the BE gives us.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Layers, ArrowLeft, Eye, Loader2, ChevronLeft, ChevronRight,
  X as XIcon, Download, Database, Sparkles, Link2,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import LineageModal from '@/components/p2/templates/fnew3v1-lineage-modal';
import { useT } from '@/lib/i18n/provider';

// ============================================================================
// Types
// ============================================================================

interface AppliedRule {
  rule_id:       string;
  rule_category: string;
  rows_affected: number;
}

interface SilverDataset {
  file_id:            string;
  source_filename:    string;
  sheet_name:         string | null;
  run_status:         string;
  row_count:          number;
  col_count:          number;
  quality_avg_pct:    number;
  first_processed_at: string | null;
  last_processed_at:  string | null;
  applied_rules_top:  AppliedRule[];
}

interface ListResponse {
  data: SilverDataset[];
  meta: { cursor: string | null; limit: number; count: number; has_more: boolean };
}

interface SampleResponse {
  data: {
    file: {
      file_id:           string;
      sheet_name:        string | null;
      row_count:         number;
      col_count:         number;
      file_format:       string;
      source_filename:   string;
      last_processed_at: string | null;
    };
    rows: Array<{
      row_index:     number;
      clean_data:    Record<string, unknown>;
      applied_rules: string[];
      quality_score: number | null;
      created_at:    string;
    }>;
    limit: number;
  };
}

// ============================================================================
// Page
// ============================================================================

export default function SilverDrillDownPage() {
  const t = useT();
  const [datasets, setDatasets]       = useState<SilverDataset[]>([]);
  const [loading, setLoading]         = useState(true);
  const [problem, setProblem]         = useState<ProblemDetails | null>(null);
  const [nextCursor, setNextCursor]   = useState<string | null>(null);
  const [cursorStack, setCursorStack] = useState<string[]>([]);
  const [selected, setSelected]       = useState<SilverDataset | null>(null);
  const [lineageFor, setLineageFor]   = useState<string | null>(null);

  async function loadList(cursor: string | null = null) {
    setLoading(true);
    setProblem(null);
    try {
      const params = new URLSearchParams({ limit: '50' });
      if (cursor) params.set('cursor', cursor);
      const r = await api<ListResponse>(`/api/v1/data/silver/datasets?${params}`);
      setDatasets(r.data ?? []);
      setNextCursor(r.meta.cursor);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setCursorStack([]);
    loadList(null);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function pageNext() {
    if (!nextCursor) return;
    setCursorStack((prev) => [...prev, nextCursor]);
    loadList(nextCursor);
  }
  function pagePrev() {
    if (cursorStack.length === 0) return;
    const prev = cursorStack.slice(0, -1);
    setCursorStack(prev);
    loadList(prev.at(-1) ?? null);
  }

  return (
    <>
      <PageHeader
        title={t('templatesFnew3v1Silver.title')}
        description={t('templatesFnew3v1Silver.description')}
        actions={
          <>
            <Badge variant="info">F-NEW3 v1</Badge>
            <a href="/p2/data">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templatesFnew3v1Silver.btnExplore')}</Button>
            </a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}

        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">{t('templatesFnew3v1Silver.thFileSheet')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Silver.thRowsCleaned')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Silver.thQualityAvg')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Silver.thRulesApplied')}</th>
                  <th className="px-5 py-3">{t('templatesFnew3v1Silver.thLastProcessed')}</th>
                  <th className="px-5 py-3 text-right">{t('templatesFnew3v1Silver.thViewSample')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading && datasets.length === 0 ? (
                  <tr><td colSpan={6} className="px-5 py-12 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesFnew3v1Silver.loadingList')}
                  </td></tr>
                ) : datasets.length === 0 ? (
                  <tr><td colSpan={6} className="px-5 py-12 text-center">
                    <Database className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">
                      {t('templatesFnew3v1Silver.emptyTitle')}
                    </p>
                  </td></tr>
                ) : (
                  datasets.map((d) => (
                    <SilverDatasetRow
                      key={d.file_id}
                      dataset={d}
                      onView={() => setSelected(d)}
                      onLineage={() => setLineageFor(d.file_id)}
                    />
                  ))
                )}
              </tbody>
            </table>
          </div>

          {(cursorStack.length > 0 || nextCursor) && (
            <div className="px-5 py-3 border-t border-[var(--border-color)] flex items-center justify-between">
              <Button
                variant="tertiary" size="sm" onClick={pagePrev}
                disabled={cursorStack.length === 0 || loading}
              >
                <ChevronLeft className="w-3.5 h-3.5 mr-1" /> {t('templatesFnew3v1Silver.pagePrev')}
              </Button>
              <span className="text-xs text-[var(--text-secondary)]">
                {t('templatesFnew3v1Silver.pageLabel', { page: cursorStack.length + 1 })}
              </span>
              <Button
                variant="tertiary" size="sm" onClick={pageNext}
                disabled={!nextCursor || loading}
              >
                {t('templatesFnew3v1Silver.pageNext')} <ChevronRight className="w-3.5 h-3.5 ml-1" />
              </Button>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <Layers className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            {t('templatesFnew3v1Silver.footnotePart1')}{' '}
            <span className="font-mono">&lt;EMAIL_1&gt;</span>{t('templatesFnew3v1Silver.footnotePart2')}
          </p>
        </div>
      </div>

      {selected && (
        <SilverSampleModal dataset={selected} onClose={() => setSelected(null)} />
      )}

      {lineageFor && (
        <LineageModal fileId={lineageFor} onClose={() => setLineageFor(null)} />
      )}
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function SilverDatasetRow({
  dataset: d, onView, onLineage,
}: { dataset: SilverDataset; onView: () => void; onLineage: () => void }) {
  const t = useT();
  const ingested = formatRelative(d.last_processed_at, t);
  const qualityVariant: 'success' | 'warning' | 'error' =
    d.quality_avg_pct >= 90 ? 'success'
    : d.quality_avg_pct >= 75 ? 'warning'
    : 'error';

  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4">
        <p className="text-sm font-medium text-[var(--text-primary)]">{d.source_filename}</p>
        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 font-mono">
          {d.file_id.slice(0, 8)}...{d.sheet_name ? ` · ${d.sheet_name}` : ''}
        </p>
      </td>
      <td className="px-5 py-4 text-right text-sm text-[var(--text-primary)]">
        {d.row_count.toLocaleString('vi-VN')}
      </td>
      <td className="px-5 py-4 min-w-[140px]">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-[var(--border-color)]/40 rounded-full overflow-hidden">
            <div
              className={cn(
                'h-full',
                qualityVariant === 'success' && 'bg-[var(--state-success)]',
                qualityVariant === 'warning' && 'bg-[var(--state-warning)]',
                qualityVariant === 'error'   && 'bg-[var(--state-error)]',
              )}
              style={{ width: `${d.quality_avg_pct}%` }}
            />
          </div>
          <span className="text-xs font-mono text-[var(--text-primary)] w-12 text-right">
            {d.quality_avg_pct.toFixed(1)}%
          </span>
        </div>
      </td>
      <td className="px-5 py-4">
        <div className="flex flex-wrap gap-1">
          {d.applied_rules_top.slice(0, 3).map((r) => (
            <Badge key={r.rule_id} variant="default">
              <span className="font-mono text-[10px]">{r.rule_id}</span>
              <span className="ml-1 text-[var(--text-secondary)] font-normal">
                ({r.rows_affected.toLocaleString('vi-VN')})
              </span>
            </Badge>
          ))}
          {d.applied_rules_top.length === 0 && (
            <span className="text-[11px] text-[var(--text-secondary)] italic">{t('templatesFnew3v1Silver.noRule')}</span>
          )}
        </div>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">{ingested}</td>
      <td className="px-5 py-4 text-right">
        <div className="inline-flex items-center gap-1">
          <Button variant="tertiary" size="sm" onClick={onLineage} title={t('templatesFnew3v1Silver.lineageTooltip')}>
            <Link2 className="w-3.5 h-3.5" />
          </Button>
          <Button variant="tertiary" size="sm" onClick={onView}>
            <Eye className="w-3.5 h-3.5 mr-1.5" /> {t('templatesFnew3v1Silver.viewBtn')}
          </Button>
        </div>
      </td>
    </tr>
  );
}

function SilverSampleModal({ dataset, onClose }: { dataset: SilverDataset; onClose: () => void }) {
  const t = useT();
  const [data, setData]       = useState<SampleResponse['data'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api<SampleResponse>(
          `/api/v1/data/silver/datasets/${dataset.file_id}/sample?limit=50`);
        setData(r.data);
      } catch (e) {
        setProblem(e as ProblemDetails);
      } finally {
        setLoading(false);
      }
    })();
  }, [dataset.file_id]);

  const columns = useMemo(() => {
    if (!data?.rows.length) return [];
    return Object.keys(data.rows[0].clean_data);
  }, [data]);

  function downloadCsv() {
    if (!data) return;
    const header = [...columns, 'applied_rules', 'quality_score'].map(quoteCsv).join(',');
    const lines  = data.rows.map((r) => {
      const cells = columns.map((c) => quoteCsv(formatCell(r.clean_data[c])));
      cells.push(quoteCsv(r.applied_rules.join('|')));
      cells.push(quoteCsv(r.quality_score == null ? '' : String(r.quality_score)));
      return cells.join(',');
    });
    const csv  = [header, ...lines].join('\r\n');
    const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `${dataset.source_filename.replace(/\.[^.]+$/, '')}-cleaned-sample.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fade-in">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-2xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-color)]">
          <div className="min-w-0">
            <h3 className="font-serif text-lg text-[var(--text-primary)] truncate">
              {dataset.source_filename}
            </h3>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              {t('templatesFnew3v1Silver.modalSubtitle', { count: dataset.row_count.toLocaleString('vi-VN'), pct: dataset.quality_avg_pct.toFixed(1) })}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="tertiary" size="sm" onClick={downloadCsv}
              disabled={!data || data.rows.length === 0}
            >
              <Download className="w-3.5 h-3.5 mr-1" /> {t('templatesFnew3v1Silver.csvSample')}
            </Button>
            <button onClick={onClose} aria-label={t('templatesFnew3v1Silver.closeAria')} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
              <XIcon className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {problem && <ErrorBanner problem={problem} />}

          {loading ? (
            <div className="text-center py-12 text-[var(--text-secondary)]">
              <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templatesFnew3v1Silver.loadingSample')}
            </div>
          ) : data && data.rows.length > 0 ? (
            <>
              <div className="overflow-auto border border-[var(--border-color)] rounded-md-custom">
                <table className="text-xs text-left w-full">
                  <thead className="bg-[var(--bg-app)] sticky top-0">
                    <tr>
                      <th className="px-3 py-2 font-medium text-[var(--text-secondary)] border-b border-[var(--border-color)]">#</th>
                      {columns.map((c) => (
                        <th key={c} className="px-3 py-2 font-medium text-[var(--text-secondary)] border-b border-[var(--border-color)] whitespace-nowrap">
                          {c}
                        </th>
                      ))}
                      <th className="px-3 py-2 font-medium text-[var(--text-secondary)] border-b border-[var(--border-color)]">{t('templatesFnew3v1Silver.thRules')}</th>
                      <th className="px-3 py-2 font-medium text-[var(--text-secondary)] border-b border-[var(--border-color)] text-right">{t('templatesFnew3v1Silver.thQuality')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border-color)]/40">
                    {data.rows.map((r) => (
                      <tr key={r.row_index} className="hover:bg-[var(--bg-app)]/40">
                        <td className="px-3 py-1.5 font-mono text-[var(--text-secondary)]">{r.row_index + 1}</td>
                        {columns.map((c) => (
                          <td key={c} className="px-3 py-1.5 text-[var(--text-primary)] whitespace-nowrap max-w-xs truncate">
                            {formatCell(r.clean_data[c])}
                          </td>
                        ))}
                        <td className="px-3 py-1.5">
                          <div className="flex flex-wrap gap-1">
                            {r.applied_rules.map((rid) => (
                              <span key={rid} className="font-mono text-[10px] px-1.5 py-0.5 rounded-sm-custom bg-[var(--bg-app)] text-[var(--text-secondary)]">
                                {rid}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-3 py-1.5 text-right font-mono text-[var(--text-primary)]">
                          {r.quality_score == null ? '—' : r.quality_score.toFixed(2)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-[11px] text-[var(--text-secondary)] mt-3">
                {t('templatesFnew3v1Silver.sampleFooter', { shown: data.rows.length, total: data.file.row_count.toLocaleString('vi-VN'), limit: data.limit })}
                <Sparkles className="w-3 h-3 inline ml-1 text-[var(--primary-gold-dark)]" /> {t('templatesFnew3v1Silver.sampleFooterPart2')}
              </p>
            </>
          ) : (
            <div className="text-center py-12 text-[var(--text-secondary)]">
              {t('templatesFnew3v1Silver.noRows')}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatRelative(iso: string | null, t: ReturnType<typeof useT>): string {
  if (!iso) return '—';
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff))     return iso;
  if (diff < 60_000)          return t('templatesFnew3v1Silver.relJustNow');
  if (diff < 3_600_000)       return t('templatesFnew3v1Silver.relMinutesAgo', { count: Math.round(diff / 60_000) });
  if (diff < 86_400_000)      return t('templatesFnew3v1Silver.relHoursAgo', { count: Math.round(diff / 3_600_000) });
  if (diff < 7 * 86_400_000)  return t('templatesFnew3v1Silver.relDaysAgo', { count: Math.round(diff / 86_400_000) });
  return new Date(iso).toLocaleDateString('vi-VN');
}

function formatCell(v: unknown): string {
  if (v === null || v === undefined) return '';
  if (typeof v === 'object') return JSON.stringify(v);
  return String(v);
}

function quoteCsv(value: string): string {
  if (value === '' || value == null) return '';
  if (/[",\r\n]/.test(value)) return '"' + value.replace(/"/g, '""') + '"';
  return value;
}
