import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';

// Compile current source in memory; never replace the running app's dist or runtime.
async function sourceModule(path) {
  const result = await build({ entryPoints: [fileURLToPath(new URL(path, import.meta.url))], bundle: true, write: false,
    platform: 'node', format: 'esm', target: 'node22', plugins: [{ name: 'official-sdk-location', setup(builder) {
      builder.onResolve({ filter: /^@siwc\/local$/ }, () => ({ path: import.meta.resolve('@siwc/local'), external: true }));
    } }] });
  return import('data:text/javascript;base64,' + Buffer.from(result.outputFiles[0].text).toString('base64'));
}
const { ResearchController } = await sourceModule('../src/main/research.ts');
const { verifyPortfolioAuthorMetadataView, verifyPortfolioAuthorExport } = await sourceModule('../src/main/repository-author-output.ts');
const { inspectRepositoryPortfolioOutputs } = await sourceModule('../src/shared/publication.ts');
const { artifactFormat, isReadableArtifactId } = await sourceModule('../src/main/artifacts.ts');
const sha = text => createHash('sha256').update(text).digest('hex');

function fixture() {
  const texts = new Map();
  const state = { id: 'research-abcdef123456', goal: 'Synthetic byline output only', research_mode: 'repository_analysis',
    stage: 'repository_manuscript', status: 'ready', code: null, message: null, updated_at: '2026-01-01T00:00:00Z',
    cleanup_pending: false, terminal_control_failure: false, execution_attempt: 0, code_attempt: 0, draft_attempt: 0,
    proposal_attempt: 1, study_literature_attempt: 1, redesign_attempt: 0, parent_research_id: null, root_research_id: null,
    followup_research_id: null, supporting_documents: [], resume_kind: 'authoring', instructions: 'Synthetic fixture only',
    schemas: {}, artifacts: {}, repository_paper: { draft: null, review: null, analysis_attempts: 2,
      plan: { title: 'Synthetic portfolio' }, artifact_ids: {}, submission_ready: false,
      portfolio: { all_content_ready: true, completed: 2, total: 2, venues: [] } } };
  const retain = (id, value) => {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    texts.set(id, text); state.artifacts[id] = { id, sha256: sha(text), size: Buffer.byteLength(text) };
    if (state.material_manifest && (/^repository-author-selection-[1-9]\d*$/.test(id) || /-author-[1-3]-intent-[1-3]$/.test(id) || /-(?:pdf|docx)-conversion-author-[1-3]-[1-3]$/.test(id))) {
      const entry = { name: id, sha256: sha(text), size: Buffer.byteLength(text) };
      const prior = state.material_manifest.evidence.findIndex(item => item.name === id);
      if (prior < 0) state.material_manifest.evidence.push(entry);
      else state.material_manifest.evidence[prior] = entry;
    }
    return state.artifacts[id];
  };
  const authorArtifact = retain('author-metadata-aaaaaaaaaaaa', { synthetic: true });
  state.source_context = 'Synthetic frozen source context projection';
  retain('context', state.source_context);
  const selection = retain('repository-author-selection-1', { author_artifact_id: authorArtifact.id });
  state.author_metadata = { origin: 'explicit_human_author_metadata', artifact_id: authorArtifact.id,
    sha256: authorArtifact.sha256, selection_artifact_id: selection.id,
    value: { display_name: 'Synthetic Author', email: 'author@example.test', affiliation: 'Synthetic Institute' } };
  for (const venueId of ['ieee-software', 'ieee-security-privacy']) {
    const prefix = `repository-portfolio-${venueId}`;
    const draft = { title: 'Synthetic retained article', sections: [{ heading: 'Abstract', text: 'Synthetic fixture only.' }],
      source_evidence: [], literature_evidence: [], document_evidence: [], revision: null };
    const ids = Object.fromEntries(['draft', 'markdown', 'review', 'pdf', 'docx'].map(kind => [kind, `${prefix}-${kind}-2`]));
    for (const [kind, id] of Object.entries(ids)) retain(id, kind === 'draft' ? draft : `Synthetic frozen ${kind} ${venueId}`);
    const input = retain(`${prefix}-export-markdown-2`, '# Synthetic article\n\nPreserved scientific bytes.');
    const receipt = retain(`${prefix}-export-2`, { input_artifact_id: input.id, input_sha256: input.sha256 });
    state.repository_paper.portfolio.venues.push({ venue_id: venueId, article_category: 'Feature Article',
      admitted_drafts: 2, draft_attempts: 2, review_attempts: 2, draft, review: { issues: [] },
      draft_sha256: state.artifacts[ids.draft].sha256, artifact_ids: ids,
      status: 'content_ready', scientific_ready: true, content_ready: true, submission_ready: false, analysis_current: true,
      export_status: 'completed', export: { artifact_id: receipt.id, sha256: receipt.sha256, errors: [] },
      export_repair_attempts: 0, format_export: null, layout_export: null,
      author_export_attempts: 0, author_export_available: true, author_export_status: 'not_started', author_export: null });
  }
  state.material_manifest = { source: [{ name: 'src/synthetic.ts', sha256: sha('frozen source'), size: 13 }], experiment: [],
    evidence: [{ name: selection.id, sha256: selection.sha256, size: selection.size }],
    literature: [{ name: 'synthetic-literature', sha256: sha('frozen literature'), size: 17 }],
    references: [{ name: 'synthetic-reference', sha256: sha('frozen primary reference'), size: 24 }],
    read_costs: { source: [{ name: 'src/synthetic.ts', full_bytes: 13 }] } };
  const before = structuredClone(state);
  const exportAuthor = (failed = false) => {
    const venue = state.repository_paper.portfolio.venues[0], prefix = `repository-portfolio-${venue.venue_id}`;
    const attempt = venue.author_export_attempts + 1;
    const input = retain(`${prefix}-export-markdown-author-${attempt}-2`, '# Synthetic article\n\nSynthetic Author\n\nPreserved scientific bytes.');
    const bindings = { venue_id: venue.venue_id, draft_attempt: 2, draft_artifact_id: venue.artifact_ids.draft,
      draft_sha256: venue.draft_sha256, markdown_artifact_id: venue.artifact_ids.markdown,
      markdown_sha256: state.artifacts[venue.artifact_ids.markdown].sha256, review_artifact_id: venue.artifact_ids.review,
      review_sha256: state.artifacts[venue.artifact_ids.review].sha256, base_export_artifact_id: venue.export.artifact_id,
      base_export_sha256: venue.export.sha256, base_input_artifact_id: `${prefix}-export-markdown-2`,
      base_input_sha256: state.artifacts[`${prefix}-export-markdown-2`].sha256,
      author_artifact_id: state.author_metadata.artifact_id, author_sha256: state.author_metadata.sha256 };
    retain(`${prefix}-author-${attempt}-intent-2`, { bindings, input_sha256: input.sha256, model_calls: 0 });
    const outputs = {};
    for (const kind of failed ? ['pdf'] : ['pdf', 'docx']) {
      const output = retain(`${prefix}-${kind}-author-${attempt}-2`, `Synthetic author ${kind}`);
      const conversion = retain(`${prefix}-${kind}-conversion-author-${attempt}-2`, {
        input_sha256: input.sha256, output_sha256: output.sha256 });
      outputs[kind] = { artifact_id: output.id, sha256: output.sha256, conversion_artifact_id: conversion.id };
      if (!failed) venue.artifact_ids[kind] = output.id;
    }
    const value = { bindings, input_artifact_id: input.id, input_sha256: input.sha256,
      author_artifact_id: state.author_metadata.artifact_id, author_sha256: state.author_metadata.sha256,
      draft_sha256: bindings.draft_sha256, markdown_sha256: bindings.markdown_sha256,
      author_block_sha256: sha('Synthetic author block'), body_sha256: sha('Preserved scientific bytes.'),
      outputs, errors: failed ? [{ format: 'docx', message: 'Synthetic conversion failure' }] : [],
      model_calls: 0, scope: 'explicit-author-block-only', scientific_approval_changed: false };
    const receipt = retain(`${prefix}-export-author-${attempt}-2`, value);
    venue.author_export = { ...value, artifact_id: receipt.id, sha256: receipt.sha256, status: failed ? 'failed' : 'completed', current: true, attempt };
    venue.author_export_attempts++; venue.author_export_status = venue.author_export.status;
    venue.author_export_available = failed && venue.author_export_attempts < 3;
    return structuredClone(state);
  };
  return { before, state, texts, exportAuthor, retain };
}

