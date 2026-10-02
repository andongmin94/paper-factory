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

export function connectionMessage(connection: Connection, agent: AgentStatus) {
  if (connection.status === "logging_out") return "앱 전용 로그인에서 로그아웃하고 있습니다.";
  if (connection.status === "waiting_user") return "공식 로그인 페이지에서 아래 코드를 입력하세요.";
  if (["starting", "probing"].includes(connection.status))
    return "연결을 확인하고 있습니다. 잠시만 기다려 주세요.";
  if (connection.code === "CLEANUP_UNCONFIRMED")
    return "작업자의 종료가 아직 확인되지 않았습니다. 종료 확인 전에는 계정 작업을 진행할 수 없습니다.";
  if (connection.pending && ["LOGOUT_FAILED", "LOGOUT_TIMEOUT"].includes(connection.code ?? ""))
    return "로그아웃을 완료하지 못했습니다. 앱 전용 로그인에서 로그아웃을 다시 시도해 주세요.";
  if (connection.status === "authenticated")
    return "공식 로그인이 완료됐습니다. 연결 확인을 누르면 모델 사용 가능 여부를 확인합니다.";
  if (["failed", "blocked"].includes(connection.status))
    return "연결을 확인하지 못했습니다. 다시 연결하거나 연결 상태를 확인해 주세요.";
  if (connection.app_login_required || connection.status === "logged_out")
    return "다시 연결하면 연구를 이어갈 수 있습니다.";
  if (agent.provider?.executable_available === false)
    return "모델 실행 도구가 준비되지 않았습니다. 설치 안내를 확인해 주세요.";
  if (agent.provider?.capabilities_supported === false)
    return "모델 실행 도구를 업데이트한 뒤 다시 확인해 주세요.";
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
  const authBusy = ["starting", "waiting_user", "probing", "logging_out"].includes(
    connection.status,
  );
  const explicitlyLoggedOut =
    connection.app_login_required === true ||
    ["logged_out", "logging_out"].includes(connection.status);
  const modelReady =
    !explicitlyLoggedOut &&
    !authBusy &&
    !["failed", "blocked"].includes(connection.status) &&
    connection.model_available === true &&
    agent.provider?.ready === true;
  const canProbe =
    !authBusy &&
    connection.code !== "CLEANUP_UNCONFIRMED" &&
    ((!explicitlyLoggedOut && (connection.authentication === "chatgpt" || modelReady)) ||
      (Boolean(connection.pending?.profile_id) &&
        connection.authentication === "chatgpt" &&
        !["cancelled", "logged_out"].includes(connection.status)));
  const canLogout = canProbe || connection.connected || Boolean(connection.pending?.profile_id);
  const logoutRetry =
    connection.app_login_required &&
    Boolean(connection.pending?.profile_id) &&
    ["failed", "blocked"].includes(connection.status);
  return {
    authBusy,
    modelReady,
    canProbe,
    canLogout: Boolean(canLogout),
    logoutRetry: Boolean(logoutRetry),
  };
}
