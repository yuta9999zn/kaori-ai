"use client";

/**
 * F-015 — Enterprise User & Role Management.
 *
 * Page-based pagination (BE returns ``{data, meta:{total, page, limit}}``).
 * Invite + role change + deactivate / delete actions all hit
 * ``/api/v1/enterprises/users`` (gateway → auth-service → EnterpriseUserController).
 * Only MANAGER can mutate; the BE returns 403 to other roles.
 */

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserPlus, ShieldCheck, Eye, Edit3, Loader2, Trash2, Power, Wand2, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { DataTable, type Column } from "@/components/ui/data-table";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Modal } from "@/components/ui/modal";
import { useAuth } from "@/lib/auth-store";
import { useT } from "@/lib/i18n/provider";
import { fmtDateTime } from "@/lib/format";

type UserRole = "MANAGER" | "OPERATOR" | "ANALYST" | "VIEWER";

interface EnterpriseUser {
  id:           string;
  user_id?:     string;
  email:        string;
  full_name?:   string | null;
  role:         UserRole;
  status:       string;
  is_active:    boolean;
  last_login_at?: string | null;
  created_at:   string;
}

interface UsersPage {
  data: EnterpriseUser[];
  meta: { total: number; page: number; limit: number };
}

const ROLE_TONE: Record<UserRole, BadgeTone> = {
  MANAGER:  "brand",
  OPERATOR: "info",
  ANALYST:  "neutral",
  VIEWER:   "neutral",
};
type TFn = (key: string, params?: Record<string, string | number>) => string;

function roleLabel(t: TFn, role: UserRole): string {
  const map: Record<UserRole, string> = {
    MANAGER:  t("usersPage.roleManager"),
    OPERATOR: t("usersPage.roleOperator"),
    ANALYST:  t("usersPage.roleAnalyst"),
    VIEWER:   t("usersPage.roleViewer"),
  };
  return map[role];
}
const ROLE_ICON: Record<UserRole, any> = {
  MANAGER:  ShieldCheck,
  OPERATOR: Edit3,
  ANALYST:  Edit3,
  VIEWER:   Eye,
};
const ROLES: UserRole[] = ["MANAGER", "OPERATOR", "ANALYST", "VIEWER"];

const PAGE_SIZE = 20;

