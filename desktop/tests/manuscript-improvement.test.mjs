import assert from 'node:assert/strict';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import test from 'node:test';
import { ResearchController } from '../dist/research.js';

// Synthetic controller fixtures exercise reservations and preservation, not paper merit.
async function fixture({ fail = false, existing = false, tamper = false, focused = false, focusedResume = false,
  development = false, developmentResume = false, extension = false, developmentContract = 1, methodBlocked = false, repairRequired = false, oversized = false, oversizedBytes = false } = {}) {
  const home = await mkdtemp(join(tmpdir(), 'pf-quality-'));
  const id = 'research-abcdef123456', events = [], submissionTimeouts = [];
  const retained = { id: 'original', sha256: 'a'.repeat(64), size: 1 };
  const record = { id, goal: 'Synthetic fixed quality continuation test', research_mode: 'repository_analysis',
    stage: 'repository_manuscript', status: 'ready', code: null, message: null, cleanup_pending: false,
    terminal_control_failure: false, execution_attempt: 0, proposal_attempt: 1, code_attempt: 0, draft_attempt: 0,
    study_literature_attempt: 1, redesign_attempt: 0, parent_research_id: null, root_research_id: null,
    followup_research_id: null, supporting_documents: [], artifacts: { original: retained }, resume_kind: null,
    repository_paper: { manuscript_available: true, portfolio: { venues: [], all_content_ready: true } } };
  const state = { policy: { model_call_limit: 8 }, calls: [], reviews: {}, versions: {}, actions: [], finished: false,
    next_task: { purpose: 'review', venue_id: 'ieee-software', manuscript_sha256: 'b'.repeat(64) } };
  const isDevelopment = development || developmentResume || extension;
  const stages = isDevelopment ? developmentContract === 2 || extension
    ? ['develop-design', 'develop-audit', ...(repairRequired ? ['develop-repair', 'develop-re-audit'] : []), 'develop-write', 'develop-review']
    : ['develop-plan', 'develop-evidence', 'develop-audit', ...(repairRequired ? ['develop-repair'] : []), 'develop-write', 'develop-review']
    : ['focused-select', 'focused-analyze', 'focused-write', 'focused-review'];
  const originalCalls = Array.from({ length: extension ? 18 : isDevelopment ? 12 : 8 }, (_, n) => ({ call_id: `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`,
    purpose: n % 2 ? 'review' : 'revise', venue_id: 'ieee-software', outcome: 'completed' }));
  if (focused || focusedResume || isDevelopment) {
    state.calls = structuredClone(originalCalls); state.finished = true; state.next_task = null;
    record.repository_paper.manuscript_improvement = state;
  }
  const oldRound = { id: 'research-development-round-1', base_reservations: 12, additional_call_limit: 6,
    closed: true, completed_stages: ['plan', 'evidence', 'audit', 'repair', 'write', 'review'], evidence_artifact_id: 'original-frozen-evidence' };
  if (extension) { state.policy.model_call_limit = 18; state.research_development = structuredClone(oldRound); }
  const grant = () => {
    state.policy.model_call_limit = 12; state.finished = false;
    state.focused_round = { id: 'focused-research-round-1', base_reservations: 8, additional_call_limit: 4,
      completed_stages: [], closed: false };
    state.next_task = { purpose: stages[0], venue_id: null, manuscript_sha256: null };
  };
  const grantDevelopment = () => {
    state.policy.model_call_limit = 18; state.finished = false;
    state.research_development = { id: 'research-development-round-1', base_reservations: 12,
      ...(developmentContract === 2 ? { contract_version: 2, status: 'research_in_progress' } : {}),
      additional_call_limit: 6, completed_stages: [], repair_required: repairRequired, closed: false };
    state.next_task = { purpose: stages[0], venue_id: null, manuscript_sha256: null };
  };
  if (focusedResume || developmentResume) {
    if (developmentResume) grantDevelopment(); else grant();
    const call_id = '11111111-1111-4111-8111-111111111111';
    state.calls.push({ call_id, ...state.next_task, round_id: (state.research_development ?? state.focused_round).id, outcome: 'reserved' });
    record.artifacts[`model-evidence-${call_id}-completed`] = { id: `model-evidence-${call_id}-completed`, sha256: 'c'.repeat(64), size: 2 };
  }
  const client = { getSession: async () => ({ status: 'connected', sharing: true, profileId: 'synthetic' }),
    listModels: async () => [{ slug: 'synthetic' }, { slug: 'synthetic-reviewer' }], streamResponse: async request => {
      events.push('sdk'); assert.equal(state.calls.filter(call => call.outcome === 'reserved').length, 1); assert.equal(events.at(-2), 'start');
      assert(state.calls.length <= state.policy.model_call_limit);
      if (isDevelopment) assert.equal(request.model, ['develop-audit', 'develop-re-audit', 'develop-review'].includes(state.calls.at(-1).purpose) ? 'synthetic-reviewer' : 'synthetic');
      if (fail) throw new Error('Synthetic model failure');
      return { text: '{"synthetic":true}' };
    } };
  const engine = { start: async () => {}, request: async (method, params, timeout) => {
    if (method === 'runtime.status') return { ready: true, repository_analysis_ready: true };
    if (method === 'workflow.list') return [structuredClone(record)];
    if (method === 'workflow.status') return structuredClone(record);
    if (method === 'workflow.grantFocusedManuscriptRound') {
      events.push('grant'); if (!state.focused_round) grant(); return structuredClone(record);
    }
    if (method === 'workflow.grantResearchDevelopmentRound') {
      events.push('development-grant'); if (!state.research_development) grantDevelopment(); return structuredClone(record);
    }
    if (method === 'workflow.extendResearchDevelopmentRound') {
      assert.equal(params.priorRoundId, oldRound.id);
      if (state.research_development_history?.some(entry => entry.id === params.priorRoundId)) return structuredClone(record);
      events.push('extension-grant'); assert(state.finished && state.research_development.closed);
      state.research_development_history = [{ id: oldRound.id, value: structuredClone(state.research_development), artifact_id: 'synthetic-round-archive', sha256: 'e'.repeat(64) }];
      state.policy.model_call_limit = 24; state.finished = false;
      state.research_development = { id: 'research-development-round-2', contract_version: 2, base_reservations: 18,
        additional_call_limit: 6, completed_stages: [], repair_required: repairRequired, closed: false };
      state.next_task = { purpose: stages[0], venue_id: null, manuscript_sha256: null }; return structuredClone(record);
    }
    if (method === 'workflow.startManuscriptImprovement') { record.repository_paper.manuscript_improvement = state; return structuredClone(record); }
    if (method === 'workflow.repairManuscriptImprovement') return structuredClone(record);
    if (method === 'workflow.reserveManuscriptImprovement') {
      events.push('reserve');
      const pending = state.calls.find(call => call.outcome === 'reserved');
      const call_id = pending?.call_id ?? (existing ? '11111111-1111-4111-8111-111111111111' : params.value.call_id);
      const phase = ['focused-write', 'develop-evidence', 'develop-repair', 'develop-write'].includes(params.value.purpose) ? 'quality-write'
        : ['focused-select', 'focused-analyze', 'develop-plan', 'develop-design'].includes(params.value.purpose) ? 'quality-plan' : 'quality-review';
      const task = { call_id, phase, prompt: oversized ? 'x'.repeat(700001) : oversizedBytes ? '☃'.repeat(350000) : 'Synthetic exact native-reserved prompt.' };
      const round = state.research_development ?? state.focused_round;
      if (!pending) state.calls.push({ ...task, purpose: params.value.purpose, outcome: 'reserved',
        ...(round ? { round_id: round.id } : {}) });
      if (existing) record.artifacts[`model-evidence-${call_id}-completed`] = { id: `model-evidence-${call_id}-completed`, sha256: 'c'.repeat(64), size: 2 };
      return { workflow: structuredClone(record), task };
    }
    if (method === 'workflow.recordInference') {
      events.push(params.receipt.outcome === 'started' ? 'start' : params.receipt.outcome);
      assert(state.calls.some(call => call.call_id === params.receipt.id));
      const key = `model-evidence-${params.receipt.id}-${params.receipt.outcome}`;
      record.artifacts[key] = { id: key, sha256: 'd'.repeat(64), size: 3 };
      return { artifactId: key, sha256: 'd'.repeat(64) };
    }
    if (method === 'workflow.submitManuscriptImprovement') {
      events.push('submit');
      assert(record.artifacts[params.inferenceArtifactId]);
      assert.match(params.inferenceArtifactId, fail ? /-failed$/ : /-completed$/);
      const pending = state.calls.find(call => call.outcome === 'reserved');
      submissionTimeouts.push({ purpose: pending.purpose, timeout });
      pending.outcome = fail ? 'failed' : 'completed';
      const round = state.research_development ?? state.focused_round;
      if (round) {
        round.completed_stages.push(isDevelopment ? pending.purpose.replace('develop-', '') : pending.purpose);
        const readinessStopped = isDevelopment && methodBlocked && ['develop-audit', 'develop-re-audit'].includes(pending.purpose);
        if (readinessStopped) {
          round.status = 'bounded_research_report'; round.stop_reason = 'method_not_ready'; state.stop_reason = 'method_not_ready';
        }
        const next = isDevelopment && fail || readinessStopped ? null : stages[round.completed_stages.length];
        state.next_task = next ? { purpose: next, venue_id: null, manuscript_sha256: null } : null;
      } else state.next_task = null;
      if (tamper) record.artifacts.original = { ...retained, sha256: 'f'.repeat(64) };
      return structuredClone(record);
    }
    if (method === 'workflow.finishManuscriptImprovement') {
      events.push('finish'); state.finished = true;
      const round = state.research_development ?? state.focused_round;
      if (round) round.closed = true;
      return structuredClone(record);
    }
    throw new Error('Unexpected request ' + method);
  } };
  await writeFile(join(home, 'jobs.json'), JSON.stringify([{ id, goal: record.goal, model: 'synthetic', reviewerModel: isDevelopment ? 'synthetic-reviewer' : 'synthetic',
    source: 'https://github.com/example/synthetic', pipeline: 'paused', status: 'ready', updatedAt: new Date().toISOString() }]));
  const controller = new ResearchController(client, engine, home, () => {});
  await controller.initialize();
  return { controller, events, submissionTimeouts, record, state, originalCalls, oldRound, cleanup: () => rm(home, { recursive: true, force: true }) };
}

