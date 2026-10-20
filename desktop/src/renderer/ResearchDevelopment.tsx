import { developmentPurposeLabels, developmentReasonLabels, type DevelopmentPurpose, type DevelopmentStage, type ManuscriptImprovement } from '../shared/manuscript-improvement';
import type { ResearchItem } from '../shared/research';
import { Button } from './components/ui/button';
import { JournalCompliance } from './JournalCompliance';
import type { ResearchAction } from './research-ui';

const legacyStages: DevelopmentStage[] = ['plan', 'evidence', 'audit', 'repair', 'write', 'review'];
const auditedStages: DevelopmentStage[] = ['design', 'audit', 'repair', 're-audit', 'write', 'review'];
const questionStages: DevelopmentStage[] = ['question', 'design', 'strengthen', 'audit', 'write', 'review'];
const venueNames: Record<string, string> = { 'ieee-software': 'IEEE Software', 'ieee-security-privacy': 'IEEE Security & Privacy' };
const resultLabels: Record<string, string> = { passed: '충족', failed: '반례 있음', vacuous: '전제 미도달', unreachable: '미도달' };
const developmentStatuses = { research_in_progress: '연구 산출물 보완 중', ready_to_write: '집필 단계',
  bounded_research_report: '연구 산출물 보존 · 집필 준비 미완료', manuscripts_unassessed: '새 원고 보존 · 독립 평가 미완료',
  manuscripts_assessed: '새 원고와 독립 평가 보존' };

