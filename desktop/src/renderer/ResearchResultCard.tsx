import { NEW_RESEARCH_MODE, inspectRepositoryPublication } from "../shared/publication";
import type { RepositoryPublicationStatus } from "../shared/publication";
import type { ManuscriptReview, PublicationReadiness, ResearchItem, ResearchPhase, ReviewCriterion, SubmissionReadiness } from "../shared/research";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { RepositoryPaperDetails } from "./RepositoryPaperDetails";
import { RepositoryPortfolioDetails } from "./RepositoryPortfolioDetails";
import { AuthorMetadataEditor, ResearchOutputs } from "./ResearchOutputs";
import { attemptCount, type ResearchAction } from "./research-ui";

const phaseLabels: Record<ResearchPhase, string> = {
  'quality-plan': '기여·근거 보완 설계', 'quality-write': '근거를 반영한 원고 보완', 'quality-review': '항목별 독립 품질 평가',
  "submission-plan": "투고 목표 설정", "manuscript-claim": "실제 관측 결론", "manuscript-repair": "원고 수정 근거",
  "venue-manuscript": "학술지별 원고 작성", "venue-manuscript-repair": "학술지별 작성 응답 꼬리 복구", "venue-manuscript-review": "학술지별 독립 심사",
  "research-questions": "연구 질문 후보", "question-search-plan": "검색 실패 보완 계획", "question-literature": "질문 근거 회수", "question-selection": "연구 질문 선택",
  "question-reframing": "새 연구 질문 제안", "question-reframing-selection": "새 연구 질문 독립 비교",
  idle: "대기", "source-selection": "연구 소스 확인", "source-analysis": "실제 소스 분석", plan: "연구 설계·투고처 선택", redesign: "연구 설계 보완", "redesign-plan": "새 연구안 준비", "redesign-review": "재설계 준비 검토", "literature-plan": "투고 근거 보완 계획", literature: "문헌 수집", "study-review": "연구 적합성 검토", code: "실험 코드 작성",
  "code-review": "실험 코드 리뷰", experiment: "과학실험", "evidence-selection": "설명 근거 확인", manuscript: "원고 작성",
  "manuscript-review": "원고 품질 검토", export: "결과 파일 생성",
};
const pipelineLabels = { idle: "대기", running: "진행 중", paused: "중단됨", failed: "실패", completed: "투고 준비 완료" };
const verifiedSubmission = (value: SubmissionReadiness | null) => value?.ready === true && value.status === "ready" &&
  value.science_verified === true && value.venue_verified === true && value.formats_verified === true && value.visual_verified === true && value.author_verified === true;
