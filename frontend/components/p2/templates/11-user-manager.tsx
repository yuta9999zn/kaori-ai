// @ts-nocheck — template import; tighten types when wiring to real API
'use client';

// ============================================================================
// 11. /p2/users — Enterprise User Management (F-015)
// ----------------------------------------------------------------------------
// GET    /api/v1/enterprises/users             — list (cursor pagination)
// PATCH  /api/v1/enterprises/users/:id         — change role / status
// DELETE /api/v1/enterprises/users/:id         — remove
//
// Critical guards (PR #73):
//   K-rule: workspace must keep ≥ 1 MANAGER. Backend returns 422 with
//           problem.title = "Cần tối thiểu một MANAGER" — surface inline.
//   Suspend/Delete buttons disabled when target is the last MANAGER.
//
// Roles canonical (CLAUDE.md §9): MANAGER / OPERATOR / ANALYST / VIEWER.
// ============================================================================

import React, { useState, useEffect, useMemo } from 'react';
import {
  Search, MoreVertical, UserPlus, Download, Filter, Trash2, Ban, Edit,
  CheckCircle2, AlertCircle, X,
} from 'lucide-react';

import {
  Button, Badge, ErrorBanner,
  api, cn,
  type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
type Role   = 'MANAGER' | 'OPERATOR' | 'ANALYST' | 'VIEWER';
type Status = 'active' | 'invited' | 'suspended';

interface User {
  id:    string;
  name:  string;
  email: string;
  role:  Role;
  status: Status;
  last_active_at: string | null;
  created_at:     string;
}

const ROLE_META: Record<Role, { variant: any; label: string; desc: string }> = {
  MANAGER:  { variant: 'current', label: 'MANAGER',  desc: 'Toàn quyền — quản trị workspace, người dùng, billing' },
  OPERATOR: { variant: 'info',    label: 'OPERATOR', desc: 'Tạo + chạy pipeline, xem/sửa data' },
  ANALYST:  { variant: 'success', label: 'ANALYST',  desc: 'Sinh insight + báo cáo, không quản lý người dùng' },
  VIEWER:   { variant: 'default', label: 'VIEWER',   desc: 'Chỉ xem dashboard + báo cáo' },
};

const STATUS_META: Record<Status, { variant: any; label: string }> = {
  active:    { variant: 'success',  label: 'Đang hoạt động' },
  invited:   { variant: 'warning',  label: 'Đã mời' },
  suspended: { variant: 'error',    label: 'Đã khoá' },
};

export default function UserManager() {
  const [users,    setUsers]    = useState<User[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [problem,  setProblem]  = useState<ProblemDetails | null>(null);
  const [search,   setSearch]   = useState('');
  const [roleFilter, setRoleFilter] = useState<Role | 'all'>('all');
  const [actionFor, setActionFor]   = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState<User | null>(null);
  const [isMutating,    setIsMutating]    = useState(false);

  async function load() {
    setLoading(true);
    setProblem(null);
    try {
      const res = await api<{ data: User[] }>('/api/v1/enterprises/users?limit=200');
      setUsers(res.data ?? []);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => { load(); }, []);

  const managerCount = useMemo(
    () => users.filter((u) => u.role === 'MANAGER' && u.status === 'active').length,
    [users],
  );

  const filtered = useMemo(() => users.filter((u) => {
    if (roleFilter !== 'all' && u.role !== roleFilter) return false;
    if (search.trim()) {
      const q = search.toLowerCase();
      if (!u.name.toLowerCase().includes(q) && !u.email.toLowerCase().includes(q)) return false;
    }
    return true;
  }), [users, roleFilter, search]);

  function isLastManager(u: User): boolean {
    return u.role === 'MANAGER' && u.status === 'active' && managerCount <= 1;
  }

  async function handleRoleChange(u: User, newRole: Role) {
    setIsMutating(true);
    setProblem(null);
    try {
      const updated = await api<User>(`/api/v1/enterprises/users/${u.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ role: newRole }),
      });
      setUsers((prev) => prev.map((x) => (x.id === u.id ? updated : x)));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsMutating(false);
      setActionFor(null);
    }
  }

  async function handleSuspend(u: User) {
    setIsMutating(true);
    setProblem(null);
    try {
      const updated = await api<User>(`/api/v1/enterprises/users/${u.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ status: u.status === 'suspended' ? 'active' : 'suspended' }),
      });
      setUsers((prev) => prev.map((x) => (x.id === u.id ? updated : x)));
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsMutating(false);
      setActionFor(null);
    }
  }

  async function handleDelete(u: User) {
    setIsMutating(true);
    setProblem(null);
    try {
      await api(`/api/v1/enterprises/users/${u.id}`, { method: 'DELETE' });
      setUsers((prev) => prev.filter((x) => x.id !== u.id));
      setConfirmDelete(null);
    } catch (err: any) {
      setProblem(err);
    } finally {
      setIsMutating(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Người dùng workspace"
        description="Quản lý vai trò và quyền truy cập của từng thành viên."
        actions={
          <>
            <Button variant="secondary" onClick={() => { /* TODO: GET /api/v1/enterprises/users/export */ }}>
              <Download className="w-4 h-4 mr-2" />
              Xuất CSV
            </Button>
            <Button onClick={() => (window.location.href = '/p2/users/invite')}>
              <UserPlus className="w-4 h-4 mr-2" />
              Mời người dùng
            </Button>
          </>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-[1400px] mx-auto space-y-4">
        {managerCount === 1 && (
          <div className="rounded-md-custom bg-[var(--state-warning)]/10 border border-[var(--state-warning)]/30 p-3 flex items-start gap-3 text-sm text-[#9E814D]">
            <AlertCircle className="w-5 h-5 shrink-0 mt-0.5 text-[var(--state-warning)]" />
            <div>
              <p className="font-medium">Workspace chỉ còn duy nhất 1 MANAGER.</p>
              <p className="opacity-90 mt-0.5">
                Không thể xoá hoặc giáng cấp người này. Mời thêm MANAGER trước nếu cần thay đổi.
              </p>
            </div>
          </div>
        )}

        <ErrorBanner problem={problem} />

        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-[var(--text-secondary)] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Tìm theo tên hoặc email..."
              className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom pl-9 pr-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 focus:border-[var(--primary-gold)]"
            />
          </div>
          <select
            value={roleFilter}
            onChange={(e) => setRoleFilter(e.target.value as any)}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
          >
            <option value="all">Tất cả vai trò</option>
            {(Object.keys(ROLE_META) as Role[]).map((r) => (
              <option key={r} value={r}>{r}</option>
            ))}
          </select>
        </div>

        <div className="bg-[var(--bg-card)] rounded-lg-custom border border-[var(--border-color)] overflow-hidden shadow-soft-sm">
          {loading ? (
            <div className="p-6 space-y-3">
              {[1,2,3,4].map((i) => (
                <div key={i} className="h-14 rounded-md-custom bg-[var(--bg-app)]/60 animate-pulse" />
              ))}
            </div>
          ) : filtered.length === 0 ? (
            <p className="p-12 text-center text-[var(--text-secondary)]">Không có người dùng nào khớp bộ lọc.</p>
          ) : (
            <table className="w-full">
              <thead className="bg-[var(--bg-app)]/50 border-b border-[var(--border-color)]">
                <tr>
                  <Th>Người dùng</Th>
                  <Th>Vai trò</Th>
                  <Th>Trạng thái</Th>
                  <Th>Hoạt động cuối</Th>
                  <Th>Tham gia</Th>
                  <Th><span className="sr-only">Hành động</span></Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-color)]/60">
                {filtered.map((u) => {
                  const lastMgr = isLastManager(u);
                  const meta = ROLE_META[u.role];
                  const statusMeta = STATUS_META[u.status];
                  return (
                    <tr key={u.id} className="hover:bg-[var(--bg-app)]/40 transition-colors">
                      <Td>
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-full bg-[var(--primary-gold)]/15 flex items-center justify-center text-xs font-semibold text-[var(--primary-gold-dark)]">
                            {u.email.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-[var(--text-primary)]">{u.name}</p>
                            <p className="text-xs text-[var(--text-secondary)]">{u.email}</p>
                          </div>
                        </div>
                      </Td>
                      <Td>
                        <Badge variant={meta.variant}>{meta.label}</Badge>
                        {lastMgr && (
                          <p className="text-[10px] text-[#9E814D] mt-1">MANAGER duy nhất</p>
                        )}
                      </Td>
                      <Td><Badge variant={statusMeta.variant}>{statusMeta.label}</Badge></Td>
                      <Td className="text-sm text-[var(--text-secondary)]">
                        {u.last_active_at ?? '—'}
                      </Td>
                      <Td className="text-sm text-[var(--text-secondary)]">{u.created_at}</Td>
                      <Td>
                        <div className="relative">
                          <Button
                            variant="tertiary"
                            size="sm"
                            onClick={() => setActionFor(actionFor === u.id ? null : u.id)}
                            disabled={isMutating}
                          >
                            <MoreVertical className="w-4 h-4" />
                          </Button>
                          {actionFor === u.id && (
                            <div className="absolute right-0 top-full mt-1 w-56 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-md-custom shadow-soft-md py-1 z-20 animate-slide-up-fade">
                              <a href={`/p2/users/${u.id}`} className="flex items-center px-3 py-2 text-sm hover:bg-[var(--bg-app)]">
                                <Edit className="w-4 h-4 mr-2 text-[var(--text-secondary)]" /> Xem chi tiết
                              </a>
                              <div className="border-t border-[var(--border-color)]/60 my-1" />
                              <p className="px-3 py-1 text-[10px] uppercase tracking-wider text-[var(--text-secondary)]">Đổi vai trò</p>
                              {(Object.keys(ROLE_META) as Role[]).map((r) => (
                                <button
                                  key={r}
                                  disabled={r === u.role || (lastMgr && r !== 'MANAGER')}
                                  onClick={() => handleRoleChange(u, r)}
                                  className="w-full flex items-center px-3 py-2 text-sm hover:bg-[var(--bg-app)] disabled:opacity-40 disabled:cursor-not-allowed"
                                >
                                  {r === u.role && <CheckCircle2 className="w-3.5 h-3.5 mr-2 text-[var(--primary-gold-dark)]" />}
                                  <span className={r !== u.role ? 'ml-[22px]' : ''}>{r}</span>
                                </button>
                              ))}
                              <div className="border-t border-[var(--border-color)]/60 my-1" />
                              <button
                                onClick={() => handleSuspend(u)}
                                disabled={lastMgr && u.status === 'active'}
                                className="w-full flex items-center px-3 py-2 text-sm hover:bg-[var(--bg-app)] disabled:opacity-40 disabled:cursor-not-allowed text-[#9E814D]"
                              >
                                <Ban className="w-4 h-4 mr-2" />
                                {u.status === 'suspended' ? 'Bỏ khoá' : 'Khoá tài khoản'}
                              </button>
                              <button
                                onClick={() => { setConfirmDelete(u); setActionFor(null); }}
                                disabled={lastMgr}
                                className="w-full flex items-center px-3 py-2 text-sm hover:bg-[var(--state-error)]/10 disabled:opacity-40 disabled:cursor-not-allowed text-[var(--state-error)]"
                              >
                                <Trash2 className="w-4 h-4 mr-2" />
                                Xoá
                              </button>
                            </div>
                          )}
                        </div>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Delete confirm modal */}
      {confirmDelete && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6 bg-black/30 backdrop-blur-sm" onClick={() => setConfirmDelete(null)}>
          <div className="bg-[var(--bg-card)] rounded-lg-custom shadow-soft-lg border border-[var(--border-color)] w-full max-w-[440px] p-6" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between mb-4">
              <h3 className="font-serif text-lg text-[var(--text-primary)]">Xoá người dùng?</h3>
              <button onClick={() => setConfirmDelete(null)} className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-sm text-[var(--text-secondary)] mb-6">
              <span className="font-medium text-[var(--text-primary)]">{confirmDelete.name}</span> sẽ mất toàn bộ quyền truy cập workspace.
              Hành động này không thể hoàn tác.
            </p>
            <div className="flex justify-end gap-3">
              <Button variant="secondary" onClick={() => setConfirmDelete(null)} disabled={isMutating}>Huỷ</Button>
              <Button variant="destructive" onClick={() => handleDelete(confirmDelete)} isLoading={isMutating}>Xoá</Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Th({ children }: any) {
  return <th className="px-5 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{children}</th>;
}
function Td({ children, className }: any) {
  return <td className={cn('px-5 py-3', className)}>{children}</td>;
}
