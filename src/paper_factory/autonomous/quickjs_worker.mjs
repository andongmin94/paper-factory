// Trusted Wasm embedder. Source and experiment text are never executed by Node.
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { stripTypeScriptTypes } from 'node:module';
import { join, posix } from 'node:path';
import { pathToFileURL } from 'node:url';

const MAX_INPUT = 24 * 1024 * 1024;
const MAX_OBSERVATION = 8 * 1024 * 1024;
const MAX_GATE = 1024 * 1024;
const MAX_CALLS = 65536;
const MAX_IMPORTS = 512;
const MAX_IMPORT_BYTES = 64 * 1024;
const LINEAR_BYTES = 64 * 1024 * 1024;
const HEAP_BYTES = 16 * 1024 * 1024;
const TYPESCRIPT_OPTIONS = Object.freeze({ mode: 'strip', sourceMap: false });
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const guardianParent = process.env.PF_QUICKJS_GUARDIAN === undefined ? null : Number(process.env.PF_QUICKJS_GUARDIAN);
if (guardianParent !== null && (process.platform !== 'darwin' || !Number.isInteger(guardianParent) || guardianParent < 2 || process.ppid !== guardianParent)) {
  throw new Error('Trusted guardian parent identity differs');
}
const pieces = [];
let inputSize = 0;
for await (const piece of process.stdin) {
  inputSize += piece.length;
  if (inputSize > MAX_INPUT) throw new Error('Trusted request exceeds input boundary');
  pieces.push(piece);
}
const request = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(pieces)));
if (!Number.isInteger(request.timeout_seconds) || request.timeout_seconds < 1 || request.timeout_seconds > 3600) {
  throw new Error('Invalid trusted deadline');
}
const root = process.argv[2];
const { newQuickJSWASMModuleFromVariant, newVariant } = await import(pathToFileURL(join(root, 'node_modules/quickjs-emscripten-core/dist/index.mjs')).href);
const { default: variant } = await import(pathToFileURL(join(root, 'node_modules/@jitl/quickjs-wasmfile-release-sync/dist/index.mjs')).href);
const wasm = readFileSync(join(root, 'node_modules/@jitl/quickjs-wasmfile-release-sync/dist/emscripten-module.wasm'));
const source = new Map(Object.entries(request.source_files));
const experiment = new Map(Object.entries(request.experiment_files));
for (const files of [source, experiment]) {
  for (const [name, record] of files) {
    if (!/\.(?:js|mjs|cjs|ts)$/.test(name) || name.startsWith('/') || name.includes('\\') || posix.normalize(name) !== name || name.split('/').includes('..')) throw new Error('Invalid frozen module name');
    if (typeof record.text !== 'string' || record.text.includes('\0') || !record.text.isWellFormed() || sha256(Buffer.from(record.text, 'utf8')) !== record.sha256) throw new Error('Frozen module bytes differ or contain unsupported text');
  }
}
const compiled = new Map();
const manifest = { backend: 'quickjs-wasm', library_version: '0.32.0', node_version: process.version,
  wasm_sha256: sha256(wasm), production_entrypoint: request.production_entrypoint,
  source_files: Object.fromEntries([...source].map(([name, item]) => [name, { original_sha256: item.sha256 }])),
  compiled_files: {}, experiment_files: Object.fromEntries([...experiment].map(([name, item]) => [name, { sha256: item.sha256 }])),
  transformer: { name: 'node:module.stripTypeScriptTypes', version: process.version,
    options: TYPESCRIPT_OPTIONS, options_scope: 'shared', native_typescript_execution: false },
  bridge: 'controller-held-wasm-call-gate', result_serialization: 'Captured JSON.stringify projection; Map/Set entries and non-JSON values are not preserved',
  json_projection_only: true, unsupported_return_encodings: ['Map entries', 'Set entries', 'BigInt', 'undefined', 'functions'],
  native_node_execution: false, native_host_rss_limit_claimed: false,
  guardian_parent_monitoring: guardianParent !== null };
let deadline = Date.now() + request.timeout_seconds * 1000;
let calls = 0;
let completedCalls = 0;
let fixtureBytes = 0;
let fixtureCount = 0;
const labels = new Set();
const imports = [];
let importAttempts = 0;
let importBytes = 0;
let infrastructureFailure = null;
let rawObservation = null;

function boundary(message) {
  infrastructureFailure ||= message;
  return new Error(message);
}

