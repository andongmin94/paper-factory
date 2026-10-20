import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { createRequire } from 'node:module';
import test, { after } from 'node:test';
import { build } from 'esbuild';

// Render the production component against the exact native preflight wrapper.
// This fixture contains no real study, account, model call or author approval.
const directory = await mkdtemp(join(tmpdir(), 'pf-focused-ui-'));
after(() => rm(directory, { recursive: true, force: true }));
const bundle = join(directory, 'renderer.cjs');
await build({ stdin: { contents: `
  import React from 'react';
  import { renderToStaticMarkup } from 'react-dom/server';
  import { ManuscriptImprovement } from './src/renderer/ManuscriptImprovement';
  export function render(job) {
    return renderToStaticMarkup(React.createElement(ManuscriptImprovement, { job, disabled: true, runAction: async () => {} }));
  }`, resolveDir: resolve('.'), sourcefile: 'synthetic-focused-ui.tsx', loader: 'tsx' },
  bundle: true, platform: 'node', format: 'cjs', outfile: bundle, jsx: 'automatic', logLevel: 'silent' });
const { render } = createRequire(import.meta.url)(bundle);

const compliance = (native = false) => ({ venue_id: 'ieee-software', checked_at: '2026-10-18',
  items: [{ id: 'abstract', label: 'abstract', status: 'passed', stage: native ? 'native' : 'manuscript',
    reason: native ? 'Synthetic actual native counts.' : 'Synthetic Markdown estimate only.', source_url: null },
    { id: 'author_biography', label: 'author biography', status: 'pending', stage: 'submission', reason: 'Synthetic author facts pending.', source_url: null },
    { id: 'author_photo', label: 'author photo', status: 'pending', stage: 'submission', reason: 'Synthetic photo pending.', source_url: null }],
  metrics: native ? { native_word: { whole_words: 3500, body_words: 3200, abstract_words: 120, reference_count: 10 }, effective_words: 3700 } : {},
  blockers: [], pending: ['author biography', 'author photo'], content_format_passed: native, submission_ready: false,
  prefilter_passed: true, scientific_merit_assessed: false, author_approval_inferred: false });

function job(report) {
  return { id: 'synthetic-focused-ui', stage: 'repository_manuscript', artifacts: [], repositoryPaper: {
    portfolio: { analysis: {} }, manuscript_improvement: {
      policy: { model_call_limit: 12, action_limit: 8 }, finished: false, calls: [], actions: [], reviews: {}, versions: {},
      focused_round: { id: 'focused-research-round-1', base_reservations: 8, additional_call_limit: 4, closed: false,
        completed_stages: ['focused-select', 'focused-analyze', 'focused-write'],
        format_preflight: { 'ieee-software': { artifact_id: 'synthetic-preflight', sha256: 'a'.repeat(64),
          content_format_passed: report.content_format_passed, report } } },
      counts: { model_attempts: 11, actions: 5, revisions: 4, reviews: 4 }, next_task: { purpose: 'focused-review' },
    } } };
}

test('focused native preflight wrapper renders actual compliance after the third stage', () => {
  const html = render(job({ editorial_preparation: { markdown: 'Synthetic only.' }, pure: compliance(),
    outputs: { docx: { artifact_id: 'synthetic-docx', sha256: 'b'.repeat(64) } }, conversion_receipts: {},
    errors: [], compliance: compliance(true), content_format_passed: true }));
  assert(html.includes('실제 Word 측정: 전체 3500단어'));
  assert(html.includes('초록 분량 · 충족'));
  assert(html.includes('실제 저자 약력 · 확인 대기'));
  assert(html.includes('실제 저자 사진 · 확인 대기'));
  assert(!html.includes('Synthetic Markdown estimate only.'));
});

test('focused preflight uses its pure report when native compliance is absent and retains conversion errors', () => {
  const html = render(job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {},
    errors: [{ format: 'pdf', error: 'Synthetic exact conversion failure.' }], content_format_passed: false }));
  assert(html.includes('Synthetic Markdown estimate only.'));
  assert(html.includes('PDF 출력: Synthetic exact conversion failure.'));
  assert(!html.includes('실제 Word 측정'));
});

test('focused classification repair explains admitted analysis while retaining the original rejected call', () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement, callId = '11111111-1111-4111-8111-111111111111';
  state.calls = [{ call_id: callId, purpose: 'focused-analyze', venue_id: null, outcome: 'rejected',
    error: 'Synthetic original rejected classification.', round_id: state.focused_round.id }];
  state.focused_round.analysis_repairs = { [callId]: { artifact_id: `manuscript-improvement-focused-analysis-repair-${callId}`,
    sha256: 'c'.repeat(64), outcome: 'admitted' } };
  const original = structuredClone(fixture);
  const html = render(fixture);
  assert(html.includes('Paste·Autosave 분석 · 완료'));
  assert(html.includes('분석 자료 분류 복구 완료'));
  assert(html.includes('이 분류 복구의 추가 모델 요청 0회'));
  assert(html.includes('원래 거절 응답·오류·사용 횟수는 보존'));
  assert(html.includes('Synthetic original rejected classification.'));
  assert.deepEqual(fixture, original);
});