export default function UsersPage() {
  const t  = useT();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [showInvite, setShowInvite] = useState(false);
  // P15-S11 Hướng A — "Áp dụng quyền theo template" modal: target user
  // captured here, opens TemplateRoleModal which fetches dept list +
  // resolves template via mig 061 endpoints and applies via the
  // orchestrator PATCH route.
  const [templateTarget, setTemplateTarget] = useState<EnterpriseUser | null>(null);

  const { data, isLoading, isError } = useQuery<UsersPage>({
    queryKey: ["enterprise-users", page],
    queryFn:  () => api(`/api/v1/enterprises/users?page=${page}&limit=${PAGE_SIZE}`),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });

  const inviteMutation = useMutation({
    mutationFn: (body: { email: string; full_name: string; role: UserRole }) =>
      api(`/api/v1/enterprises/users`, {
        method: "POST",
        body:   JSON.stringify(body),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["enterprise-users"] });
      setShowInvite(false);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, body }: { userId: string; body: { role?: UserRole; status?: string } }) =>
      api(`/api/v1/enterprises/users/${userId}`, {
        method: "PATCH",
        body:   JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["enterprise-users"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: (userId: string) =>
      api(`/api/v1/enterprises/users/${userId}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["enterprise-users"] }),
  });

  const COLUMNS: Column<EnterpriseUser>[] = useMemo(() => [
    {
      key: "full_name",
      header: t("usersPage.colUser"),
      render: (row) => (
        <div className="min-w-0">
          <p className="text-body-strong text-ink truncate">{row.full_name ?? "—"}</p>
          <p className="text-tiny text-[#B0A698] truncate">{row.email}</p>
        </div>
      ),
    },
    {
      key: "role",
      header: t("usersPage.colRole"),
      render: (row) => {
        const Icon = ROLE_ICON[row.role];
        return (
          <div className="flex items-center gap-2">
            <Icon className="w-3.5 h-3.5 text-[#B0A698]" />
            <select
              value={row.role}
              onChange={(e) =>
                updateMutation.mutate({ userId: row.id, body: { role: e.target.value as UserRole } })
              }
              disabled={updateMutation.isPending}
              className="text-tiny px-2 py-0.5 rounded-md border border-subtle bg-surface focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>{roleLabel(t, r)}</option>
              ))}
            </select>
          </div>
        );
      },
    },
    {
      key: "is_active",
      header: t("usersPage.colStatus"),
      render: (row) => (
        <Badge tone={row.is_active ? "success" : "neutral"}>
          {row.is_active ? t("usersPage.active") : t("usersPage.inactive")}
        </Badge>
      ),
    },
    {
      key: "created_at",
      header: t("usersPage.colCreatedAt"),
      render: (row) => (
        <span className="text-tiny text-[#B0A698] tabular-nums">{fmtDateTime(row.created_at)}</span>
      ),
    },
    {
      key: "id",
      header: "",
      render: (row) => (
        <div className="flex items-center gap-1.5 justify-end">
          <button
            onClick={() => setTemplateTarget(row)}
            title={t("usersPage.tooltipApplyTemplate")}
            className="p-1.5 rounded-md hover:bg-surface text-ink-muted hover:text-brand-500"
          >
            <Wand2 className="w-4 h-4" />
          </button>
          <button
            onClick={() =>
              updateMutation.mutate({
                userId: row.id,
                body:   { status: row.is_active ? "inactive" : "active" },
              })
            }
            disabled={updateMutation.isPending}
            title={row.is_active ? t("usersPage.deactivate") : t("usersPage.activate")}
            className="p-1.5 rounded-md hover:bg-surface text-ink-muted hover:text-brand-500"
          >
            <Power className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              if (confirm(t("usersPage.confirmDeleteUser", { email: row.email }))) {
                deleteMutation.mutate(row.id);
              }
            }}
            disabled={deleteMutation.isPending}
            title={t("usersPage.delete")}
            className="p-1.5 rounded-md hover:bg-danger-50 text-ink-muted hover:text-danger-600"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      ),
    },
  ], [t, updateMutation, deleteMutation]);

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-h1 font-serif text-ink">{t("nav.users")}</h1>
          <p className="text-small text-ink-muted mt-1">
            {t("usersPage.subtitle")}
          </p>
        </div>
        <Button onClick={() => setShowInvite(true)}>
          <UserPlus className="w-4 h-4 mr-1.5" />
          {t("usersPage.inviteMember")}
        </Button>
      </div>

      {showInvite && (
        <InviteForm
          isPending={inviteMutation.isPending}
          isError={inviteMutation.isError}
          errorMessage={(inviteMutation.error as { message?: string } | null)?.message}
          onCancel={() => setShowInvite(false)}
          onSubmit={(body) => inviteMutation.mutate(body)}
        />
      )}

      {isLoading && (
        <div className="space-y-3">
          {Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-14" />)}
        </div>
      )}

      {isError && (
        <Card className="border-danger-200 bg-danger-50/30">
          <CardContent className="pt-6 text-small text-danger-700">{t("error.generic")}</CardContent>
        </Card>
      )}

      {!isLoading && !isError && (data?.data ?? []).length === 0 && (
        <EmptyState
          icon={UserPlus}
          title={t("usersPage.emptyTitle")}
          description={t("usersPage.emptyDescription")}
        />
      )}

      {!isLoading && !isError && (data?.data ?? []).length > 0 && (
        <DataTable<EnterpriseUser>
          columns={COLUMNS}
          rows={data?.data ?? []}
          page={page}
          pageSize={PAGE_SIZE}
          total={data?.meta?.total ?? 0}
          onPageChange={setPage}
          emptyMessage={t("usersPage.tableEmptyMessage")}
        />
      )}

      {templateTarget && (
        <TemplateRoleModal
          target={templateTarget}
          onClose={() => setTemplateTarget(null)}
          onApplied={() => {
            qc.invalidateQueries({ queryKey: ["enterprise-users"] });
            setTemplateTarget(null);
          }}
        />
      )}
    </div>
  );
}

// ─── P15-S11 Hướng A — Apply-role-from-template modal ─────────────────
//
// Two cascading selects (phòng ban → cấp bậc). Once both are picked, the
// modal calls GET /api/v1/departments/{dept_id}/role-template?seniority_level=
// to fetch the templated default_role and renders the "Đề xuất quyền"
// preview. Manager clicks "Áp dụng theo template" → PATCH
// /api/v1/enterprise-users/{user_id}/role with the template path; audit
// row lands automatically server-side.

function seniorityLevels(t: TFn): Array<{ key: string; label: string }> {
  return [
    { key: 'entry',     label: t("usersPage.seniorityEntry") },
    { key: 'junior',    label: t("usersPage.seniorityJunior") },
    { key: 'mid',       label: t("usersPage.seniorityMid") },
    { key: 'senior',    label: t("usersPage.senioritySenior") },
    { key: 'executive', label: t("usersPage.seniorityExecutive") },
  ];
}

interface DeptOption {
  department_id: string;
  name:          string;
  dept_type:     string;
}

interface RoleTemplate {
  template_id:     string;
  default_role:    UserRole;
  is_override:     boolean;
  description_vi:  string | null;
  enterprise_id:   string | null;
}

function TemplateRoleModal({
  target, onClose, onApplied,
}: {
  target:    EnterpriseUser;
  onClose:   () => void;
  onApplied: () => void;
}) {
  const t = useT();
  // EnterpriseUser list rows don't expose enterprise_id today — read it
  // from the auth store instead. Caller + target are guaranteed to share
  // an enterprise because the list query is RLS-scoped to the caller's.
  const callerEnterpriseId = useAuth((s) => s.user?.enterprise_id);
  const [depts, setDepts]               = useState<DeptOption[]>([]);
  const [deptId, setDeptId]             = useState<string>("");
  const [seniority, setSeniority]       = useState<string>("");
  const [preview, setPreview]           = useState<RoleTemplate | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [submitting, setSubmitting]     = useState(false);
  const [submitError, setSubmitError]   = useState<string | null>(null);
  const [applied, setApplied]           = useState<{
    role: UserRole; previous: UserRole; audit_event_id: string;
  } | null>(null);

  // Load departments under the caller's enterprise. The org-detail
  // endpoint includes dept name + dept_type for all depts in the
  // enterprise (cf. routers/corporate_tree.py:451).
  useEffect(() => {
    if (!callerEnterpriseId) return;
    (async () => {
      try {
        const detail = await api<any>(
          `/api/v1/enterprises/${callerEnterpriseId}/org-detail`,
        ).catch(() => null);
        if (detail && Array.isArray(detail.departments)) {
          setDepts(detail.departments.map((d: any) => ({
            department_id: d.department_id,
            name:          d.name || d.dept_type || t("usersPage.unnamed"),
            dept_type:     d.dept_type || 'custom',
          })));
        }
      } catch (e: any) {
        // Falls back to empty; user can still close.
      }
    })();
  }, [callerEnterpriseId]);

  // When both selects set, fetch the template suggestion.
  useEffect(() => {
    setPreview(null);
    setPreviewError(null);
    if (!deptId || !seniority) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await api<any>(
          `/api/v1/departments/${deptId}/role-template?seniority_level=${encodeURIComponent(seniority)}`,
        );
        if (cancelled) return;
        setPreview(resp.template);
      } catch (e: any) {
        if (cancelled) return;
        setPreviewError(e?.title || t("usersPage.errPreviewFailed"));
      }
    })();
    return () => { cancelled = true; };
  }, [deptId, seniority]);

  async function apply() {
    if (!deptId || !seniority) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const resp = await api<any>(
        `/api/v1/enterprise-users/${target.id}/role`,
        {
          method: 'PATCH',
          body: JSON.stringify({
            department_id:   deptId,
            seniority_level: seniority,
            reason:          `Áp dụng quyền theo template — ${seniority} của ${depts.find((d) => d.department_id === deptId)?.name ?? 'phòng ban'}.`,
          }),
        },
      );
      setApplied({
        role:           resp.role,
        previous:       resp.previous_role,
        audit_event_id: resp.audit_event_id,
      });
    } catch (e: any) {
      setSubmitError(e?.title || t("usersPage.errApplyFailed"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Modal
      open
      onClose={submitting ? () => null : onClose}
      title={t("usersPage.modalApplyTemplateTitle")}
      description={
        <span className="text-tiny text-ink-muted">
          {t("usersPage.labelUserColon")} <span className="font-medium text-ink">{target.full_name || target.email}</span> ·
          {" "}{t("usersPage.labelCurrentRoleColon")} <Badge tone={target.role === 'MANAGER' ? 'brand' : 'neutral'}>{target.role}</Badge>
        </span>
      }
      footer={
        applied ? (
          <div className="flex justify-end">
            <Button onClick={onApplied}>{t("usersPage.close")}</Button>
          </div>
        ) : (
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={onClose} disabled={submitting}>{t("usersPage.cancel")}</Button>
            <Button
              onClick={apply}
              disabled={!preview || submitting}
              loading={submitting}
            >
              {t("usersPage.applyPrefix")}{preview ? preview.default_role : t("usersPage.byTemplateFallback")}
            </Button>
          </div>
        )
      }
    >
      {applied ? (
        <div className="space-y-3">
          <div className="flex items-start gap-3 p-3 rounded-md bg-success-50 border border-success-100">
            <ShieldCheck className="w-5 h-5 text-success-700 mt-0.5 shrink-0" />
            <div className="flex-1 text-small">
              <p className="font-medium text-success-700">{t("usersPage.appliedRoleMsg", { role: applied.role })}</p>
              <p className="text-tiny text-ink-muted mt-0.5">
                {applied.previous === applied.role
                  ? t("usersPage.keptSameRole")
                  : t("usersPage.roleChanged", { from: applied.previous, to: applied.role })}
              </p>
              <p className="text-tiny text-[#B0A698] mt-1 font-mono">audit_event_id: {applied.audit_event_id}</p>
            </div>
          </div>
        </div>
      ) : (
        <div className="space-y-4">
          <label className="block space-y-1">
            <span className="text-small text-ink-muted">{t("usersPage.department")}</span>
            <select
              value={deptId}
              onChange={(e) => setDeptId(e.target.value)}
              disabled={depts.length === 0}
              className="w-full px-3 py-2 rounded-xl border border-subtle bg-surface text-small focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              <option value="">{t("usersPage.selectDeptPlaceholder")}</option>
              {depts.map((d) => (
                <option key={d.department_id} value={d.department_id}>
                  {d.name} ({d.dept_type})
                </option>
              ))}
            </select>
            {depts.length === 0 && (
              <span className="text-tiny text-[#B0A698]">
                {t("usersPage.loadingDepts")}
              </span>
            )}
          </label>

          <label className="block space-y-1">
            <span className="text-small text-ink-muted">{t("usersPage.seniority")}</span>
            <select
              value={seniority}
              onChange={(e) => setSeniority(e.target.value)}
              className="w-full px-3 py-2 rounded-xl border border-subtle bg-surface text-small focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              <option value="">{t("usersPage.selectSeniorityPlaceholder")}</option>
              {seniorityLevels(t).map((s) => (
                <option key={s.key} value={s.key}>{s.label}</option>
              ))}
            </select>
          </label>

          <div className="rounded-xl border border-subtle bg-surface p-3 min-h-[64px]">
            {!deptId || !seniority ? (
              <p className="text-tiny text-[#B0A698]">
                {t("usersPage.selectBothHint")}
              </p>
            ) : previewError ? (
              <div className="flex items-start gap-2 text-small text-danger-700">
                <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                <span>{previewError}</span>
              </div>
            ) : preview ? (
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-tiny text-ink-muted">{t("usersPage.suggestedRoleLabel")}</span>
                  <Badge tone={preview.default_role === 'MANAGER' ? 'brand' : 'neutral'}>
                    {preview.default_role}
                  </Badge>
                  {preview.is_override && (
                    <Badge tone="info">{t("usersPage.overrideBadge")}</Badge>
                  )}
                </div>
                {preview.description_vi && (
                  <p className="text-tiny text-ink-muted">{preview.description_vi}</p>
                )}
              </div>
            ) : (
              <Loader2 className="w-4 h-4 animate-spin text-[#B0A698]" />
            )}
          </div>

          {submitError && (
            <div className="flex items-start gap-2 p-2 rounded-md bg-danger-50 border border-danger-100 text-small text-danger-700">
              <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>{submitError}</span>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
}

// ── Invite form (lightweight inline; modal upgrade is post-pilot polish) ──

interface InviteFormProps {
  isPending: boolean;
  isError:   boolean;
  errorMessage?: string;
  onCancel:  () => void;
  onSubmit:  (body: { email: string; full_name: string; role: UserRole }) => void;
}

function InviteForm({ isPending, isError, errorMessage, onCancel, onSubmit }: InviteFormProps) {
  const t = useT();
  const [email, setEmail]       = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole]         = useState<UserRole>("ANALYST");

  return (
    <Card>
      <CardContent className="pt-6">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            onSubmit({ email: email.trim(), full_name: fullName.trim(), role });
          }}
          className="space-y-4 max-w-2xl"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <label className="space-y-1 text-small">
              <span className="text-ink-muted">{t("usersPage.email")}</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-subtle bg-surface focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
            </label>
            <label className="space-y-1 text-small">
              <span className="text-ink-muted">{t("usersPage.fullName")}</span>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3 py-2 rounded-xl border border-subtle bg-surface focus:outline-none focus:ring-2 focus:ring-brand-300"
              />
            </label>
          </div>
          <label className="block space-y-1 text-small">
            <span className="text-ink-muted">{t("usersPage.role")}</span>
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="w-full px-3 py-2 rounded-xl border border-subtle bg-surface focus:outline-none focus:ring-2 focus:ring-brand-300"
            >
              {ROLES.map((r) => <option key={r} value={r}>{roleLabel(t, r)} ({r})</option>)}
            </select>
          </label>
          {isError && (
            <p className="text-small text-danger-600">{errorMessage ?? t("usersPage.inviteFailedDefault")}</p>
          )}
          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={onCancel} disabled={isPending}>
              {t("usersPage.cancel")}
            </Button>
            <Button type="submit" loading={isPending}>
              {isPending && <Loader2 className="w-4 h-4 mr-1.5 animate-spin" />}
              {t("usersPage.sendInvite")}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
