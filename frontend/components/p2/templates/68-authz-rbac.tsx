// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 68. /p2/authz/rbac — RBAC Member & Role Management (F-007 ✅ Phase 1)
// ----------------------------------------------------------------------------
// PHASE 1 CRITICAL — wires real endpoints (KHÔNG placeholder):
//   GET    /api/v1/users                         (list members + role)
//   POST   /api/v1/users/invite                  (invite by email)
//   PATCH  /api/v1/users/{id}                    (change role / suspend)
//   DELETE /api/v1/users/{id}                    (remove from workspace)
//
// 4 P2 roles (CLAUDE.md §9):
//   MANAGER    — full admin + ≥1 required per enterprise (min-1-MANAGER guard)
//   OPERATOR   — run pipelines, edit alerts, manage workflows
//   ANALYST    — read-write on Insights/Decisions, read-only on settings
//   VIEWER     — read-only everything
//
// Critical UI guards:
//   K-12  — never accept user_id from query string (operations use path param,
//            tenant comes from JWT)
//   Min-1-MANAGER — UI prevents demoting the LAST MANAGER (server enforces too;
//                    409 problem+json if bypassed)
//   K-13  — Idempotency-Key header (handled by `api()` helper) on POST/PATCH/DELETE
//   K-14  — RFC 7807 Problem Details surfaced via ErrorBanner
// ============================================================================

import React, { useEffect, useState, useMemo } from 'react';
import {
  Shield, UserPlus, Mail, MoreVertical, Trash2, Ban, RefreshCw,
  ShieldCheck, AlertTriangle, Search, X, CheckCircle2, Lock,
  Crown, Wrench, FlaskConical, Eye,
} from 'lucide-react';

