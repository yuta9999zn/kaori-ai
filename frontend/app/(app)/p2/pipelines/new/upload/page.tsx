import { Suspense } from 'react';
import Template from '@/components/p2/templates/20-data-pipeline-step-1-upload-file';

export default function Page() {
  return (
    <Suspense fallback={null}>
      <Template />
    </Suspense>
  );
}
