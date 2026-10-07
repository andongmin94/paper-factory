import { spawn, type ChildProcessWithoutNullStreams } from 'node:child_process';
import { createHash, randomUUID } from 'node:crypto';
import { readFile, mkdir, stat, realpath } from 'node:fs/promises';
import { delimiter, dirname, isAbsolute, join, relative, resolve, sep } from 'node:path';

export type EngineMethod = 'runtime.status' | 'workflow.create' | 'workflow.list' | 'workflow.status' |
  'workflow.readMaterial' | 'workflow.addEvidence' | 'workflow.submitProposal' | 'workflow.submitStudyReview' | 'workflow.submitCode' | 'workflow.collectLiterature' |
  'workflow.startExperiment' | 'workflow.cancel' | 'workflow.resume' | 'workflow.reviseWriting' | 'workflow.improveWriting' | 'workflow.redesignStudy' | 'workflow.submitManuscript' | 'workflow.recordInference' | 'workflow.export' | 'artifact.resolve' | 'shutdown';
const methods = new Set<EngineMethod>(['runtime.status', 'workflow.create', 'workflow.list', 'workflow.status',
  'workflow.readMaterial', 'workflow.addEvidence', 'workflow.submitProposal', 'workflow.submitStudyReview', 'workflow.submitCode', 'workflow.collectLiterature',
  'workflow.startExperiment', 'workflow.cancel', 'workflow.resume', 'workflow.reviseWriting', 'workflow.improveWriting', 'workflow.redesignStudy', 'workflow.submitManuscript', 'workflow.recordInference', 'workflow.export', 'artifact.resolve', 'shutdown']);
const MAX_LINE = 16 * 1024 * 1024;

export class EngineError extends Error {
  constructor(public code: string, message: string) { super(message); this.name = 'EngineError'; }
}

type Inventory = { schemaVersion: number; platform: string; arch: string;
  executables: { python: string; node: string; pandoc: string }; paths: { quickjs: string; fonts: string };
  files: Array<{ path: string; size: number; sha256: string }> };
type Binding = { profiles: Record<string, { inventorySha256: string }> };
type Pending = { resolve: (value: unknown) => void; reject: (error: Error) => void; timer: NodeJS.Timeout };

export async function checkedRuntimePath(root: string, name: string): Promise<string> {
  if (typeof name !== 'string' || !name || isAbsolute(name) || /[\\\u0000-\u001f]/.test(name) || name.split('/').some(p => !p || p === '.' || p === '..')) {
    throw new EngineError('RUNTIME_INVALID', '앱 실행 환경의 파일 경로가 올바르지 않습니다.');
  }
  const base = await realpath(root);
  const path = await realpath(join(base, ...name.split('/')));
  const rel = relative(base, path);
  if (rel === '..' || rel.startsWith('..' + sep) || isAbsolute(rel)) throw new EngineError('RUNTIME_INVALID', '앱 실행 환경의 파일 경로가 올바르지 않습니다.');
  return path;
}

export async function verifyRuntime(root: string, bindingPath: string): Promise<Inventory> {
  const raw = await readFile(join(root, 'runtime-inventory.json'));
  const binding = JSON.parse(await readFile(bindingPath, 'utf8')) as Binding;
  if (createHash('sha256').update(raw).digest('hex') !== binding.profiles[`${process.platform}-${process.arch}`]?.inventorySha256) {
    throw new EngineError('RUNTIME_CHANGED', '앱 실행 환경이 설치본의 검증 기록과 다릅니다.');
  }
  const inventory = JSON.parse(raw.toString('utf8')) as Inventory;
  if (inventory.schemaVersion !== 1 || inventory.platform !== process.platform || inventory.arch !== process.arch ||
      !Array.isArray(inventory.files) || !inventory.files.length) throw new EngineError('RUNTIME_INVALID', '이 기기에 맞는 앱 실행 환경이 없습니다.');
  const names = new Set<string>();
  for (const item of inventory.files) {
    if (names.has(item.path) || !Number.isSafeInteger(item.size) || item.size < 0 || !/^[a-f0-9]{64}$/.test(item.sha256)) {
      throw new EngineError('RUNTIME_INVALID', '앱 실행 환경의 파일 목록이 올바르지 않습니다.');
    }
    names.add(item.path);
  }
  let position = 0;
  // Bound simultaneous I/O while verifying every member, including on slower packaged disks.
  await Promise.all(Array.from({ length: Math.min(8, inventory.files.length) }, async () => {
    while (position < inventory.files.length) {
      const item = inventory.files[position++]!;
    const path = await checkedRuntimePath(root, item.path);
    if ((await stat(path)).size !== item.size || createHash('sha256').update(await readFile(path)).digest('hex') !== item.sha256) {
      throw new EngineError('RUNTIME_CHANGED', '앱 실행 환경의 파일이 변경되었습니다.');
    }
    }
  }));
  for (const executable of Object.values(inventory.executables)) {
    if (!names.has(executable)) throw new EngineError('RUNTIME_INVALID', '앱 실행 파일의 검증 기록이 없습니다.');
  }
  return inventory;
}

