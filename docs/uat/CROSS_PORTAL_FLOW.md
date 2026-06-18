# UAT — CROSS_PORTAL_FLOW (Studio → Enterprise → CSM Hand-off)

> **Function:** Priority 4 cross-portal flow — Studio Analyst (P3) hands off model/template → Enterprise Manager (P2) deploys → CSM (P1) monitors adoption
> **Portal:** P3 Studio → P2 Enterprise → P1 Platform (CSM)
> **Services:** All 4 microservice boundaries (auth + data-pipeline + ai-orchestrator + notification-service)
> **DB:** Cross-tenant scope for Studio (STU-01) via `view_mcp` claim + per-enterprise scope for ENT users
> **Owner:** QA Lead + PO + CSM Lead
> **Prepared:** 2026-05-21 (Round 5 N4)

---

## 0. Hand-off chain (3 portals)

```
P3 Studio Analyst (STU-01)
  ├─ Trains/customizes workflow template (Workflow Builder Developer mode)
  ├─ Promotes to library `industry_workflow_links` mig 101
  └─ Hand-off → P2 Enterprise

P2 Enterprise Manager (ENT-01)
  ├─ Industry Bootstrap (P2-02 wizard 7-step) → instantiate workflow from template
  ├─ Configures dept-specific tweaks via Workflow Builder Simple/Advanced mode (mig 102)
  ├─ Publishes workflow (status=active)
  └─ Hand-off → P1 CSM monitoring

P1 CSM Portfolio (PLT-03)
  ├─ Sees workspace adoption signals (mig 090 adoption_health_snapshots)
  ├─ Triggers intervention if health <40 (US-D2)
  └─ Tracks effectiveness 14d after intervention (US-D3)
```

---

## 1. Test scenarios

### TC-1 Happy path (full E2E)
- **Given** Studio Analyst STU-01 has new "Refund Approval v2" template
- **When**
  1. Studio: publish template to `industry_workflow_links` (Finance industry)
  2. Enterprise Manager: Industry Bootstrap re-run includes new template; Manager customizes SLA 24h→12h
  3. Publish workflow active; first run completes successfully
  4. CSM: monitors workspace D7 health score; sees adoption increase post-deploy
- **Then** Chain completes end-to-end; cross-portal events emit (workflow.promoted, workflow.deployed, adoption.signal_collected); JWT scopes correctly isolated (Studio cross-tenant; Enterprise own-tenant; CSM read-only customer scope)

### TC-2 Studio cross-tenant scope (STU-01)
- **Given** STU-01 assigned to 5 enterprises
- **When** Studio Analyst lists workflows + templates
- **Then** Sees aggregate across 5 enterprises; cross-tenant query via `view_mcp` claim (NFRS §5.bis); audit log records cross-tenant access

### TC-3 CSM intervention trigger
- **Given** Workspace adoption drops to 32 after deploy (per mig 090 cron)
- **When** CSM portfolio shows AT_RISK
- **Then** US-D2 9-signal drill-down; CSM triggers intervention (US-D3 playbook); 14d effectiveness measured

## 2. Negative scenarios

| Scenario | Trigger | Expected |
|---|---|---|
| **Happy** | Full hand-off chain | TC-1 |
| **Permission** | Enterprise OPERATOR try Studio publish | 403 USR-ERR-403-ROLE (need STU-01) |
| **Validation** | Studio template invalid YAML | 422 USR-ERR-422-WORKFLOW-YAML |
| **Dependency** | adoption cron miss day | CSM sees yesterday snapshot + timestamp warning |

## 3. K-rule invariants

- **K-1** RLS per tenant for Enterprise; STU-01 cross-tenant explicit
- **K-12** Anti-IDOR on every endpoint
- **K-15** Audit cross-portal hand-off events (workflow.promoted/deployed/etc.)
- **K-19** OTel trace_id propagates across 3 services per W3C Trace Context

## 4. Performance

| Stage | Target |
|---|---|
| Studio publish → template visible to Enterprise | <30s |
| Enterprise customize + publish | <60s |
| First adoption signal collection (after deploy) | 24h (D1) |
| CSM portfolio refresh | <2min cron |

## 5. UAT execution checklist

- [ ] Setup: 1 Studio Analyst (STU-01) + 2 Enterprise tenants (different industries) + 1 CSM
- [ ] Studio: publish "Refund v2" template to Finance industry
- [ ] Enterprise A (Finance): see template in bootstrap; customize SLA; publish; first run
- [ ] Enterprise B (Retail): does NOT see Finance template (scope correct)
- [ ] CSM: monitor Enterprise A workspace; trigger intervention if applicable
- [ ] Verify OTel trace_id same across 3 portals' actions on same business transaction
- [ ] Permission negative: OPERATOR try publish → 403

---

*UAT ID: UAT-CROSS-PORTAL-001 · Owner CSM Lead + PO*