test('focused citation repair admits the retained third response and leaves only the independent review pending', () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {},
    errors: [], compliance: compliance(true), content_format_passed: true });
  const state = fixture.repositoryPaper.manuscript_improvement, callId = '8e99c8aa-79b2-4d07-9457-b04f7663ce64';
  state.calls = ['focused-select', 'focused-analyze', 'focused-write'].map((purpose, index) => ({
    call_id: index === 2 ? callId : `11111111-1111-4111-8111-11111111111${index}`, purpose, venue_id: null,
    outcome: index === 2 ? 'rejected' : 'completed', round_id: state.focused_round.id,
    ...(index === 2 ? { error: 'Synthetic original writer citation-kind rejection.' } : {}) }));
  state.focused_round.writer_repairs = { [callId]: { artifact_id: `manuscript-improvement-focused-writer-repair-${callId}`,
    sha256: 'd'.repeat(64), outcome: 'admitted' } };
  const original = structuredClone(fixture), html = render(fixture);
  assert(html.includes('두 매체 원고 보완 · 완료'));
  assert(html.includes('독립 품질 평가 · 대기'));
  assert(html.includes('원고 인용 분류 복구 완료'));
  assert(html.includes('이 분류 복구의 추가 모델 요청 0회'));
  assert(html.includes('과학적 주장·근거 인용문·원래 거절 응답·오류·사용 횟수는 보존'));
  assert(html.includes('Synthetic original writer citation-kind rejection.'));
  assert.deepEqual(fixture, original);
});

test('development renders short native stages, real decision evidence and uncovered controls without implying execution', () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement;
  state.research_development = { id: 'research-development-round-1', origin: 'explicit_user_authorized_six_request_extension',
    base_reservations: 12, additional_call_limit: 6, closed: false, completed_stages: ['plan', 'evidence', 'audit'], repair_required: false,
    plan: { decision_problem: 'Synthetic consequential engineering decision.', expected_article_value: 'Synthetic conditional choice, not an efficacy claim.', hard_limits: ['Synthetic single-template limit.'],
      cases: [{ id: 'paste', reader_decision: 'Synthetic recipient decision.', decisive_condition_flip: 'Synthetic changed recipient makes release invalid.', properties: ['Synthetic recipient is current.'], evidence_tasks: ['Synthetic replay task.'],
        alternatives: [{ id: 'grant', label: 'Synthetic proposal', engineering_choice: 'Synthetic one-shot authority choice.', implementation_status: 'proposal', policy_assumptions: ['Synthetic current window assumption.'], costs: ['Synthetic state ownership cost.'] }] }] },
    evidence: { method_scope: 'generated_finite_rules_not_project_execution', cross_case_findings: ['Synthetic conditional result.'], limitations: ['Synthetic finite domains limit.'],
      cases: [{ id: 'paste', decision_problem: 'Synthetic release question.', policy: 'Synthetic disclosed policy.', decision_findings: ['Synthetic recipient counterexample retained.'], limits: ['Synthetic no empirical test.'] }],
      comparisons: [{ source_id: 'focused-document-1', established_method: 'Synthetic retained primary method.', local_difference: 'Synthetic explicit dispatch condition.', what_is_not_new: 'Synthetic prior capability principle.', cost_or_limit: 'Synthetic no demonstrated performance.' }] },
    checker_summary: { kind: 'generated_finite_rules', project_execution: false, input_sha256: 'a'.repeat(64), checker_sha256: 'b'.repeat(64), scope: 'Synthetic model only.', issues: [],
      cases: [{ case_id: 'paste', cartesian_state_bound: 64, issues: [], alternatives: [{ alternative_id: 'grant', reachable_state_count: 7, edge_count: 9, invariant_checks: 14, meets_declared_requirements: false,
        invariants: [{ id: 'recipient', status: 'failed', antecedent_states: 3 }, { id: 'dispatch', status: 'vacuous', antecedent_states: 0 }],
        coverage: [{ id: 'cancel', required: true, status: 'unreachable', reachable_states: 0 }] }],
        negative_controls: [{ id: 'weakened', alternative_id: 'grant', caught: false, original_status: 'failed', mutant_status: 'failed' }],
        alternative_comparisons: [{ left: 'ambient', right: 'grant', different_properties: ['recipient'], left_meets_requirements: false, right_meets_requirements: false }],
        condition_flips: [{ id: 'recipient_flip', alternative_id: 'grant', property_id: 'recipient', decisive: true, original_status: 'passed', changed_status: 'failed', alternative_outcomes_under_same_condition: [{ alternative_id: 'grant', meets_declared_requirements: false }] }] }] },
    audit: { evidence_sha256: 'a'.repeat(64), ready_to_write: false, repair_required: false, decisive_findings: ['Synthetic independently identified limit.'], honest_limits: ['Synthetic unavailable empirical evidence.'],
      correspondence: [{ case_id: 'paste', alternative_id: 'grant', target_id: 'release', verdict: 'unverifiable', reason: 'Synthetic source correspondence cannot establish this proposal.', required_repair: '' }], repair_actions: [] } };
  state.calls = ['develop-plan', 'develop-evidence', 'develop-audit'].map((purpose, index) => ({ call_id: `synthetic-${index}`, purpose, outcome: 'completed', round_id: 'research-development-round-1' }));
  const original = structuredClone(fixture), html = render(fixture);
  for (const expected of ['연구 질문·비교 설계 · 완료', '근거 독립 검토 · 완료', '추가 수정 불필요 · 요청 생략',
    'Synthetic consequential engineering decision.', 'Synthetic recipient counterexample retained.', 'Synthetic independently identified limit.',
    '도달 상태 7', '전제 미도달', 'weakened 위반 미탐지', 'recipient_flip 판단 변경', '변경한 동일 조건으로 모든 대안 재검사', '입력 저장소 프로그램의 실행·실증 보호 효과·성능 실험으로 해석하지 않습니다.']) assert(html.includes(expected), expected);
  assert(!html.includes('연구 설계·근거 보완 (최대 6회)'));
  assert.deepEqual(fixture, original);
});

