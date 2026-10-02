import { useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  Download,
  ExternalLink,
  FileText,
  GitBranch,
  Library,
  LoaderCircle,
  LogOut,
  Play,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  Square,
  X,
} from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "./components/ui/alert";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "./components/ui/dialog";
import { Input } from "./components/ui/input";
import { Progress, ProgressLabel } from "./components/ui/progress";
import { Textarea } from "./components/ui/textarea";
import type { Artifact, Candidate, Connection, DesktopBridge, Pipeline, Project } from "./model";
import {
  activeStatus,
  artifactKind,
  artifactRequestPath,
  connectionMessage,
  progress,
  readableSize,
  resumableStatus,
  shortRepository,
  stages,
  statusLabel,
  validRepository,
} from "./model";
import { useWorkspace } from "./use-workspace";
import license from "./vendor/neobrutal-ui.LICENSE?raw";

type View = "start" | "progress" | "library";
type Notice = { kind: "success" | "error"; title: string; message: string };
type LibraryEntry = { id: string; title: string; repository: string; files: Artifact[] };
const deviceUrl = "https://auth.openai.com/codex/device";

function actionError(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  if (/RESEARCH_BUSY|already active|active.*research/i.test(message))
    return "진행 중인 연구를 중지하고 종료를 확인한 뒤 다시 시도해 주세요.";
  if (/CONNECTION_BUSY|연결 작업|authentication.*progress/i.test(message))
    return "계정 연결 작업이 진행 중입니다. 작업이 끝난 뒤 다시 시도해 주세요.";
  if (/CLEANUP_UNCONFIRMED/i.test(message))
    return "작업자의 종료가 아직 확인되지 않았습니다. 계정을 유지한 채 진행 현황을 확인해 주세요.";
  if (/LOGOUT_TIMEOUT|LOGOUT_FAILED/i.test(message))
    return "로그아웃을 완료하지 못했습니다. 연결 상태를 다시 확인한 뒤 재시도해 주세요.";
  if (/MODEL_BUDGET|TIME_BUDGET|budget/i.test(message))
    return "설정한 연구 한도에 도달했습니다. 진행 현황의 중지 사유를 확인해 주세요.";
  if (/AUTH|login|로그인/i.test(message)) return "Codex 연결을 확인한 뒤 다시 시도해 주세요.";
  return "요청을 완료하지 못했습니다. 현재 상태를 새로고침한 뒤 다시 시도해 주세요.";
}

