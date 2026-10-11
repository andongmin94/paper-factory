import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { setTimeout as delay } from 'node:timers/promises';
import test from 'node:test';
import { ResearchController } from '../dist/research.js';
import { EngineError } from '../dist/engine.js';
import { ChatGPTError } from '@siwc/local';

// Component routing fixtures only. Actual portfolio generation/receipts are exercised
// in repository-portfolio.test.mjs; these synthetic values are not publication evidence.
const catalog = JSON.parse(await readFile(new URL('../../src/paper_factory/publication_venues.json', import.meta.url), 'utf8'));
const sha = value => createHash('sha256').update(value).digest('hex');
const sourceText = 'export const syntheticChoice = "local";';
const sourceInventory = [{ name: 'src/choice.js', sha256: sha(sourceText), size: Buffer.byteLength(sourceText) }];
const plan = { publication_target: { venue_id: 'ieee-software', article_category: 'Feature Article',
  selection_reason: 'Synthetic practitioner article routing fixture.', candidates: catalog.venues.map(venue => ({
    venue_id: venue.id, fit: 'suitable', reason: 'Synthetic venue routing only.', missing_evidence: [] })) },
  article_type: 'design_case_study', title: 'Synthetic practical design case', question: 'How is the declared synthetic choice bounded?',
  contribution: 'A synthetic bounded design decision used only to exercise controller routing.',
  analysis_method: 'Read the frozen synthetic source without execution.', comparison_dimensions: ['Declared responsibility boundary'],
  source_files: ['src/choice.js'], source_evidence: [], literature_queries: ['bounded design responsibility'],
  limitations: ['Synthetic fixture establishes no publication adequacy.'] };
const input = { source: 'https://github.com/synthetic/repository', goal: 'Synthetic magazine routing without project execution.',
  model: 'writer', reviewerModel: 'reviewer', researchMode: 'repository_analysis' };
const author = { display_name: 'Synthetic Author', email: 'fixture@example.test', affiliation: 'Synthetic Institution' };

