'use client';

// ============================================================================
// LineageModal — Bronze → Silver → Gold trace (F-NEW3 v1 BE PR #150)
// ----------------------------------------------------------------------------
// Wires:
//   GET /api/v1/data/lineage?file_id=
//
// Reusable modal launched from /p2/data/bronze + /p2/data/silver row
// "Lineage" buttons. Renders a 3-card vertical chain so analysts can
// follow one bronze file all the way to its gold customer rollup
// without leaving the table.
//
// Card layout:
//   Bronze  always present (404 from BE = component never renders)
//   Silver  null state shows "chưa làm sạch" + invite to /pipeline
//   Gold    null state shows either:
//             - file_status failed/cleaning issue → "không có customer link"
//             - clean_data not carrying customer_external_id key →
//               "dataset này không phải customer feed (per MEDALLION)"
// ============================================================================

import React, { useEffect, useState } from 'react';
import {
  HardDrive, Layers, Sparkles, Loader2, X as XIcon,
  CheckCircle2, AlertCircle, ChevronDown, Link2, Users,
} from 'lucide-react';

import {
  Badge, ErrorBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';

// ============================================================================
// Types — mirror BE data_explorer.get_lineage shape
// ============================================================================

interface BronzeBlock {
  file_id:               string;
  run_id:                string;
  source_filename:       string;
  run_status:            string;
  uploaded_by:           string | null;
  sheet_name:            string | null;
  sheet_index:           number;
  detected_purpose:      string | null;
  detected_language:     string | null;
  row_count:             number;
  col_count:             number;
  file_format:           string;
  ingested_at:           string | null;
  run_row_count_bronze:  number | null;
  run_row_count_silver:  number | null;
  run_quality_score:     number | null;
}

interface AppliedRule {
  rule_id:       string;
  rule_category: string;
  rows_affected: number;
}

interface SilverBlock {
  row_count:           number;
  quality_avg_pct:     number;
  first_processed_at:  string | null;
  last_processed_at:   string | null;
  applied_rules_top:   AppliedRule[];
}

interface GoldBlock {
  linked_customer_count:  number;
  silver_rows_with_key:   number;
  distinct_ids_in_silver: number;
  customer_id_key:        string;
}

interface LineageResponse {
  data: {
    bronze: BronzeBlock;
    silver: SilverBlock | null;
    gold:   GoldBlock   | null;
  };
}

// ============================================================================
// Component
// ============================================================================

export default function LineageModal({
  fileId, onClose,
}: { fileId: string; onClose: () => void }) {
  const [data, setData]       = useState<LineageResponse['data'] | null>(null);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await api<LineageResponse>(
          `/api/v1/data/lineage?file_id=${encodeURIComponent(fileId)}`);
        setData(r.data);
      } catch (e) {
        setProblem(e as ProblemDetails);
      } finally {
        setLoading(false);
      }
    })();
  }, [fileId]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fade-in">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-2xl max-w-3xl w-full max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-color)]">
          <div className="min-w-0">
            <h3 className="font-serif text-lg text-[var(--text-primary)] flex items-center gap-2">
              <Link2 className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              Lineage — Bronze → Silver → Gold
            </h3>
            <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 font-mono">
              file_id: {fileId.slice(0, 8)}...
            </p>
          </div>
          <button onClick={onClose} aria-label="Đóng" className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {problem && <ErrorBanner problem={problem} />}

          {loading ? (
            <div className="text-center py-12 text-[var(--text-secondary)]">
              <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tra cứu lineage...
            </div>
          ) : data ? (
            <div className="space-y-3">
              <BronzeCard bronze={data.bronze} />
              <ChainArrow />
              <SilverCard silver={data.silver} />
              <ChainArrow />
              <GoldCard
                gold={data.gold}
                bronzePurpose={data.bronze.detected_purpose}
                silverNull={data.silver === null}
              />

              <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)] mt-4">
                <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                <p>
                  Gold link là <strong>best-effort</strong> — đếm customer_external_id
                  có trong silver clean_data của file này, rồi giao với gold_features.
                  null nghĩa là dataset không có customer key (per{' '}
                  <span className="font-mono">MEDALLION_CONTRACT.md</span>) hoặc file
                  chưa được làm sạch.
                </p>
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Cards
// ============================================================================

