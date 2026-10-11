import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { after, test } from 'node:test';
import { build } from 'esbuild';
import { ChatGPTError } from '@siwc/local';

// Source-compiled component test, isolated from the real app build and research data.
const desktop = resolve(fileURLToPath(new URL('..', import.meta.url)));
const compiledDirectory = await mkdtemp(join(desktop, '.documentation-component-'));
const compiledPath = join(compiledDirectory, 'research.mjs');
const compiled = await build({ entryPoints: [fileURLToPath(new URL('../src/main/research.ts', import.meta.url))],
  bundle: true, platform: 'node', format: 'esm', target: 'node22', external: ['@siwc/local'], write: false });
await writeFile(compiledPath, compiled.outputFiles[0].contents);
const { ResearchController } = await import(pathToFileURL(compiledPath).href);
after(async () => { assert.equal(dirname(compiledDirectory), desktop); await rm(compiledDirectory, { recursive: true, force: true }); });
const catalog = JSON.parse(await readFile(new URL('../../src/paper_factory/publication_venues.json', import.meta.url), 'utf8'));
const sha = value => createHash('sha256').update(value).digest('hex');
const selection = { references: [{ url: 'https://authoritative.example.test/security', purpose: 'comparison',
  reason: 'Inspect the exact official sender validation and operation exposure recommendations.' }], venue_suggestions: [] };
const documentationText = 'Synthetic complete primary documentation body: validate a message sender and expose a separate operation. This is test data only.';

async function fixture({ failSelection = false, failCollectionOnce = false, value = selection, priorCollections = [] } = {}) {
  const home = await mkdtemp(join(tmpdir(), 'pf-documentation-component-'));
  const calls = [], prompts = [], receipts = [];
  const workflow = { id: 'research-abcdef123456', goal: 'Synthetic primary-document selection without execution.',
    research_mode: 'repository_analysis', stage: 'repository_manuscript', status: 'ready', code: null, message: null,
    cleanup_pending: false, terminal_control_failure: false, execution_attempt: 0, code_attempt: 0,
    proposal_attempt: 1, study_literature_attempt: 1, draft_attempt: 0, redesign_attempt: 0,
    parent_research_id: null, root_research_id: null, followup_research_id: null, supporting_documents: [],
    resume_kind: 'authoring', artifacts: {}, schemas: { repository_reference_selection: {} },
    repository_paper: { publication_venues: catalog, draft: null, review: null, analysis_attempts: 1,
      plan: { title: 'Synthetic documented decision', source_files: ['src/choice.js'] },
      references: [], reference_collections: structuredClone(priorCollections),
      portfolio: { sha256: sha('synthetic portfolio'), analysis_sha256: sha('synthetic analysis'), venues: [{
        venue_id: 'ieee-software', draft: null, draft_sha256: sha('synthetic draft'), artifact_ids: { review: 'synthetic-review' },
        review: { next_actions: [{ action: 'retrieve_documentation', target: 'Synthetic primary guidance',
          required_change: 'Inspect the actual complete official body.', verification: 'Check literal retained passages.' }] } }] } } };
  const retain = (key, value) => {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    return workflow.artifacts[key] ??= { id: key, sha256: sha(text), size: Buffer.byteLength(text) };
  };
  retain('synthetic-review', workflow.repository_paper.portfolio.venues[0].review);
  const engine = { async start() {}, async close() {}, async request(method, params = {}) {
    calls.push({ method, params: structuredClone(params) });
    if (method === 'runtime.status') return { ready: false, repository_analysis_ready: true };
    if (method === 'workflow.list') return [structuredClone(workflow)];
    if (method === 'workflow.status') return structuredClone(workflow);
    if (method === 'workflow.recordInference') {
      const receipt = params.receipt, key = `model-evidence-${receipt.id}-${receipt.outcome}`;
      if (!receipts.some(item => item.id === receipt.id && item.outcome === receipt.outcome)) receipts.push(structuredClone(receipt));
      const artifact = retain(key, receipt); return { artifactId: artifact.id, sha256: artifact.sha256 };
    }
    if (method === 'workflow.collectRepositoryReferences') {
      if (failCollectionOnce) { failCollectionOnce = false; throw new Error('Synthetic native collection persistence interruption.'); }
      assert.deepEqual(params.selection, value);
      const artifact = retain('synthetic-primary-text', documentationText);
      workflow.repository_paper.references.push({ source_id: 'synthetic-primary', purpose: 'comparison',
        url: value.references[0].url, text_sha256: artifact.sha256, text_artifact_id: artifact.id });
      workflow.repository_paper.reference_collections.push({ status: 'completed', requested: structuredClone(value.references),
        retained_sources: ['synthetic-primary'] });
      return structuredClone(workflow);
    }
    throw new Error('Unexpected documentation operation: ' + method);
  } };
  const client = { async getSession() { return { status: 'connected', sharing: true, profileId: 'synthetic-profile' }; },
    async listModels() { return [{ slug: 'writer' }, { slug: 'reviewer' }]; }, async streamResponse(options) {
      prompts.push(options.input[0].content);
      if (failSelection) throw new ChatGPTError('stream_interrupted', 'Synthetic failed document selection.');
      return { text: JSON.stringify(value) };
    } };
  const controller = new ResearchController(client, engine, home, () => {});
  controller.materials = async () => ({ text: '\nComplete synthetic frozen source material; not a research result.' });
  await controller.initialize();
  const job = controller.jobs.get(workflow.id); job.model = 'writer'; job.reviewerModel = 'reviewer';
  return { controller, workflow, calls, prompts, receipts,
    collect() { return controller.collectRepositoryDocumentation(job, structuredClone(workflow), new AbortController().signal); },
    async cleanup() { await controller.shutdown(); assert.equal(dirname(home), tmpdir()); await rm(home, { recursive: true, force: true }); } };
}

