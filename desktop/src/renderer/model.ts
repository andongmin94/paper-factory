import type { PaperFactoryApi } from "@shared/api";
export type DesktopBridge = PaperFactoryApi;

export interface Connection {
  status: string;
  authentication?: string;
  connected?: boolean;
  model_available?: boolean;
  app_login_required?: boolean;
  pending?: { profile_id: string; status: string; expires_at?: string | null } | null;
  verification_url?: string | null;
  user_code?: string | null;
  message?: string | null;
  code?: string | null;
}

export interface AgentStatus {
  provider?: {
    ready?: boolean;
    executable_available?: boolean;
    capabilities_supported?: boolean;
    missing_capabilities?: string[];
    code?: string;
    reason?: string;
  };
  runner?: { ready?: boolean; backend?: string; runtimes?: string[]; reason?: string };
  tools?: { git: boolean; pandoc: boolean };
}

export interface Artifact {
  name?: string;
  path?: string;
  url: string;
  size?: number;
  label?: string;
}

export interface Pipeline {
  id: string;
  goal: string;
  status: string;
  stage: string;
  message?: string;
  code?: string;
  cancellation_requested?: boolean;
  created_at?: string;
  model_calls?: number;
  elapsed_seconds?: number;
  budget?: { max_model_calls?: number; wall_seconds?: number };
  attempts?: { stage: string; status: string }[];
  files?: Artifact[];
  file_errors?: { path?: string; error?: string }[];
}

export interface ResearchRun {
  project: Project;
  run: Pipeline;
}

export interface Project {
  id: string;
  name: string;
  source?: string;
  status: string;
  error?: string;
  autonomous_error?: string;
  pipelines?: Pipeline[];
  files?: Artifact[];
}

export interface Job {
  id: string;
  project_id: string;
  status: string;
  action?: string;
  error?: string;
}

export interface Study {
  slug: string;
  title?: string;
  title_ko?: string;
  repository?: string | { name?: string; url?: string };
  files?: Artifact[];
  bundle_url?: string;
  abstract?: string;
}

export interface Candidate {
  name: string;
  url: string;
  reason?: string;
  language?: string;
}

export interface Snapshot {
  agent: AgentStatus;
  connection: Connection;
  projects: Project[];
  jobs: Job[];
  studies: Study[];
}

export const initialSnapshot: Snapshot = {
  agent: {},
  connection: { status: "disconnected" },
  projects: [],
  jobs: [],
  studies: [],
};

export const stages = [
  ["assess", "프로젝트 분석"],
  ["plan", "연구 설계"],
  ["literature", "문헌 확인"],
  ["generate", "실험 준비"],
  ["execute", "실험 수행"],
  ["analyze", "결과 분석"],
  ["write", "원고 작성"],
  ["export", "파일 생성"],
  ["verify", "최종 확인"],
] as const;

export function progress(run: Pipeline) {
  const latest = new Map((run.attempts ?? []).map((attempt) => [attempt.stage, attempt.status]));
  const finished = new Set(
    stages.filter(([key]) => latest.get(key) === "completed").map(([key]) => key),
  );
  return {
    finished,
    completed: finished.size,
    percent: Math.round((finished.size / stages.length) * 100),
  };
}

export const activeStatus = (status: string) => ["running", "queued"].includes(status);
export const resumableStatus = (status: string) =>
  ["blocked", "paused", "failed", "cancelled"].includes(status);

export function statusLabel(status: string) {
  return (
    (
      {
        queued: "시작 대기",
        running: "진행 중",
        completed: "검토용 원고 준비",
        ready: "가져오기 완료",
        importing: "가져오는 중",
        blocked: "확인 필요",
        paused: "일시 중지",
        failed: "작업 실패",
        cancelled: "중지됨",
        interrupted: "중단됨",
        succeeded: "완료",
      } as Record<string, string>
    )[status] ?? status
  );
}

export function artifactKind(file: Artifact) {
  const name = file.name ?? file.path ?? file.url;
  const extension = name.split("?")[0].split(".").pop()?.toLowerCase();
  return (
    {
      pdf: "논문 PDF",
      docx: "Word 원고",
      tex: "LaTeX 원고",
      md: "Markdown 원고",
      zip: "전체 재현 자료",
    } as Record<string, string>
  )[extension ?? ""];
}

