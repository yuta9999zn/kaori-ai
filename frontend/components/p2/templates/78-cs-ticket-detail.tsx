// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-34 — CS Ticket Detail
// ----------------------------------------------------------------------------
// Phase 2.8 NEW. Maps to workflow D.1 + D.2 (Ticket Triage → SLA Escalation).
//
// Route:        /p2/cs/tickets/{id}
// Permission:   OPERATOR+ với claim `triage_cs_tickets`. Reply MANAGER+ approval
//               cho HIGH-risk ticket.
// URD US-ID:    US-CS-2
// BE routes:
//   GET  /api/v1/cs/tickets/{id}                              (full thread)
//   GET  /api/v1/enterprises/{eid}/customers/{cid}/360        (sidebar)
//   POST /api/v1/cs/tickets/{id}/reply         body { body, channel }
//   POST /api/v1/cs/tickets/{id}/ai-draft-reply body { tone }
//   POST /api/v1/cs/tickets/{id}/internal-note  (mig 072)
//   POST /api/v1/cs/tickets/{id}/escalate-to-d2 (triggers D.2 workflow)
//   POST /api/v1/cs/tickets/{id}/link-to-churn-save (→ P2-37)
// ============================================================================

import React, { useState } from 'react';
import { ArrowLeft, AlertTriangle, Wand2, FileText, ExternalLink, Send } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

// ─── Types ───────────────────────────────────────────────────────────

type ChurnRisk = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';

interface TicketFull {
  ticket_id:        string;
  subject:          string;
  channel:          string;
  priority:         string;
  status:           string;
  assignee_name:    string | null;
  sla_breach_at:    string | null;
  customer_id:      string;
  customer_name:    string;
  conversation:     ConversationMessage[];
}

interface ConversationMessage {
  message_id:   string;
  author_type:  'agent' | 'customer' | 'system' | 'ai-summary';
  author_name:  string;
  channel:      string;
  body:         string;
  created_at:   string;
}

interface CustomerSidebar {
  customer_id:        string;
  name:               string;
  lifetime_value_vnd: number;
  churn_risk:         ChurnRisk;
  last_contact_at:    string | null;
  open_ticket_count:  number;
}

// ─── Page component ──────────────────────────────────────────────────

