// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 62. /p2/alerts — Alerts List (F-058 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Trung tâm cảnh báo:
//   - Bảng list alert với filter severity (info/warning/critical) + status
//     (open/acknowledged/resolved/snoozed) + source (system/data/ai/billing).
//   - Quick action: acknowledge / resolve / snooze (1h, 4h, 24h).
//   - Click row → file 63 detail page.
//
// Phase 2 (F-058) wire `GET /api/v1/alerts` + `POST /api/v1/alerts/{id}/ack`,
// `/resolve`, `/snooze`. Kafka topic `kaori.alerts.fire` đã đặt ở CLAUDE.md
// §7 — Phase 2 sẽ enable consumer notification-dispatcher.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Bell, Search, AlertTriangle, AlertCircle, CheckCircle2, Clock,
  Database, Cpu, CreditCard, Zap, Filter, ArrowRight,
  ChevronDown, Loader2, ShieldCheck, Sparkles,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type Severity = 'info' | 'warning' | 'critical';
type Status   = 'open' | 'acknowledged' | 'resolved' | 'snoozed';
type Source   = 'system' | 'data' | 'ai' | 'billing';

interface AlertRow {
  id:           string;
  title:        string;
  message:      string;
  severity:     Severity;
  status:       Status;
  source:       Source;
  fired_at:     string;
  ack_by?:      string | null;
  ack_at?:      string | null;
  related_id?:  string | null;  // pipeline_id, insight_id, etc.
}

const SEVERITY_META: Record<Severity, { label: string; variant: 'info' | 'warning' | 'error'; icon: any }> = {
  info:     { label: 'Info',      variant: 'info',    icon: AlertCircle },
  warning:  { label: 'Cảnh báo',  variant: 'warning', icon: AlertTriangle },
  critical: { label: 'Nghiêm trọng', variant: 'error', icon: AlertTriangle },
};

const STATUS_META: Record<Status, { label: string; variant: 'default' | 'success' | 'warning' | 'info' | 'current' }> = {
  open:         { label: 'Mới',         variant: 'current' },
  acknowledged: { label: 'Đã ghi nhận', variant: 'info' },
  resolved:     { label: 'Đã xử lý',     variant: 'success' },
  snoozed:      { label: 'Tạm hoãn',     variant: 'default' },
};

const SOURCE_META: Record<Source, { label: string; icon: any }> = {
  system:  { label: 'Hệ thống', icon: Cpu },
  data:    { label: 'Dữ liệu',  icon: Database },
  ai:      { label: 'AI',       icon: Zap },
  billing: { label: 'Hoá đơn',   icon: CreditCard },
};

const MOCK_ALERTS: AlertRow[] = [
  { id: 'al_201', title: 'Pipeline thất bại 3 lần liên tiếp',           message: 'Pipeline pl_42 lỗi ở step Cleaning — cột "ngay_thang" không parse được.', severity: 'critical', status: 'open',         source: 'data',    fired_at: '2026-04-30T14:32:00+07:00', related_id: 'pl_42' },
  { id: 'al_200', title: 'Workspace dùng 95% hạn mức tháng',            message: 'Đã dùng 9.612 / 10.000 khách hàng. Nâng cấp gói trước khi chạm trần.',     severity: 'critical', status: 'acknowledged', source: 'billing', fired_at: '2026-04-30T08:00:00+07:00', ack_by: 'minh@acme.vn', ack_at: '2026-04-30T08:14:00+07:00' },
  { id: 'al_199', title: 'Decision audit log chậm append',              message: 'Decision write latency p99 = 2.3s (ngưỡng 1s). Có thể do Postgres autovacuum.', severity: 'warning',  status: 'open',         source: 'system',  fired_at: '2026-04-30T03:18:00+07:00' },
  { id: 'al_198', title: 'Churn vùng APAC tăng 12%',                    message: 'Phát hiện trong insight "Q1 2026 churn analysis". Cân nhắc tạo OKR mitigation.', severity: 'warning',  status: 'open',         source: 'ai',      fired_at: '2026-04-29T22:05:00+07:00', related_id: 'ins_42' },
  { id: 'al_197', title: 'External AI quota tháng đạt 80%',             message: 'Đã chi 4.000.000₫ / 5.000.000₫ ngân sách AI ngoài. Workspace có thể bị throttle khi vượt 100%.', severity: 'warning', status: 'snoozed',     source: 'billing', fired_at: '2026-04-29T18:42:00+07:00' },
  { id: 'al_196', title: 'Dataset Gold trễ refresh',                    message: 'monthly_revenue_gold chưa refresh trong 36h (ngưỡng 24h).',                  severity: 'warning',  status: 'resolved',     source: 'data',    fired_at: '2026-04-29T11:11:00+07:00', ack_by: 'huy@acme.vn', ack_at: '2026-04-29T13:30:00+07:00' },
  { id: 'al_195', title: 'Có 3 user mới đăng ký vào workspace',         message: 'lan@acme.vn invited 3 user mới — hãy review vai trò RBAC.',                 severity: 'info',     status: 'resolved',     source: 'system',  fired_at: '2026-04-28T15:20:00+07:00', ack_by: 'minh@acme.vn', ack_at: '2026-04-28T15:35:00+07:00' },
  { id: 'al_194', title: 'Insight pack chưa sinh kịp cuộc họp',         message: 'OKR Weekly tuần 17 thiếu insight pack — fallback dùng dữ liệu tuần trước.',  severity: 'info',     status: 'resolved',     source: 'ai',      fired_at: '2026-04-25T08:55:00+07:00' },
];

