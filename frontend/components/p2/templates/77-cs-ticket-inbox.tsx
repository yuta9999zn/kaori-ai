// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-33 — CS Ticket Inbox & Triage
// ----------------------------------------------------------------------------
// Phase 2.8 NEW (Round 3, baseline 2026-05-21). Customer Service vertical.
// Maps to workflow D.1 Ticket Triage (feature-workflows.html § Vertical D).
//
// Route:        /p2/cs/inbox
// Permission:   OPERATOR+ với claim `triage_cs_tickets` (auto-grant dept=CS).
// URD US-ID:    US-CS-1 (URD v2.1 §3 UR-CS)
// BE routes:
//   GET  /api/v1/cs/tickets?status=&priority=&channel=&assignee=&sla=  (paginated)
//   POST /api/v1/cs/tickets/{id}/assign  body { assignee_id }
//   POST /api/v1/cs/tickets/{id}/snooze  body { snooze_until }
//   POST /api/v1/cs/tickets/{id}/resolve body { resolution_note }
//   POST /api/v1/cs/tickets/{id}/escalate body { escalation_reason, to_role }
//   POST /api/v1/cs/tickets/bulk-action  body { ticket_ids[], action, params }
//   POST /api/v1/cs/tickets              body { channel, customer_id, subject, body, priority? }
//   GET  /api/v1/cs/saved-views?user_id=
//   POST /api/v1/cs/saved-views
// ============================================================================

import React, { useState } from 'react';
import { Inbox, Filter, Mail, Phone, MessageSquare, Globe, Clock, AlertCircle } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

// ─── Types mirror BE shapes ──────────────────────────────────────────

type TicketChannel = 'email' | 'zalo' | 'web' | 'phone';
type TicketPriority = 'low' | 'normal' | 'high' | 'urgent';
type TicketStatus = 'open' | 'pending' | 'resolved' | 'closed';

interface Ticket {
  ticket_id:        string;
  subject:          string;
  channel:          TicketChannel;
  priority:         TicketPriority;
  status:           TicketStatus;
  assignee_user_id: string | null;
  assignee_name:    string | null;
  customer_id:      string;
  customer_name:    string;
  sla_breach_at:    string | null;       // ISO; computed for countdown
  created_at:       string;
}

interface SavedView {
  view_id: string;
  name:    string;
  filters: Record<string, string>;
}

// ─── Page component ──────────────────────────────────────────────────