function interruptionMessage(run: Pipeline) {
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

export default function App({ api }: { api: DesktopBridge }) {
  const { snapshot, loading, loadError, version, refresh } = useWorkspace(api);
  const [view, setView] = useState<View>("start");
  const [pending, setPending] = useState("");
  const pendingRef = useRef(false);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [connectionOverride, setConnectionOverride] = useState<Connection | null>(null);
  const [logoutOpen, setLogoutOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);
  const [cancelTarget, setCancelTarget] = useState<{ project: Project; run: Pipeline } | null>(
    null,
  );
  const [repository, setRepository] = useState("");
  const [projectId, setProjectId] = useState("");
  const [goal, setGoal] = useState("");
  const [calls, setCalls] = useState(12);
  const [minutes, setMinutes] = useState(60);
  const [owner, setOwner] = useState("");
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [recommended, setRecommended] = useState(false);
  const [recommendationInfo, setRecommendationInfo] = useState<{
    considered: number;
    limitations: string[];
  }>({ considered: 0, limitations: [] });
  const [query, setQuery] = useState("");
  const connection = connectionOverride ?? snapshot.connection;
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
    snapshot.agent.provider?.ready === true;
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
  const runnerReady = snapshot.agent.runner?.ready === true;
  const toolsReady = snapshot.agent.tools?.git === true && snapshot.agent.tools?.pandoc === true;
  const runs = snapshot.projects.flatMap((project) =>
    (project.pipelines ?? []).map((run) => ({ project, run })),
  );
  const activeRuns = runs.filter(({ run }) => activeStatus(run.status));
  const researchBusy =
    activeRuns.length > 0 ||
    snapshot.jobs.some((job) => activeStatus(job.status)) ||
    runs.some(({ run }) => run.code === "CLEANUP_UNCONFIRMED");
  const readyProjects = snapshot.projects.filter((project) => project.status === "ready");
  const selectedProject = readyProjects.find((project) => project.id === projectId);
  const selectedBusy =
    projectId !== "" &&
    snapshot.jobs.some((job) => job.project_id === projectId && activeStatus(job.status));
  const canStart =
    modelReady && runnerReady && toolsReady && !loading && !loadError && !pending && !selectedBusy;
  const goalValid = goal.trim().length >= 8 && goal.trim().length <= 4000;
  const budgetValid =
    Number.isInteger(calls) &&
    calls >= 1 &&
    calls <= 40 &&
    Number.isInteger(minutes) &&
    minutes >= 1 &&
    minutes <= 1440;
  const sourceValid = projectId ? Boolean(selectedProject) : validRepository(repository);

  async function action(key: string, task: () => Promise<void>) {
    if (pendingRef.current) return;
    pendingRef.current = true;
    setPending(key);
    setNotice(null);
    try {
      await task();
    } catch (error) {
      setNotice({
        kind: "error",
        title: "작업을 완료하지 못했습니다",
        message: actionError(error),
      });
    } finally {
      await refresh(true);
      setConnectionOverride(null);
      pendingRef.current = false;
      setPending("");
    }
  }

  function connect(operation: "login" | "probe" | "cancel") {
    void action(`auth-${operation}`, async () => {
      const result = await api.request<Connection>(
        "POST",
        `/api/agent/connection/${operation}`,
        {},
      );
      if (
        result.code === "RESEARCH_BUSY" ||
        result.code === "CONNECTION_BUSY" ||
        ["blocked", "failed"].includes(result.status)
      )
        throw new Error(result.code ?? result.status);
      setConnectionOverride(result);
      if (operation === "probe")
        setNotice({
          kind: "success",
          title: "연결 확인을 시작했습니다",
          message: "공식 로그인과 실제 모델 사용 가능 여부를 확인합니다.",
        });
    });
  }

  async function startStudy(event: FormEvent) {
    event.preventDefault();
    if (!canStart || !goalValid || !sourceValid || !budgetValid) return;
    void action("start", async () => {
      const study = {
        goal: goal.trim(),
        budget: { max_model_calls: calls, wall_seconds: minutes * 60 },
      };
      if (selectedProject)
        await api.request(
          "POST",
          `/api/projects/${encodeURIComponent(selectedProject.id)}/pipelines`,
          study,
        );
      else
        await api.request("POST", "/api/projects", {
          source: repository.trim(),
          autonomous: study,
        });
      setView("progress");
      setNotice({
        kind: "success",
        title: "연구를 요청했습니다",
        message: selectedProject
          ? "현재 상태는 진행 현황에서 확인할 수 있습니다."
          : "저장소를 가져온 뒤 연구가 자동으로 시작됩니다.",
      });
    });
  }

  function recommend(event: FormEvent) {
    event.preventDefault();
    if (!/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/.test(owner.trim()) || pending) return;
    void action("recommend", async () => {
      const response = await api.request<{
        repositories: Candidate[];
        considered: number;
        limitations: string[];
      }>("POST", "/api/agent/repositories", { owner: owner.trim(), count: 3 });
      setCandidates(response.repositories.filter((candidate) => validRepository(candidate.url)));
      setRecommendationInfo({
        considered: response.considered,
        limitations: response.limitations ?? [],
      });
      setRecommended(true);
    });
  }

  function fileAction(file: Artifact, operation: "open" | "save") {
    const path = artifactRequestPath(file);
    if (!path) return;
    void action(`file-${operation}-${path}`, async () => {
      if (operation === "open") await api.openArtifact(path);
      else {
        const result = await api.saveArtifact(path);
        if (!result.canceled)
          setNotice({
            kind: "success",
            title: "파일을 저장했습니다",
            message: "선택한 폴더에서 확인할 수 있습니다.",
          });
      }
    });
  }

  const library: LibraryEntry[] = [
    ...runs
      .filter(({ run }) => run.status === "completed")
      .map(({ project, run }) => ({
        id: run.id,
        title: run.goal,
        repository: shortRepository(project.source),
        files: run.files ?? [],
      })),
    ...snapshot.studies.map((study) => ({
      id: `catalog-${study.slug}`,
      title: study.title_ko ?? study.title ?? study.slug,
      repository:
        typeof study.repository === "string"
          ? shortRepository(study.repository)
          : (study.repository?.name ?? "보관된 연구"),
      files: [
        ...(study.files ?? []),
        ...(study.bundle_url && !(study.files ?? []).some((file) => file.url === study.bundle_url)
          ? [{ name: "reproducibility.zip", url: study.bundle_url }]
          : []),
      ],
    })),
  ];
  const filteredLibrary = library.filter((entry) =>
    `${entry.title} ${entry.repository}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()),
  );

  return (
    <div className="app-shell">
      <aside className="sidebar" aria-label="주 메뉴">
        <div className="brand">
          <span className="brand-icon">
            <FileText size={27} strokeWidth={2.5} />
          </span>
          <div>
            Paper
            <br />
            Factory<span className="brand-caption">내 컴퓨터의 연구 작업실</span>
          </div>
        </div>
        <nav>
          {(
            [
              ["start", Sparkles, "자동 연구"],
              ["progress", Play, "진행 현황"],
              ["library", Library, "논문 보관함"],
            ] as const
          ).map(([key, Icon, label]) => (
            <button
              key={key}
              type="button"
              className={`nav-item ${view === key ? "active" : ""}`}
              aria-label={label}
              aria-current={view === key ? "page" : undefined}
              onClick={() => setView(key)}
            >
              <Icon size={20} />
              {label}
              {key === "progress" && activeRuns.length > 0 && (
                <span className="nav-count">{activeRuns.length}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-note">
            <ShieldCheck size={21} />
            <strong>별도 회원가입 없이</strong>
            <p>공식 OpenAI 로그인으로 연결합니다. 연구 자료는 이 컴퓨터에 보관됩니다.</p>
          </div>
          <button className="text-button" onClick={() => setAboutOpen(true)}>
            앱 정보{version ? ` · v${version}` : ""}
          </button>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <span className="workspace-label">MY RESEARCH WORKSPACE</span>
          <div className="topbar-actions">
            <span className={`connection-dot ${modelReady ? "ready" : ""}`} />
            <span>
              {loading ? "작업실 준비 중" : modelReady ? "Codex 연결됨" : "Codex 연결 필요"}
            </span>
            <Button
              variant="neutral"
              size="icon-sm"
              aria-label="상태 새로고침"
              disabled={Boolean(pending) || loading}
              onClick={() => void refresh()}
            >
              <RefreshCw size={17} />
            </Button>
          </div>
        </header>
        <main>
          {notice && (
            <Alert
              variant={notice.kind === "error" ? "destructive" : "default"}
              className={`notice ${notice.kind}`}
              role={notice.kind === "error" ? "alert" : "status"}
            >
              <CheckCircle2 />
              <AlertTitle>{notice.title}</AlertTitle>
              <AlertDescription>{notice.message}</AlertDescription>
            </Alert>
          )}
          {loadError && (
            <Alert variant="destructive" className="notice">
              <AlertTitle>일부 상태를 확인할 수 없습니다</AlertTitle>
              <AlertDescription>{loadError}</AlertDescription>
            </Alert>
          )}
          {view === "start" && (
            <>
              <div className="page-heading">
                <Badge className="eyebrow">FROM CODE TO PAPER</Badge>
                <h1>
                  코드가 논문이 되는
                  <br />
                  <span className="highlight">연구 작업실.</span>
                </h1>
                <p>저장소와 연구 목표를 정하면, 설계부터 원고 생성까지 이어갑니다.</p>
              </div>
              <div className="start-grid">
                <section aria-label="연구 시작">
                  <Card className="study-card">
                    <CardHeader>
                      <CardTitle className="section-title">
                        <span className="number-chip">01</span>어떤 프로젝트를 연구할까요?
                      </CardTitle>
                      <CardDescription>
                        GitHub 저장소 주소와 궁금한 점을 입력해 주세요.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={(event) => void startStudy(event)} className="study-form">
                        {readyProjects.length > 0 && (
                          <label>
                            프로젝트 선택
                            <select
                              value={projectId}
                              onChange={(event) => setProjectId(event.target.value)}
                              disabled={Boolean(pending)}
                            >
                              <option value="">새 GitHub 저장소 가져오기</option>
                              {readyProjects.map((project) => (
                                <option key={project.id} value={project.id}>
                                  {project.name}
                                </option>
                              ))}
                            </select>
                          </label>
                        )}
                        {!projectId && (
                          <label htmlFor="repository">
                            GitHub 저장소
                            <Input
                              aria-label="GitHub 저장소"
                              id="repository"
                              value={repository}
                              onChange={(event) => setRepository(event.target.value)}
                              placeholder="https://github.com/owner/repository"
                              autoComplete="off"
                              spellCheck={false}
                              type="url"
                              required
                              disabled={Boolean(pending)}
                              aria-describedby="repository-help"
                            />
                            <span id="repository-help" className="field-help">
                              공개 저장소 주소를 입력하세요. 접근할 수 없는 저장소는 가져오기에
                              실패할 수 있습니다.
                            </span>
                          </label>
                        )}
                        <label htmlFor="goal">
                          연구 목표
                          <Textarea
                            aria-label="연구 목표"
                            id="goal"
                            value={goal}
                            onChange={(event) => setGoal(event.target.value)}
                            placeholder="예: 캐시 적용 전후의 응답 시간과 메모리 사용량을 비교하고 싶어요."
                            minLength={8}
                            maxLength={4000}
                            required
                            disabled={Boolean(pending)}
                            rows={4}
                          />
                          <span className="field-help">
                            비교하고 싶은 동작, 성능, 가설을 구체적으로 적어 주세요. 최소 8자.
                          </span>
                        </label>
                        <fieldset className="budget-fields" disabled={Boolean(pending)}>
                          <legend>연구 한도</legend>
                          <label htmlFor="calls">
                            모델 호출
                            <Input
                              aria-label="모델 호출"
                              id="calls"
                              type="number"
                              min={1}
                              max={40}
                              step={1}
                              required
                              value={Number.isNaN(calls) ? "" : calls}
                              onChange={(event) => setCalls(event.target.valueAsNumber)}
                            />
                            <span className="field-help">최대 40회</span>
                          </label>
                          <label htmlFor="minutes">
                            작업 시간 (분)
                            <Input
                              aria-label="작업 시간 (분)"
                              id="minutes"
                              type="number"
                              min={1}
                              max={1440}
                              step={1}
                              required
                              value={Number.isNaN(minutes) ? "" : minutes}
                              onChange={(event) => setMinutes(event.target.valueAsNumber)}
                            />
                            <span className="field-help">시간이 끝나면 중지</span>
                          </label>
                        </fieldset>
                        <p className="form-note">
                          한도 안에서 연구를 시도합니다. 결과와 논문 생성이 보장되지는 않으며,
                          완성된 원고는 직접 검토해야 합니다.
                        </p>
                        {!loading && !modelReady && (
                          <p className="readiness-note">
                            먼저 Codex를 연결하고 모델 사용 가능 여부를 확인해 주세요.
                          </p>
                        )}
                        {!loading && !runnerReady && (
                          <p className="readiness-note">
                            실험 실행 환경이 준비되지 않았습니다. 앱을 다시 시작해 상태를 확인해
                            주세요.
                          </p>
                        )}
                        {!loading && snapshot.agent.tools?.git === false && (
                          <p className="readiness-note">
                            Git을 찾지 못했습니다. Git 설치 후 앱을 다시 열어 주세요.
                          </p>
                        )}
                        {!loading && snapshot.agent.tools?.pandoc === false && (
                          <p className="readiness-note">
                            문서 변환 도구를 준비하지 못했습니다. 앱을 다시 시작해 주세요.
                          </p>
                        )}
                        {selectedBusy && (
                          <p className="readiness-note">
                            이 프로젝트에 진행 중인 작업이 있습니다. 종료 후 새 연구를 시작할 수
                            있습니다.
                          </p>
                        )}
                        <Button
                          type="submit"
                          size="lg"
                          className="start-button"
                          disabled={!canStart || !goalValid || !sourceValid || !budgetValid}
                        >
                          {pending === "start" ? (
                            <LoaderCircle className="spinner" />
                          ) : (
                            <Play size={18} />
                          )}
                          연구 시작하기
                          <ArrowRight size={18} />
                        </Button>
                      </form>
                    </CardContent>
                  </Card>
                </section>
                <div className="start-side">
                  <Card className="account-card">
                    <CardHeader>
                      <CardTitle className="section-title">
                        <span className="number-chip mint">✓</span>Codex 연결
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      <Badge variant="neutral" className={modelReady ? "ready-badge" : ""}>
                        {modelReady ? "사용 준비 완료" : authBusy ? "연결 진행 중" : "연결 필요"}
                      </Badge>
                      <p className="account-description">
                        {connectionMessage(connection, snapshot.agent)}
                      </p>
                      {connection.status === "waiting_user" && (
                        <div className="device-box">
                          <span>일회용 로그인 코드</span>
                          <strong>
                            {connection.user_code &&
                            /^[A-Za-z0-9-]{1,32}$/.test(connection.user_code)
                              ? connection.user_code
                              : "코드 준비 중"}
                          </strong>
                          <Button
                            className="full-width"
                            disabled={Boolean(pending) || connection.verification_url !== deviceUrl}
                            onClick={() =>
                              void action("device-page", () => api.openExternal(deviceUrl))
                            }
                          >
                            공식 로그인 페이지 열기
                            <ExternalLink size={15} />
                          </Button>
                          <p>OpenAI 페이지에서만 로그인 정보를 입력하세요.</p>
                        </div>
                      )}
                      {canProbe && (
                        <p className="field-help">
                          연결 확인은 실제 모델을 1회 호출하며 구독 사용량에 반영됩니다.
                        </p>
                      )}
                      <div className="account-actions">
                        {canProbe ? (
                          <Button
                            variant="neutral"
                            disabled={Boolean(pending) || researchBusy}
                            onClick={() => connect("probe")}
                          >
                            {modelReady ? "연결 다시 확인 (1회 호출)" : "연결 확인 (1회 호출)"}
                          </Button>
                        ) : (
                          !authBusy && (
                            <Button
                              className="full-width"
                              disabled={Boolean(pending) || loading || researchBusy}
                              onClick={() => connect("login")}
                            >
                              <ExternalLink size={16} />
                              Codex 연결하기
                            </Button>
                          )
                        )}
                        {authBusy && connection.status !== "logging_out" && (
                          <Button
                            variant="neutral"
                            disabled={Boolean(pending)}
                            onClick={() => connect("cancel")}
                          >
                            연결 취소
                          </Button>
                        )}
                        {canLogout && (
                          <Button
                            variant="ghost"
                            className="logout-button"
                            disabled={Boolean(pending) || authBusy}
                            onClick={() => setLogoutOpen(true)}
                          >
                            <LogOut size={15} />
                            {logoutRetry ? "로그아웃 다시 시도" : "로그아웃"}
                          </Button>
                        )}
                      </div>
                      {researchBusy && (
                        <p className="field-help">
                          계정 변경은 진행 중인 연구가 종료된 뒤 가능합니다.
                        </p>
                      )}
                    </CardContent>
                  </Card>
                  <Card className="recommend-card">
                    <CardHeader>
                      <CardTitle className="section-title">
                        <GitBranch size={22} />
                        저장소가 고민된다면
                      </CardTitle>
                      <CardDescription>
                        GitHub 공개 저장소의 정보와 파일을 확인합니다. 네트워크를 사용하며 모델은
                        호출하지 않습니다.
                      </CardDescription>
                    </CardHeader>
                    <CardContent>
                      <form onSubmit={recommend} className="recommend-form">
                        <label htmlFor="owner" className="sr-only">
                          GitHub 사용자 이름
                        </label>
                        <Input
                          id="owner"
                          value={owner}
                          onChange={(event) => setOwner(event.target.value)}
                          placeholder="GitHub 사용자 이름"
                          disabled={Boolean(pending)}
                        />
                        <Button
                          type="submit"
                          variant="neutral"
                          disabled={
                            Boolean(pending) ||
                            !/^[A-Za-z0-9][A-Za-z0-9-]{0,38}$/.test(owner.trim())
                          }
                          aria-label="연구할 저장소 추천 받기"
                        >
                          {pending === "recommend" ? (
                            <LoaderCircle className="spinner" />
                          ) : (
                            <Search size={18} />
                          )}
                        </Button>
                      </form>
                      {candidates.map((candidate) => (
                        <div className="candidate" key={candidate.url}>
                          <strong>{candidate.name}</strong>
                          <p>{candidate.reason}</p>
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={Boolean(pending)}
                            onClick={() => {
                              setRepository(candidate.url);
                              setProjectId("");
                            }}
                          >
                            이 저장소 선택
                            <ArrowRight size={14} />
                          </Button>
                        </div>
                      ))}
                      {recommended && (
                        <div className="recommendation-details">
                          <p>확인한 공개 저장소: {recommendationInfo.considered ?? 0}개</p>
                          <p>
                            후보 추천은 연구 가능성을 추정합니다. 새 발견, 실행 성공, 라이선스
                            허가를 보장하지 않습니다.
                          </p>
                          {recommendationInfo.limitations.length > 0 && (
                            <details>
                              <summary>확인 범위와 제한 보기</summary>
                              <ul>
                                {recommendationInfo.limitations.map((limitation) => (
                                  <li key={limitation}>{limitation}</li>
                                ))}
                              </ul>
                            </details>
                          )}
                        </div>
                      )}
                      {recommended && candidates.length === 0 && (
                        <p className="field-help">
                          사용 가능한 후보를 찾지 못했습니다. 저장소 주소를 직접 입력해 주세요.
                        </p>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </div>
            </>
          )}
          {view === "progress" && (
            <>
              <div className="page-heading compact">
                <Badge className="eyebrow">RESEARCH IN MOTION</Badge>
                <h1>
                  진행 현황<span className="heading-dot">.</span>
                </h1>
                <p>완료한 단계와 사용한 한도를 확인하세요. 연구 기록은 중지 후에도 남습니다.</p>
              </div>
              {loading && <Loading />}
              {snapshot.projects
                .filter(
                  (project) =>
                    project.status === "importing" ||
                    project.status === "failed" ||
                    project.autonomous_error,
                )
                .map((project) => (
                  <Card key={`import-${project.id}`} className="import-card">
                    <CardContent>
                      <div className="row">
                        <GitBranch />
                        <strong>{project.name}</strong>
                        <Badge variant="neutral">{statusLabel(project.status)}</Badge>
                      </div>
                      <p>
                        {project.status === "importing"
                          ? "저장소를 가져오고 있습니다. 준비되면 요청한 연구를 자동으로 시작합니다."
                          : project.autonomous_error
                            ? "저장소는 준비됐지만 연구를 시작하지 못했습니다. 연결 상태를 확인하고 자동 연구 화면에서 이 프로젝트를 선택하세요."
                            : "저장소를 가져오지 못했습니다. 주소와 접근 권한을 확인한 뒤 새로 가져와 주세요."}
                      </p>
                    </CardContent>
                  </Card>
                ))}
              {!loading &&
                runs.length === 0 &&
                snapshot.projects.every((project) => project.status !== "importing") && (
                  <Empty
                    icon="progress"
                    title="아직 시작한 연구가 없습니다"
                    description="GitHub 저장소와 연구 목표를 입력해 첫 연구를 시작하세요."
                    onStart={() => setView("start")}
                  />
                )}
              <div className="run-list">
                {runs.map(({ project, run }) => {
                  const completion = progress(run);
                  const current =
                    stages.find(([key]) => key === run.stage)?.[1] ??
                    (run.stage === "done" ? "최종 확인 완료" : "작업 준비");
                  return (
                    <Card key={run.id} className="run-card">
                      <CardHeader>
                        <div className="run-topline">
                          <span className="repo-label">
                            <GitBranch size={16} />
                            {shortRepository(project.source)}
                          </span>
                          <Badge
                            className={run.status === "completed" ? "ready-badge" : ""}
                            variant="neutral"
                          >
                            {run.cancellation_requested && activeStatus(run.status)
                              ? "중지 요청 · 정리 중"
                              : statusLabel(run.status)}
                          </Badge>
                        </div>
                        <CardTitle className="run-goal">{run.goal}</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <Progress value={completion.percent}>
                          <ProgressLabel>
                            완료한 단계 {completion.completed} / {stages.length}
                          </ProgressLabel>
                          <span className="progress-current">{current}</span>
                        </Progress>
                        <ol className="stage-list">
                          {stages.map(([key, label], index) => (
                            <li
                              key={key}
                              className={
                                completion.finished.has(key)
                                  ? "done"
                                  : run.stage === key && activeStatus(run.status)
                                    ? "current"
                                    : ""
                              }
                            >
                              <span>
                                {completion.finished.has(key) ? <Check size={12} /> : index + 1}
                              </span>
                              {label}
                            </li>
                          ))}
                        </ol>
                        <div className="run-footer">
                          <div className="run-budget">
                            <span>
                              모델 호출{" "}
                              <strong>
                                {run.model_calls ?? 0} / {run.budget?.max_model_calls ?? "—"}회
                              </strong>
                            </span>
                            <span>
                              사용 시간{" "}
                              <strong>
                                {Math.floor((run.elapsed_seconds ?? 0) / 60)} /{" "}
                                {run.budget?.wall_seconds
                                  ? Math.floor(run.budget.wall_seconds / 60)
                                  : "—"}
                                분
                              </strong>
                            </span>
                          </div>
                          <div className="run-actions">
                            {activeStatus(run.status) && (
                              <Button
                                variant="neutral"
                                size="sm"
                                disabled={Boolean(pending) || run.cancellation_requested}
                                onClick={() => setCancelTarget({ project, run })}
                              >
                                <Square size={13} />
                                {run.cancellation_requested ? "종료 확인 중" : "연구 중지"}
                              </Button>
                            )}
                            {resumableStatus(run.status) && (
                              <Button
                                size="sm"
                                disabled={
                                  Boolean(pending) ||
                                  !modelReady ||
                                  !runnerReady ||
                                  !toolsReady ||
                                  Boolean(loadError) ||
                                  researchBusy
                                }
                                onClick={() =>
                                  void action(`resume-${run.id}`, async () => {
                                    await api.request(
                                      "POST",
                                      `/api/projects/${encodeURIComponent(project.id)}/pipelines/${encodeURIComponent(run.id)}/resume`,
                                      {},
                                    );
                                  })
                                }
                              >
                                <Play size={13} />
                                이어서 진행
                              </Button>
                            )}
                            {run.status === "completed" && (
                              <Button size="sm" onClick={() => setView("library")}>
                                <BookOpen size={14} />
                                결과 확인
                              </Button>
                            )}
                          </div>
                        </div>
                        {resumableStatus(run.status) && (
                          <div className="run-warning">
                            <p>{interruptionMessage(run)}</p>
                            {run.code && <span>상태 코드: {run.code}</span>}
                          </div>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
            </>
          )}
          {view === "library" && (
            <>
              <div className="page-heading compact">
                <Badge className="eyebrow">YOUR PAPER COLLECTION</Badge>
                <h1>
                  논문 보관함<span className="heading-dot">.</span>
                </h1>
                <p>검토용 원고와 실험을 확인할 재현 자료를 열거나 저장하세요.</p>
              </div>
              <div className="library-toolbar">
                <label className="library-search">
                  <Search size={18} />
                  <Input
                    aria-label="논문 검색"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="연구 목표 또는 저장소로 검색"
                  />
                </label>
                <span>{filteredLibrary.length}개의 연구</span>
              </div>
              {loading && <Loading />}
              {!loading && filteredLibrary.length === 0 && (
                <Empty
                  icon="library"
                  title={query ? "검색 결과가 없습니다" : "첫 논문이 놓일 자리입니다"}
                  description={
                    query
                      ? "검색어를 바꾸어 다시 확인해 주세요."
                      : "연구의 최종 확인이 끝나면 원고와 재현 자료가 여기에 나타납니다."
                  }
                  onStart={query ? undefined : () => setView("start")}
                />
              )}
              <div className="library-grid">
                {filteredLibrary.map((entry, index) => {
                  const files = entry.files.filter(
                    (file) => artifactKind(file) && artifactRequestPath(file),
                  );
                  return (
                    <Card key={entry.id} className="paper-card">
                      <CardHeader>
                        <div className="paper-topline">
                          <span className="paper-number">
                            PAPER {String(index + 1).padStart(2, "0")}
                          </span>
                          <Badge variant="neutral">검토용 원고</Badge>
                        </div>
                        <CardTitle className="paper-title">{entry.title}</CardTitle>
                        <CardDescription className="repo-label">
                          <GitBranch size={15} />
                          {entry.repository}
                        </CardDescription>
                      </CardHeader>
                      <CardContent>
                        {files.length > 0 ? (
                          <div className="artifact-list">
                            {files.map((file) => (
                              <div key={file.url} className="artifact-row">
                                <div>
                                  <strong>{artifactKind(file)}</strong>
                                  <span>{readableSize(file.size)}</span>
                                </div>
                                <div>
                                  {!file.url.endsWith("/bundle") &&
                                    artifactKind(file) !== "전체 재현 자료" && (
                                      <Button
                                        variant="neutral"
                                        size="icon-sm"
                                        aria-label={`${artifactKind(file)} 열기`}
                                        disabled={Boolean(pending)}
                                        onClick={() => fileAction(file, "open")}
                                      >
                                        <ExternalLink size={15} />
                                      </Button>
                                    )}
                                  <Button
                                    variant="neutral"
                                    size="icon-sm"
                                    aria-label={`${artifactKind(file)} 저장`}
                                    disabled={Boolean(pending)}
                                    onClick={() => fileAction(file, "save")}
                                  >
                                    <Download size={16} />
                                  </Button>
                                </div>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <p className="field-help">
                            준비된 파일을 읽을 수 없습니다. 상태를 새로고침한 뒤 다시 확인해 주세요.
                          </p>
                        )}
                      </CardContent>
                    </Card>
                  );
                })}
              </div>
              <p className="library-note">
                자동 생성 원고에는 오류가 남을 수 있습니다. 인용, 결과, 저자 정보는 제출하거나
                공유하기 전에 직접 검토하세요.
              </p>
            </>
          )}
        </main>
      </div>
      <Dialog open={logoutOpen} onOpenChange={setLogoutOpen}>
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>Codex에서 로그아웃할까요?</DialogTitle>
            <DialogDescription>
              이 앱 전용 로그인에서 로그아웃합니다. 논문과 연구 기록은 보관됩니다.
            </DialogDescription>
          </DialogHeader>
          {researchBusy && (
            <Alert variant="destructive">
              <AlertTitle>진행 중인 연구를 먼저 종료해 주세요</AlertTitle>
              <AlertDescription>
                연구를 중지한 뒤 작업자의 종료가 확인되어야 계정에서 로그아웃할 수 있습니다.
              </AlertDescription>
            </Alert>
          )}
          <DialogFooter>
            <Button
              variant="neutral"
              disabled={Boolean(pending)}
              onClick={() => setLogoutOpen(false)}
            >
              돌아가기
            </Button>
            {researchBusy ? (
              <Button
                onClick={() => {
                  setLogoutOpen(false);
                  setView("progress");
                }}
              >
                진행 현황 보기
              </Button>
            ) : (
              <Button
                variant="destructive"
                disabled={Boolean(pending) || loading || Boolean(loadError)}
                onClick={() =>
                  void action("logout", async () => {
                    const result = await api.request<Connection>(
                      "POST",
                      "/api/agent/connection/logout",
                      {},
                    );
                    if (result.status !== "logged_out")
                      throw new Error(result.code ?? "LOGOUT_FAILED");
                    setConnectionOverride(result);
                    setLogoutOpen(false);
                    setNotice({
                      kind: "success",
                      title: "로그아웃했습니다",
                      message: "다시 연결하기 전에는 새 연구를 시작하지 않습니다.",
                    });
                  })
                }
              >
                {pending === "logout" && <LoaderCircle className="spinner" />}로그아웃
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog
        open={Boolean(cancelTarget)}
        onOpenChange={(open) => {
          if (!open && !pending) setCancelTarget(null);
        }}
      >
        <DialogContent showCloseButton={false}>
          <DialogHeader>
            <DialogTitle>이 연구를 중지할까요?</DialogTitle>
            <DialogDescription>
              실행 중인 작업에 중지를 요청합니다. 종료가 확인될 때까지 기다려 주세요. 완료한 자료는
              유지됩니다.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="neutral"
              disabled={Boolean(pending)}
              onClick={() => setCancelTarget(null)}
            >
              계속 연구하기
            </Button>
            <Button
              variant="destructive"
              disabled={Boolean(pending)}
              onClick={() => {
                const target = cancelTarget;
                if (target)
                  void action(`cancel-${target.run.id}`, async () => {
                    await api.request(
                      "POST",
                      `/api/projects/${encodeURIComponent(target.project.id)}/pipelines/${encodeURIComponent(target.run.id)}/cancel`,
                      {},
                    );
                    setCancelTarget(null);
                    setNotice({
                      kind: "success",
                      title: "중지를 요청했습니다",
                      message: "작업자가 종료될 때까지 진행 현황에서 상태를 확인해 주세요.",
                    });
                  });
              }}
            >
              <Square size={14} />
              중지 요청
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <Dialog open={aboutOpen} onOpenChange={setAboutOpen}>
        <DialogContent showCloseButton={false} className="about-dialog">
          <DialogHeader>
            <DialogTitle>Paper Factory{version ? ` ${version}` : ""}</DialogTitle>
            <DialogDescription>
              이 컴퓨터에서 코드 기반 연구와 논문 작성을 돕는 작업실입니다.
            </DialogDescription>
          </DialogHeader>
          <p className="field-help">
            화면 컴포넌트: neobrutal-ui · MIT License
            <br />
            https://github.com/andongmin94/neobrutal-ui
          </p>
          <details>
            <summary>neobrutal-ui 라이선스 보기</summary>
            <pre className="license-text">{license}</pre>
          </details>
          <DialogFooter>
            <Button variant="neutral" onClick={() => setAboutOpen(false)}>
              <X size={14} />
              닫기
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Empty({
  icon,
  title,
  description,
  onStart,
}: {
  icon: "progress" | "library";
  title: string;
  description: string;
  onStart?: () => void;
}) {
  const Icon = icon === "library" ? BookOpen : Sparkles;
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon size={38} />
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      {onStart && (
        <Button onClick={onStart}>
          첫 연구 시작하기
          <ArrowRight size={16} />
        </Button>
      )}
    </div>
  );
}
function Loading() {
  return (
    <p className="loading-state" role="status">
      <LoaderCircle className="spinner" size={20} />
      작업실의 기록을 불러오고 있습니다.
    </p>
  );
}