function BronzeCard({ bronze: b }: { bronze: BronzeBlock }) {
  const ingested = formatRelative(b.ingested_at);
  return (
    <Card
      tone="bronze"
      icon={HardDrive}
      title="Bronze"
      subtitle={b.source_filename}
      meta={`${b.row_count.toLocaleString('vi-VN')} hàng × ${b.col_count} cột · ingest ${ingested}`}
    >
      <div className="grid grid-cols-2 gap-3 mt-3 text-xs">
        <Field label="Format" value={b.file_format.toUpperCase()} />
        <Field label="Sheet" value={b.sheet_name ?? `#${b.sheet_index}`} />
        <Field label="Mục đích" value={b.detected_purpose ?? '—'} />
        <Field label="Ngôn ngữ" value={b.detected_language ?? '—'} />
        <Field label="Run status" value={
          <Badge variant={statusVariant(b.run_status)}>{b.run_status}</Badge>
        } />
        <Field label="Run quality" value={
          b.run_quality_score != null
            ? `${(b.run_quality_score * 100).toFixed(1)}%`
            : '—'
        } />
      </div>
    </Card>
  );
}

function SilverCard({ silver: s }: { silver: SilverBlock | null }) {
  if (s === null) {
    return (
      <Card
        tone="silver" icon={Layers} title="Silver" subtitle="Chưa làm sạch"
        meta="File này chưa qua bước cleaning."
        muted
      >
        <p className="text-xs text-[var(--text-secondary)] mt-2">
          Mở{' '}
          <a href="/p2/data" className="text-[var(--primary-gold-dark)] hover:underline">
            trang Khám phá
          </a>{' '}
          → chọn file để chạy bước cleaning.
        </p>
      </Card>
    );
  }

  const last = formatRelative(s.last_processed_at);
  return (
    <Card
      tone="silver"
      icon={Layers}
      title="Silver"
      subtitle={`${s.row_count.toLocaleString('vi-VN')} hàng đã sạch`}
      meta={`Chất lượng TB ${s.quality_avg_pct.toFixed(1)}% · xử lý lần cuối ${last}`}
    >
      <div className="mt-3">
        <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">
          Top rules áp dụng
        </p>
        <div className="flex flex-wrap gap-1.5">
          {s.applied_rules_top.length === 0 ? (
            <span className="text-[11px] text-[var(--text-secondary)] italic">— chưa có rule</span>
          ) : (
            s.applied_rules_top.map((r) => (
              <Badge key={r.rule_id} variant="default">
                <span className="font-mono text-[10px]">{r.rule_id}</span>
                <span className="ml-1 text-[var(--text-secondary)] font-normal">
                  ({r.rows_affected.toLocaleString('vi-VN')})
                </span>
              </Badge>
            ))
          )}
        </div>
      </div>
    </Card>
  );
}

