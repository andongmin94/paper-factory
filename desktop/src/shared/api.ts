export type ApiMethod = "GET" | "POST";
export const CODEX_DEVICE_URL = "https://auth.openai.com/codex/device";

export interface PaperFactoryApi {
  request<T = unknown>(method: ApiMethod, path: string, body?: Record<string, unknown>): Promise<T>;
  getRuntimeInfo(): Promise<{ version: string; platform: string; backend: "ready" }>;
  openExternal(url: string): Promise<void>;
  saveArtifact(path: string): Promise<{ canceled: boolean; path?: string }>;
  openArtifact(path: string): Promise<void>;
}

declare global {
  interface Window {
    paperFactory: PaperFactoryApi;
  }
}
