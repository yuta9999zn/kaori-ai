'use client';

// ============================================================================
// /p2/strategy/okr — OKR Editor & Tracker (F-040 BE PR #144)
// ----------------------------------------------------------------------------
// Wires:
//   GET    /api/v1/enterprises/strategy/okr?quarter=
//   POST   /api/v1/enterprises/strategy/okr                  (MANAGER)
//   PATCH  /api/v1/enterprises/strategy/okr/{id}             (MANAGER)
//   PATCH  /api/v1/enterprises/strategy/okr/{id}/kr/{krId}/progress  (MANAGER)
//   DELETE /api/v1/enterprises/strategy/okr/{id}             (MANAGER)
//
// Layout (per template 53):
//   - Quarter selector
//   - List of objectives with progress bar + status badge + KR table
//   - Inline KR progress slider — debounced PATCH
//   - "+ Thêm Objective" modal (POST)
//   - Edit objective modal (PATCH title/quarter/owner/full KR set)
//   - Soft-delete from row menu (DELETE)
// ============================================================================

import React, { useEffect, useMemo, useState } from 'react';
import {
  Target, Plus, ArrowLeft, Save, Trash2, CheckCircle2, AlertTriangle,
  TrendingUp, Loader2, X as XIcon, Calendar, ChevronDown,
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

type Status = 'on_track' | 'at_risk' | 'off_track';

interface KeyResult {
  kr_id:         string;
  title:         string;
  unit:          string;
  target:        number;
  current_value: number;
  display_order: number;
}

interface Objective {
  objective_id:    string;
  quarter:         string;
  title:           string;
  owner_user_id:   string | null;
  status:          Status;
  created_by_user: string | null;
  created_at:      string;
  updated_at:      string;
  key_results:     KeyResult[];
}

interface ListResponse {
  data: Objective[];
  meta: { total: number; page: number; limit: number };
}

const STATUS_META: Record<Status, { labelKey: string; variant: 'success' | 'warning' | 'error'; icon: React.ComponentType<{ className?: string }> }> = {
  on_track:  { labelKey: 'templatesFnew40StrategyOkr.statusOnTrack',  variant: 'success', icon: CheckCircle2 },
  at_risk:   { labelKey: 'templatesFnew40StrategyOkr.statusAtRisk',   variant: 'warning', icon: TrendingUp },
  off_track: { labelKey: 'templatesFnew40StrategyOkr.statusOffTrack', variant: 'error',   icon: AlertTriangle },
};

function buildQuarterOptions(): string[] {
  const now    = new Date();
  const month  = now.getMonth();
  const year   = now.getFullYear();
  const curQ   = Math.floor(month / 3) + 1;
  const opts: string[] = [];
  for (let offset = -2; offset <= 2; offset++) {
    let q = curQ + offset;
    let y = year;
    while (q < 1) { q += 4; y -= 1; }
    while (q > 4) { q -= 4; y += 1; }
    opts.push(`Q${q} ${y}`);
  }
  return opts;
}

function krProgressPct(kr: KeyResult): number {
  if (kr.target <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((kr.current_value / kr.target) * 100)));
}

function objProgress(obj: Objective): number {
  if (obj.key_results.length === 0) return 0;
  return Math.round(
    obj.key_results.reduce((s, k) => s + krProgressPct(k), 0) / obj.key_results.length,
  );
}

// ============================================================================
// Page
// ============================================================================