async function settled(controller) {
  for (let i = 0; i < 300 && controller.snapshot().busy; i++) await delay(10);
  assert.equal(controller.snapshot().busy, false);
  return controller.snapshot();
}

for (const options of [{}, { fail: true }, { existing: true }]) test(`quality continuation preserves old counts and reserves before SDK ${JSON.stringify(options)}`, async () => {
  const f = await fixture(options);
  try {
    await f.controller.continueManuscriptImprovement(f.record.id);
    const snapshot = await settled(f.controller);
    assert.equal(snapshot.error, null);
    assert.equal(f.state.finished, true);
    assert.equal(f.record.execution_attempt, 0); assert.equal(f.record.proposal_attempt, 1);
    assert.equal(f.record.study_literature_attempt, 1); assert.equal(f.record.draft_attempt, 0);
    assert.equal(f.events.filter(event => event === 'sdk').length, options.existing ? 0 : 1);
    assert.equal(f.events.at(-1), 'finish');
  } finally { await f.cleanup(); }
});

test('quality continuation stops when a retained artifact changes', async () => {
  const f = await fixture({ tamper: true });
  try {
    await f.controller.continueManuscriptImprovement(f.record.id);
    const snapshot = await settled(f.controller);
    assert.equal(snapshot.error.code, 'RESEARCH_STATE_INVALID');
    assert.equal(f.events.includes('finish'), false);
    assert.equal(f.events.filter(event => event === 'sdk').length, 1);
  } finally { await f.cleanup(); }
});

