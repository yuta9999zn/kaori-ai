'use client';

// ============================================================================
// 51b. /p2/reports/distribution — Manual report distribution (F-038 BE PR #118)
// ----------------------------------------------------------------------------
// BE-EU-222 v0 ships a *one-shot manual* distribute path:
//
//   POST /api/v1/reports/{id}/distribute  body { recipients[], custom_message? }
//   GET  /api/v1/reports/{id}/distributions
//
// No cron · no role groups · no format selection (always email · always the
// auto-generated content). The legacy mock template (51-report-distribution.tsx)
// imagined the full scheduler/role-groups/format scope — those land in v1.
//
// This wired page therefore covers two states:
//   * No ?report=<id> querystring → "Chọn báo cáo để gửi" picker (list ready
//     reports, click → open distribute form)
//   * ?report=<id> present → distribute form: recipient list (textarea +
//     dedup preview) + optional custom_message + Gửi ngay button + history
//     table joined to notification_outbox state
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft, Send, Mail, MailX, Loader2, AlertTriangle, ShieldCheck,
  CheckCircle2, Hourglass, FileText, Search, ChevronRight,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, SuccessBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type ReportStatus = 'queued' | 'running' | 'ready' | 'failed';

interface BackendReportItem {
  report_id:    string;
  template_id:  string;
  title:        string;
  owner_email:  string;
  status:       ReportStatus;
  narrative?:   string | null;
  created_at:   string;
  completed_at?: string | null;
}

interface ReportListResponse {
  items: BackendReportItem[];
  next_cursor?: string | null;
}

interface DistributeResponseItem {
  recipient:       string;
  distribution_id: string | null;
  outbox_id:       string | null;
  status:          'pending' | 'sent' | 'failed';
}

interface DistributeResponse {
  report_id:       string;
  recipient_count: number;
  success_count:   number;
  failure_count:   number;
  distributions:   DistributeResponseItem[];
}

interface DistributionRow {
  distribution_id:    string;
  report_id:          string;
  recipient_email:    string;
  channel:            string;
  outbox_id:          string | null;
  dispatch_status:    string;        // pending / sent / failed (frozen at distribute-time)
  custom_message:     string | null;
  triggered_by_user:  string | null;
  dispatch_error:     string | null;
  created_at:         string;
  outbox_status:      string | null; // pending / sent / dead (live from outbox)
  outbox_attempts:    number | null;
  outbox_error:       string | null;
  outbox_sent_at:     string | null;
}

interface DistributionListResponse { items: DistributionRow[] }

// ============================================================================
// Page
// ============================================================================

export default function ReportDistributionWiredPage() {
  const [reportId, setReportId] = useState<string | null>(null);

  // Sync ?report=<id> from URL (initial + on history changes).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const sync = () => {
      const params = new URLSearchParams(window.location.search);
      setReportId(params.get('report'));
    };
    sync();
    window.addEventListener('popstate', sync);
    return () => window.removeEventListener('popstate', sync);
  }, []);

  return (
    <>
      <PageHeader
        title="Phát hành báo cáo"
        description={
          reportId
            ? 'Gửi 1 báo cáo đã ready cho danh sách người nhận tuỳ chọn.'
            : 'Chọn 1 báo cáo từ danh sách bên dưới để bắt đầu.'
        }
        actions={
          <a href="/p2/reports">
            <Button variant="tertiary"><ArrowLeft className="w-4 h-4 mr-1.5" /> Về danh sách</Button>
          </a>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {reportId ? (
          <DistributePanel
            reportId={reportId}
            onBack={() => {
              const url = new URL(window.location.href);
              url.searchParams.delete('report');
              window.history.pushState({}, '', url);
              setReportId(null);
            }}
          />
        ) : (
          <ReportPicker onPick={(id) => {
            const url = new URL(window.location.href);
            url.searchParams.set('report', id);
            window.history.pushState({}, '', url);
            setReportId(id);
          }} />
        )}

        <ImplicitNote />
      </div>
    </>
  );
}

// ============================================================================
// Picker — list of recent reports filtered to status='ready'
// ============================================================================