import {
  Button, Badge, Input, ErrorBanner, SuccessBanner, cn,
  api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Role  = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';
type State = 'active' | 'invited' | 'suspended';

interface Member {
  id:               string;
  email:            string;
  display_name?:    string;
  role:             Role;
  state:            State;
  created_at:       string;
  last_active_at?:  string;
  is_self?:         boolean;
}

interface MeContext {
  id:    string;
  role:  Role;
}

const ROLE_META: Record<Role, { label: string; icon: any; tone: 'current' | 'success' | 'info' | 'default'; description: string }> = {
  MANAGER:  { label: 'MANAGER',  icon: Crown,        tone: 'current', description: 'Toàn quyền — quản trị member, gói cước, tích hợp. Mỗi workspace cần ≥ 1 MANAGER.' },
  OPERATOR: { label: 'OPERATOR', icon: Wrench,       tone: 'success', description: 'Chạy pipeline, edit cảnh báo, quản lý workflow.' },
  ANALYST:  { label: 'ANALYST',  icon: FlaskConical, tone: 'info',    description: 'Đọc/ghi insight + decision. Chỉ-đọc cài đặt + billing.' },
  VIEWER:   { label: 'VIEWER',   icon: Eye,          tone: 'default', description: 'Chỉ-đọc mọi thứ — phù hợp stakeholder ngoài team data.' },
};

const STATE_META: Record<State, { label: string; tone: 'success' | 'warning' | 'error' | 'default' }> = {
  active:    { label: 'Hoạt động', tone: 'success' },
  invited:   { label: 'Chờ xác nhận', tone: 'warning' },
  suspended: { label: 'Tạm khoá', tone: 'error' },
};

// There is no /api/v1/me endpoint — the JWT already carries who we are
// (sub = user_id, role). Decode it from the canonical token key.
function readMeFromToken(): MeContext | null {
  try {
    const tok = typeof window !== 'undefined'
      ? window.localStorage.getItem('kaori.access_token') : null;
    if (!tok) return null;
    const payload = JSON.parse(
      atob(tok.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')),
    );
    return { id: payload.sub, role: payload.role as Role };
  } catch { return null; }
}

// auth-service EnterpriseUserController returns {meta, data:[…]} with snake_case
// fields (full_name/status/last_login_at) — map to the FE Member shape.
function mapMember(d: any, meId: string): Member {
  const id = d.user_id ?? d.id;
  const state: State = d.status === 'invited' ? 'invited'
    : d.status === 'suspended' ? 'suspended' : 'active';
  return {
    id, email: d.email, display_name: d.full_name,
    role: d.role as Role, state,
    created_at: d.created_at, last_active_at: d.last_login_at,
    is_self: id === meId,
  };
}

export default function RbacPage() {
  const [me,        setMe]        = useState<MeContext | null>(null);
  const [members,   setMembers]   = useState<Member[]>([]);
  const [loading,   setLoading]   = useState(true);
  const [problem,   setProblem]   = useState<ProblemDetails | null>(null);
  const [success,   setSuccess]   = useState<string | null>(null);

  const [search,    setSearch]    = useState('');
  const [roleFilter, setRoleFilter] = useState<'ALL' | Role>('ALL');
  const [showInvite, setShowInvite] = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const meCtx = readMeFromToken();
      const listRes = await api<{ data: any[] }>('/api/v1/enterprises/users?limit=200');
      const meId = meCtx?.id ?? '';
      const mapped = (listRes.data ?? [])
        .filter((d) => (d.status ?? 'active') !== 'deleted')
        .map((d) => mapMember(d, meId));
      setMe(meCtx);
      setMembers(mapped);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  const isManager = me?.role === 'MANAGER';

  const managerCount = useMemo(
    () => members.filter((m) => m.role === 'MANAGER' && m.state === 'active').length,
    [members],
  );

  const filtered = useMemo(() => {
    return members.filter((m) => {
      if (roleFilter !== 'ALL' && m.role !== roleFilter) return false;
      if (search.trim()) {
        const q = search.trim().toLowerCase();
        if (!m.email.toLowerCase().includes(q) && !(m.display_name ?? '').toLowerCase().includes(q)) return false;
      }
      return true;
    });
  }, [members, roleFilter, search]);

  async function changeRole(member: Member, nextRole: Role) {
    if (nextRole === member.role) return;
    // Min-1-MANAGER guard (client-side; server is authoritative)
    if (member.role === 'MANAGER' && nextRole !== 'MANAGER' && managerCount <= 1) {
      setProblem({
        title:  'Không thể hạ vai trò',
        detail: 'Workspace cần ít nhất 1 MANAGER hoạt động. Chỉ định MANAGER mới trước khi hạ vai trò người này.',
        status: 409,
      });
      return;
    }
    setProblem(null);
    try {
      await api(`/api/v1/enterprises/users/${member.id}`, {
        method: 'PATCH',
        body:   JSON.stringify({ role: nextRole }),
      });
      setMembers((prev) => prev.map((m) => m.id === member.id ? { ...m, role: nextRole } : m));
      setSuccess(`Đã đổi vai trò ${member.email} → ${nextRole}`);
    } catch (err: any) {
      setProblem(err);
    }
  }

  async function suspend(member: Member) {
    if (member.role === 'MANAGER' && managerCount <= 1) {
      setProblem({
        title:  'Không thể khoá MANAGER cuối cùng',
        detail: 'Hãy chỉ định MANAGER khác trước khi khoá người này.',
        status: 409,
      });
      return;
    }
    if (!confirm(`Tạm khoá ${member.email}? Họ sẽ không đăng nhập được cho đến khi mở lại.`)) return;
    try {
      await api(`/api/v1/enterprises/users/${member.id}`, {
        method: 'PATCH',
        body:   JSON.stringify({ status: 'suspended' }),
      });
      setMembers((prev) => prev.map((m) => m.id === member.id ? { ...m, state: 'suspended' } : m));
      setSuccess(`Đã tạm khoá ${member.email}`);
    } catch (err: any) {
      setProblem(err);
    }
  }

  async function reactivate(member: Member) {
    try {
      await api(`/api/v1/enterprises/users/${member.id}`, {
        method: 'PATCH',
        body:   JSON.stringify({ status: 'active' }),
      });
      setMembers((prev) => prev.map((m) => m.id === member.id ? { ...m, state: 'active' } : m));
      setSuccess(`Đã mở lại ${member.email}`);
    } catch (err: any) {
      setProblem(err);
    }
  }

  async function remove(member: Member) {
    if (member.is_self) {
      setProblem({ title: 'Không thể tự xoá', detail: 'Bạn không thể tự xoá khỏi workspace.', status: 409 });
      return;
    }
    if (member.role === 'MANAGER' && managerCount <= 1) {
      setProblem({
        title:  'Không thể xoá MANAGER cuối cùng',
        detail: 'Hãy chỉ định MANAGER khác trước khi xoá người này.',
        status: 409,
      });
      return;
    }
    if (!confirm(`Xoá ${member.email} khỏi workspace? Hành động này không thể hoàn tác.`)) return;
    try {
      await api(`/api/v1/enterprises/users/${member.id}`, { method: 'DELETE' });  // soft-delete → status='deleted'
      setMembers((prev) => prev.filter((m) => m.id !== member.id));
      setSuccess(`Đã xoá ${member.email} khỏi workspace`);
    } catch (err: any) {
      setProblem(err);
    }
  }

  return (
    <>
      <PageHeader
        title="RBAC · Vai trò & thành viên"
        description="Quản lý 4 vai trò chuẩn cho workspace. Chỉ MANAGER chỉnh sửa được."
        actions={
          <>
            <Button variant="secondary" onClick={load}>
              <RefreshCw className="w-4 h-4 mr-2" />
              Làm mới
            </Button>
            {isManager && (
              <Button onClick={() => setShowInvite(true)}>
                <UserPlus className="w-4 h-4 mr-2" />
                Mời thành viên
              </Button>
            )}
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1300px] mx-auto space-y-5">
        <ErrorBanner problem={problem} />
        {success && <SuccessBanner message={success} />}

        {/* Min-1-MANAGER guard banner */}
        {managerCount === 1 && (
          <div className="bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 rounded-md-custom p-3 flex items-start gap-3">
            <AlertTriangle className="w-4 h-4 text-[var(--state-warning)] shrink-0 mt-0.5" />
            <p className="text-sm text-[#9E814D]">
              <span className="font-medium text-[var(--text-primary)]">Cảnh báo min-1-MANAGER:</span> workspace chỉ còn 1 MANAGER hoạt động.
              Hệ thống sẽ chặn mọi thao tác hạ/khoá/xoá người này (HTTP 409).
            </p>
          </div>
        )}

        {!isManager && (
          <div className="bg-[var(--bg-app)]/40 border border-[var(--border-color)] rounded-md-custom p-3 flex items-start gap-2">
            <Lock className="w-4 h-4 text-[var(--text-secondary)] shrink-0 mt-0.5" />
            <p className="text-xs text-[var(--text-secondary)]">
              Bạn đang ở vai trò <span className="font-medium text-[var(--text-primary)]">{me?.role}</span>. Chỉ MANAGER mới có thể mời, đổi vai trò, hoặc xoá thành viên.
            </p>
          </div>
        )}

        {/* Role legend */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {(Object.keys(ROLE_META) as Role[]).map((r) => {
            const meta  = ROLE_META[r];
            const Icon  = meta.icon;
            const count = members.filter((m) => m.role === r).length;
            return (
              <div key={r} className="bg-[var(--bg-card)] rounded-md-custom border border-[var(--border-color)] p-3 shadow-soft-sm">
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    <div className="w-7 h-7 rounded-sm-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
                      <Icon className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />
                    </div>
                    <Badge variant={meta.tone}>{meta.label}</Badge>
                  </div>
                  <span className="font-serif text-base text-[var(--text-primary)]">{count}</span>
                </div>
                <p className="text-[11px] text-[var(--text-secondary)] leading-snug">{meta.description}</p>
              </div>
            );
          })}
        </div>

        {/* Filter bar */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] p-3 shadow-soft-sm flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-secondary)]" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo email hoặc tên..."
              className="w-full pl-9 pr-4 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as any)}
            className="px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-xs font-medium focus:outline-none"
          >
            <option value="ALL">Mọi vai trò</option>
            {(Object.keys(ROLE_META) as Role[]).map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        {/* Member table */}
        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-sm overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]/60">
                <tr>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Thành viên</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-44">Vai trò</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-32">Trạng thái</th>
                  <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-44">Hoạt động gần nhất</th>
                  <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)] w-20" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {loading && members.length === 0 ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} className="px-4 py-3"><div className="h-8 bg-[var(--bg-app)] rounded-sm-custom animate-pulse" /></td>
                    </tr>
                  ))
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-12 text-center text-[var(--text-secondary)]">
                      <Shield className="w-10 h-10 mx-auto mb-2 text-[var(--text-secondary)]/40" />
                      Không có thành viên phù hợp.
                    </td>
                  </tr>
                ) : filtered.map((m) => (
                  <MemberRow
                    key={m.id}
                    member={m}
                    isManager={isManager}
                    isLastManager={m.role === 'MANAGER' && managerCount <= 1}
                    onChangeRole={(r) => changeRole(m, r)}
                    onSuspend={() => suspend(m)}
                    onReactivate={() => reactivate(m)}
                    onRemove={() => remove(m)}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Invariant footer */}
        <div className="flex items-start gap-2 p-3 rounded-md-custom bg-[var(--bg-app)]/40 border border-[var(--border-color)] text-xs text-[var(--text-secondary)]">
          <ShieldCheck className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
          <p>
            <span className="font-medium text-[var(--text-primary)]">K-12:</span> Mọi thao tác lấy <span className="font-mono">user_id</span> từ path param, không bao giờ từ query string.
            <span className="font-medium text-[var(--text-primary)]"> K-13:</span> Idempotency-Key tự thêm vào mọi POST/PATCH/DELETE (TTL 24h Redis).
            <span className="font-medium text-[var(--text-primary)]"> K-14:</span> Lỗi server trả về <span className="font-mono">application/problem+json</span>, hiển thị qua ErrorBanner.
          </p>
        </div>
      </div>

      {showInvite && isManager && (
        <InviteModal
          onClose={() => setShowInvite(false)}
          onSuccess={(msg) => { setSuccess(msg); load(); }}
          onError={setProblem}
        />
      )}
    </>
  );
}

