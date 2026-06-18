// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-37 — Churn Save Workspace
// ----------------------------------------------------------------------------
// Phase 2.8 NEW. Maps to workflow D.5 Churn Save. Integrates Adoption
// Intelligence (EPIC-13) signals + NOV impact estimate.
//
// Route:        /p2/cs/churn-save
// Permission:   OPERATOR+ với claim `run_churn_save_action` (auto-grant dept=CS).
// URD US-ID:    US-CS-5
// BE routes:
//   GET  /api/v1/cs/churn-portfolio?risk=&plan=                    (kanban data)
//   GET  /api/v1/cs/playbooks                                      (intervention templates)
//   POST /api/v1/cs/churn-save/run-action  body { customer_id, playbook_id, custom_message? }
//   POST /api/v1/cs/churn-save/assign-to-ae body { customer_id, ae_id, urgency }
//   GET  /api/v1/cs/churn-save/intervention-history?customer_id=
//   GET  /api/v1/cs/churn-save/effectiveness-summary?from=&to=
//   GET  /api/v1/adoption/signals?customer_id=                     (EPIC-13)
// ============================================================================

import React, { useState } from 'react';
import { TrendingDown, Zap, UserCheck, Activity, AlertCircle } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

// ─── Types ───────────────────────────────────────────────────────────

type RiskTier = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';

interface ChurnPortfolioCustomer {
  customer_id:          string;
  name:                 string;
  risk_tier:            RiskTier;
  risk_score:           number;            // 0..1
  primary_risk_factor:  string;            // AI SHAP top-1: "Usage drop 60% in last 14d"
  nov_at_risk_vnd:      number;            // estimated NOV at risk
  suggested_playbook:   string;            // playbook_id
  in_flight_action:     string | null;     // 'discount' | 'training' | ...
  plan:                 string;            // tenant pricing plan
}

interface Playbook {
  playbook_id:   string;
  name:          string;
  archetype:     string;                  // 'low-usage' | 'pricing-pushback' | ...
  description:   string;
}

// ─── Page component ──────────────────────────────────────────────────

