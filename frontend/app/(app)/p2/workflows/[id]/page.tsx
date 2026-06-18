'use client';

import { useParams } from 'next/navigation';
import WorkflowDetailPage from '@/components/p2/templates/60-workflow-detail';

export default function Page() {
  const params = useParams();
  const id = typeof params?.id === 'string' ? params.id : Array.isArray(params?.id) ? params.id[0] : '';
  return <WorkflowDetailPage workflowId={id} />;
}
