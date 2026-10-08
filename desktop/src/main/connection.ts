import { ChatGPTError, type ChatGPTClient } from '@siwc/local';
import { appendFile, mkdir, readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import type { AppError, AppSnapshot } from '../shared/contracts.js';

const messages: Record<string, [string, AppError['action']]> = {
  cancelled: ['요청을 취소했습니다.', null],
  sign_in_required: ['ChatGPT에 로그인해 주세요.', 'sign-in'],
  sharing_not_enabled: ['로그인은 되었지만 ChatGPT 구독 사용 권한이 없습니다. 같은 연결로 다시 동의해 주세요.', 'sign-in'],
  access_denied: ['로그인 또는 권한 동의가 완료되지 않았습니다.', 'sign-in'],
  login_timeout: ['로그인 시간이 만료되었습니다. 다시 로그인해 주세요.', 'sign-in'],
  sign_in_timeout: ['로그인 시간이 만료되었습니다. 다시 로그인해 주세요.', 'sign-in'],
  sign_in_expired: ['로그인 시간이 만료되었습니다. 다시 로그인해 주세요.', 'sign-in'],
  request_timeout: ['응답 대기 시간이 만료되었습니다. 완료되지 않은 요청은 성공으로 기록하지 않았습니다.', 'retry'],
  invalid_grant: ['인증이 만료되었거나 갱신할 수 없습니다. 다시 로그인해 주세요.', 'sign-in'],
  invalid_refresh_token: ['연결을 갱신할 수 없습니다. 다시 로그인해 주세요.', 'sign-in'],
  refresh_token_expired: ['저장된 연결이 만료되었습니다. 다시 로그인해 주세요.', 'sign-in'],
  refresh_token_invalidated: ['저장된 연결이 해제되었습니다. 다시 로그인해 주세요.', 'sign-in'],
  refresh_token_reused: ['저장된 연결을 갱신할 수 없습니다. 다시 로그인해 주세요.', 'sign-in'],
  token_expired: ['저장된 연결이 만료되었습니다. 다시 로그인해 주세요.', 'sign-in'],
  network_error: ['ChatGPT에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.', 'retry'],
  connection_error: ['연결을 완료하지 못했습니다. 다시 시도해 주세요.', 'retry'],
  stream_interrupted: ['응답이 완료되기 전에 연결이 끊겼습니다. 성공으로 기록하지 않았습니다.', 'retry'],
  response_incomplete: ['모델 응답이 완료되지 않았습니다. 성공으로 기록하지 않았습니다.', 'retry'],
  empty_response: ['완료된 응답에 텍스트가 없습니다. 모델을 확인해 주세요.', 'retry'],
  model_not_found: ['선택한 모델을 사용할 수 없습니다. 모델 목록을 새로 조회해 주세요.', 'retry'],
  no_models: ['이 연결에서 사용할 수 있는 모델이 없습니다.', 'retry'],
  subscription_sharing_user_not_eligible: ['이 계정 또는 워크스페이스에서 ChatGPT 구독을 사용할 수 없습니다.', 'sign-in'],
  subscription_sharing_usage_limit_exceeded: ['ChatGPT 사용량 제한에 도달했습니다. 사용량과 앱 한도를 확인해 주세요.', 'usage'],
  subscription_sharing_usage_unavailable: ['ChatGPT 사용량을 확인할 수 없습니다. 잠시 후 다시 시도해 주세요.', 'usage'],
  chatpass_v2_scope_not_authorized: ['이 연결의 권한으로 모델을 사용할 수 없습니다. 권한을 확인해 주세요.', 'sign-in'],
  storage_unavailable: ['운영체제의 보호 저장소를 사용할 수 없습니다. 연결 정보를 저장하지 않았습니다.', null],
  encryption_unavailable: ['운영체제의 보호 저장소를 사용할 수 없습니다. 연결 정보를 저장하지 않았습니다.', null],
  storage_encryption_unavailable: ['운영체제의 보호 저장소를 사용할 수 없습니다. 연결 정보를 저장하지 않았습니다.', null],
  storage_encryption_failed: ['연결 정보를 암호화하지 못했습니다. 기존 파일은 보존했습니다.', null],
  storage_decryption_failed: ['이 운영체제 계정으로 저장된 연결을 복호화하지 못했습니다. 기존 파일은 보존했습니다.', null],
  storage_provider_mismatch: ['저장된 연결의 보호 저장소 형식이 일치하지 않습니다. 기존 파일은 보존했습니다.', null],
  storage_encrypted_invalid: ['암호화된 연결 파일이 올바르지 않습니다. 기존 파일은 보존했습니다.', null],
  storage_invalid: ['저장된 연결 정보를 읽을 수 없습니다. 기존 파일은 보존했습니다.', null],
  storage_unsafe: ['연결 저장 경로가 안전하지 않습니다. 기존 파일은 보존했습니다.', null],
  revocation_failed: ['이 기기의 연결 정보는 삭제했지만 원격 권한 해제를 확인하지 못했습니다. ChatGPT 설정에서 앱 연결을 확인해 주세요.', 'usage'],
  evidence_write_failed: ['검증 기록을 저장하지 못했습니다. 디스크와 저장 경로를 확인해 주세요.', null],
  connection_busy: ['현재 요청이 끝나거나 취소된 후 다시 시도해 주세요.', null],
  connection_shutdown_unconfirmed: ['계정 요청 종료를 확인하지 못했습니다. 앱을 유지합니다. 요청이 끝난 뒤 종료를 다시 시도해 주세요.', null],
};

export function safeError(error: unknown): AppError {
  if (!(error instanceof ChatGPTError)) {
    return { code: 'connection_error', message: messages.connection_error[0], action: 'retry' };
  }
  const known = messages[error.code];
  const status = safeHttpDiagnostics(error)?.httpStatus;
  const action = known?.[1] ?? (status === 429 ? 'usage' : status === 401 || status === 403 ? 'sign-in' : error.retryable ? 'retry' : null);
  const message = known?.[0] ?? (status === 403 ? '계정 권한 또는 정책으로 요청이 거부되었습니다.' :
    status === 401 ? '이 연결로 요청을 인증하지 못했습니다.' :
    status === 400 || status === 422 ? '앱이 보낸 요청 형식 또는 옵션이 거부되었습니다. 앱 오류 기록을 확인해 주세요.' :
    status === 429 ? 'ChatGPT 사용량 또는 요청 빈도 제한에 도달했습니다. 사용량을 확인한 뒤 다시 시도해 주세요.' :
    status !== undefined && status >= 500 ? 'ChatGPT 서비스가 요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.' :
    '요청을 완료하지 못했습니다. 표시된 오류 코드를 확인해 주세요.');
  // Never forward arbitrary exception messages, URLs, response bodies, or credentials.
  return {
    code: /^[a-zA-Z0-9_]{1,100}$/.test(error.code) ? error.code : 'connection_error',
    message: message + (!known?.[0] && status !== undefined ? ` (HTTP ${status})` : ''),
    action,
  };
}

const requestParamRoots = new Set([
  'model', 'input', 'instructions', 'store', 'stream', 'tools', 'additional_tools', 'tool_choice', 'reasoning', 'text', 'service_tier',
  'background', 'conversation', 'max_output_tokens', 'max_tool_calls', 'metadata', 'moderation', 'multi_agent', 'prompt',
  'prompt_cache_retention', 'safety_identifier', 'temperature', 'top_logprobs', 'top_p', 'truncation', 'user', 'previous_response_id',
]);
const requestParamFields = new Set(['type', 'role', 'content', 'text', 'name', 'description', 'parameters', 'namespace', 'strict', 'format', 'effort', 'summary']);

function safeDiagnosticParam(value: unknown): string | undefined {
  if (typeof value !== 'string' || value.length > 160 || !/^[a-z][a-z0-9_]*(?:\[\d{1,5}\]|\.[a-z][a-z0-9_]*)*$/.test(value)) return undefined;
  const fields = value.match(/[a-z][a-z0-9_]*/g)!;
  return requestParamRoots.has(fields[0]!) && fields.slice(1).every((field) => requestParamFields.has(field)) ? value : undefined;
}

const shapeFields = new Set(['error', 'detail', 'code', 'message', 'type', 'param', 'loc', 'input', 'ctx', 'response', 'status', 'request_id']);
const shapeTypes = new Set(['null', 'string', 'number', 'boolean', 'undefined', 'bigint', 'symbol', 'function', 'object', 'array', 'redacted']);

function safeDiagnosticShape(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value || value.length > 2048) return undefined;
  let position = 0;
  const word = () => {
    const token = /^[a-z_]+/.exec(value.slice(position))?.[0];
    if (token) position += token.length;
    return token;
  };
  const parse = (depth: number): boolean => {
    if (value[position] === '{') {
      if (depth >= 3) return false;
      position++;
      if (value[position] === '}') { position++; return true; }
      for (let fields = 0; fields < 13; fields++) {
        const field = word();
        if (!field || (field !== 'other' && !shapeFields.has(field)) || value[position++] !== ':') return false;
        if (field === 'other') {
          const count = /^(?:0|[1-9]\d{0,6})/.exec(value.slice(position))?.[0];
          if (!count || Number(count) > 1_000_000) return false;
          position += count.length;
        } else if (!parse(depth + 1)) return false;
        if (value[position] === '}') { position++; return true; }
        if (value[position++] !== ',') return false;
      }
      return false;
    }
    if (value[position] === '[') {
      if (depth >= 3) return false;
      position++;
      if (value[position] === ']') { position++; return true; }
      return parse(depth + 1) && value[position++] === ']';
    }
    const type = word();
    return type !== undefined && shapeTypes.has(type);
  };
  return parse(0) && position === value.length ? value : undefined;
}