test('one focused grant runs at most four normal SDK requests and repeated continuation adds none', async () => {
  const f = await fixture({ focused: true });
  try {
    await f.controller.focusManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, 4);
    assert.equal(f.state.calls.length, 12);
    assert.deepEqual(f.state.calls.slice(0, 8), f.originalCalls);
    assert.deepEqual(f.state.focused_round.completed_stages, ['focused-select', 'focused-analyze', 'focused-write', 'focused-review']);
    assert.equal(f.state.focused_round.closed, true);
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, 4);
    assert.equal(f.record.execution_attempt, 0);
    assert.equal(f.record.proposal_attempt, 1);
    assert.equal(f.record.study_literature_attempt, 1);
    assert.equal(f.record.draft_attempt, 0);
    assert.equal(f.record.artifacts.original.sha256, 'a'.repeat(64));
  } finally { await f.cleanup(); }
});

test('focused resume consumes retained completion without another grant or repeated SDK request', async () => {
  const f = await fixture({ focusedResume: true });
  try {
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'grant').length, 0);
    assert.equal(f.events.filter(event => event === 'sdk').length, 3);
    assert.equal(f.state.calls.length, 12);
    assert.deepEqual(f.state.calls.slice(0, 8), f.originalCalls);
    assert.equal(f.state.focused_round.closed, true);
  } finally { await f.cleanup(); }
});