export function ResearchDevelopment({ state, job, disabled, runAction }: {
  state: ManuscriptImprovement; job: ResearchItem; disabled: boolean; runAction: ResearchAction;
}) {
  const round = state.research_development;
  if (!round) return null;
  const calls = state.calls.filter(call => call.round_id === round.id);
  const audited = round.contract_version === 2 || round.contract_version === 3;
  const stages = round.contract_version === 3 ? questionStages : round.contract_version === 2 ? auditedStages : legacyStages;
  const products = round.work_product_report;
  const productsSaved = Boolean(products?.internal_consistency_passed && round.work_products_artifact_id && round.work_product_report_artifact_id &&
    [round.work_products_artifact_id, round.work_product_report_artifact_id].every(id => job.artifacts.some(artifact => artifact.id === id)));
  const readiness = round.readiness;
  const currentAudit = Boolean(readiness && round.evidence_sha256 &&
    readiness.evidence_sha256 === round.evidence_sha256 && readiness.audit_evidence_sha256 === round.evidence_sha256 &&
    round.audit?.evidence_sha256 === round.evidence_sha256 && round.audit.ready_to_write && !round.audit.repair_required &&
    productsSaved && job.artifacts.some(artifact => artifact.id === readiness.audit_artifact_id));
  const ready = readiness?.ready_to_write === true && currentAudit;
  return <section className="space-y-3 rounded-base border-2 border-border p-3" aria-label="연구 설계·근거 보완">
    <h5 className="font-semibold">연구 설계·근거 보완 · 추가 최대 6회</h5>
    <p>현재 연구 보완 회차: {(state.research_development_history?.length ?? 0) + 1}</p>
    {!!state.research_development_history?.length && <details><summary>보존된 이전 연구 보완 회차 {state.research_development_history.length}개</summary><div className="mt-2 space-y-3">
      {state.research_development_history.map((entry, index) => <section key={entry.id} className="space-y-2">
        <p className="font-semibold">이전 연구 보완 회차 {index + 1} · {entry.value.closed ? '종료' : '보존 상태 확인 필요'}</p>
        <p>요청 시도 {state.calls.filter(call => call.round_id === entry.value.id).length}/{entry.value.additional_call_limit}회 · 기존 자료·원고·심사·횟수 보존</p>
        <p className="detail-note">완료한 작업: {entry.value.completed_stages.map(stage => developmentPurposeLabels[`develop-${stage}`]).join(' · ')}</p>
        {([['이전 연구 근거', entry.value.evidence_artifact_id], ['이전 재현 근거 ZIP', entry.value.supplement?.artifact_id], ['이전 품질 평가 보고서', entry.quality_report_artifact_id]] as const).map(([label, id]) =>
          id && job.artifacts.some(artifact => artifact.id === id) && <Button variant="outline" size="sm" disabled={disabled} key={id}
            onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, id))}>{label} 저장</Button>)}
      </section>)}
    </div></details>}
    <p role="status">이번 연구 보완 요청 시도 {calls.length}/{round.additional_call_limit}회 · {round.closed ? '종료' : '진행 중'}</p>
    {audited && round.status && <p>이번 결과: {developmentStatuses[round.status]}</p>}
    <p className="detail-note">{round.contract_version === 3
      ? '질문 후보를 비교하고 가까운 기존 방법의 실제 자료를 확보한 뒤, 선택 질문에 답할 분석과 비교를 완성합니다. 필요한 내용 보완은 한 번만 수행하고 이후 독립 검토·집필·평가로 이어집니다.'
      : '연구 질문과 결정적인 비교를 설계하고 실제 근거를 만든 뒤 독립 검토합니다. 필요한 근거 수정은 최대 한 번이며, 두 원고 집필과 독립 평가는 각각 한 번입니다.'} 입력 저장소의 프로그램 실행이나 실증 실험으로 기록하지 않습니다.</p>
    {round.contract_version === 3 && <section className="space-y-2" aria-label="선택 질문과 확보한 근거">
      <p>{round.selected_question ? `선택한 질문: ${round.selected_question.question}` : '후보 질문을 실제 확보 근거와 비교합니다.'}</p>
      {round.selected_question && <p>독자에게 필요한 결정: {round.selected_question.reader_decision}</p>}
      {(round.acquisitions ?? []).map((collection, index) => <p key={index}>근거 확보 {index + 1}회: {collection.queries?.join(' · ')} · 완전한 원문 {collection.sources?.length ?? 0}개</p>)}
      {([['질문 후보·확보 계획', round.agenda_artifact_id], ['실제 비교·결과와 집필 근거', round.research_design_artifact_id]] as const).map(([label, id]) =>
        id && job.artifacts.some(artifact => artifact.id === id) && <Button variant="outline" size="sm" disabled={disabled} key={id}
          onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, id))}>{label} 저장</Button>)}
    </section>}
    {audited && <section className="space-y-3" aria-label="완성한 연구 산출물">
      <h6 className="font-semibold">원고를 위해 완성한 연구 산출물</h6>
      <p>{productsSaved ? '연구 산출물의 내부 일관성 검사·보존 완료' : '구체적인 연구 산출물과 검사·보존 확인 대기'}</p>
      <p className="detail-note">기존 방법의 판단과 추가 분석 후의 판단을 구체적으로 비교합니다. 같은 판단이면 추가 기여가 입증되지 않았다는 한계를 남깁니다.</p>
      {products?.products.map(product => <section key={product.id} className="space-y-2 border-t-2 border-border pt-2">
        <p className="font-semibold">{product.kind === 'typed_protocol' ? '소스에 연결한 절차·권한 설계' : '소스에 연결한 대안 비교'} · {product.reader_decision}</p>
        {product.shared_requirements && <p>공통 요구 조건: {product.shared_requirements.join(' ')}</p>}
        {product.common_conditions && <p className="detail-note">같은 비교 전제: {product.common_conditions.join(' ')}</p>}
        <table className="w-full text-left"><thead><tr><th>판단 조건</th><th>기존 방법의 결정</th><th>추가 분석</th><th>추가 분석 후 판단</th></tr></thead><tbody>
          {product.decision_table.map(row => <tr key={row.id}><td>{row.condition}</td><td>{row.baseline_decision}</td><td>{row.additional_analysis}</td><td>{row.changed_decision}</td></tr>)}
        </tbody></table>
        {product.alternatives && <details><summary>대안의 구현 단계·비용·적용 조건</summary><div className="mt-2 space-y-2">
          {product.alternatives.map(alternative => <div key={alternative.id}><p className="font-semibold">{alternative.label} · {alternative.implementation_status === 'retained_source' ? '보존된 소스' : '미구현 제안'}</p>
            <p>구현 단계: {alternative.implementation_steps.join(' ')}</p><p>비용: {alternative.costs.join(' ')}</p><p>적용 조건: {alternative.applicability_conditions.join(' ')}</p></div>)}
        </div></details>}
        {product.matrix && <details><summary>대안별 실제 비교 근거</summary><table className="mt-2 w-full text-left"><thead><tr><th>대안</th><th>비교 질문</th><th>확인한 내용</th></tr></thead><tbody>
          {product.matrix.map(row => <tr key={row.id}><td>{row.alternative} · {row.implementation_status === 'retained_source' ? '보존된 소스' : '미구현 제안'}</td><td>{row.criterion}</td><td>{row.observation}</td></tr>)}
        </tbody></table></details>}
        {product.dossier && <details><summary>소유권·실행·실패 경계의 구체적인 절차</summary><div className="mt-2 space-y-2">
          {product.dossier.map(step => <div key={step.id}><p>{step.actor_id} · {step.phase} · {{ retained_source: '보존된 소스', proposed_change: '미구현 제안', environment_assumption: '환경 가정' }[step.implementation_status]}</p>
            <p>{step.instruction}</p><p className="detail-note">실패 시 결과: {step.failure_outcome}</p></div>)}
        </div></details>}
        {product.evidence_limits.length > 0 && <p className="detail-note">이 산출물의 한계: {product.evidence_limits.join(' ')}</p>}
      </section>)}
    </section>}
    <div className="space-y-2" aria-label="현재 근거의 집필 준비">
      <p className="font-semibold">{!audited ? '기존 회차 · 현재 근거판의 집필 준비 판정은 기록하지 않았습니다.'
        : ready ? '현재 근거로 집필 준비 완료' : readiness?.ready_to_write ? '현재 근거의 독립 검토 확인 필요' : '집필 준비 미완료'}</p>
      {audited && <p className="detail-note">{readiness ? developmentReasonLabels[readiness.reason] ?? readiness.reason : '연구 산출물과 현재 근거에 대한 독립 검토를 기다립니다.'}</p>}
      {audited && !ready && readiness?.ready_to_write && <p className="detail-note">검토 기록이 현재 근거와 일치하고 수정 요구가 해소됐는지 확인해야 합니다. 이전 근거판의 판단으로 집필 준비가 끝났다고 표시하지 않습니다.</p>}
      {audited && <p className="detail-note">{round.contract_version === 2 ? '근거를 보완하면 같은 근거판을 독립 재검토합니다. ' : ''}집필 준비·매체 양식·저자 확인은 각각 별도로 판단합니다.</p>}
    </div>
    <ol className="list-decimal space-y-1 pl-5">{stages.map(stage => {
      const purpose: DevelopmentPurpose = `develop-${stage}`;
      const call = calls.find(item => item.purpose === purpose);
      const skipped = stage === 'strengthen' && !round.strengthening_needed && round.completed_stages.includes('design') && !round.completed_stages.includes('strengthen') ||
        (stage === 'repair' || stage === 're-audit') && round.repair_required === false && round.completed_stages.includes('audit') && !round.completed_stages.includes('repair');
      const status = round.completed_stages.includes(stage) ? '완료' : skipped ? '추가 수정 불필요 · 요청 생략'
        : call?.outcome === 'reserved' ? '진행 중' : call?.outcome === 'completed' ? '수락 확인 미완료'
          : call ? '실패·기록 보존' : stage === 'write' && audited && !ready ? '집필 준비 확인 대기' : round.closed ? '미진행' : '대기';
      return <li key={purpose}>{developmentPurposeLabels[purpose]} · {status}</li>;
    })}</ol>
    {Object.entries(round.evidence_admission_repairs ?? {}).map(([callId, repair]) => <p className="detail-note" key={callId}>
      {repair.outcome === 'admitted' ? '보존된 연구 근거의 검사 계약 복구 완료' : '보존된 연구 근거의 검사 계약 복구 검증 거절'} · 이 복구의 추가 모델 요청 0회.
      {' '}같은 원응답의 근거 식별자와 전이·도달 결과를 다시 검증했습니다. 과학적 응답·모형·원래 거절 기록·오류·사용 횟수는 보존하며 근거를 다시 생성하지 않습니다.</p>)}
    {Object.entries(round.audit_admission_repairs ?? {}).map(([callId, repair]) => <p className="detail-note" key={callId}>
      {repair.outcome === 'admitted' ? '독립 방법 검토의 대상 분류 복구 완료' : '독립 방법 검토의 대상 분류 복구 거절'} · 이 복구의 추가 모델 요청 0회.
      {' '}기존 감사가 지적한 실제 규칙·불변식·도달 조건·대조군·판단 조건의 참조를 검증했습니다. 감사의 비판·수정 요구·원래 거절 응답·오류·사용 횟수는 보존합니다.</p>)}
    {Object.entries(round.write_admission_repairs ?? {}).map(([callId, repair]) => <p className="detail-note" key={callId}>
      {repair.outcome === 'admitted' ? '보존된 새 원고의 근거 참조 수락 복구 완료' : '보존된 새 원고의 근거 참조 수락 복구 거절'} · 이 복구의 추가 모델 요청 0회.
      {' '}동결된 연구 모형과 네이티브 검사 결과의 실제 근거 식별자를 검증했습니다. 원고 응답·본문·식별자·원래 거절 기록·오류·사용 횟수는 보존하며 원고를 다시 생성하지 않습니다.</p>)}
    {Object.entries(round.review_admission_repairs ?? {}).map(([callId, repair]) => <p className="detail-note" key={callId}>
      {repair.outcome === 'admitted' ? '보존된 독립 평가의 원고 연결 복구 완료' : '보존된 독립 평가의 원고 연결 복구 검증 거절'} · 이 복구의 추가 모델 요청 0회.
      {' '}같은 원고판의 식별자와 원문에서 유일하게 확인된 인용 위치 표기만 검증했습니다. 평가 점수·이유·권고·원고 본문·원래 거절 기록·오류·사용 횟수는 보존하며 평가를 다시 요청하지 않습니다.</p>)}
    {round.plan && <details><summary>연구 질문과 결정적인 비교 설계</summary><div className="mt-2 space-y-3">
      <p className="font-semibold">{round.plan.decision_problem}</p><p>{round.plan.expected_article_value}</p>
      {round.plan.cases.map(item => <section key={item.id} className="space-y-2">
        <p className="font-semibold">{item.id} · {item.reader_decision}</p><p>판단을 바꾸는 조건: {item.decisive_condition_flip}</p>
        <p>확인할 성질: {item.properties.join(' ')}</p><p>만들 근거: {item.evidence_tasks.join(' ')}</p>
        <ul className="list-disc space-y-2 pl-5">{item.alternatives.map(alternative => <li key={alternative.id}>
          <p>{alternative.label} · {{ actual: '현재 구현', proposal: '미구현 제안', environment_assumption: '환경 가정' }[alternative.implementation_status]}</p>
          <p>{alternative.engineering_choice}</p><p className="detail-note">가정: {alternative.policy_assumptions.join(' ')} · 비용: {alternative.costs.join(' ')}</p>
        </li>)}</ul>
      </section>)}
      <p className="detail-note">설계 단계의 한계: {round.plan.hard_limits.join(' ')}</p>
    </div></details>}
    {round.evidence && <details><summary>완성한 비교 근거와 실제 한계</summary><div className="mt-2 space-y-3">
      {round.evidence.cases.map(item => <section className="space-y-1" key={item.id}><p className="font-semibold">{item.id} · {item.decision_problem}</p>
        <p>정책 조건: {item.policy}</p><p>{item.decision_findings.join(' ')}</p><p className="detail-note">사례 한계: {item.limits.join(' ')}</p></section>)}
      {round.evidence.comparisons.map((item, index) => <section className="space-y-1" key={`${item.source_id}:${index}`}>
        <p className="font-semibold">선행 방법 {item.source_id}</p><p>{item.established_method}</p><p>추가 판단 가치: {item.local_difference}</p>
        <p className="detail-note">이미 알려진 내용: {item.what_is_not_new}</p><p className="detail-note">비용·한계: {item.cost_or_limit}</p></section>)}
      <p>{round.evidence.cross_case_findings.join(' ')}</p><p className="detail-note">근거의 한계: {round.evidence.limitations.join(' ')}</p>
    </div></details>}
    {round.checker_summary && <details><summary>네이티브 모형 검사·약화 대조군·판단 조건 변경</summary><div className="mt-2 space-y-3">
      <p className="detail-note">앱의 검사기가 생성한 추상 도달 상태의 결과입니다. 입력 저장소 프로그램의 실행·실증 보호 효과·성능 실험으로 해석하지 않습니다.</p>
      {round.checker_summary.cases.map(item => <section key={item.case_id} className="space-y-2">
        <p className="font-semibold">{item.case_id} · 상태 공간 상한 {item.cartesian_state_bound}</p>
        <ul className="space-y-1">{item.alternatives.map(alternative => <li key={alternative.alternative_id}>
          {alternative.alternative_id} · 도달 상태 {alternative.reachable_state_count} · 전이 {alternative.edge_count} · 불변식 검사 {alternative.invariant_checks} · 선언한 요건 {alternative.meets_declared_requirements ? '충족' : '미충족'}
          <p className="detail-note">불변식: {alternative.invariants.map(check => `${check.id} ${{ passed: '충족', failed: '반례 있음', vacuous: '전제 미도달' }[check.status]}`).join(' · ')}</p>
          <p className="detail-note">경로 도달: {alternative.coverage.map(check => `${check.id} ${check.status === 'passed' ? '도달' : '미도달'}`).join(' · ')}</p>
        </li>)}</ul>
        <table className="w-full text-left"><thead><tr><th>같은 조건의 대안 A</th><th>대안 B</th><th>판단이 다른 성질</th></tr></thead><tbody>
          {item.alternative_comparisons.map((comparison, index) => <tr key={index}>
            <td>{comparison.left} · {comparison.left_meets_requirements ? '요건 충족' : '요건 미충족'}</td>
            <td>{comparison.right} · {comparison.right_meets_requirements ? '요건 충족' : '요건 미충족'}</td>
            <td>{comparison.different_properties.join(', ') || '동일'}</td>
          </tr>)}
        </tbody></table>
        <p>약화한 대조군: {item.negative_controls.map(control => `${control.id} ${control.caught ? '위반 탐지' : '위반 미탐지'}`).join(' · ')}</p>
        {item.condition_flips.map(flip => <div key={flip.id}>
          <p>조건 변경: {flip.id} {flip.decisive ? '판단 변경' : '판단 동일'} ({resultLabels[flip.original_status] ?? flip.original_status} → {resultLabels[flip.changed_status] ?? flip.changed_status})</p>
          <p className="detail-note">변경한 동일 조건으로 모든 대안 재검사: {flip.alternative_outcomes_under_same_condition.map(outcome => `${outcome.alternative_id} ${outcome.meets_declared_requirements ? '요건 충족' : '요건 미충족'}`).join(' · ')}</p>
        </div>)}
        {item.issues.length > 0 && <p className="detail-note">검사 한계: {item.issues.join(' ')}</p>}
      </section>)}
      {round.checker_summary.issues.length > 0 && <p className="detail-note">전체 검사 한계: {round.checker_summary.issues.join(' ')}</p>}
    </div></details>}
    {round.audit && <details><summary>기록된 독립 방법 검토와 수정 판단</summary><div className="mt-2 space-y-3">
      <p>이 감사의 판단: {round.audit.ready_to_write ? '검토한 근거판에서 작성 가능' : '한계를 고려한 보완 필요'} · 추가 근거 수정: {round.audit.repair_required ? '한 번 요청' : '불필요'}</p>
      <p>{round.audit.decisive_findings.join(' ')}</p>
      {round.audit.correspondence.map((item, index) => <section key={index} className="space-y-1">
        <p>{item.case_id}/{item.alternative_id}/{item.target_id} · {{ faithful: '소스·가정과 대응', needs_repair: '수정 필요', unverifiable: '입증 불가' }[item.verdict]}</p>
        <p>{item.reason}</p>{item.required_repair && <p className="detail-note">필요한 수정: {item.required_repair}</p>}
      </section>)}
      {round.audit.repair_actions.map((item, index) => <p key={index}>{item.exact_change} · {item.safely_obtainable ? '확보한 근거로 수정 가능' : '현재 근거로 수정 불가'}</p>)}
      {round.audit.work_product_findings?.map(item => <p key={item.product_id}>{item.product_id} · {{ faithful: '근거와 대응', needs_repair: '보완 필요', unverifiable: '현재 입증 불가' }[item.verdict]} · {item.reason}{item.required_repair && ` · 필요한 보완: ${item.required_repair}`}</p>)}
      <p className="detail-note">독립 검토에서 남긴 한계: {round.audit.honest_limits.join(' ')}</p>
    </div></details>}
    {round.audits && <details><summary>최초 검토와 보완 후 독립 재검토 이력</summary><ul className="mt-2 space-y-2">
      {round.audits.map(audit => <li key={audit.artifact_id}>{audit.purpose === 'develop-re-audit' ? '보완 후 독립 재검토' : '최초 독립 검토'} · {audit.evidence_sha256 === round.evidence_sha256 ? '현재 근거판' : '이전 근거판'} · {audit.ready_to_write && !audit.repair_required ? '해당 근거판에서 집필 준비 확인' : '집필 전 보완 필요'}</li>)}
    </ul></details>}
    {([['연구 설계', round.plan_artifact_id], ['완성한 연구 근거', round.evidence_artifact_id], ['독립 방법 검토', round.audit_artifact_id],
      ['연구 산출물 입력', round.work_products_artifact_id], ['연구 산출물 검사 결과', round.work_product_report_artifact_id], ['연구 산출물 Markdown', round.work_product_markdown_artifact_id],
      ['연구 모형 검사', round.checker_artifact_id], ['재현 근거 묶음 ZIP', round.supplement?.artifact_id]] as const).map(([label, id]) =>
      id && job.artifacts.some(artifact => artifact.id === id) && <div className="action-row" key={id}>
        <Button variant="outline" size="sm" disabled={disabled} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, id))}>{label} 저장</Button>
        <Button variant="ghost" size="sm" disabled={disabled} onClick={() => void runAction('open', () => window.paperFactory.openArtifact(job.id, id))}>{label} 열기</Button>
      </div>)}
    {Object.entries(round.format_preflight ?? {}).map(([venue, preflight]) => <details key={venue}>
      <summary>{venueNames[venue] ?? venue} 새 연구 원고 선검사 · {preflight.content_format_passed ? '충족' : '보완 필요'}</summary>
      <JournalCompliance report={preflight.report.compliance ?? preflight.report.pure} />
      {preflight.report.errors.map((error, index) => <p className="detail-note" key={index}>{error.format} 출력: {error.error}</p>)}
    </details>)}
    {Object.entries(round.format_preflight ?? {}).map(([venue, preflight]) => {
      const version = round.write_versions?.[venue];
      const review = version && state.reviews[venue]?.find(item => item.manuscript_sha256 === version.markdown_sha256);
      const reviewId = version && state.review_artifact_ids?.[venue]?.[version.markdown_sha256];
      const selected = version && state.best_assessments?.[venue]?.manuscript_sha256 === version.markdown_sha256;
      const candidates = [{ artifact_id: preflight.artifact_id + '-markdown', label: 'Markdown' },
        ...Object.entries(preflight.report.outputs).filter(([format]) => format === 'docx' || format === 'pdf')
          .map(([format, file]) => ({ artifact_id: file.artifact_id, label: format === 'docx' ? 'Word' : 'PDF' }))];
      return <section key={venue} className="space-y-2" aria-label={`${venueNames[venue] ?? venue} 새 연구 원고`}>
        <h6 className="font-semibold">{venueNames[venue] ?? venue} · 이번에 만든 새 연구 원고</h6>
        <p className="detail-note">{selected ? '이 원고가 현재 최선으로 선택됐습니다.' : '이 원고와 보존된 최선 원고를 별도로 확인하세요. 새로 작성됐다는 이유로 최선 원고를 교체하지 않습니다.'}</p>
        <p>독립 평가: {review ? { consider_submission: '투고 검토 권장', revise_before_submission: '투고 전 보완 필요', not_recommended: '현재 투고 비권장' }[review.recommendation] : '수락된 평가 없음'}</p>
        {review && <p className="detail-note">{review.recommendation_reason}</p>}
        {candidates.filter(file => job.artifacts.some(artifact => artifact.id === file.artifact_id)).map(file => <div className="action-row" key={file.artifact_id}>
          <Button variant="outline" size="sm" disabled={disabled} onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, file.artifact_id))}>{venueNames[venue] ?? venue} 새 연구 원고 {file.label} 저장</Button>
          <Button variant="ghost" size="sm" disabled={disabled} onClick={() => void runAction('open', () => window.paperFactory.openArtifact(job.id, file.artifact_id))}>{venueNames[venue] ?? venue} 새 연구 원고 {file.label} 열기</Button>
        </div>)}
        {reviewId && job.artifacts.some(artifact => artifact.id === reviewId) && <Button variant="outline" size="sm" disabled={disabled}
          onClick={() => void runAction('save', () => window.paperFactory.saveArtifact(job.id, reviewId))}>{venueNames[venue] ?? venue} 새 연구 원고 독립 평가 저장</Button>}
      </section>;
    })}
    {Object.entries(round.format_blocked ?? {}).map(([venue, reason]) => <p className="detail-note" key={venue}>{venueNames[venue] ?? venue} 새 연구 원고 보완 필요 · {reason}</p>)}
    {Object.entries(round.assessment_errors ?? {}).map(([venue, reason]) => <p className="detail-note" key={venue}>{venueNames[venue] ?? venue} 새 연구 원고 평가 수락 실패 · {reason}</p>)}
    {round.stop_reason && <p className="detail-note">이번 연구 보완 종료 사유: {developmentReasonLabels[round.stop_reason] ?? round.stop_reason}</p>}
  </section>;
}
