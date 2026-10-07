import { useEffect, useState } from "react";
import { Download, ExternalLink, LoaderCircle } from "lucide-react";
import type { AppSnapshot } from "../shared/contracts";
import type { ManuscriptReview, PublicRepository, ResearchPhase, ResearchSnapshot, ReviewCriterion } from "../shared/research";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";

const phaseLabels: Record<ResearchPhase, string> = {
  idle: "대기", plan: "연구 설계", redesign: "연구 설계 보완", literature: "문헌 수집", "study-review": "연구 적합성 검토", code: "실험 코드 작성",
  "code-review": "실험 코드 리뷰", experiment: "과학실험", manuscript: "원고 작성",
  "manuscript-review": "원고 품질 검토", export: "결과 파일 생성",
};
const pipelineLabels = { idle: "대기", running: "진행 중", paused: "중단됨", failed: "실패", completed: "원고 생성 완료" };
const studyHoldCodes = ["STUDY_REJECTED", "STUDY_INFEASIBLE"];
const outputLabels: Record<string, string> = {
  "export-pdf": "PDF", "export-docx": "Word", "export-md": "Markdown",
  "export-tex": "LaTeX", reproducibility: "재현 패키지 ZIP",
};
const manuscriptCriterionLabels = {
  contribution: "연구 기여", literature: "문헌 사용", interpretation: "결과 해석", presentation: "내용과 분량",
};
const remediationLabels = {
  revise_manuscript: "원고 보완", redesign_study: "새 연구 설계", infeasible: "추가 근거 필요",
};

function ManuscriptRecovery({ remediation }: { remediation: NonNullable<ManuscriptReview["remediation"]> }) {
  return <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label="원고 보완 방향">
    <h4 className="font-semibold">보완 방향 · {remediationLabels[remediation.strategy]}</h4>
    <p className="detail-note whitespace-pre-wrap">{remediation.reason}</p>
    <dl className="space-y-2">
      {remediation.actions.map(({ criterion, action }, index) => <div key={index}>
        <dt className="font-semibold">{manuscriptCriterionLabels[criterion]}</dt>
        <dd className="detail-note mt-1 whitespace-pre-wrap">{action}</dd>
      </div>)}
    </dl>
    {remediation.evidence_gaps.length > 0 && <div>
      <p className="font-semibold">부족한 근거</p>
      <ul className="mt-1 list-disc space-y-1 pl-5">
        {remediation.evidence_gaps.map((gap, index) => <li key={index}>{gap}</li>)}
      </ul>
    </div>}
  </section>;
}

