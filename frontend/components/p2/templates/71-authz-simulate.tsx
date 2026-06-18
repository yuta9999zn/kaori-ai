// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 71. /p2/authz/abac/simulate — ABAC Policy Simulator (Phase 2 🔵)
// ----------------------------------------------------------------------------
// Test policy bằng synthetic subject + resource. Trả về:
//   { allow, reason, policy_id, missing_perms[] }   (CLAUDE.md §9)
//
// Phase 1: RBAC enforcement only. Simulator scaffold để test policy trước
// khi go-live trong Phase 2.
// ============================================================================

import React, { useState } from 'react';
import {
  ChevronLeft, Activity, User, Database, ArrowRight, ShieldCheck,
  CheckCircle2, Ban, AlertTriangle, Sparkles,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
interface SimulateRequest {
  subject:  Record<string, string>;
  resource: Record<string, string>;
  action:   'read' | 'write' | 'export' | 'decide';
}

interface PdpDecision {
  allow:          boolean;
  reason:         string;
  policy_id:      string | null;
  missing_perms:  string[];
  matched_rules:  Array<{ id: string; name: string; effect: 'ALLOW' | 'DENY' }>;
}

const PRESETS: Array<{ label: string; req: SimulateRequest }> = [
  {
    label: 'VIEWER đọc Gold revenue',
    req: {
      subject:  { role: 'VIEWER', department: 'sales' },
      resource: { table: 'gold_revenue', sensitivity: 'internal' },
      action:   'read',
    },
  },
  {
    label: 'OPERATOR export PII',
    req: {
      subject:  { role: 'OPERATOR', department: 'ops', mfa_state: 'enabled' },
      resource: { table: 'silver_customers', sensitivity: 'pii' },
      action:   'export',
    },
  },
  {
    label: 'ANALYST mark is_actioned',
    req: {
      subject:  { role: 'ANALYST', department: 'finance' },
      resource: { table: 'decisions', sensitivity: 'internal' },
      action:   'decide',
    },
  },
];

export default function AbacSimulatePage() {
  const [req, setReq] = useState<SimulateRequest>(PRESETS[0].req);
  const [decision, setDecision] = useState<PdpDecision | null>(null);
  const [running, setRunning] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  async function run() {
    setRunning(true);
    setProblem(null);
    try {
      const r = await api<PdpDecision>('/api/v2/enterprise/authz/abac/simulate', {
        method: 'POST',
        body:   JSON.stringify(req),
      });
      setDecision(r);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setRunning(false);
    }
  }

  function setSubject(key: string, value: string) {
    setReq({ ...req, subject: { ...req.subject, [key]: value } });
  }
  function setResource(key: string, value: string) {
    setReq({ ...req, resource: { ...req.resource, [key]: value } });
  }

  return (
    <>
      <PageHeader
        title="ABAC Simulator"
        description="Test chính sách bằng cặp subject + resource giả. Không gây side-effect lên dữ liệu thật."
        actions={
          <>
            <Badge variant="info">Phase 2</Badge>
            <Button variant="tertiary" onClick={() => (window.location.href = '/p2/authz/abac/builder')}>
              <ChevronLeft className="w-4 h-4 mr-1" />
              Builder
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1100px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />

        {/* Presets */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-4 shadow-soft-sm">
          <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-2">Tình huống mẫu</p>
          <div className="flex flex-wrap gap-2">
            {PRESETS.map((p) => (
              <button
                key={p.label}
                type="button"
                onClick={() => setReq(p.req)}
                className="px-3 py-1.5 rounded-sm-custom border border-[var(--border-color)] bg-[var(--bg-card)] text-xs text-[var(--text-primary)] hover:border-[var(--primary-gold)]/50 hover:bg-[var(--primary-gold)]/5"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {/* Subject + resource form */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <FormPanel title="Subject" icon={User}>
            <Field label="Role"        value={req.subject.role ?? ''}        onChange={(v) => setSubject('role', v)} placeholder="MANAGER / OPERATOR / ANALYST / VIEWER" />
            <Field label="Department"  value={req.subject.department ?? ''}  onChange={(v) => setSubject('department', v)} placeholder="sales / marketing / ops / finance" />
            <Field label="Location"    value={req.subject.location ?? ''}    onChange={(v) => setSubject('location', v)} placeholder="HCM / HN / DN" />
            <Field label="MFA"          value={req.subject.mfa_state ?? ''}  onChange={(v) => setSubject('mfa_state', v)} placeholder="enabled / disabled" />
          </FormPanel>

          <FormPanel title="Resource" icon={Database}>
            <Field label="Table"        value={req.resource.table ?? ''}        onChange={(v) => setResource('table', v)} placeholder="gold_revenue / silver_orders..." />
            <Field label="Sensitivity"  value={req.resource.sensitivity ?? ''}  onChange={(v) => setResource('sensitivity', v)} placeholder="public / internal / confidential / pii" />
            <Field label="Owner team"   value={req.resource.owner_team ?? ''}    onChange={(v) => setResource('owner_team', v)} placeholder="finance / sales / shared" />

            <div>
              <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">Action</label>
              <select
                value={req.action}
                onChange={(e) => setReq({ ...req, action: e.target.value as SimulateRequest['action'] })}
                className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                <option value="read">read</option>
                <option value="write">write</option>
                <option value="export">export</option>
                <option value="decide">decide</option>
              </select>
            </div>
          </FormPanel>
        </div>

        {/* Run button */}
        <div className="flex justify-center">
          <Button onClick={run} isLoading={running} disabled title="Phase 2 — Sắp ra mắt">
            <Activity className="w-4 h-4 mr-2" />
            Chạy mô phỏng
            <ArrowRight className="w-4 h-4 ml-2" />
          </Button>
        </div>

        {/* Decision panel */}
        <div className={cn(
          'rounded-lg-custom border-2 p-5 shadow-soft-sm transition-colors',
          decision?.allow === true  ? 'border-[var(--state-success)]/40 bg-[var(--state-success)]/5'
          : decision?.allow === false ? 'border-[var(--state-error)]/40 bg-[var(--state-error)]/5'
          : 'border-[var(--border-color)] bg-[var(--bg-card)]',
        )}>
          {decision ? (
            <>
              <div className="flex items-center gap-3 mb-3">
                {decision.allow ? <CheckCircle2 className="w-6 h-6 text-[var(--state-success)]" /> : <Ban className="w-6 h-6 text-[var(--state-error)]" />}
                <div>
                  <h3 className={cn('font-serif text-lg', decision.allow ? 'text-[#5C856A]' : 'text-[#9B5050]')}>
                    {decision.allow ? 'ALLOW' : 'DENY'}
                  </h3>
                  <p className="text-xs text-[var(--text-secondary)]">PDP decision</p>
                </div>
              </div>
              <p className="text-sm text-[var(--text-primary)] leading-relaxed">{decision.reason}</p>
              {decision.policy_id && (
                <p className="text-[11px] text-[var(--text-secondary)] mt-2">
                  Policy ID: <span className="font-mono">{decision.policy_id}</span>
                </p>
              )}
              {decision.missing_perms.length > 0 && (
                <div className="mt-3">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Quyền thiếu</p>
                  <div className="flex flex-wrap gap-1">
                    {decision.missing_perms.map((p) => (
                      <span key={p} className="font-mono text-[10px] px-2 py-0.5 rounded-sm-custom bg-[var(--state-error)]/10 text-[#9B5050] border border-[var(--state-error)]/30">{p}</span>
                    ))}
                  </div>
                </div>
              )}
              {decision.matched_rules.length > 0 && (
                <div className="mt-3">
                  <p className="text-[11px] uppercase tracking-wider text-[var(--text-secondary)] mb-1">Rule matched</p>
                  <ul className="space-y-1">
                    {decision.matched_rules.map((r) => (
                      <li key={r.id} className="flex items-center gap-2 text-xs">
                        <Badge variant={r.effect === 'ALLOW' ? 'success' : 'error'}>{r.effect}</Badge>
                        <span className="text-[var(--text-primary)]">{r.name}</span>
                        <span className="font-mono text-[10px] text-[var(--text-secondary)]">{r.id}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-6 text-[var(--text-secondary)]">
              <Sparkles className="w-8 h-8 mx-auto mb-2 text-[var(--primary-gold-dark)]" />
              <p className="text-sm">Điền thông tin và chạy mô phỏng để xem decision.</p>
            </div>
          )}
        </div>

        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            Simulator KHÔNG ghi vào dữ liệu thật. DENY luôn override ALLOW. Trong Hybrid PDP (Phase 2), RBAC chạy trước
            ABAC — nếu RBAC đã DENY thì ABAC không được gọi.
          </p>
        </div>
      </div>
    </>
  );
}

function FormPanel({
  title, icon: Icon, children,
}: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-[var(--border-color)]/60 bg-[var(--bg-app)]/40 flex items-center gap-2">
        <Icon className="w-4 h-4 text-[var(--primary-gold-dark)]" />
        <h4 className="font-serif text-sm text-[var(--text-primary)]">{title}</h4>
      </div>
      <div className="p-4 space-y-3">{children}</div>
    </div>
  );
}

function Field({
  label, value, onChange, placeholder,
}: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-[var(--text-secondary)] uppercase tracking-wider">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1 w-full px-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
      />
    </div>
  );
}
