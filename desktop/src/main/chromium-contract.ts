import { createHash } from 'node:crypto';
import { posix } from 'node:path';

// Installed Node 24 and Chromium 152 provide this ES2024 UTF-16 boundary check.
declare global { interface String { isWellFormed(): boolean } }

export const CHROMIUM_PROTOCOL = 'paper-factory-chromium-v1';
export const CHROMIUM_LIMITS = Object.freeze({ input: 24 * 1024 * 1024, frozen: 16 * 1024 * 1024,
  observation: 8 * 1024 * 1024, gate: 1024 * 1024, records: 4 * 1024 * 1024, calls: 65536, fixtures: 4096, scientificReads: 512,
  scientificInputs: 28, files: 512, frame: 16 * 1024 * 1024, nodes: 100000, depth: 32 });
export const sha256 = (value: Buffer | string) => createHash('sha256').update(value).digest('hex');
export function chromiumSourceURL(origin: string, name: string) {
  return origin + '/' + name.split('/').map(part => encodeURIComponent(part).replace(/[!'()*]/g, character => '%' + character.charCodeAt(0).toString(16).toUpperCase())).join('/');
}
export type FrozenFile = { text: string; sha256: string };
export type ChromiumRequest = { protocol: typeof CHROMIUM_PROTOCOL; command: 'GO'; nonce: string;
  source_files: Record<string, FrozenFile>; source_order: string[]; production_entrypoint: string;
  experiment_files: Record<string, FrozenFile>; entrypoint: string;
  scientific_inputs: Record<string, FrozenFile & { name: string }>; timeout_seconds: number };

export function boundedJson(raw: unknown, max = CHROMIUM_LIMITS.gate): unknown {
  if (typeof raw !== 'string' || !raw || !raw.isWellFormed() || Buffer.byteLength(raw) > max) throw new Error('JSON byte boundary exceeded');
  const value: unknown = JSON.parse(raw);
  let nodes = 0;
  function visit(item: unknown, depth: number) {
    if (++nodes > CHROMIUM_LIMITS.nodes || depth > CHROMIUM_LIMITS.depth) throw new Error('JSON structure boundary exceeded');
    if (typeof item === 'number' && !Number.isFinite(item)) throw new Error('Non-finite JSON number');
    if (typeof item === 'string' && !item.isWellFormed()) throw new Error('Unsupported JSON string');
    if (item && typeof item === 'object') for (const child of Object.values(item)) visit(child, depth + 1);
  }
  visit(value, 0);
  return value;
}

export function frozenName(name: unknown, classic = false): asserts name is string {
  if (typeof name !== 'string' || !name || !name.isWellFormed() || name.length > 256 || /[\\:\x00-\x1f\x7f]/.test(name) ||
      name.startsWith('/') || posix.normalize(name) !== name || name.split('/').some(part => part === '.' || part === '..') ||
      !(classic ? /\.js$/ : /\.(?:js|mjs)$/).test(name)) throw new Error('Invalid frozen module name');
}

export function validateChromiumRequest(value: unknown): ChromiumRequest {
  const request = value as ChromiumRequest;
  if (!request || typeof request !== 'object' || Array.isArray(request) ||
      Object.keys(request).sort().join(',') !== 'command,entrypoint,experiment_files,nonce,production_entrypoint,protocol,scientific_inputs,source_files,source_order,timeout_seconds' ||
      request.protocol !== CHROMIUM_PROTOCOL || request.command !== 'GO' || !/^[a-f0-9]{32}$/.test(request.nonce) ||
      !Number.isInteger(request.timeout_seconds) || request.timeout_seconds < 1 || request.timeout_seconds > 3600) throw new Error('Invalid Chromium GO frame');
  let bytes = 0;
  for (const [files, classic] of [[request.source_files, true], [request.experiment_files, false]] as const) {
    if (!files || typeof files !== 'object' || Array.isArray(files) || !Object.keys(files).length || Object.keys(files).length > CHROMIUM_LIMITS.files) throw new Error('Invalid frozen module map');
    for (const [name, item] of Object.entries(files)) {
      frozenName(name, classic);
      if (!item || Object.keys(item).sort().join(',') !== 'sha256,text' || typeof item.text !== 'string' ||
          item.text.includes('\0') || !item.text.isWellFormed() || sha256(item.text) !== item.sha256) throw new Error('Frozen source bytes differ');
      bytes += Buffer.byteLength(item.text);
    }
  }
  if (!Array.isArray(request.source_order) || request.source_order.length !== Object.keys(request.source_files).length ||
      new Set(request.source_order).size !== request.source_order.length || request.source_order.some(name => !Object.hasOwn(request.source_files, name))) throw new Error('Frozen source order differs');
  if (typeof request.production_entrypoint !== 'string' || !/^.+:[A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*$/.test(request.production_entrypoint)) throw new Error('Invalid production selector');
  const [selected, functionName] = request.production_entrypoint.split(':');
  frozenName(selected, true);
  if (request.source_order.at(-1) !== selected || functionName!.length > 128) throw new Error('Selected production module must be last');
  frozenName(request.entrypoint);
  if (!Object.hasOwn(request.experiment_files, request.entrypoint)) throw new Error('Generated entry is not frozen');
  if (!request.scientific_inputs || typeof request.scientific_inputs !== 'object' || Array.isArray(request.scientific_inputs) ||
      Object.keys(request.scientific_inputs).length > CHROMIUM_LIMITS.scientificInputs) throw new Error('Invalid scientific input map');
  for (const [key, item] of Object.entries(request.scientific_inputs)) {
    if (!item || Object.keys(item).sort().join(',') !== 'name,sha256,text' ||
        typeof item.name !== 'string' || !item.name || item.name.length > 512 || /[\\:\x00-\x1f\x7f]/.test(item.name) ||
        item.name.startsWith('/') || posix.normalize(item.name) !== item.name || item.name.split('/').some(part => part === '.' || part === '..') ||
        typeof item.text !== 'string' || !item.text.isWellFormed() || item.text.includes('\0') || sha256(item.text) !== item.sha256 ||
        !(key === `source/${item.name}` || /^supporting-document-[a-f0-9]{12}$/.test(key) && !item.name.includes('/'))) throw new Error('Frozen scientific input differs');
    bytes += Buffer.byteLength(item.text);
  }
  if (bytes > CHROMIUM_LIMITS.frozen) throw new Error('Frozen byte boundary exceeded');
  return request;
}