test('development grants are offered only before its singleton round exists', () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement; state.finished = true;
  assert(render(fixture).includes('연구 설계·근거 보완 (최대 6회)'));
  state.research_development = { id: 'research-development-round-1', base_reservations: 12, additional_call_limit: 6, closed: true, completed_stages: ['plan', 'evidence', 'audit', 'write', 'review'], repair_required: false };
  const html = render(fixture);
  assert(!html.includes('연구 설계·근거 보완 (최대 6회)'));
  assert(html.includes('최선 원고·공식 출력 다시 확인'));
});

test('new development candidate and its exact frozen review remain downloadable when the retained best is older', () => {
  const prefix = 'manuscript-improvement-development-ieee-software-preflight', oldSha = '1'.repeat(64), newSha = '2'.repeat(64);
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement;
  const review = (sha, reason) => ({ venue_id: 'ieee-software', manuscript_sha256: sha, scores: [], essential_errors: [], evidence_limits: [], recommendation: 'revise_before_submission', recommendation_reason: reason });
  const prior = review(oldSha, 'Synthetic previous best review.'), current = review(newSha, 'Synthetic new candidate independent review.');
  state.best_assessments = { 'ieee-software': prior }; state.reviews = { 'ieee-software': [prior, current] };
  state.review_artifact_ids = { 'ieee-software': { [newSha]: 'manuscript-improvement-ieee-software-review-4' } };
  state.research_development = { id: 'research-development-round-1', base_reservations: 12, additional_call_limit: 6, closed: true,
    completed_stages: ['plan', 'evidence', 'audit', 'write', 'review'], repair_required: false,
    write_versions: { 'ieee-software': { markdown_artifact_id: 'synthetic-reviewed-md', markdown_sha256: newSha } },
    format_preflight: { 'ieee-software': { artifact_id: prefix, sha256: 'a'.repeat(64), content_format_passed: true,
      report: { editorial_preparation: {}, pure: compliance(), compliance: compliance(true), conversion_receipts: {}, errors: [], content_format_passed: true,
        outputs: { docx: { artifact_id: prefix + '-docx', sha256: 'b'.repeat(64) }, pdf: { artifact_id: prefix + '-pdf', sha256: 'c'.repeat(64) } } } } } };
  fixture.artifacts = [prefix + '-markdown', prefix + '-docx', prefix + '-pdf', 'manuscript-improvement-ieee-software-review-4'].map(id => ({ id }));
  const html = render(fixture), candidate = html.match(/<section[^>]*aria-label="IEEE Software 새 연구 원고"[\s\S]*?<\/section>/)?.[0];
  assert(candidate);
  for (const phrase of ['보존된 최선 원고를 별도로 확인', 'Synthetic new candidate independent review.',
    'IEEE Software 새 연구 원고 Markdown 저장', 'IEEE Software 새 연구 원고 Word 저장', 'IEEE Software 새 연구 원고 PDF 저장', 'IEEE Software 새 연구 원고 독립 평가 저장']) assert(candidate.includes(phrase), phrase);
  assert(!candidate.includes('Synthetic previous best review.'));
  assert(!candidate.includes('이 원고가 현재 최선으로 선택됐습니다.'));
});

