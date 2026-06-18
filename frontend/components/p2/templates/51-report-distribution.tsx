// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 51. /p2/reports/distribution — Report Distribution & Schedule (F-038 🔵 Phase 2 — UI mock only)
// ----------------------------------------------------------------------------
// Người dùng cấu hình cách phát hành 1 báo cáo:
//   - Cron schedule (preset hàng ngày/tuần/tháng + custom expression).
//   - Người nhận: email cá nhân + nhóm theo vai trò (MANAGER/OPERATOR/ANALYST).
//   - Định dạng: PDF · HTML · CSV (CSV xuất kèm UTF-8 BOM cho Excel VN).
//   - Send-now button + 10 lần dispatch gần nhất.
//
// Wire (Phase 2): `GET /api/v1/reports/{id}/distribution`,
// `PUT /api/v1/reports/{id}/distribution`, `POST /api/v1/reports/{id}/dispatch`.
// Notification-service (8094) làm sender, gọi qua HTTP trực tiếp (Phase 2 sẽ
// thêm Kafka topic `kaori.alerts.fire` cho fan-out).
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Calendar, Clock, Mail, Send, FileBadge, FileText, FileSpreadsheet,
  Save, ArrowLeft, ShieldCheck, CheckCircle2, AlertTriangle,
  Loader2, Users, Sparkles,
} from 'lucide-react';

