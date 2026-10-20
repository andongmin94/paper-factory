import type { ResearchItem } from '../shared/research';
import { improvementCriterionLabels, developmentPurposeLabels, type ImprovementPurpose,
  type ManuscriptImprovement as ImprovementState } from '../shared/manuscript-improvement';
import { Button } from './components/ui/button';
import { JournalCompliance } from './JournalCompliance';
import { ResearchDevelopment } from './ResearchDevelopment';
import type { ResearchAction } from './research-ui';

const venueNames: Record<string, string> = { 'ieee-software': 'IEEE Software', 'ieee-security-privacy': 'IEEE Security & Privacy' };
const recommendationLabels = { consider_submission: '투고 검토 권장', revise_before_submission: '투고 전 보완 필요', not_recommended: '현재 투고 비권장' };
const stopLabels: Record<string, string> = { target_achieved: '항목별 목표 달성', budget_exhausted: '전체 보완 예산 도달',
  planned_actions_completed: '계획한 보완 작업 완료', bounded_actions_unavailable: '남은 범위에서 보완 경로 없음', work_remaining: '보완 진행 가능' };
const fileLabels: Record<string, string> = { docx: 'Word', pdf: 'PDF', md: 'Markdown', markdown: 'Markdown' };
const purposeLabels: Record<ImprovementPurpose, string> = { plan: '보완 계획', revise: '원고 보완', review: '독립 평가',
  'focused-select': '선행 방법·소스 선택', 'focused-analyze': 'Paste·Autosave 분석',
  'focused-write': '두 매체 원고 보완', 'focused-review': '독립 품질 평가',
  ...developmentPurposeLabels };
const focusedStages = ['focused-select', 'focused-analyze', 'focused-write', 'focused-review'] as const;

function FocusedRound({ state, job, disabled, runAction }: { state: ImprovementState; job: ResearchItem; disabled: boolean; runAction: ResearchAction }) {
  const round = state.focused_round;
  if (!round) return null;
  const calls = state.calls.filter(call => call.round_id === round.id);
  return <section className="space-y-3 rounded-base border-2 border-border p-3" aria-label="추가 근거·투고규정 보완">
    <h5 className="font-semibold">근거·투고규정 보완 · 추가 최대 4회</h5>
    <p role="status">이번 요청 시도 {calls.length}/{round.additional_call_limit}회 · {round.closed ? '종료' : '진행 중'}</p>
    <ol className="list-decimal space-y-1 pl-5">{focusedStages.map(purpose => {
      const call = calls.find(item => item.purpose === purpose);
      const status = round.completed_stages.includes(purpose) ? '완료' : call?.outcome === 'reserved' ? '진행 중'
        : call?.outcome === 'completed' ? '수락 확인 미완료' : call ? '실패·기록 보존' : round.closed ? '미진행' : '대기';
      return <li key={purpose}>{purposeLabels[purpose]} · {status}</li>;
    })}</ol>
    {Object.entries(round.analysis_repairs ?? {}).map(([callId, repair]) => <p className="detail-note" key={callId}>
      {repair.outcome === 'admitted' ? '분석 자료 분류 복구 완료' : '분석 자료 분류 복구 검증 거절'} · 이 분류 복구의 추가 모델 요청 0회.
      {' '}기존 응답의 저장소 근거와 논문 원문 근거를 분리해 다시 검증했습니다. 원래 거절 응답·오류·사용 횟수는 보존합니다.</p>)}
    {Object.entries(round.writer_repairs ?? {}).map(([callId, repair]) => <p className="detail-note" key={callId}>
      {repair.outcome === 'admitted' ? '원고 인용 분류 복구 완료' : '원고 인용 분류 복구 검증 거절'} · 이 분류 복구의 추가 모델 요청 0회.
      {' '}기존 논문 원문 근거의 인용 종류를 바로잡고 같은 원고를 다시 검증했습니다. 과학적 주장·근거 인용문·원래 거절 응답·오류·사용 횟수는 보존합니다.</p>)}
    {round.primary_collection && <details><summary>확보한 PDF 원문 {round.primary_collection.retained_full_bodies}개</summary>
      <ul className="mt-2 space-y-2">{round.primary_collection.sources.map(source => <li key={source.id}>
        <a href={source.url} target="_blank" rel="noreferrer" className="break-all underline">{source.title ?? source.url}</a>
        {' · '}{source.status === 'retained' ? '원문 보존' : source.status === 'failed' ? '확보 실패' : '확보 대기'}
        {source.failure && <p className="detail-note">{source.failure}</p>}
      </li>)}</ul>
    </details>}
    {[['완료한 분석 결과', round.analysis_artifact_id], ['유한 모형 검사 결과', round.checker_artifact_id]].map(([label, id]) =>
      id && job.artifacts.some(artifact => artifact.id === id) && <div key={id} className="action-row">
        <Button variant="outline" size="sm" disabled={disabled} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, id))}>{label} 저장</Button>
        <Button variant="ghost" size="sm" disabled={disabled} onClick={() => void runAction('open', () => window.paperFactory.openArtifact(job.id, id))}>{label} 열기</Button>
      </div>)}
    {round.checker_artifact_id && <p className="detail-note">유한 모형의 도달 상태·불변식 검사 결과를 보존합니다. 프로젝트 실행 횟수는 별도로 유지합니다.</p>}
    {Object.entries(round.format_preflight ?? {}).map(([venue, item]) => <details key={venue}>
      <summary>{venueNames[venue] ?? venue} 새 보완 원고 선검사 · {item.content_format_passed ? '충족' : '보완 필요'}</summary>
      <div className="mt-2"><JournalCompliance report={item.report.compliance ?? item.report.pure} /></div>
      {item.report.errors.map((error, index) => <p className="detail-note" key={index}>
        {fileLabels[error.format] ?? error.format} 출력: {error.error}</p>)}
    </details>)}
    {Object.entries(round.format_blocked ?? {}).map(([venue, reason]) => <p className="detail-note" key={venue}>
      {venueNames[venue] ?? venue} 원고 형식 보완 필요 · {reason}</p>)}
  </section>;
}

