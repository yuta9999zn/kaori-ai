// @ts-nocheck — template wiring; tighten when proper component lib lands.
'use client';

// ============================================================================
// P2-36 — Refund Approval Queue
// ----------------------------------------------------------------------------
// Phase 2.8 NEW. Maps to workflow D.4 Refund Approval.
//
// Route:        /p2/cs/refunds
// Permission:   OPERATOR+ xem; approve action MANAGER+ với claim `approve_refund`.
// URD US-ID:    US-CS-4
// K-rules:      K-6 audit per approval (mig 098 ai_decision_audit).
// BE routes:
//   GET  /api/v1/cs/refunds?status=pending
//   POST /api/v1/cs/refunds/{id}/approve   body { note }       (claim required)
//   POST /api/v1/cs/refunds/{id}/reject    body { reason_code, note }
//   POST /api/v1/cs/refunds/{id}/request-info body { message }
//   POST /api/v1/cs/refunds/bulk-approve   body { refund_ids[] } (claim + AUTO_OK only)
//   GET  /api/v1/cs/refund-policy/{enterpriseId}
//   PATCH /api/v1/cs/refund-policy/{enterpriseId}
//   GET  /api/v1/ai-decision-audit/refund/{id}                  (mig 098)
// ============================================================================

import React, { useState } from 'react';
import { CheckCircle2, XCircle, MessageSquareWarning, ScrollText, AlertTriangle } from 'lucide-react';

import {
  Button, Badge, ErrorBanner, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

// ─── Types ───────────────────────────────────────────────────────────

type PolicyMatch = 'AUTO_OK' | 'MANUAL_REVIEW' | 'POLICY_VIOLATION';

interface RefundRequest {
  refund_id:           string;
  customer_id:         string;
  customer_name:       string;
  amount_vnd:          number;            // K-9 NUMERIC(14,4) — handled as bigint via API
  policy_match:        PolicyMatch;
  reason_code:         string;            // 'damaged' | 'late' | 'wrong_item' | 'change_mind'
  reason_note:         string | null;
  requested_by_name:   string;
  days_waiting:        number;
  customer_ltv_vnd:    number;
  ai_confidence:       number | null;     // 0..1
  ai_recommendation:   string | null;
}

// ─── Page component ──────────────────────────────────────────────────

export default function RefundQueuePage() {
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // TODO P2-36-DATA: useQuery(['refund-queue', filters], poll 60s)
  const refunds: RefundRequest[] = [];
  const isLoading = false;
  const error: ProblemDetails | null = null;

  // TODO P2-36-PERM: hide approve buttons for VIEWER + OPERATOR without claim.

  if (error) return <ErrorBanner message={error.detail ?? 'Không tải được queue.'} />;

  return (
    <div className="space-y-4">
      <PageHeader
        title="Refund Approval Queue"
        subtitle="Duyệt hoàn tiền theo policy + AI gợi ý. Mỗi quyết định ghi K-6 audit log (mig 098)."
      />

      {/* Bulk action toolbar */}
      {selected.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-primary-gold bg-primary-gold/5 px-4 py-2 text-sm">
          <span>{selected.size} refund đã chọn</span>
          {/* TODO P2-36-PERM: bulk approve gated on approve_refund claim + AUTO_OK only */}
          <Button size="sm">Bulk approve (chỉ AUTO_OK)</Button>
        </div>
      )}

      {/* Queue table */}
      {isLoading && (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded bg-gray-100" />)}</div>
      )}
      {!isLoading && refunds.length === 0 && (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          <CheckCircle2 className="mx-auto size-8 text-green-500" />
          <div className="mt-2">Không có refund đang chờ duyệt 🎉.</div>
        </div>
      )}
      {!isLoading && refunds.length > 0 && (
        <div className="rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2"><input type="checkbox" /></th>
                <th className="px-4 py-2">Số tiền</th>
                <th className="px-4 py-2">Policy</th>
                <th className="px-4 py-2">Khách (LTV)</th>
                <th className="px-4 py-2">Lý do</th>
                <th className="px-4 py-2">Yêu cầu bởi</th>
                <th className="px-4 py-2">Chờ</th>
                <th className="px-4 py-2 text-right">Hành động</th>
              </tr>
            </thead>
            <tbody>
              {refunds.map(r => <RefundRow key={r.refund_id} refund={r} />)}
            </tbody>
          </table>
        </div>
      )}

      {/* Policy config drawer placeholder */}
      <div className="rounded-lg border bg-white p-4">
        {/* TODO P2-36-PERM: MANAGER+ for policy config */}
        <div className="font-medium">Refund Policy</div>
        <div className="mt-2 text-sm text-muted-foreground">Tính năng đang hoàn thiện</div>
      </div>

      {/* Audit panel placeholder */}
      <div className="rounded-lg border bg-white p-4">
        {/* TODO P2-36-PERM: claim view_audit_log */}
        <div className="flex items-center gap-2 font-medium">
          <ScrollText className="size-4" /> AI Decision Audit (mig 098)
        </div>
        <div className="mt-2 text-sm text-muted-foreground">Tính năng đang hoàn thiện</div>
      </div>
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function RefundRow({ refund }: { refund: RefundRequest }) {
  const isPolicyViolation = refund.policy_match === 'POLICY_VIOLATION';
  return (
    <tr className={cn('border-b hover:bg-gray-50', isPolicyViolation && 'bg-red-50')}>
      <td className="px-4 py-2"><input type="checkbox" /></td>
      <td className="px-4 py-2 font-medium">
        {refund.amount_vnd.toLocaleString('vi-VN')}₫
      </td>
      <td className="px-4 py-2">
        <PolicyBadge match={refund.policy_match} />
        {isPolicyViolation && (
          <div className="mt-1 text-xs text-red-700">Vượt policy — cần override + reason mandatory.</div>
        )}
      </td>
      <td className="px-4 py-2">
        <div>{refund.customer_name}</div>
        <div className="text-xs text-muted-foreground">LTV {refund.customer_ltv_vnd.toLocaleString('vi-VN')}₫</div>
      </td>
      <td className="px-4 py-2">
        <Badge variant="outline">{refund.reason_code}</Badge>
        {refund.reason_note && <div className="mt-1 text-xs text-muted-foreground max-w-xs truncate">{refund.reason_note}</div>}
      </td>
      <td className="px-4 py-2 text-xs">{refund.requested_by_name}</td>
      <td className="px-4 py-2 text-xs">{refund.days_waiting}d</td>
      <td className="px-4 py-2">
        {/* TODO P2-36-PERM: gate Approve on claim approve_refund + role MANAGER+ */}
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="ghost"><MessageSquareWarning className="size-4" /></Button>
          <Button size="sm" variant="destructive"><XCircle className="size-4" /></Button>
          <Button size="sm"><CheckCircle2 className="size-4" /></Button>
        </div>
      </td>
    </tr>
  );
}

function PolicyBadge({ match }: { match: PolicyMatch }) {
  const config = {
    AUTO_OK:          { label: 'Auto OK', cls: 'bg-green-100 text-green-700' },
    MANUAL_REVIEW:    { label: 'Manual review', cls: 'bg-yellow-100 text-yellow-700' },
    POLICY_VIOLATION: { label: 'Violation', cls: 'bg-red-100 text-red-700' },
  }[match];
  return <span className={cn('rounded-full px-2 py-0.5 text-xs', config.cls)}>{config.label}</span>;
}