test('development audit target admission preserves criticism and the rejected call while resuming only the remaining stages', () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement, callId = '48af8c99-61fc-438f-b195-091bb73d4e24';
  state.calls = [{ call_id: callId, purpose: 'develop-audit', venue_id: null, round_id: 'research-development-round-1',
    outcome: 'rejected', error: 'Synthetic original target-kind rejection.' }];
  state.research_development = { id: 'research-development-round-1', base_reservations: 12, additional_call_limit: 6,
    closed: false, completed_stages: ['plan', 'evidence', 'audit'], repair_required: true,
    audit_admission_repairs: { [callId]: { artifact_id: 'synthetic-audit-repair', sha256: 'a'.repeat(64), outcome: 'admitted' } },
    audit: { evidence_sha256: 'b'.repeat(64), ready_to_write: false, repair_required: true,
      decisive_findings: ['Synthetic critical counterexample remains.'], honest_limits: ['Synthetic methodological limit remains.'],
      correspondence: [{ case_id: 'paste', alternative_id: 'ambient', target_id: 'intentional_inspection', verdict: 'needs_repair', reason: 'Synthetic vacuous condition flip remains a criticism.', required_repair: 'Synthetic disclose the qualitative policy distinction.' }],
      repair_actions: [{ case_id: 'paste', alternative_id: 'ambient', target_id: 'intentional_inspection', issue: 'Synthetic original critique.', exact_change: 'Synthetic retain the vacuous outcome.', available_evidence_ids: ['source-1'], safely_obtainable: true }] } };
  const original = structuredClone(fixture), html = render(fixture);
  for (const phrase of ['근거 독립 검토 · 완료', '지적된 근거 보완 · 대기', '독립 방법 검토의 대상 분류 복구 완료', '이 복구의 추가 모델 요청 0회',
    'paste/ambient/intentional_inspection', 'Synthetic vacuous condition flip remains a criticism.', 'Synthetic original target-kind rejection.', 'Synthetic methodological limit remains.']) assert(html.includes(phrase), phrase);
  assert(!html.includes('새 원고 독립 평가 · 완료'));
  assert.deepEqual(fixture, original);
});

test('development writer admission keeps the exact rejected response and leaves only its independent review pending', () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement, callId = 'b81ef393-83bd-4495-9284-e09f13a2cd0d';
  state.calls = [{ call_id: callId, purpose: 'develop-write', venue_id: null, round_id: 'research-development-round-1',
    outcome: 'rejected', error: 'Synthetic original contribution evidence-ID rejection.' }];
  state.research_development = { id: 'research-development-round-1', base_reservations: 12, additional_call_limit: 6,
    closed: false, completed_stages: ['plan', 'evidence', 'audit', 'repair', 'write'], repair_required: true,
    write_admission_repairs: { [callId]: { artifact_id: 'synthetic-write-admission', sha256: 'a'.repeat(64), outcome: 'admitted' } } };
  state.next_task = { purpose: 'develop-review', venue_id: null, manuscript_sha256: null };
  const original = structuredClone(fixture), html = render(fixture);
  for (const phrase of ['근거를 반영한 두 원고 집필 · 완료', '새 원고 독립 평가 · 대기',
    '보존된 새 원고의 근거 참조 수락 복구 완료', '이 복구의 추가 모델 요청 0회',
    '원고 응답·본문·식별자·원래 거절 기록·오류·사용 횟수는 보존', 'Synthetic original contribution evidence-ID rejection.']) assert(html.includes(phrase), phrase);
  assert(!html.includes('새 원고 독립 평가 · 완료'));
  assert(!html.includes('연구 설계·근거 보완 (최대 6회)'));
  assert.deepEqual(fixture, original);
});