const studyHoldCodes = ["STUDY_REJECTED", "STUDY_INFEASIBLE", "STUDY_REDESIGN_REJECTED", "STUDY_REDESIGN_LIMIT", "RESEARCH_QUESTION_UNSUPPORTED", "QUESTION_PREPARATION_INCOMPLETE", "QUESTION_SELECTION_HELD"];
const questionReframingMessages: Record<NonNullable<ResearchItem["redesignQuestionReframingStatus"]>, string> = {
  planning: "보류된 기존 질문과 보존된 원문을 바탕으로, 실질적으로 다른 새 연구 질문을 제안하고 있습니다.",
  proposed: "새 연구 질문 제안을 보존했습니다. 독립 비교에서 연구 기여·중요성·검증 가능성을 판단할 차례입니다.",
  reviewing: "제안된 새 질문을 기존 질문·설계 및 보존된 원문과 독립 비교하고 있습니다.",
  ready: "독립 비교에서 새 질문을 후보 작성 대상으로 선택했습니다. 별도 연구 설계와 적합성 검토가 이어집니다.",
  held: "이번 질문 보완에서도 근거를 갖춘 후속 후보를 선택하지 못했습니다. 보류 판정과 필요한 근거를 보존했습니다.",
  incomplete: "새 질문의 제안 또는 독립 비교를 완료하지 못했습니다. 기존 보류 판정과 이번 시도 기록을 보존했습니다.",
};
const questionLiteratureFollowupMessages: Record<NonNullable<ResearchItem["questionLiteratureFollowupStatus"]>, string> = {
  planning: "보존된 초기 검색 실패를 바탕으로 한 번의 문헌 보완 계획을 작성하고 있습니다.",
  planned: "문헌 보완 계획을 보존했습니다. 남은 한 번의 수집을 진행할 수 있습니다.",
  ready: "보완 원문을 확보했습니다. 기존 연구 질문의 최초 독립 비교를 진행할 수 있습니다.",
  held: "이번 보완에서 필요한 근거를 확보하지 못했습니다. 원 질문과 보류 이유를 보존했습니다.",
  incomplete: "이번 보완을 완료하지 못했습니다. 예약과 원자료를 보존하고 같은 시도를 반복하지 않습니다.",
};
const manuscriptCriterionLabels = {
  contribution: "연구 기여", literature: "문헌 사용", interpretation: "결과 해석", presentation: "내용과 분량",
};
const articleTypeLabels = { empirical: "실증 연구", finite_enumeration: "유한 입력 전체 검증", formal: "형식적 증명" };
const outcomeLabels = { positive: "긍정 결과", negative: "부정 결과", null: "차이 미확인", mixed: "혼합 결과" };
const ledgerEventLabels: Record<string, string> = { "study-review": "연구 적합성 평가", "manuscript-review": "원고 품질 평가", "manuscript-repair": "원고 수정 기록", "submission-contract": "투고 목표 설정" };
const ledgerCriterionLabels: Record<string, string> = { ...manuscriptCriterionLabels, question: "연구 질문", comparison: "비교 설계", sampling: "표본 범위", feasibility: "실행 가능성", novelty: "신규성", significance: "중요성", validation: "검증 근거", claim_scope: "실제 주장 범위" };
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

function QualityReview({ title, review, criteria, selectedSources, kind, manuscriptAvailable = false }: {
  title: string; review: { accepted: boolean; issues: string[]; publication_readiness?: PublicationReadiness | null };
  criteria: Array<{ label: string; judgment: ReviewCriterion }>; selectedSources?: number;
  kind: "preparation" | "study" | "manuscript"; manuscriptAvailable?: boolean | null;
}) {
  const readinessTitle = kind === "study" ? "연구 기여 가능성 평가" : manuscriptAvailable ? "실제 원고 투고 준비도" : "원고 검토 기록";
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
      {kind === "preparation" ? <p className="detail-note mt-3">새 연구안을 준비할 수 있는지 검토한 기록입니다. 문헌 수집·연구 적합성·실험 코드 검토를 거쳐야 실험을 실행할 수 있습니다. 투고 준비도는 원고에서 따로 평가합니다.</p> : review.publication_readiness ? <section className="mt-4 space-y-3" aria-label={readinessTitle}>
        <h4 className="font-semibold">{readinessTitle}</h4>
        {kind === "study" && <p className="detail-note">설계의 신규성·중요성·예정된 검증 범위를 평가한 기록입니다. 실제 원고의 투고 준비도는 원고 작성 후 평가합니다.</p>}
        <dl className="space-y-3">
          {[
            { label: "선행 연구 대비 신규성", judgment: review.publication_readiness.novelty },
            { label: "기여의 중요성", judgment: review.publication_readiness.significance },
            { label: "주장 범위에 맞는 검증", judgment: review.publication_readiness.validation },
          ].map(({ label, judgment }) => <div key={label}>
            <dt className="font-semibold">{label} · {judgment.passed ? "충족" : "미충족"}</dt>
            <dd className="detail-note mt-1 whitespace-pre-wrap">{judgment.reason}</dd>
          </div>)}
          <div><dt className="font-semibold">핵심 주장</dt><dd className="detail-note mt-1 whitespace-pre-wrap">{review.publication_readiness.claim}</dd></div>
          <div><dt className="font-semibold">적용 범위</dt><dd className="detail-note mt-1 whitespace-pre-wrap">{review.publication_readiness.scope}</dd></div>
          <div><dt className="font-semibold">검증 근거 · {{ formal: "이론·증명", empirical: "경험적 평가", finite_enumeration: "유한 공간 완전 열거" }[review.publication_readiness.evidence_mode]}</dt>
            <dd className="detail-note mt-1 whitespace-pre-wrap">{review.publication_readiness.evidence_basis}</dd></div>
        </dl>
        {review.publication_readiness.closest_work.map((work, index) => <details key={`${work.source_id}:${work.excerpt_index}`} className="detail-note">
          <summary>직접 관련 선행 연구 비교 {index + 1}</summary>
          <p className="mt-2 whitespace-pre-wrap">알려진 결과: {work.known_result}</p>
          <p className="mt-2 whitespace-pre-wrap">이번 연구의 차이: {work.difference}</p>
          <blockquote className="mt-2 border-l-2 border-border pl-3 whitespace-pre-wrap">{work.quote}</blockquote>
        </details>)}
      </section> : <p className="detail-note mt-3">이 기록에는 신규성·기여의 중요성·검증 범위를 평가한 {kind === "study" ? "연구 기여 가능성" : "실제 원고 투고 준비도"} 검토가 없습니다.</p>}
      {review.issues.length > 0 && <div className="mt-3">
        <p className="font-semibold">보완할 내용</p>
        <ul className="mt-1 list-disc space-y-1 pl-5">{review.issues.map((issue, index) => <li key={index}>{issue}</li>)}</ul>
      </div>}
    </details>
  );
}

