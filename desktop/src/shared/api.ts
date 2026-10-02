export type ApiMethod = "GET" | "POST";

export interface PaperFactoryApi {
  request<T = unknown>(method: ApiMethod, path: string, body?: Record<string, unknown>): Promise<T>;
  getRuntimeInfo(): Promise<{ version: string; platform: string; backend: "ready" }>;
  openExternal(url: string): Promise<void>;
  readArtifact(path: string): Promise<{ mime: string; bytes: Uint8Array }>;
  saveArtifact(path: string): Promise<{ canceled: boolean; path?: string }>;
  openArtifact(path: string): Promise<void>;
}

declare global {
  interface Window { paperFactory: PaperFactoryApi }
}