function currentEvidenceReadinessFixture() {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const sha = '7'.repeat(64), state = fixture.repositoryPaper.manuscript_improvement;
  state.research_development = { id: 'research-development-round-1', contract_version: 2,
    base_reservations: 12, additional_call_limit: 6, closed: false, completed_stages: ['design', 'audit', 'repair', 're-audit'],
    repair_required: false, status: 'ready_to_write', evidence_sha256: sha,
    readiness: { ready_to_write: true, reason: 'Synthetic current evidence independently checked.', evidence_sha256: sha,
      audit_evidence_sha256: sha, audit_artifact_id: 'synthetic-reaudit' },
    work_products: { products: [{ id: 'synthetic-choice', kind: 'source_comparison', reader_decision: 'Synthetic consequential recipient decision.' }] },
    work_products_artifact_id: 'synthetic-products', work_product_report_artifact_id: 'synthetic-products-report',
    work_product_report: { kind: 'native_source_bound_research_work_products', internal_consistency_passed: true,
      audit_required: true, implementation_validated: false, publication_quality_assessed: false, evidence_limits: [],
      products: [{ id: 'synthetic-choice', kind: 'source_comparison', reader_decision: 'Synthetic consequential recipient decision.',
        shared_requirements: ['Synthetic shared disclosure requirement.'], common_conditions: ['Synthetic equal recipient premise.'],
        alternatives: [{ id: 'direct', label: 'Synthetic direct transfer.', implementation_status: 'proposed_change',
          implementation_steps: ['Synthetic check current recipient before native release.'], costs: ['Synthetic receiver tracking state.'], applicability_conditions: ['Synthetic trusted input mediation available.'] }],
        decision_table: [{ id: 'synthetic-row', condition: 'Synthetic recipient changes after approval.', baseline_decision: 'Synthetic baseline accepts the renderer.',
          additional_analysis: 'Synthetic retained dispatch witness.', changed_decision: 'Synthetic discard before irreversible release.', limitations: [] }],
        matrix: [{ id: 'synthetic-observation', alternative: 'Synthetic direct transfer.', criterion: 'Synthetic recipient binding question.', observation: 'Synthetic actual source observation.', implementation_status: 'retained_source' }],
        evidence_limits: ['Synthetic consistency does not validate implementation.'] }] },
    audit: { evidence_sha256: sha, ready_to_write: true, repair_required: false, decisive_findings: [], honest_limits: [], correspondence: [], repair_actions: [] } };
  fixture.artifacts = [{ id: 'synthetic-reaudit' }, { id: 'synthetic-products' }, { id: 'synthetic-products-report' }];
  return fixture;
}

test('current evidence readiness requires the exact current independent audit and shows the re-audit stage', () => {
  const fixture = currentEvidenceReadinessFixture(), before = structuredClone(fixture), html = render(fixture);
  assert(html.includes('현재 근거로 집필 준비 완료'));
  assert(html.includes('연구 설계·비교 근거 완성 · 완료'));
  assert(html.includes('보완한 근거 독립 재검토 · 완료'));
  assert(html.includes('근거를 반영한 두 원고 집필 · 대기'));
  assert(!html.includes('연구 질문·비교 설계 ·'));
  assert.deepEqual(fixture, before);
});

for (const missing of ['current-evidence', 'audit-evidence', 'audit-body', 'audit-artifact', 'audit-verdict', 'repair-required', 'work-product-artifact', 'work-product-check'])
  test(`stale or incomplete method readiness never displays current evidence as ready: ${missing}`, () => {
    const fixture = currentEvidenceReadinessFixture(), round = fixture.repositoryPaper.manuscript_improvement.research_development;
    if (missing === 'current-evidence') round.readiness.evidence_sha256 = '8'.repeat(64);
    if (missing === 'audit-evidence') round.readiness.audit_evidence_sha256 = '8'.repeat(64);
    if (missing === 'audit-body') round.audit.evidence_sha256 = '8'.repeat(64);
    if (missing === 'audit-artifact') fixture.artifacts = [];
    if (missing === 'audit-verdict') round.audit.ready_to_write = false;
    if (missing === 'repair-required') round.audit.repair_required = true;
    if (missing === 'work-product-artifact') fixture.artifacts = fixture.artifacts.filter(item => item.id !== 'synthetic-products-report');
    if (missing === 'work-product-check') round.work_product_report.internal_consistency_passed = false;
    const html = render(fixture);
    assert(!html.includes('현재 근거로 집필 준비 완료'));
    assert(html.includes('현재 근거의 독립 검토 확인 필요'));
    assert(html.includes('근거를 반영한 두 원고 집필 · 집필 준비 확인 대기'));
  });

test('concrete research work products precede scores and expose changed decisions without claiming implementation validation', () => {
  const fixture = currentEvidenceReadinessFixture(), state = fixture.repositoryPaper.manuscript_improvement;
  state.best_assessments = { 'ieee-software': { manuscript_sha256: '9'.repeat(64), recommendation: 'revise_before_submission', recommendation_reason: 'Synthetic retained review.',
    scores: [{ criterion: 'contribution', score: 7, uncertainty: 'high', reason: 'Synthetic remaining contribution issue.', passages: [], required_improvement: '' }], essential_errors: [], evidence_limits: [] } };
  const original = structuredClone(fixture), html = render(fixture);
  for (const phrase of ['원고를 위해 완성한 연구 산출물', '연구 산출물의 내부 일관성 검사·보존 완료', 'Synthetic consequential recipient decision.',
    'Synthetic baseline accepts the renderer.', 'Synthetic retained dispatch witness.', 'Synthetic discard before irreversible release.', 'Synthetic actual source observation.',
    'Synthetic shared disclosure requirement.', 'Synthetic equal recipient premise.', 'Synthetic check current recipient before native release.', 'Synthetic receiver tracking state.', 'Synthetic trusted input mediation available.',
    '같은 판단이면 추가 기여가 입증되지 않았다는 한계를 남깁니다.']) assert(html.includes(phrase), phrase);
  assert(html.indexOf('원고를 위해 완성한 연구 산출물') < html.indexOf('추가 기여</td>'));
  assert.deepEqual(fixture, original);
});

