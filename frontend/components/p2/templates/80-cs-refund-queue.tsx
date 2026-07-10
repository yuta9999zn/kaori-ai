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
import { useT } from '@/lib/i18n/provider';

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
  const t = useT();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // TODO P2-36-DATA: useQuery(['refund-queue', filters], poll 60s)
  const refunds: RefundRequest[] = [];
  const isLoading = false;
  const error: ProblemDetails | null = null;

  // TODO P2-36-PERM: hide approve buttons for VIEWER + OPERATOR without claim.

  if (error) return <ErrorBanner message={error.detail ?? t('templates80CsRefundQueue.errLoadFailed')} />;

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('templates80CsRefundQueue.title')}
        subtitle={t('templates80CsRefundQueue.subtitle')}
      />

      {/* Bulk action toolbar */}
      {selected.size > 0 && (
        <div className="flex items-center justify-between rounded-lg border border-primary-gold bg-primary-gold/5 px-4 py-2 text-sm">
          <span>{t('templates80CsRefundQueue.selectedCount', { count: selected.size })}</span>
          {/* TODO P2-36-PERM: bulk approve gated on approve_refund claim + AUTO_OK only */}
          <Button size="sm">{t('templates80CsRefundQueue.bulkApprove')}</Button>
        </div>
      )}

      {/* Queue table */}
      {isLoading && (
        <div className="space-y-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-16 animate-pulse rounded bg-gray-100" />)}</div>
      )}
      {!isLoading && refunds.length === 0 && (
        <div className="rounded-lg border border-dashed p-12 text-center text-muted-foreground">
          <CheckCircle2 className="mx-auto size-8 text-green-500" />
          <div className="mt-2">{t('templates80CsRefundQueue.emptyState')}</div>
        </div>
      )}
      {!isLoading && refunds.length > 0 && (
        <div className="rounded-lg border bg-white">
          <table className="w-full text-sm">
            <thead className="border-b bg-gray-50 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-4 py-2"><input type="checkbox" /></th>
                <th className="px-4 py-2">{t('templates80CsRefundQueue.colAmount')}</th>
                <th className="px-4 py-2">{t('templates80CsRefundQueue.colPolicy')}</th>
                <th className="px-4 py-2">{t('templates80CsRefundQueue.colCustomer')}</th>
                <th className="px-4 py-2">{t('templates80CsRefundQueue.colReason')}</th>
                <th className="px-4 py-2">{t('templates80CsRefundQueue.colRequestedBy')}</th>
                <th className="px-4 py-2">{t('templates80CsRefundQueue.colWaiting')}</th>
                <th className="px-4 py-2 text-right">{t('templates80CsRefundQueue.colAction')}</th>
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
        <div className="font-medium">{t('templates80CsRefundQueue.refundPolicyHeading')}</div>
        <div className="mt-2 text-sm text-muted-foreground">{t('templates80CsRefundQueue.featureInProgress')}</div>
      </div>

      {/* Audit panel placeholder */}
      <div className="rounded-lg border bg-white p-4">
        {/* TODO P2-36-PERM: claim view_audit_log */}
        <div className="flex items-center gap-2 font-medium">
          <ScrollText className="size-4" /> {t('templates80CsRefundQueue.auditHeading')}
        </div>
        <div className="mt-2 text-sm text-muted-foreground">{t('templates80CsRefundQueue.featureInProgress')}</div>
      </div>
    </div>
  );
}

// ─── Subcomponents ───────────────────────────────────────────────────

function RefundRow({ refund }: { refund: RefundRequest }) {
  const t = useT();
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
          <div className="mt-1 text-xs text-red-700">{t('templates80CsRefundQueue.policyViolationHint')}</div>
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
  const t = useT();
  const config = {
    AUTO_OK:          { label: t('templates80CsRefundQueue.policyAutoOk'), cls: 'bg-green-100 text-green-700' },
    MANUAL_REVIEW:    { label: t('templates80CsRefundQueue.policyManualReview'), cls: 'bg-yellow-100 text-yellow-700' },
    POLICY_VIOLATION: { label: t('templates80CsRefundQueue.policyViolation'), cls: 'bg-red-100 text-red-700' },
  }[match];
  return <span className={cn('rounded-full px-2 py-0.5 text-xs', config.cls)}>{config.label}</span>;
}