function ReportPicker({ onPick }: { onPick: (id: string) => void }) {
  const [reports, setReports] = useState<BackendReportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api<ReportListResponse>('/api/v1/reports?limit=100');
        if (!cancelled) setReports(r.items ?? []);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return reports.filter((r) => {
      if (r.status !== 'ready') return false;
      if (!q) return true;
      return r.title.toLowerCase().includes(q) || r.owner_email.toLowerCase().includes(q);
    });
  }, [reports, search]);

  return (
    <>
      {problem && (
        <ErrorBanner
          problem={{
            ...problem,
            title:  'Không tải được danh sách báo cáo',
            detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
          }}
        />
      )}

      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 shadow-soft-sm">
        <div className="relative">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo tiêu đề hoặc người tạo..."
            className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
          />
        </div>
      </div>

      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        {loading ? (
          <div className="px-5 py-12 text-center text-[var(--text-secondary)]">
            <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
          </div>
        ) : filtered.length === 0 ? (
          <div className="px-5 py-12 text-center">
            <FileText className="w-10 h-10 mx-auto text-[var(--text-secondary)]/30 mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">
              Không có báo cáo nào ở trạng thái "ready" để phát hành. Hãy tạo báo cáo trước qua{' '}
              <a href="/p2/reports/auto" className="text-[var(--primary-gold-dark)] underline">/p2/reports/auto</a>.
            </p>
          </div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">Tiêu đề</th>
                <th className="px-5 py-3">Tác giả</th>
                <th className="px-5 py-3">Hoàn thành</th>
                <th className="px-5 py-3 text-right"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {filtered.map((r) => (
                <tr
                  key={r.report_id}
                  className="hover:bg-[var(--bg-app)]/40 transition-colors cursor-pointer"
                  onClick={() => onPick(r.report_id)}
                >
                  <td className="px-5 py-4 max-w-md">
                    <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-1">{r.title}</p>
                    {r.narrative && (
                      <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">{r.narrative}</p>
                    )}
                  </td>
                  <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">{r.owner_email}</td>
                  <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
                    {r.completed_at ? formatRelative(r.completed_at) : '—'}
                  </td>
                  <td className="px-5 py-4 text-right">
                    <span className="inline-flex items-center text-xs font-medium text-[var(--primary-gold-dark)]">
                      Phát hành <ChevronRight className="w-3 h-3 ml-0.5" />
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

// ============================================================================
// Distribute panel — load report + form + history
// ============================================================================

function DistributePanel({
  reportId, onBack,
}: { reportId: string; onBack: () => void }) {
  const [report, setReport] = useState<BackendReportItem | null>(null);
  const [reportProblem, setReportProblem] = useState<ProblemDetails | null>(null);

  const [history, setHistory] = useState<DistributionRow[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);

  const [recipientsRaw, setRecipientsRaw] = useState('');
  const [customMessage, setCustomMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Initial load: report + history in parallel.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api<BackendReportItem>(`/api/v1/reports/${reportId}`);
        if (!cancelled) setReport(r);
      } catch (e: any) {
        if (!cancelled) setReportProblem(e);
      }
    })();
    refreshHistory();

    async function refreshHistory() {
      setHistoryLoading(true);
      try {
        const r = await api<DistributionListResponse>(`/api/v1/reports/${reportId}/distributions`);
        if (!cancelled) setHistory(r.items ?? []);
      } catch {
        if (!cancelled) setHistory([]);
      } finally {
        if (!cancelled) setHistoryLoading(false);
      }
    }
    return () => { cancelled = true; };
  }, [reportId]);

  const recipients = useMemo(() => dedupEmails(recipientsRaw), [recipientsRaw]);

  // BE caps recipient list at 50; mirror on FE so the disabled button + helper
  // text matches what the API will accept.
  const overCap = recipients.length > 50;
  const formValid = recipients.length >= 1 && !overCap;

  async function refreshHistory() {
    setHistoryLoading(true);
    try {
      const r = await api<DistributionListResponse>(`/api/v1/reports/${reportId}/distributions`);
      setHistory(r.items ?? []);
    } catch {
      // Best-effort — history failing shouldn't break the form.
    } finally {
      setHistoryLoading(false);
    }
  }

  async function dispatchNow() {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      const r = await api<DistributeResponse>(`/api/v1/reports/${reportId}/distribute`, {
        method: 'POST',
        body:   JSON.stringify({
          recipients,
          custom_message: customMessage.trim() || undefined,
        }),
      });
      const ok = r.success_count;
      const fail = r.failure_count;
      setSuccess(
        fail === 0
          ? `Đã enqueue ${ok} email — notification-service sẽ gửi trong vài phút.`
          : `Enqueue ${ok}/${r.recipient_count} thành công, ${fail} thất bại — kiểm tra Lịch sử bên dưới.`,
      );
      setRecipientsRaw('');
      setCustomMessage('');
      await refreshHistory();
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {/* Back to picker breadcrumb */}
      <button
        onClick={onBack}
        className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] inline-flex items-center"
      >
        <ArrowLeft className="w-3 h-3 mr-1" /> Đổi báo cáo
      </button>

      {/* Report context card */}
      {reportProblem ? (
        <ErrorBanner
          problem={{
            ...reportProblem,
            title:  'Không tải được báo cáo',
            detail: reportProblem.detail ?? reportProblem.title,
          }}
        />
      ) : !report ? (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
          <Loader2 className="w-5 h-5 animate-spin inline mr-2 text-[var(--primary-gold-dark)]" />
          <span className="text-sm text-[var(--text-secondary)]">Đang tải thông tin báo cáo...</span>
        </div>
      ) : report.status !== 'ready' ? (
        <div className="bg-[var(--state-warning)]/8 border border-[var(--state-warning)]/30 rounded-lg-custom p-5 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-[var(--text-primary)]">Báo cáo chưa sẵn sàng</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">
                Trạng thái hiện tại: <span className="font-mono">{report.status}</span>. BE từ chối phát hành (409) cho tới khi
                báo cáo ở trạng thái <span className="font-mono">ready</span>. Đợi auto-worker hoàn thành hoặc chọn báo cáo khác.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
          <div className="flex items-start gap-3 mb-3">
            <FileText className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-medium text-[var(--text-primary)]">{report.title}</p>
              <p className="text-xs text-[var(--text-secondary)] mt-0.5">
                Tác giả {report.owner_email} · hoàn thành {report.completed_at ? formatRelative(report.completed_at) : '—'}
              </p>
            </div>
            <Badge variant="success">ready</Badge>
          </div>
          {report.narrative && (
            <p className="text-xs text-[var(--text-secondary)] leading-relaxed border-t border-[var(--border-color)]/60 pt-3 mt-3">
              {report.narrative}
            </p>
          )}
        </div>
      )}

      {/* Distribute form */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm space-y-4">
        {problem && (
          <ErrorBanner
            problem={{
              ...problem,
              title:  problem.title ?? 'Phát hành thất bại',
              detail: problem.detail ?? '',
            }}
          />
        )}
        {success && <SuccessBanner message={success} />}

        <div className="space-y-2">
          <label className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] block">
            Email người nhận
          </label>
          <textarea
            value={recipientsRaw}
            onChange={(e) => setRecipientsRaw(e.target.value)}
            rows={3}
            placeholder="lan@acme.vn, huy@acme.vn — phân cách bằng dấu phẩy hoặc xuống dòng"
            className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] resize-none transition-all"
          />
          <p className="text-xs text-[var(--text-secondary)]">
            {recipients.length === 0 ? (
              <>Tối thiểu 1 email · tối đa 50.</>
            ) : (
              <>
                <span className="text-[var(--text-primary)] font-medium">{recipients.length}</span> email duy nhất sau khi gộp trùng
                {overCap && <span className="text-[var(--state-error)] ml-1">— vượt giới hạn 50</span>}.
              </>
            )}
          </p>
        </div>

        <div className="space-y-2">
          <label className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] block">
            Lời nhắn cá nhân (tuỳ chọn, ≤ 500 ký tự)
          </label>
          <textarea
            value={customMessage}
            onChange={(e) => setCustomMessage(e.target.value.slice(0, 500))}
            rows={3}
            placeholder="vd. Anh chị xem báo cáo trước cuộc họp 15h nhé."
            className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] resize-none transition-all"
          />
          <p className="text-xs text-[var(--text-secondary)]">
            Hiển thị trên đầu email, trên phần tóm tắt do AI viết. {customMessage.length}/500 ký tự.
          </p>
        </div>

        <div className="flex items-center justify-end gap-2">
          <Button
            variant="primary"
            onClick={dispatchNow}
            disabled={!formValid || submitting || !report || report.status !== 'ready'}
          >
            {submitting
              ? <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Đang gửi...</>
              : <><Send className="w-4 h-4 mr-1.5" /> Gửi ngay</>}
          </Button>
        </div>
      </div>

      {/* History */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        <div className="px-5 py-3 border-b border-[var(--border-color)] flex items-center justify-between">
          <h3 className="font-serif text-base text-[var(--text-primary)]">Lịch sử phát hành</h3>
          <Badge variant="default">{history.length}</Badge>
        </div>
        {historyLoading ? (
          <div className="px-5 py-8 text-center text-[var(--text-secondary)]">
            <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
          </div>
        ) : history.length === 0 ? (
          <div className="px-5 py-10 text-center">
            <Send className="w-10 h-10 mx-auto text-[var(--text-secondary)]/30 mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">Báo cáo này chưa được phát hành thủ công lần nào.</p>
          </div>
        ) : (
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">Người nhận</th>
                <th className="px-5 py-3">Lời nhắn</th>
                <th className="px-5 py-3">SMTP</th>
                <th className="px-5 py-3">Thời điểm</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {history.map((d) => <DistributionRowItem key={d.distribution_id} row={d} />)}
            </tbody>
          </table>
        )}
      </div>
    </>
  );
}