function statusLabel(job: ResearchItem, publication: RepositoryPublicationStatus | null): string {
  const quality = job.repositoryPaper?.manuscript_improvement;
  if (quality) return job.pipeline === 'running' ? `진행 중 · ${phaseLabels[job.phase]}`
    : !quality.finished ? '원고 품질 보완 진행 기록' : quality.target_achieved ? '항목별 목표 달성 · 투고 전 최종 확인'
      : Object.values(quality.recommendations ?? {}).some(item => item.recommendation === 'consider_submission')
        ? '목표 일부 미달 · 매체별 투고 권고 확인' : '항목별 목표 미달 · 투고 전 보완 필요';
  const portfolio = job.repositoryPaper?.portfolio;
  if (portfolio && job.pipeline !== 'running') return portfolio.all_content_ready
    ? 'IEEE 매체별 내용 심사 충족' : `매체별 심사 기록 ${portfolio.completed}/${portfolio.total}`;
  if (publication) return job.pipeline === "running" ? `진행 중 · ${phaseLabels[job.phase]}` : publication.label;
  if (job.code === "SUBMISSION_PENDING") return "투고처·원고 검수 대기";
  if (job.pipeline === "completed" && !verifiedSubmission(job.submissionReadiness)) return "보존된 원고·투고 확인 필요";
  if (job.pipeline !== "running" && studyHoldCodes.includes(job.code ?? "")) return "연구 보류";
  if (job.pipeline !== "running" && ["MANUSCRIPT_REJECTED", "MANUSCRIPT_NO_PROGRESS"].includes(job.code ?? "")) return "원고 보류";
  return pipelineLabels[job.pipeline];
}