export default function StrategyOkrPage() {
  const t = useT();
  const quarters = useMemo(buildQuarterOptions, []);
  const [quarter, setQuarter]       = useState(quarters[2]);
  const [objectives, setObjectives] = useState<Objective[]>([]);
  const [loading, setLoading]       = useState(true);
  const [problem, setProblem]       = useState<ProblemDetails | null>(null);
  const [success, setSuccess]       = useState<string | null>(null);

  const [showCreate, setShowCreate]     = useState(false);
  const [editing, setEditing]           = useState<Objective | null>(null);
  const [savingKrId, setSavingKrId]     = useState<string | null>(null);
  const [deletingId, setDeletingId]     = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const r = await api<ListResponse>(
        `/api/v1/enterprises/strategy/okr?quarter=${encodeURIComponent(quarter)}&limit=200`);
      setObjectives(r.data ?? []);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [quarter]);

  async function patchKrProgress(obj: Objective, kr: KeyResult, currentValue: number) {
    setSavingKrId(kr.kr_id);
    setProblem(null);
    try {
      const r = await api<{ data: Objective }>(
        `/api/v1/enterprises/strategy/okr/${obj.objective_id}/kr/${kr.kr_id}/progress`,
        { method: 'PATCH', body: JSON.stringify({ current_value: currentValue }) },
      );
      setObjectives((prev) => prev.map((o) =>
        o.objective_id === obj.objective_id ? r.data : o,
      ));
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setSavingKrId(null);
    }
  }

  async function deleteObjective(obj: Objective) {
    if (!window.confirm(t('templatesFnew40StrategyOkr.confirmDelete', { title: obj.title }))) return;
    setDeletingId(obj.objective_id);
    setProblem(null);
    try {
      await api(`/api/v1/enterprises/strategy/okr/${obj.objective_id}`, { method: 'DELETE' });
      setObjectives((prev) => prev.filter((o) => o.objective_id !== obj.objective_id));
      setSuccess(t('templatesFnew40StrategyOkr.deletedSuccess', { title: obj.title }));
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <>
      <PageHeader
        title={t('templatesFnew40StrategyOkr.pageTitle')}
        description={t('templatesFnew40StrategyOkr.pageDescription')}
        actions={
          <>
            <Badge variant="info">F-040</Badge>
            <a href="/p2/strategy">
              <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> {t('templatesFnew40StrategyOkr.btnOverview')}</Button>
            </a>
            <Button variant="primary" size="md" onClick={() => setShowCreate(true)}>
              <Plus className="w-4 h-4 mr-2" /> {t('templatesFnew40StrategyOkr.btnAddObjective')}
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-6">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        {/* Quarter selector */}
        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-3 flex items-center gap-3 shadow-soft-sm">
          <span className="text-xs text-[var(--text-secondary)] uppercase tracking-wider font-medium inline-flex items-center gap-1.5">
            <Calendar className="w-3.5 h-3.5" /> {t('templatesFnew40StrategyOkr.quarterLabel')}
          </span>
          {quarters.map((q) => (
            <button
              key={q}
              onClick={() => setQuarter(q)}
              className={cn(
                'px-3 py-1.5 text-xs font-medium rounded-sm-custom border transition-colors',
                q === quarter
                  ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/10 text-[var(--primary-gold-dark)]'
                  : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-[var(--bg-app)]',
              )}
            >
              {q}
            </button>
          ))}
        </div>

        {/* Objectives list */}
        {loading && objectives.length === 0 ? (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-48 rounded-lg-custom bg-[var(--bg-card)] border border-[var(--border-color)] animate-pulse" />
            ))}
          </div>
        ) : objectives.length === 0 ? (
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-12 text-center shadow-soft-sm">
            <Target className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-3" />
            <p className="text-sm text-[var(--text-secondary)]">
              {t('templatesFnew40StrategyOkr.emptyState', { quarter })}
            </p>
            <div className="mt-4">
              <Button variant="primary" size="sm" onClick={() => setShowCreate(true)}>
                <Plus className="w-3.5 h-3.5 mr-1.5" /> {t('templatesFnew40StrategyOkr.btnAddObjective')}
              </Button>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            {objectives.map((obj) => (
              <ObjectiveCard
                key={obj.objective_id}
                obj={obj}
                savingKrId={savingKrId}
                deleting={deletingId === obj.objective_id}
                onKrChange={(kr, v) => patchKrProgress(obj, kr, v)}
                onEdit={() => setEditing(obj)}
                onDelete={() => deleteObjective(obj)}
              />
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <ObjectiveModal
          mode="create"
          quarter={quarter}
          quarters={quarters}
          onClose={() => setShowCreate(false)}
          onSaved={(title) => {
            setShowCreate(false);
            setSuccess(t('templatesFnew40StrategyOkr.createdSuccess', { title }));
            load();
          }}
        />
      )}

      {editing && (
        <ObjectiveModal
          mode="edit"
          quarter={editing.quarter}
          quarters={quarters}
          existing={editing}
          onClose={() => setEditing(null)}
          onSaved={(title) => {
            setEditing(null);
            setSuccess(t('templatesFnew40StrategyOkr.updatedSuccess', { title }));
            load();
          }}
        />
      )}
    </>
  );
}

// ============================================================================
// ObjectiveCard
// ============================================================================

function ObjectiveCard({
  obj, savingKrId, deleting, onKrChange, onEdit, onDelete,
}: {
  obj:        Objective;
  savingKrId: string | null;
  deleting:   boolean;
  onKrChange: (kr: KeyResult, v: number) => void;
  onEdit:     () => void;
  onDelete:   () => void;
}) {
  const t = useT();
  const meta = STATUS_META[obj.status];
  const Icon = meta.icon;
  const overall = objProgress(obj);

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 shadow-soft-sm">
      <div className="flex items-start justify-between mb-3 gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap mb-1">
            <Badge variant="default">{obj.quarter}</Badge>
            <Badge variant={meta.variant}>
              <Icon className="w-3 h-3 mr-1" /> {t(meta.labelKey)}
            </Badge>
            {obj.owner_user_id && (
              <span className="text-[11px] text-[var(--text-secondary)] font-mono">
                {obj.owner_user_id.slice(0, 8)}...
              </span>
            )}
          </div>
          <h3 className="font-serif text-lg text-[var(--text-primary)]">{obj.title}</h3>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <Button variant="tertiary" size="sm" onClick={onEdit}>{t('templatesFnew40StrategyOkr.btnEdit')}</Button>
          <Button
            variant="tertiary" size="sm" onClick={onDelete} disabled={deleting}
            className="text-[var(--state-error)] hover:bg-[var(--state-error)]/10"
          >
            {deleting ? (
              <><Loader2 className="w-3.5 h-3.5 animate-spin" /></>
            ) : (
              <><Trash2 className="w-3.5 h-3.5" /></>
            )}
          </Button>
        </div>
      </div>

      <div className="mb-3">
        <div className="flex items-baseline justify-between mb-1">
          <span className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)]">
            {t('templatesFnew40StrategyOkr.avgProgressLabel')}
          </span>
          <span className="text-sm font-mono text-[var(--text-primary)]">{overall}%</span>
        </div>
        <div className="h-2 bg-[var(--border-color)]/40 rounded-full overflow-hidden">
          <div className="h-full bg-[var(--primary-gold)]" style={{ width: `${overall}%` }} />
        </div>
      </div>

      <ul className="divide-y divide-[var(--border-color)]/60">
        {obj.key_results.map((kr) => (
          <KrRow
            key={kr.kr_id}
            kr={kr}
            saving={savingKrId === kr.kr_id}
            onChange={(v) => onKrChange(kr, v)}
          />
        ))}
      </ul>
    </div>
  );
}

