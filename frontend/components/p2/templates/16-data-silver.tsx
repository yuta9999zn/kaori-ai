// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 16. /p2/data/silver — Silver layer (cleaned + PII-masked, K-5)
// ----------------------------------------------------------------------------
// GET /api/v1/data/silver/datasets (cursor)
// GET /api/v1/data/silver/datasets/:id   (preview + schema + applied rules)
//
// K-5 critical:
//   - PII fields rendered with mask placeholders: <EMAIL_1>, <PHONE_1>, <NAME_1>
//   - Mask is enforced server-side; UI surfaces an info badge per masked column
//   - Toggle "Hiển thị giá trị thật" requires backend audit log entry +
//     MANAGER role; default is ON (masked).
//
// Quality score per dataset (0-100) shown as colored bar.
// ============================================================================

import React, { useState, useEffect } from 'react';
import {
  Layers, Search, Filter, RefreshCw, ShieldCheck, EyeOff, Eye,
  CheckCircle2, AlertCircle, Sparkles, X, ChevronRight, Lock,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner,
  api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type SilverStatus = 'cleaned' | 'processing' | 'failed';

interface SilverDataset {
  id:    string;
  name:  string;
  bronze_source_id: string;
  bronze_source_name: string;
  rows:  number;
  size_bytes: number;
  quality_pct: number;
  pii_columns: string[];   // e.g. ['email', 'phone'] — masked by default
  status: SilverStatus;
  error?: string;
  last_processed_at: string;
  cleaning_rules_applied: number;
}

const STATUS_BADGE: Record<SilverStatus, any> = {
  cleaned:    { variant: 'success', label: 'Đã làm sạch' },
  processing: { variant: 'warning', label: 'Đang xử lý' },
  failed:     { variant: 'error',   label: 'Lỗi' },
};

const PII_LABEL: Record<string, string> = {
  email: 'Email', phone: 'SĐT', name: 'Tên', address: 'Địa chỉ', id_number: 'CCCD/CMND',
};

export default function DataSilver() {
  const [datasets, setDatasets] = useState<SilverDataset[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [search,   setSearch]   = useState('');
  const [selected, setSelected] = useState<SilverDataset | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const res = await api<{ data: SilverDataset[] }>('/api/v1/data/silver/datasets?limit=200');
      setDatasets(res.data ?? []);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  const filtered = datasets.filter((d) =>
    !search.trim() || d.name.toLowerCase().includes(search.toLowerCase())
    || d.bronze_source_name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <>
      <PageHeader
        title="Silver — dữ liệu đã sạch"
        description="Đã loại null, chuẩn hoá kiểu, deduplicate. PII đã được che (K-5)."
        actions={
          <Button variant="secondary" onClick={load} disabled={loading}>
            <RefreshCw className={'w-4 h-4 mr-2 ' + (loading ? 'animate-spin' : '')} />
            Làm mới
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-4">
        {/* K-5 PII reminder */}
        <div className="rounded-md-custom bg-[var(--primary-gold)]/8 border border-[var(--primary-gold)]/30 p-4 flex items-start gap-3">
          <Lock className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <div className="flex-1">
            <p className="text-sm font-medium text-[var(--text-primary)]">PII được che mặc định (K-5)</p>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">
              Email/SĐT/Tên/Địa chỉ/CCCD hiện dạng <span className="font-mono">&lt;EMAIL_1&gt;</span>, <span className="font-mono">&lt;PHONE_1&gt;</span>, ...
              Hiển thị giá trị thật chỉ dành cho MANAGER và sẽ tạo audit log mỗi lần truy cập.
            </p>
          </div>
        </div>

        <ErrorBanner problem={problem} />

        <div className="relative flex-1">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm dataset Silver..."
            className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading ? (
            <>
              {[1,2,3,4].map((i) => <div key={i} className="h-44 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />)}
            </>
          ) : filtered.length === 0 ? (
            <div className="md:col-span-2 p-12 text-center text-[var(--text-secondary)] bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)]">
              Chưa có dataset Silver nào.
            </div>
          ) : (
            filtered.map((d) => <SilverCard key={d.id} dataset={d} onOpen={() => setSelected(d)} />)
          )}
        </div>
      </div>

      {selected && <SilverDrawer dataset={selected} onClose={() => setSelected(null)} />}
    </>
  );
}

function SilverCard({ dataset: d, onOpen }: any) {
  const meta = STATUS_BADGE[d.status];
  const qBar =
    d.quality_pct >= 90 ? 'bg-[var(--state-success)]'
    : d.quality_pct >= 75 ? 'bg-[var(--state-warning)]'
    : 'bg-[var(--state-error)]';
  return (
    <button
      type="button"
      onClick={onOpen}
      className="text-left rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] p-5 shadow-soft-sm hover:shadow-soft-md hover:-translate-y-0.5 transition-all"
    >
      <div className="flex items-start justify-between mb-3 gap-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-serif text-base text-[var(--text-primary)] truncate">{d.name}</h3>
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
            Nguồn: <span className="font-mono">{d.bronze_source_name}</span>
          </p>
        </div>
        <Badge variant={meta.variant}>{meta.label}</Badge>
      </div>

      <div className="grid grid-cols-3 gap-3 mb-3">
        <Stat label="Hàng" value={d.rows.toLocaleString('vi-VN')} />
        <Stat label="Dung lượng" value={humanBytes(d.size_bytes)} />
        <Stat label="Quy tắc" value={`${d.cleaning_rules_applied} áp dụng`} />
      </div>

      <div className="space-y-1.5 mb-3">
        <div className="flex items-baseline justify-between">
          <span className="text-[11px] text-[var(--text-secondary)]">Chất lượng dữ liệu</span>
          <span className="text-xs font-medium text-[var(--text-primary)]">{d.quality_pct.toFixed(1)}%</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-[var(--border-color)]/40 overflow-hidden">
          <div className={cn('h-full transition-all', qBar)} style={{ width: `${d.quality_pct}%` }} />
        </div>
      </div>

      {d.pii_columns.length > 0 && (
        <div className="flex items-center flex-wrap gap-1.5 pt-2 border-t border-[var(--border-color)]/60">
          <Lock className="w-3 h-3 text-[var(--primary-gold-dark)]" />
          <span className="text-[11px] text-[var(--text-secondary)]">PII đã che:</span>
          {d.pii_columns.map((c) => (
            <Badge key={c} variant="current" className="text-[10px]">
              {PII_LABEL[c] ?? c}
            </Badge>
          ))}
        </div>
      )}
    </button>
  );
}

function SilverDrawer({ dataset: d, onClose }: any) {
  const [unmask,   setUnmask]   = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function toggleUnmask() {
    if (!unmask) {
      setRequesting(true);
      setProblem(null);
      try {
        // K-5 audit: backend logs every unmask request keyed to user_id + dataset_id
        await api(`/api/v1/data/silver/datasets/${d.id}/unmask`, { method: 'POST' });
        setUnmask(true);
      } catch (err: any) {
        setProblem(err);
      } finally {
        setRequesting(false);
      }
    } else {
      setUnmask(false);
    }
  }

  // Preview rows — backend returns either masked or unmasked depending on flag
  const previewMasked = [
    { user_id: 'usr_8401', email: '<EMAIL_1>', phone: '<PHONE_1>', country: 'VN', signed_up_at: '2024-08-12' },
    { user_id: 'usr_8402', email: '<EMAIL_2>', phone: '<PHONE_2>', country: 'VN', signed_up_at: '2024-08-12' },
    { user_id: 'usr_8403', email: '<EMAIL_3>', phone: null,         country: 'JP', signed_up_at: '2024-08-13' },
  ];
  const previewUnmasked = [
    { user_id: 'usr_8401', email: 'an.nguyen@congty.vn', phone: '+84 90 234 1567', country: 'VN', signed_up_at: '2024-08-12' },
    { user_id: 'usr_8402', email: 'binh.tran@congty.vn', phone: '+84 90 882 4412', country: 'VN', signed_up_at: '2024-08-12' },
    { user_id: 'usr_8403', email: 'yamato.k@kabu.jp',     phone: null,             country: 'JP', signed_up_at: '2024-08-13' },
  ];
  const preview = unmask ? previewUnmasked : previewMasked;

  return (
    <div className="fixed inset-0 z-50 flex justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/30" />
      <aside
        className="relative w-full max-w-[760px] bg-[var(--bg-card)] border-l border-[var(--border-color)] overflow-y-auto animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-[var(--bg-card)] border-b border-[var(--border-color)] p-5 flex items-start justify-between gap-4">
          <div>
            <h2 className="font-serif text-lg text-[var(--text-primary)]">{d.name}</h2>
            <p className="text-xs text-[var(--text-secondary)] mt-0.5">Silver dataset · {d.rows.toLocaleString('vi-VN')} hàng</p>
          </div>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          <ErrorBanner problem={problem} />

          {/* PII unmask toggle */}
          <div className={cn(
            'rounded-md-custom border p-4',
            unmask
              ? 'bg-[var(--state-warning)]/10 border-[var(--state-warning)]/30'
              : 'bg-[var(--bg-app)]/60 border-[var(--border-color)]',
          )}>
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
                  {unmask ? <Eye className="w-4 h-4 text-[var(--state-warning)]" /> : <EyeOff className="w-4 h-4" />}
                  {unmask ? 'Đang xem giá trị thật' : 'PII đã được che'}
                </p>
                <p className="text-xs text-[var(--text-secondary)] mt-1">
                  {unmask
                    ? 'Lưu ý: hành động này đã được ghi vào audit log với ID người dùng và thời gian.'
                    : 'Bật xem giá trị thật cần quyền MANAGER. Mỗi lần bật ghi vào audit log (K-5).'}
                </p>
              </div>
              <Button
                size="sm"
                variant={unmask ? 'destructive' : 'secondary'}
                onClick={toggleUnmask}
                isLoading={requesting}
              >
                {unmask ? 'Che lại' : 'Hiện giá trị thật'}
              </Button>
            </div>
          </div>

          {/* Preview table */}
          <div>
            <h3 className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] mb-3">
              Xem trước (5 hàng đầu)
            </h3>
            <div className="overflow-x-auto rounded-md-custom border border-[var(--border-color)]">
              <table className="w-full text-xs">
                <thead className="bg-[var(--bg-app)]/60">
                  <tr>
                    {Object.keys(preview[0]).map((c) => (
                      <th key={c} className="px-3 py-2 text-left font-semibold text-[var(--text-secondary)]">
                        <div className="flex items-center gap-1">
                          {c}
                          {(c === 'email' || c === 'phone' || c === 'name' || c === 'address') && (
                            <Lock className="w-3 h-3 text-[var(--primary-gold-dark)]" />
                          )}
                        </div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.map((row: any, i: number) => (
                    <tr key={i} className="border-t border-[var(--border-color)]/60">
                      {Object.values(row).map((v: any, j: number) => (
                        <td key={j} className="px-3 py-2 font-mono">
                          {v == null ? <span className="text-[var(--text-secondary)] italic">null</span> : String(v)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <h3 className="text-[11px] uppercase tracking-wider font-semibold text-[var(--text-secondary)] mb-2">
              Cleaning rules đã áp dụng
            </h3>
            <p className="text-sm text-[var(--text-secondary)]">
              {d.cleaning_rules_applied} quy tắc — xem chi tiết tại{' '}
              <a href="/p2/pipelines" className="text-[var(--primary-gold-dark)] underline">trang Pipeline</a>.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}

function Stat({ label, value }: any) {
  return (
    <div>
      <p className="text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">{label}</p>
      <p className="text-sm font-medium text-[var(--text-primary)] mt-0.5">{value}</p>
    </div>
  );
}

function humanBytes(b: number): string {
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
}