async function fixture({ planned = false, portfolioDraft = false, holdPortfolio = false, oversizedContribution = false,
  failPlanSubmission = false, failPlanRepair = false, executionAttempt = 0 } = {}) {
  const home = await mkdtemp(join(tmpdir(), 'pf-magazine-routing-'));
  const calls = [], prompts = [], receipts = [], portfolioEntries = [];
  let exists = planned || portfolioDraft, connected = true, releasePortfolio;
  const portfolioGate = holdPortfolio ? new Promise(resolve => { releasePortfolio = resolve; }) : null;
  const workflow = { id: 'research-abcdef123456', goal: input.goal, research_mode: 'repository_analysis',
    stage: portfolioDraft ? 'repository_manuscript' : planned ? 'repository_planned' : 'created',
    status: 'ready', code: null, message: null, cleanup_pending: false, terminal_control_failure: false,
    execution_attempt: executionAttempt, code_attempt: 0, proposal_attempt: planned || portfolioDraft ? 1 : 0,
    study_literature_attempt: planned ? 2 : 0, draft_attempt: 0, redesign_attempt: 0,
    parent_research_id: null, root_research_id: null, followup_research_id: null, supporting_documents: [],
    resume_kind: planned || portfolioDraft ? 'authoring' : 'preparation', instructions: 'Synthetic static source reading.',
    artifacts: {}, schemas: { repository_plan: {} }, author_metadata: null,
    material_manifest: { source: sourceInventory, experiment: [], literature: [], references: [] },
    repository_paper: { publication_venues: catalog, plan: planned || portfolioDraft ? structuredClone(plan) : null,
      analysis: null, analysis_attempts: 0, draft: null, review: null, artifact_ids: {},
      analysis_provenance: { method: 'automated_ai_assisted_source_analysis', execution_performed: false,
        human_analysis_verified: false, human_approval_verified: false, model_calls: [] },
      portfolio: portfolioDraft ? { venues: [{ venue_id: 'ieee-software', draft: { title: 'Synthetic retained magazine article' } },
        { venue_id: 'ieee-security-privacy', draft: null }] } : null } };
  const retain = (key, value) => {
    const text = JSON.stringify(value);
    return workflow.artifacts[key] ??= { id: key, sha256: sha(text), size: Buffer.byteLength(text) };
  };
  retain('context', { synthetic: true });
  if (workflow.repository_paper.plan) retain('repository-plan-1', workflow.repository_paper.plan);
  const engine = { async start() {}, async close() {}, async request(method, params = {}) {
    calls.push({ method, params: structuredClone(params) });
    if (method === 'runtime.status') return { ready: false, repository_analysis_ready: true };
    if (method === 'workflow.list') return exists ? [structuredClone(workflow)] : [];
    if (method === 'workflow.status') return structuredClone(workflow);
    if (method === 'workflow.create') { exists = true; assert.equal(params.researchMode, 'repository_analysis'); }
    else if (method === 'workflow.resume') { workflow.status = 'ready'; workflow.code = null; }
    else if (method === 'workflow.recordInference') {
      const receipt = params.receipt, key = `model-evidence-${receipt.id}-${receipt.outcome}`;
      if (!receipts.some(item => item.id === receipt.id && item.outcome === receipt.outcome)) receipts.push(structuredClone(receipt));
      const artifact = retain(key, receipt);
      return { artifactId: artifact.id, sha256: artifact.sha256 };
    } else if (method === 'workflow.submitRepositoryPlan') {
      if (failPlanSubmission) { failPlanSubmission = false; throw new EngineError('ENGINE_PROTOCOL_INVALID', 'Synthetic plan persistence interruption.'); }
      workflow.repository_paper.plan = structuredClone(params.value);
      workflow.stage = 'repository_planned'; workflow.proposal_attempt++; workflow.resume_kind = 'authoring';
      retain('repository-plan-1', params.value);
    } else if (method === 'workflow.setAuthorMetadata') {
      const artifact = retain('author-metadata-1', params.value), selection = retain('author-selection-1', { selected: artifact.id });
      workflow.author_metadata = { origin: 'explicit_human_author_metadata', artifact_id: artifact.id,
        sha256: artifact.sha256, selection_artifact_id: selection.id, value: structuredClone(params.value) };
    } else throw new Error('Unexpected native operation before the portfolio boundary: ' + method);
    return structuredClone(workflow);
  } };
  const client = { async getSession() { return { status: connected ? 'connected' : 'disconnected', sharing: connected, profileId: 'synthetic-profile' }; },
    async listModels() { return [{ slug: 'writer' }, { slug: 'reviewer' }]; },
    async streamResponse(options) {
      const prompt = options.input[0].content; prompts.push(prompt);
      if (prompt.startsWith('Develop one worthwhile paper')) {
        return { text: JSON.stringify({ ...plan, contribution: oversizedContribution ? 'Synthetic contribution '.repeat(300) : plan.contribution }) };
      }
      if (prompt.startsWith('Condense only the oversized contribution')) {
        if (failPlanRepair) throw new ChatGPTError('stream_interrupted', 'Synthetic failed plan repair.');
        const marker = '\n\nExact original-plan binding and unchanged candidate:\n';
        const binding = JSON.parse(prompt.slice(prompt.indexOf(marker) + marker.length)).binding;
        return { text: JSON.stringify({ original_plan_text_sha256: binding.originalPlanTextSha256, contribution: plan.contribution }) };
      }
      throw new Error('Unexpected generic model phase before the portfolio boundary.');
    } };
  const controller = new ResearchController(client, engine, home, () => {});
  // Isolate planning-material and portfolio components, keeping public routing,
  // controller request receipts, persistence, transition checks and lease intact.
  controller.planningMaterials = async () => ({ text: '\nSynthetic frozen source material:\n' + sourceText });
  controller.runRepositoryPortfolio = async (job, retained, signal) => {
    assert.ok(retained.repository_paper.plan);
    portfolioEntries.push({ workflow: structuredClone(retained), aborted: signal.aborted });
    await portfolioGate;
    throw new EngineError('TEST_PORTFOLIO_BOUNDARY', 'Synthetic routing reached the separately tested portfolio component.');
  };
  await controller.initialize();
  return { controller, workflow, calls, prompts, receipts, portfolioEntries, releasePortfolio,
    disconnect() { connected = false; }, async cleanup() {
      releasePortfolio?.(); await settled(controller); await controller.shutdown();
      assert.equal(dirname(home), tmpdir()); assert.ok(home.includes('pf-magazine-routing-'));
      await rm(home, { recursive: true, force: true });
    } };
}

