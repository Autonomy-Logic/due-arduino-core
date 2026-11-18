#!/usr/bin/env node
// merge-components.mjs — merge the hand-maintained inventory into the cdxgen BOM.
//   node scripts/merge-components.mjs <cdxgen.json> <components.json> <upstream.json> <version> <out.cdx.json>
//
// The platform has no package manager for what it ships: the upstream SAM core is
// downloaded by tools/ci/build-release.py and the toolchain is referenced from
// Arduino's index. security/components.json lists those, and this script makes
// them first-class CycloneDX components next to whatever cdxgen found.
//
// Drift guard: an entry pinned with the property autonomy:pin must match
// tools/ci/upstream.json (core URL and SHA-256, tool versions). Bumping a pin
// without updating the inventory fails the run instead of shipping a stale SBOM.
// Exit 0 = merged, 1 = invalid input or drift.

import { readFileSync, writeFileSync } from 'node:fs';
import { refOf } from './lib/cdx.mjs';

const [cdxP, invP, upP, version, out] = process.argv.slice(2);
if (!cdxP || !invP || !upP || !version || !out) {
  console.error('usage: merge-components.mjs <cdxgen.json> <components.json> <upstream.json> <version> <out.cdx.json>');
  process.exit(1);
}
const fail = (msg) => { console.error(`::error::merge-components: ${msg}`); process.exit(1); };
const load = (p, label) => {
  try { return JSON.parse(readFileSync(p, 'utf8')); } catch (e) { return fail(`cannot read ${label} "${p}" (${e.code || e.message})`); }
};

const cdx = load(cdxP, 'cdxgen BOM');
const inv = load(invP, 'inventory');
const up = load(upP, 'upstream pins');
if (cdx.bomFormat !== 'CycloneDX') fail(`"${cdxP}" is not a CycloneDX document`);
if (!inv.root?.name || !Array.isArray(inv.components) || !inv.components.length) fail(`"${invP}" needs root.name and a non-empty components[]`);

const pinOf = (c) => (c.properties || []).find((p) => p.name === 'autonomy:pin')?.value;
const pinned = new Map(inv.components.filter(pinOf).map((c) => [pinOf(c), c]));

// --- drift guard against tools/ci/upstream.json ---
const core = pinned.get('core');
if (!core) fail('no inventory component is pinned as "core"');
const coreHash = (core.hashes || []).find((h) => h.alg === 'SHA-256')?.content;
const coreDist = (core.externalReferences || []).find((r) => r.type === 'distribution')?.url;
if (coreHash !== up.core?.sha256) fail(`core SHA-256 drift: inventory ${coreHash} vs upstream.json ${up.core?.sha256}`);
if (coreDist !== up.core?.url) fail(`core URL drift: inventory ${coreDist} vs upstream.json ${up.core?.url}`);
for (const t of up.toolsDependencies || []) {
  const c = pinned.get(`tool:${t.name}`);
  if (!c) fail(`upstream.json depends on ${t.name} ${t.version} but no inventory component is pinned as "tool:${t.name}"`);
  if (c.version !== t.version) fail(`${t.name} drift: inventory ${c.version} vs upstream.json ${t.version}`);
}
const upTools = new Set((up.toolsDependencies || []).map((t) => `tool:${t.name}`));
for (const pin of pinned.keys()) {
  if (pin.startsWith('tool:') && !upTools.has(pin)) fail(`inventory pins ${pin} but upstream.json no longer depends on it`);
}

// --- root component: the platform itself, replacing cdxgen's guess ---
const { purlBase, ...rootFields } = inv.root;
const rootPurl = purlBase ? `${purlBase}@${version}` : undefined;
const root = { ...rootFields, version, ...(rootPurl ? { purl: rootPurl } : {}), 'bom-ref': rootPurl || `${inv.root.name}@${version}` };
const oldRootRef = cdx.metadata?.component?.['bom-ref'];

// --- components: cdxgen's plus the inventory, no duplicate refs ---
const comps = [...(cdx.components || [])];
const seen = new Set(comps.map(refOf));
// A LicenseRef- name carries its text, so the SPDX converter can declare it.
const withLicenseText = (c) => ({
  ...c,
  licenses: (c.licenses || []).map((l) => {
    const name = l.license?.name;
    if (!name?.startsWith('LicenseRef-')) return l;
    const text = inv.licenseRefs?.[name];
    if (!text) fail(`"${c.name}" uses ${name} but licenseRefs has no text for it`);
    return { license: { ...l.license, text: { content: text } } };
  }),
});
for (const c of inv.components) {
  if (!c['bom-ref']) fail(`inventory component "${c.name}" has no bom-ref`);
  if (!c.version) fail(`inventory component "${c.name}" has no version`);
  if (!(c.licenses || []).length) fail(`inventory component "${c.name}" has no licence`);
  if (seen.has(c['bom-ref'])) fail(`duplicate bom-ref "${c['bom-ref']}"`);
  seen.add(c['bom-ref']);
  comps.push(withLicenseText(c));
}

// --- dependency graph: root -> cdxgen's direct deps + inventory top level ---
const deps = (cdx.dependencies || []).filter((d) => d.ref !== oldRootRef);
const oldRootDeps = (cdx.dependencies || []).find((d) => d.ref === oldRootRef)?.dependsOn || [];
const cdxgenTop = oldRootDeps.length ? oldRootDeps : (cdx.components || []).map(refOf);
const rootDeps = [...new Set([...cdxgenTop, ...(inv.rootDependsOn || [])])];
for (const r of [...rootDeps, ...(inv.dependencies || []).flatMap((d) => [d.ref, ...(d.dependsOn || [])])]) {
  if (!seen.has(r)) fail(`dependency names unknown component "${r}"`);
}
deps.unshift({ ref: root['bom-ref'], dependsOn: rootDeps });
for (const d of inv.dependencies || []) deps.push({ ref: d.ref, dependsOn: [...d.dependsOn] });

const merged = {
  ...cdx,
  metadata: { ...cdx.metadata, component: root },
  components: comps,
  dependencies: deps,
};
writeFileSync(out, JSON.stringify(merged, null, 2) + '\n');
console.log(`Merged ${inv.components.length} inventory component(s) into ${(cdx.components || []).length} detected; root ${root.name}@${version}.`);
