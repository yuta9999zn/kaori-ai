// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 53. /p2/strategy/okr — OKR Editor & Tracker (F-054 🔵 Phase 2)
// ----------------------------------------------------------------------------
// Quản lý Objective + 3 Key Results theo quý:
//   - List OKR đang chạy với progress bar + status (on_track/at_risk/off_track).
//   - Bấm 1 OKR → mở panel chỉnh objective + 3 KR (target/current/unit).
//   - Status auto-tính từ progress + thời gian còn lại của quý:
//       progress >= timeProgress - 5%   → on_track
//       within 15% lag                  → at_risk
//       lag > 15%                       → off_track
//
// Wire (Phase 2): `GET/POST /api/v1/strategy/okr` + `PATCH /api/v1/strategy/okr/{id}/kr`.
// ============================================================================

import React, { useMemo, useState } from 'react';
import {
  Target, Plus, ArrowLeft, Save, Trash2, CheckCircle2,
  AlertTriangle, TrendingUp, Calendar, ShieldCheck,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
// ============================================================================
// Types & helpers
// ============================================================================

type OkrStatus = 'on_track' | 'at_risk' | 'off_track';

interface KeyResult {
  id:      string;
  title:   string;
  unit:    string;     // "%" | "VNĐ" | "khách hàng" | etc.
  target:  number;
  current: number;
}

interface Objective {
  id:        string;
  quarter:   string;   // "Q2 2026"
  title:     string;
  owner:     string;
  krs:       KeyResult[];
}

const Q2_PROGRESS = 0.45; // pretend Q2/2026 has elapsed 45% so we can compute status

function progressPct(kr: KeyResult): number {
  if (kr.target <= 0) return 0;
  return Math.max(0, Math.min(100, Math.round((kr.current / kr.target) * 100)));
}

function objProgress(obj: Objective): number {
  if (obj.krs.length === 0) return 0;
  return Math.round(obj.krs.reduce((sum, k) => sum + progressPct(k), 0) / obj.krs.length);
}

function objStatus(obj: Objective): OkrStatus {
  const p = objProgress(obj) / 100;
  const lag = Q2_PROGRESS - p;
  if (lag <= 0.05) return 'on_track';
  if (lag <= 0.15) return 'at_risk';
  return 'off_track';
}

const STATUS_META: Record<OkrStatus, { label: string; variant: 'success' | 'warning' | 'error'; icon: any }> = {
  on_track:  { label: 'On-track',  variant: 'success', icon: CheckCircle2 },
  at_risk:   { label: 'At-risk',   variant: 'warning', icon: TrendingUp },
  off_track: { label: 'Off-track', variant: 'error',   icon: AlertTriangle },
};

// ============================================================================
// Mock state
// ============================================================================

let _seq = 0;
function mkKr(title: string, unit: string, target: number, current: number): KeyResult {
  _seq += 1;
  return { id: `kr_${_seq}`, title, unit, target, current };
}

const INITIAL_OBJECTIVES: Objective[] = [
  {
    id: 'obj_1',
    quarter: 'Q2 2026',
    title: 'Tăng doanh thu mảng SME lên 5 tỷ/tháng',
    owner: 'minh@acme.vn',
    krs: [
      mkKr('Số khách SME mới ký HĐ',                'khách', 60, 28),
      mkKr('ARPU SME trung bình',                    'VNĐ',  3_500_000, 2_800_000),
      mkKr('Tỷ lệ giữ chân SME 90 ngày',             '%',    85, 72),
    ],
  },
  {
    id: 'obj_2',
    quarter: 'Q2 2026',
    title: 'Giảm churn APAC xuống dưới 5%',
    owner: 'lan@acme.vn',
    krs: [
      mkKr('Churn rate APAC',                        '%',    5, 8.2),  // inverted — current high = bad
      mkKr('NPS APAC',                                'điểm', 50, 38),
      mkKr('Tỷ lệ phản hồi survey',                  '%',    60, 41),
    ],
  },
  {
    id: 'obj_3',
    quarter: 'Q2 2026',
    title: 'Triển khai Auto DB cho 3 khách hàng pilot',
    owner: 'huy@acme.vn',
    krs: [
      mkKr('Số khách pilot đã go-live',              'khách', 3, 1),
      mkKr('Schema accuracy đề xuất',                '%',    85, 78),
      mkKr('Số form sinh tự động',                    'form', 30, 12),
    ],
  },
];

// ============================================================================
// Page
// ============================================================================

export default function OkrPage() {
  const [objectives, setObjectives] = useState<Objective[]>(INITIAL_OBJECTIVES);
  const [selectedId, setSelectedId] = useState<string | null>(INITIAL_OBJECTIVES[0]?.id ?? null);
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const selected = useMemo(
    () => objectives.find((o) => o.id === selectedId) ?? null,
    [objectives, selectedId],
  );

  function patchObjective(id: string, patch: Partial<Objective>) {
    setObjectives((prev) => prev.map((o) => (o.id === id ? { ...o, ...patch } : o)));
  }

  function patchKr(objId: string, krId: string, patch: Partial<KeyResult>) {
    setObjectives((prev) => prev.map((o) => o.id !== objId ? o : {
      ...o,
      krs: o.krs.map((k) => k.id === krId ? { ...k, ...patch } : k),
    }));
  }

  function addObjective() {
    const id = `obj_${Date.now()}`;
    const obj: Objective = {
      id, quarter: 'Q2 2026', title: 'Objective mới', owner: '',
      krs: [
        mkKr('Key Result 1', '%', 100, 0),
        mkKr('Key Result 2', '%', 100, 0),
        mkKr('Key Result 3', '%', 100, 0),
      ],
    };
    setObjectives((prev) => [...prev, obj]);
    setSelectedId(id);
  }

  function deleteObjective(id: string) {
    setObjectives((prev) => prev.filter((o) => o.id !== id));
    if (selectedId === id) setSelectedId(null);
  }

  async function onSave() {
    if (!selected) return;
    setSubmitting(true);
    setProblem(null);
    setSuccess(null);
    try {
      await api(`/api/v1/strategy/okr/${selected.id}`, {
        method: 'PUT',
        body: JSON.stringify(selected),
      });
      setSuccess('Đã lưu OKR.');
    } catch (e: any) {
      setProblem(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="OKR"
        description="Mỗi Objective gồm tối đa 3 Key Result đo lường được. Cập nhật current value hàng tuần."
        actions={
          <>
            <Badge variant="info">Phase 2 · F-054</Badge>
            <a href="/p2/strategy"><Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Tổng quan</Button></a>
            <Button variant="primary" size="md" onClick={addObjective}>
              <Plus className="w-4 h-4 mr-2" /> Thêm OKR
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}
        {success && <SuccessBanner message={success} />}

        <div className="grid grid-cols-1 xl:grid-cols-[420px_1fr] gap-4">
          {/* Left: list */}
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
              <Calendar className="w-4 h-4 text-[var(--primary-gold-dark)]" />
              <span>Q2 2026 · {Math.round(Q2_PROGRESS * 100)}% thời gian đã trôi qua</span>
            </div>
            {objectives.map((o) => (
              <ObjectiveListItem
                key={o.id}
                obj={o}
                active={o.id === selectedId}
                onSelect={() => setSelectedId(o.id)}
              />
            ))}
            {objectives.length === 0 && (
              <div className="bg-[var(--bg-card)] border border-[var(--border-color)] border-dashed rounded-lg-custom py-8 text-center">
                <Target className="w-10 h-10 mx-auto text-[var(--text-secondary)]/40 mb-2" />
                <p className="text-sm text-[var(--text-secondary)]">Chưa có OKR cho quý này.</p>
              </div>
            )}
          </div>

          {/* Right: editor */}
          {selected ? (
            <ObjectiveEditor
              obj={selected}
              onPatch={(patch) => patchObjective(selected.id, patch)}
              onPatchKr={(krId, patch) => patchKr(selected.id, krId, patch)}
              onDelete={() => deleteObjective(selected.id)}
              onSave={onSave}
              saving={submitting}
            />
          ) : (
            <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-12 text-center">
              <Target className="w-12 h-12 mx-auto text-[var(--text-secondary)]/30 mb-3" />
              <p className="text-sm text-[var(--text-secondary)]">Chọn 1 OKR ở cột trái để chỉnh.</p>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Status auto-tính từ progress trung bình KR vs % thời gian quý đã trôi qua. Mỗi lần update KR ghi
            <span className="font-mono"> decision_audit_log</span> (K-6).
          </p>
        </div>
      </div>
    </>
  );
}

// ============================================================================
// Sub-components
// ============================================================================

function ObjectiveListItem({
  obj, active, onSelect,
}: { obj: Objective; active: boolean; onSelect: () => void }) {
  const status = objStatus(obj);
  const meta = STATUS_META[status];
  const StatusIcon = meta.icon;
  const pct = objProgress(obj);

  return (
    <button
      onClick={onSelect}
      className={cn(
        'w-full text-left p-4 rounded-lg-custom border transition-all shadow-soft-sm',
        active
          ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/8'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
      )}
    >
      <div className="flex items-start justify-between gap-2 mb-2">
        <h3 className="font-serif text-sm text-[var(--text-primary)] leading-snug line-clamp-2">{obj.title}</h3>
        <Badge variant={meta.variant}>
          <StatusIcon className="w-3 h-3 mr-1" /> {meta.label}
        </Badge>
      </div>
      <div className="space-y-1">
        <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)]">
          <span>{obj.krs.length} KR · {obj.owner || 'chưa gán chủ'}</span>
          <span className="font-medium text-[var(--text-primary)]">{pct}%</span>
        </div>
        <div className="h-1.5 w-full rounded-sm-custom bg-[var(--border-color)]/40 overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-500',
              status === 'on_track'  ? 'bg-[var(--state-success)]'
              : status === 'at_risk' ? 'bg-[var(--state-warning)]'
              : 'bg-[var(--state-error)]',
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </button>
  );
}

function ObjectiveEditor({
  obj, onPatch, onPatchKr, onDelete, onSave, saving,
}: {
  obj:       Objective;
  onPatch:   (patch: Partial<Objective>) => void;
  onPatchKr: (krId: string, patch: Partial<KeyResult>) => void;
  onDelete:  () => void;
  onSave:    () => void;
  saving:    boolean;
}) {
  const status = objStatus(obj);
  const meta = STATUS_META[status];
  const StatusIcon = meta.icon;
  const pct = objProgress(obj);

  return (
    <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-5 lg:p-6 shadow-soft-sm space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 pb-4 border-b border-[var(--border-color)]/60">
        <div className="flex-1 min-w-0">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Objective · {obj.quarter}</p>
          <input
            value={obj.title}
            onChange={(e) => onPatch({ title: e.target.value })}
            className="w-full font-serif text-xl text-[var(--text-primary)] bg-transparent border-0 focus:outline-none focus:ring-0 px-0"
          />
        </div>
        <Badge variant={meta.variant}>
          <StatusIcon className="w-3 h-3 mr-1" /> {meta.label} · {pct}%
        </Badge>
      </div>

      {/* Owner */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input
          label="Chủ Objective"
          value={obj.owner}
          onChange={(e) => onPatch({ owner: e.target.value })}
          placeholder="email@workspace.vn"
        />
        <Input
          label="Quý"
          value={obj.quarter}
          onChange={(e) => onPatch({ quarter: e.target.value })}
          placeholder="VD: Q2 2026"
        />
      </div>

      {/* KRs */}
      <div className="space-y-3">
        <p className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-2">
          <Target className="w-4 h-4 text-[var(--primary-gold-dark)]" /> Key Results ({obj.krs.length})
        </p>
        {obj.krs.map((kr, i) => <KrEditor key={kr.id} kr={kr} index={i} onPatch={(p) => onPatchKr(kr.id, p)} />)}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between pt-4 border-t border-[var(--border-color)]/60">
        <Button variant="tertiary" size="sm" onClick={onDelete}>
          <Trash2 className="w-4 h-4 mr-2" /> Xoá OKR
        </Button>
        <Button variant="primary" size="md" onClick={onSave} isLoading={saving}>
          <Save className="w-4 h-4 mr-2" /> Lưu
        </Button>
      </div>
    </div>
  );
}

function KrEditor({
  kr, index, onPatch,
}: { kr: KeyResult; index: number; onPatch: (patch: Partial<KeyResult>) => void }) {
  const pct = progressPct(kr);
  return (
    <div className="bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom p-4 space-y-3">
      <div className="flex items-center gap-2">
        <span className="w-6 h-6 rounded-full bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center text-[10px] font-semibold text-[var(--primary-gold-dark)]">
          KR{index + 1}
        </span>
        <input
          value={kr.title}
          onChange={(e) => onPatch({ title: e.target.value })}
          className="flex-1 text-sm font-medium text-[var(--text-primary)] bg-transparent border-0 focus:outline-none focus:ring-0 px-0"
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        <Input
          label="Hiện tại"
          type="number"
          value={kr.current}
          onChange={(e) => onPatch({ current: Number(e.target.value) })}
        />
        <Input
          label="Mục tiêu"
          type="number"
          value={kr.target}
          onChange={(e) => onPatch({ target: Number(e.target.value) })}
        />
        <Input
          label="Đơn vị"
          value={kr.unit}
          onChange={(e) => onPatch({ unit: e.target.value })}
          placeholder="% / VNĐ / khách"
        />
      </div>
      <div>
        <div className="flex items-center justify-between text-[11px] text-[var(--text-secondary)] mb-1">
          <span>{kr.current.toLocaleString('vi-VN')} / {kr.target.toLocaleString('vi-VN')} {kr.unit}</span>
          <span className="font-medium text-[var(--text-primary)]">{pct}%</span>
        </div>
        <div className="h-1.5 w-full rounded-sm-custom bg-[var(--border-color)]/60 overflow-hidden">
          <div
            className={cn(
              'h-full transition-all duration-500',
              pct >= 75 ? 'bg-[var(--state-success)]' : pct >= 40 ? 'bg-[var(--primary-gold)]' : 'bg-[var(--state-error)]',
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>
    </div>
  );
}