test('author receipt selects exact author Markdown, PDF and Word while retaining scientific draft and review', () => {
  const f = fixture(), next = f.exportAuthor(), venue = next.repository_paper.portfolio.venues[0];
  verifyPortfolioAuthorExport(f.before, next, venue.venue_id);
  const outputs = inspectRepositoryPortfolioOutputs(venue, Object.values(next.artifacts), next.author_metadata);
  assert.deepEqual(outputs.map(item => item.format), ['markdown', 'pdf', 'docx']);
  assert.equal(outputs[0].artifact.id, venue.author_export.input_artifact_id);
  assert.equal(venue.artifact_ids.markdown, f.before.repository_paper.portfolio.venues[0].artifact_ids.markdown);
  assert.equal(venue.draft_attempts, 2); assert.equal(venue.review_attempts, 2); assert.equal(venue.submission_ready, false);
  assert.deepEqual(next.repository_paper.portfolio.venues[1], f.before.repository_paper.portfolio.venues[1]);
});

test('stale authors and changed input, review, base export or conversion pointers cannot expose author files', () => {
  const mutations = [
    f => { f.state.author_metadata.sha256 = sha('changed author'); },
    f => { f.state.repository_paper.portfolio.venues[0].author_export_status = 'stale'; },
    f => { f.state.repository_paper.portfolio.venues[0].author_export.bindings.review_sha256 = sha('changed review'); },
    f => { f.state.repository_paper.portfolio.venues[0].author_export.bindings.base_input_sha256 = sha('changed base'); },
    f => { f.state.repository_paper.portfolio.venues[0].author_export.input_sha256 = sha('changed input'); },
    f => { f.state.repository_paper.portfolio.venues[0].author_export.outputs.pdf.conversion_artifact_id = 'foreign-conversion'; },
  ];
  for (const [index, mutate] of mutations.entries()) {
    const f = fixture(); f.exportAuthor(); mutate(f);
    const venue = f.state.repository_paper.portfolio.venues[0];
    assert.equal(inspectRepositoryPortfolioOutputs(venue, Object.values(f.state.artifacts), f.state.author_metadata)
      .some(output => output.artifact.id.includes('-author-') && (index === mutations.length - 1 ? output.format === 'pdf' : true)), false);
  }
});

