import assert from 'node:assert/strict';
import test from 'node:test';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { access, mkdir, mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { dirname, isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { sha256 } from '../dist/chromium-contract.js';

const desktop = resolve(dirname(fileURLToPath(import.meta.url)), '..'), repository = dirname(desktop);
const file = text => ({ text, sha256: sha256(text) });
const production = 'window.J={calculate(x){const c=document.createElement("canvas").getContext("2d");return {value:x+1,width:c.measureText("가").width}}};';
const run = 'export default async function run(){return {value:JSON.parse(await callProduction("[6]"))}}';
function packet(source = production, code = run) { return { source_files: { 'original.js': file(source) }, source_order: ['original.js'],
  production_entrypoint: 'original.js:J.calculate', experiment_files: { 'run.mjs': file(code) }, entrypoint: 'run.mjs', scientific_inputs: {}, timeout_seconds: 5 }; }
async function isolated(value, cancel_after) {
  // Python creates and journals a private Windows Job before writing GO to Electron.
  const python = process.env.PF_CHROMIUM_TEST_PYTHON ?? join(repository, '.venv/Scripts/python.exe');
  assert(isAbsolute(python), 'Chromium test interpreter must be an explicit absolute path');
  try { await access(python); } catch { assert.fail('Chromium integration requires the existing project .venv or explicit PF_CHROMIUM_TEST_PYTHON from the verified bundled inventory'); }
  const child = spawn(python, ['-I', '-B', join(desktop, 'tests/chromium-fixture.py')], {
    cwd: repository, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
  const stdout = [], stderr = []; let bytes = 0;
  child.stdout.on('data', piece => { bytes += piece.length; if (bytes > 18 * 1024 * 1024) child.kill(); else stdout.push(piece); });
  child.stderr.on('data', piece => stderr.push(piece));
  child.stdin.end(JSON.stringify({ packet: value, ...(cancel_after === undefined ? {} : { cancel_after }) }));
  const code = await new Promise((resolveExit, reject) => { child.once('error', reject); child.once('close', resolveExit); });
  assert.equal(code, 0, Buffer.concat(stderr).toString().slice(0, 2000));
  const receipt = JSON.parse(Buffer.concat(stdout).toString());
  assert.equal(receipt.cleanup_confirmed, true); assert.deepEqual(receipt.active_handle, {}); assert.deepEqual(receipt.journal.workers, []);
  assert.equal(receipt.scientific_execution_attempts, 0); assert.equal(receipt.model_requests, 0);
  return receipt;
}
const options = { skip: process.platform !== 'win32', timeout: 30000 };
function observed(receipt) { return JSON.parse(Buffer.from(receipt.envelope.observation_b64, 'base64').toString()); }
function failed(receipt, pattern) {
  assert(receipt.reason || receipt.exit_code !== 0 || receipt.envelope?.status === 'failed');
  if (pattern && receipt.envelope) assert.match(receipt.envelope.error, pattern);
}

test('hidden Chromium executes original Canvas function once with main-owned receipts and source provenance', options, async () => {
  const receipt = await isolated(packet());
  assert.equal(receipt.reason, null); assert.equal(receipt.exit_code, 0); assert.equal(receipt.envelope.status, 'succeeded');
  const value = observed(receipt); assert.equal(value.value.value, 7); assert(value.value.width > 0);
  assert.deepEqual(receipt.envelope.production_calls, [{ path: 'original.js', function: 'J.calculate', calls: 1 }]);
  const manifest = receipt.envelope.runtime_manifest;
  assert.equal(manifest.production_dispatch_attempts, 1); assert.equal(manifest.production_completed_calls, 1);
  assert.equal(manifest.call_receipts[0].input_sha256, sha256('[6]')); assert.equal(manifest.call_receipts[0].status, 'succeeded');
  assert.equal(manifest.function_provenance.script_sha256, sha256(production));
  assert.equal(manifest.loaded_source_scripts.length, 1); assert.equal(manifest.loaded_source_scripts[0].sha256, sha256(production));
  assert.deepEqual(manifest.renderer_capabilities, { production: { require: 'undefined', process: 'undefined' }, experiment: { require: 'undefined', process: 'undefined' } });
  assert.equal(manifest.distinct_renderer_processes, true); assert.equal(manifest.shutdown_windows_closed, true);
  assert.equal(manifest.owned_deny_proxy.host, '127.0.0.1');
  assert(Number.isInteger(manifest.owned_deny_proxy.port) && manifest.owned_deny_proxy.port > 0 && manifest.owned_deny_proxy.port <= 65535);
  assert.equal(manifest.owned_deny_proxy.close_requested, true);
});

test('original exception is observable while trusted dispatch count includes its rejection', options, async () => {
  const receipt = await isolated(packet('window.J={calculate(){throw Error("original rejection")}};',
    'export default async function run(){let message;try{await callProduction("[6]")}catch(e){message=e.message}return {message}}'));
  assert.equal(receipt.envelope.status, 'succeeded'); assert.match(observed(receipt).message, /original rejection/);
  assert.equal(receipt.envelope.runtime_manifest.call_receipts[0].status, 'rejected');
  assert.equal(receipt.envelope.runtime_manifest.production_dispatch_attempts, 1); assert.equal(receipt.envelope.runtime_manifest.production_completed_calls, 0);
});

test('evaluation-only delayed flush retains the caught negative frame and exit 1 after hidden windows close', options, async () => {
  const original = await readFile(join(desktop, 'dist/chromium-worker.mjs'), 'utf8');
  const listener = /app\.on\("window-all-closed", \(\) => \{\s*\}\);/g;
  assert.equal([...original.matchAll(listener)].length, 1, 'Expected the worker-owned window-close listener');
  const flush = 'process.stdout.write(line, () => app.exit(frame.status === "succeeded" ? 0 : 1));';
  assert.equal(original.split(flush).length, 2, 'Expected exactly one final worker result flush');
  // Instrumented copies expose the shutdown race; the production worker has no delay or test hook.
  const delayed = original.replace(flush, 'process.stdout.write(line, () => { process.stderr.write("EVALUATION_ONLY_DELAYED_FLUSH\\n"); setTimeout(() => app.exit(frame.status === "succeeded" ? 0 : 1), 250); });');
  const base = join(repository, '.paper-factory/is19'); await mkdir(base, { recursive: true });
  const scratch = await mkdtemp(join(base, 'flush-'));
  const controls = { old: delayed.replace(listener, ''), fixed: delayed };
  const evaluator = join(scratch, 'evaluate.py');
  await writeFile(evaluator, String.raw`"""Instrumented cloned-worker evaluation only; no model, auth, workflow or SCI."""
import hashlib, json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'src'))
from paper_factory.autonomous.browser_runner import BrowserRunner
sys.stdin.reconfigure(encoding='utf-8', errors='strict')
sys.stdout.reconfigure(encoding='utf-8', errors='strict')
value = json.load(sys.stdin)
def binding(path):
    path = Path(path).resolve(); raw = path.read_bytes()
    return {'path': str(path), 'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
worker = binding(value['worker'])
runner = BrowserRunner({'executable': binding(value['executable']), 'worker': worker,
    'app_entry': worker, 'assets': []}, supervisor_root=Path(value['home']))
try:
    receipt = runner._execute(value['packet'], purpose='probe')
    raw = receipt.pop('raw_response')
    with (runner.supervisor_root / 'original-worker-response.bin').open('xb') as stream: stream.write(raw)
    receipt.update(raw_response_bytes=len(raw), raw_response_sha256=hashlib.sha256(raw).hexdigest(),
                   model_requests=0, scientific_execution_attempts=0,
                   evaluation_scope='Cloned worker with delayed final flush callback, not unmodified whole-product execution')
    if value['control'] == 'fixed': runner._verify_manifest(receipt['envelope'], value['packet'])
finally:
    runner.close()
receipt['journal'] = json.loads((runner.supervisor_root / 'owned-workers.json').read_bytes())
with (runner.supervisor_root / 'receipt.json').open('x', encoding='utf-8') as stream: json.dump(receipt, stream, ensure_ascii=False, indent=2)
print(json.dumps(receipt, ensure_ascii=False))
`, { flag: 'wx' });
  const python = process.env.PF_CHROMIUM_TEST_PYTHON ?? join(repository, '.venv/Scripts/python.exe');
  assert(isAbsolute(python)); await access(python);
  const receipts = {};
  for (const [control, code] of Object.entries(controls)) {
    const worker = join(scratch, control + '.mjs'); await writeFile(worker, code, { flag: 'wx' });
    const child = spawn(python, ['-I', '-B', evaluator], { cwd: repository, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
    const stdout = [], stderr = []; let bytes = 0;
    child.stdout.on('data', piece => { bytes += piece.length; if (bytes > 18 * 1024 * 1024) child.kill(); else stdout.push(piece); });
    child.stderr.on('data', piece => stderr.push(piece));
    child.stdin.end(JSON.stringify({ control, worker, home: join(scratch, control + '-supervisor'),
      executable: join(desktop, 'node_modules/electron/dist/electron.exe'),
      packet: packet(production, 'export default async function run(){try{globalThis.callProduction=()=>"forged"}catch{}return {caught:true}}') }));
    const exitCode = await new Promise((resolveExit, reject) => { child.once('error', reject); child.once('close', resolveExit); });
    assert.equal(exitCode, 0, Buffer.concat(stderr).toString().slice(0, 2000));
    const receipt = receipts[control] = JSON.parse(Buffer.concat(stdout).toString());
    assert.equal(receipt.cleanup_confirmed, true); assert.equal(receipt.forced_stop_confirmed, true);
    assert.deepEqual(receipt.active_handle, {}); assert.deepEqual(receipt.journal.workers, []);
    assert.equal(receipt.model_requests, 0); assert.equal(receipt.scientific_execution_attempts, 0);
    assert.equal(await readFile(worker, 'utf8'), code, 'Instrumented worker bytes must remain unchanged');
  }
  assert(receipts.old.exit_code === 0 || !receipts.old.envelope,
    'Removing the listener must expose automatic quit before the delayed failure exit');
  assert.equal(receipts.fixed.reason, null); assert.equal(receipts.fixed.exit_code, 1);
  assert.equal(receipts.fixed.envelope.status, 'failed');
  assert.match(receipts.fixed.envelope.error, /Browser capability replacement: callProduction/);
  assert.equal(receipts.fixed.envelope.runtime_manifest.shutdown_windows_closed, true);
  assert.match(receipts.fixed.stderr, /EVALUATION_ONLY_DELAYED_FLUSH/);
  assert.equal(await readFile(join(desktop, 'dist/chromium-worker.mjs'), 'utf8'), original);
  await writeFile(join(scratch, 'control-comparison.json'), JSON.stringify({ scope: 'Synthetic instrumented shutdown comparison only',
    sourceWorkerSha256: sha256(original), cloneWorkerSha256: Object.fromEntries(Object.entries(controls).map(([name, code]) => [name, sha256(code)])),
    delayMs: 250, receipts, modelRequests: 0, SCI: 0 }, null, 2) + '\n', { flag: 'wx' });
});

for (const [name, source, code, pattern] of [
  ['inherited selector', 'window.J=Object.create({calculate(x){return x+1}});', run, /own data/],
  ['getter selector', 'window.J={get calculate(){return x=>x+1}};', run, /own data/],
  ['export replacement during real invocation', 'window.J={calculate(x){J.calculate=()=>999;return x+1}};', 'export default async function run(){try{await callProduction("[6]")}catch{}return {forged:true}}', /replaced/],
  ['sourceURL function spoof', 'window.J={calculate(x){return x+1}};\n//# sourceURL=pf-science:\/\/spoof\/original.js', run, /identity|location/],
  ['nonfinite result caught by generated code', 'window.J={calculate(){return {value:NaN}}};', 'export default async function run(){try{await callProduction("[6]")}catch{}return {forged:true}}', /finite/],
  ['result accessor', 'window.J={calculate(){return {get value(){return 7}}}};', run, /accessor/],
  ['own custom JSON projection', 'window.J={calculate(){return {toJSON(){return 999},value:7}}};', run, /projection/],
  ['gate replacement caught', production, 'export default async function run(){try{globalThis.callProduction=()=>"999"}catch{}return {forged:true}}', /replacement/],
  ['gate oversized arguments caught', production, 'export default async function run(){try{await callProduction(JSON.stringify(["x".repeat(1100000)]))}catch{}return {forged:true}}', /byte|bytes/],
  ['unawaited dispatch', production, 'export default async function run(){callProduction("[6]");return {early:true}}', /unawaited|promise/],
  ['blocked fetch caught', production, 'export default async function run(){try{await fetch("https://example.invalid/")}catch{}return {forged:true}}', /Forbidden/],
  ['blocked WebSocket caught', production, 'export default async function run(){try{new WebSocket("wss://example.invalid/")}catch{}return {forged:true}}', /Forbidden/],
  ['blocked WebRTC caught', production, 'export default async function run(){try{new RTCPeerConnection()}catch{}return {forged:true}}', /Forbidden/],
  ['blocked Worker caught', production, 'export default async function run(){try{new Worker("run.mjs")}catch{}return {forged:true}}', /Forbidden/],
  ['iframe escape', production, 'export default async function run(){const f=document.createElement("iframe");f.src="data:text/html,hello";document.body.appendChild(f);await new Promise(r=>setTimeout(r,50));return {forged:true}}', /policy|Network|Frame|context/],
  ['JavaScript dialog caught', production, 'export default async function run(){try{alert("test")}catch{}return {forged:true}}', /Forbidden/],
]) test(`Chromium boundary fails closed for ${name}`, options, async () => failed(await isolated(packet(source, code)), pattern));

test('inherited toJSON and Array iterator/numeric setter changes cannot forge private frames, args or owner', options, async () => {
  const source = 'Object.prototype.toJSON=function(){return {forged:true}};Array.prototype.toJSON=function(){return [999]};Array.prototype[Symbol.iterator]=function*(){yield 999};Object.defineProperty(Array.prototype,"0",{set(){},configurable:true});window.J={base:40,calculate(x){return {value:this.base+x}}};';
  const receipt = await isolated(packet(source, 'export default async function run(){Object.prototype.toJSON=()=>({forged:true});return {value:JSON.parse(await callProduction("[2]")),production_calls:999}}'));
  assert.equal(receipt.envelope.status, 'succeeded'); assert.equal(observed(receipt).value.value, 42);
  assert.equal(receipt.envelope.production_calls[0].calls, 1); assert.equal(receipt.envelope.runtime_manifest.call_receipts[0].input_sha256, sha256('[2]'));
});

test('original exception custom toString is never called to derive rejection text', options, async () => {
  const source = 'window.J={calculate(){throw {message:"own plain rejection",toString(){J.calculate=()=>999;return "forged"}}}};';
  const receipt = await isolated(packet(source, 'export default async function run(){let message;try{await callProduction("[6]")}catch(e){message=e.message}return {message}}'));
  assert.equal(receipt.envelope.status, 'succeeded'); assert.equal(observed(receipt).message, 'own plain rejection');
});

test('strict authority frames stay inaccessible to an original production Proxy trap', options, async () => {
  const source = `window.J={calculate(){
    const result={value:7,authority_frames:[]};
    return new Proxy(result,{ownKeys:function inspect(){
      let frame=inspect;
      for(let i=0;i<12;i++){
        try{frame=frame.caller;if(!frame)break;result.authority_frames.push(frame.name||"anonymous");}catch{break;}
      }
      return Reflect.ownKeys(result);
    }});
  }};`;
  const receipt = await isolated(packet(source, run));
  assert.equal(receipt.envelope.status, 'succeeded');
  assert.equal(observed(receipt).value.value, 7);
  assert.deepEqual(observed(receipt).value.authority_frames, []);
  assert.equal(receipt.envelope.runtime_manifest.production_dispatch_attempts, 1);
  assert.equal(receipt.envelope.runtime_manifest.function_provenance.script_sha256, sha256(source));
});

test('CSS, image and fresh-frame WebSocket attempts cannot reach a controlled loopback endpoint', options, async () => {
  let connections = 0;
  const server = createServer(socket => { connections++; socket.destroy(); });
  await new Promise((resolveListen, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolveListen); });
  try {
    const port = server.address().port;
    for (const body of [
      `const link=document.createElement('link');link.rel='stylesheet';link.href='http://127.0.0.1:${port}/blocked.css';document.head.appendChild(link);`,
      `const image=new Image();image.src='http://127.0.0.1:${port}/blocked.png';document.body.appendChild(image);`,
      `const frame=document.createElement('iframe');document.body.appendChild(frame);try{new frame.contentWindow.WebSocket('ws://127.0.0.1:${port}/blocked')}catch{}`,
    ]) {
      const code = `export default async function run(){await callProduction('[6]');${body}await new Promise(resolve=>setTimeout(resolve,50));return {forged:true}}`;
      const receipt = await isolated(packet(production, code)); failed(receipt);
      assert.equal(connections, 0, 'No request may reach the controlled endpoint');
      assert.equal(receipt.envelope.runtime_manifest.owned_deny_proxy.close_requested, true);
    }
  } finally { await new Promise(resolveClose => server.close(resolveClose)); }
});

test('fixture and scientific-input receipts retain exact UTF-8 bytes across isolated async gates', options, async () => {
  const value = packet(production, 'export default async function run(){return {input:JSON.parse(await readScientificInput("supporting-document-000000000000")),fixture:JSON.parse(await retainFixture("unicode","가🙂\\r\\n")),value:JSON.parse(await callProduction("[6]"))}}');
  value.scientific_inputs = { 'supporting-document-000000000000': { name: 'check.md', ...file('\ufeff가🙂\r\n') } };
  const receipt = await isolated(value); assert.equal(receipt.envelope.status, 'succeeded');
  assert.equal(observed(receipt).input.text, '\ufeff가🙂\r\n');
  assert.equal(Buffer.from(observed(receipt).fixture.content, 'base64').toString(), '가🙂\r\n');
  assert.equal(receipt.envelope.runtime_manifest.fixture_count, 1); assert.equal(receipt.envelope.runtime_manifest.scientific_input_reads, 1);
});

test('caught fixture record overflow stays fatal and retains prior bounded records', options, async () => {
  const code = 'export default async function run(){for(let i=0;i<5;i++){try{await retainFixture("fixture-"+i,"x".repeat(700000))}catch{}}return {forged:true}}';
  const receipt = await isolated(packet(production, code)); failed(receipt, /record byte/);
  assert.equal(receipt.envelope.runtime_manifest.fixture_count, 4);
  assert.equal(receipt.envelope.runtime_manifest.retained_fixtures.length, 4);
  assert(receipt.raw_response_bytes < 16 * 1024 * 1024);
});

test('never-resolving run reaches bounded deadline and leaves no owned Chromium processes', options, async () => {
  const value = packet(production, 'export default async function run(){await new Promise(()=>{});return {}}'); value.timeout_seconds = 1;
  failed(await isolated(value));
});
test('native cancel terminates the entire owned Chromium tree and never reruns the experiment', options, async () => {
  const receipt = await isolated(packet(production, 'export default async function run(){while(true){}}'), 0.8);
  assert.equal(receipt.reason, 'cancelled'); assert.equal(receipt.forced_stop_confirmed, true); assert.equal(receipt.owned_handles.length, 1);
});

test('JIZURA original three modules make one real Canvas-backed call without font or network claims', options, async context => {
  const names = ['src/01_util.js', 'src/02_fonts.js', 'src/03_text.js'], files = {};
  const paths = names.map(name => name === 'src/02_fonts.js' ? join(repository, '.paper-factory/submission-quality-20261007/verification/jizura-browser-capability-01414/02_fonts.original.js') : join(repository, '.paper-factory/papers-20261006/selection-a/JIZURA', name));
  try { await Promise.all(paths.map(path => access(path))); } catch {
    context.skip('Optional frozen JIZURA source cache is absent; no source download, fabrication, model or SCI is authorized by this capability test'); return;
  }
  for (const name of names) {
    const path = name === 'src/02_fonts.js' ? join(repository, '.paper-factory/submission-quality-20261007/verification/jizura-browser-capability-01414/02_fonts.original.js') : join(repository, '.paper-factory/papers-20261006/selection-a/JIZURA', name);
    files[name] = file(await readFile(path, 'utf8'));
  }
  const input = { text: 'Aあ文\nB', font: 'gothic_black', size: 40, track: 0.05, align: 'left', vertical: false, sx: 1, sy: 1 };
  const value = packet(); value.source_files = files; value.source_order = names; value.production_entrypoint = 'src/03_text.js:J.measure';
  value.experiment_files['run.mjs'] = file(`export default async function run(){return {value:JSON.parse(await callProduction(${JSON.stringify(JSON.stringify([input]))}))}}`);
  const receipt = await isolated(value); assert.equal(receipt.envelope.status, 'succeeded');
  const result = observed(receipt).value; assert(result.w > 0 && result.h > 0); assert.equal(result.lay.length, 4);
  assert.equal(receipt.envelope.production_calls[0].calls, 1); assert.equal(receipt.envelope.runtime_manifest.loaded_source_scripts.length, 3);
  assert.equal(receipt.envelope.runtime_manifest.entire_electron_binary_closure_verified, undefined);
});