function moduleText(name) {
  if (compiled.has(name)) return compiled.get(name);
  const item = source.get(name);
  if (!item) throw new Error('Module is absent from frozen source map');
  const transformationOptions = name.endsWith('.ts') ? { ...TYPESCRIPT_OPTIONS, sourceUrl: `source/${name}` } : null;
  const text = transformationOptions ? stripTypeScriptTypes(item.text, transformationOptions) : item.text;
  compiled.set(name, text);
  manifest.compiled_files[name] = { original_sha256: item.sha256, compiled_sha256: sha256(Buffer.from(text, 'utf8')),
    transformation: transformationOptions ? 'node:module.stripTypeScriptTypes' : 'identity',
    ...(transformationOptions ? { transformation_options: transformationOptions } : {}) };
  return text;
}

async function guest(namespace, files) {
  const memory = new WebAssembly.Memory({ initial: 256, maximum: LINEAR_BYTES / 65536 });
  const module = await newQuickJSWASMModuleFromVariant(newVariant(variant, {
    wasmBinary: wasm.buffer.slice(wasm.byteOffset, wasm.byteOffset + wasm.byteLength), wasmMemory: memory,
  }));
  if (module.getWasmMemory() !== memory) throw new Error('Wasm memory binding is unavailable');
  let denied = false;
  try { memory.grow(LINEAR_BYTES / 65536); } catch (error) { denied = error instanceof RangeError; }
  if (!denied) throw new Error('Wasm memory maximum is not enforced');
  const runtime = module.newRuntime();
  runtime.setMemoryLimit(HEAP_BYTES);
  runtime.setMaxStackSize(512 * 1024);
  runtime.setInterruptHandler(() => {
    if (guardianParent !== null && process.ppid !== guardianParent) {
      infrastructureFailure ||= 'Trusted guardian parent exited';
      return true;
    }
    return Date.now() > deadline;
  });
  runtime.setModuleLoader(name => {
    const bytes = Buffer.byteLength(name, 'utf8');
    if (++importAttempts > MAX_IMPORTS || bytes > 256 || importBytes + bytes > MAX_IMPORT_BYTES) throw boundary('Module import boundary exceeded');
    importBytes += bytes;
    imports.push(name);
    if (!name.startsWith(`${namespace}/`)) throw boundary('Cross-guest module import is unavailable');
    const relative = name.slice(namespace.length + 1);
    if (!files.has(relative)) throw boundary('Module is absent from frozen map');
    return namespace === 'source' ? moduleText(relative) : files.get(relative).text;
  }, (base, name) => {
    if (Buffer.byteLength(name, 'utf8') > 256 || !name.startsWith('./') && !name.startsWith('../')) throw boundary('Only frozen relative imports are available');
    const result = posix.normalize(posix.join(posix.dirname(base), name));
    if (!result.startsWith(`${namespace}/`) || !files.has(result.slice(namespace.length + 1))) throw boundary('Import escapes frozen module map');
    return result;
  });
  return { runtime, context: runtime.newContext(), memory };
}

function readError(context, handle) {
  let message;
  let name = 'Error';
  try {
    const value = context.getProp(handle, 'message');
    try { message = context.getString(value).slice(0, 1000); } finally { value.dispose(); }
  } catch { message = 'Guest operation failed'; }
  try {
    const value = context.getProp(handle, 'name');
    try { name = context.getString(value).slice(0, 80); } finally { value.dispose(); }
  } catch {}
  handle.dispose();
  const error = new Error(message);
  error.guestName = name;
  return error;
}

function evaluate(guest, text, filename, options) {
  const result = guest.context.evalCode(text, filename, options);
  if (result.error) throw readError(guest.context, result.error);
  return result.value;
}

function namespaceResult(guest, handle) {
  let state = guest.context.getPromiseState(handle);
  if (state.type === 'pending') {
    const jobs = guest.runtime.executePendingJobs(512);
    if (jobs.error) { handle.dispose(); throw readError(guest.context, jobs.error); }
    state = guest.context.getPromiseState(handle);
  }
  if (state.type === 'rejected') { handle.dispose(); throw readError(guest.context, state.error); }
  if (state.type !== 'fulfilled') { handle.dispose(); throw new Error('Asynchronous module completion is unsupported'); }
  if (!state.notAPromise) handle.dispose();
  return state.value;
}

function boundedJson(text, limit = MAX_GATE) {
  if (typeof text !== 'string' || Buffer.byteLength(text, 'utf8') > limit) throw new Error('JSON byte boundary exceeded');
  const value = JSON.parse(text);
  let nodes = 0;
  const visit = (item, depth) => {
    if (++nodes > 200000 || depth > 64) throw new Error('JSON structure boundary exceeded');
    if (item && typeof item === 'object') for (const child of Object.values(item)) visit(child, depth + 1);
  };
  visit(value, 0);
  return value;
}

