// F-037 (PR #116) shipped the alert_rules CRUD + billing-quota dispatcher
// backend, so /p2/alerts now points at the F-037 page (rules + events
// history). The legacy F-058 fired-alerts inbox template (62-alert.tsx)
// stays in components/ as a Phase 2 placeholder for the eventual ack /
// resolve / snooze workflow — wire it up at a separate route when that
// feature actually has a backend.
import Template from '@/components/p2/templates/62b-alerts-f037';

export default function Page() {
  return <Template />;
}
