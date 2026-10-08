import assert from 'node:assert/strict';
import test from 'node:test';
import { randomUUID } from 'node:crypto';
import { mkdtemp, writeFile, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve, sep } from 'node:path';
import { runInNewContext } from 'node:vm';
import { CHROMIUM_PROTOCOL, validateChromiumRequest, boundedJson, chromiumSourceURL, sha256 } from '../dist/chromium-contract.js';
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
  entrypoint: 'run.mjs', scientific_inputs: { 'source/notes.md': { name: 'notes.md', ...file('가🙂\r\n') } }, timeout_seconds: 10 }; }

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
  ['extra launch limits', value => value.limits = {}],
  ['invalid nonce', value => value.nonce = 'model-picked'],
]) test(`Chromium GO rejects ${name} before dispatch`, () => { const value = request(); mutate(value); assert.throws(() => validateChromiumRequest(value)); });

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
  const scratch = await mkdtemp(join(tmpdir(), 'pf-chromium-binding-'));
  try {
    const executable = join(scratch, 'electron.bin'), worker = join(scratch, 'worker.mjs'), app_entry = join(scratch, 'bootstrap.js');
    await writeFile(executable, 'Synthetic executable; never launched'); await writeFile(worker, 'Synthetic trusted worker'); await writeFile(app_entry, 'Synthetic bootstrap');
    const binding = await chromiumBinding({ executable, worker, app_entry, assets: [] });
    assert.equal(binding.executable.path, executable); assert.equal(binding.worker.sha256, sha256(await readFile(worker)));
    assert.equal(binding.app_entry.sha256, sha256(await readFile(app_entry))); assert.deepEqual(binding.assets, []);
    await assert.rejects(chromiumBinding({ executable: 'electron', worker, assets: [] }), /경로/);
  } finally {
    assert(resolve(scratch).startsWith(resolve(tmpdir()) + sep));
    await rm(scratch, { recursive: true, force: true });
  }
});
