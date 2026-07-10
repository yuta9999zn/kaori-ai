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
import { useT } from '@/lib/i18n/provider';
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
  const t = useT();
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
    if (!window.confirm(t('templates62bAlertsF037.confirmDeleteRule', { name: rule.name }))) return;
    try {
      await api(`/api/v1/enterprises/alerts/${rule.rule_id}`, { method: 'DELETE' });
      setRules((prev) => prev.filter((r) => r.rule_id !== rule.rule_id));
    } catch (e: any) {
      window.alert(`${t('templates62bAlertsF037.deleteFailedPrefix')}: ${e.title ?? t('templates62bAlertsF037.unknownError')} — ${e.detail ?? ''}`);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templates62bAlertsF037.pageTitle')}
        description={t('templates62bAlertsF037.pageDescription')}
        actions={
          tab === 'rules' ? (
            <Button variant="primary" onClick={() => setEditor({ open: true, rule: null })}>
              <Plus className="w-4 h-4 mr-1.5" /> {t('templates62bAlertsF037.createRule')}
            </Button>
          ) : null
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-6">
        {/* Tabs */}
        <div className="flex items-center gap-1 border-b border-[var(--border-color)]">
          <TabButton active={tab === 'events'} onClick={() => setTab('events')} icon={History}>
            {t('templates62bAlertsF037.tabHistory')}
          </TabButton>
          <TabButton active={tab === 'rules'} onClick={() => setTab('rules')} icon={ListFilter}>
            {t('templates62bAlertsF037.tabRulesCount', { count: rules.length })}
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
  const t = useT();
  const [search, setSearch] = useState('');
  const [showSuppressed, setShowSuppressed] = useState(true);

  const ruleNameById = useMemo(() => {
    const m = new Map<string, string>();
    m.set(SENTINEL_BILLING_80, t('templates62bAlertsF037.quota80Default'));
    m.set(SENTINEL_BILLING_95, t('templates62bAlertsF037.quota95Default'));
    rules.forEach((r) => m.set(r.rule_id, r.name));
    return m;
  }, [rules, t]);

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
            title:  t('templates62bAlertsF037.errLoadHistory'),
            detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
          }}
        />
      )}

      {/* KPI tiles */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatTile label={t('templates62bAlertsF037.sentLast7d')}       value={stats.fired7d}      icon={Mail}        tone="text-[var(--state-success)]" />
        <StatTile label={t('templates62bAlertsF037.suppressedLast7d')} value={stats.suppressed7d} icon={Hourglass}   tone="text-[var(--text-secondary)]" />
        <StatTile label={t('templates62bAlertsF037.totalEvents')}      value={stats.total}        icon={Bell}        tone="text-[var(--primary-gold-dark)]" />
        <StatTile
          label={t('templates62bAlertsF037.lastFired')}
          value={stats.latest ? formatRelative(stats.latest, t) : '—'}
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
            placeholder={t('templates62bAlertsF037.searchPlaceholder')}
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
          {t('templates62bAlertsF037.showSuppressedLabel')}
        </label>
      </div>

      {/* Table */}
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        <div className="overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colRule')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colMetric')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colValueThreshold')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colTime')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colStatus')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {loading ? (
                <tr><td colSpan={5} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                  <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templates62bAlertsF037.loading')}
                </td></tr>
              ) : filtered.length === 0 ? (
                <tr><td colSpan={5} className="px-5 py-16 text-center">
                  <CheckCircle2 className="w-10 h-10 mx-auto text-[var(--state-success)]/40 mb-3" />
                  <p className="text-sm text-[var(--text-secondary)]">{t('templates62bAlertsF037.noEvents')}</p>
                </td></tr>
              ) : (
                filtered.map((e) => (
                  <EventRowItem
                    key={e.event_id}
                    event={e}
                    ruleName={ruleNameById.get(e.rule_id) ?? t('templates62bAlertsF037.deletedRule', { id: e.rule_id.slice(0, 8) })}
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
  const t = useT();
  const isBilling = e.metric_type === 'billing_quota_pct';
  const reason = (e.context && (e.context as any).suppress_reason) as string | undefined;
  return (
    <tr className="hover:bg-[var(--bg-app)]/40 transition-colors">
      <td className="px-5 py-4 max-w-md">
        <p className="text-sm font-medium text-[var(--text-primary)] line-clamp-1">{ruleName}</p>
        {isBilling && (
          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5">
            {t('templates62bAlertsF037.quotaMonthly', {
              used: (e.context as any)?.used ?? '—',
              limit: (e.context as any)?.quota_limit ?? '—',
            })}
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
              <MailX className="w-3 h-3 mr-1" /> {t('templates62bAlertsF037.suppressedBadge')}
            </Badge>
            {reason && (
              <span className="text-[10px] text-[var(--text-secondary)]">
                {reason === 'cooldown' ? t('templates62bAlertsF037.reasonCooldown') : reason === 'no_recipient' ? t('templates62bAlertsF037.reasonNoRecipient') : reason}
              </span>
            )}
          </div>
        ) : e.outbox_id ? (
          <Badge variant="success">
            <Mail className="w-3 h-3 mr-1" /> {t('templates62bAlertsF037.enqueuedBadge')}
          </Badge>
        ) : (
          <Badge variant="warning">{t('templates62bAlertsF037.unknownBadge')}</Badge>
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
  const t = useT();
  return (
    <>
      {problem && (
        <ErrorBanner
          problem={{
            ...problem,
            title:  t('templates62bAlertsF037.errLoadRules'),
            detail: `${problem.title}${problem.detail ? ' — ' + problem.detail : ''}.`,
          }}
        />
      )}

      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-soft-sm overflow-hidden">
        <div className="overflow-auto">
          <table className="w-full text-sm text-left">
            <thead className="bg-[var(--bg-app)] border-b border-[var(--border-color)] text-[11px] font-medium uppercase tracking-wider text-[var(--text-secondary)]">
              <tr>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colName')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colMetricCondition')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colChannel')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colCooldown')}</th>
                <th className="px-5 py-3">{t('templates62bAlertsF037.colStatus')}</th>
                <th className="px-5 py-3 text-right">{t('templates62bAlertsF037.colActions')}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-color)]/60">
              {loading ? (
                <tr><td colSpan={6} className="px-5 py-16 text-center text-[var(--text-secondary)]">
                  <Loader2 className="w-5 h-5 animate-spin inline mr-2" /> {t('templates62bAlertsF037.loading')}
                </td></tr>
              ) : rules.length === 0 ? (
                <tr><td colSpan={6} className="px-5 py-16 text-center">
                  <Bell className="w-10 h-10 mx-auto text-[var(--primary-gold)]/40 mb-3" />
                  <p className="text-sm text-[var(--text-secondary)] mb-3">
                    {t('templates62bAlertsF037.noRules')}
                  </p>
                  <Button variant="primary" onClick={onCreate}>
                    <Plus className="w-4 h-4 mr-1.5" /> {t('templates62bAlertsF037.createFirstRule')}
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
  const t = useT();
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
          {r.target_email ?? t('templates62bAlertsF037.managerDefault')}
        </span>
      </td>
      <td className="px-5 py-4 text-xs text-[var(--text-secondary)]">
        {formatCooldown(r.cooldown_seconds, t)}
      </td>
      <td className="px-5 py-4">
        <Badge variant={r.is_active ? 'success' : 'default'}>
          {r.is_active ? t('templates62bAlertsF037.statusActive') : t('templates62bAlertsF037.statusInactive')}
        </Badge>
      </td>
      <td className="px-5 py-4 text-right">
        <div className="inline-flex items-center gap-1">
          <button
            onClick={onEdit}
            className="px-2.5 py-1 text-[11px] font-medium text-[var(--text-primary)] border border-[var(--border-color)] hover:bg-[var(--bg-app)] rounded-sm-custom transition-colors inline-flex items-center"
          >
            <Pencil className="w-3 h-3 mr-1" /> {t('templates62bAlertsF037.edit')}
          </button>
          <button
            onClick={onDelete}
            className="px-2.5 py-1 text-[11px] font-medium text-[var(--state-error)] border border-[var(--state-error)]/40 hover:bg-[var(--state-error)]/5 rounded-sm-custom transition-colors inline-flex items-center"
          >
            <Trash2 className="w-3 h-3 mr-1" /> {t('templates62bAlertsF037.delete')}
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
  const t = useT();
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
        setProblem({ type: '/docs/errors/invalid-request', title: t('templates62bAlertsF037.errThresholdNotNumber'), status: 400, detail: '' });
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
            {isEdit ? t('templates62bAlertsF037.editRuleTitle') : t('templates62bAlertsF037.createRuleTitle')}
          </h2>
          <button
            onClick={onClose}
            className="p-1 text-[var(--text-secondary)] hover:text-[var(--text-primary)] rounded-sm-custom"
            aria-label={t('templates62bAlertsF037.close')}
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          {problem && (
            <ErrorBanner
              problem={{
                ...problem,
                title:  problem.title ?? t('templates62bAlertsF037.errSaveFailed'),
                detail: problem.detail ?? '',
              }}
            />
          )}

          <Field label={t('templates62bAlertsF037.fieldName')}>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t('templates62bAlertsF037.fieldNamePlaceholder')}
              className={inputCls}
            />
          </Field>

          <Field label={t('templates62bAlertsF037.fieldDescription')}>
            <textarea
              rows={2}
              value={description ?? ''}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t('templates62bAlertsF037.fieldDescriptionPlaceholder')}
              className={cn(inputCls, 'resize-none')}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label={t('templates62bAlertsF037.fieldOperator')}>
              <SelectField value={operator} onChange={(v) => setOperator(v as Operator)} options={[
                { value: 'gte', label: t('templates62bAlertsF037.opGte') },
                { value: 'gt',  label: t('templates62bAlertsF037.opGt') },
                { value: 'lte', label: t('templates62bAlertsF037.opLte') },
                { value: 'lt',  label: t('templates62bAlertsF037.opLt') },
                { value: 'eq',  label: t('templates62bAlertsF037.opEq') },
              ]} />
            </Field>
            <Field label={t('templates62bAlertsF037.fieldThreshold')}>
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

          <Field label={t('templates62bAlertsF037.fieldEmail')}>
            <input
              type="email"
              value={targetEmail ?? ''}
              onChange={(e) => setTargetEmail(e.target.value)}
              placeholder={t('templates62bAlertsF037.fieldEmailPlaceholder')}
              className={inputCls}
            />
          </Field>

          <Field label={t('templates62bAlertsF037.fieldCooldown')}>
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
            {t('templates62bAlertsF037.activeCheckboxLabel')}
          </label>

          <div className="rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] p-3 text-xs text-[var(--text-secondary)]">
            <p>
              {t('templates62bAlertsF037.supportNote1')} <span className="font-mono">metric_type=billing_quota_pct</span> {t('templates62bAlertsF037.supportNote2')} <span className="font-mono">email</span>{t('templates62bAlertsF037.supportNote3')}
            </p>
          </div>
        </div>

        <div className="px-6 py-4 border-t border-[var(--border-color)] flex items-center justify-end gap-2">
          <Button variant="secondary" onClick={onClose} disabled={saving}>{t('templates62bAlertsF037.cancel')}</Button>
          <Button variant="primary" onClick={submit} disabled={saving || name.trim().length === 0}>
            {saving ? (
              <><Loader2 className="w-4 h-4 mr-1.5 animate-spin" /> {t('templates62bAlertsF037.saving')}</>
            ) : (
              <><Save className="w-4 h-4 mr-1.5" /> {t('templates62bAlertsF037.save')}</>
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
  const t = useT();
  return (
    <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
      <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
      <p>
        {t('templates62bAlertsF037.implicitHintPre')} <span className="font-mono">{t('templates62bAlertsF037.quota80Label')}</span> {t('templates62bAlertsF037.implicitHintAnd')} <span className="font-mono">95%</span> {t('templates62bAlertsF037.implicitHintPost')}
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

function formatCooldown(secs: number, t: ReturnType<typeof useT>): string {
  if (secs < 60) return `${secs}s`;
  const min = Math.round(secs / 60);
  if (min < 60) return t('templates62bAlertsF037.cooldownMinutes', { min });
  const hr = Math.round(min / 60 * 10) / 10;
  return t('templates62bAlertsF037.cooldownHours', { hr });
}

function formatRelative(iso: string, t: ReturnType<typeof useT>): string {
  const diff = Date.now() - +new Date(iso);
  if (diff < 60_000)        return t('templates62bAlertsF037.justNow');
  if (diff < 3_600_000)     return t('templates62bAlertsF037.minutesAgo', { n: Math.round(diff / 60_000) });
  if (diff < 86_400_000)    return t('templates62bAlertsF037.hoursAgo', { n: Math.round(diff / 3_600_000) });
  if (diff < 7 * 86_400_000) return t('templates62bAlertsF037.daysAgo', { n: Math.round(diff / 86_400_000) });
  return new Date(iso).toLocaleDateString('vi-VN');
}