test('legacy closed development keeps its historical audit without inventing a new readiness decision or grant', () => {
  const fixture = currentEvidenceReadinessFixture(), state = fixture.repositoryPaper.manuscript_improvement;
  delete state.research_development.contract_version; delete state.research_development.readiness;
  state.finished = true; state.research_development.closed = true;
  const before = structuredClone(fixture), html = render(fixture);
  assert(html.includes('기존 회차 · 현재 근거판의 집필 준비 판정은 기록하지 않았습니다.'));
  assert(!html.includes('현재 근거로 집필 준비 완료'));
  assert(!html.includes('연구 설계·근거 보완 (최대 6회)'));
  assert.deepEqual(fixture, before);
});

test('only a closed unextended round offers the explicit new six-request action and keeps its archive visible in round two', () => {
  const fixture = currentEvidenceReadinessFixture(), state = fixture.repositoryPaper.manuscript_improvement;
  state.finished = true; state.research_development.closed = true;
  assert(render(fixture).includes('같은 연구에 새 보완 회차 시작 (추가 최대 6회)'));
  const prior = structuredClone(state.research_development);
  state.research_development_history = [{ id: prior.id, value: prior, artifact_id: 'synthetic-archive', sha256: 'a'.repeat(64), quality_report_artifact_id: null, quality_report_sha256: null }];
  state.research_development = { ...prior, id: 'research-development-round-2', closed: false, completed_stages: [] };state.finished = false;
  const before = structuredClone(fixture), html = render(fixture);
  assert(!html.includes('같은 연구에 새 보완 회차 시작 (추가 최대 6회)'));
  assert(html.includes('현재 연구 보완 회차: 2'));assert(html.includes('보존된 이전 연구 보완 회차 1개'));
  assert(html.includes('이전 연구 보완 회차 1 · 종료'));assert.deepEqual(fixture, before);
  state.finished = true; state.research_development.closed = true;
  assert(!render(fixture).includes('같은 연구에 새 보완 회차 시작 (추가 최대 6회)'));
});


for (const outcome of ['admitted', 'rejected']) test('retained research evidence contract admission is explicit and never implies independent readiness: ' + outcome, () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement, callId = '11111111-1111-4111-8111-111111111111';
  delete state.focused_round;
  state.calls = [{ call_id: callId, purpose: 'develop-repair', round_id: 'research-development-round-2', outcome: 'rejected', error: 'Synthetic original rule witness rejection remains.' }];
  state.research_development = { id: 'research-development-round-2', contract_version: 2, base_reservations: 18, additional_call_limit: 6,
    closed: outcome === 'rejected', completed_stages: ['design', 'audit', 'repair'], repair_required: true,
    evidence_sha256: 'b'.repeat(64), readiness: { ready_to_write: false, reason: 'latest_evidence_requires_independent_reaudit', evidence_sha256: 'b'.repeat(64), audit_evidence_sha256: 'c'.repeat(64), audit_artifact_id: 'old-audit' },
    evidence_admission_repairs: { [callId]: { artifact_id: 'synthetic-evidence-admission', sha256: 'a'.repeat(64), outcome } } };
  state.next_task = outcome === 'admitted' ? { purpose: 'develop-re-audit' } : null;
  const original = structuredClone(fixture), html = render(fixture);
  for (const phrase of ['보존된 연구 근거의 검사 계약 복구 ' + (outcome === 'admitted' ? '완료' : '검증 거절'),
    '이 복구의 추가 모델 요청 0회', '과학적 응답·모형·원래 거절 기록·오류·사용 횟수는 보존',
    'Synthetic original rule witness rejection remains.', '집필 준비 미완료']) assert(html.includes(phrase), phrase);
  assert(!html.includes('현재 근거로 집필 준비 완료'));
  assert(!html.includes('새 원고 독립 평가 · 완료'));
  assert.deepEqual(fixture, original);
});


