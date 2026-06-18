// F-NEW3 v1 BE PR #148 wired GET /api/v1/data/gold/customers (paginated,
// optional ?actioned=true|false). This route is the analyst browse view;
// /p2/customers/at-risk (F-060) is the focused workflow with action toggle.
import GoldDrillDownPage from '@/components/p2/templates/fnew3v1-gold';

export default function Page() {
  return <GoldDrillDownPage />;
}
