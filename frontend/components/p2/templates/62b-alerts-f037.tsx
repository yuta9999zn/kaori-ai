'use client';

// ============================================================================
// 62b. /p2/alerts — Alert Rules + fire history (F-037 ✅ Phase 2 BE landed PR #116)
// ----------------------------------------------------------------------------
// Two tabs:
//   - "Lịch sử"  — alert_events history (what fired, what was suppressed by
//                  cooldown). The closest analogue to the F-058 fired-alerts
//                  inbox until that feature ships its own ack/resolve workflow.
//   - "Quy tắc" — alert_rules CRUD (per-tenant custom rules). MANAGER role
//                  required for create / edit / delete.
//
// Wires (auth-service, this PR's backend):
//   GET    /api/v1/enterprises/alerts            — list rules
//   POST   /api/v1/enterprises/alerts            — create rule (MANAGER)
//   PATCH  /api/v1/enterprises/alerts/{id}       — update rule (MANAGER)
//   DELETE /api/v1/enterprises/alerts/{id}       — soft delete (MANAGER)
//   GET    /api/v1/enterprises/alerts/events     — recent fire history
//
// The 80%/95% billing alerts always fire even with no custom rules — they use
// implicit sentinel rule_ids. The "Lịch sử" tab surfaces both implicit and
// custom-rule fires; the "Quy tắc" tab only lists actual alert_rules rows.
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Bell, Plus, Search, AlertTriangle, AlertCircle, CheckCircle2, Clock,
  CreditCard, Loader2, ShieldCheck, Trash2, Pencil, X, Save,
  ChevronDown, History, ListFilter, Mail, Hourglass, MailX,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, api, cn, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types
// ============================================================================

const SENTINEL_BILLING_80 = '00000000-0000-0000-0000-000000000080';
const SENTINEL_BILLING_95 = '00000000-0000-0000-0000-000000000095';

type Operator = 'gt' | 'gte' | 'lt' | 'lte' | 'eq';
type MetricType = 'billing_quota_pct';
type Channel = 'email';

interface AlertRule {
  rule_id:           string;
  name:              string;
  description:       string | null;
  metric_type:       MetricType;
  operator:          Operator;
  threshold_value:   number | string;
  channel:           Channel;
  target_email:      string | null;
  cooldown_seconds:  number;
  is_active:         boolean;
  created_at:        string;
  updated_at:        string;
}

interface AlertEvent {
  event_id:        string;
  rule_id:         string;
  metric_type:     string;
  metric_value:    number | string;
  threshold_value: number | string;
  operator:        Operator;
  context:         Record<string, unknown>;
  outbox_id:       string | null;
  suppressed:      boolean;
  fired_at:        string;
}

interface RuleListResponse  { data: AlertRule[];  meta: { total: number; page: number; limit: number } }
interface EventListResponse { data: AlertEvent[] }
interface RuleResponse      { data: AlertRule }

// ============================================================================
// Page
// ============================================================================

type TabKey = 'events' | 'rules';

