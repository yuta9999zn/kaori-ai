/**
 * P1 Platform Manager — typed API client.
 *
 * Mirrors the auth-service controllers and the contracts the frontend depends
 * on. Endpoints marked PENDING are referenced by Batch 1 UI but the backend
 * route does not exist yet (will 404 in production until step-2 backend work
 * lands). Field shapes here ARE the contract that the backend must match.
 *
 *   ✅ implemented in WorkspaceController / PlatformController:
 *      - listWorkspaces, createWorkspace, updateWorkspace, deleteWorkspace
 *      - listKeys, generateKey, revokeKey
 *
 *   ⏳ PENDING (frontend stubs out, backend builds in step 2):
 *      - getWorkspace                              → GET    /api/v1/platform/workspaces/{id}
 *      - listWorkspaceMembers / inviteMember /
 *        updateMemberRole / removeMember           → /workspaces/{id}/members[/{userId}]
 *      - getWorkspaceBilling                       → GET    /workspaces/{id}/billing
 *      - listWorkspaceAudit                        → GET    /workspaces/{id}/audit
 *      - listAdmins / getAdmin / inviteAdmin /
 *        updateAdmin / resetAdminPassword          → /api/v1/platform/admins[/{id}[/reset-password]]
 */
import { api } from '@/lib/api';

// ────────────────────────────────────────────────────────────────────────────
// Shared envelopes
// ────────────────────────────────────────────────────────────────────────────
export interface Envelope<T>  { data: T }
export interface CursorPage<T> {
  data: T[];
  meta: { cursor: string | null; total: number };
}

// ────────────────────────────────────────────────────────────────────────────
// Workspaces — F-008
// ────────────────────────────────────────────────────────────────────────────
export type WsStatus = 'active' | 'inactive' | 'suspended';

export interface Workspace {
  workspace_id: string;
  name:         string;
  plan_code:    string;
  industry:     string;
  status:       WsStatus;
  created_at:   string;
  updated_at:   string;
}

export interface CreateWorkspaceBody {
  name:      string;
  plan_code: string;
  industry?: string;
}
export interface UpdateWorkspaceBody {
  name?:      string;
  plan_code?: string;
  status?:    WsStatus;
}