export class EngineBridge {
  private child?: ChildProcessWithoutNullStreams;
  private pending = new Map<string, Pending>();
  private buffer = Buffer.alloc(0);
  private stopping = false;
  private startup?: Promise<void>;
  private shutdown?: Promise<void>;
  private needsShutdown = false;
  private acknowledgedShutdown?: ChildProcessWithoutNullStreams;
  private childClosed?: Promise<number | null>;
  private expiredShutdowns = new Set<string>();

  constructor(private runtimeRoot: string, private home: string, private bindingPath: string) {}

  async start() {
    if (this.startup) return this.startup;
    if (this.child) return;
    this.startup ??= this.launch();
    return this.startup;
  }

  private async launch() {
    try {
      const inventory = await verifyRuntime(this.runtimeRoot, this.bindingPath);
      if (this.stopping) throw new EngineError('ENGINE_STOPPING', '앱이 종료되고 있습니다.');
      const python = await checkedRuntimePath(this.runtimeRoot, inventory.executables.python);
      const node = await checkedRuntimePath(this.runtimeRoot, inventory.executables.node);
      const pandoc = await checkedRuntimePath(this.runtimeRoot, inventory.executables.pandoc);
      const quickjs = await checkedRuntimePath(this.runtimeRoot, inventory.paths.quickjs);
      const fonts = await checkedRuntimePath(this.runtimeRoot, inventory.paths.fonts);
      const home = resolve(this.home);
      await mkdir(join(home, 'temp'), { recursive: true });
      // Explicit allowlist: account credentials, API keys, PYTHONPATH and ambient PATH never enter Python.
      const env: Record<string, string> = {
        PATH: [dirname(python), dirname(node), dirname(pandoc)].join(delimiter),
        HOME: home, USERPROFILE: home, APPDATA: home, LOCALAPPDATA: home,
        TEMP: join(home, 'temp'), TMP: join(home, 'temp'), TMPDIR: join(home, 'temp'),
        TYPST_FONT_PATHS: fonts, PYPANDOC_PANDOC: pandoc,
        PYTHONUTF8: '1', PYTHONDONTWRITEBYTECODE: '1',
        ...(process.env.SystemRoot ? { SystemRoot: process.env.SystemRoot } : {}),
        ...(process.env.WINDIR ? { WINDIR: process.env.WINDIR } : {}),
        ...(process.platform === 'darwin' ? { LANG: 'en_US.UTF-8' } : {}),
      };
      const child = spawn(python, ['-I', '-B', '-m', 'paper_factory.ipc', '--home', home,
        '--runtime-root', quickjs, '--node', node, '--pandoc', pandoc], {
        cwd: home, env, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true, shell: false,
      });
      this.buffer = Buffer.alloc(0);
      this.attachChild(child);
      this.needsShutdown = true;
      this.acknowledgedShutdown = undefined;
      this.expiredShutdowns.clear();
      await this.request('runtime.status', {}, 120_000);
    } catch (error) {
      this.child?.kill();
      this.startup = undefined;
      throw error instanceof EngineError ? error : (error as NodeJS.ErrnoException).code === 'ENOENT'
        ? new EngineError('RUNTIME_FILES_MISSING', '설치된 실행 환경의 파일이 없습니다. 설치 파일을 다시 실행해 주세요.')
        : new EngineError('RUNTIME_UNAVAILABLE', '앱에 포함된 실행 환경을 확인할 수 없습니다.');
    }
  }

  private attachChild(child: ChildProcessWithoutNullStreams) {
    this.child = child;
    child.stdout.on('data', (chunk: Buffer) => { if (this.child === child) this.receive(chunk); });
    // Keep receiving until stdio closes; the final reply can arrive after exit.
    child.stderr.resume();
    child.on('error', () => this.fail(new EngineError('ENGINE_START_FAILED', '로컬 연구 엔진을 시작하지 못했습니다.')));
    this.childClosed = new Promise(resolveClosed => child.once('close', code => {
      if (this.child === child) {
        this.child = undefined; this.buffer = Buffer.alloc(0); this.startup = undefined;
        this.fail(new EngineError('ENGINE_INTERRUPTED', '로컬 연구 엔진이 종료되었습니다. 실험을 자동 재실행하지 않았습니다.'));
      }
      resolveClosed(code);
    }));
  }

  private fail(error: EngineError) {
    for (const pending of this.pending.values()) { clearTimeout(pending.timer); pending.reject(error); }
    this.pending.clear();
  }

