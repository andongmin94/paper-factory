import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';

// Avoid embedding the entire in-memory source URL in an assertion failure.
Error.stackTraceLimit = 0;

async function sourceModule(name) {
  const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL(`../src/main/${name}.ts`, import.meta.url))],
    bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22', plugins: [{
      name: 'test-error-types', setup(builder) {
        builder.onResolve({ filter: /^\.\/engine\.js$/ }, () => ({ path: new URL('../dist/engine.js', import.meta.url).href, external: true }));
        builder.onResolve({ filter: /^@siwc\/local$/ }, () => ({ path: import.meta.resolve('@siwc/local'), external: true }));
      },
    }] });
  return import('data:text/javascript;base64,' + Buffer.from(outputFiles[0].text).toString('base64'));
}
const [{ ResearchController }, { portfolioEvidencePacket, verifyRepositoryRequestCapacity }] = await Promise.all([sourceModule('research'), sourceModule('repository-supplement')]);
const sha = text => createHash('sha256').update(text).digest('hex');
const portfolioMarker = '\n\nExact repository portfolio binding and complete scientific materials:\n';

// Synthetic transport/history fixtures establish no actual study or publication quality.
async function fixture(t, mutate = () => {}) {
  const directory = await mkdtemp(join(tmpdir(), 'pf-supplement-contract-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const texts = new Map(), requests = [];
  let sdkCalls = 0;
  const workflow = { id: 'research-123456abcdef', goal: 'Synthetic retained research', research_mode: 'repository_analysis',
    stage: 'repository_manuscript', status: 'ready', code: null, message: null,
    execution_attempt: 0, code_attempt: 0, proposal_attempt: 1, study_literature_attempt: 3, draft_attempt: 2,
    redesign_attempt: 0, parent_research_id: null, root_research_id: null, followup_research_id: null,
    cleanup_pending: false, terminal_control_failure: false, resume_kind: null, supporting_documents: [], artifacts: {},
    author_metadata: null, submission_contract: null, submission_readiness: null, submission_confirmation: null };
  const retain = (id, value) => {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    texts.set(id, text); workflow.artifacts[id] = { id, sha256: sha(text), size: Buffer.byteLength(text) };
    return workflow.artifacts[id];
  };
  const draft = { title: 'Preserved synthetic draft2', source_evidence: [], sections: [], literature_evidence: [], document_evidence: [] };
  const review = { criteria: { contribution: { passed: false, reason: 'Synthetic missing comparison.' } },
    content_assessment: { comparison: { passed: false }, contribution: { passed: false } },
    next_actions: [{ action: 'retrieve_documentation', target: 'Synthetic independent case', required_change: 'Add actual contrasting source.', verification: 'Inspect its original bytes.' }] };
  const d = retain('old-draft2', draft), r = retain('old-review2', review);
  const venue = { venue_id: 'science-computer-programming', article_category: 'research-article',
    draft_attempts: 2, admitted_drafts: 2, review_attempts: 2, draft, review, draft_sha256: d.sha256,
    artifact_ids: { draft: d.id, review: r.id, markdown: null, pdf: null, docx: null },
    writer_binding: null, writer_outcome: null, reviewer_binding: null, reviewer_outcome: null,
    scientific_ready: false, content_ready: false, submission_ready: false, analysis_current: true,
    revise_available: false, revise_reason: 'No changed scientific basis.' };
  workflow.repository_paper = { plan: { source_files: [] }, analysis_attempts: 3, draft, review,
    scientific_ready: false, content_ready: false, submission_ready: false, analysis: { method: 'Preserved analysis3', source_evidence: [] },
    portfolio: { artifact_id: 'old-start', sha256: sha('start'), analysis: { method: 'Preserved analysis3', source_evidence: [] }, analysis_sha256: sha('analysis3'),
      literature_sha256: sha('lit3'), literature_budget: { used: 3, limit: 3 }, pdf_budget: { total_used: 4, additional_used: 2, additional_limit: 2, base_used: 2 },
      analysis_revision: null, guidance: { sources: [] },
      supplementary_evidence: null, supplementary_evidence_budget: { used: 0, limit: 1 }, supplementary_evidence_available: true,
      venues: [venue], completed: 1, total: 9, all_content_ready: false } };
  const body = 'Synthetic complete independent source witness. '.repeat(800) + 'Final Unicode witness: 경계🙂.';
  const material = { id: 'supplement-case-a', kind: 'case_source', name: 'case.txt', sha256: sha(body),
    title: 'Synthetic independent source', url: 'https://github.com/example/independent/blob/abc/src/case.ts',
    provenance: 'supplied_snapshot', case_id: 'independent', path: 'src/case.ts', commit: 'abc' };
  const value = { prior_analysis_sha256: sha('analysis3'), prior_literature_sha256: sha('lit3'),
    reviews: [{ venue_id: venue.venue_id, draft_artifact_id: d.id, draft_sha256: d.sha256, review_artifact_id: r.id, review_sha256: r.sha256 }],
    members: [{ name: material.name, sha256: material.sha256, size: Buffer.byteLength(body) }], materials: [material],
    selection: { rationale: 'Synthetic required contrast.', lineage: 'Synthetic supplied snapshot, no acquisition or execution.' },
    comparison: { protocol: 'Synthetic literal witness contrast only.', provenance: 'supplied_interpretation',
      witnesses: [{ id: 'witness-a', material_id: material.id, quote: 'Final Unicode witness: 경계🙂.' }],
      results: [{ claim: 'Synthetic limited contrast.', evidence_ids: ['witness-a'], limitations: 'No real research.' }] } };
  const packet = { value, files: [{ name: material.name, contentBase64: Buffer.from(body).toString('base64') }] };
  const prior = structuredClone(workflow);
  const engine = { async start() {}, async request(method, params) {
    requests.push({ method, params });
    if (method === 'workflow.status') return structuredClone(workflow);
    if (method === 'workflow.admitPortfolioEvidence') {
      const materialArtifact = retain('supplement-member-case', body);
      const receipt = retain('supplement-receipt', value);
      const portfolio = workflow.repository_paper.portfolio;
      portfolio.supplementary_evidence = { artifact_id: receipt.id, sha256: receipt.sha256, status: 'admitted',
        affected_venues: [venue.venue_id], reviews: structuredClone(value.reviews), selection: value.selection, comparison: value.comparison,
        all_materials: [{ ...value.members[0], artifact_id: materialArtifact.id }],
        materials: [{ ...material, artifact_id: materialArtifact.id, size: materialArtifact.size }] };
      portfolio.supplementary_evidence_available = false; portfolio.supplementary_evidence_budget.used = 1;
      venue.revise_available = true; venue.revise_reason = 'Actual supplementary basis for the preserved review.';
      venue.writer_binding = { supplementary_evidence_sha256: receipt.sha256, attempt: 3, phase: 'venue-manuscript',
        venue_id: venue.venue_id, article_category: venue.article_category, prior_draft_sha256: d.sha256, prior_review_sha256: r.sha256 };
      mutate(workflow);
      return structuredClone(workflow);
    }
    if (method === 'workflow.readMaterial') {
      const full = texts.get(params.name), points = [...full];
      const text = points.slice(params.offset, params.offset + params.limit).join('');
      return { research_id: workflow.id, area: params.area, name: params.name, offset: params.offset, limit: params.limit,
        text, sha256: workflow.artifacts[params.name].sha256, total_chars: points.length, is_untrusted_data: true,
        next_offset: params.offset + [...text].length < points.length ? params.offset + [...text].length : null };
    }
    assert.fail(`Unexpected engine request: ${method}`);
  } };
  const controller = new ResearchController({ async streamResponse() { sdkCalls++; assert.fail('Import must not call a model'); } }, engine, directory, () => {});
  controller.restoring = false; controller.state.runtime = { state: 'ready', repositoryAnalysisReady: true, message: 'Synthetic ready' };
  controller.jobs.set(workflow.id, { id: workflow.id, goal: workflow.goal, researchMode: 'repository_analysis', model: 'synthetic', reviewerModel: 'synthetic',
    pipeline: 'paused', phase: 'idle', cleanupRequired: false, updatedAt: new Date().toISOString() });
  controller.materials = async () => ({ header: '\n', content: {} });
  return { controller, workflow, prior, packet, body, venue, requests, texts, sdkCalls: () => sdkCalls };
}

test('malformed and oversized import packages fail before any engine mutation', async t => {
  const f = await fixture(t);
  await assert.rejects(f.controller.admitRepositoryPortfolioEvidence(f.workflow.id, { ...f.packet, extra: true }), { code: 'PORTFOLIO_EVIDENCE_INVALID' });
  assert.throws(() => portfolioEvidencePacket({ ...f.packet, files: [{ name: 'large.txt', contentBase64: 'a'.repeat(2 * 1024 * 1024) }] }, f.workflow.id),
    { code: 'PORTFOLIO_EVIDENCE_INVALID' });
  assert.equal(f.requests.length, 0); assert.equal(f.sdkCalls(), 0);
});

test('whole case packets can contain more than eight files within the unchanged IPC limit', async t => {
  const f = await fixture(t);
  const files = Array.from({ length: 22 }, (_, index) => ({ name: `case-${index}.txt`, contentBase64: 'YQ==' }));
  assert.equal(portfolioEvidencePacket({ ...f.packet, files }, f.workflow.id).files.length, 22);
  assert.throws(() => portfolioEvidencePacket({ ...f.packet, files: Array.from({ length: 33 }, () => files[0]) }, f.workflow.id),
    { code: 'PORTFOLIO_EVIDENCE_INVALID' });
  assert.equal(f.requests.length, 0); assert.equal(f.sdkCalls(), 0);
});

test('additional complete-input capacity requires both the verified model and a bound supplement', () => {
  const body = 'a'.repeat(800_000);
  verifyRepositoryRequestCapacity(body, 'gpt-6.1-sol', true);
  for (const [model, bound] of [['gpt-6.1-sol', false], ['another-model', true]]) {
    assert.throws(() => verifyRepositoryRequestCapacity(body, model, bound), { code: 'REVIEW_CONTEXT_TOO_LARGE' });
  }
  verifyRepositoryRequestCapacity('a'.repeat(900_000), 'gpt-6.1-sol', true);
  assert.throws(() => verifyRepositoryRequestCapacity('a'.repeat(900_001), 'gpt-6.1-sol', true), { code: 'REVIEW_CONTEXT_TOO_LARGE' });
  // Fewer characters can have more bytes; Unicode cannot bypass the input/output reserve.
  assert.throws(() => verifyRepositoryRequestCapacity('한'.repeat(300_001), 'gpt-6.1-sol', true), { code: 'REVIEW_CONTEXT_TOO_LARGE' });
});

test('oversized bound requests fail before workflow reservation, model validation or SDK calls', async t => {
  const f = await fixture(t), job = f.controller.jobs.get(f.workflow.id);
  job.model = job.reviewerModel = 'gpt-6.1-sol';
  await assert.rejects(f.controller.generate(job, 'venue-manuscript', 'a'.repeat(900_001), new AbortController().signal, undefined, true),
    { code: 'REVIEW_CONTEXT_TOO_LARGE' });
  assert.equal(f.requests.length, 0); assert.equal(f.sdkCalls(), 0);
});

for (const [name, change] of [
  ['the exact frozen venue writer', frame => frame],
  ['another binding containing the same SHA', frame => ({ ...frame, venue_id: 'another-venue' })],
]) test(`complete-input capacity follows ${name}`, async t => {
  const f = await fixture(t);
  await f.controller.admitRepositoryPortfolioEvidence(f.workflow.id, f.packet);
  const frame = change(f.venue.writer_binding), prefix = 'Write capacity fixture.';
  const binding = portfolioMarker + JSON.stringify(frame) + '\n{}', prompt = prefix + binding;
  const job = f.controller.jobs.get(f.workflow.id), flags = [];
  let dispatched = false;
  f.controller.retainedInferenceReceipts = async () => dispatched ? [{ id: 'fixture-only', outcome: 'completed',
    prompt, text: '{"fixture":true}' }] : [];
  // This fixture observes source routing only; no actual provider or native model reservation is performed.
  f.controller.generate = async (_job, _phase, _prompt, _signal, _recovered, bound) => {
    flags.push(bound); dispatched = true;
  };
  await f.controller.repositoryGenerationOnce(job, f.workflow, 'venue-manuscript', prefix, prompt, binding, new AbortController().signal);
  assert.deepEqual(flags, [name === 'the exact frozen venue writer']);
  assert.equal(f.sdkCalls(), 0);
});

test('actual packet admission preserves old material, reviews, approvals and consumed budgets without SDK calls', async t => {
  const f = await fixture(t);
  const state = await f.controller.admitRepositoryPortfolioEvidence(f.workflow.id, f.packet);
  assert.equal(state.busy, false); assert.equal(f.sdkCalls(), 0);
  assert.deepEqual(f.requests.map(request => request.method), ['workflow.status', 'workflow.admitPortfolioEvidence']);
  for (const field of ['proposal_attempt', 'study_literature_attempt', 'draft_attempt', 'execution_attempt', 'code_attempt']) assert.equal(f.workflow[field], f.prior[field]);
  for (const field of ['draft', 'review', 'analysis', 'analysis_attempts']) assert.deepEqual(f.workflow.repository_paper[field], f.prior.repository_paper[field]);
  for (const [id, artifact] of Object.entries(f.prior.artifacts)) assert.deepEqual(f.workflow.artifacts[id], artifact);
  assert.equal(f.workflow.repository_paper.portfolio.supplementary_evidence_budget.used, 1);
  assert.equal(f.venue.writer_binding.attempt, 3); assert.equal(f.venue.draft_attempts, 2); assert.equal(f.venue.review_attempts, 2);
});

for (const [name, mutate] of [
  ['changed old artifact', workflow => { workflow.artifacts['old-review2'].sha256 = '0'.repeat(64); }],
  ['promoted approval', workflow => { workflow.repository_paper.portfolio.venues[0].scientific_ready = true; }],
  ['reset literature budget', workflow => { workflow.study_literature_attempt = 0; }],
  ['another local review binding', workflow => { workflow.repository_paper.portfolio.venues[0].writer_binding.prior_review_sha256 = '0'.repeat(64); }],
]) test(`admission rejects ${name} and keeps the cached old review`, async t => {
  const f = await fixture(t, mutate);
  await assert.rejects(f.controller.admitRepositoryPortfolioEvidence(f.workflow.id, f.packet), { code: 'RESEARCH_STATE_INVALID' });
  assert.equal(f.sdkCalls(), 0);
  assert.equal(f.controller.jobs.get(f.workflow.id).repositoryPaper, undefined);
});

test('the exact review-bound supplementary body reaches writer and reviewer context through Unicode EOF', async t => {
  const f = await fixture(t);
  await f.controller.admitRepositoryPortfolioEvidence(f.workflow.id, f.packet);
  for (const phase of ['venue-manuscript', 'venue-manuscript-review']) {
    const frame = { ...f.venue.writer_binding, phase };
    const content = JSON.parse(await f.controller.portfolioMaterials(f.workflow, new AbortController().signal, f.venue.venue_id, frame));
    const material = content.portfolioSupplement.materials[0];
    assert.equal(material.text, f.body); assert.equal(sha(material.text), f.packet.value.materials[0].sha256);
    assert.equal(material.totalChars, [...f.body].length); assert.equal(material.pages.length, 2); assert.equal(material.pages.at(-1).nextOffset, null);
    assert.equal(material.source_id, f.packet.value.materials[0].id);
    assert.equal(JSON.parse(content.portfolioSupplement.text).materials[0].commit, 'abc');
    assert.equal(content.portfolioSupplement.sha256, frame.supplementary_evidence_sha256);
  }
  assert.equal(f.sdkCalls(), 0);
});

test('a mismatched historical supplement or changed material cannot enter a new model context', async t => {
  const f = await fixture(t);
  await f.controller.admitRepositoryPortfolioEvidence(f.workflow.id, f.packet);
  const signal = new AbortController().signal;
  await assert.rejects(f.controller.portfolioMaterials(f.workflow, signal, f.venue.venue_id,
    { ...f.venue.writer_binding, supplementary_evidence_sha256: '0'.repeat(64) }), { code: 'ARTIFACT_CHANGED' });
  f.texts.set('supplement-member-case', f.body.replace('Final Unicode witness', 'Altered witness'));
  await assert.rejects(f.controller.portfolioMaterials(f.workflow, signal, f.venue.venue_id, f.venue.writer_binding), { code: 'ARTIFACT_CHANGED' });
  assert.equal(f.sdkCalls(), 0);
});