export default function AlertsRulesPage() {
  const [tab, setTab] = useState<TabKey>('events');

  // Rules state
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [rulesLoading, setRulesLoading] = useState(true);
  const [rulesProblem, setRulesProblem] = useState<ProblemDetails | null>(null);

  // Events state
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(true);
  const [eventsProblem, setEventsProblem] = useState<ProblemDetails | null>(null);

  // Editor modal
  const [editor, setEditor] = useState<RuleEditorState>({ open: false, rule: null });

  // Initial fetch — both tabs in parallel so switching is instant.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const r = await api<RuleListResponse>('/api/v1/enterprises/alerts?limit=100');
        if (!cancelled) setRules(r.data ?? []);
      } catch (e: any) {
        if (!cancelled) setRulesProblem(e);
      } finally {
        if (!cancelled) setRulesLoading(false);
      }
    })();
    (async () => {
      try {
        const r = await api<EventListResponse>('/api/v1/enterprises/alerts/events?limit=200');
        if (!cancelled) setEvents(r.data ?? []);
      } catch (e: any) {
        if (!cancelled) setEventsProblem(e);
      } finally {
        if (!cancelled) setEventsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  async function reloadRules() {
    setRulesLoading(true);
    try {
      const r = await api<RuleListResponse>('/api/v1/enterprises/alerts?limit=100');
      setRules(r.data ?? []);
      setRulesProblem(null);
    } catch (e: any) {
      setRulesProblem(e);
    } finally {
      setRulesLoading(false);
    }
  }

  async function deleteRule(rule: AlertRule) {
    if (!window.confirm(`Xoá quy tắc "${rule.name}"? Sự kiện cũ vẫn được giữ trong lịch sử.`)) return;
    try {
      await api(`/api/v1/enterprises/alerts/${rule.rule_id}`, { method: 'DELETE' });
      setRules((prev) => prev.filter((r) => r.rule_id !== rule.rule_id));
    } catch (e: any) {
      window.alert(`Không xoá được: ${e.title ?? 'lỗi không rõ'} — ${e.detail ?? ''}`);
    }
  }

  return (
    <>
      <PageHeader
        title="Cảnh báo"
        description="Quy tắc cảnh báo doanh nghiệp + lịch sử kích hoạt (email tự động khi vượt ngưỡng)."
        actions={
          tab === 'rules' ? (
            <Button variant="primary" onClick={() => setEditor({ open: true, rule: null })}>
              <Plus className="w-4 h-4 mr-1.5" /> Tạo quy tắc
            </Button>
          ) : null
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-[var(--border-color)]">
          <TabButton active={tab === 'events'} onClick={() => setTab('events')} icon={History}>
            Lịch sử
          </TabButton>
          <TabButton active={tab === 'rules'} onClick={() => setTab('rules')} icon={ListFilter}>
            Quy tắc ({rules.length})
          </TabButton>
        </div>

        {tab === 'events' ? (
          <EventsView
            events={events}
            rules={rules}
            loading={eventsLoading}
            problem={eventsProblem}
          />
        ) : (
          <RulesView
            rules={rules}
            loading={rulesLoading}
            problem={rulesProblem}
            onCreate={() => setEditor({ open: true, rule: null })}
            onEdit={(rule) => setEditor({ open: true, rule })}
            onDelete={deleteRule}
          />
        )}

        <ImplicitDefaultsHint />
      </div>

      {editor.open && (
        <RuleEditor
          rule={editor.rule}
          onClose={() => setEditor({ open: false, rule: null })}
          onSaved={async () => {
            setEditor({ open: false, rule: null });
            await reloadRules();
          }}
        />
      )}
    </>
  );
}

// ============================================================================
// Events tab
// ============================================================================

function EventsView({
  events, rules, loading, problem,
}: {
  events: AlertEvent[];
  rules: AlertRule[];
  loading: boolean;
  problem: ProblemDetails | null;
}) {
  const [search, setSearch] = useState('');
  const [showSuppressed, setShowSuppressed] = useState(true);

  const ruleNameById = useMemo(() => {
    const m = new Map<string, string>();
    m.set(SENTINEL_BILLING_80, 'Hạn mức 80% (mặc định)');
    m.set(SENTINEL_BILLING_95, 'Hạn mức 95% (mặc định)');
    rules.forEach((r) => m.set(r.rule_id, r.name));
    return m;
  }, [rules]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return events.filter((e) => {
      if (!showSuppressed && e.suppressed) return false;
      if (!q) return true;
      const name = ruleNameById.get(e.rule_id) ?? '';
      return name.toLowerCase().includes(q) || (e.metric_type ?? '').toLowerCase().includes(q);
    });
  }, [events, search, showSuppressed, ruleNameById]);

  const stats = useMemo(() => {
    const since7d = Date.now() - 7 * 86_400_000;
    const recent = events.filter((e) => +new Date(e.fired_at) >= since7d);
    return {
      fired7d:        recent.filter((e) => !e.suppressed).length,
      suppressed7d:   recent.filter((e) =>  e.suppressed).length,
      total:          events.length,
      latest:         events[0]?.fired_at ?? null,
    };
  }, [events]);

  return (
    <>
      {problem && (
        <ErrorBanner
          problem={{
            ...problem,
            title:  'Không tải được lịch sử',
            detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
          }}
        />
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile label="Đã gửi (7 ngày)"     value={stats.fired7d}      icon={Mail}        tone="text-[var(--state-success)]" />
        <StatTile label="Bị nén (7 ngày)"     value={stats.suppressed7d} icon={Hourglass}   tone="text-[var(--text-secondary)]" />
        <StatTile label="Tổng sự kiện"        value={stats.total}        icon={Bell}        tone="text-[var(--primary-gold-dark)]" />
        <StatTile
          label="Lần kích hoạt cuối"
          value={stats.latest ? formatRelative(stats.latest) : '—'}
          icon={Clock}
          tone="text-[var(--text-primary)]"
          isString
        />
      </div>

      {/* Toolbar */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex flex-col lg:flex-row items-stretch lg:items-center gap-3 shadow-soft-sm">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Tìm theo tên quy tắc hoặc metric..."
            className="w-full pl-9 pr-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all"
          />
        </div>
        <label className="inline-flex items-center gap-2 text-xs text-[var(--text-secondary)] select-none cursor-pointer">
          <input
            type="checkbox"
            checked={showSuppressed}
            onChange={(e) => setShowSuppressed(e.target.checked)}
            className="rounded-sm-custom border-[var(--border-color)]"
          />
          Hiện các sự kiện bị nén (cooldown / không có người nhận)
        </label>
      </div>

      {/* Table */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        <div className="overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">Quy tắc</th>
                <th className="px-5 py-3">Metric</th>
                <th className="px-5 py-3">Giá trị / ngưỡng</th>
                <th className="px-5 py-3">Thời điểm</th>
                <th className="px-5 py-3">Trạng thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {loading ? (
                <tr><td colSpan={5} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                  <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
                </td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={5} className="px-5 py-16 text-center">
                  <CheckCircle2 className="w-10 h-10 mx-auto text-[var(--state-success)]/40 mb-3" />
                  <p className="text-sm text-[var(--text-secondary)]">Chưa có sự kiện nào — quy tắc của bạn chưa từng kích hoạt.</p>
                </td></tr>
              ) : (
                filtered.map((e) => (
                  <EventRowItem
                    key={e.event_id}
                    event={e}
                    ruleName={ruleNameById.get(e.rule_id) ?? `Quy tắc đã xoá (${e.rule_id.slice(0, 8)})`}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function EventRowItem({ event: e, ruleName }: { event: AlertEvent; ruleName: string }) {
  const isBilling = e.metric_type === 'billing_quota_pct';
  const reason = (e.context && (e.context as any).suppress_reason) as string | undefined;
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4 max-w-md">
        <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-1">{ruleName}</p>
        {isBilling && (
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
            Hạn mức tháng — {(e.context as any)?.used ?? '—'} / {(e.context as any)?.quota_limit ?? '—'} khách hàng
          </p>
        )}
      </td>
      <td className="px-5 py-4">
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
          {isBilling ? <CreditCard className="w-3.5 h-3.5" /> : <AlertCircle className="w-3.5 h-3.5" />}
          {e.metric_type}
        </span>
      </td>
      <td className="px-5 py-4 font-mono text-xs">
        <span className="text-[var(--text-primary)]">{formatNumber(e.metric_value)}</span>
        <span className="text-[var(--text-secondary)] mx-1">{operatorSymbol(e.operator)}</span>
        <span className="text-[var(--text-secondary)]">{formatNumber(e.threshold_value)}</span>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {new Date(e.fired_at).toLocaleString('vi-VN', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })}
      </td>
      <td className="px-5 py-4">
        {e.suppressed ? (
          <div className="inline-flex flex-col gap-0.5">
            <Badge variant="default">
              <MailX className="w-3 h-3 mr-1" /> Bị nén
            </Badge>
            {reason && (
              <span className="text-[10px] text-[var(--text-secondary)]">
                {reason === 'cooldown' ? 'Cooldown' : reason === 'no_recipient' ? 'Không có MANAGER nhận' : reason}
              </span>
            )}
          </div>
        ) : e.outbox_id ? (
          <Badge variant="success">
            <Mail className="w-3 h-3 mr-1" /> Đã enqueue
          </Badge>
        ) : (
          <Badge variant="warning">Không rõ</Badge>
        )}
      </td>
    </tr>
  );
}

// ============================================================================
// Rules tab
// ============================================================================

function RulesView({
  rules, loading, problem, onCreate, onEdit, onDelete,
}: {
  rules: AlertRule[];
  loading: boolean;
  problem: ProblemDetails | null;
  onCreate: () => void;
  onEdit: (rule: AlertRule) => void;
  onDelete: (rule: AlertRule) => void;
}) {
  return (
    <>
      {problem && (
        <ErrorBanner
          problem={{
            ...problem,
            title:  'Không tải được danh sách quy tắc',
            detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
          }}
        />
      )}

      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        <div className="overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">Tên</th>
                <th className="px-5 py-3">Metric / điều kiện</th>
                <th className="px-5 py-3">Kênh</th>
                <th className="px-5 py-3">Cooldown</th>
                <th className="px-5 py-3">Trạng thái</th>
                <th className="px-5 py-3 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {loading ? (
                <tr><td colSpan={6} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                  <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> Đang tải...
                </td></tr>
              ) : rules.length === 0 ? (
                <tr><td colSpan={6} className="px-5 py-16 text-center">
                  <Bell className="w-10 h-10 mx-auto text-[var(--primary-gold)]/40 mb-3" />
                  <p className="text-sm text-[var(--text-secondary)] mb-3">
                    Chưa có quy tắc tuỳ chỉnh. Cảnh báo hạn mức 80% / 95% mặc định vẫn hoạt động.
                  </p>
                  <Button variant="primary" onClick={onCreate}>
                    <Plus className="w-4 h-4 mr-1.5" /> Tạo quy tắc đầu tiên
                  </Button>
                </td></tr>
              ) : (
                rules.map((r) => (
                  <RuleRowItem
                    key={r.rule_id}
                    rule={r}
                    onEdit={() => onEdit(r)}
                    onDelete={() => onDelete(r)}
                  />
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}

function RuleRowItem({
  rule: r, onEdit, onDelete,
}: { rule: AlertRule; onEdit: () => void; onDelete: () => void }) {
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4 max-w-md">
        <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-1">{r.name}</p>
        {r.description && (
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 line-clamp-1">{r.description}</p>
        )}
      </td>
      <td className="px-5 py-4 font-mono text-xs">
        <span className="text-[var(--text-secondary)]">{r.metric_type}</span>
        <span className="text-[var(--text-primary)] mx-1">{operatorSymbol(r.operator)}</span>
        <span className="text-[var(--text-primary)]">{formatNumber(r.threshold_value)}</span>
      </td>
      <td className="px-5 py-4">
        <span className="inline-flex items-center gap-1.5 text-xs text-[var(--text-secondary)]">
          <Mail className="w-3.5 h-3.5" />
          {r.target_email ?? 'MANAGER mặc định'}
        </span>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {formatCooldown(r.cooldown_seconds)}
      </td>
      <td className="px-5 py-4">
        <Badge variant={r.is_active ? 'success' : 'default'}>
          {r.is_active ? 'Đang bật' : 'Tắt'}
        </Badge>
      </td>
      <td className="px-5 py-4 text-right">
        <div className="inline-flex items-center gap-1">
          <button
            onClick={onEdit}
            className="px-2.5 py-1 text-[11px] font-medium text-[var(--text-primary)] border border-[var(--border-color)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors inline-flex items-center"
          >
            <Pencil className="w-3 h-3 mr-1" /> Sửa
          </button>
          <button
            onClick={onDelete}
            className="px-2.5 py-1 text-[11px] font-medium text-[var(--state-error)] border border-[var(--state-error)]/40 hover:bg-[var(--state-error)]/5 rounded-sm-custom transition-colors inline-flex items-center"
          >
            <Trash2 className="w-3 h-3 mr-1" /> Xoá
          </button>
        </div>
      </td>
    </tr>
  );
}

// ============================================================================
// Editor modal (create + edit share the same form)
// ============================================================================

interface RuleEditorState {
  open: boolean;
  rule: AlertRule | null;
}

function RuleEditor({
  rule, onClose, onSaved,
}: {
  rule: AlertRule | null;
  onClose: () => void;
  onSaved: () => void | Promise<void>;
}) {
  const isEdit = rule !== null;

  const [name,        setName]        = useState(rule?.name        ?? '');
  const [description, setDescription] = useState(rule?.description ?? '');
  const [operator,    setOperator]    = useState<Operator>(rule?.operator ?? 'gte');
  const [threshold,   setThreshold]   = useState<string>(String(rule?.threshold_value ?? '80'));
  const [targetEmail, setTargetEmail] = useState(rule?.target_email ?? '');
  const [cooldownMin, setCooldownMin] = useState<string>(String(Math.round((rule?.cooldown_seconds ?? 300) / 60)));
  const [isActive,    setIsActive]    = useState<boolean>(rule?.is_active ?? true);

  const [saving, setSaving] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function submit() {
    setSaving(true);
    setProblem(null);
    try {
      const cooldownSeconds = Math.max(0, Math.min(86400, Math.round(Number(cooldownMin) * 60)));
      const thresholdNum = Number(threshold);
      if (Number.isNaN(thresholdNum)) {
        setProblem({ type: '/docs/errors/invalid-request', title: 'Ngưỡng phải là số', status: 400, detail: '' });
        setSaving(false);
        return;
      }

      if (isEdit && rule) {
        const body: Record<string, unknown> = {
          name:             name.trim() || undefined,
          description:      description.trim() === '' ? null : description.trim(),
          operator,
          threshold_value:  thresholdNum,
          target_email:     targetEmail.trim() === '' ? null : targetEmail.trim(),
          cooldown_seconds: cooldownSeconds,
          is_active:        isActive,
        };
        await api(`/api/v1/enterprises/alerts/${rule.rule_id}`, {
          method: 'PATCH',
          body:   JSON.stringify(body),
        });
      } else {
        const body = {
          name:             name.trim(),
          description:      description.trim() || null,
          metric_type:      'billing_quota_pct',
          operator,
          threshold_value:  thresholdNum,
          channel:          'email',
          target_email:     targetEmail.trim() || null,
          cooldown_seconds: cooldownSeconds,
          is_active:        isActive,
        };
        await api('/api/v1/enterprises/alerts', {
          method: 'POST',
          body:   JSON.stringify(body),
        });
      }
      await onSaved();
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-40 bg-[var(--text-primary)]/40 flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-lg max-w-xl w-full max-h-[90vh] overflow-auto">
        <div className="px-6 py-4 border-b border-[var(--border-color)] flex items-center justify-between">
          <h2 className="font-serif text-xl text-[var(--text-primary)]">
            {isEdit ? 'Sửa quy tắc' : 'Tạo quy tắc mới'}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-sm-custom"
            aria-label="Đóng"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {problem && (
            <ErrorBanner
              problem={{
                ...problem,
                title:  problem.title ?? 'Không lưu được',
                detail: problem.detail ?? '',
              }}
            />
          )}

          <Field label="Tên quy tắc *">
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Ví dụ: Cảnh báo sớm hạn mức 90%"
              className={inputCls}
            />
          </Field>

          <Field label="Mô tả">
            <textarea
              rows={2}
              value={description ?? ''}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Tuỳ chọn — ngữ cảnh ngắn cho team"
              className={cn(inputCls, 'resize-none')}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Toán tử">
              <SelectField value={operator} onChange={(v) => setOperator(v as Operator)} options={[
                { value: 'gte', label: '≥ (lớn hơn hoặc bằng)' },
                { value: 'gt',  label: '> (lớn hơn)' },
                { value: 'lte', label: '≤ (nhỏ hơn hoặc bằng)' },
                { value: 'lt',  label: '< (nhỏ hơn)' },
                { value: 'eq',  label: '= (bằng)' },
              ]} />
            </Field>
            <Field label="Ngưỡng (%)">
              <input
                type="number"
                min="0"
                max="200"
                step="1"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className={inputCls}
              />
            </Field>
          </div>

          <Field label="Email người nhận">
            <input
              type="email"
              value={targetEmail ?? ''}
              onChange={(e) => setTargetEmail(e.target.value)}
              placeholder="Để trống → MANAGER mặc định"
              className={inputCls}
            />
          </Field>

          <Field label="Cooldown (phút) — gửi tối đa 1 lần trong khoảng">
            <input
              type="number"
              min="0"
              max="1440"
              step="5"
              value={cooldownMin}
              onChange={(e) => setCooldownMin(e.target.value)}
              className={inputCls}
            />
          </Field>

          <label className="inline-flex items-center gap-2 text-sm text-[var(--text-primary)] select-none cursor-pointer">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setIsActive(e.target.checked)}
              className="rounded-sm-custom border-[var(--border-color)]"
            />
            Đang bật (tắt nếu cần tạm dừng nhưng giữ cấu hình)
          </label>

          <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] p-3 text-xs text-[var(--text-secondary)]">
            <p>
              Phiên bản này hỗ trợ <span className="font-mono">metric_type=billing_quota_pct</span> + kênh <span className="font-mono">email</span>. Slack / webhook + các metric khác sẽ ship ở v1.
            </p>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-[var(--border-color)] flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={saving}>Huỷ</Button>
          <Button variant="primary" onClick={submit} disabled={saving || name.trim().length === 0}>
            {saving ? (
              <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> Đang lưu...</>
            ) : (
              <><Save className="w-4 h-4 mr-1.5" /> Lưu</>
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

const inputCls = 'w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm placeholder:text-[var(--text-secondary)]/60 focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)] transition-all';

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)] mb-1.5 block">
        {label}
      </span>
      {children}
    </label>
  );
}

function SelectField({
  value, onChange, options,
}: { value: string; onChange: (v: string) => void; options: { value: string; label: string }[] }) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={cn(inputCls, 'appearance-none pr-9 cursor-pointer')}
      >
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
      <ChevronDown className="w-4 h-4 text-[var(--text-secondary)] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
    </div>
  );
}

// ============================================================================
// Shared UI bits
// ============================================================================

function TabButton({
  active, onClick, icon: Icon, children,
}: { active: boolean; onClick: () => void; icon: any; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-2 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors',
        active
          ? 'text-[var(--text-primary)] border-[var(--primary-gold)]'
          : 'text-[var(--text-secondary)] border-transparent hover:text-[var(--text-primary)]',
      )}
    >
      <Icon className="w-4 h-4" />
      {children}
    </button>
  );
}

function StatTile({
  label, value, icon: Icon, tone, isString = false,
}: {
  label: string;
  value: number | string;
  icon: any;
  tone: string;
  isString?: boolean;
}) {
  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">{label}</span>
        <Icon className={cn('w-5 h-5', tone)} />
      </div>
      <p className={cn('font-serif text-[var(--text-primary)]', isString ? 'text-xl' : 'text-3xl')}>
        {value}
      </p>
    </div>
  );
}

function ImplicitDefaultsHint() {
  return (
    <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
      <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
      <p>
        Cảnh báo <span className="font-mono">hạn mức 80%</span> và <span className="font-mono">95%</span> luôn được gửi đến MANAGER khi bạn vượt ngưỡng — không cần tạo quy tắc.
        Cooldown mặc định 6 giờ, mỗi tháng phát tối đa 1 lần cho mỗi mức.
        Quy tắc tuỳ chỉnh ở tab "Quy tắc" cho phép chọn ngưỡng / email / cooldown khác.
      </p>
    </div>
  );
}

// ============================================================================
// Helpers
// ============================================================================

function operatorSymbol(op: Operator): string {
  switch (op) {
    case 'gt':  return '>';
    case 'gte': return '≥';
    case 'lt':  return '<';
    case 'lte': return '≤';
    case 'eq':  return '=';
    default:    return op;
  }
}

function formatNumber(v: number | string): string {
  const n = typeof v === 'number' ? v : Number(v);
  if (Number.isNaN(n)) return String(v);
  if (Number.isInteger(n)) return n.toLocaleString('vi-VN');
  return n.toFixed(2);
}

function formatCooldown(secs: number): string {
  if (secs < 60) return `${secs}s`;
  const min = Math.round(secs / 60);
  if (min < 60) return `${min} phút`;
  const hr = Math.round(min / 60 * 10) / 10;
  return `${hr} giờ`;
}

function formatRelative(iso: string): string {
  const diff = Date.now() - +new Date(iso);
  if (diff < 60_000)        return 'vừa xong';
  if (diff < 3_600_000)     return `${Math.round(diff / 60_000)} phút trước`;
  if (diff < 86_400_000)    return `${Math.round(diff / 3_600_000)} giờ trước`;
  if (diff < 7 * 86_400_000) return `${Math.round(diff / 86_400_000)} ngày trước`;
  return new Date(iso).toLocaleDateString('vi-VN');
}