function QualityReview({ title, review, criteria, selectedSources }: {
  title: string; review: { accepted: boolean; issues: string[] };
  criteria: Array<{ label: string; judgment: ReviewCriterion }>; selectedSources?: number;
}) {
  return (
    <details className="rounded-base border-2 border-border p-3 text-sm" open={!review.accepted}>
      <summary className="font-semibold">{title} · {review.accepted ? "통과" : "보완 필요"}</summary>
      <dl className="mt-3 space-y-3">
        {criteria.map(({ label, judgment }) => <div key={label}>
          <dt className="font-semibold">{label} · {judgment.passed ? "충족" : "미충족"}</dt>
          <dd className="detail-note mt-1 whitespace-pre-wrap">{judgment.reason}</dd>
        </div>)}
      </dl>
      {selectedSources !== undefined && <p className="detail-note mt-3">선정한 문헌 근거 {selectedSources}개</p>}
      {review.issues.length > 0 && <div className="mt-3">
        <p className="font-semibold">보완할 내용</p>
        <ul className="mt-1 list-disc space-y-1 pl-5">{review.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>
      </div>}
    </details>
  );
}

function ModelPicker({ id, label, models, value, onChange, disabled }: {
  id: string; label: string; models: AppSnapshot["models"]; value: string;
  onChange: (value: string) => void; disabled: boolean;
}) {
  return (
    <div className="field">
      <label id={`${id}-label`}>{label}</label>
      <Select value={value || null} items={models.map((model) => ({ value: model.slug, label: model.displayName }))}
        onValueChange={(next) => onChange(next ?? "")} disabled={disabled}>
        <SelectTrigger aria-labelledby={`${id}-label`}><SelectValue placeholder="모델 조회 필요" /></SelectTrigger>
        <SelectContent>
          {models.map((model) => <SelectItem key={model.slug} value={model.slug}>{model.displayName}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
  );
}

export function ResearchPane({ connection, connectionBusy, onBusyChange, view, onNavigate }: {
  connection: AppSnapshot; connectionBusy: boolean; onBusyChange: (busy: boolean) => void;
  view: "connection" | "research" | "results"; onNavigate: (view: "connection" | "research" | "results") => void;
}) {
  const [snapshot, setSnapshot] = useState<ResearchSnapshot | null>(null);
  const [source, setSource] = useState("");
  const [repositories, setRepositories] = useState<PublicRepository[] | null>(null);
  const [goal, setGoal] = useState("");
  const [model, setModel] = useState("");
  const [reviewerModel, setReviewerModel] = useState("");
  const [pending, setPending] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const unsubscribe = window.paperFactory.onResearchSnapshot((next) => {
      if (mounted) setSnapshot(next);
    });
    window.paperFactory.researchSnapshot().then(
      (next) => { if (mounted) setSnapshot(next); },
      () => { if (mounted) setLocalError("연구 상태를 읽지 못했습니다. 앱 실행 환경을 다시 확인해 주세요."); },
    );
    return () => { mounted = false; unsubscribe(); };
  }, []);

  useEffect(() => {
    const available = (current: string) => connection.models.some((item) => item.slug === current)
      ? current : (connection.models[0]?.slug ?? "");
    setModel(available);
    setReviewerModel(available);
  }, [connection.models, connection.session.profileId]);

  const active = (snapshot?.busy ?? false) || ["create", "resume", "revise", "improve", "cancel", "evidence", "save"].includes(pending ?? "");
  useEffect(() => {
    onBusyChange(active);
  }, [active, onBusyChange]);

  async function runAction(name: string, operation: () => Promise<ResearchSnapshot | boolean | void>) {
    setPending(name);
    setLocalError(null);
    setNotice(null);
    try {
      const result = await operation();
      if (result && typeof result === "object") setSnapshot(result);
      if (["create", "resume", "revise", "improve"].includes(name) && result && typeof result === "object" && result.jobs.some((job) => job.pipeline === "running")) {
        onNavigate("results");
      }
      if (name === "evidence") setNotice(result === false ? "추가 근거 선택을 취소했습니다." : "추가 근거를 보존했습니다. 연구를 이어가려면 재개 버튼을 누르세요.");
      if (name === "open") setNotice("결과 파일 열기를 요청했습니다.");
      if (name === "save" && result === true) setNotice("결과 파일을 저장했습니다.");
    } catch {
      setLocalError(name === "repositories"
        ? "GitHub 공개 저장소 목록을 조회하지 못했습니다. 계정 URL과 인터넷 연결, GitHub 조회 한도를 확인해 주세요."
        : name === "save"
          ? "결과 파일을 저장하지 못했습니다. 선택한 위치의 접근 권한과 남은 공간을 확인해 주세요."
          : "연구 작업 요청을 완료하지 못했습니다. 엔진 상태와 ChatGPT 연결을 확인해 주세요.");
    } finally {
      setPending(null);
    }
  }

  const locked = active || pending !== null || connectionBusy;
  const authorized = connection.session.connected && connection.session.sharing;
  const ready = snapshot?.runtime.state === "ready";
  const canRun = ready && authorized && !!model && !!reviewerModel && !locked;
  const accountSource = /^https:\/\/github\.com\/[A-Za-z0-9][A-Za-z0-9-]{0,38}\/?$/.test(source.trim());
  const error = snapshot?.error?.message ?? localError;
  const feedback = <>
    {error && (
      <div className="error-panel" role="alert">
        <p>{error}</p>
        {snapshot?.error && <p className="detail-note">오류 코드: {snapshot.error.code}</p>}
        {snapshot?.error?.action === "usage" && (
          <Button variant="outline" disabled={pending !== null}
            onClick={() => void runAction("usage", () => window.paperFactory.openUsage())}>
            ChatGPT 사용량 확인 <ExternalLink aria-hidden="true" />
          </Button>
        )}
        {snapshot?.error?.action === "sign-in" && <Button variant="neutral" onClick={() => onNavigate("connection")}>연결 화면으로 이동</Button>}
      </div>
    )}
    {notice && <p className="detail-note" role="status">{notice}</p>}
  </>;

  return (
    <>
    <section id="research-panel" role="tabpanel" aria-labelledby="workspace-tab-research" hidden={view !== "research"}
      className="workspace-panel" tabIndex={0}>
    <Card className="connection-card workspace-card">
      <CardHeader>
        <div className="section-heading">
          <CardTitle role="heading" aria-level={2} className="text-xl">새 연구</CardTitle>
          <span className="workspace-section-tag">GITHUB / RESEARCH</span>
        </div>
        <CardDescription>
          공개 GitHub 저장소에서 연구를 설계하고, 문헌과 연구 적합성을 검토한 뒤 실험과 원고 작성을 진행합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section aria-label="앱 실행 환경" className="runtime-summary">
          <div className="runtime-summary-heading">
            <Badge variant={ready ? "default" : "neutral"}>
              {!snapshot || snapshot.runtime.state === "checking" ? "실행 환경 확인 중" : ready ? "실행 환경 준비됨" : "실행 환경 사용 불가"}
            </Badge>
            <Button variant="ghost" size="sm" disabled={locked || snapshot?.runtime.state === "checking"}
              onClick={() => void runAction("runtime", () => window.paperFactory.checkRuntime())}>실행 환경 다시 확인</Button>
          </div>
          {snapshot && <p className="detail-note" role="status">{snapshot.runtime.message}</p>}
          {snapshot?.runtime.versions && (
            <details className="detail-note">
              <summary>확인된 실행 환경 버전</summary>
              <dl className="mt-2 grid gap-1">
                {Object.entries(snapshot.runtime.versions).map(([name, version]) => (
                  <div key={name} className="flex flex-wrap gap-2"><dt>{name}</dt><dd>{version}</dd></div>
                ))}
              </dl>
            </details>
          )}
        </section>

        {!authorized && <div className="research-guidance"><p className="detail-note">연결 화면에서 ChatGPT 로그인과 모델 사용 권한을 먼저 확인해 주세요.</p>
          <Button type="button" variant="neutral" size="sm" onClick={() => onNavigate("connection")}>연결 화면으로 이동</Button></div>}
        {authorized && connection.models.length === 0 && <div className="research-guidance"><p className="detail-note">연결 화면에서 모델을 새로고침한 뒤 작성·리뷰 모델을 선택하세요.</p>
          <Button type="button" variant="neutral" size="sm" onClick={() => onNavigate("connection")}>모델 연결 확인</Button></div>}
        {active && <div className="research-guidance"><p className="progress-message" role="status"><LoaderCircle className="status-spinner" aria-hidden="true" /> 연구 작업이 진행 중입니다.</p>
          <Button type="button" variant="neutral" size="sm" onClick={() => onNavigate("results")}>진행 중인 연구 보기</Button></div>}
        <form className="research-form" onSubmit={(event) => {
          event.preventDefault();
          if (canRun && source.trim() && !accountSource && goal.trim().length >= 8) {
            void runAction("create", () => window.paperFactory.createResearch({
              source: source.trim(), goal: goal.trim(), model, reviewerModel,
            }));
          }
        }}>
          <div className="field">
            <label htmlFor="research-source">공개 GitHub 저장소 또는 계정 URL</label>
            <input id="research-source" type="url" required maxLength={2048} value={source}
              onChange={(event) => { setSource(event.target.value); setRepositories(null); }} disabled={locked}
              className="w-full rounded-base border-2 border-border bg-secondary-background px-3 py-2 text-sm disabled:opacity-50"
              aria-describedby="research-source-note" />
            <p id="research-source-note" className="detail-note">공개 저장소 URL을 입력하거나 계정 URL에서 연구할 저장소를 선택하세요.</p>
            {accountSource && <Button type="button" variant="outline" disabled={locked}
              onClick={() => void runAction("repositories", async () => {
                setRepositories(await window.paperFactory.listPublicRepositories(source.trim()));
              })}>공개 저장소 조회</Button>}
            {repositories && <div className="space-y-2">
              <p className="detail-note">최근 업데이트된 공개 저장소 최대 100개입니다. 선택 후 소스와 실험 가능성을 확인합니다.</p>
              {repositories.length === 0 ? <p className="detail-note">공개 저장소가 없습니다.</p> :
                <Select value={null} items={repositories.map(repo => ({ value: repo.url, label: repo.name }))}
                  onValueChange={(url) => { if (url) { setSource(url); setRepositories(null); } }}>
                  <SelectTrigger aria-label="연구할 공개 저장소"><SelectValue placeholder="연구할 저장소 선택" /></SelectTrigger>
                  <SelectContent>{repositories.map(repo => <SelectItem key={repo.url} value={repo.url}>{repo.name}</SelectItem>)}</SelectContent>
                </Select>}
            </div>}
          </div>
          <div className="field">
            <label htmlFor="research-goal">연구 목표</label>
            <textarea id="research-goal" required minLength={8} maxLength={4000} rows={4} value={goal}
              onChange={(event) => setGoal(event.target.value)} disabled={locked} style={{ font: "inherit" }}
              className="w-full resize-y rounded-base border-2 border-border bg-secondary-background px-3 py-2 text-sm disabled:opacity-50" />
            <p className="detail-note">어떤 문제를 밝히고 싶은지, 비교할 방법과 실제 사용 상황을 적어 주세요. 단순 동작 확인만으로 연구 기여가 부족하면 실험 전에 보류됩니다.</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <ModelPicker id="writer-model" label="작성 모델 (writer)" models={connection.models}
              value={model} onChange={setModel} disabled={locked || !authorized || connection.models.length === 0} />
            <ModelPicker id="reviewer-model" label="리뷰 모델 (reviewer)" models={connection.models}
              value={reviewerModel} onChange={setReviewerModel} disabled={locked || !authorized || connection.models.length === 0} />
          </div>
          <p className="detail-note">선택한 두 모델은 새 연구·재개·보완·원고 수정에 적용됩니다. 모델 요청에는 ChatGPT 사용량이 적용됩니다.</p>
          <div className="action-row">
            <Button type="submit" disabled={!canRun || !source.trim() || accountSource || goal.trim().length < 8}>연구 시작</Button>
          </div>
        </form>
        {feedback}
      </CardContent>
    </Card>
    </section>
    <section id="results-panel" role="tabpanel" aria-labelledby="workspace-tab-results" hidden={view !== "results"}
      className="workspace-panel" tabIndex={0}>
    <Card className="connection-card workspace-card results-card">
      <CardHeader>
        <div className="section-heading"><CardTitle role="heading" aria-level={2} className="text-xl">연구 결과</CardTitle>
          <Badge variant="neutral">{snapshot ? `${snapshot.jobs.length}개 연구` : "상태 확인 중"}</Badge></div>
        <CardDescription>보존된 연구 설계·원고의 검토 판단과 결과 파일을 확인합니다. 원고 생성 완료는 초안 파일이 준비되었다는 뜻입니다.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {feedback}
        {!snapshot && <p className="progress-message" role="status"><LoaderCircle className="status-spinner" aria-hidden="true" /> 저장된 연구 상태를 불러오고 있습니다.</p>}
        {snapshot?.jobs.length === 0 && <div className="empty-results"><h2>아직 저장된 연구가 없습니다.</h2>
          <p className="detail-note">새 연구에서 저장소와 목표를 정하면 이곳에서 작업 상태와 결과를 확인할 수 있습니다.</p>
          <Button variant="neutral" onClick={() => onNavigate("research")}>새 연구로 이동</Button></div>}
        {snapshot?.jobs.some((job) => ["idle", "paused", "failed", "completed"].includes(job.pipeline)) && (
          <details className="resume-models"><summary>재개·보완·원고 수정에 사용할 모델</summary>
            <div className="grid gap-4 sm:grid-cols-2 mt-4">
              <ModelPicker id="resume-writer-model" label="재개 작성 모델" models={connection.models}
                value={model} onChange={setModel} disabled={locked || !authorized || connection.models.length === 0} />
              <ModelPicker id="resume-reviewer-model" label="재개 리뷰 모델" models={connection.models}
                value={reviewerModel} onChange={setReviewerModel} disabled={locked || !authorized || connection.models.length === 0} />
            </div>
          </details>
        )}
        {snapshot && snapshot.jobs.length > 0 && (
          <section className="space-y-4" aria-labelledby="research-jobs-label">
            <h2 id="research-jobs-label" className="font-semibold">저장된 연구</h2>
            <p className="detail-note">재개는 버튼을 눌러 시작합니다. 중단됐거나 결과가 불명확한 과학실험은 자동으로 다시 실행하지 않습니다.</p>
            {snapshot.jobs.map((job) => (
              <article key={job.id} id={job.id} tabIndex={-1} className="space-y-3 rounded-base border-2 border-border bg-secondary-background p-4" aria-labelledby={`${job.id}-label`}>
                <div className="section-heading">
                  <h3 id={`${job.id}-label`} className="font-semibold break-words">{job.source.split("/").filter(Boolean).at(-1) || job.id}</h3>
                  <Badge variant={job.pipeline === "completed" ? "default" : "neutral"}>{job.pipeline !== "running" && studyHoldCodes.includes(job.code ?? "") ? "연구 보류" : job.pipeline !== "running" && job.code === "MANUSCRIPT_REJECTED" ? "원고 보류" : pipelineLabels[job.pipeline]}</Badge>
                </div>
                <p className="detail-note break-all">{job.source}</p>
                <details className="detail-note"><summary>연구 목표</summary><p className="mt-2 whitespace-pre-wrap">{job.goal}</p></details>
                <dl className="grid gap-1 text-xs">
                  <div><dt className="inline font-semibold">작업 단계: </dt><dd className="inline">{phaseLabels[job.phase]} ({job.phase})</dd></div>
                  <div><dt className="inline font-semibold">엔진 단계·상태: </dt><dd className="inline">{job.stage} · {job.status}</dd></div>
                  <div><dt className="inline font-semibold">작성·리뷰 모델: </dt><dd className="inline">{job.model} · {job.reviewerModel}</dd></div>
                  <div><dt className="inline font-semibold">연구 ID: </dt><dd className="inline">{job.id}</dd></div>
                  <div><dt className="inline font-semibold">연구 설계 보완: </dt><dd className="inline">{job.redesignAttempt}/2회</dd></div>
                </dl>
                {(job.parentResearchId || job.followupResearchId) && <nav className="flex flex-wrap gap-4 text-sm" aria-label="연결된 연구">
                  {job.parentResearchId && <a className="font-semibold underline underline-offset-4" href={`#${job.parentResearchId}`}>이전 연구 보기</a>}
                  {job.rootResearchId !== job.id && job.rootResearchId !== job.parentResearchId && <a className="font-semibold underline underline-offset-4" href={`#${job.rootResearchId}`}>최초 연구 보기</a>}
                  {job.followupResearchId && <a className="font-semibold underline underline-offset-4" href={`#${job.followupResearchId}`}>후속 연구 보기</a>}
                </nav>}
                {job.message && <p className="detail-note">{job.message}</p>}
                {job.code && <p className="detail-note">상태 코드: {job.code}</p>}
                {job.studyReview && <QualityReview title="연구 적합성 검토" review={job.studyReview}
                  selectedSources={job.studyReview.selected_sources.length} criteria={[
                    { label: "연구 질문", judgment: job.studyReview.question },
                    { label: "새로운 기여", judgment: job.studyReview.contribution },
                    { label: "관련 문헌", judgment: job.studyReview.literature },
                    { label: "비교 대상", judgment: job.studyReview.comparison },
                    { label: "표본과 실험 설계", judgment: job.studyReview.sampling },
                    { label: "실행 가능성과 주장 범위", judgment: job.studyReview.feasibility },
                  ]} />}
                {job.manuscriptReview && <QualityReview title="원고 품질 검토" review={job.manuscriptReview} criteria={[
                  { label: "연구 기여", judgment: job.manuscriptReview.contribution },
                  { label: "문헌 사용", judgment: job.manuscriptReview.literature },
                  { label: "결과 해석", judgment: job.manuscriptReview.interpretation },
                  { label: "내용과 분량", judgment: job.manuscriptReview.presentation },
                ]} />}
                {job.manuscriptReview?.remediation && <ManuscriptRecovery remediation={job.manuscriptReview.remediation} />}
                {job.pipeline === "completed" && !job.studyReview && <p className="detail-note">이 결과에는 현재 기준의 연구 적합성 검토 기록이 없습니다.</p>}
                {job.pipeline === "completed" && !job.manuscriptReview && <p className="detail-note">이 결과에는 현재 기준의 원고 품질 검토 기록이 없습니다.</p>}
                {studyHoldCodes.includes(job.code ?? "") && job.pipeline !== "running" && <p className="detail-note" role="status">현재 실행 환경과 확보한 근거로 연구 기준을 충족하는 설계를 마련하지 못해 실험과 원고 생성을 진행하지 않았습니다. 검토 이유를 참고해 목표와 비교 방법을 바꾼 새 연구를 시작하세요.</p>}
                {job.code === "MANUSCRIPT_REJECTED" && job.pipeline !== "running" && <p className="detail-note" role="status">{job.followupResearchId
                  ? "원고와 실험 결과를 보존하고, 검토 내용에 따라 별도 후속 연구를 만들었습니다. 후속 연구에서 설계를 보완하며 이전 실험 결과는 변경하지 않습니다."
                  : "원고가 품질 검토를 통과하지 못해 결과 파일을 생성하지 않았습니다. 보완 방향과 검토 이유를 확인하세요. 이전 실험 결과는 보존됩니다."}</p>}
                {snapshot.cleanupResearchIds.includes(job.id) && job.pipeline !== "running" && (
                  <p className="detail-note" role="status">실험 종료와 기록 보존을 확인해야 새 연구와 계정 변경을 할 수 있습니다. 로그인 없이 정리 확인을 다시 시도할 수 있습니다.</p>
                )}
                <div className="action-row">
                  {job.pipeline === "running" && (
                    <Button variant="outline" disabled={pending !== null}
                      onClick={() => void runAction("cancel", () => window.paperFactory.cancelResearch(job.id))}>연구 취소</Button>
                  )}
                  {snapshot.cleanupResearchIds.includes(job.id) && job.pipeline !== "running" && (
                    <Button variant="outline" disabled={pending !== null || snapshot.runtime.state === "checking"}
                      onClick={() => void runAction("cancel", () => window.paperFactory.cancelResearch(job.id))}>
                      {pending === "cancel" ? "정리 확인 중…" : "정리 다시 확인"}
                    </Button>
                  )}
                  {job.improvementAvailable && ["idle", "paused", "failed"].includes(job.pipeline) && (
                    <Button variant="outline" disabled={!canRun}
                      onClick={() => void runAction("improve", () => window.paperFactory.improveResearchWriting(job.id, model, reviewerModel))}>
                      심사·보완 이어가기
                    </Button>
                  )}
                  {["idle", "paused", "failed"].includes(job.pipeline) && job.status !== "blocked" && !studyHoldCodes.includes(job.code ?? "") && job.resumeKind && !snapshot.cleanupResearchIds.includes(job.id) && (
                    <Button variant="outline" disabled={!canRun}
                      onClick={() => void runAction("resume", () => window.paperFactory.resumeResearch(job.id, model, reviewerModel))}>
                      {job.resumeKind === "preparation" ? "연구 준비 재개" : "원고 작성 재개"}
                    </Button>
                  )}
                  {["idle", "paused", "failed"].includes(job.pipeline) && ["created", "proposed", "planned", "analyzed"].includes(job.stage) &&
                    ["ready", "cancelled"].includes(job.status) && (
                    <Button variant="outline" disabled={locked}
                      onClick={() => void runAction("evidence", () => window.paperFactory.addResearchEvidence(job.id))}>추가 근거 선택</Button>
                  )}
                </div>
                {job.improvementAvailable && <p className="detail-note">보존된 근거로 새 심사를 진행합니다. 추가 측정이 필요하면 별도 연구를 설계하고 적합성 검토부터 진행합니다.</p>}
                {(["created", "proposed", "planned", "analyzed"].includes(job.stage) || job.supportingDocuments.length > 0) && (
                  <div className="space-y-2">
                    <p className="detail-note">원문 문서(.md·.txt·.json, 영문 파일명)를 다음 작성·검토 요청과 재현 ZIP에 포함합니다. 각 128 KiB, 연구당 최대 8개·256 KiB입니다. 측정·고정 계획·리뷰 승인을 변경하지 않으며, 가져온 시각은 문서 안의 사전 활동 주장을 증명하지 않습니다.</p>
                    <details className="detail-note"><summary>첨부 근거 {job.supportingDocuments.length}개</summary>
                      {job.supportingDocuments.length === 0 ? <p className="mt-2">첨부된 근거 문서가 없습니다.</p> :
                        <ul className="mt-2 space-y-1">{job.supportingDocuments.map(document =>
                          <li key={document.id}>{document.name} · {document.size.toLocaleString("ko-KR")} 바이트</li>)}</ul>}
                    </details>
                  </div>
                )}
                {job.pipeline === "completed" && job.artifacts.some((artifact) => outputLabels[artifact.id]) && (
                  <div className="space-y-3 border-t-2 border-border pt-3">
                    <h4 className="font-semibold">생성된 결과 파일</h4>
                    <p className="detail-note">완료 상태와 모델의 검토 통과는 학술지 심사나 채택을 의미하지 않습니다. 제출 전 원문 문헌·실험 설계·연구 기여를 직접 확인해 주세요.</p>
                    <div className="action-row">
                      <Button variant="outline" size="sm" disabled={locked}
                        onClick={() => void runAction("folder", () => window.paperFactory.showArtifactFolder(job.id,
                          job.artifacts.find(artifact => outputLabels[artifact.id])!.id))}>결과 폴더 열기</Button>
                      {job.stage === "exported" && job.status === "completed" && job.studyReview?.accepted && job.manuscriptReview?.accepted && (
                        <Button variant="outline" size="sm" disabled={!canRun}
                          onClick={() => void runAction("revise", () => window.paperFactory.reviseResearchWriting(job.id, model, reviewerModel))}>원고 수정</Button>
                      )}
                    </div>
                    {job.studyReview?.accepted && job.manuscriptReview?.accepted && <p className="detail-note">원고 수정은 보존된 실험 결과로 새 원고와 리뷰를 작성합니다. 이전 결과 파일과 실험 기록은 보존됩니다.</p>}
                    {job.artifacts.filter((artifact) => outputLabels[artifact.id]).map((artifact) => (
                      <div key={artifact.id} className="space-y-2">
                        <p className="text-sm">{outputLabels[artifact.id]} · {artifact.size.toLocaleString("ko-KR")} 바이트</p>
                        <div className="action-row">
                          <Button variant="outline" size="sm" disabled={locked}
                            onClick={() => void runAction("save", () => window.paperFactory.saveArtifact(job.id, artifact.id))}>
                            <Download aria-hidden="true" /> {outputLabels[artifact.id]} 저장
                          </Button>
                          <Button variant="ghost" size="sm" disabled={locked}
                            onClick={() => void runAction("open", () => window.paperFactory.openArtifact(job.id, artifact.id))}>
                            {outputLabels[artifact.id]} 열기 <ExternalLink aria-hidden="true" />
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            ))}
          </section>
        )}
      </CardContent>
    </Card>
    </section>
    </>
  );
}