for (const outcome of ['admitted', 'rejected']) test('same-version review binding repair retains scores and the rejected SDK call without reassessment: ' + outcome, () => {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement, callId = '22222222-2222-4222-8222-222222222222';delete state.focused_round;
  state.calls = [{ call_id: callId, purpose: 'develop-review', round_id: 'research-development-round-2', outcome: 'rejected', error: 'Synthetic original exact-version rejection remains.' }];
  state.finished = true;state.next_task = null;
  state.research_development = { id: 'research-development-round-2', contract_version: 2, base_reservations: 18, additional_call_limit: 6, closed: true,
    completed_stages: ['design', 'audit', 'repair', 're-audit', 'write', ...(outcome === 'admitted' ? ['review'] : [])],
    review_admission_repairs: { [callId]: { artifact_id: 'synthetic-review-binding', sha256: 'a'.repeat(64), outcome } } };
  const original = structuredClone(fixture), html = render(fixture);
  for (const phrase of ['보존된 독립 평가의 원고 연결 복구 ' + (outcome === 'admitted' ? '완료' : '검증 거절'),
    '이 복구의 추가 모델 요청 0회', '평가 점수·이유·권고·원고 본문·원래 거절 기록·오류·사용 횟수는 보존',
    'Synthetic original exact-version rejection remains.']) assert(html.includes(phrase), phrase);
  if (outcome === 'admitted') assert(html.includes('새 원고 독립 평가 · 완료'));
  assert(!html.includes('모든 항목 달성'));assert(!html.includes('현재 근거로 집필 준비 완료'));
  assert.deepEqual(fixture, original);
});

function questionDesignFixture() {
  const fixture = job({ editorial_preparation: {}, pure: compliance(), outputs: {}, conversion_receipts: {}, errors: [], content_format_passed: false });
  const state = fixture.repositoryPaper.manuscript_improvement;
  delete state.focused_round;
  state.policy.model_call_limit = 6;
  state.counts = { model_attempts: 1, actions: 0, revisions: 0, reviews: 0 };
  state.research_development = { id: 'synthetic-question-round', contract_version: 3,
    base_reservations: 0, additional_call_limit: 6, closed: false, completed_stages: [],
    agenda_artifact_id: 'synthetic-question-agenda', research_design_artifact_id: 'synthetic-question-design',
    selected_question: null, acquisitions: [], strengthening_needed: false };
  state.calls = [{ call_id: 'synthetic-question-call', purpose: 'develop-question', outcome: 'reserved', round_id: state.research_development.id }];
  state.next_task = { purpose: 'develop-question' };
  return fixture;
}

const questionStageLabels = ['질문 후보·가까운 방법·필요 근거 설계', '연구 설계·비교 근거 완성',
  '새 근거로 비교·연구 내용 보완', '근거 독립 검토', '근거를 반영한 두 원고 집필', '새 원고 독립 평가'];

test('question-first research displays its six content stages without inventing a selected question or legacy repairs', () => {
  const fixture = questionDesignFixture(), before = structuredClone(fixture), html = render(fixture);
  const stages = html.match(/<ol[^>]*>[\s\S]*?<\/ol>/)?.[0];
  assert(stages);
  let previous = -1;
  for (const label of questionStageLabels) {
    const offset = stages.indexOf(label);
    assert(offset > previous, label);
    previous = offset;
  }
  assert.equal((stages.match(/<li>/g) ?? []).length, 6);
  assert(stages.includes('질문 후보·가까운 방법·필요 근거 설계 · 진행 중'));
  assert(stages.includes('새 근거로 비교·연구 내용 보완 · 대기'));
  assert(html.includes('후보 질문을 실제 확보 근거와 비교합니다.'));
  assert(!html.includes('선택한 질문:'));
  assert(!stages.includes('지적된 근거 보완'));
  assert(!stages.includes('보완한 근거 독립 재검토'));
  assert(!html.includes('현재 근거로 집필 준비 완료'));
  assert.deepEqual(fixture, before);
});

test('selected question and actual zero/two-body acquisition results remain distinct from a completed method audit', () => {
  const fixture = questionDesignFixture(), state = fixture.repositoryPaper.manuscript_improvement, round = state.research_development;
  round.completed_stages = ['question', 'design'];
  round.selected_question = { id: 'migration-diagnosis', question: 'Which configuration defaults make migration failures diagnosable?',
    reader_decision: 'Choose whether migration configuration needs explicit diagnostic context.', method_route: 'source_comparison' };
  round.strengthening_needed = true;
  round.acquisitions = [
    { queries: ['migration configuration observability'], sources: [], retained_full_bodies: 0 },
    { queries: ['migration diagnostic context primary method'], sources: [
      { id: 'synthetic-prior-one', status: 'retained', complete_body: true },
      { id: 'synthetic-prior-two', status: 'retained', complete_body: true }], retained_full_bodies: 2 },
  ];
  fixture.artifacts = [{ id: round.agenda_artifact_id }, { id: round.research_design_artifact_id }];
  state.calls = ['question', 'design'].map(stage => ({ call_id: 'synthetic-' + stage, purpose: 'develop-' + stage,
    outcome: 'completed', round_id: round.id }));
  state.next_task = { purpose: 'develop-strengthen' };
  const before = structuredClone(fixture), html = render(fixture);
  for (const phrase of ['선택한 질문: Which configuration defaults make migration failures diagnosable?',
    '독자에게 필요한 결정: Choose whether migration configuration needs explicit diagnostic context.',
    '근거 확보 1회: migration configuration observability · 완전한 원문 0개',
    '근거 확보 2회: migration diagnostic context primary method · 완전한 원문 2개',
    '질문 후보·확보 계획 저장', '실제 비교·결과와 집필 근거 저장',
    '연구 설계·비교 근거 완성 · 완료', '새 근거로 비교·연구 내용 보완 · 대기', '근거 독립 검토 · 대기']) assert(html.includes(phrase), phrase);
  assert(!html.includes('현재 근거로 집필 준비 완료'));
  assert(!html.includes('새 원고 독립 평가 · 완료'));
  assert(!html.includes('같은 연구에 새 보완 회차 시작 (추가 최대 6회)'));
  assert.deepEqual(fixture, before);
});