test('a focused primary-document selection retains its native body and updated workflow without changing research counts', async () => {
  const f = await fixture();
  try {
    const updated = await f.collect();
    assert.equal(f.prompts.length, 1); assert.ok(f.prompts[0].startsWith('Select focused primary comparison documentation'));
    assert.match(f.prompts[0], /current_reviews/); assert.match(f.prompts[0], /Inspect the actual complete official body/);
    assert.equal(updated.repository_paper.reference_collections.length, 1);
    assert.equal(updated.repository_paper.references[0].text_sha256, sha(documentationText));
    assert.deepEqual(f.receipts.map(receipt => [receipt.phase, receipt.outcome]), [['literature-plan', 'started'], ['literature-plan', 'completed']]);
    assert.equal(updated.proposal_attempt, 1); assert.equal(updated.study_literature_attempt, 1);
    assert.equal(updated.repository_paper.analysis_attempts, 1); assert.equal(updated.draft_attempt, 0);
    assert.equal(updated.code_attempt, 0); assert.equal(updated.execution_attempt, 0);
  } finally { await f.cleanup(); }
});

test('a completed document selection replays after native persistence failure without another model call', async () => {
  const f = await fixture({ failCollectionOnce: true });
  try {
    await assert.rejects(f.collect(), /Synthetic native collection persistence interruption/);
    assert.equal(f.workflow.repository_paper.reference_collections.length, 0);
    const preserved = structuredClone(f.workflow.artifacts), updated = await f.collect();
    assert.equal(f.prompts.length, 1); assert.equal(updated.repository_paper.reference_collections.length, 1);
    for (const [key, artifact] of Object.entries(preserved)) assert.deepEqual(f.workflow.artifacts[key], artifact);
    assert.equal(f.calls.filter(call => call.method === 'workflow.collectRepositoryReferences').length, 2);
  } finally { await f.cleanup(); }
});

test('a failed primary-document selection consumes one request and cannot repeat the same input or fetch bodies', async () => {
  const f = await fixture({ failSelection: true });
  try {
    await assert.rejects(f.collect(), error => error.code === 'stream_interrupted');
    await assert.rejects(f.collect(), error => /INCOMPLETE$/.test(error.code));
    assert.equal(f.prompts.length, 1); assert.equal(f.receipts.filter(receipt => receipt.outcome === 'failed').length, 1);
    assert.equal(f.calls.some(call => call.method === 'workflow.collectRepositoryReferences'), false);
    assert.equal(f.workflow.repository_paper.reference_collections.length, 0);
  } finally { await f.cleanup(); }
});

for (const [label, value] of [
  ['venue-purpose references', { ...selection, references: [{ ...selection.references[0], purpose: 'venue' }] }],
  ['venue suggestions', { ...selection, venue_suggestions: [{ name: 'Synthetic unrelated journal', url: 'https://venue.example.test' }] }],
]) test(`document selection rejects ${label} before any fetch and cannot regenerate its rejected response`, async () => {
  const f = await fixture({ value });
  try {
    await assert.rejects(f.collect(), error => error.code === 'PORTFOLIO_DOCUMENTATION_SCOPE');
    await assert.rejects(f.collect(), error => error.code === 'PORTFOLIO_DOCUMENTATION_SCOPE');
    assert.equal(f.prompts.length, 1); assert.equal(f.calls.some(call => call.method === 'workflow.collectRepositoryReferences'), false);
    assert.equal(f.workflow.repository_paper.reference_collections.length, 0);
  } finally { await f.cleanup(); }
});

test('exhausted primary-document collections stop before model selection or native fetching', async () => {
  const f = await fixture({ priorCollections: [{ status: 'completed' }, { status: 'completed' }, { status: 'completed' }] });
  try {
    await assert.rejects(f.collect(), error => error.code === 'REPOSITORY_REFERENCE_LIMIT');
    assert.equal(f.prompts.length, 0); assert.equal(f.calls.some(call => call.method === 'workflow.collectRepositoryReferences'), false);
  } finally { await f.cleanup(); }
});