export default function CsTicketDetailPage({ ticketId }: { ticketId: string }) {
  // TODO P2-34-DATA: useQuery(['cs-ticket', ticketId])
  const ticket: TicketFull | null = null;
  // TODO P2-34-DATA: useQuery(['cs-customer-360', customerId])
  const customer: CustomerSidebar | null = null;
  const isLoading = false;
  const error: ProblemDetails | null = null;

  const [composerDraft, setComposerDraft] = useState('');
  const [aiDraftLoading, setAiDraftLoading] = useState(false);

  if (isLoading) return <div className="h-screen animate-pulse rounded bg-gray-100" />;
  if (error) return <ErrorBanner message={error.detail ?? 'Không tải được ticket.'} />;
  if (!ticket) return <div className="rounded border border-dashed p-12 text-center">Ticket không tồn tại hoặc đã xoá.</div>;

  const slaBreachIn2h = ticket.sla_breach_at &&
    new Date(ticket.sla_breach_at).getTime() - Date.now() < 2 * 60 * 60 * 1000;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm"><ArrowLeft className="size-4" /></Button>
        <div className="flex-1">
          <h1 className="text-xl font-medium">{ticket.subject}</h1>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Badge variant="outline">{ticket.priority}</Badge>
            <Badge variant="outline">{ticket.channel}</Badge>
            <span>Assignee: {ticket.assignee_name ?? 'Unassigned'}</span>
          </div>
        </div>
      </div>

      {/* SLA breach banner */}
      {slaBreachIn2h && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 p-4">
          <AlertTriangle className="size-5 text-red-600" />
          <div className="flex-1 text-sm text-red-800">
            SLA breach trong &lt; 2h — cân nhắc escalate D.2 workflow.
          </div>
          <Button size="sm" variant="destructive">Escalate</Button>
        </div>
      )}

      {/* 3-column layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Customer sidebar */}
        <div className="col-span-3">
          <CustomerSidebarPanel customer={customer} />
        </div>

        {/* Conversation thread */}
        <div className="col-span-6 space-y-4">
          <div className="rounded-lg border bg-white">
            <div className="border-b px-4 py-3 font-medium">Conversation</div>
            <div className="space-y-3 px-4 py-3">
              {ticket.conversation.length === 0 ? (
                <div className="text-sm text-muted-foreground">Chưa có tin nhắn.</div>
              ) : (
                ticket.conversation.map(m => <MessageBubble key={m.message_id} message={m} />)
              )}
            </div>
          </div>

          {/* Reply composer */}
          <div className="rounded-lg border bg-white p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">Trả lời</span>
              <div className="flex items-center gap-2">
                <Button size="sm" variant="ghost" disabled={aiDraftLoading}
                  onClick={() => {
                    setAiDraftLoading(true);
                    // TODO P2-34-DATA: POST /cs/tickets/{id}/ai-draft-reply
                  }}>
                  <Wand2 className="size-4" /> AI gợi ý
                </Button>
                <Button size="sm" variant="ghost">
                  <FileText className="size-4" /> Mẫu trả lời
                </Button>
              </div>
            </div>
            <textarea
              className="mt-2 h-32 w-full rounded border p-2 text-sm"
              placeholder="Nhập nội dung trả lời..."
              value={composerDraft}
              onChange={(e) => setComposerDraft(e.target.value)}
            />
            <div className="mt-2 flex items-center justify-between">
              <div className="text-xs text-muted-foreground">
                {/* TODO P2-34-PERM: gate Send on MANAGER approval for HIGH-risk */}
              </div>
              <Button><Send className="size-4" /> Gửi</Button>
            </div>
          </div>
        </div>

        {/* Right rail */}
        <div className="col-span-3 space-y-3">
          <RailPanel title="Nội bộ ghi chú" body="[TODO: mig 072 collab notes]" />
          <RailPanel title="Ticket tương tự (T-Cube)" body="[TODO: related-tickets list]" />
          <RailPanel title="AI gợi ý hành động" body="[TODO: Refund / Escalate L2 / Churn Save]" />
          {slaBreachIn2h && <RailPanel title="SLA Escalation Path (D.2)" body="[TODO: workflow visualisation]" />}
        </div>
      </div>

      {/* Footer actions */}
      <div className="sticky bottom-0 -mx-6 flex justify-end gap-2 border-t bg-white px-6 py-3">
        <Button variant="ghost">Snooze</Button>
        <Button variant="ghost">Reassign</Button>
        <Button variant="ghost">Merge</Button>
        <Button variant="ghost"><ExternalLink className="size-4" /> Link insight</Button>
        <Button>Resolve</Button>
      </div>
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function CustomerSidebarPanel({ customer }: { customer: CustomerSidebar | null }) {
  if (!customer) return <div className="rounded-lg border bg-white p-4 text-sm text-muted-foreground">Đang tải...</div>;
  const riskColor = {
    LOW: 'bg-green-100 text-green-700',
    MEDIUM: 'bg-yellow-100 text-yellow-700',
    HIGH: 'bg-orange-100 text-orange-700',
    CRITICAL: 'bg-red-100 text-red-700',
  }[customer.churn_risk];
  const churnHigh = customer.churn_risk === 'HIGH' || customer.churn_risk === 'CRITICAL';
  return (
    <div className="space-y-3 rounded-lg border bg-white p-4">
      <div>
        <div className="text-xs uppercase text-muted-foreground">Khách hàng</div>
        <div className="font-medium">{customer.name}</div>
      </div>
      <div>
        <div className="text-xs uppercase text-muted-foreground">LTV</div>
        <div className="text-sm">{customer.lifetime_value_vnd.toLocaleString('vi-VN')}₫</div>
      </div>
      <div>
        <div className="text-xs uppercase text-muted-foreground">Churn risk</div>
        <span className={cn('inline-block rounded-full px-2 py-0.5 text-xs', riskColor)}>
          {customer.churn_risk}
        </span>
      </div>
      <div>
        <div className="text-xs uppercase text-muted-foreground">Mở ticket</div>
        <div className="text-sm">{customer.open_ticket_count}</div>
      </div>
      {churnHigh && (
        <div className="rounded border border-yellow-300 bg-yellow-50 p-2 text-xs text-yellow-800">
          Khách HIGH risk churn — link sang Churn Save?
          <Button size="sm" variant="ghost" className="mt-1">Link → P2-37</Button>
        </div>
      )}
    </div>
  );
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  const isAgent = message.author_type === 'agent';
  const isAi = message.author_type === 'ai-summary';
  return (
    <div className={cn('rounded-lg p-3', isAi ? 'border bg-purple-50' : isAgent ? 'ml-8 bg-primary-gold/5' : 'mr-8 bg-gray-50')}>
      <div className="text-xs text-muted-foreground">
        {message.author_name} · {message.channel} · {new Date(message.created_at).toLocaleString('vi-VN')}
      </div>
      <div className="mt-1 whitespace-pre-wrap text-sm">{message.body}</div>
    </div>
  );
}

function RailPanel({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-lg border bg-white p-3">
      <div className="text-xs uppercase text-muted-foreground">{title}</div>
      <div className="mt-1 text-sm">{body}</div>
    </div>
  );
}
