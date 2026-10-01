"use strict";

// All values displayed by the workspace come from its API. Catalog HTML and
// manuscript Markdown are escaped; only locally served artifact URLs are used.
const icons = {
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  article: '<path d="M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7"/>',
  folder:
    '<path d="M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7z"/>',
  activity: '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 4 2c-1 .6-1.5 1-1.5 2M12 17h.01"/>',
  code: '<path d="m8 7-5 5 5 5m8-10 5 5-5 5m-3-13-2 16"/>',
  spark:
    '<path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5zM20 3v4m-2-2h4"/>',
  home: '<path d="m3 11 9-8 9 8M5 9v12h5v-7h4v7h5V9"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
  refresh:
    '<path d="M20 8a9 9 0 0 0-15-3L3 8m0-5v5h5M4 16a9 9 0 0 0 15 3l2-3m0 5v-5h-5"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  close: '<path d="m6 6 12 12M6 18 18 6"/>',
  check: '<path d="m5 12 4 4L19 6"/>',
  arrow: '<path d="M4 12h16m-6-6 6 6-6 6"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 16v4h16v-4"/>',
  link: '<path d="m9 15 6-6m-5-3 2-2a5 5 0 0 1 7 7l-2 2m-3 5-2 2a5 5 0 0 1-7-7l2-2"/>',
  flask:
    '<path d="M9 3h6m-5 0v7l-6 9a1.5 1.5 0 0 0 1.5 2h13a1.5 1.5 0 0 0 1.5-2l-6-9V3M8 15h8"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  book: '<path d="M3 4h6a3 3 0 0 1 3 3v14a4 4 0 0 0-4-2H3zm18 0h-6a3 3 0 0 0-3 3v14a4 4 0 0 1 4-2h5z"/>',
  shield:
    '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6z"/><path d="m8 12 3 3 5-6"/>',
  file: '<path d="M6 3h9l4 4v14H6zM14 3v5h5"/>',
  external: '<path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7"/>',
};
const icon = (name) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[name] || icons.file}</svg>`;
const e = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ],
  );
const $ = (selector) => document.querySelector(selector);
const list = (value) => (Array.isArray(value) ? value : []);
const textValue = (value) =>
  typeof value === "string" || typeof value === "number" ? String(value) : "";
const localURL = (value) =>
  typeof value === "string" &&
  /^\/api\/(studies|projects)\//.test(value) &&
  !value.includes("\\")
    ? value
    : "";
const externalURL = (value) => {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) &&
      !url.username &&
      !url.password
      ? url.href
      : "";
  } catch {
    return "";
  }
};
const actionLabels = {
  start: "프로젝트 가져오기",
  research: "연구 설계",
  register: "실험 계획 등록",
  run: "실험 수행",
  "literature-search": "문헌 검색",
  "literature-doi": "DOI 문헌 확인",
  "manuscript-build": "원고 생성",
  "manuscript-render": "원고 파일 생성",
  "integrity-check": "무결성 검토",
  "autonomous-start": "자동 연구",
  "autonomous-resume": "자동 연구 재개",
};
const statusLabels = {
  queued: "대기 중",
  running: "수행 중",
  succeeded: "완료",
  failed: "실패",
  interrupted: "중단됨",
  ready: "가져오기 완료",
  complete: "산출물 준비",
  importing: "가져오는 중",
  completed: "산출물 검증 완료",
  blocked: "진행 조건 확인 필요",
  paused: "일시 중지",
  cancelled: "취소됨",
  STUDY_PLANNED: "연구 설계",
  NOVELTY_CHECKED: "문헌 연결",
  EXPERIMENTS_RUNNING: "실험 수행",
  EVIDENCE_READY: "근거 준비",
  MANUSCRIPT_DRAFTED: "검토용 원고",
  INTEGRITY_CHECKED: "무결성 검토 완료",
  AUTHOR_APPROVED: "저자 승인",
};
const views = {
  overview: "대시보드",
  papers: "논문 라이브러리",
  projects: "진행 중인 연구",
  jobs: "작업 기록",
  guide: "연구 시작 안내",
  autonomous: "자동 연구",
};
const state = {
  view: "overview",
  search: "",
  studies: [],
  projects: [],
  jobs: [],
  health: null,
  agent: null,
  agentError: "",
  modelConnection: null,
  modelConnectionError: "",
  modelConnectionFetchError: "",
  modelConnectionBusy: false,
  repositories: null,
  findingRepositories: false,
  startingRecommended: false,
  repositoryDraft: {owner: "", goal: "핵심 동작을 재현 가능한 비교 실험으로 평가하고, 관련 문헌과 한계를 포함한 소프트웨어 공학 논문을 작성한다."},
  loading: true,
  errors: [],
  selectedProject: null,
  stage: "research",
  projectDetail: null,
  paper: null,
  canonical: null,
  expandedJobs: new Set(),
  drafts: {},
  refreshing: false,
};
let toastTimer;
let lastRefresh = 0;
function decorate(root = document) {
  root.querySelectorAll("[data-icon]").forEach((node) => {
    node.innerHTML = icon(node.dataset.icon);
  });
}
function date(value, short = false) {
  if (!value) return "";
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) return "";
  return new Intl.DateTimeFormat("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "short",
    day: "numeric",
    ...(short ? {} : { hour: "2-digit", minute: "2-digit", hour12: false }),
  }).format(d);
}
function size(value) {
  if (!Number.isFinite(Number(value))) return "";
  const n = Number(value);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}
function number(value) {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 4 }).format(value)
    : textValue(value);
}
function extension(file) {
  return (
    textValue(file.path || file.name)
      .split(".")
      .pop() || "FILE"
  ).toUpperCase();
}
function badge(status, label) {
  return `<span class="status-badge ${e(status)}">${status === "succeeded" || status === "ready" ? icon("check") : ""}${e(label || statusLabels[status] || status || "상태 미지정")}</span>`;
}
function toast(message) {
  $("#toast").textContent = message;
  $("#toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    $("#toast").hidden = true;
  }, 4500);
}
function empty(title, description, button = "", symbol = "article") {
  return `<div class="empty-state">${icon(symbol)}<strong>${e(title)}</strong><p>${e(description)}</p>${button}</div>`;
}
function newButton() {
  return `<button class="button button-primary" data-action="new-project" ${state.health?.writes_enabled === false ? "disabled" : ""}>${icon("plus")}새 연구 시작</button>`;
}
function heading(
  title,
  description,
  eyebrow = "RESEARCH WORKSPACE",
  action = true,
) {
  return `<div class="page-title-row"><div><p class="eyebrow">${e(eyebrow)}</p><h1>${e(title)}</h1><p class="page-description">${e(description)}</p></div>${action ? newButton() : ""}</div>`;
}
function sectionHeading(title, count, view, description) {
  return `<div class="section-heading"><div><div class="section-title"><h2>${e(title)}</h2>${count === undefined ? "" : `<span class="section-counter">${e(count)}</span>`}</div>${description ? `<p class="section-caption">${e(description)}</p>` : ""}</div>${view ? `<button class="text-button" data-view="${e(view)}">전체 보기 <span aria-hidden="true">→</span></button>` : ""}</div>`;
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  const content = response.headers.get("content-type") || "";
  let data;
  if (content.includes("application/json")) {
    data = await response.json();
  } else {
    const body = await response.text();
    if (!response.ok)
      throw new Error(`요청을 완료하지 못했습니다 (HTTP ${response.status}).`);
    return body;
  }
  if (!response.ok)
    throw new Error(
      textValue(data.error || data.detail || data.message) ||
        `요청을 완료하지 못했습니다 (HTTP ${response.status}).`,
    );
  return data;
}
function visible(items) {
  const query = state.search.trim().toLocaleLowerCase();
  return query
    ? items.filter((item) =>
        [
          item.title,
          item.title_ko,
          item.name,
          item.question,
          item.research_question,
          list(item.research_questions).join(" "),
          item.repository && typeof item.repository === "object"
            ? item.repository.name
            : item.repository,
          item.source,
          item.subtitle,
        ]
          .map(textValue)
          .join(" ")
          .toLocaleLowerCase()
          .includes(query),
      )
    : items;
}
function metrics(study) {
  const raw = study.metrics;
  if (Array.isArray(raw))
    return raw
      .map((metric) =>
        typeof metric === "object" && metric
          ? {
              label: metric.label || metric.name || metric.metric || "측정값",
              value: metric.value,
              unit: metric.unit || "",
              description: metric.description || "",
            }
          : null,
      )
      .filter(Boolean);
  if (raw && typeof raw === "object")
    return Object.entries(raw).map(([key, value]) =>
      typeof value === "object" && value
        ? {
            label: value.label || key,
            value: value.value,
            unit: value.unit || "",
            description: value.description || "",
          }
        : { label: key, value, unit: "", description: "" },
    );
  return [];
}
function paperStatus(study) {
  const files = list(study.files);
  const pdf = files.some((file) => extension(file) === "PDF");
  const status = study.status || study.state;
  return status
    ? badge(
        status === "complete" ? "ready" : status,
        study.status_label || (status === "complete" ? "산출물 준비" : null),
      )
    : badge(pdf ? "ready" : "warning", pdf ? "원고 준비" : "산출물 확인 중");
}
function studyQuestion(study) {
  return (
    study.question ||
    study.research_question ||
    list(study.research_questions)[0] ||
    ""
  );
}
function repo(study) {
  const raw = textValue(
    study.repository && typeof study.repository === "object"
      ? study.repository.name || study.repository.url
      : study.repository || study.repo || study.source,
  );
  return raw
    .replace(/^https?:\/\/(www\.)?github\.com\//, "")
    .replace(/\/$/, "");
}
function paperCard(study, index) {
  const data = metrics(study).slice(0, 3);
  const types = [
    ...new Set(
      list(study.files)
        .map(extension)
        .filter((ext) => ["PDF", "DOCX", "TEX"].includes(ext)),
    ),
  ];
  return `<article class="paper-card"><div class="paper-cover"><span class="cover-label">EMPIRICAL STUDY / ${e(study.field || "SOFTWARE & SYSTEMS")}</span><span class="cover-number">${String(index + 1).padStart(2, "0")}</span><div class="cover-lines" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div></div><div class="paper-card-content"><div class="card-topline"><span class="repo-label" title="${e(repo(study))}">${e(repo(study) || "연구 프로젝트")}</span>${paperStatus(study)}</div><h3>${e(study.title_ko || study.title || study.slug)}</h3>${study.subtitle ? `<p class="card-subtitle">${e(study.subtitle)}</p>` : ""}<p class="paper-question">${e(studyQuestion(study) || "연구 질문이 아직 등록되지 않았습니다.")}</p><div class="card-metrics">${data.length ? data.map((item) => `<div class="metric-mini"><strong>${e(number(item.value))}${item.unit ? ` <span>${e(item.unit)}</span>` : ""}</strong><small>${e(item.label)}</small></div>`).join("") : '<span class="small-label">측정 결과가 아직 등록되지 않았습니다.</span>'}</div></div><div class="paper-card-footer"><div class="artifact-types">${types.map((ext) => `<span class="file-chip">${ext}</span>`).join("")}${study.bundle_url ? '<span class="file-chip">SOURCE</span>' : ""}</div><button class="card-open" data-action="open-paper" data-id="${e(study.slug)}">논문 열기 ${icon("arrow")}</button></div></article>`;
}
function activityList(jobs) {
  if (!jobs.length)
    return empty(
      "아직 작업 기록이 없습니다",
      "새 연구를 시작하면 수행 과정과 결과가 여기에 기록됩니다.",
      "",
      "activity",
    );
  return `<ul class="activity-list">${jobs
    .slice(0, 4)
    .map((job) => {
      const project = state.projects.find((p) => p.id === job.project_id);
      return `<li><span class="activity-symbol">${icon(job.status === "succeeded" ? "check" : job.status === "running" ? "activity" : "clock")}</span><div class="activity-copy"><strong>${e(actionLabels[job.action] || job.action)} · ${e(statusLabels[job.status] || job.status)}</strong><small>${e(project?.name || job.project_id)}</small></div><span class="activity-time">${e(date(job.finished_at || job.created_at, true))}</span></li>`;
    })
    .join("")}</ul>`;
}
function overview() {
  const papers = visible(state.studies);
  const files = state.studies.flatMap((s) => list(s.files));
  const stats = [
    {
      label: "등록된 연구",
      value: state.studies.length + state.projects.length,
      unit: "건",
      symbol: "folder",
    },
    {
      label: "논문 PDF",
      value: files.filter((f) => extension(f) === "PDF").length,
      unit: "파일",
      symbol: "article",
    },
    {
      label: "진행 중인 작업",
      value: state.jobs.filter((j) => ["queued", "running"].includes(j.status))
        .length,
      unit: "건",
      symbol: "flask",
    },
    { label: "연구 산출물", value: files.length, unit: "파일", symbol: "book" },
  ];
  return `${heading("나의 연구 대시보드", "프로젝트의 가능성을 발견하고, 재현 가능한 논문으로 연결하세요.")}<section class="welcome-panel" aria-label="연구 작업실 안내"><div class="welcome-copy"><p class="eyebrow">FROM CODE TO RESEARCH</p><h2>코드에서 시작해,<br><span>논문으로 완성하는 연구.</span></h2><p>실험, 근거, 문헌, 그리고 원고.<br>연구의 모든 맥락을 한곳에서 이어가세요.</p></div><div class="welcome-art" aria-hidden="true"><div class="art-orbit"></div><div class="art-paper back"></div><div class="art-paper front"><div class="art-label">RESEARCH PAPER</div><i class="art-line dark"></i><i class="art-line short"></i><div class="art-chart"><span></span><span></span><span></span><span></span><span></span></div><i class="art-line"></i><i class="art-line"></i><i class="art-line short"></i></div><div class="art-chip">${icon("check")}Evidence first</div></div></section><section class="stats-grid" aria-label="작업실 현황">${stats.map((stat) => `<div class="stat-card"><div><div class="stat-label">${stat.label}</div><div class="stat-value">${state.loading ? "—" : stat.value}<small>${stat.unit}</small></div></div><span class="stat-icon">${icon(stat.symbol)}</span></div>`).join("")}</section>${sectionHeading("연구 논문", state.studies.length, "papers", "실제 실험 결과와 문헌에 연결된 원고와 재현 자료")}<section class="paper-grid" aria-label="연구 논문 목록">${papers.map(paperCard).join("")}</section>${!papers.length ? (state.loading ? '<div class="loading-state"><span class="spinner"></span>연구 자료를 불러오는 중입니다.</div>' : empty(state.search ? "검색 결과가 없습니다" : "연구 논문이 아직 없습니다", state.search ? "다른 연구 제목이나 프로젝트 이름을 검색해 보세요." : "등록된 최종 원고는 이곳에서 열고 다운로드할 수 있습니다.")) : ""}<div class="lower-grid"><section>${sectionHeading("연구 워크플로", undefined, "guide")}<div class="panel"><ol class="workflow-list"><li><span class="step-number">01</span><div class="step-copy"><strong>연구 설계</strong><small>프로젝트와 검증할 연구 질문을 연결합니다.</small></div><span class="step-arrow">→</span></li><li><span class="step-number">02</span><div class="step-copy"><strong>실험과 근거 수집</strong><small>실험 계획을 실행하고 측정 결과를 보존합니다.</small></div><span class="step-arrow">→</span></li><li><span class="step-number">03</span><div class="step-copy"><strong>문헌 검토와 원고 작성</strong><small>관련 문헌과 검증된 근거로 논문을 구성합니다.</small></div><span class="step-arrow">→</span></li><li><span class="step-number">04</span><div class="step-copy"><strong>최종 산출물 검토</strong><small>무결성을 검토하고 원고와 재현 자료를 내려받습니다.</small></div>${icon("check")}</li></ol></div></section><section>${sectionHeading("최근 작업", undefined, "jobs")}<div class="panel">${activityList(state.jobs)}</div></section></div>`;
}
function papersView() {
  const papers = visible(state.studies);
  return `${heading("논문 라이브러리", "연구 질문부터 최종 원고까지, 검토 가능한 연구 산출물을 모았습니다.", "RESEARCH LIBRARY")}<div class="filter-row"><span class="filter-chip active">전체 논문 ${e(state.studies.length)}</span><span class="filter-chip">원고 · 근거 · 재현 자료</span></div>${papers.length ? `<section class="paper-grid">${papers.map(paperCard).join("")}</section>` : empty(state.search ? "검색 결과가 없습니다" : "등록된 논문이 없습니다", "연구 산출물이 등록되면 원고와 실험 자료를 이곳에서 확인할 수 있습니다.")}`;
}
function projectsView() {
  const projects = visible(state.projects);
  return `${heading("진행 중인 연구", "프로젝트를 가져온 뒤 연구 설계, 실험, 문헌, 원고를 순서대로 이어가세요.", "ACTIVE RESEARCH")}<div class="project-list">${projects.map((project) => `<article class="project-card"><span class="project-card-symbol">${icon("folder")}</span><div class="project-card-copy"><h3>${e(project.name || project.id)}</h3><p title="${e(project.source)}">${e(project.source)}</p></div>${badge(project.status)}<button class="button button-secondary button-small" data-action="open-project" data-id="${e(project.id)}">작업실 열기 ${icon("arrow")}</button></article>`).join("")}</div>${projects.length ? "" : empty(state.search ? "검색 결과가 없습니다" : "첫 연구를 시작해 보세요", "공개 저장소 또는 로컬 프로젝트를 가져와 연구할 질문을 정하세요.", newButton(), "folder")}`;
}
function agentReadiness() {
  if (!state.agent) return `<div class="notice">${e(state.agentError || "구독 모델 연결과 실험 환경을 확인하고 있습니다.")}</div>`;
  const provider = state.agent.provider || {};
  const runner = state.agent.runner || {};
  const providerReady = provider.ready === true;
  let providerMessage = provider.reason;
  if (!providerMessage) {
    if (provider.executable_available === false)
      providerMessage = "공식 Codex CLI를 찾지 못했습니다. CLI 설치 또는 PF_CODEX_BIN 설정을 확인하세요.";
    else if (provider.capabilities_supported === false)
      providerMessage = `설치된 Codex CLI가 필요한 기능을 지원하지 않습니다. 지원되는 CLI로 업데이트하세요.${list(provider.missing_capabilities).length ? ` 누락된 기능: ${list(provider.missing_capabilities).join(", ")}` : ""}`;
    else if (provider.authentication === "api_key")
      providerMessage = "현재 CLI는 API 키로 로그인되어 있습니다. 연구를 시작하려면 ChatGPT 구독으로 로그인하세요.";
    else
      providerMessage = providerReady ? "현재 사용되는 ChatGPT 구독 로그인을 확인했습니다. 실제 모델 요청 가능 여부는 연구 시작 시 확인합니다." : "공식 Codex CLI의 ChatGPT 구독 로그인 상태를 확인하세요.";
  }
  const runnerReady = runner.ready === true;
  return `<div class="agent-readiness"><article class="record-card"><strong>${icon("spark")}Codex 모델 실행 ${badge(providerReady ? "ready" : "warning", providerReady ? "준비됨" : "확인 필요")}</strong><p>${e(providerMessage)}</p></article><article class="record-card"><strong>${icon("shield")}${runner.backend === "windows-appcontainer" ? "Windows 네이티브 실험 환경" : "Docker 격리 실험 환경"} ${badge(runnerReady ? "ready" : "warning", runnerReady ? "사용 가능" : "확인 필요")}</strong><p>${e(runner.reason || (runnerReady ? "생성한 실험 코드를 자원 제한이 있는 별도 환경에서 실행합니다." : "격리 실행 환경이 준비되어야 생성 코드를 실행할 수 있습니다."))}</p></article></div>`;
}
const connectionStates = {
  idle: "연결 전", disconnected: "연결 해제", starting: "로그인 준비 중",
  waiting_user: "공식 로그인 승인 대기", authenticated: "로그인 확인",
  probing: "모델 요청 확인 중", available: "모델 요청 확인 완료",
  blocked: "진행 조건 확인 필요", cancelled: "중단됨", failed: "연결 실패",
};
function officialVerificationURL(value) {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && ["auth.openai.com", "chatgpt.com"].includes(url.hostname) && !url.username && !url.password && !url.port ? url.href : "";
  } catch { return ""; }
}
function connectionPanel() {
  const connection = state.modelConnection;
  const readOnly = state.health?.writes_enabled === false;
  const status = connection?.status || "idle";
  const authentic = connection?.authentication === "chatgpt" || connection?.connected === true;
  const existingLogin = state.agent?.provider.ready === true && !authentic;
  const modelAvailable = connection?.model_available === true;
  const waiting = status === "waiting_user";
  const active = ["starting", "waiting_user", "probing"].includes(status);
  const blocked = readOnly || state.modelConnectionBusy;
  const verificationURL = waiting ? officialVerificationURL(connection?.verification_url) : "";
  const userCode = waiting && typeof connection?.user_code === "string" && /^[A-Za-z0-9-]{4,32}$/.test(connection.user_code) ? connection.user_code : "";
  return `<section class="model-connection panel" aria-label="ChatGPT 구독 연결"><div class="section-heading"><div><h2>연구 작업자에 ChatGPT 구독 연결</h2><p class="section-caption">${existingLogin ? "현재 구독 로그인을 사용할 수 있습니다. 아래에서 다른 연구 계정을 연결할 수 있습니다." : "공식 로그인 페이지에서 계정을 승인하고 실제 모델 요청을 확인하세요."}</p></div>${badge(active ? "running" : ["blocked", "failed"].includes(status) ? "warning" : modelAvailable ? "ready" : "warning", existingLogin && status === "disconnected" ? "새 계정 연결 전" : connectionStates[status] || (modelAvailable ? "모델 요청 확인 완료" : "연결 확인 필요"))}</div><div class="connection-checks"><span>${authentic ? icon("check") : icon("clock")}${existingLogin ? "새 연결의 구독 로그인" : "구독 로그인"}: <strong>${authentic ? "확인" : "확인 필요"}</strong></span><span>${modelAvailable ? icon("check") : icon("clock")}실제 모델 요청: <strong>${modelAvailable ? "확인" : status === "probing" ? "확인 중" : "미확인"}</strong></span></div>${connection?.verified_at && modelAvailable ? `<p class="field-help">마지막 실제 요청 확인: ${e(date(connection.verified_at))}</p>` : ""}${waiting ? `<div class="official-login"><strong>공식 페이지에서 아래 일회용 코드를 입력하세요.</strong>${userCode ? `<div class="device-code" aria-label="일회용 로그인 코드"><code>${e(userCode)}</code></div>` : '<p class="field-help">로그인 코드를 기다리고 있습니다.</p>'}${verificationURL ? `<a class="button button-primary" href="${e(verificationURL)}" target="_blank" rel="noopener noreferrer">공식 로그인 페이지 열기 ${icon("external")}</a>` : '<p class="field-help">공식 로그인 주소를 확인한 뒤 링크를 표시합니다.</p>'}<p class="field-help">비밀번호와 계정 승인은 공식 페이지에서 진행합니다. OpenAI에서 로그인을 완료한 뒤 이 화면에서 연결 상태를 확인하세요.</p></div>` : ""}${connection?.message ? `<p class="connection-message" role="status">${e(connection.message)}</p>` : ""}${pipelineHelp(connection || {})}${state.modelConnectionError || state.modelConnectionFetchError ? `<div class="form-error" role="alert">${e(state.modelConnectionError || state.modelConnectionFetchError)}</div>` : ""}${readOnly ? '<p class="field-help">현재는 논문 열람 모드입니다. 구독 연결은 로컬 주소로 연 연구 작업실에서 사용할 수 있습니다.</p>' : ""}<div class="inline-actions">${!active ? `<button class="button ${authentic ? "button-secondary" : "button-primary"}" data-action="connect-model" ${blocked ? "disabled" : ""}>${icon("link")}${authentic ? "계정 다시 연결" : "ChatGPT 구독으로 연결"}</button>` : ""}${authentic && !active ? `<button class="button button-secondary" data-action="probe-model" ${blocked ? "disabled" : ""}>${icon("activity")}실제 모델 요청 확인</button>` : ""}${active ? `<button class="button button-secondary" data-action="cancel-model-connection" ${blocked ? "disabled" : ""}>연결 작업 중단</button>` : ""}${authentic && !active ? `<button class="button button-secondary" data-action="disconnect-model" ${blocked ? "disabled" : ""}>연구 작업자 연결 해제</button>` : ""}</div><p class="field-help">로그인 확인과 모델 사용 가능 여부를 따로 검증합니다. 사용량 제한이나 네트워크 오류가 발생하면 원인을 확인하고 다시 요청할 수 있습니다.</p></section>`;
}
async function changeModelConnection(operation) {
  if (state.modelConnectionBusy || state.health?.writes_enabled === false) return;
  state.modelConnectionBusy = true;
  state.modelConnectionError = "";
  render();
  if ($("#project-dialog").open && state.stage === "autonomous") renderProject();
  try {
    const result = await api(`/api/agent/connection/${operation}`, {method: "POST", body: JSON.stringify({})});
    state.modelConnection = result;
  } catch (error) {
    state.modelConnectionError = error.message;
  } finally {
    state.modelConnectionBusy = false;
    await refresh({silent: true});
    render();
    if ($("#project-dialog").open && state.stage === "autonomous") renderProject();
  }
}
function autonomousView() {
  const projects = visible(state.projects);
  return `${heading("저장소에서 논문까지", "구독으로 로그인한 Codex와 실제 실험을 연결해, 원고와 재현 자료를 만듭니다.", "AUTONOMOUS RESEARCH")}${agentReadiness()}${connectionPanel()}<section class="panel autonomous-intro"><h2>연구 목표를 정하고 시작하세요.</h2><p>프로젝트를 가져온 뒤 목표와 실행 한도를 입력하세요. 연구 설계, 문헌 확인, 실험 코드 생성·실행, 분석, 원고 작성과 파일 검증을 이어갑니다. 이 화면을 닫아도 서버 작업자는 진행하며, 중단된 작업은 저장된 단계부터 재개할 수 있습니다.</p><p class="field-help">실험 결과가 부족하거나 실행·로그인 조건이 충족되지 않으면 이유를 표시합니다. 생성된 원고는 저자의 검토가 필요한 초안입니다.</p></section><section class="panel autonomous-intro"><h2>GitHub 계정에서 연구할 저장소 찾기</h2><form data-form="repositories"><label class="field-label" for="repository-owner">계정 이름 또는 프로필 주소</label><input id="repository-owner" name="owner" class="field" required placeholder="https://github.com/owner" value="${e(state.repositoryDraft.owner)}"><label class="field-label" for="repository-goal">선택한 저장소의 연구 목표</label><textarea id="repository-goal" name="goal" class="field" required minlength="8" maxlength="4000">${e(state.repositoryDraft.goal)}</textarea><div class="inline-actions"><button class="button button-secondary" type="submit" ${state.health?.writes_enabled === false || state.findingRepositories ? "disabled" : ""}>${icon("search")}${state.findingRepositories ? "저장소를 확인하는 중" : "적절한 저장소 3개 찾기"}</button></div><div id="repository-error" class="form-error" role="alert" hidden></div></form>${repositoryResults()}</section>${sectionHeading("연구할 프로젝트", projects.length)}<div class="project-list">${projects.map(project => `<article class="project-card"><span class="project-card-symbol">${icon("folder")}</span><div class="project-card-copy"><h3>${e(project.name || project.id)}</h3><p>${e(project.source)}</p></div>${badge(project.status)}<button class="button button-secondary button-small" data-action="open-autonomous" data-id="${e(project.id)}">자동 연구 열기 ${icon("arrow")}</button></article>`).join("")}</div>${projects.length ? "" : empty("연구할 저장소를 가져오세요", "GitHub 저장소나 로컬 프로젝트에서 자동 연구를 시작할 수 있습니다.", newButton(), "folder")}`;
}
function repositoryResults() {
  if (!state.repositories) return "";
  const candidates = list(state.repositories.repositories);
  return `<div class="record-list repository-results">${candidates.map((candidate, index) => `<article class="record-card"><strong>${e(candidate.name)}</strong><p>${e(candidate.reason)}</p><p class="field-help">${e(candidate.language || "언어 정보 없음")}</p><button class="button button-secondary button-small" data-action="import-recommended" data-index="${index}" ${state.startingRecommended ? "disabled" : ""}>이 저장소로 자동 연구 시작</button></article>`).join("")}</div>${candidates.length ? `<div class="inline-actions"><button class="button button-primary" data-action="import-all-recommended" ${state.startingRecommended ? "disabled" : ""}>${candidates.length}개 저장소 모두 자동 연구 시작</button></div>` : '<p class="field-help">지원 가능한 연구 후보를 찾지 못했습니다.</p>'}<p class="field-help">${list(state.repositories.limitations).map(e).join(" ")}</p>`;
}
async function findRepositories(form) {
  state.findingRepositories = true;
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  state.repositoryDraft = {owner: form.elements.owner.value.trim(), goal: form.elements.goal.value.trim()};
  try {
    state.repositories = await api("/api/agent/repositories", {method: "POST", body: JSON.stringify({owner: state.repositoryDraft.owner, count: 3})});
    state.findingRepositories = false;
    render();
  } catch (error) {
    if ($("#repository-error")) {
      $("#repository-error").textContent = error.message;
      $("#repository-error").hidden = false;
    } else notice(error.message, true);
  } finally { state.findingRepositories = false; button.disabled = false; }
}
async function startRecommended(indices, button) {
  if (state.startingRecommended) return;
  state.startingRecommended = true;
  const candidates = list(state.repositories?.repositories);
  if (button) button.disabled = true;
  let count = 0;
  try {
    for (const index of indices) {
      const candidate = candidates[index];
      if (!candidate) continue;
      const result = await api("/api/projects", {method: "POST", body: JSON.stringify({source: candidate.url, name: candidate.name, autonomous: {goal: state.repositoryDraft.goal}})});
      state.projects.push(result.project);
      state.jobs.unshift(result.job);
      count += 1;
    }
    state.startingRecommended = false;
    render();
    toast(`${count}개 저장소를 가져온 뒤 자동 연구를 시작합니다.`);
  } catch (error) {
    notice(`${count ? `${count}개 연구를 시작했습니다. ` : ""}${error.message}`, true);
  } finally { state.startingRecommended = false; if (button) button.disabled = false; }
}
function jobDetail(job) {
  return `<div class="job-detail">${job.error ? `<div class="form-error">${e(job.error)}</div>` : ""}${job.result ? `<strong class="small-label">결과 기록</strong><pre>${e(JSON.stringify(job.result, null, 2))}</pre>` : ""}<strong class="small-label">수행 기록</strong><pre>${e(job.log || (["queued", "running"].includes(job.status) ? "기록을 기다리고 있습니다." : "추가 수행 기록이 없습니다."))}</pre></div>`;
}
function jobsView() {
  return `${heading("작업 기록", "실험과 원고 생성의 실제 수행 상태, 결과와 실패 원인을 확인하세요.", "ACTIVITY LOG", false)}${
    state.jobs.length
      ? `<div class="data-table-wrap"><table class="data-table"><thead><tr><th>작업</th><th>연구 프로젝트</th><th>상태</th><th>시작 시각 · 서울</th><th>기록</th></tr></thead><tbody>${state.jobs
          .map((job) => {
            const project = state.projects.find((p) => p.id === job.project_id);
            return `<tr><td>${e(actionLabels[job.action] || job.action)}</td><td>${e(project?.name || job.project_id)}</td><td>${badge(job.status)}</td><td>${e(date(job.started_at || job.created_at))}</td><td><button data-action="toggle-job" data-id="${e(job.id)}" aria-expanded="${state.expandedJobs.has(job.id)}">${state.expandedJobs.has(job.id) ? "접기" : "자세히"}</button></td></tr>${state.expandedJobs.has(job.id) ? `<tr><td colspan="5">${jobDetail(job)}</td></tr>` : ""}`;
          })
          .join("")}</tbody></table></div>`
      : empty(
          "아직 수행한 작업이 없습니다",
          "프로젝트를 가져오거나 연구 단계를 수행하면 결과가 기록됩니다.",
          newButton(),
          "activity",
        )
  }`;
}
function guideView() {
  const items = [
    [
      "프로젝트와 연구 질문",
      "공개 Git 저장소 또는 로컬 프로젝트를 가져오고, 검증할 연구 질문을 작성하세요. 자동 기초 조사는 파일 구성을 확인하는 시작점이며, 논문의 기여를 대신하지 않습니다.",
    ],
    [
      "실험 계획과 측정",
      "프로젝트에 포함된 분석 스크립트의 실험 계획을 JSON으로 등록하세요. 입력, 출력, 지표를 명시하고 실험을 수행하면 결과와 근거가 보존됩니다.",
    ],
    [
      "문헌 검토",
      "연구 질문에 맞는 문헌을 검색하거나 DOI를 등록하세요. 서지 정보 확인 뒤 원문을 읽고, 기존 연구와 이번 연구의 차이를 검토하세요.",
    ],
    [
      "원고와 최종 산출물",
      "측정 결과를 바탕으로 원고를 만들고 본문을 편집하세요. PDF·DOCX·TeX 파일을 생성한 뒤 무결성을 검토하고 재현 자료와 함께 내려받으세요.",
    ],
  ];
  return `${heading("연구 시작 안내", "한 단계씩 근거를 쌓고, 직접 검토할 수 있는 논문으로 완성하세요.", "GETTING STARTED")}<section class="guide-grid">${items.map(([title, description], index) => `<article class="guide-card"><span class="step-number">0${index + 1}</span><h2>${e(title)}</h2><p>${e(description)}</p></article>`).join("")}</section><p class="guide-footnote">실험 실행에는 가져온 프로젝트의 분석 스크립트가 사용됩니다. 검토한 프로젝트의 실험 계획을 등록하세요. 문헌 검색은 검색어나 DOI를 Crossref에 전달하며, 원문 내용의 검토는 별도 단계입니다. 원고 파일의 준비 상태와 학술적 기여·게재 여부는 각각 검토해야 합니다.</p>`;
}
function render() {
  const focused = state.view === "autonomous" && document.activeElement?.closest('[data-form="repositories"]') ? {id: document.activeElement.id, start: document.activeElement.selectionStart, end: document.activeElement.selectionEnd} : null;
  const renderers = {
    overview,
    papers: papersView,
    projects: projectsView,
    jobs: jobsView,
    guide: guideView,
    autonomous: autonomousView,
  };
  $("#page-content").innerHTML = renderers[state.view]();
  $("#view-label").textContent = views[state.view];
  document
    .querySelectorAll(".nav-item[data-view], .mobile-nav [data-view]")
    .forEach((node) => {
      const active = node.dataset.view === state.view;
      node.classList.toggle("active", active);
      if (active) node.setAttribute("aria-current", "page");
      else node.removeAttribute("aria-current");
    });
  $("#library-count").textContent = state.loading ? "—" : state.studies.length;
  $("#project-count").textContent = state.loading ? "—" : state.projects.length;
  $("#jobs-dot").hidden = !state.jobs.some((job) =>
    ["queued", "running"].includes(job.status),
  );
  decorate($("#page-content"));
  if (focused && document.getElementById(focused.id)) {
    const field = document.getElementById(focused.id);
    field.focus({preventScroll: true});
    if (Number.isInteger(focused.start)) field.setSelectionRange(focused.start, focused.end);
  }
}
function notice(message, error = false) {
  const node = $("#global-notice");
  node.textContent = message;
  node.hidden = !message;
  node.classList.toggle("error", error);
}
function updateConnection() {
  const healthy = Boolean(state.health);
  $("#connection-dot").className =
    `connection-dot ${healthy ? "online" : "offline"}`;
  $("#connection-label").textContent = healthy
    ? "환경 연결됨"
    : "연결을 확인해 주세요";
  $("#connection-detail").textContent = healthy
    ? state.health.writes_enabled
      ? "연구 작업 사용 가능"
      : "논문 열람 모드"
    : "새로고침으로 다시 연결";
  $("#version-label").textContent = state.health?.version
    ? `v${state.health.version}`
    : "";
}
async function refresh({ silent = false } = {}) {
  if (state.refreshing) return;
  state.refreshing = true;
  const results = await Promise.allSettled([
    api("/api/health"),
    api("/api/studies"),
    api("/api/projects"),
    api("/api/jobs"),
    api("/api/agent/status"),
    api("/api/agent/connection"),
  ]);
  if (results[0].status === "fulfilled") state.health = results[0].value;
  else state.health = null;
  if (results[1].status === "fulfilled") {
    state.studies = list(results[1].value.studies);
    state.errors = list(results[1].value.errors);
  }
  if (results[2].status === "fulfilled")
    state.projects = list(results[2].value.projects);
  const old = new Map(state.jobs.map((job) => [job.id, job.status]));
  if (results[3].status === "fulfilled")
    state.jobs = list(results[3].value.jobs);
  if (results[4].status === "fulfilled") {
    state.agent = results[4].value;
    state.agentError = "";
  } else {
    state.agent = null;
    state.agentError = results[4].reason.message;
  }
  if (results[5].status === "fulfilled") {
    state.modelConnection = results[5].value;
    state.modelConnectionFetchError = "";
  } else {
    state.modelConnection = null;
    state.modelConnectionFetchError = state.health?.writes_enabled === false ? "" : results[5].reason.message;
  }
  state.loading = false;
  state.refreshing = false;
  lastRefresh = Date.now();
  updateConnection();
  if (!state.health)
    notice(
      "연구 환경에 연결하지 못했습니다. 서버 상태를 확인한 뒤 새로고침해 주세요.",
      true,
    );
  else if (results[1].status === "rejected")
    notice(
      `논문 자료를 불러오지 못했습니다. ${results[1].reason.message}`,
      true,
    );
  else if (state.errors.length)
    notice(
      `일부 연구 자료를 불러오지 못했습니다 (${state.errors.length}건). 등록된 파일과 연구 정보를 확인해 주세요.`,
    );
  else if (state.health.writes_enabled === false)
    notice(
      "현재는 논문 열람 모드입니다. 프로젝트 작업은 로컬 주소로 열린 연구 작업실에서 사용할 수 있습니다.",
    );
  else if (results[2].status === "rejected" || results[3].status === "rejected")
    notice(
      "논문을 열람할 수 있지만 연구 작업 기록에 연결하지 못했습니다. 새로고침해 주세요.",
      true,
    );
  else notice("");
  render();
  updateProjectJob();
  const changed = state.jobs.some(
    (job) =>
      job.project_id === state.selectedProject &&
      ["succeeded", "failed", "interrupted", "blocked", "paused", "cancelled"].includes(job.status) &&
      old.get(job.id) &&
      old.get(job.id) !== job.status,
  );
  if ((changed || state.stage === "autonomous") && $("#project-dialog").open) {
    await reloadProject();
    if (changed) toast("작업 결과가 기록되었습니다.");
  }
  if (!silent && !state.loading && results[0].status === "fulfilled")
    return true;
}
function switchView(view) {
  if (!views[view]) return;
  state.view = view;
  render();
}
function openImport() {
  if (state.health?.writes_enabled === false) {
    toast("현재 논문 열람 모드에서는 새 연구를 시작할 수 없습니다.");
    return;
  }
  $("#import-error").hidden = true;
  $("#import-dialog").showModal();
}
async function handleImport(form) {
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  $("#import-error").hidden = true;
  try {
    const payload = { source: form.elements.source.value.trim() };
    if (form.elements.name.value.trim())
      payload.name = form.elements.name.value.trim();
    const data = await api("/api/projects", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    $("#import-dialog").close();
    form.reset();
    state.projects.push(data.project);
    state.jobs.unshift(data.job);
    state.view = "projects";
    render();
    toast(
      "프로젝트를 가져오는 중입니다. 작업 기록에서 진행 상태를 확인하세요.",
    );
    await openProject(data.project.id);
  } catch (error) {
    $("#import-error").textContent = error.message;
    $("#import-error").hidden = false;
  } finally {
    button.disabled = false;
  }
}
function downloadItem(file, label) {
  const url = localURL(file.url);
  if (!url) return "";
  return `<a class="download-item" href="${e(url)}?download=1" download><span class="download-filetype">${e(extension(file))}</span><span class="download-copy"><strong>${e(label || file.label || file.name)}</strong><small>${e(size(file.size))}</small></span>${icon("download")}</a>`;
}
function fileList(files) {
  return `<ul class="file-list">${files
    .filter((file) => localURL(file.url))
    .map(
      (file) =>
        `<li><a href="${e(localURL(file.url))}?download=1" download>${icon("file")}<span class="file-name">${e(file.path || file.name)}</span><span class="file-size">${e(size(file.size))}</span>${icon("download")}</a></li>`,
    )
    .join("")}</ul>`;
}
function figureMarkup(study) {
  return list(study.figures)
    .map((figure) => {
      const path = typeof figure === "string" ? figure : figure.path;
      const file = list(study.files).find((f) => f.path === path);
      const url = localURL(file?.url);
      if (!url || !file?.mime?.startsWith("image/")) return "";
      const caption =
        typeof figure === "object"
          ? figure.caption || figure.title || file.name
          : file.name;
      return `<figure class="figure-preview"><img src="${e(url)}" alt="${e(typeof figure === "object" ? figure.alt || caption : caption)}" loading="lazy"><figcaption>${e(caption)}</figcaption></figure>`;
    })
    .join("");
}
function tableMarkup(table) {
  const columns = list(table.columns || table.headers);
  const rows = list(table.rows || table.data);
  if (!columns.length || !rows.length) return "";
  return `<div class="detail-section">${table.title ? `<h3>${e(table.title)}</h3>` : ""}<div class="result-table-wrap"><table class="result-table"><thead><tr>${columns.map((col) => `<th scope="col">${e(typeof col === "object" ? col.label || col.key : col)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((col, i) => `<td>${e(number(Array.isArray(row) ? row[i] : row[typeof col === "object" ? col.key : col]))}</td>`).join("")}</tr>`).join("")}</tbody></table></div></div>`;
}
async function openPaper(slug) {
  $("#paper-title").textContent = "논문을 불러오는 중";
  $("#paper-subtitle").textContent = "";
  $("#paper-dialog-body").innerHTML =
    '<div class="loading-state"><span class="spinner"></span>연구 자료를 불러오는 중입니다.</div>';
  $("#paper-dialog").showModal();
  try {
    const study = await api(`/api/studies/${encodeURIComponent(slug)}`);
    state.paper = study;
    $("#paper-title").textContent = study.title || study.slug;
    $("#paper-subtitle").textContent = [study.subtitle, repo(study)]
      .filter(Boolean)
      .join(" · ");
    renderPaper(study);
  } catch (error) {
    $("#paper-title").textContent = "자료를 불러오지 못했습니다";
    $("#paper-dialog-body").innerHTML = empty(
      "연구 자료에 연결할 수 없습니다",
      error.message,
    );
  }
}
function renderPaper(study) {
  const data = metrics(study);
  const files = list(study.files);
  const docs = files.filter((file) =>
    ["PDF", "DOCX", "TEX"].includes(extension(file)),
  );
  const manuscript =
    files.find(
      (file) => file.role === "manuscript" && extension(file) === "MD",
    ) ||
    files.find(
      (file) => extension(file) === "MD" && !/readme/i.test(file.name),
    );
  const limitations = list(study.limitations);
  const abstract =
    typeof study.abstract === "string"
      ? study.abstract
      : study.abstract
        ? JSON.stringify(study.abstract, null, 2)
        : "";
  $("#paper-dialog-body").innerHTML =
    `<div class="paper-detail-layout"><div class="paper-main"><div class="reading-tabs"><button class="active" data-reading="overview">연구 개요</button><button data-reading="article" ${manuscript ? "" : "disabled"}>원고 읽기</button><button data-reading="data">근거 자료</button></div><div id="paper-overview"><section class="detail-section"><h3>연구 질문</h3><div class="question-callout">${e(studyQuestion(study) || "연구 질문 미등록")}</div></section>${abstract ? `<section class="detail-section"><h3>초록</h3><p>${e(abstract)}</p></section>` : ""}${data.length ? `<section class="detail-section"><h3>핵심 측정 결과</h3><div class="detail-metrics">${data.map((item) => `<div class="detail-metric"><strong>${e(number(item.value))} ${e(item.unit)}</strong><small>${e(item.label)}</small>${item.description ? `<p>${e(item.description)}</p>` : ""}</div>`).join("")}</div></section>` : ""}${figureMarkup(study) ? `<section class="detail-section"><h3>그림과 결과</h3>${figureMarkup(study)}</section>` : ""}${list(study.tables).map(tableMarkup).join("")}${limitations.length ? `<section class="detail-section"><h3>연구 범위와 한계</h3><ul>${limitations.map((item) => `<li>${e(typeof item === "string" ? item : JSON.stringify(item))}</li>`).join("")}</ul></section>` : ""}</div><div id="paper-article" hidden><div class="article-content" id="article-content">${manuscript ? '<div class="loading-state"><span class="spinner"></span>원고를 불러오는 중입니다.</div>' : empty("읽을 수 있는 원고가 없습니다", "PDF 또는 DOCX 파일을 내려받아 원고를 검토하세요.")}</div></div><div id="paper-data" hidden><section class="detail-section"><h3>실험 자료와 원고 파일</h3><p>등록된 원고, 결과 데이터, 그림과 재현 자료를 확인하세요.</p></section>${files.length ? fileList(files) : empty("등록된 파일이 없습니다", "연구 산출물 등록을 기다리고 있습니다.")}</div></div><aside class="paper-aside"><section class="detail-section"><p class="aside-label">DOWNLOADS</p><div class="download-list">${docs.map((file) => downloadItem(file, extension(file) === "PDF" ? "논문 PDF" : extension(file) === "DOCX" ? "편집용 Word 원고" : "LaTeX 원고")).join("")}${localURL(study.bundle_url) ? `<a class="download-item" href="${e(localURL(study.bundle_url))}" download><span class="download-filetype">ZIP</span><span class="download-copy"><strong>전체 재현 자료</strong><small>원고 · 데이터 · 그림</small></span>${icon("download")}</a>` : ""}</div>${!docs.length ? "<p>원고 파일이 아직 등록되지 않았습니다.</p>" : ""}</section><section class="detail-section"><p class="aside-label">RESEARCH DETAILS</p>${paperStatus(study)}<p class="paper-kind">${e(study.kind || study.study_type || "재현 가능한 경험적 연구")}</p>${externalURL(study.repository && typeof study.repository === "object" ? study.repository.url : study.repository) ? `<a class="button button-secondary button-small" href="${e(externalURL(study.repository && typeof study.repository === "object" ? study.repository.url : study.repository))}" target="_blank" rel="noopener noreferrer">저장소 보기 ${icon("external")}</a>` : ""}</section>${study.author ? `<section class="detail-section"><p class="aside-label">AUTHOR</p><p>${e(typeof study.author === "string" ? study.author : study.author.display_name || study.author.name || "")}</p>${typeof study.author === "object" && study.author.orcid ? `<a class="small-label" href="https://orcid.org/${e(study.author.orcid)}" target="_blank" rel="noopener noreferrer">ORCID ${e(study.author.orcid)}</a>` : ""}</section>` : ""}</aside></div>`;
  if (manuscript && localURL(manuscript.url)) {
    fetch(localURL(manuscript.url), { headers: { Accept: "text/plain" } })
      .then((response) => {
        if (!response.ok)
          throw new Error(`원고 읽기 실패 (HTTP ${response.status})`);
        return response.text();
      })
      .then((content) => {
        if (state.paper?.slug === study.slug && $("#article-content"))
          $("#article-content").innerHTML = markdown(content);
      })
      .catch((error) => {
        if (state.paper?.slug === study.slug && $("#article-content"))
          $("#article-content").innerHTML = empty(
            "원고를 불러오지 못했습니다",
            error.message,
          );
      });
  }
}
function inlineMarkdown(text) {
  return e(text)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\[([^\]]+)\]\(([^\s)]+)\)/g, (_, label, url) => {
      const raw = url.replace(/&amp;/g, "&");
      const href = externalURL(raw);
      return href
        ? `<a href="${e(href)}" target="_blank" rel="noopener noreferrer">${label}</a>`
        : label;
    });
}
function markdown(content) {
  const lines = String(content)
    .replace(/\r\n/g, "\n")
    .replace(/^---\n[\s\S]*?\n---\n/, "")
    .split("\n");
  let output = "",
    paragraph = [],
    code = [],
    inCode = false,
    items = [],
    ordered = false;
  const flush = () => {
    if (paragraph.length) {
      output += `<p>${inlineMarkdown(paragraph.join(" "))}</p>`;
      paragraph = [];
    }
    if (items.length) {
      output += `<${ordered ? "ol" : "ul"}>${items.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</${ordered ? "ol" : "ul"}>`;
      items = [];
    }
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (/^\s*```/.test(line)) {
      flush();
      if (inCode) {
        output += `<pre>${e(code.join("\n"))}</pre>`;
        code = [];
      }
      inCode = !inCode;
      continue;
    }
    if (inCode) {
      code.push(line);
      continue;
    }
    if (/^\s*\|?\s*:?-{3,}/.test(lines[i + 1] || "") && line.includes("|")) {
      flush();
      const cells = (value) =>
        value
          .trim()
          .replace(/^\||\|$/g, "")
          .split("|")
          .map((cell) => cell.trim());
      const columns = cells(line);
      i++;
      const rows = [];
      while (
        i + 1 < lines.length &&
        lines[i + 1].includes("|") &&
        lines[i + 1].trim()
      ) {
        rows.push(cells(lines[++i]));
      }
      output += `<table><thead><tr>${columns.map((c) => `<th>${inlineMarkdown(c)}</th>`).join("")}</tr></thead><tbody>${rows.map((row) => `<tr>${columns.map((_, j) => `<td>${inlineMarkdown(row[j] || "")}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
      continue;
    }
    const headingMatch = line.match(/^(#{1,3})\s+(.+)$/);
    if (headingMatch) {
      flush();
      output += `<h${headingMatch[1].length}>${inlineMarkdown(headingMatch[2])}</h${headingMatch[1].length}>`;
      continue;
    }
    const item = line.match(/^\s*(?:([-*])|(\d+)\.)\s+(.+)$/);
    if (item) {
      if (paragraph.length) flush();
      if (items.length && ordered !== Boolean(item[2])) flush();
      ordered = Boolean(item[2]);
      items.push(item[3]);
      continue;
    }
    if (!line.trim()) {
      flush();
      continue;
    }
    if (items.length) flush();
    if (/^---+$/.test(line.trim())) {
      flush();
      output += "<hr>";
      continue;
    }
    paragraph.push(line);
  }
  flush();
  if (code.length) output += `<pre>${e(code.join("\n"))}</pre>`;
  return output;
}
async function openProject(id, stage = "research") {
  state.selectedProject = id;
  state.stage = stage;
  state.projectDetail = null;
  state.canonical = null;
  $("#project-title").textContent = "연구 작업실";
  $("#project-subtitle").textContent = "";
  $("#project-dialog-body").innerHTML =
    '<div class="loading-state"><span class="spinner"></span>연구 기록을 불러오는 중입니다.</div>';
  $("#project-dialog").showModal();
  await reloadProject();
}
async function reloadProject() {
  const id = state.selectedProject;
  if (!id) return;
  try {
    const detail = await api(`/api/projects/${encodeURIComponent(id)}`);
    if (state.selectedProject !== id) return;
    state.projectDetail = detail;
    $("#project-title").textContent = detail.name || detail.id;
    $("#project-subtitle").textContent = detail.source || "";
    renderProject();
  } catch (error) {
    if (state.selectedProject === id)
      $("#project-dialog-body").innerHTML = empty(
        "연구 기록에 연결하지 못했습니다",
        error.message,
      );
  }
}
function records(kind) {
  return list(state.projectDetail?.records?.[kind]);
}
function latest(kind) {
  return records(kind).at(-1);
}
function studySelect(name = "study", id = "study-select") {
  const studies = records("study");
  return `<label class="field-label" for="${e(id)}">연구 질문</label><select class="field" name="${e(name)}" id="${e(id)}">${studies.map((study) => `<option value="${e(study.id)}">${e(study.title)}</option>`).join("")}</select>`;
}
function formError() {
  return '<div class="form-error" id="workspace-error" role="alert" hidden></div>';
}
const pipelineStages = {
  assess: "프로젝트 분석", plan: "연구 설계", literature: "문헌 확인",
  generate: "실험 코드 생성", execute: "실험 실행", analyze: "결과 분석",
  write: "논문 작성", export: "파일 생성", verify: "산출물 검증", done: "완료",
};
function pipelineHelp(run) {
  const help = {
    AUTH_REQUIRED: "서버 환경에서 공식 Codex CLI에 로그인한 뒤 재개하세요.",
    CODEX_UNAVAILABLE: "서버 환경에 공식 Codex CLI를 설치하거나 실행 경로를 설정한 뒤 재개하세요.",
    RATE_LIMITED: "구독 계정의 사용량 제한이 해제된 뒤 재개하세요. 완료된 단계는 보존됩니다.",
    ISOLATION_UNAVAILABLE: "선택된 실험 환경을 준비한 뒤 재개하세요. 생성 코드는 해당 환경의 격리와 자원 제한 안에서 실행됩니다.",
    NETWORK_ERROR: `모델 서비스의 네트워크 접근 설정을 확인한 뒤 재개하세요.${/403/.test(run.message || "") ? " HTTP CONNECT 403은 환경 프록시가 모델 요청을 거부했다는 뜻입니다." : ""} CLI 로그인 확인과 실제 모델 요청 가능 여부는 별도로 확인됩니다.`,
  };
  return help[run.code] ? `<p class="field-help pipeline-help">${e(help[run.code])}</p>` : "";
}
function pipelineCard(run) {
  const active = ["queued", "running"].includes(run.status);
  const resumable = ["blocked", "paused", "failed", "cancelled"].includes(run.status);
  const completedStages = new Set(list(run.attempts).filter(a => a.status === "completed").map(a => a.stage));
  const steps = Object.entries(pipelineStages).filter(([key]) => key !== "done");
  return `<article class="pipeline-card"><div class="project-job-title"><strong>${e(run.goal || run.id)}</strong>${badge(run.status)}</div><p class="field-help">현재 단계: ${e(pipelineStages[run.stage] || run.stage)} · 모델 호출 ${e(number(run.model_calls || 0))}/${e(run.budget?.max_model_calls || "—")} · 수행 시간 ${e(Math.round(Number(run.elapsed_seconds) || 0))}초</p><ol class="pipeline-stages" aria-label="자동 연구 진행 단계">${steps.map(([key, label]) => `<li class="${completedStages.has(key) ? "finished" : run.stage === key ? "current" : ""}">${completedStages.has(key) ? icon("check") : icon(run.stage === key && active ? "clock" : "file")}<span>${e(label)}</span></li>`).join("")}</ol>${run.message || run.error ? `<div class="notice ${run.status === "failed" ? "error" : ""}">${e(run.message || run.error)}${run.code ? `<small class="pipeline-code">${e(run.code)}</small>` : ""}</div>` : ""}${pipelineHelp(run)}${run.cancellation_requested && active ? '<p class="field-help">중단 요청을 전달했습니다. 현재 작업을 정리한 뒤 상태를 저장합니다.</p>' : ""}<div class="inline-actions">${active ? `<button class="button button-secondary button-small" data-action="cancel-pipeline" data-id="${e(run.id)}" ${run.cancellation_requested ? "disabled" : ""}>중단 요청</button>` : ""}${resumable ? `<button class="button button-primary button-small" data-action="resume-pipeline" data-id="${e(run.id)}">저장된 단계부터 재개</button>` : ""}<span class="small-label">${e(date(run.updated_at || run.created_at))}</span></div>${list(run.files).length ? `<h4 class="field-label">생성된 산출물</h4>${fileList(run.files)}` : ""}</article>`;
}
function autonomousStage() {
  const runs = list(state.projectDetail.pipelines);
  const draft = state.drafts[`${state.selectedProject}:autonomous`] || state.projectDetail.pending_autonomous || {};
  const active = runs.some(run => ["queued", "running"].includes(run.status));
  return `<h3 class="workspace-section-heading">연구 목표부터 최종 파일까지</h3><p class="workspace-section-intro">연구할 목표를 입력하면 프로젝트 분석부터 실험·분석·원고 작성까지 작업자가 진행합니다. 결과를 실제로 측정하고 근거를 확인한 원고와 재현 자료를 생성합니다.</p>${agentReadiness()}${connectionPanel()}${state.projectDetail.autonomous_error ? `<div class="notice error">자동 연구 시작·재개 조건을 확인하세요. ${e(state.projectDetail.autonomous_error)}</div>` : ""}${runs.map(pipelineCard).join("")}<form data-form="autonomous"><label class="field-label" for="autonomous-goal">연구 목표 <span class="required">*</span></label><textarea id="autonomous-goal" name="goal" class="field" required minlength="8" maxlength="4000" placeholder="예: 이 프로젝트의 핵심 동작을 비교 실험으로 평가하고, 한계와 재현 자료를 포함한 소프트웨어 공학 논문을 작성한다.">${e(draft.goal || "")}</textarea><div class="workspace-form-grid"><label class="field-label" for="autonomous-calls">최대 모델 호출 횟수<input id="autonomous-calls" name="max_model_calls" type="number" class="field" min="1" max="40" value="${e(draft.max_model_calls || 12)}" required></label><label class="field-label" for="autonomous-wall">전체 수행 한도 · 분<input id="autonomous-wall" name="wall_minutes" type="number" class="field" min="1" max="1440" value="${e(draft.wall_minutes || 60)}" required></label></div><p class="field-help">사용량 제한이나 로그인 만료, 실행 환경 오류가 발생하면 상태와 이유를 저장합니다. 예산과 조건을 확인한 뒤 재개하세요. 원고의 투고와 게재는 저자가 최종 검토합니다.</p>${formError()}<div class="inline-actions"><button class="button button-primary" type="submit" ${active ? "disabled" : ""}>${icon("spark")}자동 연구 시작</button></div></form>`;
}
function researchStage() {
  return `<h3 class="workspace-section-heading">무엇을 확인할 연구인가요?</h3><p class="workspace-section-intro">구체적인 연구 질문과 제목을 정하세요. 등록한 질문별로 실험과 문헌을 연결할 수 있습니다.</p>${
    records("study").length
      ? `<div class="record-list">${records("study")
          .map(
            (study) =>
              `<article class="record-card"><strong>${e(study.title)} ${badge(study.state)}</strong><p>${e(study.research_question)}</p><code>${e(study.id)}</code></article>`,
          )
          .join("")}</div>`
      : ""
  }<form data-form="research"><label class="field-label" for="research-title">연구 제목 <span class="required">*</span></label><input id="research-title" name="title" class="field" required maxlength="500" placeholder="연구를 설명하는 제목"><label class="field-label" for="research-question">연구 질문 <span class="required">*</span></label><textarea id="research-question" name="question" class="field" required placeholder="어떤 조건에서, 무엇을 비교하고, 어떤 지표로 확인할까요?"></textarea><label class="field-label" for="research-domain">연구 분야</label><select name="domain" id="research-domain" class="field"><option value="software_engineering">소프트웨어 공학</option><option value="generic_empirical">일반 경험적 연구</option></select>${formError()}<div class="inline-actions"><button type="submit" class="button button-primary">${icon("plus")}연구 질문 등록</button><button type="button" class="button button-secondary" data-action="inventory">기초 자료 조사로 시작</button></div><p class="field-help">기초 자료 조사는 프로젝트의 파일 수와 크기를 확인하는 설명적 조사입니다. 별도의 연구 질문과 실험으로 확장할 수 있습니다.</p></form>`;
}
function manifestTemplate() {
  const project = latest("project");
  const study = latest("study");
  return JSON.stringify(
    {
      study_id: study?.id || "연구 질문을 먼저 등록하세요",
      source_commit: project?.source_commit ?? null,
      source_digest: project?.snapshot_digest || "",
      command: ["{python}", "scripts/experiment.py"],
      inputs: [],
      expected_outputs: ["results/metrics.json"],
      metrics: [
        {
          name: "metric_name",
          output: "results/metrics.json",
          pointer: "/metric_name",
          unit: "",
          description: "이 지표가 측정하는 내용",
        },
      ],
      seed: 0,
      timeout_seconds: 120,
    },
    null,
    2,
  );
}
function experimentStage() {
  const manifests = records("manifest");
  const runs = records("run");
  return `<h3 class="workspace-section-heading">실험을 설계하고 수행하세요.</h3><p class="workspace-section-intro">가져온 프로젝트의 분석 스크립트와 측정 지표를 등록합니다. 실험 결과는 원본 근거와 함께 기록됩니다.</p>${!records("study").length ? empty("연구 질문을 먼저 등록하세요", "연구 설계 단계에서 질문을 등록한 뒤 실험을 연결할 수 있습니다.", '<button class="button button-secondary" data-stage="research">연구 설계로 이동</button>', "flask") : ""}${
    manifests.length
      ? `<form data-form="run"><label class="field-label" for="experiment-select">등록된 실험 계획</label><select name="experiment" id="experiment-select" class="field">${manifests
          .map(
            (manifest) =>
              `<option value="${e(manifest.id)}">${e(manifest.id)} · ${e(
                list(manifest.metrics)
                  .map((m) => m.name)
                  .join(", "),
              )}</option>`,
          )
          .join(
            "",
          )}</select><div class="inline-actions"><button type="submit" class="button button-primary">${icon("flask")}실험 수행</button></div></form>`
      : ""
  }${
    runs.length
      ? `<h4 class="field-label">실제 수행 결과</h4><div class="record-list">${runs
          .slice()
          .reverse()
          .map(
            (run) =>
              `<article class="record-card"><strong>${e(run.id)} ${badge(run.status === "SUCCEEDED" ? "succeeded" : run.status === "FAILED" ? "failed" : "running")}</strong><p>${e(
                Object.entries(run.metrics || {})
                  .map(([key, value]) => `${key}: ${number(value)}`)
                  .join(" · ") ||
                  run.error ||
                  "아직 측정 결과가 없습니다.",
              )}</p><code>${e(date(run.ended_at || run.started_at))}</code></article>`,
          )
          .join("")}</div>`
      : ""
  }<hr class="form-divider"><form data-form="register"><label class="field-label" for="manifest-json">새 실험 계획 · JSON</label><p class="field-help">아래는 작성용 예시입니다. 분석 스크립트 경로와 입력·출력·지표를 프로젝트에 맞게 수정하세요. 실행할 스크립트는 가져온 프로젝트에 포함되어 있어야 합니다.</p><textarea id="manifest-json" name="manifest" class="field json-field" spellcheck="false" required>${e(state.drafts[`${state.selectedProject}:manifest`] || manifestTemplate())}</textarea>${formError()}<div class="inline-actions"><button type="submit" class="button button-secondary" ${records("study").length ? "" : "disabled"}>실험 계획 등록</button></div></form>`;
}
function literatureStage() {
  const citations = records("citation");
  return `<h3 class="workspace-section-heading">연구를 기존 문헌과 연결하세요.</h3><p class="workspace-section-intro">Crossref에서 관련 문헌을 찾거나 DOI로 서지 정보를 확인합니다. 검색 결과와 원문 내용을 함께 검토해 연구의 맥락을 작성하세요.</p><form data-form="literature-search">${records("study").length ? studySelect("study", "literature-study") : ""}<label class="field-label" for="literature-query">검색어 <span class="required">*</span></label><input name="query" id="literature-query" class="field" required placeholder="연구 주제, 방법론, 또는 논문 제목"><div class="inline-actions"><button type="submit" class="button button-primary">${icon("search")}관련 문헌 검색</button><label class="small-label" for="literature-limit">검색 수</label><select name="limit" id="literature-limit" class="field field-count"><option value="5">5</option><option value="10">10</option><option value="20">20</option></select></div></form><hr class="form-divider"><form data-form="literature-doi"><label class="field-label" for="literature-doi">DOI로 문헌 추가</label><input name="doi" id="literature-doi" class="field" required placeholder="10.xxxx/identifier">${records("study").length ? studySelect("study", "doi-study") : ""}<div class="inline-actions"><button type="submit" class="button button-secondary">${icon("link")}DOI 확인 및 연결</button></div></form>${formError()}<h4 class="field-label">확인된 문헌 ${citations.length}</h4>${citations.length ? citations.map((citation) => `<article class="literature-result"><h4>${e(citation.title)}</h4><p>${e(list(citation.authors).join(", "))}${citation.year ? ` · ${e(citation.year)}` : ""}</p><p>${e(citation.doi)}</p><a href="https://doi.org/${e(encodeURIComponent(citation.doi).replace(/%2F/g, "/"))}" target="_blank" rel="noopener noreferrer">원문 확인 ↗</a><p>검증 범위: 서지 정보 · 원문 내용은 직접 검토하세요.</p></article>`).join("") : empty("확인된 문헌이 없습니다", "검색 또는 DOI 확인 결과가 이곳에 표시됩니다.", "", "book")}`;
}
function manuscriptStage() {
  const papers = records("paper");
  const files = list(state.projectDetail.files);
  return `<h3 class="workspace-section-heading">근거에서 원고를 완성하세요.</h3><p class="workspace-section-intro">실험 결과와 연결된 근거로 검토용 원고를 생성합니다. 본문을 편집한 뒤 파일을 다시 만들고 무결성을 검토하세요.</p><form data-form="manuscript-build">${records("study").length ? studySelect("study", "manuscript-study") : empty("연구 질문을 먼저 등록하세요", "실험 결과가 준비된 연구에서 원고를 만들 수 있습니다.", "", "article")}<details class="author-fields"><summary class="small-label">저자 정보 · 선택</summary><p class="field-help">제공한 정보만 원고에 반영됩니다. ORCID는 공개 연구자 식별자이며 이름·소속·이메일을 대신하지 않습니다.</p><div class="workspace-form-grid"><label class="field-label">표기 이름<input class="field" name="author_name" placeholder="논문에 표기할 성명"></label><label class="field-label">ORCID<input class="field" name="author_orcid" placeholder="0000-0000-0000-0000"></label><label class="field-label">소속<input class="field" name="author_affiliation" placeholder="소속 기관"></label><label class="field-label">공개 이메일<input class="field" name="author_email" type="email" placeholder="연락용 이메일"></label></div></details><label class="checkbox-field"><input name="pdf" type="checkbox" checked>PDF 파일 포함</label><div class="inline-actions"><button type="submit" class="button button-primary" ${records("study").length ? "" : "disabled"}>${icon("article")}검토용 원고 생성</button></div></form>${papers.length ? `<hr class="form-divider"><label class="field-label" for="paper-select">생성된 원고</label><select class="field" id="paper-select">${papers.map((paper) => `<option value="${e(paper.id)}" ${state.canonical?.paper_id === paper.id ? "selected" : ""}>${e(paper.title)} · ${e(statusLabels[paper.state] || paper.state)}</option>`).join("")}</select><div class="inline-actions"><button class="button button-secondary" data-action="edit-manuscript">원고 편집</button><button class="button button-secondary" data-action="render-manuscript">${icon("refresh")}파일 다시 만들기</button><button class="button button-secondary" data-action="check-integrity">${icon("shield")}무결성 검토</button></div><div id="manuscript-editor"></div><h4 class="field-label">원고 산출물</h4>${fileList(files.filter((file) => file.path.startsWith("manuscripts/")))}` : ""}${formError()}`;
}
function filesStage() {
  const files = list(state.projectDetail.files);
  const errors = list(state.projectDetail.file_errors);
  return `<h3 class="workspace-section-heading">근거와 산출물</h3><p class="workspace-section-intro">원고, 실험 계획, 결과 데이터와 검토 보고서를 내려받으세요. 파일은 실제 연구 작업에서 생성된 자료입니다.</p>${errors.length ? `<div class="form-error" role="status">일부 파일은 크기 제한 또는 접근 문제로 내려받을 수 없습니다.<ul>${errors.map(error => `<li>${e(error.path)}</li>`).join("")}</ul></div>` : ""}${files.length ? fileList(files) : empty("아직 생성된 산출물이 없습니다", "연구 질문을 정하고 실험을 수행하면 결과 자료가 나타납니다.", "", "folder")}`;
}
function renderProject() {
  const detail = state.projectDetail;
  if (!detail) return;
  collectCanonical();
  const focused = document.activeElement?.closest('[data-form="autonomous"], #canonical-form') ? {id: document.activeElement.id, start: document.activeElement.selectionStart, end: document.activeElement.selectionEnd} : null;
  document
    .querySelectorAll(".workflow-tabs [data-stage]")
    .forEach((button) =>
      button.classList.toggle("active", button.dataset.stage === state.stage),
    );
  let content;
  if (detail.status !== "ready") {
    content = `${empty(detail.status === "importing" ? "프로젝트를 가져오는 중입니다" : "프로젝트 가져오기를 완료하지 못했습니다", detail.error || (detail.status === "importing" ? "자료의 스냅샷을 준비하고 있습니다. 완료되면 연구 설계를 시작할 수 있습니다." : "작업 기록에서 실패 원인을 확인하고 새로 가져오세요."), "", "folder")}`;
  } else {
    const stages = {
      autonomous: autonomousStage,
      research: researchStage,
      experiment: experimentStage,
      literature: literatureStage,
      manuscript: manuscriptStage,
      files: filesStage,
    };
    content = stages[state.stage]();
  }
  $("#project-dialog-body").innerHTML =
    `${content}<div id="project-job"></div>`;
  if (detail.status !== "ready")
    document
      .querySelectorAll(".workflow-tabs [data-stage]")
      .forEach((button) => (button.disabled = true));
  else
    document
      .querySelectorAll(".workflow-tabs [data-stage]")
      .forEach((button) => (button.disabled = false));
  if (state.stage === "manuscript" && state.canonical && $("#manuscript-editor"))
    renderCanonical();
  decorate($("#project-dialog-body"));
  updateProjectJob();
  if (focused && document.getElementById(focused.id)) {
    const field = document.getElementById(focused.id);
    field.focus({preventScroll: true});
    if (field.tagName === "TEXTAREA" && Number.isInteger(focused.start)) field.setSelectionRange(focused.start, focused.end);
  }
}
function updateProjectJob() {
  if (!$("#project-dialog").open || !$("#project-job")) return;
  const job = state.jobs.find((j) => j.project_id === state.selectedProject);
  if (!job) {
    $("#project-job").innerHTML = "";
    return;
  }
  const active = ["queued", "running"].includes(job.status);
  $("#project-job").innerHTML =
    `<section class="project-job-panel"><div class="project-job-title"><strong>${e(actionLabels[job.action] || job.action)}</strong>${badge(job.status)}</div>${active ? "<p>작업을 수행하고 있습니다. 완료되면 실제 결과를 불러옵니다.</p>" : `<p>${job.status === "succeeded" ? "작업이 완료되어 결과가 연구 기록에 보존되었습니다." : job.status === "cancelled" ? "작업을 중단하고 진행 상태를 보존했습니다." : ["blocked", "paused"].includes(job.status) ? "진행 조건을 확인하고 저장된 단계부터 재개하세요." : "작업을 완료하지 못했습니다. 아래 원인과 수행 기록을 확인하세요."}</p>`}${job.error ? `<div class="form-error">${e(job.error)}</div>` : ""}${job.result && typeof job.result === "object" ? `<details><summary>결과 기록 보기</summary><pre class="code-preview">${e(JSON.stringify(job.result, null, 2))}</pre></details>` : ""}<details><summary>수행 기록 보기</summary><pre class="code-preview">${e(job.log || "추가 기록을 기다리고 있습니다.")}</pre></details></section>`;
  $("#project-dialog-body")
    .querySelectorAll(
      'button[type="submit"], [data-action="inventory"], [data-action="render-manuscript"], [data-action="check-integrity"]',
    )
    .forEach((button) => {
      if (active) {
        if (!button.disabled) button.dataset.jobDisabled = "true";
        button.disabled = true;
      } else if (button.dataset.jobDisabled) {
        button.disabled = false;
        delete button.dataset.jobDisabled;
      }
    });
}
function workspaceError(message) {
  let node = $("#workspace-error");
  if (!node) {
    node = document.createElement("div");
    node.id = "workspace-error";
    node.className = "form-error";
    node.setAttribute("role", "alert");
    $("#project-dialog-body").prepend(node);
  }
  node.textContent = message;
  node.hidden = false;
}
async function action(payload, button) {
  if (!state.selectedProject) return;
  if (button) button.disabled = true;
  if ($("#workspace-error")) $("#workspace-error").hidden = true;
  try {
    const data = await api(
      `/api/projects/${encodeURIComponent(state.selectedProject)}/actions`,
      { method: "POST", body: JSON.stringify(payload) },
    );
    state.jobs.unshift(data.job);
    updateProjectJob();
    render();
    toast(`${actionLabels[payload.action] || "연구 작업"}을 시작했습니다.`);
    return data;
  } catch (error) {
    workspaceError(error.message);
    return null;
  } finally {
    if (button) button.disabled = false;
    updateProjectJob();
  }
}
async function handleWorkspaceForm(form) {
  const kind = form.dataset.form;
  const values = new FormData(form);
  const payload = { action: kind };
  const button = form.querySelector('[type="submit"]');
  if (kind === "autonomous") {
    const draft = {goal: textValue(values.get("goal")).trim(), max_model_calls: Number(values.get("max_model_calls")), wall_minutes: Number(values.get("wall_minutes"))};
    state.drafts[`${state.selectedProject}:autonomous`] = draft;
    await pipelineRequest("", {goal: draft.goal, budget: {max_model_calls: draft.max_model_calls, wall_seconds: draft.wall_minutes * 60}}, button);
    return;
  } else if (kind === "research") {
    payload.title = textValue(values.get("title")).trim();
    payload.question = textValue(values.get("question")).trim();
    payload.domain = values.get("domain");
  } else if (kind === "register") {
    try {
      payload.manifest = JSON.parse(values.get("manifest"));
      if (
        !payload.manifest ||
        Array.isArray(payload.manifest) ||
        typeof payload.manifest !== "object"
      )
        throw new Error("실험 계획은 JSON 객체여야 합니다.");
      state.drafts[`${state.selectedProject}:manifest`] =
        values.get("manifest");
    } catch (error) {
      workspaceError(`실험 계획 JSON을 확인해 주세요. ${error.message}`);
      return;
    }
  } else if (kind === "run") {
    payload.experiment = values.get("experiment");
  } else if (kind === "literature-search") {
    payload.query = textValue(values.get("query")).trim();
    payload.limit = Number(values.get("limit"));
    if (values.get("study")) payload.study = values.get("study");
  } else if (kind === "literature-doi") {
    payload.doi = textValue(values.get("doi"))
      .trim()
      .replace(/^https?:\/\/(?:dx\.)?doi\.org\//, "");
    if (values.get("study")) payload.study = values.get("study");
  } else if (kind === "manuscript-build") {
    if (values.get("study")) payload.study = values.get("study");
    payload.pdf = values.get("pdf") === "on";
    const author = {
      display_name: textValue(values.get("author_name")).trim(),
      orcid: textValue(values.get("author_orcid")).trim(),
      affiliation: textValue(values.get("author_affiliation")).trim(),
      email: textValue(values.get("author_email")).trim(),
    };
    if (Object.values(author).some(Boolean)) payload.author = author;
  } else if (kind === "canonical") {
    await saveCanonical(form);
    return;
  }
  await action(payload, button);
}
async function pipelineRequest(suffix, payload, button) {
  if (!state.selectedProject) return;
  if (button) button.disabled = true;
  try {
    const result = await api(`/api/projects/${encodeURIComponent(state.selectedProject)}/pipelines${suffix}`, {method: "POST", body: JSON.stringify(payload)});
    if (result.job) state.jobs.unshift(result.job);
    await reloadProject();
    render();
    toast(suffix.endsWith("/cancel") ? "중단을 요청했습니다." : suffix.endsWith("/resume") ? "자동 연구를 재개했습니다." : "자동 연구를 시작했습니다.");
  } catch (error) {
    workspaceError(error.message);
  } finally {
    if (button) button.disabled = false;
    updateProjectJob();
  }
}
async function loadCanonical() {
  const paperId = $("#paper-select")?.value;
  if (!paperId) return;
  collectCanonical();
  if (state.canonical?.paper_id === paperId) {
    renderCanonical();
    return;
  }
  const file = list(state.projectDetail.files).find(
    (item) => item.path === `manuscripts/${paperId}/canonical.json`,
  );
  if (!file || !localURL(file.url)) {
    workspaceError(
      "편집할 원고 자료를 찾지 못했습니다. 원고 파일을 다시 생성하고 확인해 주세요.",
    );
    return;
  }
  const projectId = state.selectedProject;
  try {
    const canonical = await api(localURL(file.url));
    if (state.selectedProject !== projectId || state.stage !== "manuscript")
      return;
    state.canonical = canonical;
    renderCanonical();
  } catch (error) {
    workspaceError(error.message);
  }
}
function collectCanonical() {
  if (!state.canonical || !$("#canonical-form")) return;
  state.canonical.title = $("#canonical-title").value;
  state.canonical.limitations = $("#canonical-limitations")
    .value.split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  $("#canonical-form")
    .querySelectorAll("[data-section-heading]")
    .forEach((input) => {
      state.canonical.sections[Number(input.dataset.sectionHeading)].heading =
        input.value;
    });
  $("#canonical-form")
    .querySelectorAll("[data-prose-section]")
    .forEach((input) => {
      state.canonical.sections[Number(input.dataset.proseSection)].blocks[
        Number(input.dataset.proseBlock)
      ].text = input.value;
    });
}
function renderCanonical() {
  const doc = state.canonical;
  if (!doc || !$("#manuscript-editor")) return;
  $("#manuscript-editor").innerHTML =
    `<form id="canonical-form" data-form="canonical" class="manuscript-editor"><hr class="form-divider"><h4 class="workspace-section-heading">원고 편집</h4><p class="field-help">측정값과 인용은 연결된 근거를 유지합니다. 본문과 연구의 한계를 작성하고 저장한 뒤 원고 파일을 다시 생성하세요.</p><label class="field-label" for="canonical-title">논문 제목</label><input class="field" id="canonical-title" value="${e(doc.title)}" required>${list(
      doc.sections,
    )
      .map(
        (section, si) =>
          `<section class="record-card"><label class="field-label" for="section-${si}">절 제목</label><input class="field" id="section-${si}" value="${e(section.heading)}" data-section-heading="${si}" required>${list(
            section.blocks,
          )
            .map((block, bi) =>
              block.kind === "prose"
                ? `<label class="field-label" for="prose-${si}-${bi}">본문 문단</label><textarea class="field" id="prose-${si}-${bi}" data-prose-section="${si}" data-prose-block="${bi}" required>${e(block.text)}</textarea>`
                : `<p>${block.kind === "claim" ? "연결된 측정 근거" : "연결된 문헌"} <code>${e(block.ref)}</code></p>`,
            )
            .join(
              "",
            )}<button class="text-button" type="button" data-action="add-paragraph" data-index="${si}">+ 본문 문단 추가</button></section>`,
      )
      .join(
        "",
      )}<div class="inline-actions"><button class="button button-secondary button-small" type="button" data-action="add-section">+ 새 절 추가</button></div><label class="field-label" for="canonical-limitations">연구의 한계 · 항목별 줄바꿈</label><textarea class="field" id="canonical-limitations" required>${e(list(doc.limitations).join("\n"))}</textarea><div class="inline-actions"><button class="button button-primary" type="submit">원고 내용 저장</button><span class="small-label">저장 후 파일 다시 만들기 → 무결성 검토</span></div></form>`;
}
async function saveCanonical(form) {
  collectCanonical();
  const button = form.querySelector('[type="submit"]');
  button.disabled = true;
  try {
    await api(
      `/api/projects/${encodeURIComponent(state.selectedProject)}/manuscripts/${encodeURIComponent(state.canonical.paper_id)}/canonical`,
      { method: "PUT", body: JSON.stringify({ canonical: state.canonical }) },
    );
    toast("원고 내용을 저장했습니다. 파일을 다시 만들고 무결성을 검토하세요.");
  } catch (error) {
    workspaceError(error.message);
  } finally {
    button.disabled = false;
  }
}
document.addEventListener("click", async (event) => {
  const button = event.target.closest("button, a[data-view]");
  if (!button) return;
  if (button.dataset.view) {
    switchView(button.dataset.view);
    return;
  }
  if (button.dataset.closeDialog) {
    document.getElementById(button.dataset.closeDialog)?.close();
    return;
  }
  if (button.dataset.stage && state.projectDetail?.status === "ready") {
    if (state.stage === "autonomous" && $("#autonomous-goal")) {
      state.drafts[`${state.selectedProject}:autonomous`] = {goal: $("#autonomous-goal").value, max_model_calls: $("#autonomous-calls").value, wall_minutes: $("#autonomous-wall").value};
    }
    if (state.stage === "experiment" && $("#manifest-json"))
      state.drafts[`${state.selectedProject}:manifest`] =
        $("#manifest-json").value;
    state.stage = button.dataset.stage;
    renderProject();
    return;
  }
  if (button.dataset.reading) {
    document
      .querySelectorAll(".reading-tabs button")
      .forEach((tab) => tab.classList.toggle("active", tab === button));
    ["overview", "article", "data"].forEach((name) => {
      const node = document.getElementById(`paper-${name}`);
      if (node) node.hidden = name !== button.dataset.reading;
    });
    return;
  }
  const kind = button.dataset.action;
  if (kind === "connect-model") await changeModelConnection("login");
  else if (kind === "cancel-model-connection") await changeModelConnection("cancel");
  else if (kind === "probe-model") await changeModelConnection("probe");
  else if (kind === "disconnect-model") await changeModelConnection("disconnect");
  else if (kind === "new-project") openImport();
  else if (kind === "open-paper") await openPaper(button.dataset.id);
  else if (kind === "open-project") await openProject(button.dataset.id);
  else if (kind === "open-autonomous") await openProject(button.dataset.id, "autonomous");
  else if (kind === "cancel-pipeline") await pipelineRequest(`/${encodeURIComponent(button.dataset.id)}/cancel`, {}, button);
  else if (kind === "resume-pipeline") await pipelineRequest(`/${encodeURIComponent(button.dataset.id)}/resume`, {}, button);
  else if (kind === "import-recommended") await startRecommended([Number(button.dataset.index)], button);
  else if (kind === "import-all-recommended") await startRecommended(list(state.repositories?.repositories).map((_, index) => index), button);
  else if (kind === "toggle-job") {
    if (state.expandedJobs.has(button.dataset.id))
      state.expandedJobs.delete(button.dataset.id);
    else state.expandedJobs.add(button.dataset.id);
    render();
  } else if (kind === "inventory")
    await action(
      {
        action: "research",
        candidate: "asset-inventory",
        domain: "generic_empirical",
      },
      button,
    );
  else if (kind === "edit-manuscript") await loadCanonical();
  else if (kind === "render-manuscript")
    await action(
      {
        action: "manuscript-render",
        paper: $("#paper-select").value,
        pdf: true,
      },
      button,
    );
  else if (kind === "check-integrity")
    await action(
      { action: "integrity-check", paper: $("#paper-select").value },
      button,
    );
  else if (kind === "add-paragraph") {
    collectCanonical();
    state.canonical.sections[Number(button.dataset.index)].blocks.push({
      kind: "prose",
      text: "",
      ref: "",
    });
    renderCanonical();
  } else if (kind === "add-section") {
    collectCanonical();
    state.canonical.sections.push({
      heading: "",
      blocks: [{ kind: "prose", text: "", ref: "" }],
    });
    renderCanonical();
  }
});
document.addEventListener("submit", async (event) => {
  const form = event.target;
  if (form.id === "import-form") {
    event.preventDefault();
    await handleImport(form);
  } else if (form.dataset.form === "repositories") {
    event.preventDefault();
    await findRepositories(form);
  } else if (form.dataset.form) {
    event.preventDefault();
    await handleWorkspaceForm(form);
  }
});
$("#global-search").addEventListener("input", (event) => {
  state.search = event.target.value;
  render();
});
document.addEventListener("input", event => {
  if (event.target.closest('[data-form="autonomous"]')) {
    state.drafts[`${state.selectedProject}:autonomous`] = {goal: $("#autonomous-goal").value, max_model_calls: $("#autonomous-calls").value, wall_minutes: $("#autonomous-wall").value};
  }
  if (event.target.closest('[data-form="repositories"]')) state.repositoryDraft = {owner: $("#repository-owner").value, goal: $("#repository-goal").value};
});
$("#refresh-button").addEventListener("click", async () => {
  await refresh();
  if ($("#project-dialog").open) await reloadProject();
  toast("연구 자료를 새로 불러왔습니다.");
});
$("#project-dialog").addEventListener("close", () => {
  state.selectedProject = null;
  state.projectDetail = null;
  state.canonical = null;
});
$("#paper-dialog").addEventListener("close", () => {
  state.paper = null;
});
document.querySelectorAll("dialog").forEach((dialog) => {
  dialog.addEventListener("click", (event) => {
    if (event.target !== dialog) return;
    const rect = dialog.getBoundingClientRect();
    if (
      event.clientX < rect.left ||
      event.clientX > rect.right ||
      event.clientY < rect.top ||
      event.clientY > rect.bottom
    )
      dialog.close();
  });
});
decorate();
render();
refresh({ silent: true });
setInterval(() => {
  if (document.hidden) return;
  const active = state.jobs.some((job) =>
    ["queued", "running"].includes(job.status),
  ) || ["starting", "waiting_user", "probing"].includes(state.modelConnection?.status);
  if (Date.now() - lastRefresh > (active ? 2000 : 15000))
    refresh({ silent: true });
}, 2500);
