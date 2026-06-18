# Governance Tightening — N8 Scripts Reference

> **Status:** ✅ shipped 2026-05-21 (Round 5 N8) per REVIEW_NOTES §8
> **Trigger:** CR Register v2.1 §9 Governance findings lần 1 + 2 (CR-0009/0010 post-facto; Permission Claims concept BA catch-up lag)
> **Audience:** Tech Lead · Platform Eng · PM · QA Lead

---

## 1. Background

### Governance finding lần 1 (CR Register v2.0)

CR-0009 (Workflow Events) và CR-0010 (Lineage Edges + AI Decision Audit + Policy Engine) đã shipped Phase 2.6/2.7 **không qua CR Review Board formal**. Engineering đẩy thẳng vào sprint. → Process gap: BA layer behind code reality.

### Governance finding lần 2 (CR Register v2.1)

Permission Claims concept đã dùng code-side + FE spec-side suốt Phase 2.5/2.6/2.7 nhưng BA layer không catch trong NFRS đến Phase 2.8 (CR-0012). → Lesson: bất kỳ concept mới nào trong code/FE phải reflect ngược lên BA layer (NFRS/URD) trong cùng sprint, không defer.

---

## 2. Tools shipped

### 2.1 `scripts/check_cr_compliance.py`

Check if commits reference `CR-####` when feature files are added.

**Usage:**
```bash
# Check last commit
python scripts/check_cr_compliance.py

# Check all commits since main
python scripts/check_cr_compliance.py --since main

# CI mode (exit 1 on violation)
python scripts/check_cr_compliance.py --since main --ci
```

**Trigger paths (commits MUST reference CR-####):**
- `infrastructure/postgres/migrations/` (new .sql files)
- `services/*/routers/` (new endpoint files)
- `services/*/main/java/.../controller/` (new Spring controllers)

**Excluded:** tests, docs, scripts, README — these don't require CR reference.

**CI integration (planned):** GitHub Actions step in `.github/workflows/ci.yml`:
```yaml
- name: CR compliance check
  run: python scripts/check_cr_compliance.py --since ${{ github.event.pull_request.base.sha }} --ci
```

### 2.2 `scripts/check_ba_sync.py`

Detect drift between BA layer + code repo.

**Usage:**
```bash
# Run all checks
python scripts/check_ba_sync.py

# CI mode
python scripts/check_ba_sync.py --ci --threshold 0.05
```

**Checks performed:**
1. Migration count (matches sprint plan?)
2. OpenAPI paths count (matches API_CATALOG_V4 estimate?)
3. BA docs sync: `D:\Tài liệu dự án\*.md` vs `docs/ba/*.md` — alert on MISSING/DIFFER/ORPHAN files
4. CR reference rate: at least 50% feat commits should reference CR

**Weekly cron (planned):**
```yaml
# .github/workflows/ba-drift.yml
on:
  schedule:
    - cron: '0 9 * * MON'  # Every Monday 9AM ICT
```

### 2.3 `scripts/openapi_precommit_hook.sh`

Pre-commit hook: regen OpenAPI when router files change.

**Install:**
```bash
ln -s ../../scripts/openapi_precommit_hook.sh .git/hooks/pre-commit
chmod +x scripts/openapi_precommit_hook.sh
```

**Behavior:**
1. If router files staged → run `dump_openapi.py` → auto-stage regen
2. If `docs/api-specs/*.openapi.json` manually edited → warn (these are generated)
3. Suggest FE types regen (`npx openapi-typescript`)

---

## 3. Roll-out plan

### Phase 2.8 (current — Round 5 N8 ship)
- ✅ Scripts written + tested locally
- ⏳ Pre-commit hook install: optional per-developer
- ⏳ CI workflow integration: defer to Phase 2.9 (need to verify scripts don't break existing CI)

### Phase 2.9 (planned)
- Enable `check_cr_compliance.py --ci` on all PRs to main
- Enable `check_ba_sync.py` weekly Monday cron
- Add pre-commit hook to onboarding docs (mandatory for new devs)
- Alert SEC if check_ba_sync detects drift >5%

### Phase 3 (planned)
- Auto-create CR draft when feat commit lacks CR-#### reference (push to CR Review Board queue)
- BA-code drift auto-fix: PR comment with link to outdated BA doc + suggest update path
- Audit dashboard `/platform/governance` shows drift score over time

---

## 4. Related K-rules + NFRs

- **K-15** Audit every action (CR-0009/0010 violated by going around)
- **NFR-SEC-19** Claim escalation alert (>5/hour 403-CLAIM) — already wired
- **NFR-SEC-20** Claim drift detection weekly — implemented in `check_ba_sync.py`

---

## 5. Maintenance

- Update TRIGGER_PATHS in `check_cr_compliance.py` when new code organizing paths added
- Update EXCLUDED_PATTERNS conservatively (no false negatives)
- Re-baseline BA sync after each major BA docs sync (Round 4/5 sync pattern)
- Document any exceptions to CR-required workflow (e.g. emergency hotfix → submit retroactive CR within 48h)

---

*— Hết Governance Tightening N8 reference. CR Register v2.1 §9 closed.*