test('question and completed-research downloads require the exact retained artifact rather than a planned identifier', () => {
  const fixture = questionDesignFixture(), round = fixture.repositoryPaper.manuscript_improvement.research_development;
  fixture.artifacts = [{ id: round.agenda_artifact_id }];
  let html = render(fixture);
  assert(html.includes('질문 후보·확보 계획 저장'));
  assert(!html.includes('실제 비교·결과와 집필 근거 저장'));
  fixture.artifacts = [{ id: round.research_design_artifact_id }];
  const before = structuredClone(fixture);
  html = render(fixture);
  assert(!html.includes('질문 후보·확보 계획 저장'));
  assert(html.includes('실제 비교·결과와 집필 근거 저장'));
  assert.deepEqual(fixture, before);
});

test('one constructive strengthening call is shown in progress and completed without creating a second repair stage', () => {
  const fixture = questionDesignFixture(), state = fixture.repositoryPaper.manuscript_improvement, round = state.research_development;
  round.completed_stages = ['question', 'design'];
  round.strengthening_needed = true;
  state.calls = ['question', 'design', 'strengthen'].map(stage => ({ call_id: 'synthetic-' + stage,
    purpose: 'develop-' + stage, outcome: stage === 'strengthen' ? 'reserved' : 'completed', round_id: round.id }));
  state.next_task = { purpose: 'develop-strengthen' };
  let html = render(fixture);
  assert(html.includes('새 근거로 비교·연구 내용 보완 · 진행 중'));
  assert(html.includes('이번 연구 보완 요청 시도 3/6회'));
  assert(!html.includes('지적된 근거 보완 ·'));
  round.completed_stages.push('strengthen');
  state.calls[2].outcome = 'completed';
  state.next_task = { purpose: 'develop-audit' };
  const before = structuredClone(fixture);
  html = render(fixture);
  assert(html.includes('새 근거로 비교·연구 내용 보완 · 완료'));
  assert(html.includes('근거 독립 검토 · 대기'));
  assert(!html.includes('보완한 근거 독립 재검토 ·'));
  assert.deepEqual(fixture, before);
});

test('five-call completion visibly skips unnecessary strengthening while retaining its existing round and counters', () => {
  const fixture = questionDesignFixture(), state = fixture.repositoryPaper.manuscript_improvement, round = state.research_development;
  round.completed_stages = ['question', 'design', 'audit', 'write', 'review'];
  round.closed = true;
  state.finished = true;
  state.next_task = null;
  state.research_development_history = [{ id: 'synthetic-closed-prior', artifact_id: 'synthetic-archive', sha256: 'a'.repeat(64),
    value: { id: 'synthetic-closed-prior', contract_version: 2, closed: true, additional_call_limit: 6, completed_stages: ['design', 'audit', 'write', 'review'] } }];
  state.calls = round.completed_stages.map(stage => ({ call_id: 'synthetic-' + stage, purpose: 'develop-' + stage, outcome: 'completed', round_id: round.id }));
  state.counts = { model_attempts: 5, actions: 2, revisions: 2, reviews: 2 };
  const before = structuredClone(fixture), html = render(fixture);
  assert(html.includes('이번 연구 보완 요청 시도 5/6회 · 종료'));
  assert(html.includes('새 근거로 비교·연구 내용 보완 · 추가 수정 불필요 · 요청 생략'));
  for (const label of questionStageLabels.filter(label => !label.startsWith('새 근거로'))) assert(html.includes(label + ' · 완료'), label);
  assert(html.includes('보존된 이전 연구 보완 회차 1개'));
  assert(!html.includes('연구 설계·근거 보완 (최대 6회)'));
  assert(!html.includes('같은 연구에 새 보완 회차 시작 (추가 최대 6회)'));
  assert(!html.includes('모든 항목 달성'));
  assert(!html.includes('현재 근거로 집필 준비 완료'));
  assert.deepEqual(fixture, before);
});
