import { app, BrowserWindow, protocol, session, type Session } from 'electron';
import { lstatSync, realpathSync, readdirSync, mkdirSync, readSync } from 'node:fs';
import { isAbsolute, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomBytes } from 'node:crypto';
import { createServer, type Server, type Socket } from 'node:net';
import { CHROMIUM_PROTOCOL, CHROMIUM_LIMITS, boundedJson, chromiumSourceURL, sha256, validateChromiumRequest, type ChromiumRequest, type FrozenFile } from './chromium-contract.js';
import { rendererAuthority } from './chromium-authority.js';

const SCHEME = 'pf-science';
type Remote = { type: string; objectId?: string; value?: unknown; unserializableValue?: string };
type Realm = { window: BrowserWindow; session: Session; origin: string; authority: string; context: number;
  scripts: Map<string, { url: string }>; served: Set<string> };
type Receipt = { index: number; input_sha256: string; input_bytes: number; status: 'succeeded' | 'rejected'; output_sha256?: string; output_bytes?: number };

function argvValue(name: string) {
  const positions = process.argv.flatMap((item, index) => item === name ? [index] : []);
  if (positions.length !== 1 || !process.argv[positions[0]! + 1] || process.argv[positions[0]! + 1]!.startsWith('--')) throw new Error('Invalid worker launch argument');
  return process.argv[positions[0]! + 1]!;
}

async function readGo(): Promise<ChromiumRequest> {
  const pieces: Buffer[] = []; let bytes = 0;
  while (true) {
    const buffer = Buffer.alloc(65536), count = readSync(0, buffer, 0, buffer.length, null);
    if (!count) throw new Error('GO handshake ended before frame');
    bytes += count; if (bytes > CHROMIUM_LIMITS.input) throw new Error('GO frame byte boundary exceeded');
    const piece = buffer.subarray(0, count), newline = piece.indexOf(10); pieces.push(piece);
    if (newline < 0) continue;
    if (newline !== piece.length - 1) throw new Error('Only one GO frame is permitted');
    return validateChromiumRequest(JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(Buffer.concat(pieces).subarray(0, bytes - 1))));
  }
}