export const workspaceApi = {
  list: (cursor?: string | null, limit = 50) => {
    const qs = new URLSearchParams();
    qs.set('limit', String(limit));
    if (cursor) qs.set('cursor', cursor);
    return api<CursorPage<Workspace>>(`/api/v1/platform/workspaces?${qs}`);
  },
  /** ⏳ PENDING backend: GET /api/v1/platform/workspaces/{id} */
  get: (id: string) =>
    api<Envelope<Workspace>>(`/api/v1/platform/workspaces/${id}`),

  create: (body: CreateWorkspaceBody) =>
    api<Envelope<Workspace>>(`/api/v1/platform/workspaces`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  update: (id: string, body: UpdateWorkspaceBody) =>
    api<Envelope<Workspace>>(`/api/v1/platform/workspaces/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  softDelete: (id: string) =>
    api<Envelope<{ workspace_id: string; status: WsStatus }>>(
      `/api/v1/platform/workspaces/${id}`,
      { method: 'DELETE' },
    ),
};

// ────────────────────────────────────────────────────────────────────────────
// Workspace members — PENDING backend
// ────────────────────────────────────────────────────────────────────────────
export type MemberRole   = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';
export type MemberStatus = 'active' | 'pending' | 'inactive';

export interface WorkspaceMember {
  user_id:      string;
  email:        string;
  full_name:    string | null;
  role:         MemberRole;
  status:       MemberStatus;
  last_login_at: string | null;
  created_at:   string;
}

export interface InviteMemberBody {
  email: string;
  role:  MemberRole;
}

export const workspaceMemberApi = {
  /** ⏳ PENDING: GET /api/v1/platform/workspaces/{id}/members */
  list: (workspaceId: string) =>
    api<Envelope<WorkspaceMember[]>>(
      `/api/v1/platform/workspaces/${workspaceId}/members`,
    ),

  /** ⏳ PENDING: POST /api/v1/platform/workspaces/{id}/members */
  invite: (workspaceId: string, body: InviteMemberBody) =>
    api<Envelope<WorkspaceMember>>(
      `/api/v1/platform/workspaces/${workspaceId}/members`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  /** ⏳ PENDING: PATCH /api/v1/platform/workspaces/{id}/members/{userId} */
  updateRole: (workspaceId: string, userId: string, role: MemberRole) =>
    api<Envelope<WorkspaceMember>>(
      `/api/v1/platform/workspaces/${workspaceId}/members/${userId}`,
      { method: 'PATCH', body: JSON.stringify({ role }) },
    ),

  /** ⏳ PENDING: DELETE /api/v1/platform/workspaces/{id}/members/{userId} */
  remove: (workspaceId: string, userId: string) =>
    api<Envelope<{ user_id: string }>>(
      `/api/v1/platform/workspaces/${workspaceId}/members/${userId}`,
      { method: 'DELETE' },
    ),
};

// ────────────────────────────────────────────────────────────────────────────
// Workspace billing summary — PENDING backend
// (Phase-1 source of truth: enterprise_monthly_billing table)
// ────────────────────────────────────────────────────────────────────────────
export interface WorkspaceBillingSummary {
  workspace_id:        string;
  plan_code:           string;
  billing_month:       string;             // 'YYYY-MM'
  unique_customers:    number;             // billable unit, K-11
  quota:               number;
  overage_units:       number;
  base_amount_vnd:     number;
  overage_amount_vnd:  number;
  total_amount_vnd:    number;
  quota_warn_at_pct:   number;             // 80 / 95
  status:              'normal' | 'warn' | 'critical' | 'overage';
  next_invoice_date:   string | null;
}

export const workspaceBillingApi = {
  /** ⏳ PENDING: GET /api/v1/platform/workspaces/{id}/billing */
  get: (workspaceId: string) =>
    api<Envelope<WorkspaceBillingSummary>>(
      `/api/v1/platform/workspaces/${workspaceId}/billing`,
    ),
};

// ────────────────────────────────────────────────────────────────────────────
// Workspace audit log — PENDING backend
// (Phase-1 source: decision_audit_log + auth events; cursor-paginated)
// ────────────────────────────────────────────────────────────────────────────
export interface AuditEvent {
  event_id:    string;
  event_type:  string;             // e.g. 'workspace.updated', 'member.invited'
  actor_email: string | null;      // null for system events
  actor_role:  string | null;
  resource:    string | null;      // free-form short label
  detail:      string | null;
  ip_address:  string | null;
  created_at:  string;
}

export const workspaceAuditApi = {
  /** ⏳ PENDING: GET /api/v1/platform/workspaces/{id}/audit?cursor=&limit= */
  list: (workspaceId: string, cursor?: string | null, limit = 50) => {
    const qs = new URLSearchParams();
    qs.set('limit', String(limit));
    if (cursor) qs.set('cursor', cursor);
    return api<CursorPage<AuditEvent>>(
      `/api/v1/platform/workspaces/${workspaceId}/audit?${qs}`,
    );
  },
};

// ────────────────────────────────────────────────────────────────────────────
// Workspace API keys — F-009
// (Nested deepening pattern, consistent with members/billing/audit.
//  Backend reuses workspace_keys table + PlatformKeyService — see
//  WorkspaceController.list/generate/revokeKey. The flat
//  /api/v1/platform/keys routes remain in PlatformController for
//  AuthService.activateWorkspace internal use; do not call them here.)
// ────────────────────────────────────────────────────────────────────────────
export type KeyStatus = 'active' | 'revoked';

export interface WorkspaceKey {
  key_id:     string;
  label:      string;
  status:     KeyStatus;
  created_at: string;
  revoked_at: string | null;
}

export interface CreateKeyBody { label?: string }

export interface CreatedKey extends WorkspaceKey {
  /** Returned ONCE on creation — never persisted, never returned by list. */
  raw_key: string;
}

export const workspaceKeyApi = {
  /** GET /api/v1/platform/workspaces/{id}/keys */
  list: (workspaceId: string) =>
    api<Envelope<WorkspaceKey[]>>(
      `/api/v1/platform/workspaces/${workspaceId}/keys`,
    ),

  /** POST /api/v1/platform/workspaces/{id}/keys */
  create: (workspaceId: string, body: CreateKeyBody) =>
    api<Envelope<CreatedKey> & { meta: { warning: string } }>(
      `/api/v1/platform/workspaces/${workspaceId}/keys`,
      { method: 'POST', body: JSON.stringify(body) },
    ),

  /** DELETE /api/v1/platform/workspaces/{id}/keys/{keyId} */
  revoke: (workspaceId: string, keyId: string) =>
    api<Envelope<{ key_id: string; status: KeyStatus; revoked_at: string }>>(
      `/api/v1/platform/workspaces/${workspaceId}/keys/${keyId}`,
      { method: 'DELETE' },
    ),
};

// ────────────────────────────────────────────────────────────────────────────
// Platform billing — F-011
// (Aggregation across enterprises. Reuses the same physical data as F-008's
//  per-workspace /billing endpoint; status thresholds are 80% / 95% (BillingMath).
//  /export returns text/csv with UTF-8 BOM — fetch via fetchExportCsv below.)
// ────────────────────────────────────────────────────────────────────────────
export type BillingStatus = 'normal' | 'warn' | 'critical' | 'overage';

export interface BillingOverview {
  billing_month:             string;          // YYYY-MM
  enterprise_count:          number;
  by_status: {
    normal:   number;
    warn:     number;
    critical: number;
    overage:  number;
  };
  total_unique_customers:    number;
  total_quota:               number;
  total_overage_units:       number;
  total_base_amount_vnd:     number;
  total_overage_amount_vnd:  number;
  total_revenue_vnd:         number;
  next_invoice_date:         string;
  /** Sprint 7 PR C — F-031 cron health surfacing. */
  last_aggregated_at:        string | null;
  stale_enterprise_count:    number;
}

export interface EnterpriseBillingSummary {
  enterprise_id:       string;
  enterprise_name:     string;
  workspace_id:        string;
  plan_code:           string;
  billing_month:       string;
  unique_customers:    number;
  quota:               number;
  overage_units:       number;
  base_amount_vnd:     number;
  overage_amount_vnd:  number;
  total_amount_vnd:    number;
  quota_warn_at_pct:   number;
  status:              BillingStatus;
  next_invoice_date:   string | null;
}

export interface QuotaRow {
  enterprise_id:    string;
  enterprise_name:  string;
  workspace_id:     string;
  plan_code:        string;
  unique_customers: number;
  quota:            number;
  usage_pct:        number;
  overage_units:    number;
  status:           BillingStatus;
  total_amount_vnd: number;
}

export interface QuotaFilters {
  plan?:   string;
  status?: BillingStatus;
}

const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8080';

export const platformBillingApi = {
  /** GET /api/v1/platform/billing/overview */
  overview: () =>
    api<Envelope<BillingOverview>>(`/api/v1/platform/billing/overview`),

  /** GET /api/v1/platform/billing/enterprises/{id} */
  getEnterprise: (enterpriseId: string) =>
    api<Envelope<EnterpriseBillingSummary>>(
      `/api/v1/platform/billing/enterprises/${enterpriseId}`,
    ),

  /** GET /api/v1/platform/billing/quota?plan=&status=&cursor=&limit= */
  listQuota: (filters: QuotaFilters = {}, cursor?: string | null, limit = 50) => {
    const qs = new URLSearchParams();
    qs.set('limit', String(limit));
    if (cursor)         qs.set('cursor', cursor);
    if (filters.plan)   qs.set('plan',   filters.plan);
    if (filters.status) qs.set('status', filters.status);
    return api<CursorPage<QuotaRow>>(
      `/api/v1/platform/billing/quota?${qs}`,
    );
  },

  /**
   * GET /api/v1/platform/billing/export — returns the CSV bytes (with BOM)
   * ready to download. Uses raw fetch instead of api() because the response
   * is text/csv, not JSON.
   */
  exportCsv: async (
    filters: QuotaFilters & { month?: string } = {},
  ): Promise<{ blob: Blob; filename: string }> => {
    const qs = new URLSearchParams();
    if (filters.month)  qs.set('month',  filters.month);
    if (filters.plan)   qs.set('plan',   filters.plan);
    if (filters.status) qs.set('status', filters.status);
    const url = `${BASE_URL}/api/v1/platform/billing/export${qs.toString() ? `?${qs}` : ''}`;

    const token =
      typeof window !== 'undefined' ? localStorage.getItem('kaori.access_token') : null;
    const res = await fetch(url, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) {
      const text = await res.text();
      let message = res.statusText;
      try { message = JSON.parse(text)?.detail ?? message; } catch { /* not JSON */ }
      throw { status: res.status, error: 'export_failed', message };
    }

    // Filename from Content-Disposition (server returns
    // `attachment; filename="kaori-billing-2026-04.csv"`).
    const disp = res.headers.get('Content-Disposition') ?? '';
    const match = /filename="?([^"]+)"?/.exec(disp);
    const filename = match?.[1] ?? `kaori-billing-${new Date().toISOString().slice(0, 7)}.csv`;
    return { blob: await res.blob(), filename };
  },
};

// ────────────────────────────────────────────────────────────────────────────
// Platform admin security — Module 3 (MFA + sessions)
// ────────────────────────────────────────────────────────────────────────────

export interface MfaEnableResult {
  secret:      string;     // Base32, shown ONCE for manual entry
  otpauth_url: string;     // for QR rendering
  issuer:      string;
  account:     string;
}

export interface MfaVerifyResult {
  mfa_enabled: boolean;
  verified_at: string;
}

export interface AdminSession {
  session_id:     string;
  ip_address:     string | null;
  user_agent:     string | null;
  device_label:   string | null;
  created_at:     string;
  last_active_at: string;
  is_current:     boolean;
}

export const platformSecurityApi = {
  /** POST /api/v1/platform/security/mfa/enable — initiates MFA, returns secret + otpauth URL once. */
  enableMfa: () =>
    api<Envelope<MfaEnableResult> & { meta: { warning: string } }>(
      `/api/v1/platform/security/mfa/enable`,
      { method: 'POST' },
    ),

  /** POST /api/v1/platform/security/mfa/verify */
  verifyMfa: (code: string) =>
    api<Envelope<MfaVerifyResult>>(`/api/v1/platform/security/mfa/verify`, {
      method: 'POST',
      body:   JSON.stringify({ code }),
    }),

  /** GET /api/v1/platform/security/sessions */
  listSessions: () =>
    api<Envelope<AdminSession[]>>(`/api/v1/platform/security/sessions`),

  /** DELETE /api/v1/platform/security/sessions/{id} */
  revokeSession: (sessionId: string) =>
    api<
      Envelope<{ session_id: string; revoked_at: string }>
      & { meta: { signed_out: boolean } }
    >(
      `/api/v1/platform/security/sessions/${sessionId}`,
      { method: 'DELETE' },
    ),

  /**
   * 3.3 — POST /api/v1/platform/security/sessions/revoke-others
   * Bulk-revoke every active session for the caller EXCEPT their current one
   * (resolved server-side from X-Session-Id forwarded by the gateway).
   */
  revokeOtherSessions: () =>
    api<Envelope<{
      revoked_count:    number;
      kept_session_id:  string | null;
      revoked_at:       string;
    }>>(
      `/api/v1/platform/security/sessions/revoke-others`,
      { method: 'POST' },
    ),
};

// ────────────────────────────────────────────────────────────────────────────
// Platform admins — PENDING backend (no PlatformAdminController exists yet)
// ────────────────────────────────────────────────────────────────────────────
export type PlatformRole = 'SUPER_ADMIN' | 'ADMIN' | 'SUPPORT';

export interface PlatformAdmin {
  id:            string;
  email:         string;
  full_name:     string | null;
  role:          PlatformRole;
  is_active:     boolean;
  mfa_enabled:   boolean;
  last_login_at: string | null;
  created_at:    string;
}

export interface InviteAdminBody {
  email:     string;
  full_name: string;
  role:      PlatformRole;
}
export interface UpdateAdminBody {
  role?:      PlatformRole;
  is_active?: boolean;
  full_name?: string;
}

export const platformAdminApi = {
  /** ✅ Frontend already calls this — backend not yet implemented */
  list: () =>
    api<Envelope<PlatformAdmin[]>>(`/api/v1/platform/admins`),

  /** ⏳ PENDING: GET /api/v1/platform/admins/{id} */
  get: (id: string) =>
    api<Envelope<PlatformAdmin>>(`/api/v1/platform/admins/${id}`),

  /** ⏳ PENDING: POST /api/v1/platform/admins */
  invite: (body: InviteAdminBody) =>
    api<Envelope<PlatformAdmin>>(`/api/v1/platform/admins`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  /** ⏳ PENDING: PATCH /api/v1/platform/admins/{id} */
  update: (id: string, body: UpdateAdminBody) =>
    api<Envelope<PlatformAdmin>>(`/api/v1/platform/admins/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  /** ⏳ PENDING: POST /api/v1/platform/admins/{id}/reset-password */
  resetPassword: (id: string) =>
    api<Envelope<{ id: string; reset_token_sent_to: string }>>(
      `/api/v1/platform/admins/${id}/reset-password`,
      { method: 'POST' },
    ),
};