import {
  Button, Badge, Input, Checkbox, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type Cadence = 'off' | 'daily' | 'weekly_mon' | 'weekly_fri' | 'monthly_1st' | 'custom';

interface CadencePreset {
  code:   Cadence;
  label:  string;
  cron:   string | null;
  helper: string;
}

const CADENCE_PRESETS: CadencePreset[] = [
  { code: 'off',          label: 'Tắt lịch tự động', cron: null,         helper: 'Chỉ phát hành thủ công.' },
  { code: 'daily',        label: 'Hàng ngày 07:00',  cron: '0 7 * * *',  helper: 'Mỗi sáng 07:00 ICT.' },
  { code: 'weekly_mon',   label: 'Thứ Hai 07:00',     cron: '0 7 * * 1',  helper: 'Mỗi đầu tuần.' },
  { code: 'weekly_fri',   label: 'Thứ Sáu 17:00',     cron: '0 17 * * 5', helper: 'Cuối tuần làm việc.' },
  { code: 'monthly_1st',  label: 'Ngày 1 hàng tháng', cron: '0 7 1 * *',  helper: 'Đầu mỗi tháng 07:00 ICT.' },
  { code: 'custom',       label: 'Cron tuỳ chỉnh',    cron: '',           helper: 'Nhập biểu thức cron 5-trường.' },
];

type Format = 'pdf' | 'html' | 'csv';

interface FormatMeta {
  code:        Format;
  label:       string;
  icon:        any;
  description: string;
}

const FORMATS: FormatMeta[] = [
  { code: 'pdf',  label: 'PDF',  icon: FileBadge,        description: 'Layout cố định · in ấn.' },
  { code: 'html', label: 'HTML', icon: FileText,         description: 'Email body inline · biểu đồ tương tác.' },
  { code: 'csv',  label: 'CSV',  icon: FileSpreadsheet,  description: 'Số liệu thô · UTF-8 BOM cho Excel VN.' },
];

interface DispatchLog {
  id:          string;
  dispatched_at: string;
  status:      'success' | 'partial' | 'failed';
  recipient_count: number;
  delivered_count: number;
  failure_reason?: string | null;
  format:      Format;
  trigger:     'scheduled' | 'manual';
}

const MOCK_DISPATCHES: DispatchLog[] = [
  { id: 'dsp_1041', dispatched_at: '2026-04-29T07:00:00+07:00', status: 'success', recipient_count: 6, delivered_count: 6, format: 'pdf',  trigger: 'scheduled' },
  { id: 'dsp_1040', dispatched_at: '2026-04-22T07:00:00+07:00', status: 'success', recipient_count: 6, delivered_count: 6, format: 'pdf',  trigger: 'scheduled' },
  { id: 'dsp_1039', dispatched_at: '2026-04-21T14:33:00+07:00', status: 'partial', recipient_count: 6, delivered_count: 5, format: 'html', trigger: 'manual', failure_reason: 'SMTP timeout với 1 hộp thư' },
  { id: 'dsp_1038', dispatched_at: '2026-04-15T07:00:00+07:00', status: 'failed',  recipient_count: 6, delivered_count: 0, format: 'pdf',  trigger: 'scheduled', failure_reason: 'Render PDF lỗi — chart_id không tồn tại' },
  { id: 'dsp_1037', dispatched_at: '2026-04-08T07:00:00+07:00', status: 'success', recipient_count: 5, delivered_count: 5, format: 'csv',  trigger: 'scheduled' },
];

const ROLE_GROUPS = [
  { code: 'MANAGER',  label: 'Tất cả MANAGER',  count: 2 },
  { code: 'OPERATOR', label: 'Tất cả OPERATOR', count: 4 },
  { code: 'ANALYST',  label: 'Tất cả ANALYST',  count: 3 },
] as const;

// ============================================================================
// Page
// ============================================================================

export default function ReportDistributionPage() {
  // Could read ?report_id from URL — kept synthetic for template.
  const reportName = 'Báo cáo doanh thu Q1 2026';

  const [cadence, setCadence] = useState<Cadence>('weekly_mon');
  const [customCron, setCustomCron] = useState('0 7 * * 1');
  const [format, setFormat] = useState<Format>('pdf');

  const [recipientEmails, setRecipientEmails] = useState('manager@acme.vn');
  const [roleGroups, setRoleGroups] = useState<Record<string, boolean>>({ MANAGER: true });
  const [includeAttachment, setIncludeAttachment] = useState(true);

  const [submitting, setSubmitting] = useState(false);
  const [dispatching, setDispatching] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [logs, setLogs] = useState<DispatchLog[]>([]);
  const [logLoading, setLogLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await api<{ items: DispatchLog[] }>('/api/v1/reports/demo/dispatches?limit=10');
        if (!cancelled) setLogs(data.items ?? []);
      } catch {
        if (!cancelled) setLogs(MOCK_DISPATCHES);
      } finally {
        if (!cancelled) setLogLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const emailList = useMemo(
    () => recipientEmails.split(/[,\n]/).map((s) => s.trim()).filter(Boolean),
    [recipientEmails],
  );

  const cron = useMemo(() => {
    if (cadence === 'off') return null;
    if (cadence === 'custom') return customCron.trim() || null;
    return CADENCE_PRESETS.find((c) => c.code === cadence)?.cron ?? null;
  }, [cadence, customCron]);

  const totalReach = emailList.length + Object.entries(roleGroups)
    .filter(([, on]) => on)
    .reduce((sum, [code]) => sum + (ROLE_GROUPS.find((g) => g.code === code)?.count ?? 0), 0);

  const formValid = totalReach > 0 && (cadence === 'off' || cron !== null);

  async function onSave() {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      await api('/api/v1/reports/demo/distribution', {
        method: 'PUT',
        body: JSON.stringify({
          schedule_cron:        cron,
          format,
          recipient_emails:     emailList,
          recipient_role_groups: Object.entries(roleGroups).filter(([, on]) => on).map(([code]) => code),
          include_attachment:   includeAttachment,
        }),
      });
      setSuccess('Đã lưu cấu hình phát hành.');
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  async function onDispatchNow() {
    setDispatching(true);
    setProblem(null);
    setSuccess(null);
    try {
      await api('/api/v1/reports/demo/dispatch', {
        method: 'POST',
        body: JSON.stringify({ format, recipient_emails: emailList }),
      });
      setSuccess(`Đã đẩy báo cáo cho ${totalReach} người nhận. Theo dõi nhật ký bên dưới.`);
    } catch (e: any) {
      setProblem(e);
    } finally {
      setDispatching(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Phát hành báo cáo"
        description={`Báo cáo: "${reportName}" · Cấu hình lịch + người nhận + định dạng.`}
        actions={
          <>
            <Badge variant="info">Phase 2 · F-038</Badge>
            <a href="/p2/reports">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Về danh sách</Button>
            </a>
            <Button variant="secondary" size="md" onClick={onSave} disabled={!formValid || submitting} isLoading={submitting}>
              <Save className="w-4 h-4 mr-2" /> Lưu
            </Button>
            <Button variant="primary" size="md" onClick={onDispatchNow} disabled={!formValid || dispatching} isLoading={dispatching}>
              <Send className="w-4 h-4 mr-2" /> Gửi ngay
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1200px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {/* Schedule */}
        <Section title="Lịch chạy" icon={Calendar}>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {CADENCE_PRESETS.map((c) => (
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
                {c.cron && c.code !== 'custom' && (
                  <p className="text-[11px] text-[var(--text-secondary)]/80 font-mono mt-2">{c.cron}</p>
                )}
              </button>
            ))}
          </div>
          {cadence === 'custom' && (
            <div className="mt-4 max-w-md">
              <Input
                label="Cron expression (5-field)"
                value={customCron}
                onChange={(e) => setCustomCron(e.target.value)}
                placeholder="VD: 0 7 1,15 * *"
                helperText="phút giờ ngày tháng thứ — chạy lúc 02:00-08:00 ICT (idle window)."
              />
            </div>
          )}
        </Section>

        {/* Recipients */}
        <Section title="Người nhận" icon={Mail}>
          <div className="space-y-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">Email cá nhân</label>
              <textarea
                value={recipientEmails}
                onChange={(e) => setRecipientEmails(e.target.value)}
                rows={3}
                placeholder="manager@acme.vn, ops@acme.vn"
                className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
              />
              <p className="text-xs text-[var(--text-secondary)]">
                {emailList.length} email cá nhân — cách nhau dấu phẩy hoặc xuống dòng.
              </p>
            </div>

            <div>
              <p className="text-sm font-medium text-[var(--text-primary)] mb-2 flex items-center gap-2">
                <Users className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Hoặc theo vai trò
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                {ROLE_GROUPS.map((g) => (
                  <label
                    key={g.code}
                    className={cn(
                      'flex items-center justify-between p-3 rounded-md-custom border cursor-pointer transition-colors',
                      roleGroups[g.code]
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
                    )}
                  >
                    <Checkbox
                      checked={!!roleGroups[g.code]}
                      onChange={(e) => setRoleGroups((prev) => ({ ...prev, [g.code]: e.target.checked }))}
                      label={<span className="text-sm">{g.label}</span>}
                    />
                    <span className="text-xs text-[var(--text-secondary)]">{g.count} người</span>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/60 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
              <Sparkles className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0" />
              <span>
                Tổng dự kiến: <span className="text-[var(--text-primary)] font-medium">{totalReach}</span> người nhận
                {totalReach === 0 && ' — cần ít nhất 1 để lưu/gửi.'}
              </span>
            </div>
          </div>
        </Section>

        {/* Format */}
        <Section title="Định dạng" icon={FileBadge}>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {FORMATS.map((f) => {
              const Icon = f.icon;
              const active = format === f.code;
              return (
                <button
                  key={f.code}
                  onClick={() => setFormat(f.code)}
                  className={cn(
                    'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
                    active
                      ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
                      : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
                  )}
                >
                  <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center mb-3">
                    <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
                  </div>
                  <p className="font-medium text-sm text-[var(--text-primary)]">{f.label}</p>
                  <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{f.description}</p>
                </button>
              );
            })}
          </div>
          <div className="mt-3">
            <Checkbox
              checked={includeAttachment}
              onChange={(e) => setIncludeAttachment(e.target.checked)}
              label="Đính kèm file vào email (mặc định bật)"
            />
            <p className="text-xs text-[var(--text-secondary)] mt-1 ml-6">
              Bỏ chọn nếu chỉ muốn gửi link xem online (tránh attachment lớn vượt giới hạn SMTP).
            </p>
          </div>
        </Section>

        {/* Dispatch log */}
        <DispatchLogSection logs={logs} loading={logLoading} />

        {/* Footer note */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Dispatch ghi vào <span className="font-mono">decision_audit_log</span> (K-6) — tenant_id, recipient_emails (đã hash),
            format, dispatched_at. CSV xuất đính UTF-8 BOM để Excel VN không lỗi font (Sprint 7 PR A pattern).
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function Section({
  title, icon: Icon, children,
}: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm">
      <div className="flex items-center gap-2 mb-4 pb-3 border-b border-[var(--border-color)]/60">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h3 className="font-serif text-base text-[var(--text-primary)]">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function DispatchLogSection({ logs, loading }: { logs: DispatchLog[]; loading: boolean }) {
  return (
    <section className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Send className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <h3 className="font-serif text-base text-[var(--text-primary)]">Lần phát hành gần đây</h3>
          <Badge variant="default">{logs.length}</Badge>
        </div>
        <span className="text-xs text-[var(--text-secondary)]">10 lần gần nhất</span>
      </div>
      <div className="overflow-auto">
        {loading ? (
          <div className="px-5 py-12 text-center text-[var(--text-secondary)]">
            <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải nhật ký...
          </div>
        ) : logs.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <Send className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">Chưa có lần phát hành nào.</p>
          </div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">Thời điểm</th>
                <th className="px-5 py-3">Cách kích hoạt</th>
                <th className="px-5 py-3">Định dạng</th>
                <th className="px-5 py-3">Đã gửi / Tổng</th>
                <th className="px-5 py-3">Trạng thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {logs.map((d) => <DispatchRow key={d.id} log={d} />)}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function DispatchRow({ log: d }: { log: DispatchLog }) {
  const statusMeta = {
    success: { label: 'Thành công',    variant: 'success' as const, icon: CheckCircle2 },
    partial: { label: 'Một phần',      variant: 'warning' as const, icon: AlertTriangle },
    failed:  { label: 'Thất bại',      variant: 'error' as const,   icon: AlertTriangle },
  }[d.status];
  const StatusIcon = statusMeta.icon;
  const formatLabel = FORMATS.find((f) => f.code === d.format)?.label ?? d.format.toUpperCase();

  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-3">
        <p className="text-sm text-[var(--text-primary)]">
          {new Date(d.dispatched_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })}
        </p>
        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">{d.id}</p>
      </td>
      <td className="px-5 py-3">
        <Badge variant={d.trigger === 'manual' ? 'current' : 'default'}>
          {d.trigger === 'manual' ? 'Thủ công' : 'Tự động'}
        </Badge>
      </td>
      <td className="px-5 py-3 text-xs text-[var(--text-secondary)]">{formatLabel}</td>
      <td className="px-5 py-3 text-sm text-[var(--text-primary)]">
        {d.delivered_count} / {d.recipient_count}
      </td>
      <td className="px-5 py-3">
        <div className="flex items-start gap-2">
          <Badge variant={statusMeta.variant}>
            <StatusIcon className="w-3 h-3 mr-1" /> {statusMeta.label}
          </Badge>
          {d.failure_reason && (
            <span className="text-[11px] text-[var(--state-error)]/80 max-w-[260px] line-clamp-1">{d.failure_reason}</span>
          )}
        </div>
      </td>
    </tr>
  );
}