export function ManuscriptImprovement({ job, disabled, runAction }: { job: ResearchItem; disabled: boolean; runAction: ResearchAction }) {
  const state = job.repositoryPaper?.manuscript_improvement;
  const available = job.stage === 'repository_manuscript' && job.repositoryPaper?.portfolio?.analysis;
  if (!available) return null;
  return <section className="space-y-3 rounded-base border-2 border-border p-3 text-sm" aria-label="원고 품질 보완">
    <h4 className="font-semibold">기여와 근거를 보완하고 항목별로 평가</h4>
    <p className="detail-note">항목별 9/10을 목표로 합니다. 원래 외부 GPT의 세부 평가표가 제공되지 않아 명시한 9개 항목으로 평가하며, 점수는 모델의 판단입니다. 기여·근거의 한계와 투고 권고를 별도로 확인하세요.</p>
    <p className="detail-note">기존 자료·원고·심사·횟수를 유지합니다. 기본 8회와 한 번의 근거 보완 4회, 별도로 선택하는 연구 설계·근거 보완 최대 6회는 각 한도에서 진행합니다. 실패와 중단도 예산에 포함하고 진전이 없는 경로는 종료합니다.</p>
    {!state?.finished && <Button variant="outline" disabled={disabled} onClick={() => void runAction('manuscript-improvement',
      () => window.paperFactory.continueManuscriptImprovement(job.id))}>항목별 품질 보완 이어가기</Button>}
    {state?.finished && <Button variant="outline" disabled={disabled} onClick={() => void runAction('manuscript-improvement',
      () => window.paperFactory.continueManuscriptImprovement(job.id))}>최선 원고·공식 출력 다시 확인</Button>}
    {state?.finished && !state.focused_round && !state.research_development && <Button variant="outline" disabled={disabled} onClick={() => void runAction('manuscript-improvement',
      () => window.paperFactory.focusManuscriptImprovement(job.id))}>근거·투고규정 보완 4회</Button>}
    {state?.finished && !state.research_development && <Button variant="outline" disabled={disabled} onClick={() => void runAction('manuscript-improvement',
      () => window.paperFactory.developManuscriptImprovement(job.id))}>연구 설계·근거 보완 (최대 6회)</Button>}
    {state?.finished && state.research_development?.closed && !state.research_development_history?.length && <Button variant="outline" disabled={disabled} onClick={() => void runAction('manuscript-improvement',
      () => window.paperFactory.extendResearchDevelopmentRound(job.id, state.research_development!.id))}>같은 연구에 새 보완 회차 시작 (추가 최대 6회)</Button>}
    {state && <>
      <p role="status">전체 모델 요청 시도 {state.counts?.model_attempts ?? state.calls.length}/{state.policy.model_call_limit}회 · 보완 원고 {state.counts?.revisions ?? 0}개 · 독립 평가 {state.counts?.reviews ?? 0}회</p>
      <FocusedRound state={state} job={job} disabled={disabled} runAction={runAction} />
      <ResearchDevelopment state={state} job={job} disabled={disabled} runAction={runAction} />
      {!!state.counts?.format_repairs && <p className="detail-note">완료 응답의 참고문헌 형식 복구 {state.counts.format_repairs}회 · 추가 모델 호출 0회 · 과학 본문과 원래 실패·횟수 보존</p>}
      <p>9점 목표: {state.target_achieved ? '모든 항목 달성' : '미달성 또는 평가 중'} · {stopLabels[state.stop_reason ?? 'work_remaining'] ?? state.stop_reason}</p>
      {state.calls.some(call => call.error) && <details><summary>보존된 실패·검증 거절</summary>{state.calls.filter(call => call.error).map(call =>
        <p className="detail-note mt-2 whitespace-pre-wrap" key={call.call_id}>{call.venue_id ? venueNames[call.venue_id] : '공통'} · {purposeLabels[call.purpose]} · {call.error}</p>)}</details>}
      {state.evidence_collection && <details><summary>추가 근거 확보 · {state.evidence_collection.sources.filter(source => source.status === 'retained').length}개 원문 보존</summary>
        <p className="detail-note mt-2">{state.evidence_collection.reason}</p>
        {state.evidence_collection.sources.map(source => <p className="detail-note mt-2" key={source.id}>
          <a href={source.url} target="_blank" rel="noreferrer" className="break-all underline">{source.url}</a> · {source.status === 'retained' ? '원문 보존' : '확보 실패'}{source.failure ? ` · ${source.failure}` : ''}</p>)}
      </details>}
      {state.plan && <details><summary className="font-semibold">연구 방향 선택과 실제 보완 계획</summary>
        <p className="mt-2 whitespace-pre-wrap">{state.plan.scope_and_limits}</p>
        {state.plan.directions.map(direction => <div className="mt-3 space-y-1" key={direction.id}>
          <p className="font-semibold">{direction.id === state.plan!.selected_direction_id ? '선택: ' : '검토: '}{direction.reader_problem}</p>
          <p>{direction.added_value}</p><p className="detail-note">기존 접근: {direction.closest_baseline}</p>
          <p className="detail-note">선택 판단: {direction.selection_reason}</p>
        </div>)}
      </details>}
      {Object.entries(state.best_assessments ?? {}).map(([venueId, review]) => <section key={venueId} className="space-y-3 border-t-2 border-border pt-3" aria-label={`${venueNames[venueId] ?? venueId} 품질 평가`}>
        <h5 className="font-semibold">{venueNames[venueId] ?? venueId} · 보존된 최선 원고</h5>
        {review ? <>
          <p className="font-semibold">{recommendationLabels[review.recommendation]}</p><p className="whitespace-pre-wrap">{review.recommendation_reason}</p>
          <table className="w-full text-left"><thead><tr><th>평가 항목</th><th>점수</th><th>불확실성</th></tr></thead><tbody>
            {review.scores.map(score => <tr key={score.criterion}><td>{improvementCriterionLabels[score.criterion]}</td><td>{score.score}/10</td><td>{{ low: '낮음', medium: '보통', high: '높음' }[score.uncertainty]}</td></tr>)}
          </tbody></table>
          {!!review.essential_errors.length && <p className="detail-note">필수 수정: {review.essential_errors.join(' ')}</p>}
          <details><summary>항목별 판단 근거와 남은 문제</summary>{review.scores.map(score => <div key={score.criterion} className="mt-3 space-y-1">
            <p className="font-semibold">{improvementCriterionLabels[score.criterion]} · {score.score}/10</p><p>{score.reason}</p>
            <p className="detail-note">원고 근거: {score.passages.join(' ')}</p>{score.required_improvement && <p>필요한 보완: {score.required_improvement}</p>}
          </div>)}{review.evidence_limits.map((limit, index) => <div key={index} className="mt-3 space-y-1">
            <p>{limit.explanation}</p><p className="detail-note">검토한 대안: {limit.alternatives_attempted.join(' ')}</p><p className="detail-note">확보 가능성: {limit.obtainable_evidence}</p>
          </div>)}</details>
        </> : <p>독립 평가 미완료 · 현재 투고 비권장</p>}
        {Object.entries(state.exports?.[venueId]?.outputs ?? {}).map(([format, output]) => fileLabels[format] && <div key={format} className="action-row">
          <Button variant="outline" size="sm" disabled={disabled} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, output.artifact_id))}>
            {venueNames[venueId] ?? venueId} 개선 원고 {fileLabels[format]} 저장</Button>
          <Button variant="ghost" size="sm" disabled={disabled} onClick={() => void runAction('open', () => window.paperFactory.openArtifact(job.id, output.artifact_id))}>
            {venueNames[venueId] ?? venueId} 개선 원고 {fileLabels[format]} 열기</Button>
        </div>)}
        {state.exports?.[venueId]?.errors.map((error, index) => <p className="detail-note" key={index}>{error.format} 출력: {error.message}</p>)}
        {state.exports?.[venueId]?.compliance && <JournalCompliance report={state.exports[venueId].compliance!} />}
      </section>)}
      {state.finished && <p className="detail-note">최선 원고를 보존하고 종료했습니다. 실제 게재 가능성·저자 승인·투고 접수는 이 평가와 별개입니다.</p>}
      {state.report_artifact_id && job.artifacts.some(artifact => artifact.id === state.report_artifact_id) && <Button variant="outline" disabled={disabled}
        onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, state.report_artifact_id!))}>품질 평가 보고서 저장</Button>}
    </>}
  </section>;
}
