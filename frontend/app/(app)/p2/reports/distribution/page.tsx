// F-038 distribution BE PR #118 shipped /api/v1/reports/{id}/distribute +
// /api/v1/reports/{id}/distributions. The legacy mock template (51-) imagined
// a fuller cron + role-groups + format scope — those land in v1 and stay in
// components/ as a reference. This route now serves the wired one-shot
// manual distribute flow.
import Template from '@/components/p2/templates/51b-report-distribution-wired';

export default function Page() {
  return <Template />;
}
