import { useEffect, useState } from "react";
import { getPublicationVenue } from "../shared/venues";
import type { RepositoryPublicationStatus } from "../shared/publication";
import type { ResearchItem } from "../shared/research";
import { Button } from "./components/ui/button";
import { attemptCount, repositoryCriterionLabels, type ResearchAction } from "./research-ui";
import { RepositoryAnalysisDetails, RepositoryTargetDetails } from './RepositoryEvidenceDetails';

const repositoryArticleTypeLabels = { software_tool: "소프트웨어 도구 분석", design_case_study: "설계 사례 분석", technical_analysis: "기술 분석" };

function RepositoryRevisionEditor({ job, disabled, runAction }: { job: ResearchItem; disabled: boolean; runAction: ResearchAction }) {
  const [feedback, setFeedback] = useState("");
  useEffect(() => { setFeedback(""); }, [job.repositoryPaper?.draft_sha256]);
  if (job.researchMode !== "repository_analysis" || job.stage !== "repository_manuscript" ||
    !job.manuscriptAvailable || !job.repositoryPaper?.draft) return null;
  const saved = job.repositoryPaper.revision_feedback ?? job.repositoryPaper.prior_feedback?.revision_feedback;
  const available = job.pipeline === "paused" && ["ready", "blocked"].includes(job.status) && job.draftAttempt !== null && job.draftAttempt > 0 &&
    job.draftAttempt < 3 && !job.repositoryPaper.revision_feedback;
  if (!saved && !available) return null;
  const formatBlockers = job.repositoryPaper.venueFormat?.blockers ?? [];
  const venueName = getPublicationVenue(job.repositoryPaper.plan?.publication_target?.venue_id,
    job.repositoryPaper.publication_venues?.venues)?.name ?? '선택한 투고처';
  const valid = feedback.trim().length >= 12 && feedback.length <= 12000 && !/[\u0000]/.test(feedback);
  return <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label="투고 품질 보완">
    <h4 className="font-semibold">투고 품질 보완</h4>
    {saved && <details className="detail-note"><summary>보존한 보완 의견</summary>
      <p className="mt-2 whitespace-pre-wrap">{saved.feedback}</p>
    </details>}
    {available && <form className="space-y-3" onSubmit={event => {
      event.preventDefault();
      if (!valid || disabled) return;
      void runAction("repository-revision", () => window.paperFactory.requestRepositoryRevision(job.id, feedback));
    }}>
      <p className="detail-note">검토에서 찾은 문제를 적으면 수정 계획을 만들고 새 원고·심사·출력을 이어갑니다. 원고마다 한 번 제출할 수 있으며, 이전 원고·심사와 사용한 횟수는 보존됩니다.</p>
      {!!formatBlockers.length && <Button type="button" variant="neutral" disabled={disabled}
        onClick={() => setFeedback(`${venueName} 형식 점검에서 확인한 다음 항목을 보존된 근거와 원고에 맞게 보완해 주세요.\n${formatBlockers.map(item => `- ${item}`).join("\n")}`)}>형식 보완 의견 넣기</Button>}
      <div className="field"><label htmlFor={`${job.id}-revision-feedback`}>투고 품질 보완 의견 (12~12,000자)</label>
        <textarea id={`${job.id}-revision-feedback`} required minLength={12} maxLength={12000} value={feedback} disabled={disabled}
          onChange={event => setFeedback(event.target.value)} /></div>
      <Button type="submit" variant="outline" disabled={disabled || !valid}>의견 반영해 원고 보완</Button>
    </form>}
  </section>;
}