export function safeHttpDiagnostics(error: unknown) {
  if (!(error instanceof ChatGPTError)) return undefined;
  const httpStatus = Number.isSafeInteger(error.status) && error.status! >= 100 && error.status! <= 599 ? error.status : undefined;
  const requestId = typeof error.requestId === 'string' && /^[a-zA-Z0-9_][a-zA-Z0-9_.:[\]-]{0,159}$/.test(error.requestId) ? error.requestId : undefined;
  const param = safeDiagnosticParam(error.param);
  const responseShape = safeDiagnosticShape(error.responseShape);
  const diagnostics = { ...(httpStatus !== undefined ? { httpStatus } : {}), ...(requestId ? { requestId } : {}),
    ...(param ? { param } : {}), ...(responseShape ? { responseShape } : {}) };
  return Object.keys(diagnostics).length ? diagnostics : undefined;
}

export class ConnectionController {
  private state: AppSnapshot;
  private request?: AbortController;
  private active?: Promise<AppSnapshot>;
  private stopping = false;
  private disposed = false;
  private shutdownTask?: Promise<void>;
  private pendingRecords: string[] = [];
  private writing?: Promise<void>;
  private unsubscribe: () => void;

  constructor(private client: ChatGPTClient, version: string, private evidenceDir: string,
    private publish: (snapshot: AppSnapshot) => void) {
    this.state = { version, session: { connected: false, sharing: false }, profiles: [], models: [], busy: null, error: null, verification: null };
    this.unsubscribe = client.subscribe((session) => {
      this.state.session = { connected: session.status === 'connected', sharing: session.sharing,
        ...(session.profileId ? { profileId: session.profileId } : {}), ...(session.identity ? { account: { ...session.identity } } : {}) };
      if (session.error) this.state.error = safeError(new ChatGPTError(session.error.code, '', session.error.retryable, session.error.status));
      this.emit();
    });
  }