let productionGuest;
let experimentGuest;
const handles = [];
let envelope;
try {
  productionGuest = await guest('source', source);
  experimentGuest = await guest('experiment', experiment);
  const pc = productionGuest.context;
  const ec = experimentGuest.context;
  const productionJson = pc.getProp(pc.global, 'JSON');
  const parse = pc.getProp(productionJson, 'parse');
  const stringify = pc.getProp(productionJson, 'stringify');
  const object = pc.getProp(pc.global, 'Object');
  const hasOwn = pc.getProp(object, 'hasOwn');
  const experimentJson = ec.getProp(ec.global, 'JSON');
  const observationStringify = ec.getProp(experimentJson, 'stringify');
  handles.push(productionJson, parse, stringify, object, hasOwn, experimentJson, observationStringify);
  function experimentString(handle) {
    // The library's C-string reader truncates raw NULs. Captured JSON.stringify
    // escapes them before crossing that boundary, preserving the original text.
    const encoded = ec.callFunction(observationStringify, ec.undefined, handle);
    if (encoded.error) throw readError(ec, encoded.error);
    try {
      const text = JSON.parse(ec.getString(encoded.value));
      if (typeof text !== 'string' || !text.isWellFormed()) throw new Error('Guest string is not lossless UTF-8 text');
      return text;
    } finally { encoded.value.dispose(); }
  }
  const separator = request.production_entrypoint.lastIndexOf(':');
  const selected = request.production_entrypoint.slice(0, separator);
  const functionName = request.production_entrypoint.slice(separator + 1);
  const text = moduleText(selected);
  let exports;
  if (selected.endsWith('.cjs') || !selected.endsWith('.ts') && /\bmodule\s*\.\s*exports\b/.test(text)) {
    evaluate(productionGuest, 'globalThis.module={exports:{}};', 'trusted-umd-adapter.js').dispose();
    evaluate(productionGuest, text, `source/${selected}`).dispose();
    const commonjs = pc.getProp(pc.global, 'module');
    handles.push(commonjs);
    exports = pc.getProp(commonjs, 'exports');
  } else exports = namespaceResult(productionGuest, evaluate(productionGuest, text, `source/${selected}`, { type: 'module' }));
  handles.push(exports);
  let original = exports;
  for (const name of functionName.split('.')) {
    const key = pc.newString(name);
    let owned;
    try { owned = pc.callFunction(hasOwn, pc.undefined, original, key); } finally { key.dispose(); }
    if (owned.error) throw readError(pc, owned.error);
    try { if (pc.dump(owned.value) !== true) throw new Error('Production selector must traverse own exports'); }
    finally { owned.value.dispose(); }
    original = pc.getProp(original, name);
    handles.push(original);
  }
  if (pc.typeof(original) !== 'function') throw new Error('Frozen production export is not callable');
  const productionGate = ec.newFunction('callProduction', arg => {
    const argv = [];
    let parsed;
    try {
      if (calls >= MAX_CALLS) throw new Error('Production dispatch budget exceeded');
      if (!arg || ec.typeof(arg) !== 'string') throw new Error('Production gate accepts JSON argument-array text');
      const raw = experimentString(arg);
      const values = boundedJson(raw);
      if (!Array.isArray(values) || values.length > 16) throw new Error('Production gate requires at most sixteen arguments');
      const string = pc.newString(raw);
      try { parsed = pc.callFunction(parse, pc.undefined, string); } finally { string.dispose(); }
      if (parsed.error) throw readError(pc, parsed.error);
      for (let index = 0; index < values.length; index++) argv.push(pc.getProp(parsed.value, index));
      calls += 1; // Controller-owned invocation evidence includes actual original exceptions.
      const returned = pc.callFunction(original, pc.undefined, argv);
      if (returned.error) {
        const error = readError(pc, returned.error);
        error.productionRejection = error.guestName !== 'InternalError' && !/out of memory|interrupted|stack overflow/i.test(error.message) && Date.now() <= deadline;
        throw error;
      }
      completedCalls += 1;
      let encoded;
      try {
        const state = pc.getPromiseState(returned.value);
        if (!state.notAPromise) {
          if (state.type === 'fulfilled') state.value.dispose();
          if (state.type === 'rejected') state.error.dispose();
          throw new Error('Asynchronous production exports are unsupported');
        }
        encoded = pc.callFunction(stringify, pc.undefined, returned.value);
      } finally { returned.value.dispose(); }
      if (encoded.error) throw readError(pc, encoded.error);
      try {
        if (pc.typeof(encoded.value) !== 'string') throw new Error('Production result has no JSON projection');
        const rawOutput = pc.getString(encoded.value);
        boundedJson(rawOutput);
        return ec.newString(rawOutput);
      } finally { encoded.value.dispose(); }
    } catch (error) {
      if (!error.productionRejection) infrastructureFailure ||= String(error.message).slice(0, 1000);
      return { error: ec.newError(String(error.message).slice(0, 1000)) };
    }
    finally {
      argv.forEach(item => item.dispose());
      if (parsed?.value) parsed.value.dispose();
    }
  });
  const fixtureGate = ec.newFunction('retainFixture', (labelHandle, textHandle) => {
    try {
      if (!labelHandle || !textHandle || ec.typeof(labelHandle) !== 'string' || ec.typeof(textHandle) !== 'string') throw new Error('Fixture gate accepts a label and UTF-8 text');
      const label = experimentString(labelHandle);
      const text = experimentString(textHandle);
      const raw = Buffer.from(text, 'utf8');
      if (!label || label.length > 200 || /[\x00-\x1f\x7f]/.test(label) || labels.has(label)) throw new Error('Fixture label must be unique and bounded');
      if (++fixtureCount > 4096 || raw.length > MAX_OBSERVATION || fixtureBytes + raw.length > MAX_OBSERVATION) throw new Error('Fixture retention boundary exceeded');
      fixtureBytes += raw.length;
      labels.add(label);
      return ec.newString(JSON.stringify({ label, encoding: 'base64', content: raw.toString('base64'), sha256: sha256(raw) }));
    } catch (error) {
      infrastructureFailure ||= String(error.message).slice(0, 1000);
      return { error: ec.newError(String(error.message).slice(0, 1000)) };
    }
  });
  for (const [name, gate] of [['callProduction', productionGate], ['retainFixture', fixtureGate]]) {
    ec.defineProp(ec.global, name, { value: gate, configurable: false, writable: false });
    gate.dispose();
  }
  const experimentNamespace = namespaceResult(experimentGuest, evaluate(experimentGuest, experiment.get(request.entrypoint).text, `experiment/${request.entrypoint}`, { type: 'module' }));
  const run = ec.getProp(experimentNamespace, 'default');
  handles.push(experimentNamespace, run);
  if (ec.typeof(run) !== 'function') throw new Error('Experiment must export a default synchronous run function');
  const returned = ec.callFunction(run, ec.undefined);
  if (returned.error) throw readError(ec, returned.error);
  let encoded;
  try {
    const state = ec.getPromiseState(returned.value);
    if (!state.notAPromise) {
      if (state.type === 'fulfilled') state.value.dispose();
      if (state.type === 'rejected') state.error.dispose();
      throw new Error('Experiment run must return synchronously');
    }
    encoded = ec.callFunction(observationStringify, ec.undefined, returned.value);
  } finally { returned.value.dispose(); }
  if (encoded.error) throw readError(ec, encoded.error);
  let raw;
  try {
    if (ec.typeof(encoded.value) !== 'string') throw new Error('Experiment result is not a JSON envelope');
    raw = ec.getString(encoded.value);
    const observation = boundedJson(raw, MAX_OBSERVATION);
    if (!observation || typeof observation !== 'object' || Array.isArray(observation)) throw new Error('Experiment result must be an object');
    rawObservation = Buffer.from(raw, 'utf8');
  } finally { encoded.value.dispose(); }
  manifest.imports = imports;
  manifest.production_dispatch_attempts = calls;
  manifest.production_completed_calls = completedCalls;
  manifest.fixture_bytes = fixtureBytes;
  manifest.distinct_wasm_memories = productionGuest.memory !== experimentGuest.memory;
  manifest.hard_linear_growth_denied = true;
  if (infrastructureFailure) throw new Error('Fatal runtime boundary: ' + infrastructureFailure);
  envelope = { protocol: 'paper-factory-quickjs-v1', status: 'succeeded',
    observation_b64: rawObservation.toString('base64'), production_calls: calls ? [{ path: selected, function: functionName, calls }] : [],
    coverage_truncated: false, coverage_mechanism: 'controller-held-wasm-call-gate', runtime_manifest: manifest };
} catch (error) {
  envelope = { protocol: 'paper-factory-quickjs-v1', status: 'failed', error: String(error.message).slice(0, 1000),
    ...(rawObservation === null ? {} : { observation_b64: rawObservation.toString('base64') }),
    production_calls: calls ? [{ path: request.production_entrypoint.slice(0, request.production_entrypoint.lastIndexOf(':')),
      function: request.production_entrypoint.slice(request.production_entrypoint.lastIndexOf(':') + 1), calls }] : [],
    coverage_truncated: false, runtime_manifest: manifest };
} finally {
  // A disposal failure prevents emission of a success frame and produces nonzero exit.
  handles.reverse().forEach(handle => handle.dispose());
  for (const guest of [experimentGuest, productionGuest]) {
    if (guest) { guest.context.dispose(); guest.runtime.dispose(); }
  }
}
manifest.production_dispatch_attempts = calls;
manifest.production_completed_calls = completedCalls;
manifest.imports = imports;
manifest.fatal_infrastructure_failure = infrastructureFailure;
console.log(JSON.stringify(envelope));
if (envelope.status !== 'succeeded') process.exitCode = 1;