function DistributionRowItem({ row: d }: { row: DistributionRow }) {
  // Live SMTP state from notification_outbox; fall back to the dispatch
  // status frozen at distribute-time when the join missed (rare).
  const live = d.outbox_status ?? d.dispatch_status;
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4">
        <p className="text-sm text-[var(--text-primary)] font-mono">{d.recipient_email}</p>
        {d.outbox_id && (
          <p className="text-[10px] text-[var(--text-secondary)] mt-0.5 font-mono">outbox: {d.outbox_id.slice(0, 8)}…</p>
        )}
      </td>
      <td className="px-5 py-4 max-w-xs">
        <p className="text-xs text-[var(--text-secondary)] line-clamp-2">
          {d.custom_message ?? <span className="italic">(không có)</span>}
        </p>
      </td>
      <td className="px-5 py-4">
        <SmtpBadge status={live} attempts={d.outbox_attempts ?? 0} error={d.outbox_error ?? d.dispatch_error} />
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {formatRelative(d.outbox_sent_at ?? d.created_at)}
      </td>
    </tr>
  );
}

function SmtpBadge({
  status, attempts, error,
}: { status: string; attempts: number; error: string | null }) {
  if (status === 'sent') {
    return <Badge variant="success"><Mail className="w-3 h-3 mr-1" /> Đã gửi</Badge>;
  }
  if (status === 'dead' || status === 'failed') {
    return (
      <div className="inline-flex flex-col gap-0.5">
        <Badge variant="error"><MailX className="w-3 h-3 mr-1" /> Thất bại</Badge>
        {error && <span className="text-[10px] text-[var(--text-secondary)] line-clamp-1 max-w-[200px]">{error}</span>}
      </div>
    );
  }
  // pending / unknown
  return (
    <div className="inline-flex flex-col gap-0.5">
      <Badge variant="warning"><Hourglass className="w-3 h-3 mr-1" /> Đang chờ</Badge>
      {attempts > 0 && <span className="text-[10px] text-[var(--text-secondary)]">{attempts} lần thử</span>}
    </div>
  );
}