  snapshot(): AppSnapshot { return structuredClone(this.state); }
  isBusy(): boolean { return Boolean(this.active) || this.state.busy !== null || this.stopping || this.pendingRecords.length > 0; }
  private emit() { if (!this.stopping) this.publish(this.snapshot()); }

  private async sync() {
    const session = await this.client.getSession();
    const profiles = await this.client.listProfiles();
    this.state.session = { connected: session.status === 'connected', sharing: session.sharing,
      ...(session.profileId ? { profileId: session.profileId } : {}), ...(session.identity ? { account: { ...session.identity } } : {}) };
    this.state.profiles = profiles.map((p) => ({ id: p.id, label: p.label, connected: p.status === 'connected', sharing: p.sharing,
      ...(p.identity?.email ? { email: p.identity.email } : {}), ...(p.pending ? { pending: true } : {}) }));
    if (session.error) this.state.error = safeError(new ChatGPTError(session.error.code, '', session.error.retryable, session.error.status));
  }

  async initialize() {
    try {
      await this.sync();
      await this.record({ event: 'launch', connected: this.state.session.connected, sharing: this.state.session.sharing });
    } catch (error) { this.state.error = safeError(error); }
    this.emit();
    return this.snapshot();
  }

  private async record(event: Record<string, string | number | boolean>) {
    this.pendingRecords.push(JSON.stringify({ at: new Date().toISOString(), version: this.state.version,
      ...(this.state.session.profileId ? { profileId: this.state.session.profileId } : {}), ...event }) + '\n');
    await this.flushRecords();
  }