test('author transition rejects mutations to science, counts, other venues, approvals and input proof', () => {
  for (const mutate of [
    state => { state.repository_paper.portfolio.venues[0].draft.title = 'Changed science'; },
    state => { state.repository_paper.portfolio.venues[0].review_attempts = 0; },
    state => { state.repository_paper.portfolio.venues[1].status = 'needs_revision'; },
    state => { state.repository_paper.portfolio.venues[0].submission_ready = true; },
    state => { state.repository_paper.portfolio.venues[0].author_export.bindings.base_export_sha256 = sha('wrong receipt'); },
    state => { state.author_metadata.value.email = 'changed@example.test'; },
  ]) {
    const f = fixture(), next = f.exportAuthor(); mutate(next);
    assert.throws(() => verifyPortfolioAuthorExport(f.before, next, 'ieee-software'), error => error.code === 'RESEARCH_STATE_INVALID');
  }
});

test('failed output consumes its bounded attempt and preserves existing selected files', () => {
  const f = fixture(), next = f.exportAuthor(true), venue = next.repository_paper.portfolio.venues[0];
  verifyPortfolioAuthorExport(f.before, next, venue.venue_id);
  assert.equal(venue.author_export_attempts, 1); assert.equal(venue.author_export_available, true);
  assert.deepEqual(venue.artifact_ids, f.before.repository_paper.portfolio.venues[0].artifact_ids);
});

