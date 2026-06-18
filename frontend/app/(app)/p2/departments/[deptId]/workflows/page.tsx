'use client';

import { use } from 'react';
import DepartmentWorkflowsPage from '@/components/p2/templates/fnew-department-workflows';

export default function Page({ params }: { params: Promise<{ deptId: string }> }) {
  const { deptId } = use(params);
  return <DepartmentWorkflowsPage departmentId={deptId} />;
}
