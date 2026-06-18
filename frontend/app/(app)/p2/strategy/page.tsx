// F-040 BE PR #144 wired GET /api/v1/enterprises/strategy/summary.
// /p2/strategy lives at the bare path (matching the navigation entry);
// the older /p2/strategy/hub route mounted the static template with no
// BE wire.
import StrategyHubPage from '@/components/p2/templates/fnew40-strategy-hub';

export default function Page() {
  return <StrategyHubPage />;
}