// ----------------------------------------------------------------------------
// MemberRow
// ----------------------------------------------------------------------------

function MemberRow({
  member: m, isManager, isLastManager,
  onChangeRole, onSuspend, onReactivate, onRemove,
}: {
  member: Member;
  isManager: boolean;
  isLastManager: boolean;
  onChangeRole: (r: Role) => void;
  onSuspend: () => void;
  onReactivate: () => void;
  onRemove: () => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);
  const roleMeta  = ROLE_META[m.role];
  const stateMeta = STATE_META[m.state];

  return (
    <tr className="hover:bg-[var(--bg-app)]/30">
      <td className="px-4 py-3 align-top">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-[var(--primary-gold)]/15 border border-[var(--primary-gold)]/30 flex items-center justify-center">
            <span className="text-xs font-semibold text-[var(--primary-gold-dark)]">{(m.display_name ?? m.email).slice(0, 2).toUpperCase()}</span>
          </div>
          <div>
            <p className="font-medium text-sm text-[var(--text-primary)]">
              {m.display_name ?? m.email.split('@')[0]}
              {m.is_self && <Badge variant="default" className="ml-2">bạn</Badge>}
            </p>
            <p className="text-xs text-[var(--text-secondary)]">{m.email}</p>
          </div>
        </div>
      </td>
      <td className="px-4 py-3 align-top">
        {isManager && !m.is_self ? (
          <select
            value={m.role}
            onChange={(e) => onChangeRole(e.target.value as Role)}
            disabled={isLastManager && m.role === 'MANAGER'}
            className="px-2 py-1.5 bg-white border border-[var(--border-color)] rounded-sm-custom text-xs focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:opacity-60 disabled:cursor-not-allowed"
            title={isLastManager && m.role === 'MANAGER' ? 'Không thể hạ MANAGER cuối cùng' : ''}
          >
            {(Object.keys(ROLE_META) as Role[]).map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        ) : (
          <Badge variant={roleMeta.tone}>
            <roleMeta.icon className="w-3 h-3 mr-1 inline" />
            {roleMeta.label}
          </Badge>
        )}
      </td>
      <td className="px-4 py-3 align-top">
        <Badge variant={stateMeta.tone}>{stateMeta.label}</Badge>
      </td>
      <td className="px-4 py-3 align-top text-xs text-[var(--text-secondary)] whitespace-nowrap">
        {m.last_active_at ?? '—'}
      </td>
      <td className="px-4 py-3 align-top text-right">
        {isManager && !m.is_self && (
          <div className="relative inline-block">
            <button
              type="button"
              onClick={() => setMenuOpen(!menuOpen)}
              className="p-1.5 rounded-sm-custom text-[var(--text-secondary)] hover:bg-[var(--bg-app)] hover:text-[var(--text-primary)]"
              aria-label="Thao tác khác"
            >
              <MoreVertical className="w-4 h-4" />
            </button>
            {menuOpen && (
              <div className="absolute right-0 top-full mt-1 w-44 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom shadow-soft-md py-1 z-20 animate-slide-up-fade">
                {m.state === 'active' ? (
                  <button
                    onClick={() => { onSuspend(); setMenuOpen(false); }}
                    className="w-full text-left px-3 py-2 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-app)] inline-flex items-center"
                  >
                    <Ban className="w-3.5 h-3.5 mr-2 text-[var(--state-warning)]" />
                    Tạm khoá
                  </button>
                ) : m.state === 'suspended' ? (
                  <button
                    onClick={() => { onReactivate(); setMenuOpen(false); }}
                    className="w-full text-left px-3 py-2 text-xs text-[var(--text-primary)] hover:bg-[var(--bg-app)] inline-flex items-center"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5 mr-2 text-[var(--state-success)]" />
                    Mở khoá lại
                  </button>
                ) : null}
                <button
                  onClick={() => { onRemove(); setMenuOpen(false); }}
                  className="w-full text-left px-3 py-2 text-xs text-[var(--state-error)] hover:bg-[var(--state-error)]/8 inline-flex items-center"
                >
                  <Trash2 className="w-3.5 h-3.5 mr-2" />
                  Xoá khỏi workspace
                </button>
              </div>
            )}
          </div>
        )}
      </td>
    </tr>
  );
}

// ----------------------------------------------------------------------------
// InviteModal
// ----------------------------------------------------------------------------

function InviteModal({
  onClose, onSuccess, onError,
}: {
  onClose:  () => void;
  onSuccess: (msg: string) => void;
  onError:   (p: ProblemDetails) => void;
}) {
  const [email,    setEmail]    = useState('');
  const [role,     setRole]     = useState<Role>('VIEWER');
  const [sending,  setSending]  = useState(false);

  async function send() {
    if (!email.trim()) return;
    setSending(true);
    try {
      await api('/api/v1/enterprises/users', {
        method: 'POST',
        body:   JSON.stringify({
          email: email.trim(),
          role,
          full_name: email.trim().split('@')[0],  // sensible default; full_name optional on BE
        }),
      });
      onSuccess(`Đã gửi lời mời tới ${email.trim()} với vai trò ${role}`);
      onClose();
    } catch (err: any) {
      onError(err);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-[var(--text-primary)]/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] shadow-soft-lg w-full max-w-md p-5 animate-slide-up-fade">
        <div className="flex items-center justify-between mb-1">
          <h3 className="font-serif text-lg text-[var(--text-primary)]">Mời thành viên</h3>
          <button onClick={onClose} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"><X className="w-4 h-4" /></button>
        </div>
        <p className="text-xs text-[var(--text-secondary)] mb-4">
          Lời mời gửi qua email (notification-service · F-NEW1). Người được mời cần xác nhận trước khi vào workspace.
        </p>

        <div className="space-y-3">
          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">Email</label>
            <div className="relative mt-1">
              <Mail className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="ten@cong-ty.com"
                className="w-full pl-9 pr-3 py-2 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              />
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-[var(--text-primary)]">Vai trò</label>
            <div className="mt-1.5 space-y-1.5">
              {(Object.keys(ROLE_META) as Role[]).map((r) => {
                const meta = ROLE_META[r];
                const Icon = meta.icon;
                const isActive = role === r;
                return (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setRole(r)}
                    className={cn(
                      'w-full text-left p-3 rounded-md-custom border transition-colors',
                      isActive
                        ? 'border-[var(--primary-gold)] bg-[var(--primary-gold)]/5'
                        : 'border-[var(--border-color)] bg-[var(--bg-card)] hover:border-[var(--primary-gold)]/40',
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <Icon className="w-4 h-4 text-[var(--primary-gold-dark)] shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-sm text-[var(--text-primary)]">{meta.label}</p>
                          {isActive && <CheckCircle2 className="w-3.5 h-3.5 text-[var(--primary-gold-dark)]" />}
                        </div>
                        <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 leading-snug">{meta.description}</p>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        <div className="mt-5 flex items-center gap-2 justify-end">
          <Button variant="tertiary" onClick={onClose} disabled={sending}>Huỷ</Button>
          <Button onClick={send} isLoading={sending} disabled={!email.trim()}>
            <UserPlus className="w-4 h-4 mr-2" />
            Gửi lời mời
          </Button>
        </div>
      </div>
    </div>
  );
}