function KrRow({
  kr, saving, onChange,
}: { kr: KeyResult; saving: boolean; onChange: (v: number) => void }) {
  // Local state for the slider so dragging doesn't fire a PATCH per pixel.
  // Commits on `mouseup` / `touchend` via the onPointerUp handler.
  const [draft, setDraft] = useState(kr.current_value);
  useEffect(() => { setDraft(kr.current_value); }, [kr.current_value]);

  const pct = kr.target > 0 ? Math.min(100, Math.round((draft / kr.target) * 100)) : 0;

  return (
    <li className="py-3">
      <div className="flex items-baseline justify-between gap-3 mb-1">
        <p className="text-sm font-medium text-[var(--text-primary)] flex-1 truncate">{kr.title}</p>
        <span className="text-xs font-mono text-[var(--text-secondary)] shrink-0">
          {draft.toLocaleString('vi-VN')} / {kr.target.toLocaleString('vi-VN')} {kr.unit}
        </span>
        {saving && <Loader2 className="w-3.5 h-3.5 animate-spin text-[var(--text-secondary)]" />}
      </div>
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={0}
          max={Math.max(kr.target, draft)}
          step={kr.target >= 100 ? Math.round(kr.target / 100) || 1 : 1}
          value={draft}
          onChange={(e) => setDraft(Number(e.target.value))}
          onPointerUp={() => {
            if (draft !== kr.current_value) onChange(draft);
          }}
          onBlur={() => {
            if (draft !== kr.current_value) onChange(draft);
          }}
          className="flex-1 h-2 bg-[var(--border-color)]/40 rounded-full accent-[var(--primary-gold)]"
        />
        <span className="text-xs font-mono text-[var(--text-primary)] w-10 text-right">{pct}%</span>
      </div>
    </li>
  );
}

