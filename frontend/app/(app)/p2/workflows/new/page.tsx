'use client';

// ============================================================================
// /p2/workflows/new — Create blank workflow (P15-S11 Tuần 8).
//
// Two-field form: name (Vietnamese) + department picker. POSTs to BE then
// redirects to the builder. Template-based creation lives in the hub picker.
// ============================================================================

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Workflow, ArrowLeft, Plus, Loader2, Lock } from 'lucide-react';

import { Button, Input, ErrorBanner, api, type ProblemDetails } from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';
import { useAuth } from '@/lib/auth-store';


type DeptType = 'marketing' | 'sales' | 'customer_service' | 'warehouse' | 'hr' | 'finance' | 'custom';

const DEPT_LABEL: Record<DeptType, string> = {
  marketing: 'Marketing',
  sales: 'Sales',
  customer_service: 'CSKH',
  warehouse: 'Kho vận',
  hr: 'Nhân sự',
  finance: 'Tài chính',
  custom: 'Tùy chỉnh',
};

interface DepartmentSnapshot {
  department_id: string;
  // Real department name from the backend (org-detail). This is what the
  // picker MUST show — never a hardcoded dept_type label, which collapses
  // distinct depts (e.g. "JM" and "Kinh doanh" are both dept_type=sales).
  name?:         string;
  dept_type:     DeptType;
}


export default function NewWorkflowPage() {
  return (
    <Suspense fallback={null}>
      <NewWorkflowPageInner />
    </Suspense>
  );
}

function NewWorkflowPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Pre-filled from /p2/org-tree click-through (org-tree always sends both).
  const preDeptId    = searchParams?.get('department_id') ?? null;
  // Fall back to the signed-in user's enterprise_id when the URL param is
  // missing — landing on /p2/workflows/new directly (sidebar, deep link)
  // still needs to load the dept list.
  const userEntId    = useAuth((s) => s.user?.enterprise_id);
  const preEntId     = searchParams?.get('enterprise_id') ?? userEntId ?? null;

  const [name, setName] = useState('');
  const [nameVi, setNameVi] = useState('');
  const [description, setDescription] = useState('');
  const [departments, setDepartments] = useState<DepartmentSnapshot[]>([]);
  const [deptId, setDeptId] = useState<string>(preDeptId ?? '');
  const [loadingDepts, setLoadingDepts] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [problem, setProblem] = useState<ProblemDetails | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoadingDepts(true);
    (async () => {
      // Single outer try/finally so EVERY exit path (incl. the early return
      // on the org-detail success branch) clears the loading flag. Bug fix
      // 2026-05-24: the success branch used to `return` before
      // setLoadingDepts(false), leaving the page stuck on "Đang tải danh
      // sách phòng ban…" whenever org-detail returned 200.
      try {
        // Preferred path: when org-tree passes ?enterprise_id=, fetch the
        // enterprise's full org-detail to get real dept names + dept_types.
        if (preEntId) {
          try {
            const detail = await api<any>(`/api/v1/enterprises/${preEntId}/org-detail`);
            if (cancelled) return;
            const list = (detail.departments || []).map((d: any) => ({
              department_id: d.department_id,
              name:          d.name,
              dept_type:     (d.dept_type || 'custom') as DeptType,
            }));
            setDepartments(list);
            if (preDeptId && list.find((d: any) => d.department_id === preDeptId)) {
              setDeptId(preDeptId);
            } else if (preDeptId) {
              // Pre-supplied dept not in this enterprise's list — keep it as
              // the selected id anyway (POST validates at BE) so the form is
              // still submittable instead of silently empty.
              setDeptId(preDeptId);
            } else if (list.length > 0) {
              setDeptId(list[0].department_id);
            }
            return;
          } catch (e: any) {
            // Fall through to legacy sniff path on error.
            if (!cancelled) setProblem(e);
          }
        }

        // Fallback: sniff dept_ids from existing workflows.
        const wfs = await api<any[]>('/api/v1/workflows?limit=200');
        if (cancelled) return;
        const seen: Record<string, DepartmentSnapshot> = {};
        for (const w of wfs ?? []) {
          if (w.department_id && !seen[w.department_id]) {
            seen[w.department_id] = {
              department_id: w.department_id,
              dept_type: (w.category || '').includes('marketing') ? 'marketing' :
                          (w.category || '').includes('pipeline') || (w.category || '').includes('risk') ? 'sales' :
                          'custom',
            };
          }
        }
        const list = Object.values(seen);
        if (preDeptId && !seen[preDeptId]) {
          // Pre-supplied dept not in our sniff list (org-tree didn't pass
          // enterprise_id) — keep as raw entry; POST will validate at BE.
          list.unshift({ department_id: preDeptId, dept_type: 'custom' });
        }
        setDepartments(list);
        if (!preDeptId && list.length > 0) setDeptId(list[0].department_id);
      } catch (e: any) {
        if (!cancelled) setProblem(e);
      } finally {
        if (!cancelled) setLoadingDepts(false);
      }
    })();
    return () => { cancelled = true; };
  }, [preDeptId, preEntId]);

  async function submit() {
    if (!name || !deptId) return;
    setSubmitting(true);
    setProblem(null);
    try {
      const created = await api<any>('/api/v1/workflows', {
        method: 'POST',
        body: JSON.stringify({
          name,
          name_vi: nameVi || name,
          description: description || null,
          department_id: deptId,
        }),
      });
      router.push(`/p2/workflows/${created.workflow_id}`);
    } catch (e: any) {
      setProblem(e);
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Workflow mới"
        description="Tạo workflow trắng. Sau khi tạo, thêm từng bước và gắn tài liệu."
        actions={
          <a href="/p2/workflows">
            <Button variant="tertiary" size="md"><ArrowLeft className="w-4 h-4 mr-2" /> Quay lại</Button>
          </a>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-2xl mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}

        <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-6 shadow-soft-sm space-y-4">
          <div className="flex items-center gap-3 pb-3 border-b border-[var(--border-color)]/60">
            <div className="w-10 h-10 rounded-md-custom bg-[var(--primary-gold)]/10 flex items-center justify-center">
              <Workflow className="w-5 h-5 text-[var(--primary-gold-dark)]" />
            </div>
            <div>
              <h3 className="font-serif text-base text-[var(--text-primary)]">Thông tin workflow</h3>
              <p className="text-[11px] text-[var(--text-secondary)]">Có thể chỉnh sau khi tạo.</p>
            </div>
          </div>

          <Input
            label="Tên workflow (Tiếng Việt)"
            value={nameVi}
            onChange={(e) => setNameVi(e.target.value)}
            placeholder="VD: Quy trình thẩm định lead"
          />
          <Input
            label="Tên workflow (English / internal)"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="VD: Lead Qualification Workflow"
            required
          />

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-[var(--text-primary)] flex items-center gap-1.5">
              Phòng ban
              {preDeptId && <Lock className="w-3 h-3 text-[var(--text-secondary)]" />}
            </label>
            {loadingDepts ? (
              <p className="text-[11px] text-[var(--text-secondary)] flex items-center gap-1.5">
                <Loader2 className="w-3 h-3 animate-spin" /> Đang tải danh sách phòng ban…
              </p>
            ) : departments.length === 0 ? (
              <div className="text-[11px] text-[var(--text-secondary)] bg-[var(--bg-app)] border border-[var(--border-color)]/60 rounded-md-custom px-3 py-2">
                Doanh nghiệp chưa có phòng ban nào. Vào{' '}
                <a href="/p2/departments" className="text-[var(--primary-gold-dark)] hover:underline">
                  /p2/departments
                </a>
                {' '}tạo phòng ban trước (cần quyền MANAGER).
              </div>
            ) : (
              <select
                value={deptId}
                onChange={(e) => setDeptId(e.target.value)}
                disabled={!!preDeptId}
                className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30 disabled:bg-[var(--bg-app)] disabled:cursor-not-allowed"
              >
                {departments.map((d) => (
                  <option key={d.department_id} value={d.department_id}>
                    {/* Real dept name first; dept_type label only as a last
                        resort when name is unavailable (sniff fallback). */}
                    {d.name || DEPT_LABEL[d.dept_type] || d.dept_type}
                    {d.department_id === preDeptId ? ' (từ cây tổ chức)' : ''}
                  </option>
                ))}
              </select>
            )}
            {preDeptId && (
              <p className="text-[10px] text-[var(--text-secondary)]">
                Phòng ban đã chọn từ /p2/org-tree. Đổi phòng ban bằng cách bấm
                "Quay lại" rồi chọn phòng khác.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-[var(--text-primary)]">Mô tả</label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              placeholder="Mục tiêu workflow + ai sử dụng + tần suất chạy…"
              className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
            />
          </div>

          <div className="flex justify-end pt-3 border-t border-[var(--border-color)]/60">
            <Button variant="primary" size="md" onClick={submit} disabled={!name || !deptId || submitting}>
              {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
              Tạo workflow
            </Button>
          </div>
        </div>

        <p className="text-[11px] text-[var(--text-secondary)] text-center">
          Hoặc <a href="/p2/workflows" className="text-[var(--primary-gold-dark)] hover:underline">tạo từ template</a> để có sẵn 5 bước theo phòng ban.
        </p>
      </div>
    </>
  );
}