export function artifactRequestPath(file: Artifact) {
  if (
    !/^\/api\/(?:projects|studies)\/[A-Za-z0-9_-]+\/(?:files\/.+|bundle)$/.test(file.url) ||
    /[?#\\]/.test(file.url)
  )
    return null;
  try {
    const parts = file.url.split("/").slice(1).map(decodeURIComponent);
    if (
      parts.some(
        (part) =>
          !part ||
          part === "." ||
          part === ".." ||
          part.includes("/") ||
          part.includes("\\") ||
          [...part].some((character) => character.charCodeAt(0) < 32),
      )
    )
      return null;
    return file.url;
  } catch {
    return null;
  }
}

export function readableSize(bytes?: number) {
  if (bytes === undefined || !Number.isFinite(bytes)) return "";
  return bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function validRepository(value: string) {
  return /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+\/?$/.test(value.trim());
}

export function shortRepository(source?: string) {
  return source?.replace(/^https:\/\/github\.com\//, "").replace(/\/$/, "") ?? "가져온 프로젝트";
}

const connectionErrors: Record<string, string> = {
  AUTH_REQUIRED: "Codex 구독 로그인이 필요합니다. 공식 로그인 후 연결을 다시 확인해 주세요.",
  API_KEY_UNSUPPORTED: "API 키 로그인은 사용할 수 없습니다. ChatGPT 구독 계정으로 연결해 주세요.",
  SUBSCRIPTION_AUTH_REQUIRED:
    "API 키 로그인은 사용할 수 없습니다. ChatGPT 구독 계정으로 연결해 주세요.",
  NETWORK_ERROR: "Codex 서버에 연결하지 못했습니다. 네트워크와 프록시 연결을 확인해 주세요.",
  PROXY_BLOCKED: "프록시가 Codex 연결을 차단했습니다(HTTP 403). 프록시 설정을 확인해 주세요.",
  RATE_LIMITED:
    "구독 사용량 제한으로 연결을 확인하지 못했습니다. 이용 가능해진 뒤 다시 확인해 주세요.",
  LOGIN_TIMEOUT: "공식 로그인의 대기 시간이 끝났습니다. Codex 연결을 다시 시작해 주세요.",
  LOGIN_START_TIMEOUT:
    "공식 로그인 주소와 코드를 받지 못했습니다. 네트워크를 확인한 뒤 다시 연결해 주세요.",
  OUTPUT_LIMIT: "Codex 연결 응답이 지원하는 크기를 초과하여 중단했습니다.",
  CODEX_NOT_FOUND: "Codex 실행 도구를 찾지 못했습니다. 앱을 다시 설치한 뒤 연결해 주세요.",
  CONFIGURATION_ERROR:
    "Codex 실행 환경을 준비하지 못했습니다. 앱 설치 상태와 접근 권한을 확인해 주세요.",
  SCHEMA_ERROR: "모델이 올바른 연결 확인 응답을 반환하지 않았습니다. 연결을 다시 확인해 주세요.",
  INTERRUPTED: "이전 연결 작업이 중단되었습니다. Codex 연결을 다시 시작할 수 있습니다.",
  CLEANUP_UNCONFIRMED:
    "작업자의 종료가 아직 확인되지 않았습니다. 계정을 유지한 채 진행 현황을 확인해 주세요.",
  CONNECTION_BUSY: "계정 연결 작업이 진행 중입니다. 작업이 끝난 뒤 다시 시도해 주세요.",
  AUTH_STORAGE_INVALID:
    "앱의 Codex 로그인 저장소를 사용할 수 없습니다. 저장 경로와 접근 권한을 확인해 주세요.",
  UNSUPPORTED_PLATFORM: "이 실행 환경은 Codex 로그인 저장소의 파일 잠금을 지원하지 않습니다.",
  CODEX_FAILED: "Codex 연결 작업을 완료하지 못했습니다. 앱 설치 상태와 네트워크를 확인해 주세요.",
  DEVICE_AUTH_UNAVAILABLE:
    "Codex 서버에서 기기 로그인을 허용하지 않습니다. 공식 로그인 설정을 확인해 주세요.",
  LOGOUT_TIMEOUT:
    "로그아웃 확인 시간이 끝났습니다. 연결 상태를 확인한 뒤 로그아웃을 다시 시도해 주세요.",
  LOGOUT_FAILED:
    "로그아웃을 완료하지 못했습니다. 연결 상태를 확인한 뒤 로그아웃을 다시 시도해 주세요.",
};

export function connectionErrorMessage(code?: string | null): string | null {
  return code && Object.hasOwn(connectionErrors, code) ? connectionErrors[code] : null;
}

function codexToolMissing(connection: Connection, agent: AgentStatus): boolean {
  return (
    agent.provider?.executable_available === false ||
    (connection.code === "CODEX_NOT_FOUND" && agent.provider?.executable_available !== true)
  );
}

function connectionToolingMessage(connection: Connection, agent: AgentStatus): string | null {
  if (codexToolMissing(connection, agent)) return connectionErrors.CODEX_NOT_FOUND;
  if (
    agent.provider?.capabilities_supported === false &&
    (agent.provider.missing_capabilities?.length ?? 0) > 0
  )
    return "설치된 Codex 도구가 필요한 기능을 지원하지 않습니다. 앱을 업데이트한 뒤 연결해 주세요.";
  return null;
}

export function connectionMessage(connection: Connection, agent: AgentStatus) {
  if (connection.status === "logging_out") return "앱 전용 로그인에서 로그아웃하고 있습니다.";
  if (connection.status === "waiting_user") return "공식 로그인 페이지에서 아래 코드를 입력하세요.";
  if (["starting", "probing"].includes(connection.status))
    return "연결을 확인하고 있습니다. 잠시만 기다려 주세요.";
  if (connection.code === "CLEANUP_UNCONFIRMED")
    return "작업자의 종료가 아직 확인되지 않았습니다. 종료 확인 전에는 계정 작업을 진행할 수 없습니다.";
  const toolingMessage = connectionToolingMessage(connection, agent);
  if (toolingMessage) return toolingMessage;
  if (connection.code === "CODEX_NOT_FOUND" && agent.provider?.executable_available === true)
    return "이전 연결 작업에서 Codex 실행 도구를 찾지 못했습니다. 현재 도구가 있으므로 계정 작업을 다시 시도할 수 있습니다.";
  if (connection.pending && ["LOGOUT_FAILED", "LOGOUT_TIMEOUT"].includes(connection.code ?? ""))
    return "로그아웃을 완료하지 못했습니다. 앱 전용 로그인에서 로그아웃을 다시 시도해 주세요.";
  const errorMessage = connectionErrorMessage(connection.code);
  if (errorMessage) return errorMessage;
  if (connection.status === "authenticated")
    return "공식 로그인이 완료됐습니다. 연결 확인을 누르면 모델 사용 가능 여부를 확인합니다.";
  if (["failed", "blocked"].includes(connection.status))
    return "연결을 확인하지 못했습니다. 다시 연결하거나 연결 상태를 확인해 주세요.";
  if (connection.app_login_required || connection.status === "logged_out")
    return "다시 연결하면 연구를 이어갈 수 있습니다.";
  if (connection.model_available === true && agent.provider?.ready === true)
    return "구독 로그인이 준비됐습니다. 새 연구를 시작할 수 있습니다.";
  if (agent.provider?.ready === false)
    return "현재 모델 실행 연결이 준비되지 않았습니다. 연결 상태를 다시 확인해 주세요.";
  return "공식 OpenAI 로그인으로 사용 중인 구독을 연결하세요.";
}

export function interruptionMessage(run: Pipeline) {
  const code = run.code ?? "";
  if (/MODEL_BUDGET/.test(code))
    return "모델 호출 한도를 사용했습니다. 남은 작업은 완료되지 않았습니다.";
  if (/TIME_BUDGET/.test(code))
    return "설정한 작업 시간이 끝났습니다. 완료한 연구 자료는 보존됩니다.";
  if (/CLEANUP/.test(code))
    return "작업자의 종료가 확인되지 않았습니다. 계정을 변경하기 전에 종료 확인이 필요합니다.";
  if (/AUTH|LOGIN|PROVIDER/.test(code))
    return "Codex 연결 또는 모델 사용 가능 여부를 확인해 주세요.";
  if (/CANCELLED/.test(code) || run.status === "cancelled")
    return "연구를 중지했습니다. 완료한 자료와 연구 기록은 보존됩니다.";
  return "이 연구는 확인이 필요합니다. 연구 기록을 보존한 채 다시 이어갈 수 있습니다.";
}

export function connectionReadiness(connection: Connection, agent: AgentStatus) {
  const toolingBlocked = connectionToolingMessage(connection, agent) !== null;
  const authBusy = ["starting", "waiting_user", "probing", "logging_out"].includes(
    connection.status,
  );
  const explicitlyLoggedOut =
    connection.app_login_required === true ||
    ["logged_out", "logging_out"].includes(connection.status);
  const modelReady =
    !toolingBlocked &&
    !explicitlyLoggedOut &&
    !authBusy &&
    !["failed", "blocked"].includes(connection.status) &&
    connection.model_available === true &&
    agent.provider?.ready === true;
  const canProbe =
    !toolingBlocked &&
    !authBusy &&
    connection.code !== "CLEANUP_UNCONFIRMED" &&
    ((!explicitlyLoggedOut && (connection.authentication === "chatgpt" || modelReady)) ||
      (Boolean(connection.pending?.profile_id) &&
        connection.authentication === "chatgpt" &&
        !["cancelled", "logged_out"].includes(connection.status)));
  const canLogout =
    !codexToolMissing(connection, agent) &&
    (canProbe || connection.connected || Boolean(connection.pending?.profile_id));
  const logoutRetry =
    connection.app_login_required &&
    Boolean(connection.pending?.profile_id) &&
    ["failed", "blocked"].includes(connection.status);
  return {
    authBusy,
    toolingBlocked,
    canLogin: !authBusy && !toolingBlocked,
    modelReady,
    canProbe,
    canLogout: Boolean(canLogout),
    logoutRetry: Boolean(logoutRetry),
  };
}