// ============================================================================
// Create / Edit modal
// ============================================================================

interface KrDraft {
  title:         string;
  unit:          string;
  target:        number;
  current_value: number;
}

function ObjectiveModal({
  mode, quarter, quarters, existing, onClose, onSaved,
}: {
  mode:      'create' | 'edit';
  quarter:   string;
  quarters:  string[];
  existing?: Objective;
  onClose:   () => void;
  onSaved:   (title: string) => void;
}) {
  const t = useT();
  const [title, setTitle]       = useState(existing?.title ?? '');
  const [q, setQ]               = useState(existing?.quarter ?? quarter);
  const [ownerId, setOwnerId]   = useState(existing?.owner_user_id ?? '');
  const [krs, setKrs]           = useState<KrDraft[]>(
    existing
      ? existing.key_results.map((k) => ({
          title: k.title, unit: k.unit, target: k.target, current_value: k.current_value,
        }))
      : [
          { title: '', unit: '', target: 100, current_value: 0 },
          { title: '', unit: '', target: 100, current_value: 0 },
          { title: '', unit: '', target: 100, current_value: 0 },
        ],
  );
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem]       = useState<ProblemDetails | null>(null);

  function setKr(i: number, patch: Partial<KrDraft>) {
    setKrs((prev) => prev.map((k, idx) => idx === i ? { ...k, ...patch } : k));
  }
  function addKr() {
    if (krs.length >= 10) return;
    setKrs((prev) => [...prev, { title: '', unit: '', target: 100, current_value: 0 }]);
  }
  function removeKr(i: number) {
    if (krs.length <= 1) return;
    setKrs((prev) => prev.filter((_, idx) => idx !== i));
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setProblem(null);
    try {
      const body = {
        quarter:       q,
        title,
        owner_user_id: ownerId || null,
        key_results:   krs.map((k) => ({
          title:         k.title,
          unit:          k.unit,
          target:        k.target,
          current_value: k.current_value,
        })),
      };
      if (mode === 'create') {
        await api('/api/v1/enterprises/strategy/okr', {
          method: 'POST', body: JSON.stringify(body),
        });
      } else if (existing) {
        await api(`/api/v1/enterprises/strategy/okr/${existing.objective_id}`, {
          method: 'PATCH', body: JSON.stringify(body),
        });
      }
      onSaved(title);
    } catch (e) {
      setProblem(e as ProblemDetails);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 animate-fade-in">
      <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-auto">
        <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border-color)]">
          <h3 className="font-serif text-lg text-[var(--text-primary)]">
            {mode === 'create' ? t('templatesFnew40StrategyOkr.modalTitleCreate') : t('templatesFnew40StrategyOkr.modalTitleEdit')}
          </h3>
          <button onClick={onClose} aria-label={t('templatesFnew40StrategyOkr.closeAria')} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
            <XIcon className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={onSubmit} className="p-5 space-y-4">
          {problem && <ErrorBanner problem={problem} />}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-2 md:col-span-2">
              <Input
                label={t('templatesFnew40StrategyOkr.objectiveNameLabel')}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t('templatesFnew40StrategyOkr.objectiveNamePlaceholder')}
                required
                maxLength={200}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-[var(--text-primary)]">{t('templatesFnew40StrategyOkr.quarterFieldLabel')}</label>
              <div className="relative">
                <select
                  value={q}
                  onChange={(e) => setQ(e.target.value)}
                  className="w-full h-10 pl-3 pr-9 appearance-none bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
                >
                  {quarters.map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                </select>
                <ChevronDown className="w-4 h-4 text-[var(--text-secondary)] absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              </div>
            </div>
          </div>

          <Input
            label={t('templatesFnew40StrategyOkr.ownerLabel')}
            value={ownerId}
            onChange={(e) => setOwnerId(e.target.value)}
            placeholder="00000000-0000-0000-0000-000000000000"
          />

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-[var(--text-primary)]">
                {t('templatesFnew40StrategyOkr.keyResultsLabel', { count: String(krs.length) })}
              </label>
              <Button
                variant="tertiary" type="button" size="sm"
                onClick={addKr} disabled={krs.length >= 10}
              >
                <Plus className="w-3.5 h-3.5 mr-1" /> {t('templatesFnew40StrategyOkr.btnAddKr')}
              </Button>
            </div>
            <ul className="space-y-3">
              {krs.map((kr, i) => (
                <li key={i} className="border border-[var(--border-color)] rounded-md-custom p-3 bg-[var(--bg-app)]/30">
                  <div className="flex items-baseline justify-between gap-2 mb-2">
                    <span className="text-[11px] uppercase tracking-wider font-medium text-[var(--text-secondary)]">
                      {t('templatesFnew40StrategyOkr.krLabel', { n: String(i + 1) })}
                    </span>
                    {krs.length > 1 && (
                      <button
                        type="button" onClick={() => removeKr(i)}
                        className="text-[var(--state-error)] hover:underline text-xs"
                      >
                        {t('templatesFnew40StrategyOkr.btnRemoveKr')}
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-12 gap-2">
                    <div className="md:col-span-6">
                      <Input
                        label={t('templatesFnew40StrategyOkr.krDescLabel')}
                        value={kr.title}
                        onChange={(e) => setKr(i, { title: e.target.value })}
                        placeholder={t('templatesFnew40StrategyOkr.krDescPlaceholder')}
                        required
                        maxLength={200}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Input
                        label={t('templatesFnew40StrategyOkr.unitLabel')}
                        value={kr.unit}
                        onChange={(e) => setKr(i, { unit: e.target.value })}
                        placeholder={t('templatesFnew40StrategyOkr.unitPlaceholder')}
                        maxLength={40}
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Input
                        label={t('templatesFnew40StrategyOkr.targetLabel')}
                        type="number"
                        value={String(kr.target)}
                        onChange={(e) => setKr(i, { target: Number(e.target.value) || 0 })}
                        min={0.0001}
                        step="any"
                        required
                      />
                    </div>
                    <div className="md:col-span-2">
                      <Input
                        label={t('templatesFnew40StrategyOkr.currentLabel')}
                        type="number"
                        value={String(kr.current_value)}
                        onChange={(e) => setKr(i, { current_value: Number(e.target.value) || 0 })}
                        min={0}
                        step="any"
                      />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-color)]">
            <Button variant="tertiary" type="button" onClick={onClose} disabled={submitting}>{t('templatesFnew40StrategyOkr.btnCancel')}</Button>
            <Button
              variant="primary" type="submit" isLoading={submitting}
              disabled={!title.trim() || krs.some((k) => !k.title.trim() || k.target <= 0)}
            >
              <Save className="w-4 h-4 mr-2" /> {mode === 'create' ? t('templatesFnew40StrategyOkr.btnCreateObjective') : t('templatesFnew40StrategyOkr.btnSaveChanges')}
            </Button>
          </div>
        </form>
      </div>
    </div>
  );
}
