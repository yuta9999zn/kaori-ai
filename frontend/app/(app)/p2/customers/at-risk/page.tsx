// F-060 BE PR #124 wired the GET /api/v1/dashboard/north-star +
// /api/v1/customers/at-risk + POST /customers/{id}/action endpoints.
// This page combines the canonical North Star tile with an at-risk
// customer list + toggle UI — one screen for the pilot CS workflow.
import CustomersAtRiskPage from '@/components/p2/templates/f060-customers-at-risk';

export default function Page() {
  return <CustomersAtRiskPage />;
}
