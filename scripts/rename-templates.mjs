#!/usr/bin/env node
/**
 * rename-templates.mjs — sanitize + standardize frontend template filenames.
 *
 * Pipeline (per file, after stripping extension):
 *   1. Extract numeric prefix       → `9Dasshboard OverView` → num=9, name="Dasshboard OverView"
 *   2. Pad number to 2 digits       → "09"
 *   3. Lowercase + trim
 *   4. COMPOUND merges              → "auto db" → "autodb"
 *   5. TYPO fixes                   → "dasshboard" → "dashboard"
 *   6. SPLIT_HINTS                  → "resetpassword" → "reset-password"
 *   7. Replace [^a-z0-9]+ → "-"
 *   8. Trim leading/trailing "-"
 *
 * JSX detection: closing tag `</…>` OR `from 'react'` import. TS generics never
 * match (no closing tag form), so false positives are negligible.
 *
 * Safety:
 *   - Dry-run by default; pass --apply to execute
 *   - Skips `_*` foundation files (already canonical)
 *   - Detects case-insensitive collisions before renaming (Windows FS)
 *   - Two-phase rename through `.tmp.<pid>.<i>.<final>` to handle A→B + B→A
 *   - Rewrites relative imports + markdown references
 *   - Emits RENAME_REPORT.md after apply
 *
 * Usage:
 *   node rename-templates.mjs "<dir>"           # dry-run
 *   node rename-templates.mjs "<dir>" --apply   # execute
 */

import fs from 'node:fs';
import path from 'node:path';

// ────────────────────────────────────────────────────────────
// CLI
// ────────────────────────────────────────────────────────────

const TARGET_DIR = process.argv[2];
const APPLY = process.argv.includes('--apply');

if (!TARGET_DIR) {
  console.error('Usage: node rename-templates.mjs <directory> [--apply]');
  process.exit(1);
}
if (!fs.existsSync(TARGET_DIR) || !fs.statSync(TARGET_DIR).isDirectory()) {
  console.error(`Not a directory: ${TARGET_DIR}`);
  process.exit(1);
}

// ────────────────────────────────────────────────────────────
// Substitution dictionaries
// ────────────────────────────────────────────────────────────

/** Multi-word → single token. Applied first on lowercased name. */
const COMPOUND = [
  [/\bauto[- ]db\b/gi, 'autodb'],
];

/** Whole-word typo fixes (case-insensitive). */
const TYPOS = [
  [/\bdasshboard\b/gi, 'dashboard'],
  [/\bcharrt\b/gi, 'chart'],
  [/\bsupcription\b/gi, 'subscription'],
  [/\brepost\b/gi, 'reports'],
  [/\bork\b/gi, 'okr'],
  [/\briview\b/gi, 'review'],
  [/\bricks\b/gi, 'risks'],
  [/\bgenerete\b/gi, 'generate'],
  [/\bquanlity\b/gi, 'quality'],
];

/** Known camelCase compounds → split form. Applied AFTER typos + compound. */
const SPLIT_HINTS = [
  [/\bresetpassword\b/gi, 'reset-password'],
  [/\bworkflowhub\b/gi, 'workflow-hub'],
  [/\bauthsession\b/gi, 'auth-session'],
];

// ────────────────────────────────────────────────────────────
// Core transforms
// ────────────────────────────────────────────────────────────

/**
 * JSX detection: any of (a) a closing tag `</X` or (b) a React import.
 * Both signals are absent in pure-data `.ts` files like `_navigation.ts`.
 */
