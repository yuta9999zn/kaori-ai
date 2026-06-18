'use client';

// ============================================================================
// /p2/departments — Department list + create (MANAGER UX gap fill).
//
// Pilot blocker: register flow creates Workspace + Enterprise + MANAGER, but
// there was no UX to create departments under that enterprise. /p2/workflows/new
// kept its picker stuck on "Đang tải…" because no row existed. This page is
// the missing piece — list dept + form to create more.
//
// BE: GET/POST /api/v1/departments  (ai-orchestrator workflow_builder router)
// ============================================================================

import { useEffect, useState } from 'react';
import { Plus, Loader2, Users, X, Workflow as WorkflowIcon, ShieldAlert } from 'lucide-react';

import {
  Button, Input, ErrorBanner, Badge, api, type ProblemDetails,
} from '@/components/p2/foundation';
import { PageHeader } from '@/components/p2/shell';

type DeptType = 'marketing' | 'sales' | 'customer_service' | 'warehouse' | 'hr' | 'finance' | 'custom';
type PiiLevel = 'low' | 'normal' | 'high' | 'restricted';

const DEPT_LABEL: Record<DeptType, string> = {
  marketing:        'Marketing',
  sales:            'Kinh doanh',
  customer_service: 'Chăm sóc khách hàng',
  warehouse:        'Kho vận',
  hr:               'Nhân sự',
  finance:          'Tài chính',
  custom:           'Tùy chỉnh',
};

const PII_LABEL: Record<PiiLevel, string> = {
  low:        'Thấp',
  normal:     'Bình thường',
  high:       'Cao',
  restricted: 'Hạn chế',
};

const PII_VARIANT: Record<PiiLevel, 'default' | 'info' | 'warning' | 'error'> = {
  low:        'default',
  normal:     'info',
  high:       'warning',
  restricted: 'error',
};

interface Department {
  department_id:   string;
  name:            string;
  dept_type:       DeptType;
  status:          string;
  description?:    string | null;
  pii_sensitivity: PiiLevel;
  workflow_count:  number;
  created_at:      string;
}