for (const repairRequired of [false, true]) test(`development preserves twelve calls and uses independent audit/review within six requests; repair=${repairRequired}`, async () => {
  const f = await fixture({ development: true, repairRequired });
  try {
    await f.controller.developManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    const expected = repairRequired ? 6 : 5;
    assert.equal(f.events.filter(event => event === 'development-grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, expected);
    assert.equal(f.state.calls.length, 12 + expected);
    assert.deepEqual(f.state.calls.slice(0, 12), f.originalCalls);
    assert.equal(f.state.policy.model_call_limit, 18);
    assert.equal(f.state.research_development.closed, true);
    assert.equal(f.state.calls.some(call => call.purpose === 'develop-repair'), repairRequired);
    for (const purpose of ['develop-audit', 'develop-review']) assert.equal(f.state.calls.filter(call => call.purpose === purpose).length, 1);
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'development-grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, expected);
    assert.equal(f.record.execution_attempt, 0); assert.equal(f.record.code_attempt, 0);
    assert.equal(f.record.proposal_attempt, 1); assert.equal(f.record.study_literature_attempt, 1);
    assert.equal(f.record.artifacts.original.sha256, 'a'.repeat(64));
  } finally { await f.cleanup(); }
});

test('development resume reuses a retained completed response without a grant or duplicate request', async () => {
  const f = await fixture({ developmentResume: true, repairRequired: true });
  try {
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'development-grant').length, 0);
    assert.equal(f.events.filter(event => event === 'sdk').length, 5);
    assert.equal(f.state.calls.length, 18);
    assert.deepEqual(f.state.calls.slice(0, 12), f.originalCalls);
  } finally { await f.cleanup(); }
});

test('an oversized native development prompt never reaches the SDK', async () => {
  const f = await fixture({ development: true, oversized: true });
  try {
    await f.controller.developManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error.code, 'RESEARCH_STATE_INVALID');
    assert.equal(f.events.filter(event => event === 'sdk').length, 0);
    assert.equal(f.events.includes('finish'), false);
    assert.deepEqual(f.state.calls.slice(0, 12), f.originalCalls);
  } finally { await f.cleanup(); }
});

for (const repairRequired of [false, true]) test(`new development independently audits the current evidence before its single write and review; repair=${repairRequired}`, async () => {
  const f = await fixture({ development: true, developmentContract: 2, repairRequired });
  try {
    await f.controller.developManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    const expected = ['develop-design', 'develop-audit', ...(repairRequired ? ['develop-repair', 'develop-re-audit'] : []), 'develop-write', 'develop-review'];
    assert.deepEqual(f.state.calls.slice(12).map(call => call.purpose), expected);
    assert.equal(f.events.filter(event => event === 'sdk').length, expected.length);
    assert.equal(f.state.calls.length, 12 + expected.length);
    assert.deepEqual(f.state.calls.slice(0, 12), f.originalCalls);
    assert.equal(f.submissionTimeouts.find(item => item.purpose === 'develop-design').timeout, 600_000);
    if (repairRequired) assert.equal(f.submissionTimeouts.find(item => item.purpose === 'develop-re-audit').timeout, 600_000);
    assert.equal(f.state.calls.filter(call => call.purpose === 'develop-write').length, 1);
    assert.equal(f.state.calls.filter(call => call.purpose === 'develop-review').length, 1);
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'development-grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, expected.length);
    assert.equal(f.record.execution_attempt, 0);
  } finally { await f.cleanup(); }
});

test('native method readiness can stop before writing without claiming a completed manuscript review', async () => {
  const f = await fixture({ development: true, developmentContract: 2, methodBlocked: true });
  try {
    await f.controller.developManuscriptImprovement(f.record.id);
    const snapshot = await settled(f.controller);
    assert.equal(snapshot.error, null);
    assert.deepEqual(f.state.calls.slice(12).map(call => call.purpose), ['develop-design', 'develop-audit']);
    assert.equal(f.events.filter(event => event === 'sdk').length, 2);
    assert.equal(f.state.research_development.status, 'bounded_research_report');
    assert.equal(f.state.research_development.closed, true);
    assert(snapshot.jobs[0].message.includes('집필 준비 판단'));
    assert(!snapshot.jobs[0].message.includes('독립 평가를 마쳤습니다'));
    assert(!snapshot.jobs[0].message.includes('독립 평가를 보존했습니다'));
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'sdk').length, 2);
    assert.equal(f.events.filter(event => event === 'development-grant').length, 1);
    assert.deepEqual(f.state.calls.slice(0, 12), f.originalCalls);
  } finally { await f.cleanup(); }
});