  private receive(chunk: Buffer) {
    this.buffer = Buffer.concat([this.buffer, chunk]);
    while (true) {
      const end = this.buffer.indexOf(10);
      if (end < 0) break;
      if (end > MAX_LINE) { this.protocolFailure(); return; }
      const line = this.buffer.subarray(0, end);
      this.buffer = this.buffer.subarray(end + 1);
      try {
        const message = JSON.parse(line.toString('utf8'));
        if (typeof message.id !== 'string' || typeof message.ok !== 'boolean') throw new Error('Malformed envelope');
        const pending = this.pending.get(message.id);
        if (!pending && this.expiredShutdowns.delete(message.id)) continue;
        if (!pending) throw new Error('Unknown request');
        this.pending.delete(message.id);
        clearTimeout(pending.timer);
        if (message.ok) pending.resolve(message.result);
        else pending.reject(new EngineError(typeof message.error?.code === 'string' && /^[A-Z_]{1,80}$/.test(message.error.code) ? message.error.code : 'ENGINE_ERROR',
          typeof message.error?.message === 'string' ? message.error.message.slice(0, 2000) : '연구 작업을 완료하지 못했습니다.'));
      } catch { this.protocolFailure(); return; }
    }
    if (this.buffer.length > MAX_LINE) this.protocolFailure();
  }

  private protocolFailure() {
    this.fail(new EngineError('ENGINE_PROTOCOL_INVALID', '로컬 연구 엔진의 응답 형식이 올바르지 않습니다.'));
    this.child?.kill();
  }

  request<T = unknown>(method: EngineMethod, params: Record<string, unknown> = {}, timeoutMs = 120_000): Promise<T> {
    if (!methods.has(method) || !this.child || (this.stopping && method !== 'shutdown')) return Promise.reject(new EngineError('ENGINE_UNAVAILABLE', '로컬 연구 엔진이 준비되지 않았습니다.'));
    const id = randomUUID();
    const line = JSON.stringify({ id, method, params }) + '\n';
    if (Buffer.byteLength(line) > 2 * 1024 * 1024) return Promise.reject(new EngineError('REQUEST_TOO_LARGE', '연구 요청이 허용 크기를 초과했습니다.'));
    return new Promise<T>((resolveRequest, reject) => {
      const timer = setTimeout(() => {
        if (method === 'shutdown') {
          this.pending.delete(id);
          this.expiredShutdowns.add(id);
          reject(new EngineError('ENGINE_SHUTDOWN_UNCONFIRMED', '엔진의 정리 완료 응답을 확인하지 못했습니다. 앱에서 종료를 다시 시도하세요.'));
          return;
        }
        // A timeout cannot authorize redispatch. Stop this owned engine; recovery reconciles receipts.
        this.fail(new EngineError('ENGINE_TIMEOUT', '연구 작업의 응답이 지연되어 중단했습니다. 완료 기록 확인 전 실험을 다시 실행하지 않습니다.'));
        this.child?.kill();
      }, timeoutMs);
      timer.unref();
      this.pending.set(id, { resolve: value => resolveRequest(value as T), reject, timer });
      this.child!.stdin.write(line, (error) => { if (error) this.fail(new EngineError('ENGINE_INTERRUPTED', '로컬 연구 엔진과의 연결이 끊겼습니다.')); });
    });
  }

  close(): Promise<void> {
    this.shutdown ??= this.finishShutdown().finally(() => { this.shutdown = undefined; });
    return this.shutdown;
  }

  private async finishShutdown() {
    if (this.startup) { try { await this.startup; } catch { /* A failed startup may still own a process. */ } }
    if (!this.child && this.needsShutdown) await this.start();
    const child = this.child;
    if (!child) return;
    const closed = this.childClosed!;
    this.stopping = true;
    try {
      if (this.acknowledgedShutdown !== child) {
        const result = await this.request<{ closed: boolean }>('shutdown', {}, 35_000);
        if (result?.closed !== true) throw new EngineError('ENGINE_SHUTDOWN_UNCONFIRMED', '엔진의 정리 완료를 확인하지 못했습니다.');
        this.acknowledgedShutdown = child;
      }
      const code = await new Promise<number | null>((resolveExit, reject) => {
        const timer = setTimeout(() => {
          reject(new EngineError('ENGINE_SHUTDOWN_UNCONFIRMED', '정리 응답 뒤에도 엔진이 종료되지 않았습니다. 종료를 다시 시도하세요.'));
        }, 10_000);
        timer.unref();
        void closed.then(code => { clearTimeout(timer); resolveExit(code); });
      });
      if (code !== 0) throw new EngineError('ENGINE_SHUTDOWN_UNCONFIRMED', '엔진이 정상 종료되지 않았습니다. 정리 확인을 다시 시도하세요.');
      this.needsShutdown = false;
      this.acknowledgedShutdown = undefined;
      if (this.child === child) { this.child = undefined; this.startup = undefined; }
      this.expiredShutdowns.clear();
    } finally { this.stopping = false; }
  }
}