export default function DepartmentsPage() {
  const [list,       setList]       = useState<Department[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [problem,    setProblem]    = useState<ProblemDetails | null>(null);

  const [open,       setOpen]       = useState(false);
  const [name,       setName]       = useState('');
  const [deptType,   setDeptType]   = useState<DeptType>('sales');
  const [pii,        setPii]        = useState<PiiLevel>('normal');
  const [description,setDescription]= useState('');
  const [submitting, setSubmitting] = useState(false);
  const [createErr,  setCreateErr]  = useState<ProblemDetails | null>(null);

  async function refresh() {
    setLoading(true);
    setProblem(null);
    try {
      const data = await api<Department[]>('/api/v1/departments');
      setList(data ?? []);
    } catch (e: any) {
      setProblem(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { refresh(); }, []);

  async function submit() {
    if (!name.trim()) return;
    setSubmitting(true);
    setCreateErr(null);
    try {
      await api('/api/v1/departments', {
        method: 'POST',
        body: JSON.stringify({
          name:            name.trim(),
          dept_type:       deptType,
          pii_sensitivity: pii,
          description:     description.trim() || null,
        }),
      });
      setName('');
      setDescription('');
      setDeptType('sales');
      setPii('normal');
      setOpen(false);
      await refresh();
    } catch (e: any) {
      setCreateErr(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Phòng ban"
        description="Cơ cấu phòng ban của doanh nghiệp. Mỗi phòng ban có thể có nhiều workflow."
        actions={
          <Button variant="primary" size="md" onClick={() => setOpen(true)}>
            <Plus className="w-4 h-4 mr-2" /> Tạo phòng ban
          </Button>
        }
      />

      <div className="px-6 lg:px-8 py-6 max-w-5xl mx-auto space-y-4">
        {problem && <ErrorBanner problem={problem} />}

        {loading ? (
          <p className="text-[12px] text-[var(--text-secondary)] flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin" /> Đang tải danh sách phòng ban…
          </p>
        ) : list.length === 0 ? (
          <div className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-8 text-center">
            <Users className="w-8 h-8 mx-auto text-[var(--text-secondary)] mb-2" />
            <p className="text-sm text-[var(--text-primary)] mb-1">Chưa có phòng ban nào</p>
            <p className="text-[12px] text-[var(--text-secondary)] mb-4">
              Tạo phòng ban đầu tiên để bắt đầu xây workflow theo từng bộ phận.
            </p>
            <Button variant="primary" size="md" onClick={() => setOpen(true)}>
              <Plus className="w-4 h-4 mr-2" /> Tạo phòng ban đầu tiên
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {list.map((d) => (
              <div
                key={d.department_id}
                className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg-custom p-4 shadow-soft-sm hover:shadow-soft-md transition-shadow"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h4 className="font-medium text-[var(--text-primary)]">{d.name}</h4>
                    <p className="text-[11px] text-[var(--text-secondary)]">
                      {DEPT_LABEL[d.dept_type] || d.dept_type}
                    </p>
                  </div>
                  <Badge variant={PII_VARIANT[d.pii_sensitivity]}>
                    <ShieldAlert className="w-3 h-3 inline mr-1" />
                    PII: {PII_LABEL[d.pii_sensitivity]}
                  </Badge>
                </div>
                {d.description && (
                  <p className="text-[12px] text-[var(--text-secondary)] mb-2 line-clamp-2">
                    {d.description}
                  </p>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-[var(--border-color)]/60">
                  <span className="text-[11px] text-[var(--text-secondary)] flex items-center gap-1">
                    <WorkflowIcon className="w-3 h-3" /> {d.workflow_count} workflow
                  </span>
                  <a
                    href={`/p2/workflows/new?department_id=${d.department_id}`}
                    className="text-[11px] text-[var(--primary-gold-dark)] hover:underline"
                  >
                    + Workflow
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => !submitting && setOpen(false)}
        >
          <div
            className="bg-[var(--bg-card)] rounded-lg-custom shadow-soft-lg max-w-md w-full p-6 space-y-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between">
              <h3 className="font-serif text-base text-[var(--text-primary)]">Tạo phòng ban mới</h3>
              <button
                onClick={() => !submitting && setOpen(false)}
                className="text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {createErr && <ErrorBanner problem={createErr} />}

            <Input
              label="Tên phòng ban"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="VD: Phòng kinh doanh khu vực miền Bắc"
              required
            />

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-[var(--text-primary)]">
                Loại phòng ban <span className="text-[var(--accent-red)]">*</span>
              </label>
              <select
                value={deptType}
                onChange={(e) => setDeptType(e.target.value as DeptType)}
                className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                {(Object.keys(DEPT_LABEL) as DeptType[]).map((k) => (
                  <option key={k} value={k}>{DEPT_LABEL[k]}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-[var(--text-primary)]">
                Mức độ nhạy cảm PII
              </label>
              <select
                value={pii}
                onChange={(e) => setPii(e.target.value as PiiLevel)}
                className="w-full h-10 px-3 bg-white border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              >
                {(Object.keys(PII_LABEL) as PiiLevel[]).map((k) => (
                  <option key={k} value={k}>{PII_LABEL[k]}</option>
                ))}
              </select>
              <p className="text-[10px] text-[var(--text-secondary)]">
                Phòng có nhiều dữ liệu cá nhân (CSKH, HR) nên đặt "Cao". Marketing thường đặt "Thấp".
              </p>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium text-[var(--text-primary)]">Mô tả</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                placeholder="Mục tiêu của phòng ban, phạm vi công việc…"
                className="w-full px-3 py-2 bg-[var(--bg-app)] border border-[var(--border-color)] rounded-md-custom text-sm focus:outline-none focus:ring-2 focus:ring-[var(--primary-gold)]/30"
              />
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[var(--border-color)]/60">
              <Button variant="tertiary" size="md" onClick={() => setOpen(false)} disabled={submitting}>
                Huỷ
              </Button>
              <Button variant="primary" size="md" onClick={submit} disabled={!name.trim() || submitting}>
                {submitting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Plus className="w-4 h-4 mr-2" />}
                Tạo
              </Button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