// ============================================================================
// Footer note
// ============================================================================

function ImplicitNote() {
  return (
    <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
      <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
      <p>
        Phiên bản này hỗ trợ <span className="font-mono">channel=email</span> và phát hành thủ công.
        Lịch tự động (cron), gửi theo nhóm vai trò (MANAGER / OPERATOR / ANALYST), và Slack / webhook đều thuộc v1.
        Mỗi email được durable enqueue qua <span className="font-mono">notification_outbox</span> — poller retry tới 5 lần
        rồi vào trạng thái <span className="font-mono">dead</span>.
      </p>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

/** Trim, dedup case-insensitively, drop blanks. Preserves first-seen casing. */
function dedupEmails(raw: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of raw.split(/[,\n]/)) {
    const cleaned = part.trim();
    if (!cleaned) continue;
    const key = cleaned.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(cleaned);
  }
  return out;
}

function formatRelative(iso: string): string {
  const diff = Date.now() - +new Date(iso);
  if (diff < 60_000)         return 'vừa xong';
  if (diff < 3_600_000)      return `${Math.round(diff / 60_000)} phút trước`;
  if (diff < 86_400_000)     return `${Math.round(diff / 3_600_000)} giờ trước`;
  if (diff < 7 * 86_400_000) return `${Math.round(diff / 86_400_000)} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}