test('metadata may invalidate only author output views and cannot reset counts or alter an article', () => {
  const f = fixture(); f.exportAuthor(); const prior = structuredClone(f.state);
  const artifact = f.retain('author-metadata-bbbbbbbbbbbb', { synthetic: 'new-author' });
  f.state.author_metadata = { ...f.state.author_metadata, artifact_id: artifact.id, sha256: artifact.sha256 };
  const venue = f.state.repository_paper.portfolio.venues[0];
  venue.author_export = null; venue.author_export_status = 'stale'; venue.author_export_available = true;
  for (const kind of ['pdf', 'docx']) venue.artifact_ids[kind] = f.before.repository_paper.portfolio.venues[0].artifact_ids[kind];
  assert.equal(verifyPortfolioAuthorMetadataView(prior, f.state), true);
  venue.review_attempts = 0;
  assert.equal(verifyPortfolioAuthorMetadataView(prior, f.state), false);
});

test('portfolio downloads allow only active two venues, known output formats and bounded native attempts', () => {
  for (const venue of ['ieee-software', 'ieee-security-privacy']) {
    for (const [name, extension] of [['markdown-2', 'md'], ['pdf-2', 'pdf'], ['docx-layout-2', 'docx'],
      ['export-markdown-format-2', 'md'], ['pdf-author-3-2', 'pdf'], ['docx-author-1-1', 'docx'], ['export-markdown-author-3-2', 'md']]) {
      const id = `repository-portfolio-${venue}-${name}`;
      assert.equal(isReadableArtifactId(id), true); assert.equal(artifactFormat(id).extension, extension);
    }
  }
  for (const id of ['repository-portfolio-unknown-pdf-1', 'repository-portfolio-ieee-software-draft-2',
    'repository-portfolio-ieee-software-export-author-1-2', 'repository-portfolio-ieee-software-pdf-conversion-author-1-2',
    'repository-portfolio-ieee-software-author-1-intent-2', 'repository-portfolio-ieee-software-markdown-author-1-2',
    'repository-portfolio-ieee-software-pdf-author-4-2', 'repository-portfolio-ieee-software-pdf-author-1-4',
    'repository-portfolio-ieee-software-pdf-../paper', 'repository-portfolio-ieee-software-pdf-2/raw']) {
    assert.equal(isReadableArtifactId(id), false); assert.equal(artifactFormat(id), undefined);
  }
});

async function controllerFixture(t, mutate = () => {}, failed = false, mutateMetadata = () => {}) {
  const f = fixture(), directory = await mkdtemp(join(tmpdir(), 'pf-author-output-')), calls = [], prompts = [];
  t.after(() => rm(directory, { recursive: true, force: true }));
  const engine = { async start() {}, async close() {}, async request(method, params = {}) {
    calls.push({ method, params });
    if (method === 'runtime.status') return { ready: false, repository_analysis_ready: true };
    if (method === 'workflow.list') return [structuredClone(f.state)];
    if (method === 'workflow.status') return structuredClone(f.state);
    if (method === 'workflow.exportPortfolioAuthor') {
      const next = f.exportAuthor(failed);
      // Native status(context=True) includes source_context; mutation(context=False) omits it.
      delete next.source_context; mutate(next, f); return next;
    }
    if (method === 'workflow.setAuthorMetadata') {
      const artifact = f.retain('author-metadata-bbbbbbbbbbbb', params.value);
      const selection = f.retain('repository-author-selection-2', { author_artifact_id: artifact.id, author_sha256: artifact.sha256 });
      f.state.author_metadata = { origin: 'explicit_human_author_metadata', artifact_id: artifact.id,
        sha256: artifact.sha256, selection_artifact_id: selection.id, value: structuredClone(params.value) };
      const next = structuredClone(f.state); delete next.source_context; mutateMetadata(next); return next;
    }
    if (method === 'workflow.readMaterial') {
      const full = f.texts.get(params.name), points = [...full], text = points.slice(params.offset, params.offset + params.limit).join('');
      return { research_id: f.state.id, area: params.area, name: params.name, offset: params.offset, limit: params.limit,
        text, sha256: sha(full), total_chars: points.length, is_untrusted_data: true, next_offset: null };
    }
    throw new Error('Unexpected operation: ' + method);
  } };
  const client = { async getSession() { return { status: 'disconnected', sharing: false }; },
    async streamResponse(options) { prompts.push(options); throw new Error('No model calls permitted'); } };
  const controller = new ResearchController(client, engine, directory, () => {});
  t.after(() => controller.shutdown());
  await controller.initialize();
  return { ...f, controller, calls, prompts };
}