  private flushRecords(): Promise<void> {
    if (this.writing) return this.writing;
    if (!this.pendingRecords.length) return Promise.resolve();
    const task = (async () => {
      try {
        await mkdir(this.evidenceDir, { recursive: true });
        const path = join(this.evidenceDir, 'connection-checks.jsonl');
        while (this.pendingRecords.length) {
          let bytes: Buffer;
          try { bytes = await readFile(path); }
          catch (error) {
            if ((error as NodeJS.ErrnoException).code !== 'ENOENT') throw error;
            bytes = Buffer.alloc(0);
          }
          const text = bytes.toString('utf8');
          if (!Buffer.from(text, 'utf8').equals(bytes) || (text && !text.endsWith('\n'))) throw new Error('Incomplete evidence journal');
          const lines = text ? text.slice(0, -1).split('\n') : [];
          for (const line of lines) {
            const value: unknown = JSON.parse(line);
            if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid evidence journal');
          }
          const pending = this.pendingRecords[0]!;
          // A failed append may already have committed the whole line. Never
          // append it twice, and never overwrite or extend a partial journal.
          if (!lines.some(line => line + '\n' === pending)) await appendFile(path, pending, { mode: 0o600 });
          this.pendingRecords.shift();
        }
      } catch { throw new ChatGPTError('evidence_write_failed', ''); }
      finally { this.writing = undefined; }
    })();
    this.writing = task;
    return task;
  }

  private run(busy: NonNullable<AppSnapshot['busy']>, operation: (signal: AbortSignal) => Promise<void>): Promise<AppSnapshot> {
    if (this.isBusy()) return Promise.resolve({ ...this.snapshot(), error: safeError(new ChatGPTError('connection_busy', '')) });
    const controller = new AbortController();
    let expired = false;
    const timeout = setTimeout(() => { expired = true; controller.abort(); }, busy === 'sign-in' ? 9 * 60_000 : 180_000);
    timeout.unref();
    this.request = controller;
    this.state.busy = busy;
    this.state.error = null;
    this.emit();
    const task = (async () => {
      try {
        await this.record({ event: 'request-started', operation: busy });
        controller.signal.throwIfAborted();
        await operation(controller.signal);
      }
      catch (error) {
        this.state.error = safeError(controller.signal.aborted
          ? new ChatGPTError(expired ? busy === 'sign-in' ? 'sign_in_expired' : 'request_timeout' : 'cancelled', '')
          : error);
        try {
          // SDK shapes contain field/type labels only; validate that grammar again
          // at the evidence boundary rather than persisting a raw response body.
          await this.record({ event: 'request-failed', operation: busy, code: this.state.error.code,
            ...safeHttpDiagnostics(error) });
        }
        catch (writeError) { this.state.error = safeError(writeError); }
      }
      finally {
        clearTimeout(timeout);
        try { await this.sync(); } catch (error) { this.state.error ??= safeError(error); }
        this.state.busy = null;
        this.request = undefined;
        this.active = undefined;
        this.emit();
      }
      return this.snapshot();
    })();
    this.active = task;
    return task;
  }

