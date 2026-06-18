#!/usr/bin/env node
/**
 * migrate-templates-to-app-router.mjs
 * ─────────────────────────────────────────────────────────────────────────────
 * Production-grade two-phase migration:
 *   PHASE 1 — sanitize template filenames in source folder
 *   PHASE 2 — copy foundation + templates into Next.js App Router under frontend/
 *
 * Safety:
 *   • Dry-run by default; --apply executes
 *   • Two-phase rename (case-insensitive Windows FS safe)
 *   • COPY semantics — source folder preserved (delete manually after verify)
 *   • Skips foundation files starting with `_` from rename
 *   • Skips Phase 2 files outside /p2/ scope (auth/onboarding)
 *   • Skips writing if target file already exists (warns instead of overwriting)
 *   • Detects rename collisions before applying
 *
 * Usage:
 *   node migrate-templates-to-app-router.mjs <source-dir> [<frontend-dir>]
 *   node migrate-templates-to-app-router.mjs <source-dir> [<frontend-dir>] --apply
 *
 * Default frontend-dir = ./frontend (relative to cwd)
 */

import fs from 'node:fs';
import path from 'node:path';

// ─────────────────────────────────────────────────────────────────────────────
// CLI
// ─────────────────────────────────────────────────────────────────────────────

function parseArgs() {
  const args = process.argv.slice(2);
  const apply = args.includes('--apply');
  const positional = args.filter((a) => !a.startsWith('--'));
  const sourceDir = positional[0];
  const frontendDir = positional[1] ?? path.resolve(process.cwd(), 'frontend');
  return { sourceDir, frontendDir, apply };
}

const { sourceDir: SRC, frontendDir: FRONTEND, apply: APPLY } = parseArgs();

if (!SRC) {
  console.error('Usage: node migrate-templates-to-app-router.mjs <source-dir> [<frontend-dir>] [--apply]');
  process.exit(1);
}
if (!fs.existsSync(SRC) || !fs.statSync(SRC).isDirectory()) {
  console.error(`❌ Source not a directory: ${SRC}`);
  process.exit(1);
}
if (!fs.existsSync(FRONTEND) || !fs.statSync(FRONTEND).isDirectory()) {
  console.error(`❌ Frontend not a directory: ${FRONTEND}`);
  process.exit(1);
}

// ─────────────────────────────────────────────────────────────────────────────
// Dictionaries
// ─────────────────────────────────────────────────────────────────────────────

/** Multi-word → single token. Applied first, on lowercased input. */
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

/** Filename domain → URL domain. Applied to first kebab token. */
const DOMAIN_MAP = {
  user: 'users',
  pipeline: 'pipelines',
  insight: 'insights',
  chart: 'charts',
  decision: 'decisions',
  report: 'reports',
  workflow: 'workflows',
  alert: 'alerts',
  autodb: 'auto-db',
  analyst: 'analysis',
};

/** Domains that route under /p2/. Anything else is skipped from Phase 2. */
const P2_DOMAINS = new Set([
  'dashboard', 'data', 'pipeline', 'pipelines', 'insight', 'insights',
  'chart', 'charts', 'user', 'users', 'decision', 'decisions',
  'subscription', 'analyst', 'analysis', 'frameworks', 'report', 'reports',
  'strategy', 'risks', 'alert', 'alerts', 'workflow', 'workflows',
  'autodb', 'authz', 'branding',
]);

/** Out-of-scope domains — Phase 2 skipped (existing routes handle them). */
const OUT_OF_SCOPE_DOMAINS = new Set([
  'login', 'auth', 'forgot', 'reset', 'onboarding',
]);

// ─────────────────────────────────────────────────────────────────────────────
// PHASE 1 — Filename normalization
// ─────────────────────────────────────────────────────────────────────────────