// ============================================================================
// Page
// ============================================================================

export default function AlertsListPage() {
  const [alerts, setAlerts] = useState<AlertRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  const [severity, setSeverity] = useState<'all' | Severity>('all');
  const [status, setStatus]     = useState<'all' | Status>('all');
  const [source, setSource]     = useState<'all' | Source>('all');
  const [search, setSearch]     = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: AlertRow[] }>('/api/v1/alerts?limit=200');
        if (!cancelled) setAlerts(data.items ?? []);
      } catch (e: any) {
        if (!cancelled) {
          setProblem(e);
          setAlerts(MOCK_ALERTS);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return alerts.filter((a) => {
      if (severity !== 'all' && a.severity !== severity) return false;
      if (status !== 'all'   && a.status !== status)     return false;
      if (source !== 'all'   && a.source !== source)     return false;
      if (q && !a.title.toLowerCase().includes(q) && !a.message.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [alerts, severity, status, source, search]);

  const stats = useMemo(() => ({
    open:         alerts.filter((a) => a.status === 'open').length,
    critical:     alerts.filter((a) => a.severity === 'critical' && a.status !== 'resolved').length,
    warning:      alerts.filter((a) => a.severity === 'warning' && a.status !== 'resolved').length,
    last24h:      alerts.filter((a) => Date.now() - +new Date(a.fired_at) < 86_400_000).length,
  }), [alerts]);

  async function quickAck(id: string) {
    setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, status: 'acknowledged', ack_at: new Date().toISOString() } : a));
    try {
      await api(`/api/v1/alerts/${id}/ack`, { method: 'POST' });
    } catch { /* optimistic — Phase 2 sẽ rollback */ }
  }

  async function quickResolve(id: string) {
    setAlerts((prev) => prev.map((a) => a.id === id ? { ...a, status: 'resolved', ack_at: new Date().toISOString() } : a));
    try {
      await api(`/api/v1/alerts/${id}/resolve`, { method: 'POST' });
    } catch { /* optimistic */ }
  }

  return (
    <>
      <PageHeader
        title="Cảnh báo"
        description="Sự kiện hệ thống cần chú ý — pipeline · billing · AI · dữ liệu."
        actions={<Badge variant="info">Phase 2 · F-058</Badge>}
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  'Đang dùng dữ liệu mẫu',
              detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}. Hiển thị fixture cho tới khi /api/v1/alerts sẵn sàng.`,
            }}
          />
        )}

        {/* KPI tiles */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatTile label="Mới chưa xử lý"          value={stats.open}     icon={Bell}            tone="text-[var(--primary-gold-dark)]" />
          <StatTile label="Nghiêm trọng (chưa xong)" value={stats.critical} icon={AlertTriangle}   tone="text-[var(--state-error)]" />
          <StatTile label="Cảnh báo (chưa xong)"     value={stats.warning}  icon={AlertCircle}     tone="text-[var(--state-warning)]" />
          <StatTile label="Trong 24h"                value={stats.last24h}  icon={Clock}           tone="text-[var(--text-primary)]" />
        </div>

        {/* Toolbar */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col lg:flex-row items-stretch lg:items-center gap-3 shadow-soft-sm">
          <div className="relative flex-1 min-w-[200px]">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo nội dung..."
              className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
            />
          </div>
          <FilterPill label="Mức độ" value={severity} onChange={setSeverity} options={[
            { value: 'all', label: 'Tất cả' },
            { value: 'critical', label: 'Nghiêm trọng' },
            { value: 'warning',  label: 'Cảnh báo' },
            { value: 'info',     label: 'Info' },
          ]} />
          <FilterPill label="Trạng thái" value={status} onChange={setStatus} options={[
            { value: 'all',           label: 'Tất cả' },
            { value: 'open',          label: 'Mới' },
            { value: 'acknowledged',  label: 'Đã ghi nhận' },
            { value: 'resolved',      label: 'Đã xử lý' },
            { value: 'snoozed',       label: 'Tạm hoãn' },
          ]} />
          <FilterPill label="Nguồn" value={source} onChange={setSource} options={[
            { value: 'all',     label: 'Tất cả' },
            { value: 'system',  label: 'Hệ thống' },
            { value: 'data',    label: 'Dữ liệu' },
            { value: 'ai',      label: 'AI' },
            { value: 'billing', label: 'Hoá đơn' },
          ]} />
        </div>

        {/* Table */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-5 py-3">Mức</th>
                  <th className="px-5 py-3">Nội dung</th>
                  <th className="px-5 py-3">Nguồn</th>
                  <th className="px-5 py-3">Phát sinh</th>
                  <th className="px-5 py-3">Trạng thái</th>
                  <th className="px-5 py-3 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading ? (
                  <tr><td colSpan={6} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                    <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
                  </td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={6} className="px-5 py-16 text-center">
                    <CheckCircle2 className="w-10 h-10 mx-auto text-[var(--state-success)]/40 mb-3" />
                    <p className="text-sm text-[var(--text-secondary)]">Không có cảnh báo nào khớp bộ lọc.</p>
                  </td></tr>
                ) : (
                  filtered.map((a) => <AlertRowItem key={a.id} alert={a} onAck={() => quickAck(a.id)} onResolve={() => quickResolve(a.id)} />)
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Mỗi acknowledge / resolve ghi vào <span className="font-mono">decision_audit_log</span> (K-6) với actor + thời điểm.
            Cảnh báo critical còn open quá 24h sẽ tự escalate qua <span className="font-mono">notification-service</span> (Phase 2).
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function StatTile({
  label, value, icon: Icon, tone,
}: { label: string; value: number; icon: any; tone: string }) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">{label}</span>
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
      <p className="font-serif text-3xl text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function FilterPill({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: any) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="appearance-none h-9 pl-3 pr-9 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 cursor-pointer hover:bg-[var(--bg-card)]"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{label}: {o.label}</option>)}
      </select>
      <ChevronDown className="w-3.5 h-3.5 text-[var(--text-secondary)] absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  );
}

function AlertRowItem({
  alert: a, onAck, onResolve,
}: { alert: AlertRow; onAck: () => void; onResolve: () => void }) {
  const sev = SEVERITY_META[a.severity];
  const SevIcon = sev.icon;
  const stt = STATUS_META[a.status];
  const src = SOURCE_META[a.source];
  const SrcIcon = src.icon;

  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors group">
      <td className="px-5 py-4">
        <Badge variant={sev.variant}>
          <SevIcon className="w-3 h-3 mr-1" /> {sev.label}
        </Badge>
      </td>
      <td className="px-5 py-4 max-w-md">
        <a href={`/p2/alerts/${a.id}`} className="text-sm font-medium text-[var(--text-primary)] group-hover:text-[var(--primary-gold-dark)] transition-colors line-clamp-1">
          {a.title}
        </a>
        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">{a.message}</p>
        {a.related_id && (
          <p className="text-[10px] text-[var(--primary-gold-dark)] mt-0.5 font-mono">→ {a.related_id}</p>
        )}
      </td>
      <td className="px-5 py-4">
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
          <SrcIcon className="w-3.5 h-3.5" /> {src.label}
        </span>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {new Date(a.fired_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
      </td>
      <td className="px-5 py-4">
        <Badge variant={stt.variant}>{stt.label}</Badge>
        {a.ack_by && (
          <p className="text-[10px] text-[var(--text-secondary)] mt-1">{a.ack_by}</p>
        )}
      </td>
      <td className="px-5 py-4 text-right">
        <div className="inline-flex items-center gap-1">
          {a.status === 'open' && (
            <>
              <button onClick={onAck} className="px-2.5 py-1 text-[11px] font-medium text-[var(--text-primary)] border border-[var(--border-color)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors">
                Ghi nhận
              </button>
              <button onClick={onResolve} className="px-2.5 py-1 text-[11px] font-medium text-white bg-[var(--state-success)] hover:opacity-90 rounded-sm-custom transition-opacity">
                Xử lý
              </button>
            </>
          )}
          {a.status === 'acknowledged' && (
            <button onClick={onResolve} className="px-2.5 py-1 text-[11px] font-medium text-white bg-[var(--state-success)] hover:opacity-90 rounded-sm-custom transition-opacity">
              Xử lý
            </button>
          )}
          <a href={`/p2/alerts/${a.id}`} className="ml-1 px-2.5 py-1 text-[11px] font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)] rounded-sm-custom inline-flex items-center transition-colors">
            Chi tiết <ArrowRight className="w-3 h-3 ml-1" />
          </a>
        </div>
      </td>
    </tr>
  );
}