function detectJsx(content) {
  if (/<\/[A-Za-z]/.test(content)) return true;
  if (/from\s+['"]react['"]/i.test(content)) return true;
  return false;
}

/** Normalize a stripped file stem to `{NN}-{kebab}` (or `{kebab}` if no number). */
function normalizeStem(rawStem) {
  const m = rawStem.match(/^\s*(\d+)\s*(.*)$/);
  let num = null;
  let name = rawStem;
  if (m) {
    num = m[1].padStart(2, '0');
    name = m[2];
  }

  let s = name.toLowerCase().trim();

  for (const [re, rep] of COMPOUND)    s = s.replace(re, rep);
  for (const [re, rep] of TYPOS)       s = s.replace(re, rep);
  for (const [re, rep] of SPLIT_HINTS) s = s.replace(re, rep);

  const kebab = s
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');

  return num ? `${num}-${kebab}` : kebab;
}

// ────────────────────────────────────────────────────────────
// Plan
// ────────────────────────────────────────────────────────────

function buildPlan(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const plan = [];

  for (const e of entries) {
    if (!e.isFile()) continue;
    if (e.name.startsWith('_')) continue;          // foundation helpers stay
    if (!/\.(ts|tsx)$/i.test(e.name)) continue;    // only .ts / .tsx considered

    const ext = path.extname(e.name).toLowerCase();
    const stem = path.basename(e.name, ext);

    const content = fs.readFileSync(path.join(dir, e.name), 'utf8');
    const hasJsx = detectJsx(content);
    const newExt = hasJsx ? '.tsx' : '.ts';

    const newStem = normalizeStem(stem);
    const newName = `${newStem}${newExt}`;

    if (newName !== e.name) {
      plan.push({ oldName: e.name, newName, oldStem: stem, newStem, hasJsx });
    }
  }

  return plan;
}

function detectCollisions(plan) {
  const seen = new Map();
  for (const p of plan) {
    const key = p.newName.toLowerCase();
    if (seen.has(key)) return { first: seen.get(key), second: p };
    seen.set(key, p);
  }
  return null;
}

// ────────────────────────────────────────────────────────────
// Apply
// ────────────────────────────────────────────────────────────

/**
 * Two-phase rename:
 *   Phase 1: every old → `.tmp.<pid>.<i>.<final>`
 *   Phase 2: every tmp → final
 *
 * Why two phases:
 *   - On Windows (case-insensitive FS), renaming `Foo.ts` → `foo.ts` can fail
 *   - If two files swap names (`A→B`, `B→A`), single-phase loop overwrites
 *   - Tmp prefix `.tmp.<pid>.<i>` is unique across processes + within batch
 */
function applyRenames(dir, plan) {
  const records = [];
  for (let i = 0; i < plan.length; i += 1) {
    const item = plan[i];
    const tmpName = `.tmp.${process.pid}.${i}.${item.newName}`;
    fs.renameSync(path.join(dir, item.oldName), path.join(dir, tmpName));
    records.push({ tmpName, finalName: item.newName });
  }
  for (const r of records) {
    fs.renameSync(path.join(dir, r.tmpName), path.join(dir, r.finalName));
  }
}

/**
 * Rewrite:
 *   - Relative imports `from './<oldStem>'` → `from './<newStem>'`
 *   - Markdown references to old full filenames → new full filenames
 * Returns count of files modified.
 */
function rewriteReferences(dir, plan, dryRun) {
  const stemMap = new Map();
  for (const p of plan) stemMap.set(p.oldStem, p.newStem);

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  let touched = 0;

  for (const e of entries) {
    if (!e.isFile()) continue;
    if (!/\.(ts|tsx|md)$/i.test(e.name)) continue;

    const filePath = path.join(dir, e.name);
    let content = fs.readFileSync(filePath, 'utf8');
    const original = content;

    // 1. Update relative imports — only stems that actually changed
    for (const [oldStem, newStem] of stemMap) {
      if (oldStem === newStem) continue;
      const escaped = oldStem.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const importRe = new RegExp(
        `(from\\s+['"])\\.\\/${escaped}(\\.tsx?)?(['"])`,
        'g',
      );
      content = content.replace(importRe, `$1./${newStem}$3`);
    }

    // 2. Update markdown references to old filenames (full name with extension)
    if (e.name.toLowerCase().endsWith('.md')) {
      for (const p of plan) {
        const escaped = p.oldName.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        content = content.replace(new RegExp(escaped, 'g'), p.newName);
      }
    }

    if (content !== original) {
      touched += 1;
      if (!dryRun) fs.writeFileSync(filePath, content, 'utf8');
    }
  }

  return touched;
}

function writeReport(dir, plan) {
  const reportPath = path.join(dir, 'RENAME_REPORT.md');
  const lines = [
    '# Rename Report',
    '',
    `Generated: ${new Date().toISOString()}`,
    `Total renamed: ${plan.length}`,
    '',
    '| Old | New | Extension change |',
    '|---|---|---|',
    ...plan.map((p) => {
      const oldExt = path.extname(p.oldName);
      const newExt = path.extname(p.newName);
      const flag = oldExt !== newExt ? `${oldExt} → ${newExt}` : '—';
      return `| \`${p.oldName}\` | \`${p.newName}\` | ${flag} |`;
    }),
  ];
  fs.writeFileSync(reportPath, lines.join('\n') + '\n', 'utf8');
}

// ────────────────────────────────────────────────────────────
// Main
// ────────────────────────────────────────────────────────────

function main() {
  console.log(`Target: ${TARGET_DIR}`);
  console.log(`Mode:   ${APPLY ? 'APPLY' : 'DRY-RUN'}\n`);

  const plan = buildPlan(TARGET_DIR);

  if (plan.length === 0) {
    console.log('Nothing to rename.');
    return;
  }

  // Print plan
  const oldW = Math.max(...plan.map((p) => p.oldName.length));
  const newW = Math.max(...plan.map((p) => p.newName.length));
  console.log(`Plan: ${plan.length} files\n`);
  for (const p of plan) {
    const flag = p.hasJsx ? '[JSX→tsx]' : '[ts]';
    console.log(`  ${p.oldName.padEnd(oldW)}  →  ${p.newName.padEnd(newW)}  ${flag}`);
  }
  console.log();

  // Collision check
  const collision = detectCollisions(plan);
  if (collision) {
    console.error('❌ Collision detected (case-insensitive):');
    console.error(`   ${collision.first.oldName}  →  ${collision.first.newName}`);
    console.error(`   ${collision.second.oldName}  →  ${collision.second.newName}`);
    console.error('Aborting. Resolve manually before re-running.');
    process.exit(2);
  }

  // Reference rewrite preview
  const dryTouched = rewriteReferences(TARGET_DIR, plan, /* dryRun */ true);
  console.log(`References to update in ${dryTouched} file(s).`);

  if (!APPLY) {
    console.log('\n💡 Dry-run only. Re-run with --apply to execute.');
    return;
  }

  console.log('\nRewriting references...');
  rewriteReferences(TARGET_DIR, plan, /* dryRun */ false);
  console.log('Renaming files (two-phase)...');
  applyRenames(TARGET_DIR, plan);
  writeReport(TARGET_DIR, plan);
  console.log(`\n✅ Done — ${plan.length} files renamed.`);
  console.log(`   Report: ${path.join(TARGET_DIR, 'RENAME_REPORT.md')}`);
}

main();