async function start() {
  const windows: BrowserWindow[] = [];
  let request: ChromiumRequest | undefined, failure: string | undefined, finishing = false;
  let attempts = 0, completed = 0, fixtureBytes = 0, scientificReads = 0, scientificReadBytes = 0, recordBytes = 0;
  const receipts: Receipt[] = [], fixtures: Array<{ label: string; encoding: string; content: string; sha256: string }> = [], labels = new Set<string>();
  let observation: Buffer | undefined;
  let denyProxy: Server | undefined, proxyPort: number | undefined;
  const proxySockets = new Set<Socket>();
  const proxyReceipt = { host: '127.0.0.1', port: 0, denied_connections: 0, close_requested: false, close_callback_confirmed: false };
  const manifest: Record<string, unknown> = { backend: 'chromium-sandbox', bridge: 'controller-held-chromium-call-gate',
    json_projection_only: true, result_serialization: 'Finite own-data JSON snapshot serialized with captured JSON.stringify and null prototypes',
    native_node_execution: false, native_host_rss_limit_claimed: false,
    versions: { electron: process.versions.electron, chromium: process.versions.chrome, node: process.versions.node, os: process.platform, architecture: process.arch } };
  let timeout: NodeJS.Timeout | undefined;
  const fatal = (reason: string) => { if (!finishing) failure ??= reason.slice(0, 1000); };
  const check = () => { if (failure) throw new Error('Fatal runtime boundary: ' + failure); };
  function finish(status: 'succeeded' | 'failed', error?: string) {
    if (finishing) return; finishing = true; clearTimeout(timeout);
    for (const window of windows) if (!window.isDestroyed()) window.destroy();
    for (const socket of proxySockets) socket.destroy();
    if (denyProxy?.listening) {
      proxyReceipt.close_requested = true;
      denyProxy.close(error => { if (!error) proxyReceipt.close_callback_confirmed = true; });
    }
    manifest.owned_deny_proxy = proxyReceipt;
    manifest.shutdown_windows_closed = !app.isReady() || BrowserWindow.getAllWindows().length === 0;
    manifest.production_dispatch_attempts = attempts; manifest.production_completed_calls = completed;
    manifest.call_receipts = receipts; manifest.retained_fixtures = fixtures;
    manifest.fixture_count = fixtures.length; manifest.fixture_bytes = fixtureBytes;
    manifest.scientific_input_reads = scientificReads; manifest.scientific_input_read_bytes = scientificReadBytes;
    const [path = '', fn = ''] = request?.production_entrypoint.split(':') ?? [];
    const frame: Record<string, unknown> = { protocol: CHROMIUM_PROTOCOL, phase: 'result', nonce: request?.nonce ?? null,
      status: failure || !manifest.shutdown_windows_closed ? 'failed' : status,
      ...(failure || error ? { error: failure ?? error } : {}),
      ...(observation ? { observation_b64: observation.toString('base64') } : {}),
      production_calls: attempts ? [{ path, function: fn, calls: attempts }] : [], coverage_truncated: false,
      coverage_mechanism: 'controller-held-chromium-call-gate', runtime_manifest: manifest };
    let line = JSON.stringify(frame) + '\n';
    if (Buffer.byteLength(line) > CHROMIUM_LIMITS.frame) {
      delete frame.observation_b64;
      frame.status = 'failed'; frame.error = 'Final frame byte boundary exceeded';
      line = JSON.stringify(frame) + '\n';
    }
    process.stdout.write(line, () => app.exit(frame.status === 'succeeded' ? 0 : 1));
  }
  try {
    if (process.platform !== 'win32' || !process.argv.includes('--paper-factory-chromium-worker')) throw new Error('Chromium worker is Windows-only and requires child mode');
    const workerPath = argvValue('--worker');
    if (realpathSync(workerPath) !== realpathSync(fileURLToPath(import.meta.url))) throw new Error('Worker launch path differs');
    const profile = argvValue('--profile');
    if (!isAbsolute(profile) || resolve(profile) !== profile || lstatSync(profile).isSymbolicLink() ||
        !lstatSync(profile).isDirectory() || realpathSync(profile) !== profile || readdirSync(profile).length) throw new Error('Worker profile must be an empty owned real directory');
    app.setName('Paper Factory Scientific Worker');
    app.setPath('userData', profile); app.setPath('sessionData', profile);
    mkdirSync(join(profile, 'logs')); app.setPath('logs', join(profile, 'logs'));
    mkdirSync(join(profile, 'crashes')); app.setPath('crashDumps', join(profile, 'crashes'));
    app.disableHardwareAcceleration(); app.enableSandbox();
    for (const name of ['disable-background-networking', 'disable-component-update', 'disable-domain-reliability', 'disable-sync', 'disable-breakpad', 'dns-prefetch-disable', 'no-first-run']) app.commandLine.appendSwitch(name);
    app.commandLine.appendSwitch('host-resolver-rules', 'MAP * ~NOTFOUND');
    app.commandLine.appendSwitch('force-webrtc-ip-handling-policy', 'disable_non_proxied_udp');
    protocol.registerSchemesAsPrivileged([{ scheme: SCHEME, privileges: { standard: true, secure: true } }]);
    denyProxy = createServer(socket => {
      proxyReceipt.denied_connections++; proxySockets.add(socket);
      socket.once('close', () => proxySockets.delete(socket)); socket.destroy();
    });
    await new Promise<void>((resolveListen, reject) => {
      denyProxy!.once('error', reject); denyProxy!.listen(0, '127.0.0.1', resolveListen);
    });
    const address = denyProxy.address();
    if (!address || typeof address === 'string' || address.address !== '127.0.0.1') throw new Error('Owned deny proxy binding differs');
    proxyPort = address.port; proxyReceipt.port = proxyPort;
    app.commandLine.appendSwitch('proxy-server', `http://127.0.0.1:${proxyPort}`);
    app.commandLine.appendSwitch('proxy-bypass-list', '<-loopback>');
    // No renderer or source is started until native has journaled and attached the Job.
    await new Promise<void>((resolveWrite, reject) => process.stdout.write(JSON.stringify({ protocol: CHROMIUM_PROTOCOL, phase: 'awaiting-go' }) + '\n', error => error ? reject(error) : resolveWrite()));
    request = await readGo();
    process.stdin.on('data', () => { fatal('Unexpected frame after GO'); finish('failed'); });
    timeout = setTimeout(() => { fatal('Scientific worker deadline exceeded'); finish('failed'); }, request.timeout_seconds * 1000);
    manifest.production_entrypoint = request.production_entrypoint; manifest.source_order = request.source_order;
    manifest.source_files = Object.fromEntries(Object.entries(request.source_files).map(([name, item]) => [name, { original_sha256: item.sha256, size: Buffer.byteLength(item.text) }]));
    manifest.experiment_files = Object.fromEntries(Object.entries(request.experiment_files).map(([name, item]) => [name, { sha256: item.sha256, size: Buffer.byteLength(item.text) }]));
    manifest.scientific_inputs = Object.fromEntries(Object.entries(request.scientific_inputs).map(([key, item]) => [key, { name: item.name, sha256: item.sha256, size: Buffer.byteLength(item.text) }]));
    manifest.scientific_input_bytes = Object.values(request.scientific_inputs).reduce((total, item) => total + Buffer.byteLength(item.text), 0);
    await app.whenReady();
    let production: Realm, experiment: Realm, selectedHandle: string;
    let nextId = 1, queue: Promise<void> = Promise.resolve();
    async function remote(realm: Realm, method: string, args: Array<{ value?: unknown; objectId?: string }> = [], awaitPromise = false): Promise<Remote> {
      check();
      const response = await realm.window.webContents.debugger.sendCommand('Runtime.callFunctionOn', { objectId: realm.authority,
        functionDeclaration: `function(a,b,c){return this.${method}(a,b,c)}`, arguments: args,
        awaitPromise, returnByValue: !['select'].includes(method), userGesture: false });
      if (response.exceptionDetails) {
        const message = response.exceptionDetails.exception?.description ?? response.exceptionDetails.text;
        throw new Error(String(message).slice(0, 1000));
      }
      check(); return response.result;
    }
    async function dispatch(op: string, args: unknown[]): Promise<string> {
      check();
      if (op === 'callProduction') {
        if (args.length !== 1 || attempts >= CHROMIUM_LIMITS.calls) throw new Error('Production dispatch boundary exceeded');
        const raw = args[0]; const values = boundedJson(raw);
        if (!Array.isArray(values) || values.length > 16) throw new Error('Production gate requires a JSON argument array');
        const input = raw as string;
        const receipt: Receipt = { index: attempts + 1, input_sha256: sha256(input), input_bytes: Buffer.byteLength(input), status: 'rejected' };
        attempts++;
        try {
          const returned = await remote(production, 'invoke', [{ objectId: selectedHandle }, { value: input }]);
          const envelope = boundedJson(returned.value) as { ok: boolean; error?: string; text?: string };
          if (!envelope || typeof envelope !== 'object' || typeof envelope.ok !== 'boolean') throw new Error('Production envelope differs');
          if (!envelope.ok) throw new OriginalRejection(typeof envelope.error === 'string' ? envelope.error.slice(0, 1000) : 'Original production rejection');
          const text = envelope.text; boundedJson(text);
          if (typeof text !== 'string') throw new Error('Production output is not JSON text');
          receipt.status = 'succeeded'; receipt.output_sha256 = sha256(text); receipt.output_bytes = Buffer.byteLength(text); completed++;
          return text;
        } catch (error) {
          check();
          // An ordinary original exception is an observed rejection; bridge and result violations remain fatal.
          if (!(error instanceof OriginalRejection)) fatal((error as Error).message);
          throw error;
        } finally {
          receipts.push(receipt); recordBytes += Buffer.byteLength(JSON.stringify(receipt));
          if (recordBytes > CHROMIUM_LIMITS.records) fatal('Trusted record byte boundary exceeded');
        }
      }
      if (op === 'retainFixture') {
        if (args.length !== 2 || typeof args[0] !== 'string' || typeof args[1] !== 'string') throw new Error('Fixture gate requires label and text');
        const [label, text] = args as [string, string], bytes = Buffer.from(text);
        if (!label || label.length > 200 || /[\x00-\x1f\x7f]/.test(label) || !text.isWellFormed() || labels.has(label) ||
            fixtures.length >= CHROMIUM_LIMITS.fixtures || bytes.length + fixtureBytes > CHROMIUM_LIMITS.observation) throw new Error('Fixture retention boundary exceeded');
        const record = { label, encoding: 'base64', content: bytes.toString('base64'), sha256: sha256(bytes) };
        const encodedBytes = Buffer.byteLength(JSON.stringify(record));
        if (encodedBytes + recordBytes > CHROMIUM_LIMITS.records) throw new Error('Trusted record byte boundary exceeded');
        labels.add(label); fixtureBytes += bytes.length; recordBytes += encodedBytes; fixtures.push(record);
        return JSON.stringify(record);
      }
      if (op === 'readScientificInput') {
        if (args.length !== 1 || typeof args[0] !== 'string' || !Object.hasOwn(request!.scientific_inputs, args[0])) throw new Error('Scientific input key is not frozen');
        const text = JSON.stringify(request!.scientific_inputs[args[0]]);
        if (scientificReads >= CHROMIUM_LIMITS.scientificReads || scientificReadBytes + Buffer.byteLength(text) > CHROMIUM_LIMITS.frozen) throw new Error('Scientific input read boundary exceeded');
        scientificReads++; scientificReadBytes += Buffer.byteLength(text); return text;
      }
      throw new Error('Unknown capability operation');
    }
    async function realm(kind: 'production' | 'experiment', files: Record<string, FrozenFile>): Promise<Realm> {
      const origin = `${SCHEME}://${kind}-${request!.nonce}`;
      const contents = new Map(Object.entries(files).map(([name, item]) => [chromiumSourceURL(origin, name), { bytes: Buffer.from(item.text), type: 'text/javascript; charset=utf-8' }]));
      contents.set(origin + '/index.html', { bytes: Buffer.from('<!doctype html><html><head><meta charset="utf-8"></head><body></body></html>'), type: 'text/html; charset=utf-8' });
      const ses = session.fromPartition(`${kind}-${randomBytes(16).toString('hex')}`, { cache: false });
      await ses.setProxy({ mode: 'fixed_servers', proxyRules: `http=127.0.0.1:${proxyPort};https=127.0.0.1:${proxyPort};ftp=127.0.0.1:${proxyPort};socks=127.0.0.1:${proxyPort}`, proxyBypassRules: '<-loopback>' });
      ses.setPermissionCheckHandler(() => { fatal('Permission check denied'); return false; });
      ses.setPermissionRequestHandler((_contents, _permission, callback) => { fatal('Permission request denied'); callback(false); });
      ses.setDevicePermissionHandler(() => { fatal('Device permission denied'); return false; });
      ses.setDisplayMediaRequestHandler((_request, callback) => { fatal('Display media denied'); callback({}); });
      ses.on('will-download', (_event, download) => { fatal('Download denied'); download.cancel(); });
      const served = new Set<string>();
      let productionIndex = -1;
      ses.webRequest.onBeforeRequest((details, callback) => {
        let allow = contents.has(details.url) && !served.has(details.url);
        if (kind === 'production') {
          const expected = productionIndex === -1 ? origin + '/index.html' : chromiumSourceURL(origin, request!.source_order[productionIndex]!);
          allow &&= details.url === expected;
          if (allow) productionIndex++;
        }
        if (allow) served.add(details.url); else fatal('Network or duplicate module request denied');
        callback({ cancel: !allow });
      });
      ses.protocol.handle(SCHEME, incoming => {
        const item = contents.get(incoming.url);
        if (!item) { fatal('Protocol origin denied'); return new Response(null, { status: 403 }); }
        return new Response(item.bytes, { headers: { 'Content-Type': item.type,
          'Content-Security-Policy': `default-src 'none'; script-src ${origin}; connect-src 'none'; font-src 'none'; img-src 'none'; frame-src 'none'; worker-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'` } });
      });
      const window = new BrowserWindow({ show: false, width: 320, height: 240, skipTaskbar: true, focusable: false,
        webPreferences: { session: ses, offscreen: true, sandbox: true, contextIsolation: true, nodeIntegration: false,
          nodeIntegrationInWorker: false, webSecurity: true, webviewTag: false, devTools: false, spellcheck: false,
          backgroundThrottling: false, navigateOnDragDrop: false, allowRunningInsecureContent: false } });
      windows.push(window);
      window.webContents.setWindowOpenHandler(() => { fatal('Window creation denied'); return { action: 'deny' }; });
      window.webContents.on('will-navigate', event => { fatal('Navigation denied'); event.preventDefault(); });
      window.webContents.on('will-frame-navigate', event => { fatal('Frame navigation denied'); event.preventDefault(); });
      window.webContents.on('will-attach-webview', event => { fatal('Webview denied'); event.preventDefault(); });
      window.webContents.on('render-process-gone', () => fatal('Renderer process ended'));
      window.webContents.setWebRTCIPHandlingPolicy('disable_non_proxied_udp');
      const debuggerClient = window.webContents.debugger;
      debuggerClient.attach('1.3');
      const scripts = new Map<string, { url: string }>();
      const bindingName = '__pf_' + randomBytes(16).toString('hex');
      const realmNonce = randomBytes(16).toString('hex');
      const result: Realm = { window, session: ses, origin, scripts, served, authority: '', context: -1 };
      debuggerClient.on('message', (_event, method, params) => {
        if (method === 'Debugger.scriptParsed') scripts.set(params.scriptId, { url: params.url });
        if (method === 'Runtime.executionContextCreated' && params.context.auxData?.isDefault) {
          if (result.context > 0 && params.context.id !== result.context) fatal('Additional renderer context denied');
          else result.context = params.context.id;
        }
        if (method === 'Runtime.executionContextDestroyed' && params.executionContextId === result.context ||
            method === 'Runtime.executionContextsCleared' && result.context > 0) fatal('Pinned renderer context ended');
        if (method !== 'Runtime.bindingCalled') return;
        try {
          if (params.name !== bindingName || params.executionContextId !== result.context || Buffer.byteLength(params.payload) > CHROMIUM_LIMITS.gate + 65536) throw new Error('Capability frame source or bytes differ');
          const message = boundedJson(params.payload, CHROMIUM_LIMITS.gate + 65536) as { nonce: string; op: string; id?: number; args?: unknown[]; reason?: string };
          if (message.nonce !== realmNonce) throw new Error('Capability nonce differs');
          if (message.op === 'fatal') { fatal(typeof message.reason === 'string' ? message.reason : 'Renderer boundary violation'); return; }
          if (kind !== 'experiment' || message.id !== nextId++ || !Array.isArray(message.args) || typeof message.op !== 'string') throw new Error('Capability identity or order differs');
          queue = queue.then(async () => {
            let ok = true, value: string;
            try { value = await dispatch(message.op, message.args!); } catch (error) {
              if (!(error instanceof OriginalRejection) || failure) fatal((error as Error).message);
              ok = false; value = (error as Error).message.slice(0, 1000);
            }
            // Deliver a caught production rejection; a fatal flag cannot be cleared by the experiment.
            await debuggerClient.sendCommand('Runtime.callFunctionOn', { objectId: result.authority,
              functionDeclaration: 'function(id,ok,text){return this.deliver(id,ok,text)}', arguments: [{ value: message.id }, { value: ok }, { value }], returnByValue: true });
          }).catch(error => { fatal((error as Error).message); });
        } catch (error) { fatal((error as Error).message); }
      });
      await window.loadURL(origin + '/index.html');
      await debuggerClient.sendCommand('Runtime.enable'); await debuggerClient.sendCommand('Debugger.enable');
      if (result.context < 1) throw new Error('Default renderer context is absent');
      await debuggerClient.sendCommand('Runtime.addBinding', { name: bindingName, executionContextId: result.context });
      const context = await debuggerClient.sendCommand('Runtime.evaluate', { expression: 'globalThis', returnByValue: false });
      const evaluated = await debuggerClient.sendCommand('Runtime.evaluate', { expression: `(${rendererAuthority.toString()})(${JSON.stringify(bindingName)},${JSON.stringify(realmNonce)},${JSON.stringify(kind)})`, returnByValue: false });
      // addBinding must precede the authority closure. The first evaluation above contains no untrusted code.
      if (evaluated.exceptionDetails || !evaluated.result.objectId) throw new Error('Renderer authority initialization failed');
      result.authority = evaluated.result.objectId;
      if (!context.result.objectId) throw new Error('Renderer context is absent');
      const capabilities = await debuggerClient.sendCommand('Runtime.callFunctionOn', { objectId: result.authority,
        functionDeclaration: 'function(){return this.capabilities()}', returnByValue: true });
      const initial = boundedJson(capabilities.result?.value) as { require: string; process: string };
      if (initial.require !== 'undefined' || initial.process !== 'undefined') throw new Error('Renderer exposes native Node');
      manifest.renderer_capabilities ??= {};
      (manifest.renderer_capabilities as Record<string, unknown>)[kind] = initial;
      return result;
    }
    production = await realm('production', request.source_files);
    experiment = await realm('experiment', request.experiment_files);
    manifest.distinct_renderer_processes = production.window.webContents.getOSProcessId() !== experiment.window.webContents.getOSProcessId();
    manifest.separate_nonpersistent_sessions = production.session !== experiment.session;
    const metrics = app.getAppMetrics();
    manifest.sandboxed = windows.every(window => metrics.find(item => item.pid === window.webContents.getOSProcessId())?.sandboxed === true);
    manifest.node_integration = false; // Configured false, also checked inside each pristine renderer below.
    manifest.network_denied = true;
    if (!manifest.distinct_renderer_processes || !manifest.separate_nonpersistent_sessions || !manifest.sandboxed || manifest.node_integration || windows.some(window => window.isVisible())) throw new Error('Renderer isolation differs');
    const loaded: Array<{ path: string; script_url: string; script_id: string; sha256: string; size: number }> = [];
    for (const name of request.source_order) {
      const url = chromiumSourceURL(production.origin, name);
      await remote(production, 'loadClassic', [{ value: url }], true);
      const matching = [...production.scripts].filter(([, item]) => item.url === url);
      if (matching.length !== 1) throw new Error('Loaded production script identity differs');
      const id = matching[0]![0], actual = await production.window.webContents.debugger.sendCommand('Debugger.getScriptSource', { scriptId: id });
      if (actual.scriptSource !== request.source_files[name]!.text || sha256(actual.scriptSource) !== request.source_files[name]!.sha256) throw new Error('Loaded production script bytes differ');
      loaded.push({ path: name, script_url: url, script_id: id, sha256: sha256(actual.scriptSource), size: Buffer.byteLength(actual.scriptSource) });
    }
    manifest.loaded_source_scripts = loaded;
    const [selectedFile, selector] = request.production_entrypoint.split(':');
    const fn = await remote(production, 'select', [{ value: selector!.split('.') }]);
    if (fn.type !== 'function' || !fn.objectId) throw new Error('Selected export is not a held function');
    selectedHandle = fn.objectId;
    const properties = await production.window.webContents.debugger.sendCommand('Runtime.getProperties', { objectId: selectedHandle, ownProperties: true });
    const location = properties.internalProperties?.find((item: { name: string }) => item.name === '[[FunctionLocation]]')?.value?.value;
    if (!location || typeof location.scriptId !== 'string' || production.scripts.get(location.scriptId)?.url !== chromiumSourceURL(production.origin, selectedFile!)) throw new Error('Production function location differs');
    const actual = await production.window.webContents.debugger.sendCommand('Debugger.getScriptSource', { scriptId: location.scriptId });
    if (actual.scriptSource !== request.source_files[selectedFile!]!.text || sha256(actual.scriptSource) !== request.source_files[selectedFile!]!.sha256) throw new Error('Production function source bytes differ');
    manifest.function_provenance = { script_url: chromiumSourceURL(production.origin, selectedFile!), script_id: location.scriptId,
      script_sha256: sha256(actual.scriptSource), size: Buffer.byteLength(actual.scriptSource) };
    const returned = await remote(experiment, 'run', [{ value: chromiumSourceURL(experiment.origin, request.entrypoint) }], true);
    await queue; check();
    const value = boundedJson(returned.value, CHROMIUM_LIMITS.observation);
    if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Experiment result must be an object');
    observation = Buffer.from(returned.value as string); finish('succeeded');
  } catch (error) { finish('failed', (error as Error).message.slice(0, 1000)); }
}

class OriginalRejection extends Error {}

// Keep entry evaluation nonblocking so Electron can complete its ready lifecycle after GO.
void start();
