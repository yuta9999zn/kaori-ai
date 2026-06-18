#!/usr/bin/env bash
#
# N8 Governance — OpenAPI pre-commit hook.
#
# Per REVIEW_NOTES §8.3: pre-commit hook regen *.openapi.json khi router file
# thay đổi. CI fail nếu snapshot lệch với router code.
#
# Install:
#   cp scripts/openapi_precommit_hook.sh .git/hooks/pre-commit
#   chmod +x .git/hooks/pre-commit
#
# Or symlink:
#   ln -s ../../scripts/openapi_precommit_hook.sh .git/hooks/pre-commit
#
# Behavior:
#   - If staged files include services/*/routers/**, regen OpenAPI + stage
#   - If staged files include docs/api-specs/*.openapi.json directly (manual edit),
#     warn (these are generated artefacts, prefer regen)
#

set -e

# Check if any router file is staged
ROUTER_CHANGED=$(git diff --cached --name-only | grep -E "^services/(ai-orchestrator|data-pipeline)/routers/" || true)
SPEC_CHANGED=$(git diff --cached --name-only | grep -E "^docs/api-specs/.*\.openapi\.json$" || true)

if [ -n "$SPEC_CHANGED" ]; then
    echo "⚠ Manual edit detected on:"
    echo "$SPEC_CHANGED" | sed 's/^/  - /'
    echo ""
    echo "These are GENERATED artefacts. Prefer:"
    echo "  python scripts/dump_openapi.py"
    echo "  git add docs/api-specs/"
    echo ""
    read -p "Continue with manual edit? (y/N) " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        echo "Commit aborted."
        exit 1
    fi
fi

if [ -n "$ROUTER_CHANGED" ]; then
    echo "Router file(s) staged:"
    echo "$ROUTER_CHANGED" | sed 's/^/  - /'
    echo ""
    echo "Regenerating OpenAPI snapshots..."

    if ! python scripts/dump_openapi.py 2>&1 | tail -5; then
        echo "✗ OpenAPI dump failed. Fix errors above and retry commit."
        exit 1
    fi

    # Stage regenerated specs if they changed
    SPEC_DIFF=$(git diff --name-only docs/api-specs/ || true)
    if [ -n "$SPEC_DIFF" ]; then
        echo ""
        echo "OpenAPI snapshots regenerated. Auto-staging:"
        echo "$SPEC_DIFF" | sed 's/^/  - /'
        git add docs/api-specs/

        # Suggest TypeScript types regen
        echo ""
        echo "💡 FE TypeScript types may be stale. Run:"
        echo "   cd frontend && npx openapi-typescript ../docs/api-specs/orchestrator.openapi.json -o lib/api/types/orchestrator.d.ts"
        echo "   cd frontend && npx openapi-typescript ../docs/api-specs/pipeline.openapi.json -o lib/api/types/pipeline.d.ts"
    fi
fi

# Optional: CR compliance check on the commit being created
if [ -f scripts/check_cr_compliance.py ]; then
    # Get commit message from prepared file (Git provides COMMIT_EDITMSG)
    # For now, just skip — check_cr_compliance runs on actual commits via CI
    :
fi

exit 0
