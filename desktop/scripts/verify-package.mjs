import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { basename, dirname, join, relative, resolve, sep } from 'node:path';
import { pathToFileURL } from 'node:url';
import asar from '@electron/asar';
import { verifyRuntime } from '../dist/engine.js';

// This command reads package contents. It never starts Electron or authenticates.
const release = resolve('release');
const candidates = (await readdir(release, { recursive: true }))
  .filter((name) => basename(name) === 'app.asar').map((name) => join(release, name));
assert.equal(candidates.length, 1, 'Expected exactly one app package in release/');
const archive = candidates[0];
const extract = (name) => asar.extractFile(archive, name.replaceAll('/', sep));
const files = asar.listPackage(archive).map((name) => name.replaceAll('\\', '/').replace(/^\//, ''));
assert(!files.some((name) => /(^|\/)(chatgpt-auth\.json|chatgpt-host\.json|\.env|\.paper-factory|output)(\/|$)/.test(name)), 'Private data must not be packaged');
const required = [
  'package.json', 'dist/main.js', 'dist/preload.cjs', 'dist/renderer/index.html', 'dist/LICENSE',
  'node_modules/@siwc/local/package.json', 'node_modules/@siwc/local/dist/index.js',
  'node_modules/@siwc/local/LICENSE', 'node_modules/@siwc/local/THIRD_PARTY_NOTICES.md',
  'node_modules/jose/package.json', 'node_modules/proper-lockfile/package.json',
  'third-party/neobrutal-ui/LICENSE', 'third-party/neobrutal-ui/provenance.json',
];
for (const name of required) assert(files.includes(name), `Missing package member: ${name}`);
const packaged = JSON.parse(extract('package.json').toString());
const sourcePackage = JSON.parse(await readFile('package.json', 'utf8'));
assert.equal(packaged.version, sourcePackage.version);
assert.equal(packaged.main, 'dist/main.js');
for (const name of ['dist/main.js', 'dist/preload.cjs', 'dist/renderer/index.html']) {
  assert.deepEqual(extract(name), await readFile(name), `Package has stale built source: ${name}`);
}
const html = extract('dist/renderer/index.html').toString();
const assets = Array.from(html.matchAll(/(?:src|href)="\.\/([^"?]+)"/g), (match) => `dist/renderer/${match[1]}`);
assert(assets.some((name) => name.endsWith('.js')) && assets.some((name) => name.endsWith('.css')), 'Renderer JS/CSS missing');
for (const name of assets) {
  assert(files.includes(name), `Missing renderer asset: ${name}`);
  assert.deepEqual(extract(name), await readFile(name), `Package renderer asset differs: ${name}`);
}

const inspection = await mkdtemp(join(tmpdir(), 'pf-package-inspect-'));
let runtimeVerification;
try {
  asar.extractAll(archive, inspection);
  // Node validates the bundled SDK dependency graph without Electron or any network call.
  const sdk = await import(pathToFileURL(join(inspection, 'node_modules/@siwc/local/dist/index.js')).href);
  assert.equal(typeof sdk.createChatGPT, 'function');
  assert.equal(typeof sdk.ChatGPTError, 'function');
  {
    const runtimeRoot = join(dirname(archive), 'runtime');
    const bindingName = 'third-party/runtime-inventory-binding.json';
    assert(files.includes(bindingName), 'Missing runtime inventory binding');
    const inventory = await verifyRuntime(runtimeRoot, join(inspection, bindingName));
    const generated = JSON.parse(await readFile(join('runtime', `${process.platform}-${process.arch}`, 'runtime-inventory.json'), 'utf8'));
    assert.deepEqual(inventory, generated, 'Packaged runtime differs from verified build output');
    const engineRoot = join(runtimeRoot, inventory.paths.sitePackages, 'paper_factory');
    const sourceNames = (await readdir('../src/paper_factory', { recursive: true })).filter(name => /\.(?:py|mjs)$/.test(name)).sort();
    assert.deepEqual((await readdir(engineRoot, { recursive: true })).filter(name => /\.(?:py|mjs)$/.test(name)).sort(), sourceNames,
      'Runtime contains obsolete or missing engine source');
    for (const name of sourceNames) {
      const engineMember = join(engineRoot, name);
      assert.deepEqual(await readFile(engineMember), await readFile(join('../src/paper_factory', name)), `Stale bundled engine source: ${name}`);
    }
    runtimeVerification = { fileCount: inventory.files.length, fullHashesVerified: true,
      inventorySha256: createHash('sha256').update(await readFile(join(runtimeRoot, 'runtime-inventory.json'))).digest('hex'),
      executables: inventory.executables, appEngineSourceMatches: true };
  }
} finally {
  const target = resolve(inspection);
  assert(target.startsWith(resolve(tmpdir()) + sep) && basename(target).startsWith('pf-package-inspect-'), 'Unsafe temporary cleanup path');
  await rm(target, { recursive: true, force: true });
}

const appDirectory = process.platform === 'darwin' ? resolve(dirname(archive), '../MacOS') : resolve(dirname(archive), '..');
const executable = process.platform === 'darwin' ? join(appDirectory, 'Paper Factory') : join(appDirectory, 'Paper Factory.exe');
const receipt = {
  scope: 'Static standalone app and complete runtime verification; no installed execution or live research',
  verifiedAt: new Date().toISOString(), appVersion: packaged.version, platform: process.platform,
  memberCount: files.length, sdkModuleImport: true, rendererAssetsPresent: true,
  liveSignIn: 'unverified', liveInference: 'unverified', restartAuthentication: 'unverified',
  researchRuntime: runtimeVerification,
  files: await Promise.all([archive, executable, ...(await readdir(release)).filter(name => /\.(exe|dmg)$/.test(name)).map(name => join(release, name))].map(async (path) => ({
    path: relative(release, path).replaceAll('\\', '/'), size: (await stat(path)).size,
    sha256: createHash('sha256').update(await readFile(path)).digest('hex'),
  }))),
};
await writeFile(join(release, 'standalone-package-verification.json'), JSON.stringify(receipt, null, 2) + '\n');
console.log(JSON.stringify(receipt, null, 2));
