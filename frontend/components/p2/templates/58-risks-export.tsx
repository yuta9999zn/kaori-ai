// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 58. /p2/risks/export — Risks Export (F-055 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Trang xuất risk register:
//   - Filter giống file 56 (status/severity/category) + period (last 7d/30d/quarter/all).
//   - Format toggle: CSV (UTF-8 BOM cho Excel VN) / PDF (server-side render).
//   - Chọn cột muốn export (default tất cả).
//   - Recipients: gửi qua email cho ban GĐ hoặc download trực tiếp.
//   - Last 5 export gần nhất + status.
//
// Wire (Phase 2): `POST /api/v1/risks/export` returns `{export_id}`,
// poll `GET /api/v1/risks/export/{id}` cho status, download URL.
// ============================================================================

import React, { useState } from 'react';
import {
  ArrowLeft, FileSpreadsheet, FileBadge, Download, Send, Calendar,
  Mail, ShieldCheck, CheckCircle2, AlertTriangle, Clock, Loader2,
} from 'lucide-react';

import {
  Button, Badge, Checkbox, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

type ExportFormat = 'csv' | 'pdf';
type ExportPeriod = 'all' | 'last7d' | 'last30d' | 'quarter';

const COLUMNS = [
  { key: 'id',                label: 'ID' },
  { key: 'title',             label: 'Tên rủi ro' },
  { key: 'category',          label: 'Danh mục' },
  { key: 'likelihood',        label: 'Khả năng' },
  { key: 'impact',            label: 'Tác động' },
  { key: 'severity',          label: 'Mức độ' },
  { key: 'status',            label: 'Trạng thái' },
  { key: 'owner',             label: 'Owner' },
  { key: 'mitigation_due',    label: 'Hạn mitigation' },
  { key: 'last_reviewed_at',  label: 'Lần review gần nhất' },
];

interface ExportRun {
  id:           string;
  format:       ExportFormat;
  status:       'pending' | 'success' | 'failed';
  generated_at: string;
  by:           string;
  rows:         number;
  delivery:     'download' | 'email';
  recipient_count?: number;
}

const RECENT_EXPORTS: ExportRun[] = [
  { id: 'exp_007', format: 'csv', status: 'success', generated_at: '2026-04-30T08:30:00+07:00', by: 'minh@acme.vn', rows: 12, delivery: 'email',    recipient_count: 4 },
  { id: 'exp_006', format: 'pdf', status: 'success', generated_at: '2026-04-25T15:14:00+07:00', by: 'lan@acme.vn',  rows: 12, delivery: 'download' },
  { id: 'exp_005', format: 'pdf', status: 'failed',  generated_at: '2026-04-22T11:08:00+07:00', by: 'huy@acme.vn',  rows:  0, delivery: 'email',    recipient_count: 4 },
  { id: 'exp_004', format: 'csv', status: 'success', generated_at: '2026-04-15T08:00:00+07:00', by: 'system',        rows: 11, delivery: 'email',    recipient_count: 4 },
  { id: 'exp_003', format: 'csv', status: 'success', generated_at: '2026-04-08T08:00:00+07:00', by: 'system',        rows: 10, delivery: 'email',    recipient_count: 4 },
];

// ============================================================================
// Page
// ============================================================================

export default function RisksExportPage() {
  const [format, setFormat] = useState<ExportFormat>('csv');
  const [period, setPeriod] = useState<ExportPeriod>('all');
  const [statusFilter, setStatusFilter] = useState<'all' | 'open' | 'mitigating' | 'closed'>('all');
  const [severityFilter, setSeverityFilter] = useState<'all' | 'low' | 'medium' | 'high' | 'critical'>('all');
  const [columns, setColumns] = useState<Record<string, boolean>>(
    Object.fromEntries(COLUMNS.map((c) => [c.key, true])),
  );
  const [delivery, setDelivery] = useState<'download' | 'email'>('download');
  const [recipientEmails, setRecipientEmails] = useState('');

  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selectedColumns = Object.entries(columns).filter(([, on]) => on).map(([k]) => k);
  const recipientList = recipientEmails.split(/[,\n]/).map((s) => s.trim()).filter(Boolean);
  const formValid = selectedColumns.length > 0 && (delivery === 'download' || recipientList.length > 0);

  async function onExport() {
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      await api('/api/v1/risks/export', {
        method: 'POST',
        body: JSON.stringify({
          format,
          period,
          status_filter:    statusFilter === 'all' ? null : statusFilter,
          severity_filter:  severityFilter === 'all' ? null : severityFilter,
          columns:          selectedColumns,
          delivery,
          recipient_emails: delivery === 'email' ? recipientList : [],
        }),
      });
      setSuccess(
        delivery === 'email'
          ? `Đã đẩy job export. Sẽ gửi qua ${recipientList.length} email khi xong (1-2 phút).`
          : 'Đã đẩy job export. File sẽ tải về khi sinh xong (1-2 phút).',
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
        title="Xuất risk register"
        description="Tạo CSV/PDF từ risk hiện tại để gửi ban GĐ hoặc lưu trữ."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-055</Badge>
            <a href="/p2/risks"><Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Về danh sách</Button></a>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {/* Format */}
        <Section title="Định dạng" icon={FileBadge}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <FormatCard
              format="csv"
              label="CSV"
              description="UTF-8 BOM cho Excel Việt Nam · giữ tiếng Việt + emoji."
              icon={FileSpreadsheet}
              selected={format === 'csv'}
              onSelect={() => setFormat('csv')}
            />
            <FormatCard
              format="pdf"
              label="PDF"
              description="Layout cố định · in/gửi cho ban GĐ · server-side render."
              icon={FileBadge}
              selected={format === 'pdf'}
              onSelect={() => setFormat('pdf')}
            />
          </div>
        </Section>

        {/* Filter */}
        <Section title="Phạm vi dữ liệu" icon={Calendar}>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <SelectField
              label="Khoảng thời gian (last reviewed)"
              value={period}
              onChange={setPeriod}
              options={[
                { value: 'all',     label: 'Tất cả' },
                { value: 'last7d',  label: '7 ngày gần nhất' },
                { value: 'last30d', label: '30 ngày gần nhất' },
                { value: 'quarter', label: 'Quý hiện tại (Q2/2026)' },
              ]}
            />
            <SelectField
              label="Trạng thái"
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: 'all',         label: 'Tất cả' },
                { value: 'open',        label: 'Mở' },
                { value: 'mitigating',  label: 'Đang xử lý' },
                { value: 'closed',      label: 'Đã đóng' },
              ]}
            />
            <SelectField
              label="Mức độ"
              value={severityFilter}
              onChange={setSeverityFilter}
              options={[
                { value: 'all',       label: 'Tất cả' },
                { value: 'critical',  label: 'Nghiêm trọng' },
                { value: 'high',      label: 'Cao' },
                { value: 'medium',    label: 'Trung' },
                { value: 'low',       label: 'Thấp' },
              ]}
            />
          </div>
        </Section>

        {/* Columns */}
        <Section title="Cột muốn xuất" icon={FileSpreadsheet}>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {COLUMNS.map((c) => (
              <Checkbox
                key={c.key}
                checked={!!columns[c.key]}
                onChange={(e) => setColumns((prev) => ({ ...prev, [c.key]: e.target.checked }))}
                label={<span className="text-sm">{c.label}</span>}
              />
            ))}
          </div>
          <p className="text-xs text-[var(--text-secondary)] mt-3">
            {selectedColumns.length}/{COLUMNS.length} cột được chọn.
          </p>
        </Section>

        {/* Delivery */}
        <Section title="Cách nhận" icon={Send}>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-4">
            <button
              onClick={() => setDelivery('download')}
              className={cn(
                'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
                delivery === 'download'
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
                  : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
              )}
            >
              <Download className="w-5 h-5 text-[var(--primary-gold-dark)] mb-2" />
              <p className="font-medium text-sm text-[var(--text-primary)]">Tải về máy</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">File trở về trình duyệt khi sinh xong.</p>
            </button>
            <button
              onClick={() => setDelivery('email')}
              className={cn(
                'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
                delivery === 'email'
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
                  : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
              )}
            >
              <Mail className="w-5 h-5 text-[var(--primary-gold-dark)] mb-2" />
              <p className="font-medium text-sm text-[var(--text-primary)]">Gửi email</p>
              <p className="text-xs text-[var(--text-secondary)] mt-1">notification-service đính kèm file vào email.</p>
            </button>
          </div>
          {delivery === 'email' && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">Người nhận</label>
              <textarea
                value={recipientEmails}
                onChange={(e) => setRecipientEmails(e.target.value)}
                rows={3}
                placeholder="manager@acme.vn, ceo@acme.vn"
                className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm text-[var(--text-primary)] focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all resize-none"
              />
              <p className="text-xs text-[var(--text-secondary)]">{recipientList.length} email cách nhau dấu phẩy hoặc xuống dòng.</p>
            </div>
          )}
        </Section>

        {/* Action */}
        <div className="sticky bottom-0 bg-[var(--bg-card)]/95 backdrop-blur-sm border-t border-[var(--border-color)] -mx-6 lg:-mx-8 px-6 lg:px-8 py-4 flex items-center justify-between">
          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)]" />
            Export ghi vào audit log (K-6) với actor + filter snapshot.
          </p>
          <Button variant="primary" size="md" onClick={onExport} disabled={!formValid || submitting} isLoading={submitting}>
            {delivery === 'email' ? <Send className="w-4 h-4 mr-2" /> : <Download className="w-4 h-4 mr-2" />}
            {delivery === 'email' ? 'Gửi email' : 'Tạo file'}
          </Button>
        </div>

        {/* Recent */}
        <Section title="5 lần xuất gần nhất" icon={Clock}>
          <div className="overflow-auto">
            <table className="w-full text-sm text-left">
              <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
                <tr>
                  <th className="px-3 py-2">Thời điểm</th>
                  <th className="px-3 py-2">Format</th>
                  <th className="px-3 py-2">Người tạo</th>
                  <th className="px-3 py-2">Số dòng</th>
                  <th className="px-3 py-2">Cách nhận</th>
                  <th className="px-3 py-2">Trạng thái</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {RECENT_EXPORTS.map((r) => (
                  <tr key={r.id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                    <td className="px-3 py-2 text-xs text-[var(--text-primary)]">
                      {new Date(r.generated_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
                    </td>
                    <td className="px-3 py-2 text-xs text-[var(--text-secondary)] uppercase font-medium">{r.format}</td>
                    <td className="px-3 py-2 text-xs text-[var(--text-primary)]">{r.by}</td>
                    <td className="px-3 py-2 text-xs text-[var(--text-primary)]">{r.rows}</td>
                    <td className="px-3 py-2 text-xs text-[var(--text-secondary)]">
                      {r.delivery === 'email' ? `Email × ${r.recipient_count}` : 'Download'}
                    </td>
                    <td className="px-3 py-2">
                      {r.status === 'success' ? (
                        <Badge variant="success"><CheckCircle2 className="w-3 h-3 mr-1" /> Thành công</Badge>
                      ) : r.status === 'failed' ? (
                        <Badge variant="error"><AlertTriangle className="w-3 h-3 mr-1" /> Thất bại</Badge>
                      ) : (
                        <Badge variant="info"><Loader2 className="w-3 h-3 mr-1 animate-spin" /> Đang chạy</Badge>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Section>
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

function FormatCard({
  format, label, description, icon: Icon, selected, onSelect,
}: { format: string; label: string; description: string; icon: any; selected: boolean; onSelect: () => void }) {
  return (
    <button
      onClick={onSelect}
      className={cn(
        'text-left p-4 rounded-md-custom border transition-all shadow-soft-sm',
        selected
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="w-9 h-9 rounded-md-custom bg-[var(--primary-gold)]/15 flex items-center justify-center mb-3">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
      </div>
      <p className="font-medium text-sm text-[var(--text-primary)]">{label}</p>
      <p className="text-xs text-[var(--text-secondary)] mt-1 leading-relaxed">{description}</p>
    </button>
  );
}

function SelectField({
  label, value, onChange, options,
}: { label: string; value: string; onChange: (v: any) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="space-y-2">
      <label className="text-sm font-medium text-[var(--text-primary)]">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </div>
  );
}