test('controller author export runs offline with native conversions and repeated current output is idempotent', async t => {
  const f = await controllerFixture(t);
  await f.controller.exportRepositoryPortfolioAuthor(f.state.id, 'ieee-software');
  await f.controller.exportRepositoryPortfolioAuthor(f.state.id, 'ieee-software');
  assert.equal(f.calls.filter(call => call.method === 'workflow.exportPortfolioAuthor').length, 1);
  assert.equal(f.calls.filter(call => call.method === 'workflow.readMaterial').length, 2);
  assert.equal(f.prompts.length, 0); assert.equal(f.state.draft_attempt, 0);
  assert.equal(f.state.repository_paper.portfolio.venues[0].draft_attempts, 2);
  const appended = f.state.material_manifest.evidence.slice(f.before.material_manifest.evidence.length).map(item => item.name);
  assert.deepEqual(appended, ['repository-portfolio-ieee-software-author-1-intent-2',
    'repository-portfolio-ieee-software-pdf-conversion-author-1-2', 'repository-portfolio-ieee-software-docx-conversion-author-1-2']);
});

test('actual native metadata evidence projection appends only the selected author receipt without changing research', async t => {
  const f = await controllerFixture(t), previous = structuredClone(f.state.material_manifest);
  const value = { display_name: 'Synthetic Updated Author', email: 'updated@example.test', affiliation: 'Synthetic Updated Institute',
    biography: 'A supplied public biography retained as plain text, without author approval.' };
  await f.controller.setAuthorMetadata(f.state.id, value);
  assert.deepEqual(f.controller.snapshot().jobs[0].authorMetadata.value, value);
  assert.deepEqual(f.state.material_manifest.evidence.slice(0, previous.evidence.length), previous.evidence);
  assert.equal(f.state.material_manifest.evidence.at(-1).name, f.state.author_metadata.selection_artifact_id);
  for (const key of ['source', 'experiment', 'literature', 'references', 'read_costs']) assert.deepEqual(f.state.material_manifest[key], previous[key]);
  assert.equal(f.prompts.length, 0);
  for (const venue of f.state.repository_paper.portfolio.venues) { assert.equal(venue.draft_attempts, 2); assert.equal(venue.review_attempts, 2); }
});

test('author metadata response cannot silently discard the supplied biography', async t => {
  const f = await controllerFixture(t, undefined, false, next => { delete next.author_metadata.value.biography; });
  await assert.rejects(f.controller.setAuthorMetadata(f.state.id, {
    display_name: 'Synthetic Updated Author', email: 'updated@example.test', affiliation: 'Synthetic Updated Institute',
    biography: 'A supplied biography that must remain exact.',
  }), error => error.code === 'RESEARCH_STATE_INVALID');
  assert.equal(f.prompts.length, 0);
});

test('native context projection omission permits metadata and author output while retaining the exact frozen context', async t => {
  const f = await controllerFixture(t), original = structuredClone(f.state.artifacts.context);
  await f.controller.setAuthorMetadata(f.state.id,
    { display_name: 'Synthetic Updated Author', email: 'updated@example.test', affiliation: 'Synthetic Updated Institute' });
  await f.controller.exportRepositoryPortfolioAuthor(f.state.id, 'ieee-software');
  assert.deepEqual(f.state.artifacts.context, original);
  assert.equal(f.texts.get('context'), f.before.source_context);
  assert.equal(f.prompts.length, 0);
});