async function settled(controller) {
  for (let i = 0; i < 600; i++) { if (!controller.snapshot().busy) return controller.snapshot(); await delay(5); }
  throw new Error('Synthetic routing controller did not settle.');
}
async function enteredPortfolio(f) {
  for (let i = 0; i < 600; i++) { if (f.portfolioEntries.length) return; await delay(5); }
  throw new Error('The planned study did not reach the portfolio component.');
}
const assertNoGenericPaper = f => {
  assert.equal(f.workflow.draft_attempt, 0); assert.equal(f.workflow.code_attempt, 0); assert.equal(f.workflow.execution_attempt, 0);
  assert.equal(f.calls.some(call => /submitRepositoryAnalysis|submitRepositoryManuscript|submitRepositoryReview|startExperiment|submitCode/.test(call.method)), false);
  assert.equal(f.receipts.some(receipt => ['source-analysis', 'manuscript', 'manuscript-review'].includes(receipt.phase)), false);
};

test('new magazine research goes from one preserved plan directly to portfolio without a generic manuscript or review', async () => {
  const f = await fixture();
  try {
    await f.controller.create(input); await settled(f.controller);
    assert.equal(f.portfolioEntries.length, 1); assert.equal(f.workflow.proposal_attempt, 1);
    assert.deepEqual(f.workflow.repository_paper.plan.publication_target.candidates.map(candidate => candidate.venue_id).sort(), ['ieee-security-privacy', 'ieee-software']);
    assert.equal(f.prompts.length, 1); assert.ok(f.prompts[0].startsWith('Develop one worthwhile paper'));
    assert.deepEqual(f.receipts.map(receipt => receipt.outcome), ['started', 'completed']); assertNoGenericPaper(f);
  } finally { await f.cleanup(); }
});

test('the actual active lease stays busy across automatic portfolio handoff and rejects a second start', async () => {
  const f = await fixture({ holdPortfolio: true });
  try {
    await f.controller.create(input); await enteredPortfolio(f); assert.equal(f.controller.snapshot().busy, true);
    await assert.rejects(f.controller.create(input), error => error.code === 'RESEARCH_BUSY');
    assert.equal(f.calls.filter(call => call.method === 'workflow.create').length, 1);
    f.releasePortfolio(); await settled(f.controller); assert.equal(f.controller.snapshot().busy, false);
  } finally { await f.cleanup(); }
});

test('resuming a retained plan enters the magazine portfolio without regenerating a plan or resetting counts', async () => {
  const f = await fixture({ planned: true });
  try {
    const preserved = structuredClone(f.workflow);
    await f.controller.resume(f.workflow.id, 'writer', 'reviewer'); await settled(f.controller);
    assert.equal(f.portfolioEntries.length, 1); assert.equal(f.prompts.length, 0);
    assert.deepEqual(f.workflow.repository_paper.plan, preserved.repository_paper.plan);
    assert.equal(f.workflow.proposal_attempt, 1); assert.equal(f.workflow.study_literature_attempt, 2);
    assert.equal(f.calls.some(call => call.method === 'workflow.submitRepositoryPlan'), false); assertNoGenericPaper(f);
  } finally { await f.cleanup(); }
});