/** JSX detection: closing tag OR React import — both signals are absent in pure-data .ts files. */
function detectJsx(content) {
  if (/<\/[A-Za-z]/.test(content)) return true;
  if (/from\s+['"]react['"]/i.test(content)) return true;
  return false;
}

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
  const kebab = s.replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
  return num ? `${num}-${kebab}` : kebab;
}

function buildRenamePlan(srcDir) {
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  const plan = [];
  for (const e of entries) {
    if (!e.isFile()) continue;
    if (e.name.startsWith('_')) continue;
    if (!/\.(ts|tsx)$/i.test(e.name)) continue;

    const ext = path.extname(e.name).toLowerCase();
    const stem = path.basename(e.name, ext);
    const content = fs.readFileSync(path.join(srcDir, e.name), 'utf8');
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

function detectRenameCollisions(plan) {
  const seen = new Map();
  for (const p of plan) {
    const key = p.newName.toLowerCase();
    if (seen.has(key)) return { first: seen.get(key), second: p };
    seen.set(key, p);
  }
  return null;
}

/** Two-phase rename to handle case-insensitive Windows FS + A→B/B→A swaps. */
function applyRenames(srcDir, plan) {
  const records = [];
  for (let i = 0; i < plan.length; i += 1) {
    const item = plan[i];
    const tmpName = `.tmp.${process.pid}.${i}.${item.newName}`;
    fs.renameSync(path.join(srcDir, item.oldName), path.join(srcDir, tmpName));
    records.push({ tmpName, finalName: item.newName });
  }
  for (const r of records) {
    fs.renameSync(path.join(srcDir, r.tmpName), path.join(srcDir, r.finalName));
  }
}

/** Update relative imports + markdown references inside source folder (post-rename). */
function rewriteReferencesInSource(srcDir, plan, dryRun) {
  const stemMap = new Map();
  for (const p of plan) stemMap.set(p.oldStem, p.newStem);
  const entries = fs.readdirSync(srcDir, { withFileTypes: true });
  let touched = 0;
  for (const e of entries) {
    if (!e.isFile()) continue;
    if (!/\.(ts|tsx|md)$/i.test(e.name)) continue;
    const filePath = path.join(srcDir, e.name);
    let content = fs.readFileSync(filePath, 'utf8');
    const original = content;
    for (const [oldStem, newStem] of stemMap) {
      if (oldStem === newStem) continue;
      const escaped = oldStem.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const re = new RegExp(`(from\\s+['"])\\.\\/${escaped}(\\.tsx?)?(['"])`, 'g');
      content = content.replace(re, `$1./${newStem}$3`);
    }
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

// ─────────────────────────────────────────────────────────────────────────────
// PHASE 2 — Routing
// ─────────────────────────────────────────────────────────────────────────────

function deriveRoute(newStem) {
  const m = newStem.match(/^(\d+)-(.+)$/);
  if (!m) return { skip: true, reason: 'no numeric prefix' };
  const tokens = m[2].split('-');
  const domainKey = tokens[0];

  if (OUT_OF_SCOPE_DOMAINS.has(domainKey)) {
    return { skip: true, reason: 'out-of-scope (auth/onboarding handled separately)' };
  }
  if (!P2_DOMAINS.has(domainKey)) {
    return { skip: true, reason: `unknown domain "${domainKey}"` };
  }

  const domain = DOMAIN_MAP[domainKey] ?? domainKey;
  const featureTokens = tokens.slice(1);
  const featureSeg = featureTokens.length > 0 ? '/' + featureTokens.join('-') : '';
  const routePath = `/p2/${domain}${featureSeg}`;
  // FS path uses forward slashes; path.join normalizes on Windows when needed.
  const pageFsPath = `app/(app)/p2/${domain}${featureSeg}/page.tsx`;
  return { skip: false, routePath, pageFsPath };
}

// ─────────────────────────────────────────────────────────────────────────────
// PHASE 2 — Foundation + import rewrites
// ─────────────────────────────────────────────────────────────────────────────

const FOUNDATION_FILES = {
  '_foundation.tsx':         'components/p2/foundation.tsx',
  '_foundation_wizard.tsx':  'components/p2/foundation-wizard.tsx',
  '_shell.tsx':              'components/p2/shell.tsx',
  '_navigation.ts':          'components/p2/navigation.ts',
};

/** Imports inside template files (after copy to components/p2/templates/). */
const TEMPLATE_IMPORT_REWRITES = [
  [/from\s+['"]\.\/_foundation_wizard['"]/g, "from '@/components/p2/foundation-wizard'"],
  [/from\s+['"]\.\/_foundation['"]/g,        "from '@/components/p2/foundation'"],
  [/from\s+['"]\.\/_shell['"]/g,             "from '@/components/p2/shell'"],
  [/from\s+['"]\.\/_navigation['"]/g,        "from '@/components/p2/navigation'"],
];

/** Imports inside foundation files themselves (siblings stay relative). */
const FOUNDATION_INTERNAL_REWRITES = [
  [/from\s+['"]\.\/_foundation_wizard['"]/g, "from './foundation-wizard'"],
  [/from\s+['"]\.\/_foundation['"]/g,        "from './foundation'"],
  [/from\s+['"]\.\/_shell['"]/g,             "from './shell'"],
  [/from\s+['"]\.\/_navigation['"]/g,        "from './navigation'"],
];

function rewriteContent(content, rules) {
  let out = content;
  for (const [re, rep] of rules) out = out.replace(re, rep);
  return out;
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

// ─────────────────────────────────────────────────────────────────────────────
// PHASE 2 — Apply
// ─────────────────────────────────────────────────────────────────────────────

function copyFoundation(srcDir, frontendDir, dryRun, log) {
  const created = [];
  const skipped = [];
  for (const [src, dst] of Object.entries(FOUNDATION_FILES)) {
    const srcPath = path.join(srcDir, src);
    const dstPath = path.join(frontendDir, dst);
    if (!fs.existsSync(srcPath)) {
      log.warn(`  source missing: ${src}`);
      skipped.push({ src, reason: 'source-missing' });
      continue;
    }
    if (fs.existsSync(dstPath)) {
      log.warn(`  target exists, skipping: ${dst}`);
      skipped.push({ src, reason: 'target-exists' });
      continue;
    }
    log.info(`  ${src.padEnd(28)} → ${dst}`);
    created.push({ src, dst });
    if (!dryRun) {
      ensureDir(path.dirname(dstPath));
      const content = fs.readFileSync(srcPath, 'utf8');
      const rewritten = rewriteContent(content, FOUNDATION_INTERNAL_REWRITES);
      fs.writeFileSync(dstPath, rewritten, 'utf8');
    }
  }
  return { created, skipped };
}

function writeLayout(frontendDir, dryRun, log) {
  const layoutPath = path.join(frontendDir, 'app', '(app)', 'p2', 'layout.tsx');
  const rel = 'app/(app)/p2/layout.tsx';
  if (fs.existsSync(layoutPath)) {
    log.warn(`  layout exists, skipping: ${rel}`);
    return false;
  }
  log.info(`  ${'(generated)'.padEnd(28)} → ${rel}`);
  if (!dryRun) {
    ensureDir(path.dirname(layoutPath));
    const content = `import type { ReactNode } from 'react';

export const metadata = {
  title: 'Kaori Enterprise',
};

export default function P2Layout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
`;
    fs.writeFileSync(layoutPath, content, 'utf8');
  }
  return true;
}

function copyTemplatesAndPages(srcDir, frontendDir, postRenameNames, dryRun, log) {
  const migrated = [];
  const skipped = [];
  const conflicts = [];

  for (const newName of postRenameNames) {
    const ext = path.extname(newName).toLowerCase();
    if (ext !== '.tsx') continue;
    const stem = path.basename(newName, ext);

    const route = deriveRoute(stem);
    if (route.skip) {
      skipped.push({ name: newName, reason: route.reason });
      continue;
    }

    const templateRel = `components/p2/templates/${stem}.tsx`;
    const templateAbs = path.join(frontendDir, templateRel);
    const srcAbs = path.join(srcDir, newName);
    const pageAbs = path.join(frontendDir, route.pageFsPath);

    let templateAction = 'create';
    let pageAction = 'create';
    if (fs.existsSync(templateAbs)) {
      log.warn(`  template exists, skipping: ${templateRel}`);
      templateAction = 'skip';
      conflicts.push({ name: newName, target: templateRel, kind: 'template' });
    }
    if (fs.existsSync(pageAbs)) {
      log.warn(`  page exists, skipping: ${route.pageFsPath}`);
      pageAction = 'skip';
      conflicts.push({ name: newName, target: route.pageFsPath, kind: 'page' });
    }

    if (templateAction === 'create') {
      log.info(`  ${newName.padEnd(40)} → ${templateRel}`);
    }
    if (pageAction === 'create') {
      log.info(`  ${'  (page wrapper)'.padEnd(40)} → ${route.pageFsPath}  [${route.routePath}]`);
    }

    migrated.push({ name: newName, route: route.routePath, templateRel, pageRel: route.pageFsPath, templateAction, pageAction });

    if (!dryRun) {
      if (templateAction === 'create') {
        ensureDir(path.dirname(templateAbs));
        const srcContent = fs.readFileSync(srcAbs, 'utf8');
        const rewritten = rewriteContent(srcContent, TEMPLATE_IMPORT_REWRITES);
        fs.writeFileSync(templateAbs, rewritten, 'utf8');
      }
      if (pageAction === 'create') {
        ensureDir(path.dirname(pageAbs));
        const wrapper = `import Template from '@/components/p2/templates/${stem}';

export default function Page() {
  return <Template />;
}
`;
        fs.writeFileSync(pageAbs, wrapper, 'utf8');
      }
    }
  }
  return { migrated, skipped, conflicts };
}

function detectRouteCollisions(migrated) {
  const seen = new Map();
  for (const m of migrated) {
    const key = m.route.toLowerCase();
    if (seen.has(key)) return { first: seen.get(key), second: m };
    seen.set(key, m);
  }
  return null;
}

// ─────────────────────────────────────────────────────────────────────────────
// Reports
// ─────────────────────────────────────────────────────────────────────────────

function writeRenameReport(srcDir, plan) {
  const reportPath = path.join(srcDir, 'RENAME_REPORT.md');
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

function writeMigrationReport(frontendDir, migrated, skipped, conflicts) {
  const reportPath = path.join(frontendDir, 'MIGRATION_REPORT.md');
  const lines = [
    '# P2 App Router Migration Report',
    '',
    `Generated: ${new Date().toISOString()}`,
    `Migrated: ${migrated.length}  ·  Skipped: ${skipped.length}  ·  Conflicts: ${conflicts.length}`,
    '',
    '## Migrated routes',
    '',
    '| Source | Route | Page | Template |',
    '|---|---|---|---|',
    ...migrated.map((m) => `| \`${m.name}\` | \`${m.route}\` | \`${m.pageRel}\` | \`${m.templateRel}\` |`),
    '',
    '## Skipped (Phase 2)',
    '',
    skipped.length > 0
      ? ['| File | Reason |', '|---|---|', ...skipped.map((s) => `| \`${s.name}\` | ${s.reason} |`)].join('\n')
      : '_None._',
    '',
    '## Conflicts (target already existed)',
    '',
    conflicts.length > 0
      ? ['| Source | Target | Kind |', '|---|---|---|', ...conflicts.map((c) => `| \`${c.name}\` | \`${c.target}\` | ${c.kind} |`)].join('\n')
      : '_None._',
  ];
  fs.writeFileSync(reportPath, lines.join('\n') + '\n', 'utf8');
}

// ─────────────────────────────────────────────────────────────────────────────
// Logging
// ─────────────────────────────────────────────────────────────────────────────

const log = {
  info: (msg) => console.log(msg),
  warn: (msg) => console.warn(`⚠️  ${msg}`),
  err:  (msg) => console.error(`❌  ${msg}`),
};

function hr() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
}

// ─────────────────────────────────────────────────────────────────────────────
// Main
// ─────────────────────────────────────────────────────────────────────────────

function main() {
  hr();
  console.log(`  Kaori P2 Template Migration — ${APPLY ? 'APPLY' : 'DRY-RUN'}`);
  hr();
  console.log(`  Source:   ${SRC}`);
  console.log(`  Frontend: ${FRONTEND}\n`);

  // ── PHASE 1 ──
  console.log('━━━ PHASE 1 — Sanitize template filenames ━━━\n');
  const renamePlan = buildRenamePlan(SRC);

  if (renamePlan.length === 0) {
    console.log('  No files need renaming.\n');
  } else {
    const oldW = Math.max(...renamePlan.map((p) => p.oldName.length));
    for (const p of renamePlan) {
      const flag = p.hasJsx ? '[JSX→tsx]' : '[ts]';
      console.log(`  ${p.oldName.padEnd(oldW)}  →  ${p.newName}  ${flag}`);
    }
    console.log(`\n  Total to rename: ${renamePlan.length}\n`);

    const collision = detectRenameCollisions(renamePlan);
    if (collision) {
      log.err('Phase 1 collision (case-insensitive on Windows):');
      log.err(`   ${collision.first.oldName}  →  ${collision.first.newName}`);
      log.err(`   ${collision.second.oldName}  →  ${collision.second.newName}`);
      process.exit(2);
    }

    const refCount = rewriteReferencesInSource(SRC, renamePlan, /* dryRun */ true);
    console.log(`  References to rewrite in source: ${refCount} file(s)\n`);
  }

  // Build the post-rename file list (for Phase 2)
  const postRenameNames = new Set();
  const allEntries = fs.readdirSync(SRC, { withFileTypes: true });
  for (const e of allEntries) {
    if (!e.isFile()) continue;
    if (e.name.startsWith('_')) continue;
    if (!/\.(ts|tsx)$/i.test(e.name)) continue;
    postRenameNames.add(e.name);
  }
  for (const p of renamePlan) {
    postRenameNames.delete(p.oldName);
    postRenameNames.add(p.newName);
  }
  const sortedPostRename = [...postRenameNames].sort();

  // ── PHASE 2 plan ──
  console.log('━━━ PHASE 2 — Convert to Next.js App Router ━━━\n');

  console.log('  Foundation files:');
  copyFoundation(SRC, FRONTEND, /* dryRun */ true, log);
  console.log();

  console.log('  Layout:');
  writeLayout(FRONTEND, /* dryRun */ true, log);
  console.log();

  console.log('  Templates + page wrappers:');
  const phase2Plan = copyTemplatesAndPages(SRC, FRONTEND, sortedPostRename, /* dryRun */ true, log);
  console.log();

  // Route collision check
  const routeCollision = detectRouteCollisions(phase2Plan.migrated);
  if (routeCollision) {
    log.err('Phase 2 route collision:');
    log.err(`   ${routeCollision.first.name}  →  ${routeCollision.first.route}`);
    log.err(`   ${routeCollision.second.name}  →  ${routeCollision.second.route}`);
    process.exit(3);
  }

  if (phase2Plan.skipped.length > 0) {
    console.log(`  Skipped (${phase2Plan.skipped.length}):`);
    for (const s of phase2Plan.skipped) {
      console.log(`    ${s.name.padEnd(40)} — ${s.reason}`);
    }
    console.log();
  }

  if (phase2Plan.conflicts.length > 0) {
    console.log(`  ⚠️  Conflicts (${phase2Plan.conflicts.length}) — target already exists, will not overwrite:`);
    for (const c of phase2Plan.conflicts) {
      console.log(`    ${c.name.padEnd(40)} → ${c.target}  [${c.kind}]`);
    }
    console.log();
  }

  // ── Summary ──
  hr();
  console.log(`  Phase 1: ${renamePlan.length} renames`);
  console.log(`  Phase 2: ${phase2Plan.migrated.length} migrated, ${phase2Plan.skipped.length} skipped, ${phase2Plan.conflicts.length} conflicts`);
  hr();

  if (!APPLY) {
    console.log('\n  💡 Dry-run only. Re-run with --apply to execute.');
    return;
  }

  // ── APPLY ──
  console.log('\n━━━ EXECUTING ━━━\n');

  if (renamePlan.length > 0) {
    console.log('Rewriting source references...');
    rewriteReferencesInSource(SRC, renamePlan, /* dryRun */ false);
    console.log('Renaming source files (two-phase)...');
    applyRenames(SRC, renamePlan);
    writeRenameReport(SRC, renamePlan);
    console.log(`  Phase 1 report: ${path.join(SRC, 'RENAME_REPORT.md')}`);
  }

  console.log('Copying foundation...');
  copyFoundation(SRC, FRONTEND, /* dryRun */ false, log);
  console.log('Writing layout...');
  writeLayout(FRONTEND, /* dryRun */ false, log);
  console.log('Copying templates + writing page wrappers...');
  copyTemplatesAndPages(SRC, FRONTEND, sortedPostRename, /* dryRun */ false, log);
  writeMigrationReport(FRONTEND, phase2Plan.migrated, phase2Plan.skipped, phase2Plan.conflicts);
  console.log(`  Phase 2 report: ${path.join(FRONTEND, 'MIGRATION_REPORT.md')}`);

  console.log('\n✅ Migration complete. Review reports + run `npm run typecheck && npm run build` next.');
}

main();