export function RepositoryPaperDetails({ job, publication, disabled, runAction }: {
  job: ResearchItem; publication: RepositoryPublicationStatus | null; disabled: boolean; runAction: ResearchAction;
}) {
  const paper = job.repositoryPaper;
  const assessment = paper?.content_assessment;
  return <>
    {publication && <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="원고 준비도">
      <h4 className="font-semibold">현재 준비도 · {publication.label}</h4>
      <p className="whitespace-pre-wrap">다음 작업: {publication.nextAction}</p>
      {!!publication.blockers.length && <ul className="list-disc space-y-1 pl-5">{publication.blockers.map((blocker, index) => <li key={index}>{blocker}</li>)}</ul>}
      <p className="detail-note">저자는 분석과 AI 사용 공개, 저작권·저자 책임, 필요한 소개문·사진, 최신 PDF 전체 페이지와 선택한 학술지의 실제 제출 요건을 직접 확인해야 합니다. 앱의 원고 평가와 출력 기록은 저자 승인이나 학술지 채택을 대신하지 않습니다.</p>
    </section>}
    {paper && <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label="레포 분석 논문">
      <h4 className="font-semibold">코드·문서 분석 논문</h4>
      {paper.plan && <>
        <p>{repositoryArticleTypeLabels[paper.plan.article_type]}</p>
        <p className="font-semibold whitespace-pre-wrap">{paper.plan.title}</p>
        <p className="whitespace-pre-wrap">연구 질문: {paper.plan.question}</p>
        <p className="whitespace-pre-wrap">기여: {paper.plan.contribution}</p>
        <details className="detail-note"><summary>분석 방법과 비교 기준</summary>
          <p className="mt-2 whitespace-pre-wrap">{paper.plan.analysis_method}</p>
          <ul className="mt-2 list-disc pl-5">{paper.plan.comparison_dimensions.map((dimension, index) => <li key={index}>{dimension}</li>)}</ul>
        </details>
      </>}
      <p className="detail-note">저장소 코드 실행 {attemptCount(job.executionAttempt)} · 보존한 매체별 실제 원고 {paper.portfolio?.venues.reduce((sum, venue) => sum + venue.admitted_drafts, 0) ?? 0}개. 코드를 읽어 확인한 설계와 구현을 다루며 실행 성능·사용자 효과를 추정하지 않습니다.</p>
      {paper.analysis_provenance && <p className="detail-note">{paper.analysis_provenance.model_calls.length
        ? "분석·작성 방식: 앱과 AI 모델이 보존된 코드·문서를 읽고 원고를 작성했습니다. 사람의 분석·승인은 별도 확인이 필요합니다."
        : "분석·작성 방식의 모델 수행 기록이 보존되어 있지 않습니다. 실제 수행 과정과 사람의 분석·승인을 확인해야 합니다."}</p>}
      <RepositoryTargetDetails paper={paper} />
      <p className="detail-note">분석 수행 {attemptCount(paper.analysis_attempts)}{paper.analysis_revision_required ? ' · 보존된 심사 요구를 반영한 추가 분석 대기' : ''}</p>
      {paper.analysis && <RepositoryAnalysisDetails paper={paper} />}
      {!!paper.references?.length && <details className="detail-note">
        <summary>공식 문서 확보 기록 {paper.references.length}개</summary>
        <ul className="mt-2 space-y-2">{paper.references.map(reference => <li key={reference.id}>
          <p className="break-all">{reference.url}</p>
          <p>{reference.purpose === "comparison" ? "설계·도구 비교" : "투고처 안내"} · {reference.status === "retained" ? "원문 보존" : "확보 실패"}</p>
          {reference.failure && <p className="whitespace-pre-wrap">{reference.failure}</p>}
        </li>)}</ul>
      </details>}
      {paper.review && <>
        <h5 className="font-semibold">실제 원고 평가 · {paper.scientific_ready ? "과학적 검토 충족" : "보완 필요"}</h5>
        <dl className="space-y-3">{Object.entries(paper.review.criteria).map(([key, criterion]) => <div key={key}>
          <dt className="font-semibold">{repositoryCriterionLabels[key as keyof typeof repositoryCriterionLabels]} · {criterion.passed ? "충족" : "미충족"}</dt>
          <dd className="detail-note mt-1 whitespace-pre-wrap">{criterion.reason}</dd>
        </div>)}</dl>
        {paper.review.issues.length > 0 && <ul className="list-disc space-y-1 pl-5">{paper.review.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>}
        <p className="detail-note">실제 원고는 평가 결과와 관계없이 보존됩니다. 분석·비교·기여 논증과 선택한 투고처의 제출 요건, 저자·출력 확인은 별개입니다.</p>
      </>}
      {assessment && <section className="space-y-3" aria-label="실무 선행 비교·기여 논증 평가">
        <h5 className="font-semibold">실무 선행 비교·기여 논증 · {paper.content_ready ? "충족" : "보완 필요"}</h5>
        <dl className="space-y-3">{(["comparison", "contribution"] as const).map(key => <div key={key}>
          <dt className="font-semibold">{key === "comparison" ? "선행 작업·원문 비교" : "실무 기여 논증"} · {assessment[key].passed ? "충족" : "미충족"}</dt>
          <dd className="detail-note mt-1 whitespace-pre-wrap">{assessment[key].reason}</dd>
        </div>)}</dl>
        {!!assessment.issues.length && <ul className="list-disc space-y-1 pl-5">{assessment.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>}
        {!!assessment.revision_outline.length && <details className="detail-note"><summary>실제 원고에 반영할 문단 수정</summary>
          <ul className="mt-2 space-y-2">{assessment.revision_outline.map((item, index) => <li key={index}>
            <p className="font-semibold">{item.heading}</p><p className="whitespace-pre-wrap">{item.instruction}</p>
          </li>)}</ul>
        </details>}
      </section>}
      {paper.assessment_available && <p className="detail-note">보존된 과학 심사를 유지하며 선행 작업 비교와 실무 기여 논증의 부족한 부분을 한 번 평가합니다. 구체적인 자료 확보·원고 수정이 가능하면 남은 횟수 안에서 이어갑니다.</p>}
      {!!paper.next_actions.length && <>
        <h5 className="font-semibold">구체적인 다음 보완 작업</h5>
        <ul className="space-y-3">{paper.next_actions.map((action, index) => <li key={index}>
          <p className="font-semibold">{action.target}</p>
          <p className="whitespace-pre-wrap">{action.required_change}</p>
          <p className="detail-note whitespace-pre-wrap">확인 방법: {action.verification}</p>
        </li>)}</ul>
      </>}
    </section>}
    <RepositoryRevisionEditor job={job} disabled={disabled} runAction={runAction} />
  </>;
}
