import { useEffect, useState } from "react";
import { ExternalLink, LoaderCircle } from "lucide-react";
import type { AppSnapshot } from "../shared/contracts";
import { NEW_RESEARCH_MODE } from "../shared/publication";
import { PUBLICATION_VENUES } from '../shared/venues';
import type { PublicRepository, ResearchSnapshot } from "../shared/research";
import { ResearchResultCard } from "./ResearchResultCard";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./components/ui/select";

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

  const active = (snapshot?.busy ?? false) || ["create", "resume", "improve", "repository-revision", "portfolio", "portfolio-format", "portfolio-layout", "reformat", "cancel", "save", "author"].includes(pending ?? "");
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
      if (["create", "resume", "improve", "repository-revision", "portfolio"].includes(name) && result && typeof result === "object" && result.jobs.some((job) => job.pipeline === "running")) {
        onNavigate("results");
      }
      if (name === "open") setNotice("결과 파일 열기를 요청했습니다.");
      if (name === "save" && result === true) setNotice("결과 파일을 저장했습니다.");
      if (name === "reformat") setNotice("출력 다시 생성 기록을 보존했습니다. 새 PDF와 Word 파일의 페이지를 확인하세요.");
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
  const analysisReady = snapshot?.runtime.repositoryAnalysisReady === true;
  const canRun = analysisReady && authorized && !!model && !!reviewerModel && !locked;
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
          <span className="workspace-section-tag">GITHUB / IEEE SOFTWARE · S&amp;P</span>
        </div>
        <CardDescription>
          공개 GitHub 저장소의 소스·문서를 분석해 IEEE Software·Security &amp; Privacy에 적합한 실제 Feature Article을 작성하고 각각 평가합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section aria-label="앱 실행 환경" className="runtime-summary">
          <div className="runtime-summary-heading">
            <Badge variant={analysisReady ? "default" : "neutral"}>
              {!snapshot || snapshot.runtime.state === "checking" ? "연구 엔진 확인 중" : analysisReady ? "코드·문서 분석 준비됨" : "연구 엔진 사용 불가"}
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
              source: source.trim(), goal: goal.trim(), model, reviewerModel, researchMode: NEW_RESEARCH_MODE,
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
              <p className="detail-note">최근 업데이트된 공개 저장소 최대 100개입니다. 선택 후 코드·문서에서 연구할 내용을 파악합니다.</p>
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
            <p className="detail-note">저장소에서 연구할 문제와 기대하는 기여를 적어 주세요. 앱이 실제 근거에 맞는 분석 범위, 투고처와 원고 구성을 설계합니다.</p>
          </div>
          <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="학술지 선택과 작성 목표">
            <h3 className="font-semibold">투고 목표 · 공통 연구와 학술지별 실제 원고</h3>
            <p className="detail-note">설계 → 필요한 문헌 확보 → 공통 소스 분석 → 적합한 매체별 원고 → PDF·Word 형식 선점검 → 독립 평가로 진행합니다. Software는 설계 결정과 실무 교훈, S&amp;P는 위협·권한 경계와 대응을 중심으로 작성합니다.</p>
            <details className="detail-note"><summary>지원하는 두 IEEE 매체와 공식 안내</summary>
              <ul className="mt-2 space-y-1">{PUBLICATION_VENUES.map(venue => <li key={venue.id}>
                <a href={venue.guidelines_url} target="_blank" rel="noreferrer" className="underline">{venue.name} 공식 작성 안내</a>
              </li>)}</ul>
            </details>
            <p className="detail-note">프로젝트마다 코드를 실행하지 않습니다. 학술지별로 부족한 근거와 다음 작업을 표시합니다. 임용 실적 인정과 학술지 채택은 별도 확인이 필요합니다.</p>
          </section>
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
        <CardDescription>공통 연구와 학술지별 원고·심사·필요한 근거를 확인합니다. 기존 자료·횟수와 결과 파일은 보존합니다.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        {feedback}
        {!snapshot && <p className="progress-message" role="status"><LoaderCircle className="status-spinner" aria-hidden="true" /> 저장된 연구 상태를 불러오고 있습니다.</p>}
        {snapshot?.jobs.length === 0 && <div className="empty-results"><h2>아직 저장된 연구가 없습니다.</h2>
          <p className="detail-note">새 연구에서 저장소와 목표를 정하면 이곳에서 작업 상태와 결과를 확인할 수 있습니다.</p>
          <Button variant="neutral" onClick={() => onNavigate("research")}>새 연구로 이동</Button></div>}
        {snapshot?.jobs.some((job) => job.researchMode === NEW_RESEARCH_MODE && ["idle", "paused", "failed", "completed"].includes(job.pipeline)) && (
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
            <p className="detail-note">최종 목표: 적합한 IEEE Software·Security &amp; Privacy 실제 원고와 개별 투고 준비도 평가</p>
            <p className="detail-note">원고의 작성·보완은 버튼을 눌러 이어갑니다. 과거 실험 연구는 조회와 결과 파일 열기·저장만 제공합니다.</p>
            {snapshot.jobs.map(job => <ResearchResultCard key={job.id} job={job} locked={locked}
              canWork={canRun && job.researchMode === NEW_RESEARCH_MODE} analysisReady={analysisReady}
              cleanupPending={snapshot.cleanupResearchIds.includes(job.id)} runtimeChecking={snapshot.runtime.state === "checking"}
              pending={pending} model={model} reviewerModel={reviewerModel} runAction={runAction} />)}
          </section>
        )}
      </CardContent>
    </Card>
    </section>
    </>
  );
}