function GoldCard({
  gold: g, bronzePurpose, silverNull,
}: { gold: GoldBlock | null; bronzePurpose: string | null; silverNull: boolean }) {
  if (g === null) {
    const reason = silverNull
      ? 'Chưa có Silver — Gold không thể link.'
      : `Dataset "${bronzePurpose ?? 'unknown'}" không có cột customer_external_id (per MEDALLION_CONTRACT). Đây là feed phi-customer (vd. inventory).`;
    return (
      <Card
        tone="gold" icon={Sparkles} title="Gold" subtitle="Không có customer link"
        meta={reason}
        muted
      />
    );
  }

  return (
    <Card
      tone="gold"
      icon={Sparkles}
      title="Gold"
      subtitle={`${g.linked_customer_count.toLocaleString('vi-VN')} khách trong gold_features`}
      meta={`${g.distinct_ids_in_silver.toLocaleString('vi-VN')} ID phân biệt trong Silver · key ${g.customer_id_key}`}
    >
      <div className="grid grid-cols-3 gap-3 mt-3 text-xs">
        <Field label="Silver rows có key" value={g.silver_rows_with_key.toLocaleString('vi-VN')} />
        <Field label="ID phân biệt" value={g.distinct_ids_in_silver.toLocaleString('vi-VN')} />
        <Field label="Khớp gold" value={
          <span className="inline-flex items-center gap-1 text-[var(--state-success)]">
            <Users className="w-3 h-3" /> {g.linked_customer_count.toLocaleString('vi-VN')}
          </span>
        } />
      </div>
    </Card>
  );
}

// ============================================================================
// Card primitives
// ============================================================================

function Card({
  tone, icon: Icon, title, subtitle, meta, muted, children,
}: {
  tone:     'bronze' | 'silver' | 'gold';
  icon:     React.ComponentType<{ className?: string }>;
  title:    string;
  subtitle: string;
  meta:     string;
  muted?:   boolean;
  children?: React.ReactNode;
}) {
  const accent = ({
    bronze: 'border-l-[#BFA88C]',
    silver: 'border-l-[#A5B4CB]',
    gold:   'border-l-[var(--primary-gold)]',
  } as const)[tone];

  return (
    <div className={cn(
      'rounded-lg-custom border border-l-4 p-4 shadow-soft-sm',
      accent,
      muted ? 'bg-[var(--bg-app)]/40' : 'bg-[var(--bg-card)] border-[var(--border-color)]',
      muted && 'border-[var(--border-color)]',
    )}>
      <div className="flex items-start gap-3">
        <div className={cn(
          'w-9 h-9 rounded-md-custom flex items-center justify-center shrink-0',
          muted ? 'bg-[var(--border-color)]/20' : 'bg-[var(--primary-gold)]/12',
        )}>
          <Icon className={cn('w-4 h-4', muted ? 'text-[var(--text-secondary)]' : 'text-[var(--primary-gold-dark)]')} />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-serif text-base text-[var(--text-primary)]">
            {title} {muted && <span className="text-xs text-[var(--text-secondary)] italic">— null</span>}
          </p>
          <p className="text-sm text-[var(--text-primary)] truncate">{subtitle}</p>
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-relaxed">{meta}</p>
        </div>
      </div>
      {children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <div className="text-[var(--text-primary)] mt-0.5">{value}</div>
    </div>
  );
}

function ChainArrow() {
  return (
    <div className="flex justify-center py-1">
      <ChevronDown className="w-5 h-5 text-[var(--text-secondary)]/40" />
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function formatRelative(iso: string | null): string {
  if (!iso) return '—';
  const diff = Date.now() - +new Date(iso);
  if (Number.isNaN(diff))     return iso;
  if (diff < 60_000)          return 'vừa xong';
  if (diff < 3_600_000)       return `${Math.round(diff / 60_000)} phút trước`;
  if (diff < 86_400_000)      return `${Math.round(diff / 3_600_000)} giờ trước`;
  if (diff < 7 * 86_400_000)  return `${Math.round(diff / 86_400_000)} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}

function statusVariant(s: string): 'success' | 'warning' | 'error' | 'info' | 'current' | 'default' {
  switch (s) {
    case 'analysis_complete':
    case 'silver_complete':
    case 'bronze_complete':
      return 'success';
    case 'analyzing':
      return 'warning';
    case 'failed':
    case 'cancelled':
      return 'error';
    case 'schema_review':
      return 'current';
    case 'uploading':
      return 'info';
    default:
      return 'default';
  }
}
