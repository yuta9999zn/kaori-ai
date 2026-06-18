// F-034 BE PR #119 shipped /api/v1/frameworks/{templates,generate,list,detail}.
// Hub now renders the live catalogue + recent runs; legacy mock template
// 40-frameworks.tsx stays in components/ as a fallback reference.
import { FrameworksHub } from '@/components/p2/templates/f034-frameworks-wired';

export default function Page() {
  return <FrameworksHub />;
}
