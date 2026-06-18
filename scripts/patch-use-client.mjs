#!/usr/bin/env node
/**
 * patch-use-client.mjs — prepend "use client" to React-hook-using files
 * under frontend/components/p2/.
 *
 * Why this is a one-shot vs baked into the migration script: the source
 * templates were authored before the Next.js 16 App Router server-by-
 * default contract was settled, so they don't carry the directive. Once
 * we patch them in-place here, future re-runs of the migration script
 * skip files that already exist (target-exists check), so this never
 * needs to run twice.
 *
 * Detection: any of (useState | useEffect | useMemo | useRef |
 * useCallback | useContext | useReducer | useLayoutEffect | useId)
 * imported from 'react'. Files already starting with "use client"
 * are left alone.
 *
 * Usage:
 *   node patch-use-client.mjs <dir>           # dry-run
 *   node patch-use-client.mjs <dir> --apply   # write
 */

import fs from 'node:fs';
import path from 'node:path';

const TARGET = process.argv[2];
const APPLY = process.argv.includes('--apply');

if (!TARGET) {
  console.error('Usage: node patch-use-client.mjs <dir> [--apply]');
  process.exit(1);
}

const HOOKS_RE = /\b(use(?:State|Effect|Memo|Ref|Callback|Context|Reducer|LayoutEffect|Id))\b/;

function* walkTsx(dir) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, entry.name);
    if (entry.isDirectory()) yield* walkTsx(p);
    else if (entry.isFile() && p.endsWith('.tsx')) yield p;
  }
}

function needsDirective(content) {
  // Already a Client Component → no-op.
  const head = content.slice(0, 200).trim();
  if (head.startsWith("'use client'") || head.startsWith('"use client"')) {
    return false;
  }
  // Only patch when an actual React hook is referenced — pure-display
  // templates without state stay as Server Components (better perf).
  return HOOKS_RE.test(content);
}

function patch(content) {
  // Preserve a leading hashbang or banner comment block if present;
  // for our templates head is always an import, so prepending is fine.
  return `'use client';\n\n${content}`;
}

function main() {
  const touched = [];
  const skipped = [];
  for (const file of walkTsx(TARGET)) {
    const content = fs.readFileSync(file, 'utf8');
    if (!needsDirective(content)) {
      skipped.push(file);
      continue;
    }
    touched.push(file);
    if (APPLY) fs.writeFileSync(file, patch(content), 'utf8');
  }

  console.log(`Mode:    ${APPLY ? 'APPLY' : 'DRY-RUN'}`);
  console.log(`Patched: ${touched.length}`);
  console.log(`Skipped: ${skipped.length} (no hooks or already client)`);
  if (!APPLY) console.log('\n💡 Re-run with --apply to write.');
}

main();