test('provided changed or null source context and changed frozen context artifact remain denied', async t => {
  for (const mutate of [next => { next.source_context = 'Changed source'; }, next => { next.source_context = null; },
    next => { next.artifacts.context.sha256 = sha('Changed frozen context'); }]) {
    const metadata = await controllerFixture(t, undefined, false, mutate);
    await assert.rejects(metadata.controller.setAuthorMetadata(metadata.state.id,
      { display_name: 'Synthetic Updated Author', email: 'updated@example.test', affiliation: 'Synthetic Updated Institute' }),
    error => error.code === 'RESEARCH_STATE_INVALID');
    const output = await controllerFixture(t, mutate);
    await assert.rejects(output.controller.exportRepositoryPortfolioAuthor(output.state.id, 'ieee-software'),
      error => error.code === 'RESEARCH_STATE_INVALID');
    assert.equal(metadata.prompts.length + output.prompts.length, 0);
  }
});

test('author metadata cannot alter old evidence, source, literature, references, read costs, instructions or author approvals', async t => {
  for (const mutate of [
    next => { next.material_manifest.evidence[0].sha256 = sha('changed old evidence'); },
    next => { next.material_manifest.source[0].size = 0; },
    next => { next.material_manifest.literature = []; },
    next => { next.material_manifest.references = []; },
    next => { next.material_manifest.read_costs.source[0].full_bytes = 0; },
    next => { next.material_manifest.evidence.push({ name: 'repository-forged-scientific-data', sha256: sha('forged'), size: 6 }); },
    next => { next.instructions += ' false author approval'; },
    next => { next.submission_confirmation = { approved: true }; },
  ]) {
    const f = await controllerFixture(t, undefined, false, mutate);
    await assert.rejects(f.controller.setAuthorMetadata(f.state.id,
      { display_name: 'Synthetic Updated Author', email: 'updated@example.test', affiliation: 'Synthetic Updated Institute' }),
    error => error.code === 'RESEARCH_STATE_INVALID');
    assert.equal(f.prompts.length, 0);
  }
});

test('controller rejects global count resets, source mutations and false conversion metadata', async t => {
  for (const mutate of [next => { next.proposal_attempt = 0; }, next => { next.source_context = 'Changed source'; },
    next => { next.submission_confirmation = { approved: true }; },
    (next, f) => {
      const id = next.repository_paper.portfolio.venues[0].author_export.outputs.pdf.conversion_artifact_id;
      const bad = f.retain(id, { input_sha256: sha('wrong input'), output_sha256: sha('wrong output') });
      next.artifacts[id] = bad;
    }]) {
    const f = await controllerFixture(t, mutate);
    await assert.rejects(f.controller.exportRepositoryPortfolioAuthor(f.state.id, 'ieee-software'), error => error.code === 'RESEARCH_STATE_INVALID');
    assert.equal(f.prompts.length, 0);
  }
});

test('missing author, exhausted output budget and malformed venue fail before export dispatch', async t => {
  for (const alter of [f => { f.state.author_metadata = null; }, f => {
    f.state.repository_paper.portfolio.venues[0].author_export_attempts = 3;
    f.state.repository_paper.portfolio.venues[0].author_export_available = false;
  }]) {
    const f = await controllerFixture(t); alter(f);
    await assert.rejects(f.controller.exportRepositoryPortfolioAuthor(f.state.id, 'ieee-software'));
    assert.equal(f.calls.some(call => call.method === 'workflow.exportPortfolioAuthor'), false);
  }
  const f = await controllerFixture(t);
  await assert.rejects(f.controller.exportRepositoryPortfolioAuthor(f.state.id, '../ieee-software'));
  assert.equal(f.calls.some(call => call.method === 'workflow.exportPortfolioAuthor'), false);
});
