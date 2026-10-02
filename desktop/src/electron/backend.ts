import {
  spawn,
  type ChildProcessWithoutNullStreams,
  type SpawnOptionsWithoutStdio,
} from "node:child_process";
import { parseBackendReady, MAX_JSON } from "./security.js";

export interface BackendOptions {
  executable: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
  startupMs?: number;
  shutdownMs?: number;
}

interface BackendExit {
  code: number | null;
  signal: NodeJS.Signals | null;
}

export async function boundedBytes(response: Response, maximum: number): Promise<Uint8Array> {
  const length = Number(response.headers.get("content-length"));
  if (Number.isFinite(length) && length > maximum) {
    await response.body?.cancel();
    throw new Error("파일이 지원하는 크기를 초과합니다.");
  }
  const reader = response.body?.getReader();
  if (!reader) return new Uint8Array();
  let size = 0;
  const chunks: Uint8Array[] = [];
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > maximum) throw new Error("응답이 지원하는 크기를 초과합니다.");
      chunks.push(value);
    }
  } finally {
    await reader.cancel().catch(() => {});
  }
  return Buffer.concat(chunks, size);
}

export class Backend {
  private child?: ChildProcessWithoutNullStreams;
  private connection?: { url: string; token: string };
  private exited?: Promise<BackendExit>;
  private exitResult?: BackendExit;
  private closed = false;
  private stopPromise?: Promise<void>;

  constructor(private readonly options: BackendOptions) {}

  get ready(): boolean {
    return Boolean(this.connection && !this.closed);
  }

  async start(): Promise<void> {
    if (this.child) throw new Error("백엔드가 이미 시작되었습니다.");
    const options: SpawnOptionsWithoutStdio = {
      cwd: this.options.cwd,
      env: this.options.env,
      shell: false,
      windowsHide: true,
    };
    const child = spawn(this.options.executable, this.options.args, { ...options, stdio: "pipe" });
    this.child = child;
    this.exited = new Promise((resolve) =>
      child.once("close", (code, signal) => {
        this.closed = true;
        this.exitResult = { code, signal };
        resolve(this.exitResult);
      }),
    );
    // Drain private diagnostics without forwarding credentials or readiness tokens.
    child.stderr.resume();
    await new Promise<void>((resolve, reject) => {
      let pending = "";
      const timer = setTimeout(
        () => finish(new Error("백엔드를 시작하지 못했습니다. 실행환경을 확인해 주세요.")),
        this.options.startupMs ?? 30_000,
      );
      const onError = () => finish(new Error("Python 실행환경을 시작할 수 없습니다."));
      const onExit = () => finish(new Error("백엔드가 준비되기 전에 종료되었습니다."));
      const onData = (chunk: Buffer) => {
        pending += chunk.toString("utf8");
        if (pending.length > 8192) return finish(new Error("백엔드 준비 신호가 너무 큽니다."));
        const newline = pending.indexOf("\n");
        if (newline === -1) return;
        try {
          this.connection = parseBackendReady(JSON.parse(pending.slice(0, newline).trim()));
          finish();
        } catch {
          finish(new Error("백엔드 준비 신호가 올바르지 않습니다."));
        }
      };
      const finish = (error?: Error) => {
        clearTimeout(timer);
        child.off("error", onError);
        child.off("close", onExit);
        child.stdout.off("data", onData);
        child.stdout.resume();
        if (error) {
          if (!this.connection) child.kill();
          reject(error);
        } else resolve();
      };
      child.once("error", onError);
      child.once("close", onExit);
      child.stdout.on("data", onData);
    });
  }

  async fetch(
    path: string,
    options: { method?: string; body?: string; timeoutMs?: number } = {},
  ): Promise<Response> {
    if (!this.ready || !this.connection) throw new Error("백엔드가 연결되어 있지 않습니다.");
    // Only main-owned, already validated relative paths reach this method.
    if (!path.startsWith("/api/") || path.startsWith("//") || /[\\#]/.test(path))
      throw new Error("허용되지 않은 백엔드 경로입니다.");
    return fetch(this.connection.url + path, {
      method: options.method ?? "GET",
      headers: {
        Authorization: `Bearer ${this.connection.token}`,
        Origin: this.connection.url,
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      body: options.body,
      redirect: "error",
      signal: AbortSignal.timeout(options.timeoutMs ?? 120_000),
    });
  }

  async json(path: string, options: { method?: string; body?: string } = {}): Promise<unknown> {
    const response = await this.fetch(path, options);
    const value = JSON.parse(new TextDecoder().decode(await boundedBytes(response, MAX_JSON * 8)));
    if (!response.ok) {
      const code =
        typeof value?.code === "string" && /^[A-Z][A-Z0-9_]{1,63}$/.test(value.code)
          ? `[${value.code}] `
          : "";
      throw new Error(
        code +
          (typeof value?.error === "string"
            ? value.error
            : `요청이 실패했습니다 (${response.status}).`),
      );
    }
    return value;
  }

  stop(): Promise<void> {
    if (!this.child) return Promise.resolve();
    if (this.closed) {
      return this.exitResult?.code === 0 && this.exitResult.signal === null
        ? Promise.resolve()
        : Promise.reject(
            new Error("백엔드가 비정상적으로 종료되었습니다. 작업 정리 상태를 확인해 주세요."),
          );
    }
    if (this.stopPromise) return this.stopPromise;
    this.stopPromise = this.shutdown().finally(() => {
      this.stopPromise = undefined;
    });
    return this.stopPromise;
  }

  private async shutdown(): Promise<void> {
    const timeoutMs = this.options.shutdownMs ?? 30_000;
    const start = Date.now();
    const response = await this.fetch("/api/desktop/shutdown", {
      method: "POST",
      body: "{}",
      timeoutMs,
    });
    if (!response.ok)
      throw new Error(
        "진행 중인 작업을 안전하게 종료하지 못했습니다. 작업을 중지한 뒤 다시 시도해 주세요.",
      );
    await response.body?.cancel();
    await new Promise<void>((resolve, reject) => {
      const timer = setTimeout(
        () =>
          reject(
            new Error("백엔드 종료 확인이 지연되고 있습니다. 앱을 유지한 뒤 다시 시도해 주세요."),
          ),
        Math.max(1, timeoutMs - (Date.now() - start)),
      );
      this.exited!.then((result) => {
        clearTimeout(timer);
        if (result.code !== 0 || result.signal !== null)
          reject(
            new Error("백엔드가 비정상적으로 종료되었습니다. 작업 정리 상태를 확인해 주세요."),
          );
        else resolve();
      });
    });
  }
}