test('a completed plan and contribution repair replay after persistence interruption without another model request', async () => {
  const f = await fixture({ oversizedContribution: true, failPlanSubmission: true });
  try {
    await f.controller.create(input); await settled(f.controller);
    assert.equal(f.workflow.proposal_attempt, 0); assert.equal(f.portfolioEntries.length, 0);
    const original = f.receipts.find(receipt => receipt.outcome === 'completed' && receipt.prompt.startsWith('Develop one worthwhile paper'));
    assert.ok(JSON.parse(original.text).contribution.length > 6000);
    const preserved = structuredClone(f.workflow.artifacts);
    await f.controller.resume(f.workflow.id, 'writer', 'reviewer'); await settled(f.controller);
    assert.equal(f.prompts.length, 2); assert.equal(f.workflow.proposal_attempt, 1); assert.equal(f.portfolioEntries.length, 1);
    assert.deepEqual(f.workflow.repository_paper.plan, plan);
    for (const [key, artifact] of Object.entries(preserved)) assert.deepEqual(f.workflow.artifacts[key], artifact);
    assertNoGenericPaper(f);
  } finally { await f.cleanup(); }
});

test('a failed contribution repair retains its original plan and single consumed request on resume', async () => {
  const f = await fixture({ oversizedContribution: true, failPlanRepair: true });
  try {
    await f.controller.create(input); await settled(f.controller);
    await f.controller.resume(f.workflow.id, 'writer', 'reviewer'); const state = await settled(f.controller);
    assert.equal(state.error.code, 'PLAN_REPAIR_INCOMPLETE');
    assert.equal(f.prompts.length, 2); assert.equal(f.workflow.proposal_attempt, 0); assert.equal(f.portfolioEntries.length, 0);
    assert.equal(f.receipts.filter(receipt => receipt.outcome === 'failed').length, 1); assertNoGenericPaper(f);
  } finally { await f.cleanup(); }
});

test('nonzero execution history cannot enter fresh static planning or the magazine portfolio', async () => {
  const f = await fixture({ executionAttempt: 1 });
  try {
    await f.controller.create(input); const state = await settled(f.controller);
    assert.equal(state.error.code, 'RESEARCH_STATE_INVALID'); assert.equal(f.prompts.length, 0); assert.equal(f.portfolioEntries.length, 0);
    assert.equal(f.workflow.execution_attempt, 1);
  } finally { await f.cleanup(); }
});

test('a portfolio-only magazine draft enables explicit author metadata without models or a generic base draft', async () => {
  const f = await fixture({ portfolioDraft: true });
  try {
    assert.equal(f.controller.snapshot().jobs[0].manuscriptAvailable, true);
    const preserved = structuredClone(f.workflow.repository_paper);
    f.disconnect(); await f.controller.setAuthorMetadata(f.workflow.id, author);
    assert.deepEqual(f.workflow.author_metadata.value, author); assert.deepEqual(f.workflow.repository_paper, preserved);
    assert.equal(f.workflow.repository_paper.draft, null); assert.equal(f.prompts.length, 0);
    assert.equal(f.workflow.proposal_attempt, 1); assertNoGenericPaper(f);
  } finally { await f.cleanup(); }
});

test('a plan without any actual magazine draft cannot enable author entry or metadata mutation', async () => {
  const f = await fixture({ planned: true });
  try {
    assert.equal(f.controller.snapshot().jobs[0].manuscriptAvailable, false);
    await assert.rejects(f.controller.setAuthorMetadata(f.workflow.id, author), error => error.code === 'AUTHOR_ACTION_NOT_ALLOWED');
    assert.equal(f.calls.some(call => call.method === 'workflow.setAuthorMetadata'), false); assert.equal(f.prompts.length, 0);
    assert.equal(f.workflow.author_metadata, null); assertNoGenericPaper(f);
  } finally { await f.cleanup(); }
});
