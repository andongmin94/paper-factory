import assert from 'node:assert/strict';
import test from 'node:test';
import { randomUUID } from 'node:crypto';
import { mkdtemp, writeFile, readFile, realpath, rm, mkdir } from 'node:fs/promises';
import { spawn } from 'node:child_process';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { runInNewContext } from 'node:vm';
import { fileURLToPath } from 'node:url';
import asar from '@electron/asar';
import { CHROMIUM_PROTOCOL, validateChromiumRequest, validateLayoutRequest, boundedJson, chromiumSourceURL, sha256 } from '../dist/chromium-contract.js';
import { chromiumBinding } from '../dist/engine.js';

const file = text => ({ text, sha256: sha256(text) });

test('built renderer authority preserves strict private frames after toString and CDP-style reevaluation', async () => {
  const worker = await readFile(new URL('../dist/chromium-worker.mjs', import.meta.url), 'utf8');
  const begin = worker.indexOf('function rendererAuthority(');
  const end = worker.indexOf('// src/main/chromium-worker.ts', begin);
  assert(begin >= 0 && end > begin, 'Actual compiled renderer authority must be present');
  const authority = runInNewContext(`(${worker.slice(begin, end).trim()})`);
  const serialized = Function.prototype.toString.call(authority);
  assert.match(serialized, /^function rendererAuthority\([^)]*\)\s*\{\s*["']use strict["'];/);
  const restored = runInNewContext(`(${serialized})`);
  for (const privateFrame of ['caller', 'arguments']) {
    assert.throws(() => restored[privateFrame], error => error.name === 'TypeError');
  }
});
function request() { return { protocol: CHROMIUM_PROTOCOL, command: 'GO', nonce: randomUUID().replaceAll('-', ''),
  source_files: { 'first.js': file('window.J={};'), 'last.js': file('J.fn=()=>1') }, source_order: ['first.js', 'last.js'],
  production_entrypoint: 'last.js:J.fn', experiment_files: { 'run.mjs': file('export default async function run(){return {}}') },
  entrypoint: 'run.mjs', scientific_inputs: { 'source/notes.md': { name: 'notes.md', ...file('가🙂\r\n') } }, fonts: {}, timeout_seconds: 10 }; }

test('Chromium GO freezes exact full classic order, async ESM and scientific input bytes', () => {
  const value = request(); assert.equal(validateChromiumRequest(value), value);
  assert.equal(value.scientific_inputs['source/notes.md'].text, '가🙂\r\n');
});
for (const [name, mutate] of [
  ['source bytes replaced', value => value.source_files['last.js'].text += ' '],
  ['duplicate order', value => value.source_order = ['last.js', 'last.js']],
  ['selected script not final', value => value.source_order.reverse()],
  ['unfrozen module', value => value.source_order[0] = 'missing.js'],
  ['prototype selector expression', value => value.production_entrypoint = 'last.js:J["fn"]'],
  ['host path', value => value.source_order = ['C:/first.js', 'last.js']],
  ['generated host dependency', value => value.experiment_files['../evil.mjs'] = file('')],
  ['source surrogate', value => value.source_files['last.js'] = file('\ud800')],
  ['scientific stale hash', value => value.scientific_inputs['source/notes.md'].text += ' '],
  ['font path escapes', value => value.fonts['../font.woff2'] = { content: 'AA==', size: 1, sha256: sha256(Buffer.from([0])) }],
  ['font bytes replaced', value => value.fonts['font.woff2'] = { content: 'AA==', size: 1, sha256: sha256('other') }],
  ['font noncanonical base64', value => value.fonts['font.woff2'] = { content: 'AA', size: 1, sha256: sha256(Buffer.from([0])) }],
  ['unrecognized font format', value => value.fonts['font.exe'] = { content: 'AA==', size: 1, sha256: sha256(Buffer.from([0])) }],
  ['extra launch limits', value => value.limits = {}],
  ['invalid nonce', value => value.nonce = 'model-picked'],
]) test(`Chromium GO rejects ${name} before dispatch`, () => { const value = request(); mutate(value); assert.throws(() => validateChromiumRequest(value)); });

test('layout requests bind only frozen font paths or explicitly unverified system fallbacks', () => {
  const font = { content: 'AA==', size: 1, sha256: sha256(Buffer.from([0])) };
  const value = { text: '가A🙂', font: 'source/font.woff2', font_size: 16, width: 200, direction: 'ltr' };
  assert.throws(() => validateLayoutRequest(JSON.stringify(value), { 'font.woff2': font }));
  value.font = 'source:font.woff2';
  assert.deepEqual(validateLayoutRequest(JSON.stringify(value), { 'font.woff2': font }), value);
  for (const mutate of [x => x.font = 'system:invented', x => x.font = 'source:missing.woff2', x => x.width = 0,
    x => x.font_size = 257, x => x.direction = 'sideways', x => x.url = 'https://example.invalid', x => x.text = '', x => x.text = '\0']) {
    const changed = { ...value }; mutate(changed); assert.throws(() => validateLayoutRequest(JSON.stringify(changed), { 'font.woff2': font }));
  }
});

test('Chromium finite JSON rejects overflow numbers, deep structure and oversized UTF-8 bytes', () => {
  assert.throws(() => boundedJson('{"value":1e999}'), /finite/);
  assert.throws(() => boundedJson('['.repeat(34) + '0' + ']'.repeat(34)), /structure/);
  assert.throws(() => boundedJson(JSON.stringify('가'.repeat(10)), 20), /byte/);
  assert.deepEqual(boundedJson('{"zero":0,"negative":-1,"empty":[]}'), { zero: 0, negative: -1, empty: [] });
});

test('frozen Unicode module paths use one canonical encoded URL without changing source names', () => {
  assert.equal(chromiumSourceURL('pf-science://production-abc', 'src/한 글#%?.js'), 'pf-science://production-abc/src/%ED%95%9C%20%EA%B8%80%23%25%3F.js');
  const value = request(), bytes = value.source_files['last.js'];
  delete value.source_files['last.js']; value.source_files['한 글#.js'] = bytes;
  value.source_order[1] = '한 글#.js'; value.production_entrypoint = '한 글#.js:J.fn';
  assert.equal(validateChromiumRequest(value).source_order[1], '한 글#.js');
});

test('explicit Chromium binding hashes only supplied trusted files and never uses ambient PATH', async () => {
  const scratch = await realpath(await mkdtemp(join(tmpdir(), 'pf-chromium-binding-')));
  try {
    const executable = join(scratch, 'electron.bin'), worker = join(scratch, 'worker.mjs'), app_entry = join(scratch, 'bootstrap.js');
    await writeFile(executable, 'Synthetic executable; never launched'); await writeFile(worker, 'Synthetic trusted worker'); await writeFile(app_entry, 'Synthetic bootstrap');
    const binding = await chromiumBinding({ executable, worker, app_entry, assets: [] });
    assert.equal(binding.executable.path, executable); assert.equal(binding.worker.sha256, sha256(await readFile(worker)));
    assert.equal(binding.app_entry.sha256, sha256(await readFile(app_entry))); assert.deepEqual(binding.assets, []);
    await assert.rejects(chromiumBinding({ executable: 'electron', worker, assets: [] }), /경로/);
    for (const field of ['executable', 'worker', 'app_entry', 'assets']) {
      await assert.rejects(chromiumBinding({ executable, worker, app_entry, assets: [],
        [field]: field === 'assets' ? [scratch] : scratch }), /경로/);
    }
    await mkdir(join(scratch, 'nested'));
    await assert.rejects(chromiumBinding({ executable: `${scratch}${sep}nested${sep}..${sep}electron.bin`, worker, assets: [] }), /경로/);
  } finally {
    assert(resolve(scratch).startsWith(await realpath(tmpdir()) + sep));
    await rm(scratch, { recursive: true, force: true });
  }
});

test('Electron binds physical ASAR bytes while retaining directory and canonical-path guards', { skip: process.platform !== 'win32', timeout: 30000 }, async () => {
  const scratch = await realpath(await mkdtemp(join(tmpdir(), 'pf-chromium-asar-')));
  let child;
  try {
    const input = join(scratch, 'archive-input'), archive = join(scratch, 'fixture.asar');
    await mkdir(input);
    await writeFile(join(input, 'fixture.txt'), 'Synthetic archive fixture; no research or credentials.');
    await asar.createPackage(input, archive);
    const worker = join(scratch, 'worker.mjs');
    await writeFile(worker, 'Synthetic trusted worker; never dispatched.');
    const electron = fileURLToPath(new URL('../node_modules/electron/dist/electron.exe', import.meta.url));
    const engine = new URL('../dist/engine.js', import.meta.url).href;
    const entry = join(scratch, 'fixture.mjs');
    await writeFile(entry, `
import { app, BrowserWindow } from 'electron';
import { stat } from 'node:fs/promises';
import { chromiumBinding } from ${JSON.stringify(engine)};
app.setPath('userData', ${JSON.stringify(scratch)});
(async () => {
const executable = ${JSON.stringify(electron)}, worker = ${JSON.stringify(worker)}, archive = ${JSON.stringify(archive)};
const virtual = await stat(archive);
if (!virtual.isDirectory() || virtual.isFile()) throw new Error('Fixture must expose Electron ASAR virtualization.');
const binding = await chromiumBinding({ executable, worker, assets: [archive] });
const rejected = [];
for (const field of ['executable', 'worker', 'app_entry', 'assets']) {
  try { await chromiumBinding({ executable, worker, assets: [archive], [field]: field === 'assets' ? [${JSON.stringify(scratch)}] : ${JSON.stringify(scratch)} }); }
  catch { rejected.push(field); }
}
process.stdout.write('PF_BINDING_FIXTURE_JSON=' + JSON.stringify({ binding, rejected, windows: BrowserWindow.getAllWindows().length, models: 0, research: 0 }) + '\\n', () => app.exit(0));
})().catch(error => { console.error(error.stack); app.exit(1); });
`);
    const env = { ...process.env };
    delete env.ELECTRON_RUN_AS_NODE; delete env.NODE_OPTIONS;
    child = spawn(electron, [entry], { env, windowsHide: true, stdio: ['ignore', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    child.stdout.on('data', part => stdout += part); child.stderr.on('data', part => stderr += part);
    const code = await new Promise((resolveExit, reject) => {
      const timer = setTimeout(() => { child.kill(); reject(new Error('Owned Electron ASAR fixture timed out.')); }, 15_000);
      child.once('error', error => { clearTimeout(timer); reject(error); });
      child.once('close', code => { clearTimeout(timer); resolveExit(code); });
    });
    assert.equal(code, 0, stderr);
    const line = stdout.split(/\r?\n/).find(line => line.startsWith('PF_BINDING_FIXTURE_JSON='));
    assert(line, stderr || stdout);
    const receipt = JSON.parse(line.slice('PF_BINDING_FIXTURE_JSON='.length));
    const raw = await readFile(archive);
    assert.deepEqual(receipt.binding.assets, [{ path: archive, size: raw.length, sha256: sha256(raw) }]);
    assert.deepEqual(receipt.rejected, ['executable', 'worker', 'app_entry', 'assets']);
    assert.equal(receipt.windows, 0); assert.equal(receipt.models, 0); assert.equal(receipt.research, 0);
  } finally {
    if (child && child.exitCode === null) child.kill();
    assert(resolve(scratch).startsWith(await realpath(tmpdir()) + sep));
    await rm(scratch, { recursive: true, force: true });
  }
});