export function ResearchResultCard({ job, locked, canWork, analysisReady, cleanupPending, runtimeChecking, pending, model, reviewerModel, runAction }: {
  job: ResearchItem; locked: boolean; canWork: boolean; analysisReady: boolean; cleanupPending: boolean;
  runtimeChecking: boolean; pending: string | null; model: string; reviewerModel: string; runAction: ResearchAction;
}) {
  const publication = job.researchMode === NEW_RESEARCH_MODE && !job.repositoryPaper?.portfolio ? inspectRepositoryPublication(job) : null;
  const submissionVerified = job.pipeline === "completed" && verifiedSubmission(job.submissionReadiness);
  const canResume = job.researchMode === NEW_RESEARCH_MODE && publication?.stage !== "human_hold" &&
    ["idle", "paused", "failed"].includes(job.pipeline) && !!job.resumeKind && !cleanupPending &&
    job.status !== "blocked" && !studyHoldCodes.includes(job.code ?? "");
  return (
    <article key={job.id} id={job.id} tabIndex={-1} className="space-y-3 rounded-base border-2 border-border bg-secondary-background p-4" aria-labelledby={`${job.id}-label`}>
      <div className="section-heading">
        <h3 id={`${job.id}-label`} className="font-semibold break-words">{job.source.split("/").filter(Boolean).at(-1) || job.id}</h3>
        <Badge variant={submissionVerified ? "default" : "neutral"}>{statusLabel(job, publication)}</Badge>
      </div>
      <p className="detail-note break-all">{job.source}</p>
      {job.researchMode !== NEW_RESEARCH_MODE && <p className="detail-note">과거 실험 연구 · 읽기 전용. 원자료·심사·횟수와 당시 상태를 보존합니다.</p>}
      <details className="detail-note"><summary>연구 목표</summary><p className="mt-2 whitespace-pre-wrap">{job.goal}</p></details>
      <RepositoryPaperDetails job={job} publication={publication} disabled={!canWork} runAction={runAction} />
      <RepositoryPortfolioDetails job={job} disabled={!canWork} locked={locked} runAction={runAction} />
      {job.submissionContract && <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="저장된 투고 목표">
        <h4 className="font-semibold">저장된 투고 목표</h4>
        <p>{articleTypeLabels[job.submissionContract.value.article_type]} · {job.submissionContract.value.language}</p>
        <p className="whitespace-pre-wrap">대상 독자: {job.submissionContract.value.target_audience}</p>
        <p className="whitespace-pre-wrap">계획한 기여: {job.submissionContract.value.core_claim}</p>
        <ul className="space-y-2">{job.submissionContract.value.claim_obligations.map(obligation => <li key={obligation.id}>
          <p className="font-semibold">{obligation.claim}</p><p className="detail-note whitespace-pre-wrap">필요한 근거: {obligation.required_evidence}</p>
        </li>)}</ul>
        <p className="font-semibold">미검증 투고처 후보</p>
        <ul className="space-y-2">{job.submissionContract.value.venue_candidates.map(venue => <li key={venue.name}>
          <p>{venue.name} · 공식 요건 확인 대기</p><p className="detail-note whitespace-pre-wrap">{venue.rationale}</p>
        </li>)}</ul>
        <p className="detail-note">후보 제안은 학술지의 공식 요건 검수나 투고 승인이 아닙니다.</p>
      </section>}
      {(job.plannedClaim || job.manuscriptClaim) && <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="계획 가설과 실제 관측 결론">
        <h4 className="font-semibold">계획 가설과 실제 관측 결론</h4>
        {job.plannedClaim && <p className="whitespace-pre-wrap">계획 가설: {job.plannedClaim.claim}<br />계획 범위: {job.plannedClaim.scope}</p>}
        {job.manuscriptClaim ? <><p className="whitespace-pre-wrap">실제 결론 ({outcomeLabels[job.manuscriptClaim.value.outcome]}): {job.manuscriptClaim.value.claim}</p>
          <p className="whitespace-pre-wrap">관측으로 뒷받침되는 범위: {job.manuscriptClaim.value.scope}</p>
          <p className="detail-note whitespace-pre-wrap">{job.manuscriptClaim.value.scope_justification}</p></> : <p className="detail-note">아직 실제 관측 결론이 동결되지 않았습니다. 계획 가설은 관측 결과가 아닙니다.</p>}
      </section>}
      {job.submissionReadiness && <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="실제 투고 완료 조건">
        <h4 className="font-semibold">실제 투고 완료 조건 · {verifiedSubmission(job.submissionReadiness) ? "확인 완료" : "확인 대기"}</h4>
        <dl className="grid gap-1 sm:grid-cols-2">{[
          ["과학 근거·원고", job.submissionReadiness.science_verified], ["투고처 공식 요건", job.submissionReadiness.venue_verified],
          ["출력 형식", job.submissionReadiness.formats_verified], ["출력 화면 검수", job.submissionReadiness.visual_verified], ["저자 확인", job.submissionReadiness.author_verified],
        ].map(([label, passed]) => <div key={String(label)}><dt className="inline font-semibold">{label}: </dt><dd className="inline">{passed === true ? "확인" : passed === false ? "대기" : "미확인"}</dd></div>)}</dl>
        {job.submissionReadiness.blockers.length > 0 && <ul className="space-y-1">{job.submissionReadiness.blockers.map((blocker, index) => <li key={index} className="detail-note whitespace-pre-wrap">{blocker}</li>)}</ul>}
        {!verifiedSubmission(job.submissionReadiness) && <p className="detail-note">다음 작업: 표시된 공식 요건·출력·저자 확인을 마쳐야 투고 준비 완료로 표시합니다. 기존 원고와 실험 자료는 보존됩니다.</p>}
      </section>}
      <AuthorMetadataEditor job={job} disabled={locked || !analysisReady} runAction={runAction} />
      {job.researchLedger && job.researchLedger.entries.length > 0 && <details className="rounded-base border-2 border-border p-3 text-sm">
        <summary>누적 판단·보완 기록 {job.researchLedger.entries.length}개</summary>
        <ul className="mt-2 space-y-2">{job.researchLedger.entries.map((entry, index) => <li key={index}>
          <p className="font-semibold">{ledgerEventLabels[String(entry.event)] ?? String(entry.event ?? entry.kind ?? "보존된 판단")}</p>
          {Array.isArray(entry.failed_criteria) && entry.failed_criteria.length > 0 && <p className="detail-note">미해결 기준: {entry.failed_criteria.map(value => ledgerCriterionLabels[String(value)] ?? String(value)).join(", ")}</p>}
          {typeof entry.reason === "string" && <p className="detail-note whitespace-pre-wrap">{entry.reason}</p>}
          {entry.repeated_failure === true && <p className="detail-note">동일한 실패가 반복되었습니다.</p>}
          {entry.stop_required === true && <p className="detail-note">해결할 실제 변경이나 새 근거 없이 같은 원고를 반복하지 않습니다.</p>}
        </li>)}</ul>
      </details>}
      <dl className="grid gap-1 text-xs">
        <div><dt className="inline font-semibold">작업 단계: </dt><dd className="inline">{phaseLabels[job.phase]} ({job.phase})</dd></div>
        <div><dt className="inline font-semibold">엔진 단계·상태: </dt><dd className="inline">{job.stage} · {job.status}</dd></div>
        <div><dt className="inline font-semibold">작성·리뷰 모델: </dt><dd className="inline">{job.model} · {job.reviewerModel}</dd></div>
        <div><dt className="inline font-semibold">연구 ID: </dt><dd className="inline">{job.id}</dd></div>
      </dl>
      <section aria-label="연구 진행 횟수" className="rounded-base border-2 border-border p-3 text-sm">
        <dl className="grid gap-2 sm:grid-cols-2">
          {(job.researchMode === "repository_analysis" ? [
            ["분석 설계", attemptCount(job.proposalAttempt)],
            ["문헌 조사", attemptCount(job.studyLiteratureAttempt, 3)],
            ["공통 소스 분석", attemptCount(job.repositoryPaper?.analysis_attempts ?? 0, 3)],
            ["매체별 원고 작성", `${job.repositoryPaper?.portfolio?.venues.reduce((sum, venue) => sum + venue.draft_attempts, 0) ?? 0}회`],
            ["보존한 매체별 원고", `${job.repositoryPaper?.portfolio?.venues.reduce((sum, venue) => sum + venue.admitted_drafts, 0) ?? 0}개`],
            ["매체별 독립 평가", `${job.repositoryPaper?.portfolio?.venues.reduce((sum, venue) => sum + venue.review_attempts, 0) ?? 0}회`],
          ] : [
            ["정식 설계 제출", attemptCount(job.proposalAttempt, 3)],
            ["문헌 보완", attemptCount(job.studyLiteratureAttempt, 3)],
            ["초기 문헌 보완 계획", attemptCount(job.questionLiteratureFollowupPlans ?? null, 1)],
            ["초기 문헌 보완 회수", attemptCount(job.questionLiteratureFollowupCollections ?? null, 1)],
            ["질문 근거 회수", attemptCount(job.redesignQuestionEvidenceCollections, 1)],
            ["검색 보완 계획", attemptCount(job.redesignQuestionSearchRepairPlans, 1)],
            ["검색 보완 회수", attemptCount(job.redesignQuestionSearchRepairCollections, 1)],
            ["새 질문 제안", attemptCount(job.redesignQuestionReframingPlans, 1)],
            ["새 질문 독립 비교", attemptCount(job.redesignQuestionReframingComparisons, 1)],
            ["실험 코드 작성", attemptCount(job.codeAttempt)],
            ["과학실험 실행", attemptCount(job.executionAttempt, 1)],
            ["원고 작성", attemptCount(job.draftAttempt)],
            ["연구 설계 보완", attemptCount(job.redesignAttempt, 2)],
            ["후보 세부 보완", attemptCount(job.preparationRepairAttempt, 1)],
          ]).map(([label, value]) => <div key={label}>
            <dt className="inline font-semibold">{label}: </dt><dd className="inline">{value}</dd>
          </div>)}
        </dl>
        <p className="detail-note mt-2">{job.researchMode === "repository_analysis"
          ? "사용한 조사·원고 횟수와 모든 원문·원고·검토를 보존합니다. 원고 검토는 학술지 심사와 별개입니다."
          : "초기 문헌 조사는 문헌 보완 횟수에 포함되지 않습니다. 설계 제출 횟수와 학술지 심사는 별개입니다. 기존 횟수와 결과는 보존됩니다."}</p>
      </section>
      {job.questionLiteratureFollowupStatus && <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="초기 문헌 보완">
        <h4 className="font-semibold">초기 문헌 보완</h4>
        <p role="status">{questionLiteratureFollowupMessages[job.questionLiteratureFollowupStatus]}</p>
        <p className="detail-note">원 연구 질문과 초기 검색 기록은 보존됩니다. 문헌 확보 후에도 별도 질문·설계·실험·원고 검토가 필요합니다.</p>
      </section>}
      {job.redesignQuestionReframingStatus && <section className="space-y-2 rounded-base border-2 border-border p-3 text-sm" aria-label="새 연구 질문 검토">
        <h4 className="font-semibold">새 연구 질문 검토</h4>
        <p role="status">{questionReframingMessages[job.redesignQuestionReframingStatus]}</p>
        <p className="detail-note">기존 질문과 보류 판정은 그대로 보존됩니다. 새 질문 선택 후에도 별도 설계·실험·원고 검토를 거쳐야 투고 준비도를 평가할 수 있습니다.</p>
      </section>}
      <p className="detail-note">{job.manuscriptAvailable === null ? "원고 확인 필요: 연구 기록을 확인한 뒤 실제 원고 유무를 표시합니다." : job.manuscriptAvailable ? "실제 원고가 보존되어 있습니다. 원고 검토 결과에서 투고 준비도를 확인하세요." : "아직 실제 원고가 없습니다. 투고 준비도는 원고 작성 후 평가합니다."}</p>
      {(job.parentResearchId || job.followupResearchId) && <nav className="flex flex-wrap gap-4 text-sm" aria-label="연결된 연구">
        {job.parentResearchId && <a className="font-semibold underline underline-offset-4" href={`#${job.parentResearchId}`}>이전 연구 보기</a>}
        {job.rootResearchId !== job.id && job.rootResearchId !== job.parentResearchId && <a className="font-semibold underline underline-offset-4" href={`#${job.rootResearchId}`}>최초 연구 보기</a>}
        {job.followupResearchId && <a className="font-semibold underline underline-offset-4" href={`#${job.followupResearchId}`}>후속 연구 보기</a>}
      </nav>}
      {job.message && <p className="detail-note">{job.message}</p>}
      {job.code && <p className="detail-note">상태 코드: {job.code}</p>}
      {job.preparationRedesignReview && <QualityReview title="새 연구안 준비 검토" review={job.preparationRedesignReview} kind="preparation" criteria={[
        { label: "이전 연구와의 과학적 차이", judgment: job.preparationRedesignReview.scientific_difference },
        { label: "이전 결과와 근거의 보존", judgment: job.preparationRedesignReview.prior_evidence },
        { label: "실행 가능성과 주장 범위", judgment: job.preparationRedesignReview.feasibility },
      ]} />}
      {job.preparationRepair && <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label="후보 세부 보완 기록">
        <h4 className="font-semibold">동일 후보의 절차·분석 방법 보완 · 1/1회</h4>
        <p className="detail-note">원 후보와 반려 심사는 보존되어 있습니다. 이전 통과 판정을 승계하지 않고 세 기준을 모두 새로 검토합니다. 연구 기여·신규성·중요성과 실제 관측은 별도 검증이 필요합니다.</p>
        {job.preparationRepair.value.changes.map(change => <div key={change.issue_index} className="space-y-1">
          <p className="font-semibold">원 심사 문제 {change.issue_index + 1}</p>
          <p className="detail-note whitespace-pre-wrap">{change.required_change}</p>
          <p className="detail-note whitespace-pre-wrap">보완 설명: {change.actual_change}</p>
          <p className="detail-note">변경 필드: {change.changed_fields.map(field => field === "procedure" ? "실행 절차" : "분석 방법").join(", ")}</p>
        </div>)}
        {job.preparationOriginal && <>
          <QualityReview title="보완 전 준비 심사 원문" review={job.preparationOriginal.review} kind="preparation" criteria={[
            { label: "이전 연구와의 과학적 차이", judgment: job.preparationOriginal.review.scientific_difference },
            { label: "이전 결과와 근거의 보존", judgment: job.preparationOriginal.review.prior_evidence },
            { label: "실행 가능성과 주장 범위", judgment: job.preparationOriginal.review.feasibility },
          ]} />
          <details><summary>보완 전 후보·부모 수정 설명 원문</summary>
            <pre className="mt-2 whitespace-pre-wrap break-all">{JSON.stringify({ candidate: job.preparationOriginal.candidate, parentRepair: job.preparationOriginal.repair }, null, 2)}</pre>
          </details>
        </>}
        <div className="flex flex-wrap gap-2">{["redesign-candidate", "redesign-review", "redesign-repair"].filter(id => job.artifacts.some(artifact => artifact.id === id)).map(id =>
          <Button key={id} variant="outline" size="sm" disabled={locked} onClick={() => void runAction("open", () => window.paperFactory.openArtifact(job.id, id))}>
            {{ "redesign-candidate": "원 후보 원문 열기", "redesign-review": "원 준비 심사 원문 열기", "redesign-repair": "부모 수정 설명 원문 열기" }[id]}
          </Button>)}</div>
      </section>}
      {job.studyReview && <QualityReview title="연구 적합성 검토" review={job.studyReview} kind="study"
        selectedSources={job.studyReview.selected_sources.length} criteria={[
          { label: "연구 질문", judgment: job.studyReview.question },
          { label: "새로운 기여", judgment: job.studyReview.contribution },
          { label: "관련 문헌", judgment: job.studyReview.literature },
          { label: "비교 대상", judgment: job.studyReview.comparison },
          { label: "표본과 실험 설계", judgment: job.studyReview.sampling },
          { label: "실행 가능성과 주장 범위", judgment: job.studyReview.feasibility },
        ]} />}
      {job.manuscriptReview && <QualityReview title="원고 품질 검토" review={job.manuscriptReview} kind="manuscript" manuscriptAvailable={job.manuscriptAvailable} criteria={[
        { label: "연구 기여", judgment: job.manuscriptReview.contribution },
        { label: "문헌 사용", judgment: job.manuscriptReview.literature },
        { label: "결과 해석", judgment: job.manuscriptReview.interpretation },
        { label: "내용과 분량", judgment: job.manuscriptReview.presentation },
        ...(job.manuscriptReview.claim_scope ? [{ label: "실제 결론과 범위의 근거", judgment: job.manuscriptReview.claim_scope }] : []),
      ]} />}
      {job.manuscriptReview?.remediation && <ManuscriptRecovery remediation={job.manuscriptReview.remediation} />}
      {job.pipeline === "completed" && !job.studyReview && <p className="detail-note">이 결과에는 현재 기준의 연구 적합성 검토 기록이 없습니다.</p>}
      {job.pipeline === "completed" && !job.manuscriptReview && <p className="detail-note">이 결과에는 현재 기준의 원고 품질 검토 기록이 없습니다.</p>}
      {studyHoldCodes.includes(job.code ?? "") && job.pipeline !== "running" && <p className="detail-note" role="status">{job.followupResearchId
        ? "이 연구의 설계와 검토 기록을 보존하고 별도 후속 연구를 만들었습니다. 후속 연구에서 새 설계의 적합성을 검토합니다."
        : "현재 설계의 근거가 부족해 실험과 원고 생성을 진행하지 않았습니다. 검토 이유와 이어갈 수 있는 보완 작업을 확인하세요."}</p>}
      {job.code === "MANUSCRIPT_REJECTED" && job.pipeline !== "running" && <p className="detail-note" role="status">{job.followupResearchId
        ? "원고와 실험 결과를 보존하고, 검토 내용에 따라 별도 후속 연구를 만들었습니다. 후속 연구에서 설계를 보완하며 이전 실험 결과는 변경하지 않습니다."
        : "원고가 품질 검토를 통과하지 못해 결과 파일을 생성하지 않았습니다. 보완 방향과 검토 이유를 확인하세요. 이전 실험 결과는 보존됩니다."}</p>}
      {cleanupPending && job.pipeline !== "running" && (
        <p className="detail-note" role="status">실험 종료와 기록 보존을 확인해야 새 연구와 계정 변경을 할 수 있습니다. 로그인 없이 정리 확인을 다시 시도할 수 있습니다.</p>
      )}
      <div className="action-row">
        {job.pipeline === "running" && (
          <Button variant="outline" disabled={pending !== null}
            onClick={() => void runAction("cancel", () => window.paperFactory.cancelResearch(job.id))}>연구 취소</Button>
        )}
        {cleanupPending && job.pipeline !== "running" && (
          <Button variant="outline" disabled={pending !== null || runtimeChecking}
            onClick={() => void runAction("cancel", () => window.paperFactory.cancelResearch(job.id))}>
            {pending === "cancel" ? "정리 확인 중…" : "정리 다시 확인"}
          </Button>
        )}
        {job.researchMode === NEW_RESEARCH_MODE && publication?.stage !== "human_hold" && job.improvementAvailable && job.stage === "repository_manuscript" &&
          ["idle", "paused", "failed"].includes(job.pipeline) && (
          <Button variant="outline" disabled={!canWork}
            onClick={() => void runAction("improve", () => window.paperFactory.improveResearch(job.id, model, reviewerModel))}>
            {job.repositoryPaper?.assessment_available ? "실무 선행 비교·기여 보완" : "원고 보완 이어가기"}
          </Button>
        )}
        {canResume && (
          <Button variant="outline" disabled={!canWork}
            onClick={() => void runAction("resume", () => window.paperFactory.resumeResearch(job.id, model, reviewerModel))}>
            {job.stage === "repository_planned" && job.resumeKind === "preparation" &&
              [1, 2].includes(job.draftAttempt ?? 0) ? "원고 보완 이어가기"
              : job.resumeKind === "preparation" ? "연구 준비 재개" : "원고 검토 재개"}
          </Button>
        )}
      </div>
      {job.researchMode === NEW_RESEARCH_MODE && job.improvementAvailable && <p className="detail-note">검토에서 지정한 원문 분석·문헌·원고 내용을 실제로 보완합니다. 이전 원고와 검토, 사용한 횟수는 보존됩니다.</p>}
      {(["created", "proposed", "planned", "analyzed"].includes(job.stage) || job.supportingDocuments.length > 0) && (
        <div className="space-y-2">
          <p className="detail-note">당시 가져온 첨부 문서의 이름과 크기입니다. 원자료·심사·횟수와 함께 보존합니다.</p>
          <details className="detail-note"><summary>첨부 근거 {job.supportingDocuments.length}개</summary>
            {job.supportingDocuments.length === 0 ? <p className="mt-2">첨부된 근거 문서가 없습니다.</p> :
              <ul className="mt-2 space-y-1">{job.supportingDocuments.map(document =>
                <li key={document.id}>{document.name} · {document.size.toLocaleString("ko-KR")} 바이트</li>)}</ul>}
          </details>
        </div>
      )}
      <ResearchOutputs job={job} publication={publication} locked={locked} analysisReady={analysisReady} runAction={runAction} />
    </article>
  );
}
