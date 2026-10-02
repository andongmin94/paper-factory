import { useRef, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  CheckCircle2,
  FileText,
  GitBranch,
  Library,
  LoaderCircle,
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
import { Textarea } from "./components/ui/textarea";
import type { Artifact, Candidate, Connection, DesktopBridge, Pipeline, Project } from "./model";
import { activeStatus, artifactRequestPath, connectionReadiness, validRepository } from "./model";
import { ConnectionCard } from "./components/connection-card";
import { CODEX_DEVICE_URL } from "@shared/api";
import { useWorkspace } from "./use-workspace";
import { LibraryView } from "./views/library-view";
import { ProgressView } from "./views/progress-view";
import license from "./vendor/neobrutal-ui.LICENSE?raw";
import fontLicense from "./assets/fonts/OFL.txt?raw";

type View = "start" | "progress" | "library";
type Notice = { kind: "success" | "error"; title: string; message: string };

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
  const { modelReady } = connectionReadiness(connection, snapshot.agent);
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
                  <ConnectionCard
                    connection={connection}
                    agent={snapshot.agent}
                    loading={loading}
                    pending={Boolean(pending)}
                    researchBusy={researchBusy}
                    onConnect={connect}
                    onDevicePage={() => {
                      void action("device-page", () => api.openExternal(CODEX_DEVICE_URL));
                    }}
                    onLogout={() => setLogoutOpen(true)}
                  />
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
            <ProgressView
              projects={snapshot.projects}
              runs={runs}
              loading={loading}
              pending={Boolean(pending)}
              canResume={
                modelReady &&
                runnerReady &&
                toolsReady &&
                !loading &&
                !loadError &&
                !pending &&
                !researchBusy
              }
              onCancel={setCancelTarget}
              onResume={({ project, run }) => {
                void action(`resume-${run.id}`, async () => {
                  await api.request(
                    "POST",
                    `/api/projects/${encodeURIComponent(project.id)}/pipelines/${encodeURIComponent(run.id)}/resume`,
                    {},
                  );
                });
              }}
              onStart={() => setView("start")}
              onLibrary={() => setView("library")}
            />
          )}
          {view === "library" && (
            <LibraryView
              runs={runs}
              studies={snapshot.studies}
              loading={loading}
              pending={Boolean(pending)}
              query={query}
              onQuery={setQuery}
              onFileAction={fileAction}
              onStart={() => setView("start")}
            />
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
          <p className="field-help">글꼴: Pretendard Variable · SIL Open Font License 1.1</p>
          <details>
            <summary>Pretendard 라이선스 보기</summary>
            <pre className="license-text">{fontLicense}</pre>
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