export default function CsTicketInboxPage() {
  const [activeView, setActiveView] = useState<string>('my-queue');
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());

  // TODO P2-33-DATA: useQuery(['cs-tickets', filters], poll 30s)
  const tickets: Ticket[] = [];
  const isLoading = false;
  const error: ProblemDetails | null = null;

  // TODO P2-33-DATA: useQuery(['cs-saved-views', userId])
  const savedViews: SavedView[] = [
    { view_id: 'my-queue', name: 'My queue', filters: { assignee: 'me' } },
    { view_id: 'unassigned', name: 'Unassigned', filters: { assignee: 'none' } },
    { view_id: 'high', name: 'High priority', filters: { priority: 'high' } },
    { view_id: 'sla-risk', name: 'SLA breach risk', filters: { sla: 'risk' } },
  ];

  // TODO P2-33-PERM: hide quick actions for VIEWER; enable bulk only for MANAGER+.
  // TODO P2-33-PERM: empty state cho user thiếu claim triage_cs_tickets.

  return (
    <div className="space-y-4">
      <PageHeader
        title="CS Ticket Inbox"
        subtitle="Triage tickets từ mọi kênh — email · Zalo · web form · phone log."
      />

      {/* Saved views switcher */}
      <div className="flex items-center gap-2 overflow-x-auto">
        {savedViews.map(v => (
          <button
            key={v.view_id}
            onClick={() => { setActiveView(v.view_id); setFilters(v.filters); }}
            className={cn(
              'rounded-full border px-3 py-1 text-sm whitespace-nowrap',
              activeView === v.view_id ? 'bg-primary-gold/10 border-primary-gold' : 'bg-white'
            )}
          >
            {v.name}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-3 rounded-lg border bg-white px-4 py-3">
        <Filter className="size-4 text-muted-foreground" />
        <select className="bg-transparent text-sm outline-none">
          <option value="">Tất cả status</option>
          <option value="open">Open</option>
          <option value="pending">Pending</option>
          <option value="resolved">Resolved</option>
        </select>
        <select className="bg-transparent text-sm outline-none">
          <option value="">Tất cả priority</option>
          <option value="urgent">Urgent</option>
          <option value="high">High</option>
        </select>
        <select className="bg-transparent text-sm outline-none">
          <option value="">Tất cả channel</option>
          <option value="email">Email</option>
          <option value="zalo">Zalo</option>
          <option value="web">Web form</option>
          <option value="phone">Phone log</option>
        </select>
        <div className="flex-1" />
        <Button>+ Ticket mới</Button>
      </div>

      {/* Bulk action toolbar */}
      {selectedRows.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-primary-gold bg-primary-gold/5 px-4 py-2 text-sm">
          <span>{selectedRows.size} ticket đã chọn</span>
          <div className="flex gap-2">
            <Button size="sm" variant="ghost">Assign</Button>
            <Button size="sm" variant="ghost">Snooze</Button>
            <Button size="sm" variant="ghost">Resolve</Button>
            <Button size="sm" variant="ghost">Escalate</Button>
          </div>
        </div>
      )}

      {/* Ticket table */}
      {error && <ErrorBanner message={error.detail ?? 'Không tải được tickets.'} />}
      {isLoading && (
        <div className="space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="h-12 animate-pulse rounded bg-gray-100" />
          ))}
        </div>
      )}
      {!isLoading && tickets.length === 0 && (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          <Inbox className="mx-auto size-8" />
          <div className="mt-2">Inbox sạch — chưa có ticket nào.</div>
          <div className="mt-1 text-xs">Tháng này resolved 0 tickets.</div>
        </div>
      )}
      {!isLoading && tickets.length > 0 && (
        <div className="rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2"><input type="checkbox" /></th>
                <th className="px-4 py-2">Channel</th>
                <th className="px-4 py-2">Priority</th>
                <th className="px-4 py-2">Subject</th>
                <th className="px-4 py-2">Customer</th>
                <th className="px-4 py-2">Assignee</th>
                <th className="px-4 py-2">SLA</th>
                <th className="px-4 py-2"></th>
              </tr>
            </thead>
            <tbody>
              {tickets.map(t => <TicketRow key={t.ticket_id} ticket={t} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function TicketRow({ ticket }: { ticket: Ticket }) {
  const slaBreachImminent = ticket.sla_breach_at &&
    new Date(ticket.sla_breach_at).getTime() - Date.now() < 2 * 60 * 60 * 1000;  // < 2h

  const ChannelIcon = { email: Mail, zalo: MessageSquare, web: Globe, phone: Phone }[ticket.channel];
  return (
    <tr className={cn('border-b hover:bg-gray-50', slaBreachImminent && 'bg-red-50 hover:bg-red-100')}>
      <td className="px-4 py-2"><input type="checkbox" /></td>
      <td className="px-4 py-2"><ChannelIcon className="size-4" /></td>
      <td className="px-4 py-2"><PriorityChip priority={ticket.priority} /></td>
      <td className="px-4 py-2 font-medium">{ticket.subject}</td>
      <td className="px-4 py-2">{ticket.customer_name}</td>
      <td className="px-4 py-2">{ticket.assignee_name ?? <em className="text-muted-foreground">Unassigned</em>}</td>
      <td className="px-4 py-2"><SlaTimer breachAt={ticket.sla_breach_at} /></td>
      <td className="px-4 py-2 text-right">
        <Button size="sm" variant="ghost">⋯</Button>
      </td>
    </tr>
  );
}

function PriorityChip({ priority }: { priority: TicketPriority }) {
  const map: Record<TicketPriority, { label: string; cls: string }> = {
    urgent: { label: 'Urgent', cls: 'bg-red-100 text-red-700' },
    high:   { label: 'High',   cls: 'bg-orange-100 text-orange-700' },
    normal: { label: 'Normal', cls: 'bg-gray-100 text-gray-700' },
    low:    { label: 'Low',    cls: 'bg-blue-50 text-blue-600' },
  };
  return <span className={cn('rounded-full px-2 py-0.5 text-xs', map[priority].cls)}>{map[priority].label}</span>;
}

function SlaTimer({ breachAt }: { breachAt: string | null }) {
  if (!breachAt) return <span className="text-xs text-muted-foreground">—</span>;
  const ms = new Date(breachAt).getTime() - Date.now();
  const hours = Math.max(0, Math.floor(ms / 3_600_000));
  const breaching = ms < 2 * 60 * 60 * 1000;
  return (
    <span className={cn('flex items-center gap-1 text-xs', breaching ? 'text-red-700' : 'text-muted-foreground')}>
      <Clock className="size-3" /> {hours}h
    </span>
  );
}