test('new development resume consumes a retained design response and keeps the same six-request grant', async () => {
  const f = await fixture({ developmentResume: true, developmentContract: 2, repairRequired: true });
  try {
    await f.controller.continueManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'development-grant').length, 0);
    assert.equal(f.events.filter(event => event === 'sdk').length, 5);
    assert.deepEqual(f.state.calls.slice(12).map(call => call.purpose), ['develop-design', 'develop-audit', 'develop-repair', 'develop-re-audit', 'develop-write', 'develop-review']);
    assert.deepEqual(f.state.calls.slice(0, 12), f.originalCalls);
    assert.equal(f.state.calls.length, 18);
  } finally { await f.cleanup(); }
});

test('explicit six-request extension preserves the archived round and repeated ordinary resume or the same prior grant adds none', async () => {
  const f = await fixture({ extension: true, repairRequired: true });
  try {
    await f.controller.extendResearchDevelopmentRound(f.record.id, f.oldRound.id);
    assert.equal((await settled(f.controller)).error, null);
    assert.equal(f.events.filter(event => event === 'sdk').length, 6); assert.equal(f.state.calls.length, 24);
    assert.deepEqual(f.state.calls.slice(0, 18), f.originalCalls);assert.deepEqual(f.state.research_development_history[0].value, f.oldRound);
    assert.equal(f.state.research_development.id, 'research-development-round-2');assert.equal(f.state.policy.model_call_limit, 24);
    await f.controller.continueManuscriptImprovement(f.record.id);await settled(f.controller);
    await f.controller.extendResearchDevelopmentRound(f.record.id, f.oldRound.id);await settled(f.controller);
    assert.equal(f.events.filter(event => event === 'extension-grant').length, 1);assert.equal(f.events.filter(event => event === 'sdk').length, 6);
    assert.deepEqual(f.state.research_development_history[0].value, f.oldRound);assert.equal(f.record.execution_attempt, 0);
  } finally { await f.cleanup(); }
});

test('the exact SDK JSON byte limit blocks non-ASCII quality prompts before any provider dispatch', async () => {
  const f = await fixture({ development: true, developmentContract: 2, oversizedBytes: true });
  try {
    await f.controller.developManuscriptImprovement(f.record.id);
    assert.equal((await settled(f.controller)).error.code, 'REVIEW_CONTEXT_TOO_LARGE');
    assert.equal(f.events.filter(event => event === 'sdk').length, 0);assert.equal(f.events.includes('start'), false);
  } finally { await f.cleanup(); }
});

test('a simultaneous extension click cannot grant a second six-request allowance', async () => {
  const f = await fixture({ extension: true });
  try {
    const started = f.controller.extendResearchDevelopmentRound(f.record.id, f.oldRound.id);
    await assert.rejects(f.controller.extendResearchDevelopmentRound(f.record.id, f.oldRound.id), error => error.code === 'RESEARCH_BUSY');
    await started; await settled(f.controller);
    assert.equal(f.events.filter(event => event === 'extension-grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, 4);
    assert.deepEqual(f.state.calls.slice(0, 18), f.originalCalls);
  } finally { await f.cleanup(); }
});

test('a failed extension request remains counted and ordinary resume never regrants or retries it', async () => {
  const f = await fixture({ extension: true, fail: true });
  try {
    await f.controller.extendResearchDevelopmentRound(f.record.id, f.oldRound.id); await settled(f.controller);
    assert.equal(f.events.filter(event => event === 'sdk').length, 1);
    assert.equal(f.state.calls.length, 19); assert.equal(f.state.calls.at(-1).outcome, 'failed');
    await f.controller.continueManuscriptImprovement(f.record.id); await settled(f.controller);
    assert.equal(f.events.filter(event => event === 'extension-grant').length, 1);
    assert.equal(f.events.filter(event => event === 'sdk').length, 1);
    assert.deepEqual(f.state.research_development_history[0].value, f.oldRound);
  } finally { await f.cleanup(); }
});
