// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 70. /p2/authz/abac/builder — ABAC Policy Builder (Phase 2 🔵)
// ----------------------------------------------------------------------------
// Phase 2 — Hybrid PDP (RBAC + ABAC) trả về:
//   { allow, reason, policy_id, missing_perms[] }   (CLAUDE.md §9)
//
// Builder UI:
//   - Subject attributes  (role, department, location, mfa_state)
//   - Resource attributes (table, sensitivity, owner_team)
//   - Action               (read / write / export / decide)
//   - Effect               (ALLOW / DENY)
//   - Conditions           (time-of-day, ip-range, etc)
//
// Phase 1 only RBAC. Builder shipped as scaffold; enforcement TBD.
// ============================================================================

import React, { useState } from 'react';
import {
  ChevronLeft, Shield, Plus, X, Save, Sparkles, ShieldCheck,
  User, Database, Activity, CheckCircle2, Ban, Clock,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Effect    = 'ALLOW' | 'DENY';
type Action    = 'read' | 'write' | 'export' | 'decide';

interface Condition {
  attribute: string;
  operator:  'equals' | 'not_equals' | 'in' | 'not_in' | 'matches';
  value:     string;
}

interface Policy {
  name:               string;
  description:        string;
  effect:             Effect;
  action:             Action;
  subject_conditions: Condition[];
  resource_conditions: Condition[];
}

const SUBJECT_ATTRS = [
  { key: 'role',        label: 'Vai trò',     hint: 'MANAGER / OPERATOR / ANALYST / VIEWER' },
  { key: 'department',  label: 'Phòng ban',   hint: 'sales / marketing / ops / finance' },
  { key: 'location',    label: 'Địa điểm',     hint: 'HCM / HN / DN' },
  { key: 'mfa_state',   label: 'MFA',          hint: 'enabled / disabled' },
];

const RESOURCE_ATTRS = [
  { key: 'table',       label: 'Bảng',         hint: 'gold_revenue, silver_orders...' },
  { key: 'sensitivity', label: 'Độ nhạy',      hint: 'public / internal / confidential / pii' },
  { key: 'owner_team',  label: 'Team sở hữu',  hint: 'finance / sales / shared' },
];

const newCondition = (): Condition => ({ attribute: '', operator: 'equals', value: '' });

export default function AbacBuilderPage() {
  const [policy, setPolicy] = useState<Policy>({
    name:        '',
    description: '',
    effect:      'ALLOW',
    action:      'read',
    subject_conditions:  [newCondition()],
    resource_conditions: [newCondition()],
  });
  const [saving,  setSaving]  = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  function updateSubject(idx: number, patch: Partial<Condition>) {
    setPolicy({ ...policy, subject_conditions: policy.subject_conditions.map((c, i) => i === idx ? { ...c, ...patch } : c) });
  }
  function updateResource(idx: number, patch: Partial<Condition>) {
    setPolicy({ ...policy, resource_conditions: policy.resource_conditions.map((c, i) => i === idx ? { ...c, ...patch } : c) });
  }

  async function save() {
    setSaving(true);
    setProblem(null);
    try {
      await api('/api/v2/enterprise/authz/abac/policies', {
        method: 'POST',
        body:   JSON.stringify(policy),
      });
    } catch (err: any) {
      setProblem(err);
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="ABAC Policy Builder"
        description="Định nghĩa chính sách theo thuộc tính subject × resource × action × condition."
        actions={
          <>
            <Badge variant="info">Phase 2</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/authz/rbac')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              RBAC
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[900px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Phase 2 banner */}
        <div className="bg-[var(--primary-gold)]/8 rounded-lg-custom border border-[var(--primary-gold)]/30 p-4 shadow-soft-sm">
          <div className="flex items-start gap-3">
            <Sparkles className="w-5 h-5 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
            <p className="text-sm text-[var(--text-primary)]">
              Phase 2 — Hybrid PDP. Hiện tại enforcement chỉ RBAC. Policy bạn save ở đây sẽ dry-run trong simulator
              (file 71 <a href="/p2/authz/abac/simulate" className="text-[var(--primary-gold-dark)] underline">/p2/authz/abac/simulate</a>) trước khi đi vào production.
            </p>
          </div>
        </div>

        {/* Metadata */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm space-y-3">
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">Tên policy</label>
            <input
              type="text"
              value={policy.name}
              onChange={(e) => setPolicy({ ...policy, name: e.target.value })}
              placeholder="Ví dụ: Chỉ Finance HCM xem revenue confidential"
              className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">Mô tả ngắn</label>
            <input
              type="text"
              value={policy.description}
              onChange={(e) => setPolicy({ ...policy, description: e.target.value })}
              placeholder="Khi nào áp dụng, vì sao"
              className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
        </div>

        {/* Effect + Action */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-5 shadow-soft-sm grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)] mb-2">Hiệu ứng</p>
            <div className="flex gap-2">
              <EffectButton active={policy.effect === 'ALLOW'} onClick={() => setPolicy({ ...policy, effect: 'ALLOW' })} variant="allow">
                <CheckCircle2 className="w-4 h-4 mr-1.5" />
                ALLOW
              </EffectButton>
              <EffectButton active={policy.effect === 'DENY'} onClick={() => setPolicy({ ...policy, effect: 'DENY' })} variant="deny">
                <Ban className="w-4 h-4 mr-1.5" />
                DENY
              </EffectButton>
            </div>
          </div>
          <div>
            <p className="text-sm font-medium text-[var(--text-primary)] mb-2">Hành động</p>
            <select
              value={policy.action}
              onChange={(e) => setPolicy({ ...policy, action: e.target.value as Action })}
              className="w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            >
              <option value="read">read</option>
              <option value="write">write</option>
              <option value="export">export</option>
              <option value="decide">decide (mark is_actioned)</option>
            </select>
          </div>
        </div>

        {/* Subject conditions */}
        <ConditionPanel
          title="Subject (người gọi)"
          icon={User}
          attrs={SUBJECT_ATTRS}
          conditions={policy.subject_conditions}
          onUpdate={updateSubject}
          onAdd={() => setPolicy({ ...policy, subject_conditions: [...policy.subject_conditions, newCondition()] })}
          onRemove={(idx) => setPolicy({ ...policy, subject_conditions: policy.subject_conditions.filter((_, i) => i !== idx) })}
        />

        {/* Resource conditions */}
        <ConditionPanel
          title="Resource (dữ liệu/đối tượng)"
          icon={Database}
          attrs={RESOURCE_ATTRS}
          conditions={policy.resource_conditions}
          onUpdate={updateResource}
          onAdd={() => setPolicy({ ...policy, resource_conditions: [...policy.resource_conditions, newCondition()] })}
          onRemove={(idx) => setPolicy({ ...policy, resource_conditions: policy.resource_conditions.filter((_, i) => i !== idx) })}
        />

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            <span className="font-medium text-[var(--text-primary)]">DENY luôn override ALLOW</span> trong Hybrid PDP.
            Policy không có condition = áp dụng cho mọi subject/resource.
          </p>
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={() => (window.location.href = '/p2/authz/abac/simulate')} disabled title="Phase 2">
            <Activity className="w-4 h-4 mr-2" />
            Mô phỏng
          </Button>
          <Button onClick={save} isLoading={saving} disabled title="Phase 2 — Sắp ra mắt">
            <Save className="w-4 h-4 mr-2" />
            Lưu policy
          </Button>
        </div>
      </div>
    </>
  );
}

function EffectButton({
  active, onClick, variant, children,
}: { active: boolean; onClick: () => void; variant: 'allow' | 'deny'; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center px-4 py-2 rounded-md-custom border text-sm font-medium transition-colors',
        active
          ? variant === 'allow'
            ? 'border-[var(--state-success)]/50 bg-[var(--state-success)]/10 text-[#5C856A]'
            : 'border-[var(--state-error)]/50 bg-[var(--state-error)]/10 text-[#9B5050]'
          : 'border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]',
      )}
    >
      {children}
    </button>
  );
}

function ConditionPanel({
  title, icon: Icon, attrs, conditions, onUpdate, onAdd, onRemove,
}: {
  title: string;
  icon: any;
  attrs: Array<{ key: string; label: string; hint: string }>;
  conditions: Condition[];
  onUpdate: (idx: number, patch: Partial<Condition>) => void;
  onAdd: () => void;
  onRemove: (idx: number) => void;
}) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-4 border-b border-[var(--border-color)]/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
          <h4 className="font-serif text-sm text-[var(--text-primary)]">{title}</h4>
        </div>
        <Button size="sm" variant="secondary" onClick={onAdd}>
          <Plus className="w-3.5 h-3.5 mr-1" />
          Thêm điều kiện
        </Button>
      </div>
      <div className="p-3 space-y-2">
        {conditions.length === 0 ? (
          <p className="text-xs text-[var(--text-secondary)] italic px-2 py-3">Không có điều kiện — áp dụng cho mọi {title.toLowerCase()}.</p>
        ) : conditions.map((c, idx) => (
          <div key={idx} className="grid grid-cols-12 gap-2 items-center">
            <select
              value={c.attribute}
              onChange={(e) => onUpdate(idx, { attribute: e.target.value })}
              className="col-span-4 px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-sm-custom text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            >
              <option value="">— Thuộc tính —</option>
              {attrs.map((a) => <option key={a.key} value={a.key}>{a.label}</option>)}
            </select>
            <select
              value={c.operator}
              onChange={(e) => onUpdate(idx, { operator: e.target.value as Condition['operator'] })}
              className="col-span-3 px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-sm-custom text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            >
              <option value="equals">=</option>
              <option value="not_equals">≠</option>
              <option value="in">∈</option>
              <option value="not_in">∉</option>
              <option value="matches">matches</option>
            </select>
            <input
              type="text"
              value={c.value}
              onChange={(e) => onUpdate(idx, { value: e.target.value })}
              placeholder="Giá trị"
              className="col-span-4 px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-sm-custom text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
            <button
              type="button"
              onClick={() => onRemove(idx)}
              className="col-span-1 p-1.5 text-[var(--text-secondary)] hover:text-[var(--state-error)] rounded-sm-custom"
              aria-label="Xoá điều kiện"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
