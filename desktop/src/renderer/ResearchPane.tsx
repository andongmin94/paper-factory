import { useEffect, useState } from "react";
import { Download, ExternalLink, LoaderCircle } from "lucide-react";
import type { AppSnapshot } from "../shared/contracts";
import type { PublicRepository, ResearchPhase, ResearchSnapshot } from "../shared/research";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";
import { SaveArtifactDialog } from "./SaveArtifactDialog";

const phaseLabels: Record<ResearchPhase, string> = {
  idle: "대기", plan: "연구 계획", literature: "문헌 수집", code: "실험 코드 작성",
  "code-review": "실험 코드 리뷰", experiment: "과학실험", manuscript: "원고 작성",
  "manuscript-review": "원고 리뷰", export: "결과 파일 생성",
};
const pipelineLabels = { idle: "대기", running: "진행 중", paused: "중단됨", failed: "실패", completed: "완료" };
const outputLabels: Record<string, string> = {
  "export-pdf": "PDF", "export-docx": "Word", "export-md": "Markdown",
  "export-tex": "LaTeX", reproducibility: "재현 패키지 ZIP",
};
const outputNames: Record<string, string> = {
  "export-pdf": "paper.pdf", "export-docx": "paper.docx", "export-md": "paper.md",
  "export-tex": "paper.tex", reproducibility: "reproducibility.zip",
};

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
  const [saveTarget, setSaveTarget] = useState<{ id: string; artifactId: string; label: string; trigger: HTMLElement } | null>(null);

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

  const active = (snapshot?.busy ?? false) || ["create", "resume", "revise", "cancel", "evidence", "save"].includes(pending ?? "");
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
      if (["create", "resume", "revise"].includes(name) && result && typeof result === "object" && result.jobs.some((job) => job.pipeline === "running")) {
        onNavigate("results");
      }
      if (name === "evidence") setNotice(result === false ? "추가 근거 선택을 취소했습니다." : "추가 근거를 보존했습니다. 연구를 이어가려면 재개 버튼을 누르세요.");
      if (name === "open") setNotice("결과 파일 열기를 요청했습니다.");
    } catch {
      setLocalError(name === "repositories"
        ? "GitHub 공개 저장소 목록을 조회하지 못했습니다. 계정 URL과 인터넷 연결, GitHub 조회 한도를 확인해 주세요."
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
          공개 GitHub 저장소를 바탕으로 계획·실험·리뷰·원고 작성과 결과 파일 생성을 진행합니다.
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
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <ModelPicker id="writer-model" label="작성 모델 (writer)" models={connection.models}
              value={model} onChange={setModel} disabled={locked || !authorized || connection.models.length === 0} />
            <ModelPicker id="reviewer-model" label="리뷰 모델 (reviewer)" models={connection.models}
              value={reviewerModel} onChange={setReviewerModel} disabled={locked || !authorized || connection.models.length === 0} />
          </div>
          <p className="detail-note">선택한 두 모델은 새 연구·재개·원고 수정에 적용됩니다. 모델 요청에는 ChatGPT 사용량이 적용됩니다.</p>
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
        <CardDescription>저장된 연구의 실제 단계와 생성된 결과 파일을 확인합니다.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {feedback}
        {!snapshot && <p className="progress-message" role="status"><LoaderCircle className="status-spinner" aria-hidden="true" /> 저장된 연구 상태를 불러오고 있습니다.</p>}
        {snapshot?.jobs.length === 0 && <div className="empty-results"><h2>아직 저장된 연구가 없습니다.</h2>
          <p className="detail-note">새 연구에서 저장소와 목표를 정하면 이곳에서 작업 상태와 결과를 확인할 수 있습니다.</p>
          <Button variant="neutral" onClick={() => onNavigate("research")}>새 연구로 이동</Button></div>}
        {snapshot?.jobs.some((job) => ["idle", "paused", "failed", "completed"].includes(job.pipeline)) && (
          <details className="resume-models"><summary>재개·원고 수정에 사용할 모델</summary>
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
              <article key={job.id} className="space-y-3 rounded-base border-2 border-border bg-secondary-background p-4" aria-labelledby={`${job.id}-label`}>
                <div className="section-heading">
                  <h3 id={`${job.id}-label`} className="font-semibold break-words">{job.source.split("/").filter(Boolean).at(-1) || job.id}</h3>
                  <Badge variant={job.pipeline === "completed" ? "default" : "neutral"}>{pipelineLabels[job.pipeline]}</Badge>
                </div>
                <p className="detail-note break-all">{job.source}</p>
                <details className="detail-note"><summary>연구 목표</summary><p className="mt-2 whitespace-pre-wrap">{job.goal}</p></details>
                <dl className="grid gap-1 text-xs">
                  <div><dt className="inline font-semibold">작업 단계: </dt><dd className="inline">{phaseLabels[job.phase]} ({job.phase})</dd></div>
                  <div><dt className="inline font-semibold">엔진 단계·상태: </dt><dd className="inline">{job.stage} · {job.status}</dd></div>
                  <div><dt className="inline font-semibold">작성·리뷰 모델: </dt><dd className="inline">{job.model} · {job.reviewerModel}</dd></div>
                  <div><dt className="inline font-semibold">연구 ID: </dt><dd className="inline">{job.id}</dd></div>
                </dl>
                {job.message && <p className="detail-note">{job.message}</p>}
                {job.code && <p className="detail-note">오류 코드: {job.code}</p>}
                <div className="action-row">
                  {job.pipeline === "running" && (
                    <Button variant="outline" disabled={pending !== null}
                      onClick={() => void runAction("cancel", () => window.paperFactory.cancelResearch(job.id))}>연구 취소</Button>
                  )}
                  {["idle", "paused", "failed"].includes(job.pipeline) && (
                    <Button variant="outline" disabled={!canRun}
                      onClick={() => void runAction("resume", () => window.paperFactory.resumeResearch(job.id, model, reviewerModel))}>선택한 모델로 재개</Button>
                  )}
                  {["idle", "paused", "failed"].includes(job.pipeline) && ["created", "planned", "analyzed"].includes(job.stage) &&
                    ["ready", "cancelled"].includes(job.status) && (
                    <Button variant="outline" disabled={locked}
                      onClick={() => void runAction("evidence", () => window.paperFactory.addResearchEvidence(job.id))}>추가 근거 선택</Button>
                  )}
                </div>
                {(["created", "planned", "analyzed"].includes(job.stage) || job.supportingDocuments.length > 0) && (
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
                    <div className="action-row">
                      <Button variant="outline" size="sm" disabled={locked}
                        onClick={() => void runAction("folder", () => window.paperFactory.showArtifactFolder(job.id,
                          job.artifacts.find(artifact => outputLabels[artifact.id])!.id))}>결과 폴더 열기</Button>
                      {job.stage === "exported" && job.status === "completed" && (
                        <Button variant="outline" size="sm" disabled={!canRun}
                          onClick={() => void runAction("revise", () => window.paperFactory.reviseResearchWriting(job.id, model, reviewerModel))}>원고 수정</Button>
                      )}
                    </div>
                    <p className="detail-note">원고 수정은 보존된 실험 결과로 새 원고와 리뷰를 작성합니다. 이전 결과 파일과 실험 기록은 보존됩니다.</p>
                    {job.artifacts.filter((artifact) => outputLabels[artifact.id]).map((artifact) => (
                      <div key={artifact.id} className="space-y-2">
                        <p className="text-sm">{outputLabels[artifact.id]} · {artifact.size.toLocaleString("ko-KR")} 바이트</p>
                        <div className="action-row">
                          <Button variant="outline" size="sm" disabled={locked}
                            onClick={(event) => { setNotice(null); setLocalError(null); setSaveTarget({ id: job.id, artifactId: artifact.id,
                              label: outputLabels[artifact.id], trigger: event.currentTarget }); }}>
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
    {saveTarget && <SaveArtifactDialog label={saveTarget.label} fileName={outputNames[saveTarget.artifactId]} returnFocus={saveTarget.trigger}
      onCancel={() => { setSaveTarget(null); setNotice("파일 저장을 취소했습니다."); }}
      onSave={async (destinationPath) => {
        setPending("save");
        try {
          const saved = await window.paperFactory.saveArtifact(saveTarget.id, saveTarget.artifactId, destinationPath);
          if (saved !== true) throw new Error("Artifact save was not confirmed");
          setSaveTarget(null); setNotice("결과 파일을 저장했습니다.");
        } finally { setPending(null); }
      }} />}
    </>
  );
}