  signIn(profileId?: string) {
    return this.run('sign-in', async (signal) => {
      const session = await this.client.signIn({ signal, ...(profileId ? { profileId, reconsent: true } : { newProfile: true }) });
      await this.sync();
      this.state.models = [];
      this.state.verification = null;
      await this.record({ event: 'sign-in', connected: session.status === 'connected', sharing: session.sharing });
      if (!session.sharing) throw new ChatGPTError('sharing_not_enabled', '');
    });
  }

  selectProfile(profileId: string) {
    return this.run('select-profile', async () => {
      this.state.models = [];
      this.state.verification = null;
      await this.client.selectProfile(profileId);
      await this.sync();
      await this.record({ event: 'profile-selected' });
    });
  }

  refreshModels() {
    return this.run('models', async (signal) => {
      this.state.models = [];
      this.state.models = await this.client.listModels({ signal });
      if (!this.state.models.length) throw new ChatGPTError('no_models', '');
      await this.record({ event: 'models', count: this.state.models.length });
    });
  }

  verify(model: string) {
    return this.run('verify', async (signal) => {
      this.state.verification = null;
      if (!this.state.models.some((m) => m.slug === model)) throw new ChatGPTError('model_not_found', '');
      const result = await this.client.streamResponse({ model, input: [{ role: 'user', content: 'Reply with exactly: Paper Factory connection works.' }], signal });
      signal.throwIfAborted();
      if (!result.text.trim()) throw new ChatGPTError('empty_response', '');
      const completedAt = new Date().toISOString();
      await this.record({ event: 'response-completed', model, completedAt, text: result.text,
        textSha256: createHash('sha256').update(result.text).digest('hex') });
      this.state.verification = { model, text: result.text, completedAt };
    });
  }

  async cancel() {
    this.request?.abort();
    this.client.cancelSignIn();
    if (this.active) await this.active;
    return this.snapshot();
  }

  disconnect() {
    return this.run('disconnect', async () => {
      this.state.models = [];
      this.state.verification = null;
      await this.client.disconnect();
      await this.record({ event: 'disconnected' });
    });
  }

  shutdown(): Promise<void> {
    if (this.disposed) return Promise.resolve();
    if (this.shutdownTask) return this.shutdownTask;
    this.stopping = true;
    const task = (async () => {
      let timer: ReturnType<typeof setTimeout> | undefined;
      try {
        await Promise.race([
          (async () => { await this.cancel(); await this.flushRecords(); })(),
          new Promise<never>((_resolve, reject) => {
            timer = setTimeout(() => reject(new ChatGPTError('connection_shutdown_unconfirmed', messages.connection_shutdown_unconfirmed[0])), 15_000);
            timer.unref();
          }),
        ]);
        this.unsubscribe();
        this.disposed = true;
      } catch (error) {
        const failure = error instanceof ChatGPTError ? error : new ChatGPTError('connection_shutdown_unconfirmed', messages.connection_shutdown_unconfirmed[0]);
        this.state.error = safeError(failure);
        this.stopping = false;
        this.emit();
        throw failure;
      } finally {
        clearTimeout(timer);
        this.shutdownTask = undefined;
      }
    })();
    this.shutdownTask = task;
    return task;
  }
}
