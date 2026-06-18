// F-040 BE PR #144 wired GET/POST/PATCH/DELETE for OKR objectives + per-KR
// progress updates. This route mounts the wired editor; the template-mount
// version lived here previously without any BE.
import StrategyOkrPage from '@/components/p2/templates/fnew40-strategy-okr';

export default function Page() {
  return <StrategyOkrPage />;
}
