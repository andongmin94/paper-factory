import path from "node:path";

const identifier = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$/;
const artifactExtensions = new Set([".pdf", ".md", ".docx", ".tex", ".csv", ".tsv", ".json", ".bib", ".txt", ".png", ".jpg", ".jpeg", ".svg", ".webp", ".zip"]);
export const MAX_JSON = 1024 * 1024;
export const MAX_PREVIEW = 16 * 1024 * 1024;
export const MAX_ARTIFACT = 96 * 1024 * 1024;

function segments(value: unknown): string[] {
  const controls = (text: string) => [...text].some((character) => character.charCodeAt(0) < 32);
  if (typeof value !== "string" || value.length > 8192 || !value.startsWith("/api/") || /[?#\\]/.test(value) || controls(value)) {
    throw new Error("허용되지 않은 API 경로입니다.");
  }
  const parts = value.slice(1).split("/").map((part) => decodeURIComponent(part));
  if (parts.some((part) => !part || part === "." || part === ".." || /[/\\:]/.test(part) || controls(part))) {
    throw new Error("허용되지 않은 API 경로입니다.");
  }
  return parts;
}

export function validateApiRequest(method: unknown, value: unknown, body?: unknown): { method: "GET" | "POST"; path: string; body?: string } {
  const parts = segments(value);
  const validId = (index: number) => identifier.test(parts[index] ?? "");
  const route = parts.join("/");
  let allowed = false;
  if (method === "GET") {
    allowed = ["api/health", "api/agent/status", "api/agent/connection", "api/projects", "api/jobs", "api/studies"].includes(route)
      || (parts.length === 3 && ["projects", "jobs", "studies"].includes(parts[1]) && validId(2))
      || (parts[1] === "projects" && validId(2) && parts[3] === "pipelines" && (parts.length === 4 || (parts.length === 5 && validId(4))));
    if (body !== undefined) throw new Error("GET 요청에는 본문을 전달할 수 없습니다.");
  } else if (method === "POST") {
    allowed = ["api/agent/repositories", "api/projects"].includes(route)
      || (parts.length === 4 && parts.slice(0, 3).join("/") === "api/agent/connection" && ["login", "probe", "cancel", "logout"].includes(parts[3]))
      || (parts.length === 4 && parts[1] === "projects" && validId(2) && parts[3] === "pipelines")
      || (parts.length === 6 && parts[1] === "projects" && validId(2) && parts[3] === "pipelines" && validId(4) && ["cancel", "resume"].includes(parts[5]));
  }
  if (!allowed) throw new Error("허용되지 않은 API 작업입니다.");
  let serialized: string | undefined;
  if (method === "POST") {
    if (body !== undefined && (!body || typeof body !== "object" || Array.isArray(body))) throw new Error("요청 본문은 JSON 객체여야 합니다.");
    serialized = JSON.stringify(body ?? {}, (_key, item) => {
      if (typeof item === "number" && !Number.isFinite(item)) throw new Error("유한한 JSON 숫자만 사용할 수 있습니다.");
      return item;
    });
    if (Buffer.byteLength(serialized) > MAX_JSON) throw new Error("요청 본문이 너무 큽니다.");
  }
  return { method: method as "GET" | "POST", path: value as string, body: serialized };
}

export function validateArtifactPath(value: unknown): string {
  const parts = segments(value);
  if (!["projects", "studies"].includes(parts[1]) || !identifier.test(parts[2] ?? "")) throw new Error("허용되지 않은 파일 경로입니다.");
  if (parts[1] === "studies" && parts.length === 4 && parts[3] === "bundle") return value as string;
  if (parts.length < 5 || parts[3] !== "files" || !artifactExtensions.has(path.extname(parts.at(-1)!).toLowerCase())) throw new Error("지원하지 않는 파일입니다.");
  return value as string;
}

export function artifactName(value: string): string {
  const parts = segments(validateArtifactPath(value));
  return parts.at(-1) === "bundle" ? `${parts[2]}-reproducibility.zip` : parts.at(-1)!;
}

export function validateDeviceUrl(value: unknown): string {
  if (value !== "https://auth.openai.com/codex/device") throw new Error("공식 인증 페이지만 열 수 있습니다.");
  return value;
}

export function parseBackendReady(value: unknown): { url: string; token: string } {
  if (!value || typeof value !== "object") throw new Error("백엔드 준비 신호가 올바르지 않습니다.");
  const { url, token } = value as Record<string, unknown>;
  if (typeof url !== "string" || typeof token !== "string" || !/^[A-Za-z0-9_-]{32,256}$/.test(token)) throw new Error("백엔드 준비 신호가 올바르지 않습니다.");
  const parsed = new URL(url);
  if (parsed.protocol !== "http:" || parsed.hostname !== "127.0.0.1" || !parsed.port || Number(parsed.port) < 1 || parsed.username || parsed.password || parsed.pathname !== "/" || parsed.search || parsed.hash) throw new Error("백엔드는 전용 로컬 주소에서 실행해야 합니다.");
  return { url: parsed.origin, token };
}

export function isTrustedFrame(senderId: number, expectedId: number, isMainFrame: boolean, frameUrl: string, rendererUrl: string): boolean {
  if (senderId !== expectedId || !isMainFrame) return false;
  try {
    const candidate = new URL(frameUrl);
    const expected = new URL(rendererUrl);
    return candidate.protocol === expected.protocol && candidate.host === expected.host && candidate.pathname === expected.pathname && !candidate.username && !candidate.password;
  } catch { return false; }
}