export default function ChurnSavePage() {
  const [planFilter, setPlanFilter] = useState<string>('');
  const [selectedCustomer, setSelectedCustomer] = useState<ChurnPortfolioCustomer | null>(null);
  const [playbookDrawerOpen, setPlaybookDrawerOpen] = useState(false);

  // TODO P2-37-DATA: useQuery(['churn-portfolio', filters], poll 5m)
  const customers: ChurnPortfolioCustomer[] = [];
  const playbooks: Playbook[] = [];
  const isLoading = false;
  const error: ProblemDetails | null = null;

  if (error) return <ErrorBanner message={error.detail ?? 'Không tải được portfolio.'} />;

  const byTier = (tier: RiskTier) => customers.filter(c => c.risk_tier === tier);

  return (
    <div className="space-y-4">
      <PageHeader
        title="Churn Save Workspace"
        subtitle="Kanban khách hàng theo risk tier · NOV impact · playbook gợi ý."
      />

      {/* Portfolio filters */}
      <div className="flex items-center gap-3 rounded-lg border bg-white px-4 py-3">
        <select className="bg-transparent text-sm outline-none" value={planFilter} onChange={(e) => setPlanFilter(e.target.value)}>
          <option value="">Tất cả plan</option>
          <option value="PILOT">PILOT</option>
          <option value="ENT_BASIC">ENT BASIC</option>
          <option value="ENT_MID">ENT MID</option>
          <option value="ENT_MAX">ENT MAX</option>
        </select>
        <div className="flex-1" />
        <Badge variant="outline">
          NOV at risk: {customers.reduce((sum, c) => sum + c.nov_at_risk_vnd, 0).toLocaleString('vi-VN')}₫
        </Badge>
      </div>

      {/* Kanban */}
      {isLoading ? (
        <div className="h-96 animate-pulse rounded bg-gray-100" />
      ) : customers.length === 0 ? (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          <UserCheck className="mx-auto size-8 text-green-500" />
          <div className="mt-2">Portfolio sạch — 0 khách HIGH risk 🎉.</div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <RiskColumn tier="CRITICAL" customers={byTier('CRITICAL')} onSelect={setSelectedCustomer} />
          <RiskColumn tier="HIGH"     customers={byTier('HIGH')}     onSelect={setSelectedCustomer} />
          <RiskColumn tier="MEDIUM"   customers={byTier('MEDIUM')}   onSelect={setSelectedCustomer} />
          <RiskColumn tier="LOW"      customers={byTier('LOW')}      onSelect={setSelectedCustomer} />
        </div>
      )}

      {/* Effectiveness summary */}
      <div className="rounded-lg border bg-white p-4">
        <div className="flex items-center gap-2 font-medium">
          <Activity className="size-4" /> Hiệu quả intervention (30d)
        </div>
        <div className="mt-2 text-sm text-muted-foreground">Tính năng đang hoàn thiện</div>
        {/* TODO low effectiveness warning: yellow banner if <20% recovery */}
      </div>

      {/* Intervention history side panel */}
      {selectedCustomer && (
        <CustomerActionDrawer
          customer={selectedCustomer}
          playbooks={playbooks}
          onClose={() => setSelectedCustomer(null)}
          onOpenPlaybook={() => setPlaybookDrawerOpen(true)}
        />
      )}

      {/* Playbook drawer */}
      {playbookDrawerOpen && (
        <PlaybookDrawer playbooks={playbooks} onClose={() => setPlaybookDrawerOpen(false)} />
      )}
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function RiskColumn({ tier, customers, onSelect }: { tier: RiskTier; customers: ChurnPortfolioCustomer[]; onSelect: (c: ChurnPortfolioCustomer) => void }) {
  const config = {
    CRITICAL: { label: 'Critical', cls: 'border-red-300 bg-red-50' },
    HIGH:     { label: 'High',     cls: 'border-orange-300 bg-orange-50' },
    MEDIUM:   { label: 'Medium',   cls: 'border-yellow-200 bg-yellow-50' },
    LOW:      { label: 'Low',      cls: 'border-blue-200 bg-blue-50' },
  }[tier];
  return (
    <div className={cn('rounded-lg border p-3', config.cls)}>
      <div className="mb-3 flex items-center justify-between">
        <span className="font-medium">{config.label}</span>
        <Badge variant="outline">{customers.length}</Badge>
      </div>
      <div className="space-y-2">
        {customers.length === 0 ? (
          <div className="text-xs text-muted-foreground">Không có khách.</div>
        ) : (
          customers.map(c => (
            <button
              key={c.customer_id}
              onClick={() => onSelect(c)}
              className="w-full rounded border bg-white p-3 text-left text-sm hover:border-primary-gold"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium truncate">{c.name}</span>
                <Badge variant="outline">{c.plan}</Badge>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                <TrendingDown className="inline size-3" /> {c.primary_risk_factor}
              </div>
              <div className="mt-1 text-xs">
                NOV at risk: <strong>{c.nov_at_risk_vnd.toLocaleString('vi-VN')}₫</strong>
              </div>
              {c.in_flight_action && (
                <div className="mt-1 inline-block rounded bg-purple-100 px-2 py-0.5 text-xs text-purple-700">
                  Đang chạy: {c.in_flight_action}
                </div>
              )}
            </button>
          ))
        )}
      </div>
    </div>
  );
}

function CustomerActionDrawer({ customer, playbooks, onClose, onOpenPlaybook }: {
  customer: ChurnPortfolioCustomer; playbooks: Playbook[];
  onClose: () => void; onOpenPlaybook: () => void;
}) {
  void playbooks;
  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-lg border-l bg-white shadow-lg overflow-y-auto">
      <div className="flex items-center justify-between border-b px-6 py-4">
        <h2 className="text-lg font-medium">{customer.name}</h2>
        <Button variant="ghost" onClick={onClose}>Đóng</Button>
      </div>
      <div className="space-y-4 px-6 py-4">
        <div className="rounded border bg-gray-50 p-3 text-sm">
          <div className="text-xs uppercase text-muted-foreground">Risk factor (SHAP top-1)</div>
          <div className="mt-1">{customer.primary_risk_factor}</div>
          <div className="mt-3 text-xs uppercase text-muted-foreground">NOV at risk</div>
          <div className="mt-1 text-lg font-medium">{customer.nov_at_risk_vnd.toLocaleString('vi-VN')}₫</div>
        </div>
        <div>
          <div className="font-medium">Adoption signals (EPIC-13)</div>
          <div className="mt-2 rounded border bg-gray-50 p-3 text-sm text-muted-foreground">
            Tính năng đang hoàn thiện
          </div>
        </div>
        <div>
          <div className="font-medium">Intervention history</div>
          <div className="mt-2 rounded border bg-gray-50 p-3 text-sm text-muted-foreground">
            Tính năng đang hoàn thiện
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t pt-4">
          {/* TODO P2-37-PERM: gate Run on claim run_churn_save_action */}
          <Button variant="ghost"><UserCheck className="size-4" /> Assign AE</Button>
          <Button onClick={onOpenPlaybook}><Zap className="size-4" /> Run playbook</Button>
        </div>
      </div>
    </div>
  );
}

function PlaybookDrawer({ playbooks, onClose }: { playbooks: Playbook[]; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="w-full max-w-2xl rounded-lg bg-white p-6 shadow-lg">
        <div className="flex items-center justify-between border-b pb-3">
          <h3 className="text-lg font-medium">Chọn playbook</h3>
          <Button variant="ghost" onClick={onClose}>Đóng</Button>
        </div>
        <div className="mt-4 space-y-2">
          {playbooks.length === 0 ? (
            <div className="text-sm text-muted-foreground">Chưa có playbook — định nghĩa trong P2-37 setup.</div>
          ) : (
            playbooks.map(p => (
              <div key={p.playbook_id} className="rounded border p-3 text-sm">
                <div className="font-medium">{p.name}</div>
                <div className="text-xs text-muted-foreground">{p.archetype}</div>
                <div className="mt-1 text-muted-foreground">{p.description}</div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
