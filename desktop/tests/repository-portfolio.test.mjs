import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { mkdir, mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { build } from 'esbuild';
import { EngineError } from '../dist/engine.js';
import { ChatGPTError } from '@siwc/local';

// Exercise current controller source without replacing the running app's dist/runtime.
const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/main/research.ts', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22', plugins: [{
    name: 'retained-test-error-types', setup(builder) {
      builder.onResolve({ filter: /^\.\/engine\.js$/ }, () => ({ path: new URL('../dist/engine.js', import.meta.url).href, external: true }));
      builder.onResolve({ filter: /^@siwc\/local$/ }, () => ({ path: import.meta.resolve('@siwc/local'), external: true }));
    },
  }] });
const { ResearchController } = await import('data:text/javascript;base64,' + Buffer.from(outputFiles[0].text).toString('base64'));

// Independent synthetic controller fixture. It establishes no real research or publication quality.
const catalog = JSON.parse(await readFile(new URL('../../src/paper_factory/publication_venues.json', import.meta.url), 'utf8'));
const digest = text => createHash('sha256').update(text).digest('hex');
const source = { 'src/choice.ts': 'export const choice = "synthetic-local";',
  'src/retained-analysis.ts': 'export const priorAnalysisOnly = "complete previously inspected synthetic witness";' };
const sourceEvidence = Object.entries(source).map(([path, quote], index) => ({ id: `witness-${index}`, path,
  sha256: digest(quote), quote, interpretation: 'Synthetic static witness only.' }));
const analysis = { method: 'Synthetic complete source analysis.', codebook: [], units: [], findings: [], counterexamples: [],
  source_evidence: sourceEvidence, literature_evidence: [], document_evidence: [], limitations: ['No actual research.'] };
const manuscript = title => ({ title, sections: [...['Abstract', 'The developer decision', 'What the source shows', 'Costs and limits'].map(heading => ({ heading,
  text: 'Synthetic bounded source interpretation only, without observed execution or actual scholarly result. {{source:witness-0}}' })),
  { heading: 'Actionable Insights', text: '- Inspect the literal boundary.\n- Compare the actual alternatives.\n- Retain the unsupported conditions.' },
  { heading: 'Acknowledgments', text: 'Synthetic model assistance only, with no human approval or actual study. '.repeat(2) }], source_evidence: [sourceEvidence[0]],
  literature_evidence: [], document_evidence: [], revision: null });
const review = () => ({ criteria: Object.fromEntries(['supported_findings', 'contribution', 'literature', 'method',
  'presentation', 'empirical_claims_absent', 'venue_fit'].map(key => [key, { passed: true, reason: 'Synthetic controller assertion only.' }])),
  issues: [], next_actions: [], content_assessment: { comparison: { passed: true, reason: 'Synthetic comparison.' },
    contribution: { passed: true, reason: 'Synthetic contribution.' }, issues: [], next_actions: [],
    literature_queries: [], pdf_candidates: [], revision_outline: [] } });

async function fixture(t, { failedWriter = null, partialWriter = null, failedRepair = false, alteredRepair = false,
  interruptedAdmission = null, globalError = null, rejectStartOnce = false, failedExport = null, failedExportRepair = false,
  revisionBodyChars = 0, negativeVenueReview = null } = {}) {
  const directory = await mkdtemp(join(tmpdir(), 'pf-independent-portfolio-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const requests = [], modelCalls = [], texts = new Map(), reservations = new Set();
  const targets = catalog.venues.map(venue => ({ venue_id: venue.id, article_category: venue.article_categories[0] }));
  const workflow = { id: 'research-123456abcdef', goal: 'Synthetic IEEE feature portfolio', research_mode: 'repository_analysis',
    stage: 'repository_manuscript', status: 'ready', code: null, message: null, cleanup_pending: false, terminal_control_failure: false,
    execution_attempt: 0, code_attempt: 0, proposal_attempt: 1, study_literature_attempt: 2, draft_attempt: 2, redesign_attempt: 0,
    parent_research_id: null, root_research_id: null, followup_research_id: null, supporting_documents: [], artifacts: {},
    material_manifest: { source: Object.entries(source).map(([name, text]) => ({ name, sha256: digest(text), size: Buffer.byteLength(text) })),
      experiment: [], literature: [], references: [] }, schemas: { repository_analysis: {}, repository_manuscript: { properties: {} }, repository_review: {} },
    repository_paper: { publication_venues: catalog, plan: { source_files: ['src/choice.ts'],
      publication_target: { ...targets[0], selection_reason: 'Synthetic original feature target.', candidates: [] } },
      analysis: structuredClone(analysis), analysis_attempts: 1, analysis_revision_required: false,
      draft: manuscript('Preserved original draft 2'), review: review(), scientific_ready: true, submission_ready: false,
      literature: null, revision_available: false, artifact_ids: { draft: 'repository-draft-2' } } };
  const retain = (id, value) => {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    const artifact = { id, sha256: digest(text), size: Buffer.byteLength(text) };
    if (workflow.artifacts[id]) assert.deepEqual(workflow.artifacts[id], artifact, 'Frozen evidence must not be replaced');
    workflow.artifacts[id] = artifact; texts.set(id, text); return artifact;
  };
  retain('repository-draft-2', workflow.repository_paper.draft);
  retain('repository-review-2', workflow.repository_paper.review);
  retain('repository-analysis-1', analysis);
  retain('repository-draft-pdf-2', 'Synthetic preserved PDF bytes');
  const portfolio = workflow.repository_paper.portfolio = { artifact_id: 'repository-portfolio-start', sha256: digest('synthetic start'),
    bindings: {}, targets, analysis: null, analysis_sha256: null, analysis_binding: null, analysis_outcome: null,
    analysis_revision: null, analysis_revision_available: false, analysis_revision_required: false,
    literature_followup_available: false, documentation_followup_available: false, literature_budget: { used: 2, limit: 3 },
    literature: null, literature_sha256: null, literature_collections: [{ artifact_id: 'synthetic-collection', sha256: digest('collection'),
      attempt: 2, queries: ['synthetic primary-body comparison'], status: 'completed' }],
    pdf_budget: { base_used: 2, additional_limit: 2, additional_used: 0, total_used: 2, base_reservations_sha256: digest('old reservations') },
    guidance: { artifact_id: 'synthetic-guidance', sha256: digest('guidance'), scope: 'Synthetic official guidance only.',
      sources: targets.map(target => {
        const artifact = retain(`synthetic-guidance-${target.venue_id}`, `Complete synthetic submission guidance for ${target.venue_id}.`);
        return { venue_id: target.venue_id, url: 'https://example.test/guidelines', status: 'retained', failure: null,
          text_artifact_id: artifact.id, text_sha256: artifact.sha256, text_size: artifact.size, text_chars: [...texts.get(artifact.id)].length };
      }) }, venues: [], all_content_ready: false, completed: 0, total: targets.length };
  const frame = (phase, target = null) => ({ research_id: workflow.id, portfolio_start_sha256: portfolio.sha256,
    source_digest: digest('source'), source_commit: 'synthetic-commit', plan_sha256: digest('plan'), base_analysis_sha256: digest('base analysis'),
    catalog_sha256: digest(JSON.stringify(catalog)), guidance_sha256: portfolio.guidance.sha256, literature_sha256: null,
    portfolio_analysis_sha256: portfolio.analysis_sha256, phase, venue_id: target?.venue_id ?? null,
    article_category: target?.article_category ?? null, attempt: phase === 'source-analysis' ? 2 : 1,
    prior_draft_sha256: null, draft_sha256: null, markdown_sha256: null });
  portfolio.analysis_binding = frame('source-analysis');
  portfolio.venues = targets.map(target => ({ ...target, draft_attempts: 0, review_attempts: 0, admitted_drafts: 0,
    draft: null, review: null, draft_sha256: null, artifact_ids: { draft: null, markdown: null, review: null, pdf: null, docx: null },
    status: 'pending_analysis', scientific_ready: false, content_ready: false, submission_ready: false, analysis_current: true,
    revise_available: false, revise_reason: 'No changed scientific basis in this synthetic fixture.',
    writer_binding: frame('venue-manuscript', target), reviewer_binding: null, writer_outcome: null, reviewer_outcome: null,
    repair_attempts: 0, repair_binding: null, repair_outcome: null,
    export_repair_available: false, export_repair_attempts: 0, export_repair_total: 0,
    format_export_available: false, format_export_attempts: 0, format_export: null,
    layout_export_available: false, layout_export_attempts: 0, layout_export: null,
    export_status: 'not_started', export: null }));
  const original = structuredClone(workflow);
  let admissionInterrupted = false;
  const engine = { async start() {}, async request(method, params) {
    requests.push({ method, params: structuredClone(params) });
    assert.equal(params.researchId, workflow.id);
    if (method === 'workflow.status') return structuredClone(workflow);
    if (method === 'workflow.resume') {
      assert.equal(workflow.status, 'cancelled');
      workflow.status = 'ready'; workflow.code = null; workflow.resume_kind = 'authoring';
      return structuredClone(workflow);
    }
    if (method === 'workflow.readMaterial') {
      if (globalError instanceof EngineError && params.area === 'source') throw globalError;
      const full = params.area === 'source' ? source[params.name] : texts.get(params.name);
      assert.equal(typeof full, 'string');
      const points = [...full], text = points.slice(params.offset, params.offset + params.limit).join('');
      return { research_id: workflow.id, area: params.area, name: params.name, offset: params.offset, limit: params.limit,
        text, sha256: digest(full), total_chars: points.length, is_untrusted_data: true,
        next_offset: params.offset + [...text].length < points.length ? params.offset + [...text].length : null };
    }
    if (method === 'workflow.recordInference') {
      const receipt = params.receipt, id = `model-evidence-${receipt.id}-${receipt.outcome}`;
      if (rejectStartOnce && receipt.phase === 'source-analysis' && receipt.outcome === 'started') {
        rejectStartOnce = false;
        throw new EngineError('INVALID_ARGUMENT', 'Synthetic native preflight parser rejection; no provider dispatch.');
      }
      const artifact = retain(id, receipt);
      const outcome = ['completed', 'failed', 'interrupted'].find(value => workflow.artifacts[`model-evidence-${receipt.id}-${value}`]) ?? 'started';
      const venueId = /for ([\w-]+) attempt/.exec(receipt.prompt)?.[1];
      const venue = portfolio.venues.find(item => item.venue_id === venueId);
      if (receipt.phase === 'source-analysis') portfolio.analysis_outcome = outcome;
      else if (receipt.phase === 'venue-manuscript') venue.writer_outcome = outcome;
      else if (receipt.phase === 'venue-manuscript-review') venue.reviewer_outcome = outcome;
      else if (receipt.phase === 'venue-manuscript-repair') venue.repair_outcome = outcome;
      if (receipt.phase === 'venue-manuscript' && receipt.outcome === 'failed' && receipt.code === 'stream_interrupted' && !venue.draft) {
        venue.repair_binding = { ...venue.writer_binding, phase: 'venue-manuscript-repair', attempt: 1, repair: {
          original_inference_artifact_id: id, original_inference_sha256: artifact.sha256,
          original_prompt_sha256: receipt.promptSha256, partial_text_sha256: receipt.textSha256, original_attempt: 1 } };
      }
      if (receipt.outcome === 'started' && !reservations.has(receipt.id)) {
        reservations.add(receipt.id);
        if (receipt.phase === 'source-analysis') workflow.repository_paper.analysis_attempts++;
        else if (receipt.phase === 'venue-manuscript') { venue.draft_attempts++; venue.status = 'writing_interrupted'; }
        else if (receipt.phase === 'venue-manuscript-review') { venue.review_attempts++; venue.status = 'review_interrupted'; }
        else if (receipt.phase === 'venue-manuscript-repair') venue.repair_attempts++;
        else if (receipt.phase !== 'literature-plan') assert.fail(`Unexpected phase ${receipt.phase}`);
      }
      return { artifactId: id, sha256: artifact.sha256 };
    }
    if (method === 'workflow.submitPortfolioAnalysis') {
      assert.deepEqual(Object.keys(params.value).sort(), ['analysis', 'inference_artifact_id']);
      assert.ok(workflow.artifacts[params.value.inference_artifact_id]);
      const revised = portfolio.analysis_revision?.status === 'planned';
      portfolio.analysis = params.value.analysis;
      portfolio.analysis_sha256 = retain(revised ? 'repository-portfolio-analysis-revision-3' : 'repository-portfolio-analysis', params.value.analysis).sha256;
      portfolio.analysis_binding = null; portfolio.analysis_outcome = null;
      if (revised) {
        portfolio.analysis_revision.status = 'incomplete';
        portfolio.analysis_revision_available = false;
        for (const venue of portfolio.venues) { venue.analysis_current = false; venue.scientific_ready = venue.content_ready = false; }
      } else for (const venue of portfolio.venues) { venue.writer_binding = frame('venue-manuscript', venue); venue.status = 'pending_draft'; }
    } else if (method === 'workflow.preparePortfolioRevision') {
      assert.equal(portfolio.analysis_revision, null);
      const artifact = retain('repository-portfolio-analysis-revision-plan', { prior_analysis_sha256: portfolio.analysis_sha256,
        ...(revisionBodyChars ? { completeSyntheticReviewBody: 'x'.repeat(revisionBodyChars) } : {}),
        reviews: portfolio.venues.map(venue => ({ venue_id: venue.venue_id, review: venue.review })) });
      portfolio.analysis_revision = { artifact_id: artifact.id, sha256: artifact.sha256,
        prior_analysis_sha256: portfolio.analysis_sha256, affected_venues: targets.map(target => target.venue_id),
        actions: [{ action: 'revise_source_analysis', target: 'Synthetic common decision rule',
          required_change: 'Resolve a synthetic analytical contradiction.', verification: 'Reapply the original source witnesses.' }], status: 'planned' };
      portfolio.analysis_revision_available = false;
      portfolio.analysis_binding = { ...frame('source-analysis'), attempt: 3, analysis_revision_sha256: artifact.sha256 };
    } else if (method === 'workflow.collectPortfolioLiterature') {
      assert.equal(portfolio.literature_followup_available, true);
      assert.equal(workflow.study_literature_attempt, 2);
      assert.deepEqual(params.pdfCandidates, []);
      assert.equal(params.htmlCandidates.length, 1);
      workflow.study_literature_attempt++;
      portfolio.literature_budget.used++;
      portfolio.literature_followup_available = false;
      const artifact = retain('synthetic-new-literature-3', { sources: [], html_candidates: params.htmlCandidates });
      portfolio.literature_sha256 = artifact.sha256;
      portfolio.literature_collections.push({ artifact_id: artifact.id, sha256: artifact.sha256,
        attempt: 3, queries: params.queries, status: 'completed' });
    } else if (method === 'workflow.submitPortfolioManuscript') {
      assert.deepEqual(Object.keys(params.value).sort(), ['inference_artifact_id', 'manuscript', 'venue_id']);
      assert.ok(workflow.artifacts[params.value.inference_artifact_id]);
      if (params.value.venue_id === interruptedAdmission && !admissionInterrupted) {
        admissionInterrupted = true;
        throw new EngineError('INVALID_ARGUMENT', 'Synthetic transient post-completion admission failure.');
      }
      const venue = portfolio.venues.find(item => item.venue_id === params.value.venue_id);
      venue.draft = params.value.manuscript; venue.admitted_drafts++;
      venue.review = null; venue.analysis_current = true; venue.revise_available = false;
      venue.scientific_ready = venue.content_ready = false;
      venue.artifact_ids.review = venue.artifact_ids.pdf = venue.artifact_ids.docx = null;
      venue.export_status = 'not_started';
      const prefix = `repository-portfolio-${venue.venue_id}`;
      venue.artifact_ids.draft = `${prefix}-draft-${venue.admitted_drafts}`; venue.artifact_ids.markdown = `${prefix}-markdown-${venue.admitted_drafts}`;
      venue.draft_sha256 = retain(venue.artifact_ids.draft, venue.draft).sha256;
      retain(venue.artifact_ids.markdown, `# ${venue.draft.title}\nComplete synthetic candidate prose.`);
      venue.reviewer_binding = { ...frame('venue-manuscript-review', venue), attempt: venue.review_attempts + 1, draft_sha256: venue.draft_sha256,
        markdown_sha256: workflow.artifacts[venue.artifact_ids.markdown].sha256 };
      venue.status = 'pending_review';
      venue.writer_outcome = null;
      venue.repair_binding = null;
      venue.repair_outcome = null;
    } else if (method === 'workflow.submitPortfolioReview') {
      assert.deepEqual(Object.keys(params.value).sort(), ['inference_artifact_id', 'review', 'venue_id']);
      const venue = portfolio.venues.find(item => item.venue_id === params.value.venue_id);
      assert.equal(venue.review, null); assert.ok(workflow.artifacts[params.value.inference_artifact_id]);
      venue.review = params.value.review; venue.artifact_ids.review = `repository-portfolio-${venue.venue_id}-review-${venue.admitted_drafts}`;
      retain(venue.artifact_ids.review, venue.review);
      venue.scientific_ready = Object.values(venue.review.criteria).every(item => item.passed);
      venue.content_ready = venue.scientific_ready;
      venue.status = venue.content_ready ? 'content_ready' : 'needs_revision'; venue.writer_binding = venue.reviewer_binding = null;
      venue.writer_outcome = venue.reviewer_outcome = null;
      portfolio.completed = portfolio.venues.filter(venue => venue.review).length;
      portfolio.all_content_ready = portfolio.venues.every(venue => venue.content_ready);
    } else if (method === 'workflow.exportPortfolioDraft') {
      assert.deepEqual(Object.keys(params).sort(), ['researchId', 'venueId']);
      const venue = portfolio.venues.find(item => item.venue_id === params.venueId);
      assert.ok(venue.draft, 'First feature files are generated before independent review');
      if (venue.venue_id === failedExport) {
        const id = `repository-portfolio-${venue.venue_id}-export-1`, artifact = retain(id, { outputs: {},
          errors: [{ format: 'pdf', message: 'Synthetic proved Lua helper path failure.' }] });
        venue.export = { artifact_id: id, sha256: artifact.sha256,
          errors: [{ format: 'pdf', message: 'Synthetic proved Lua helper path failure.' }] };
        venue.export_status = 'failed'; venue.export_repair_available = true;
        return structuredClone(workflow);
      }
      for (const format of ['pdf', 'docx']) {
        venue.artifact_ids[format] = `repository-portfolio-${venue.venue_id}-${format}-${venue.admitted_drafts}`;
        retain(venue.artifact_ids[format], `Synthetic ${format} bytes for ${venue.venue_id}`);
      }
      venue.export_status = 'completed';
    } else if (method === 'workflow.repairPortfolioExport') {
      const venue = portfolio.venues.find(item => item.venue_id === params.venueId);
      assert.equal(venue.export_repair_attempts, 0);
      assert.equal(venue.export_repair_available, true);
      venue.export_repair_available = false; venue.export_repair_attempts = 1; venue.export_repair_total += 1;
      const id = `repository-portfolio-${venue.venue_id}-export-repair-1`,
        errors = failedExportRepair ? [{ format: 'pdf', message: 'Synthetic retained repair failure.' }] : [];
      const artifact = retain(id, { errors, original_export_sha256: venue.export.sha256 });
      venue.export = { artifact_id: id, sha256: artifact.sha256, errors };
      venue.export_status = failedExportRepair ? 'failed' : 'completed';
      if (!failedExportRepair) for (const format of ['pdf', 'docx']) {
        venue.artifact_ids[format] = `repository-portfolio-${venue.venue_id}-${format}-repair-1`;
        retain(venue.artifact_ids[format], `Synthetic repaired ${format} bytes.`);
      }
    } else assert.fail(`Unexpected native method ${method}`);
    return structuredClone(workflow);
  } };
  const client = { async getSession() { return { status: 'connected', sharing: true, profileId: 'synthetic-profile' }; },
    async listModels() { return [{ slug: 'synthetic-writer' }, { slug: 'synthetic-reviewer' }]; },
    async streamResponse(request) {
      modelCalls.push(request);
      if (globalError instanceof ChatGPTError) throw globalError;
      const prompt = request.input[0].content;
      assert.ok(prompt.includes(JSON.stringify(source['src/retained-analysis.ts'])), 'The original analysis witness must reach every full scientific context');
      if (prompt.startsWith('Select closest primary scholarly bodies')) return { text: JSON.stringify({
        queries: ['Synthetic exact primary HTML paper'], pdf_candidates: [], html_candidates: [{
          landing_url: 'https://example.test/official-paper', html_url: 'https://example.test/full-paper.html',
          title: 'Synthetic exact primary HTML paper', authors: ['Synthetic Author'], year: 2026,
          publication_type: 'proceedings-article', publication_version: 'published' }], reason: 'Synthetic retrieval planning only.' }) };
      const venueId = /for ([\w-]+) attempt/.exec(prompt)?.[1];
      if (prompt.startsWith('Perform the common')) {
        if (portfolio.analysis_revision) {
          assert.ok(prompt.includes('"portfolioRevision"'));
          assert.ok(prompt.includes(JSON.stringify(analysis.method)));
          const materials = JSON.parse(prompt.split('\n').at(-1));
          assert.equal(materials.portfolioRevision.text, texts.get(portfolio.analysis_revision.artifact_id));
          assert.equal(digest(materials.portfolioRevision.text), portfolio.analysis_revision.sha256);
          assert.equal(prompt.split(JSON.stringify(materials.portfolioRevision.text)).length - 1, 1);
          assert.ok(!prompt.includes(JSON.stringify('Preserved original draft 2')));
          return { text: JSON.stringify({ ...analysis, method: 'Synthetic corrected common decision rule, not new research data.' }) };
        }
        return { text: JSON.stringify(analysis) };
      }
      if (prompt.startsWith('Complete only the interrupted portfolio manuscript tail')) {
        assert.equal(request.model, 'synthetic-writer');
        assert.ok(prompt.includes('Protected original text and completed evidence prefixes'));
        if (failedRepair) throw new ChatGPTError('stream_interrupted', 'Synthetic tail completion interruption', false);
        return { text: JSON.stringify({ acknowledgments: alteredRepair ? 'Changed protected disclosure. '.repeat(6) : 'Synthetic model assistance, no human approval or real study. '.repeat(3),
          source_evidence: [sourceEvidence[0]], literature_evidence: [], document_evidence: [], revision: null }) };
      }
      if (prompt.startsWith('Independently assess')) {
        assert.equal(request.model, 'synthetic-reviewer');
        assert.ok(prompt.includes(`Complete synthetic candidate prose.`));
        assert.ok(prompt.includes('all seven criteria'));
        const actual = portfolio.venues.find(venue => venue.venue_id === venueId).draft;
        const venue = portfolio.venues.find(venue => venue.venue_id === venueId);
        const delivered = JSON.parse(prompt.split('\n').at(-1)).portfolioDraft;
        assert.equal(delivered.artifact_id, venue.artifact_ids.markdown);
        assert.equal(delivered.text, texts.get(venue.artifact_ids.markdown));
        assert.equal(delivered.sha256, workflow.artifacts[venue.artifact_ids.markdown].sha256);
        assert.equal(delivered.sha256, digest(delivered.text));
        assert.equal(Object.hasOwn(delivered, 'value'), false);
        const assessed = review();
        if (venueId === negativeVenueReview && portfolio.venues.find(venue => venue.venue_id === venueId).admitted_drafts === 1) {
          assessed.criteria.method.passed = false;
          assessed.next_actions = [{ action: 'revise_source_analysis', target: 'Synthetic mediator rule',
            required_change: 'Use the genuinely changed common model.', verification: 'Check every method example.' }];
        }
        return { text: JSON.stringify(assessed) };
      }
      assert.equal(request.model, 'synthetic-writer');
      if (venueId === partialWriter) {
        const value = { title: 'Protected synthetic title', sections: ['Abstract', 'Introduction', 'Related Work', 'Method',
          'Repository Analysis', 'Discussion', 'Limitations', 'Conclusion'].map(heading => ({ heading,
            text: 'Complete protected scientific section with only a synthetic source witness. {{source:witness-0}}' })),
          source_evidence: [sourceEvidence[0]], literature_evidence: [], document_evidence: [], revision: null };
        value.sections.push({ heading: 'Actionable Insights', text: '- Inspect the boundary in the actual source.\n- Compare each supported alternative carefully.\n- Retain the limits of the bounded analysis.' });
        value.sections.push({ heading: 'Acknowledgments', text: 'Synthetic model assistance, no human approval or real study. '.repeat(3) });
        request.onDelta(JSON.stringify(value).split('"source_evidence"')[0] + '"source_evidence":[{"id":');
        throw new ChatGPTError('stream_interrupted', 'Synthetic interruption after all protected sections', false);
      }
      return { text: venueId === failedWriter ? '' : JSON.stringify(manuscript(`Synthetic manuscript specific to ${venueId}`)) };
    } };
  const controller = new ResearchController(client, engine, directory, () => {});
  const job = { id: workflow.id, goal: workflow.goal, model: 'synthetic-writer', reviewerModel: 'synthetic-reviewer',
    pipeline: 'running', phase: 'idle', cleanupRequired: false, updatedAt: new Date().toISOString() };
  controller.jobs.set(job.id, job);
  const run = () => controller.runRepositoryPortfolio(job, structuredClone(workflow), new AbortController().signal);
  const assertPreserved = () => {
    for (const field of ['proposal_attempt', 'study_literature_attempt', 'draft_attempt', 'execution_attempt', 'code_attempt'])
      assert.equal(workflow[field], original[field], `${field} must preserve the common study`);
    for (const field of ['plan', 'analysis', 'draft', 'review']) assert.deepEqual(workflow.repository_paper[field], original.repository_paper[field]);
    for (const [id, artifact] of Object.entries(original.artifacts)) assert.deepEqual(workflow.artifacts[id], artifact);
  };
  return { controller, client, engine, directory, workflow, portfolio, job, requests, modelCalls, run, assertPreserved, retain, frame, texts };
}

async function formatOnlyFixture(t, alterResult = () => {}, venueId = catalog.venues[0].id) {
  const f = await fixture(t);
  const streamResponse = f.client.streamResponse;
  f.client.streamResponse = async request => {
    const result = await streamResponse(request), prompt = request.input[0].content;
    if (prompt.startsWith('Independently assess') && /for ([\w-]+) attempt/.exec(prompt)?.[1] === venueId) {
      const assessed = JSON.parse(result.text);
      assessed.criteria.presentation = { passed: false, reason: 'Synthetic duplicate bibliography only.' };
      assessed.next_actions = [{ action: 'revise_manuscript', target: 'References',
        required_change: 'Keep one canonical bibliography.', verification: 'Inspect the derived output without changing science.' }];
      return { ...result, text: JSON.stringify(assessed) };
    }
    return result;
  };
  await f.run();
  const venue = f.portfolio.venues.find(item => item.venue_id === venueId);
  assert.equal(venue.review.criteria.presentation.passed, false);
  assert.ok(Object.entries(venue.review.criteria).every(([name, criterion]) => name === 'presentation' || criterion.passed));
  assert.equal(venue.scientific_ready, false);
  venue.format_export_available = true;
  f.workflow.status = 'cancelled'; f.workflow.code = 'CANCELLED'; f.workflow.resume_kind = 'authoring';
  f.controller.restoring = false;
  f.controller.state.runtime = { state: 'ready', repositoryAnalysisReady: true, message: 'Synthetic ready engine.' };
  for (const method of ['getSession', 'listModels', 'streamResponse']) f.client[method] = async () => assert.fail(`Format-only export must not call SDK ${method}`);
  const request = f.engine.request.bind(f.engine);
  f.engine.request = async (method, params) => {
    if (method !== 'workflow.reformatPortfolioDraft') return request(method, params);
    f.requests.push({ method, params: structuredClone(params) });
    assert.deepEqual(params, { researchId: f.workflow.id, venueId });
    const prefix = `repository-portfolio-${venueId}`, original = {
      original_draft_sha256: venue.draft_sha256,
      original_markdown_sha256: f.workflow.artifacts[venue.artifact_ids.markdown].sha256,
      original_review_sha256: f.workflow.artifacts[venue.artifact_ids.review].sha256,
    };
    const input = f.retain(`${prefix}-export-markdown-format-1`, '# Synthetic unchanged science\nOne canonical bibliography.');
    const receipt = f.retain(`${prefix}-export-format-1`, { ...original, input_artifact_id: input.id,
      input_sha256: input.sha256, model_calls: 0, errors: [] });
    for (const format of ['pdf', 'docx']) {
      const output = f.retain(`${prefix}-${format}-format-1`, `Synthetic format-only ${format} bytes.`);
      venue.artifact_ids[format] = output.id;
    }
    venue.format_export_available = false; venue.format_export_attempts = 1;
    venue.format_export = { artifact_id: receipt.id, sha256: receipt.sha256, ...original,
      input_artifact_id: input.id, input_sha256: input.sha256, status: 'completed', errors: [] };
    const updated = structuredClone(f.workflow);
    alterResult(updated, updated.repository_paper.portfolio.venues.find(item => item.venue_id === venueId));
    return updated;
  };
  return { ...f, venue, before: structuredClone(f.workflow), calls: f.modelCalls.length };
}

test('public bibliography-only export works while cancelled without SDK dispatch, resuming or changing scientific approval', async t => {
  const f = await formatOnlyFixture(t), before = f.before.repository_paper.portfolio.venues[0];
  const snapshot = await f.controller.reformatRepositoryPortfolioDraft(f.job.id, f.venue.venue_id);
  assert.equal(f.modelCalls.length, f.calls);
  assert.equal(f.requests.filter(item => item.method === 'workflow.resume').length, 0);
  assert.equal(f.requests.filter(item => item.method === 'workflow.reformatPortfolioDraft').length, 1);
  assert.equal(f.workflow.status, 'cancelled'); assert.equal(f.workflow.code, 'CANCELLED');
  for (const field of ['draft', 'review', 'draft_sha256', 'draft_attempts', 'review_attempts', 'admitted_drafts',
    'repair_attempts', 'export_repair_attempts', 'export_repair_total', 'scientific_ready', 'content_ready', 'submission_ready'])
    assert.deepEqual(f.venue[field], before[field], `${field} must not be changed by bibliography export`);
  assert.equal(f.venue.format_export_attempts, 1); assert.equal(f.venue.format_export_available, false);
  assert.equal(f.venue.scientific_ready, false); assert.equal(f.venue.review.criteria.presentation.passed, false);
  for (const key of ['draft', 'markdown', 'review']) assert.equal(f.venue.artifact_ids[key], before.artifact_ids[key]);
  for (const [id, artifact] of Object.entries(f.before.artifacts)) assert.deepEqual(f.workflow.artifacts[id], artifact);
  for (const id of [f.venue.format_export.artifact_id, f.venue.format_export.input_artifact_id, f.venue.artifact_ids.pdf, f.venue.artifact_ids.docx])
    assert.equal(f.workflow.artifacts[id].sha256, digest(f.texts.get(id)), `${id} must be registered actual synthetic bytes`);
  assert.equal(snapshot.jobs.find(item => item.id === f.job.id).repositoryPaper.portfolio.venues[0].format_export.status, 'completed');
  assert.equal(snapshot.error, null);
  f.assertPreserved();
  await assert.rejects(f.controller.reformatRepositoryPortfolioDraft(f.job.id, f.venue.venue_id), error => error.code === 'PORTFOLIO_FORMAT_UNAVAILABLE');
  assert.equal(f.requests.filter(item => item.method === 'workflow.reformatPortfolioDraft').length, 1);
  assert.equal(f.modelCalls.length, f.calls);
});

test('public format-only export rejects altered original bindings, science, counters and retained evidence', async t => {
  const mutations = {
    draft_proof: (_workflow, venue) => { venue.format_export.original_draft_sha256 = digest('wrong original draft'); },
    markdown_proof: (_workflow, venue) => { venue.format_export.original_markdown_sha256 = digest('wrong original Markdown'); },
    review_proof: (_workflow, venue) => { venue.format_export.original_review_sha256 = digest('wrong original review'); },
    scientific_approval: (_workflow, venue) => { venue.scientific_ready = true; },
    review_pass: (_workflow, venue) => { venue.review.criteria.presentation.passed = true; },
    manuscript_prose: (_workflow, venue) => { venue.draft.sections[0].text += ' Changed original science.'; },
    common_counter: workflow => { workflow.study_literature_attempt++; },
    writer_counter: (_workflow, venue) => { venue.draft_attempts++; },
    review_counter: (_workflow, venue) => { venue.review_attempts++; },
    frozen_artifact: workflow => { workflow.artifacts['repository-draft-2'].sha256 = digest('replaced old artifact'); },
  };
  for (const [name, mutate] of Object.entries(mutations)) await t.test(name, async t => {
    const f = await formatOnlyFixture(t, mutate);
    await assert.rejects(f.controller.reformatRepositoryPortfolioDraft(f.job.id, f.venue.venue_id),
      error => error.code === 'RESEARCH_STATE_INVALID', name);
    assert.equal(f.modelCalls.length, f.calls);
    assert.equal(f.venue.scientific_ready, false);
    assert.equal(f.venue.review.criteria.presentation.passed, false);
    for (const [id, artifact] of Object.entries(f.before.artifacts)) assert.deepEqual(f.workflow.artifacts[id], artifact);
    assert.equal(f.requests.filter(item => item.method === 'workflow.reformatPortfolioDraft').length, 1);
    f.assertPreserved();
  });
});

test('public format-only export requires native availability and an unused one-export allowance', async t => {
  for (const guard of ['unavailable', 'already_used']) await t.test(guard, async t => {
    const f = await formatOnlyFixture(t);
    if (guard === 'unavailable') f.venue.format_export_available = false;
    else f.venue.format_export_attempts = 1;
    const before = structuredClone(f.workflow);
    await assert.rejects(f.controller.reformatRepositoryPortfolioDraft(f.job.id, f.venue.venue_id),
      error => error.code === 'PORTFOLIO_FORMAT_UNAVAILABLE');
    assert.equal(f.modelCalls.length, f.calls);
    assert.equal(f.requests.filter(item => item.method === 'workflow.reformatPortfolioDraft').length, 0);
    assert.deepEqual(f.workflow, before);
    f.assertPreserved();
  });
});

async function layoutOnlyFixture(t, { formatted = false, failed = false, alterResult = () => {} } = {}) {
  const venueId = formatted ? 'ieee-software' : 'ieee-security-privacy';
  const f = await formatOnlyFixture(t, () => {}, venueId), venue = f.venue;
  const prefix = `repository-portfolio-${venueId}`, originalMarkdown = f.texts.get(venue.artifact_ids.markdown);
  const authorInput = f.retain(`${prefix}-export-markdown-1`, 'Synthetic retained author block.\n\n' + originalMarkdown);
  const originalReceipt = f.retain(`${prefix}-export-1`, { draft_sha256: venue.draft_sha256,
    markdown_sha256: f.workflow.artifacts[venue.artifact_ids.markdown].sha256,
    input_artifact_id: authorInput.id, input_sha256: authorInput.sha256,
    outputs: Object.fromEntries(['pdf', 'docx'].map(kind => [kind, { artifact_id: venue.artifact_ids[kind],
      sha256: f.workflow.artifacts[venue.artifact_ids[kind]].sha256 }])), errors: [], model_calls: 0 });
  venue.export = { artifact_id: originalReceipt.id, sha256: originalReceipt.sha256, errors: [] };
  if (formatted) await f.controller.reformatRepositoryPortfolioDraft(f.job.id, venueId);
  else venue.format_export_available = false;
  venue.layout_export_available = true;
  const before = structuredClone(f.workflow), calls = f.modelCalls.length;
  const selected = structuredClone(formatted ? venue.format_export : venue.export);
  const selectedInput = formatted ? { id: selected.input_artifact_id, sha256: selected.input_sha256 } : authorInput;
  const request = f.engine.request.bind(f.engine);
  f.engine.request = async (method, params) => {
    if (method !== 'workflow.correctPortfolioLayout') return request(method, params);
    f.requests.push({ method, params: structuredClone(params) });
    assert.deepEqual(params, { researchId: f.workflow.id, venueId });
    const input = f.retain(`${prefix}-export-markdown-layout-1`,
      f.texts.get(selectedInput.id) + '\nSynthetic code-formatted reference and numbered Word caption.');
    const proof = { original_markdown_sha256: selectedInput.sha256, formatted_markdown_sha256: input.sha256,
      scientific_body_sha256_before: digest(originalMarkdown), scientific_body_sha256_after: digest(originalMarkdown) };
    const descriptor = { original_draft_sha256: venue.draft_sha256,
      original_markdown_sha256: before.artifacts[venue.artifact_ids.markdown].sha256,
      original_review_sha256: before.artifacts[venue.artifact_ids.review].sha256,
      original_artifact_id: selected.artifact_id, original_sha256: selected.sha256,
      original_input_artifact_id: selectedInput.id, original_input_sha256: selectedInput.sha256,
      input_artifact_id: input.id, input_sha256: input.sha256,
      scope: 'canonical-source-labels-and-docx-captions', model_calls: 0, scientific_approval_changed: false,
      layout_proof: proof, status: failed ? 'failed' : 'completed',
      errors: failed ? [{ format: 'docx', message: 'Synthetic retained layout conversion failure.' }] : [] };
    const receipt = f.retain(`${prefix}-export-layout-1`, descriptor);
    if (!failed) for (const kind of ['pdf', 'docx']) {
      const output = f.retain(`${prefix}-${kind}-layout-1`, `Synthetic local layout-only ${kind} bytes.`);
      venue.artifact_ids[kind] = output.id;
    }
    venue.layout_export_available = false; venue.layout_export_attempts = 1;
    venue.layout_export = { ...descriptor, artifact_id: receipt.id, sha256: receipt.sha256 };
    const updated = structuredClone(f.workflow);
    alterResult(updated, updated.repository_paper.portfolio.venues.find(item => item.venue_id === venueId));
    return updated;
  };
  const assertUnchanged = () => {
    assert.equal(f.modelCalls.length, calls);
    assert.equal(f.requests.filter(item => item.method === 'workflow.resume').length, 0);
    assert.equal(f.workflow.status, 'cancelled'); assert.equal(f.workflow.code, 'CANCELLED');
    for (const key of ['draft', 'review', 'draft_sha256', 'draft_attempts', 'review_attempts', 'admitted_drafts',
      'repair_attempts', 'export_repair_attempts', 'export_repair_total', 'export', 'export_status', 'status', 'writer_binding', 'reviewer_binding',
      'writer_outcome', 'reviewer_outcome', 'scientific_ready', 'content_ready', 'submission_ready', 'analysis_current',
      'format_export', 'format_export_attempts'])
      assert.deepEqual(venue[key], before.repository_paper.portfolio.venues.find(item => item.venue_id === venueId)[key], key);
    for (const key of ['draft', 'markdown', 'review'])
      assert.equal(venue.artifact_ids[key], before.repository_paper.portfolio.venues.find(item => item.venue_id === venueId).artifact_ids[key]);
    for (const item of before.repository_paper.portfolio.venues.filter(item => item.venue_id !== venueId))
      assert.deepEqual(f.portfolio.venues.find(current => current.venue_id === item.venue_id), item);
    for (const [id, artifact] of Object.entries(before.artifacts)) assert.deepEqual(f.workflow.artifacts[id], artifact);
    f.assertPreserved();
  };
  return { ...f, before, calls, selected, selectedInput, assertUnchanged };
}

test('public layout-only correction preserves IEEE format1 or S&P author-input while cancelled with zero SDK/resume', async t => {
  for (const formatted of [true, false]) await t.test(formatted ? 'IEEE format1 to layout1' : 'S&P base export to layout1', async t => {
    const f = await layoutOnlyFixture(t, { formatted });
    const snapshot = await f.controller.correctRepositoryPortfolioLayout(f.job.id, f.venue.venue_id);
    f.assertUnchanged();
    assert.equal(f.venue.layout_export_attempts, 1); assert.equal(f.venue.layout_export_available, false);
    assert.equal(f.venue.layout_export.original_artifact_id, f.selected.artifact_id);
    assert.equal(f.venue.layout_export.original_sha256, f.selected.sha256);
    assert.equal(f.venue.layout_export.original_input_sha256, f.selectedInput.sha256);
    assert.equal(f.venue.format_export_attempts, formatted ? 1 : 0);
    if (!formatted) assert.notEqual(f.venue.layout_export.original_input_sha256, f.venue.layout_export.original_markdown_sha256,
      'The retained author-enriched input must be distinct from the reviewed raw Markdown');
    for (const id of [f.venue.layout_export.artifact_id, f.venue.layout_export.input_artifact_id,
      f.venue.artifact_ids.pdf, f.venue.artifact_ids.docx])
      assert.equal(f.workflow.artifacts[id].sha256, digest(f.texts.get(id)));
    assert.equal(snapshot.jobs.find(item => item.id === f.job.id).repositoryPaper.portfolio.venues
      .find(item => item.venue_id === f.venue.venue_id).layout_export.status, 'completed');
    assert.equal(snapshot.error, null);
    await assert.rejects(f.controller.correctRepositoryPortfolioLayout(f.job.id, f.venue.venue_id),
      error => error.code === 'PORTFOLIO_LAYOUT_UNAVAILABLE');
    assert.equal(f.requests.filter(item => item.method === 'workflow.correctPortfolioLayout').length, 1);
  });
});

test('public failed layout correction spends its allowance and retains both previous output pointers', async t => {
  const f = await layoutOnlyFixture(t, { formatted: true, failed: true });
  const before = f.before.repository_paper.portfolio.venues.find(item => item.venue_id === f.venue.venue_id);
  await f.controller.correctRepositoryPortfolioLayout(f.job.id, f.venue.venue_id);
  f.assertUnchanged();
  assert.equal(f.venue.layout_export.status, 'failed'); assert.equal(f.venue.layout_export_attempts, 1);
  for (const kind of ['pdf', 'docx']) assert.equal(f.venue.artifact_ids[kind], before.artifact_ids[kind]);
  assert.match(f.venue.layout_export.errors[0].message, /retained layout conversion failure/);
  await assert.rejects(f.controller.correctRepositoryPortfolioLayout(f.job.id, f.venue.venue_id),
    error => error.code === 'PORTFOLIO_LAYOUT_UNAVAILABLE');
  assert.equal(f.requests.filter(item => item.method === 'workflow.correctPortfolioLayout').length, 1);
});

test('public layout correction requires native availability and its own unused allowance', async t => {
  for (const guard of ['unavailable', 'already_used']) await t.test(guard, async t => {
    const f = await layoutOnlyFixture(t, { formatted: true });
    if (guard === 'unavailable') f.venue.layout_export_available = false;
    else f.venue.layout_export_attempts = 1;
    const before = structuredClone(f.workflow);
    await assert.rejects(f.controller.correctRepositoryPortfolioLayout(f.job.id, f.venue.venue_id),
      error => error.code === 'PORTFOLIO_LAYOUT_UNAVAILABLE');
    assert.deepEqual(f.workflow, before); f.assertUnchanged();
    assert.equal(f.requests.filter(item => item.method === 'workflow.correctPortfolioLayout').length, 0);
  });
});

test('public layout correction rejects altered selected receipts, author inputs, body proof and frozen state', async t => {
  const mutations = {
    selected_receipt: (_workflow, venue) => { venue.layout_export.original_sha256 = digest('wrong selected format receipt'); },
    author_input: (_workflow, venue) => { venue.layout_export.original_input_sha256 = digest('changed author input'); },
    scientific_body: (_workflow, venue) => { venue.layout_export.layout_proof.scientific_body_sha256_after = digest('changed science'); },
    original_format_receipt: (_workflow, venue) => { venue.format_export.sha256 = digest('replaced prior format1'); },
    scientific_approval: (_workflow, venue) => { venue.scientific_ready = true; },
    common_counter: workflow => { workflow.study_literature_attempt++; },
    retained_export_repair_total: (_workflow, venue) => { venue.export_repair_total--; },
    other_venue: workflow => { workflow.repository_paper.portfolio.venues[1].review_attempts++; },
    unregistered_output: (_workflow, venue) => { venue.artifact_ids.pdf = 'unregistered-layout-output'; },
    failed_output_pointer: (_workflow, venue) => { venue.artifact_ids.pdf = venue.artifact_ids.docx; },
  };
  for (const [name, mutate] of Object.entries(mutations)) await t.test(name, async t => {
    const f = await layoutOnlyFixture(t, { formatted: true, failed: name === 'failed_output_pointer', alterResult: mutate });
    await assert.rejects(f.controller.correctRepositoryPortfolioLayout(f.job.id, f.venue.venue_id),
      error => error.code === 'RESEARCH_STATE_INVALID', name);
    f.assertUnchanged();
    assert.equal(f.requests.filter(item => item.method === 'workflow.correctPortfolioLayout').length, 1);
  });
});

test('a local negative review and changed native-authorized analysis permit a complete venue revision despite another journal hold', async t => {
  const venueId = catalog.venues[0].id;
  const f = await fixture(t, { negativeVenueReview: venueId });
  await f.run();
  const venue = f.portfolio.venues[0], original = structuredClone(f.workflow.artifacts);
  const priorDraft = venue.draft_sha256, reviewId = venue.artifact_ids.review;
  f.portfolio.analysis = { ...analysis, method: 'Actually changed synthetic decision model.' };
  f.portfolio.analysis_sha256 = f.retain('synthetic-analysis-3', f.portfolio.analysis).sha256;
  f.workflow.repository_paper.analysis_attempts = 3;
  f.portfolio.analysis_revision = { artifact_id: 'synthetic-plan', sha256: digest('synthetic plan'),
    prior_analysis_sha256: digest('old model'), affected_venues: [venueId], status: 'incomplete',
    actions: [{ action: 'human_validation', target: 'Another journal only', required_change: 'Unavailable data.', verification: 'Real data required.' }] };
  venue.analysis_current = false; venue.revise_available = true;
  venue.writer_binding = { ...f.frame('venue-manuscript', venue), attempt: 2,
    prior_draft_sha256: priorDraft, prior_review_sha256: f.workflow.artifacts[reviewId].sha256 };
  await f.run();
  assert.equal(venue.admitted_drafts, 2); assert.equal(venue.review_attempts, 2);
  assert.equal(f.workflow.repository_paper.analysis_attempts, 3);
  assert.equal(f.modelCalls.length, 3 + 2 * catalog.venues.length);
  const prompt = f.modelCalls.at(-2).input[0].content, materials = JSON.parse(prompt.split('\n').at(-1));
  assert.equal(materials.portfolioPriorReview.text, f.texts.get(reviewId));
  assert.equal(materials.portfolioPriorReview.sha256, f.workflow.artifacts[reviewId].sha256);
  assert.equal(digest(materials.portfolioPriorReview.text), materials.portfolioPriorReview.sha256);
  assert.ok(materials.portfolioDraft.text.includes('Complete synthetic candidate prose.'));
  for (const [id, artifact] of Object.entries(original)) assert.deepEqual(f.workflow.artifacts[id], artifact);
  const calls = f.modelCalls.length; await f.run(); assert.equal(f.modelCalls.length, calls);
});

test('post-analysis primary HTML collection uses the last retained collection without another analysis or PDF reservation', async t => {
  const f = await fixture(t, { negativeVenueReview: catalog.venues[0].id }); await f.run();
  const artifacts = structuredClone(f.workflow.artifacts), analysisCalls = f.workflow.repository_paper.analysis_attempts;
  const history = { sources: [{ id: 'synthetic-prior-paper', title: 'Synthetic previously searched paper', scope: 'metadata_only' }],
    searches: [{ query: 'Synthetic previously searched paper', status: 'failed' }],
    warnings: ['Synthetic prior full-body route failed; metadata is not comparison evidence.'] };
  f.portfolio.literature = history;
  f.portfolio.literature_followup_available = true;
  f.portfolio.pdf_budget.additional_used = 2; f.portfolio.pdf_budget.total_used = 4;
  await f.run();
  assert.equal(f.workflow.study_literature_attempt, 3); assert.equal(f.modelCalls.length, 2 + 2 * catalog.venues.length);
  assert.equal(f.workflow.repository_paper.analysis_attempts, analysisCalls);
  assert.equal(f.portfolio.pdf_budget.total_used, 4);
  assert.equal(f.requests.filter(item => item.method === 'workflow.collectPortfolioLiterature').length, 1);
  const planning = f.modelCalls.find(request => request.input[0].content.startsWith('Select closest primary scholarly bodies'));
  assert.ok(planning.input[0].content.includes('"literature_history":' + JSON.stringify(history)),
    'The remaining collection must receive the actual prior searches, failures and reading scopes.');
  for (const [id, artifact] of Object.entries(artifacts)) assert.deepEqual(f.workflow.artifacts[id], artifact);
  await f.run(); assert.equal(f.modelCalls.length, 2 + 2 * catalog.venues.length);
});

for (const entrypoint of ['requestRepositoryPortfolio', 'resume']) test(`${entrypoint} resumes a cancelled retained portfolio without restarting common authoring`, async t => {
  const f = await fixture(t);
  f.workflow.status = 'cancelled'; f.workflow.code = 'CANCELLED'; f.workflow.resume_kind = 'authoring';
  f.job.researchMode = 'repository_analysis';
  f.controller.restoring = false;
  f.controller.state.runtime = { state: 'ready', repositoryAnalysisReady: true, message: 'Synthetic ready engine.' };
  await f.controller[entrypoint](f.job.id, f.job.model, f.job.reviewerModel);
  const task = f.controller.current?.task;
  assert.ok(task, 'The public entrypoint must install the active portfolio lifecycle');
  await task;
  assert.equal(f.controller.snapshot().error, null);
  assert.equal(f.requests.filter(item => item.method === 'workflow.resume').length, 1);
  assert.equal(f.portfolio.completed, catalog.venues.length);
  assert.equal(f.modelCalls.length, 1 + 2 * catalog.venues.length);
  assert.ok(f.modelCalls.every(request => /portfolio/.test(request.input[0].content.split('\n')[0])));
  f.assertPreserved();
});

for (const entrypoint of ['requestRepositoryPortfolio', 'resume']) test(`${entrypoint} rejects a resume that changes retained counters or scientific analysis before dispatch`, async t => {
  for (const changed of ['counter', 'analysis', 'artifact']) await t.test(changed, async t => {
    const f = await fixture(t);
    f.workflow.status = 'cancelled'; f.workflow.code = 'CANCELLED'; f.workflow.resume_kind = 'authoring';
    f.job.researchMode = 'repository_analysis';
    f.controller.restoring = false;
    f.controller.state.runtime = { state: 'ready', repositoryAnalysisReady: true, message: 'Synthetic ready engine.' };
    const request = f.engine.request.bind(f.engine);
    f.engine.request = async (method, params) => {
      const result = await request(method, params);
      if (method === 'workflow.resume') {
        if (changed === 'counter') result.proposal_attempt++;
        if (changed === 'analysis') result.repository_paper.analysis.method = 'Invalid replacement of retained analysis';
        if (changed === 'artifact') result.artifacts['repository-review-2'].sha256 = digest('Invalid replacement of retained review');
      }
      return result;
    };
    await assert.rejects(f.controller[entrypoint](f.job.id, f.job.model, f.job.reviewerModel), error => error.code === 'RESEARCH_STATE_INVALID');
    assert.equal(f.controller.current, undefined);
    assert.equal(f.modelCalls.length, 0);
    f.assertPreserved();
  });
});

test('one tail request preserves the failed venue writer and every complete section, then normal review and export resume', async t => {
  const f = await fixture(t, { partialWriter: catalog.venues[0].id });
  await f.run();
  const first = f.portfolio.venues[0];
  assert.equal(first.draft_attempts, 1); assert.equal(first.admitted_drafts, 0);
  assert.equal(first.repair_attempts, 0); assert.equal(f.modelCalls.length, 2 * catalog.venues.length);
  const key = first.repair_binding.repair.original_inference_artifact_id;
  const original = structuredClone(f.workflow.artifacts[key]);
  const failed = f.requests.find(request => request.method === 'workflow.recordInference' &&
    `model-evidence-${request.params.receipt.id}-${request.params.receipt.outcome}` === key).params.receipt;
  await f.run();
  assert.equal(first.draft_attempts, 1); assert.equal(first.repair_attempts, 1);
  assert.equal(first.review_attempts, 1); assert.equal(first.admitted_drafts, 1);
  assert.deepEqual(f.workflow.artifacts[key], original);
  assert.equal(first.draft.title, 'Protected synthetic title');
  assert.ok(failed.text.startsWith(JSON.stringify({ title: first.draft.title, sections: first.draft.sections }).slice(0, -1)));
  assert.equal(f.modelCalls.length, 2 + 2 * catalog.venues.length);
  const before = f.modelCalls.length;
  await f.run(); assert.equal(f.modelCalls.length, before);
  f.assertPreserved();
});

test('failed or altered venue tail completion retains the original failure and cannot call another repair', async t => {
  for (const option of ['failedRepair', 'alteredRepair']) await t.test(option, async t => {
    const f = await fixture(t, { partialWriter: catalog.venues[0].id, [option]: true });
    await f.run(); const first = f.portfolio.venues[0];
    const original = structuredClone(f.workflow.artifacts[first.repair_binding.repair.original_inference_artifact_id]);
    await f.run(); assert.equal(first.admitted_drafts, 0); assert.equal(first.draft_attempts, 1);
    assert.equal(first.repair_attempts, 1);
    const before = f.modelCalls.length;
    await f.run(); assert.equal(f.modelCalls.length, before);
    assert.deepEqual(f.workflow.artifacts[first.repair_binding.repair.original_inference_artifact_id], original);
    f.assertPreserved();
  });
});

test('a review-bound source-analysis repair appends one real result within the original three-attempt limit and holds stale manuscripts', async t => {
  const f = await fixture(t, { negativeVenueReview: catalog.venues[0].id });
  await f.run();
  const before = structuredClone(f.workflow.artifacts), prior = f.portfolio.analysis_sha256;
  f.portfolio.analysis_revision_required = f.portfolio.analysis_revision_available = true;
  f.portfolio.venues[1].scientific_ready = f.portfolio.venues[1].content_ready = false;
  f.portfolio.venues[1].status = 'needs_revision';
  await f.run();
  assert.equal(f.workflow.repository_paper.analysis_attempts, 3);
  assert.equal(f.modelCalls.length, 2 + 2 * catalog.venues.length);
  assert.equal(f.portfolio.analysis_revision.prior_analysis_sha256, prior);
  assert.equal(f.portfolio.analysis_revision.status, 'incomplete');
  assert.ok(f.portfolio.venues.every(venue => !venue.analysis_current && venue.admitted_drafts === 1 && venue.review_attempts === 1));
  for (const [id, artifact] of Object.entries(before)) assert.deepEqual(f.workflow.artifacts[id], artifact);
  assert.equal(f.requests.filter(request => request.method === 'workflow.preparePortfolioRevision').length, 1);
  await f.run();
  assert.equal(f.modelCalls.length, 2 + 2 * catalog.venues.length);
  assert.equal(f.requests.filter(request => request.method === 'workflow.preparePortfolioRevision').length, 1);
  f.assertPreserved();
});

test('two complete IEEE reviews use the final request limit without truncation or consuming a rejected analysis attempt', async t => {
  for (const revisionBodyChars of [610_000, 710_000]) await t.test(String(revisionBodyChars), async t => {
    const f = await fixture(t, { revisionBodyChars, negativeVenueReview: catalog.venues[0].id });
    await f.run();
    f.portfolio.analysis_revision_required = f.portfolio.analysis_revision_available = true;
    const before = f.modelCalls.length;
    if (revisionBodyChars < 700_000) {
      await f.run();
      assert.equal(f.modelCalls.length, before + 1);
      assert.equal(f.workflow.repository_paper.analysis_attempts, 3);
      const prompt = f.modelCalls.at(-1).input[0].content;
      assert.ok(prompt.length < 700_000);
      const materials = JSON.parse(prompt.split('\n').at(-1));
      assert.equal(JSON.parse(materials.portfolioRevision.text).completeSyntheticReviewBody.length, revisionBodyChars);
    } else {
      await assert.rejects(f.run(), error => error.code === 'REVIEW_CONTEXT_TOO_LARGE');
      const frozenPlan = structuredClone(f.workflow.artifacts[f.portfolio.analysis_revision.artifact_id]);
      await assert.rejects(f.run(), error => error.code === 'REVIEW_CONTEXT_TOO_LARGE');
      assert.equal(f.modelCalls.length, before);
      assert.equal(f.workflow.repository_paper.analysis_attempts, 2);
      assert.equal(f.portfolio.analysis_revision.status, 'planned');
      assert.deepEqual(f.workflow.artifacts[f.portfolio.analysis_revision.artifact_id], frozenPlan);
    }
    f.assertPreserved();
  });
});

test('format preflight repair preserves the original failure and a successful output enables one later independent review', async t => {
  for (const failedExportRepair of [false, true]) await t.test(String(failedExportRepair), async t => {
    const venueId = catalog.venues.at(-1).id;
    const f = await fixture(t, { failedExport: venueId, failedExportRepair });
    await f.run();
    const original = structuredClone(f.workflow.artifacts), counts = [f.job.proposalAttempt, f.job.studyLiteratureAttempt,
      f.job.draftAttempt, f.job.codeAttempt, f.job.executionAttempt], calls = f.modelCalls.length;
    await f.run();
    const venue = f.portfolio.venues.at(-1);
    assert.equal(venue.export_repair_attempts, 1);
    assert.equal(venue.export_repair_available, false);
    assert.equal(venue.export_status, failedExportRepair ? 'failed' : 'completed');
    assert.equal(f.modelCalls.length, calls, 'The format repair itself makes no model request');
    assert.deepEqual([f.job.proposalAttempt, f.job.studyLiteratureAttempt, f.job.draftAttempt,
      f.job.codeAttempt, f.job.executionAttempt], counts);
    for (const [id, artifact] of Object.entries(original)) assert.deepEqual(f.workflow.artifacts[id], artifact);
    assert.equal(f.requests.filter(request => request.method === 'workflow.repairPortfolioExport').length, 1);
    await f.run();
    assert.equal(f.requests.filter(request => request.method === 'workflow.repairPortfolioExport').length, 1);
    assert.equal(f.modelCalls.length, calls + (failedExportRepair ? 0 : 1),
      'A repaired output receives its first independent review; a failed preflight cannot consume that review slot');
    assert.equal(venue.review_attempts, failedExportRepair ? 0 : 1);
    f.assertPreserved();
  });
});

test('unadmitted local start resumes its original UUID once after cleanup; an already admitted unknown start cannot resend', async t => {
  for (const alreadyAdmitted of [false, true]) await t.test(String(alreadyAdmitted), async t => {
    const f = await fixture(t, { rejectStartOnce: true });
    await assert.rejects(f.run(), error => error.code === 'INVALID_ARGUMENT');
    assert.equal(f.modelCalls.length, 0);
    assert.equal(f.workflow.repository_paper.analysis_attempts, 1);
    const inferenceDirectory = join(f.directory, f.job.id, 'inference');
    const startName = (await readdir(inferenceDirectory)).find(name => name.endsWith('-started.json'));
    const originalBytes = await readFile(join(inferenceDirectory, startName), 'utf8');
    const start = JSON.parse(originalBytes);
    if (alreadyAdmitted) {
      await f.engine.request('workflow.recordInference', { researchId: f.job.id, receipt: start });
      await assert.rejects(f.run(), error => error.code === 'SOURCE_ANALYSIS_INCOMPLETE');
      assert.equal(f.modelCalls.length, 0, 'A native start may already have reached the provider');
    } else {
      f.controller.restoring = false;
      await f.controller.cancel(f.job.id);
      assert.equal(f.job.cleanupRequired, false);
      assert.equal(f.controller.snapshot().jobs[0].portfolioUnsentRequestAvailable, true);
      assert.equal(f.requests.some(request => request.method === 'workflow.cancel'), false);
      const prefix = start.prompt.slice(0, start.prompt.indexOf('.') + 1);
      const binding = start.prompt.slice(start.prompt.indexOf('\n\nExact repository portfolio binding and complete scientific materials:\n'));
      await assert.rejects(f.controller.repositoryGenerationOnce(f.job, structuredClone(f.workflow), 'source-analysis',
        prefix, prefix + ' Changed scientific instructions.' + binding, binding, new AbortController().signal),
      error => error.code === 'INFERENCE_EVIDENCE_INVALID');
      assert.equal(f.modelCalls.length, 0, 'The recovered request must match the exact current prompt');
      await f.run();
      assert.equal(f.modelCalls.length, 1 + 2 * catalog.venues.length);
      assert.equal(f.workflow.repository_paper.analysis_attempts, 2);
      assert.equal(f.portfolio.completed, catalog.venues.length);
      assert.ok((await readdir(inferenceDirectory)).includes(start.id + '-completed.json'));
      assert.equal(f.controller.snapshot().jobs[0].portfolioUnsentRequestAvailable, false);
    }
    assert.equal(await readFile(join(inferenceDirectory, startName), 'utf8'), originalBytes);
    f.assertPreserved();
  });
});

test('local-only preflight start can reconcile and run directly without a stale workflow snapshot', async t => {
  const f = await fixture(t, { rejectStartOnce: true });
  await assert.rejects(f.run(), error => error.code === 'INVALID_ARGUMENT');
  f.job.cleanupRequired = false;
  await f.run();
  assert.equal(f.modelCalls.length, 1 + 2 * catalog.venues.length);
  assert.equal(f.workflow.repository_paper.analysis_attempts, 2);
  assert.equal(f.portfolio.completed, catalog.venues.length);
  f.assertPreserved();
});

async function admittedUnsentFixture(t) {
  const f = await fixture(t, { rejectStartOnce: true });
  await assert.rejects(f.run(), error => error.code === 'INVALID_ARGUMENT');
  assert.equal(f.modelCalls.length, 0);
  const inferenceDirectory = join(f.directory, f.job.id, 'inference');
  const startName = (await readdir(inferenceDirectory)).find(name => name.endsWith('-started.json'));
  const startPath = join(inferenceDirectory, startName), originalBytes = await readFile(startPath, 'utf8');
  const start = JSON.parse(originalBytes);
  f.controller.restoring = false;
  await f.controller.cancel(f.job.id);
  assert.equal(f.job.cleanupRequired, false);
  const auditPath = join(f.directory, f.job.id, 'inference-recovery', start.id + '.json');
  const admissionPath = join(f.directory, f.job.id, 'inference-recovery', start.id + '-admission.json');
  const auditBytes = await readFile(auditPath, 'utf8'), admissionBytes = await readFile(admissionPath, 'utf8');
  const admission = JSON.parse(admissionBytes);
  assert.equal(admission.nativeStartSha256, f.workflow.artifacts[`model-evidence-${start.id}-started`].sha256);
  assert.equal(admission.auditSha256, digest(auditBytes));
  assert.equal(admission.dispatchGate, 'exclusive-marker-before-provider');
  return { ...f, start, startPath, originalBytes, auditPath, auditBytes, admissionPath, admissionBytes };
}

function restartedController(f) {
  const controller = new ResearchController(f.client, f.engine, f.directory, () => {});
  const job = structuredClone(f.job);
  controller.jobs.set(job.id, job);
  assert.equal(controller.undispatchedStarts.size, 0, 'The new controller cannot inherit the process-local recovery map');
  return { controller, job,
    run: () => controller.runRepositoryPortfolio(job, structuredClone(f.workflow), new AbortController().signal) };
}

test('durable unsent admission survives a fresh controller and dispatches the original source UUID exactly once', async t => {
  const f = await admittedUnsentFixture(t), restarted = restartedController(f);
  await restarted.run();
  assert.equal(f.modelCalls.length, 1 + 2 * catalog.venues.length);
  assert.equal(f.modelCalls.filter(call => call.input[0].content.startsWith('Perform the common')).length, 1);
  assert.equal(f.workflow.repository_paper.analysis_attempts, 2);
  assert.equal(f.portfolio.completed, catalog.venues.length);
  const names = await readdir(join(f.directory, f.job.id, 'inference'));
  assert.ok(names.includes(f.start.id + '-completed.json'));
  const sourceIds = new Set(f.requests.filter(call => call.method === 'workflow.recordInference' && call.params.receipt.phase === 'source-analysis')
    .map(call => call.params.receipt.id));
  assert.deepEqual([...sourceIds], [f.start.id]);
  assert.equal(await readFile(f.startPath, 'utf8'), f.originalBytes);
  assert.equal(await readFile(f.auditPath, 'utf8'), f.auditBytes);
  assert.equal(await readFile(f.admissionPath, 'utf8'), f.admissionBytes);
  f.assertPreserved();
});

test('an exclusive dispatch marker before a simulated process exit forbids a fresh controller from sending an uncertain request', async t => {
  const f = await admittedUnsentFixture(t);
  const directory = join(f.directory, f.job.id, 'inference-dispatch');
  await mkdir(directory, { recursive: true });
  const markerPath = join(directory, f.start.id + '.json');
  const markerBytes = JSON.stringify({ id: f.start.id, promptSha256: f.start.promptSha256, model: f.start.model,
    profileId: f.start.profileId, event: 'provider-dispatch-intent' });
  await writeFile(markerPath, markerBytes, { flag: 'wx' });
  await assert.rejects(restartedController(f).run(), error => error.code === 'SOURCE_ANALYSIS_INCOMPLETE');
  assert.equal(f.modelCalls.length, 0);
  assert.equal(await readFile(markerPath, 'utf8'), markerBytes);
  assert.equal(await readFile(f.startPath, 'utf8'), f.originalBytes);
  f.assertPreserved();
});

test('changed native-admission and audit hashes reject durable recovery before provider dispatch', async t => {
  for (const corruption of ['nativeStartSha256', 'auditSha256', 'auditBytes']) await t.test(corruption, async t => {
    const f = await admittedUnsentFixture(t);
    if (corruption === 'auditBytes') await writeFile(f.auditPath, f.auditBytes + ' ');
    else {
      const admission = JSON.parse(f.admissionBytes);
      admission[corruption] = 'f'.repeat(64);
      await writeFile(f.admissionPath, JSON.stringify(admission));
    }
    await assert.rejects(restartedController(f).run(), error => error.code === 'INFERENCE_EVIDENCE_INVALID');
    assert.equal(f.modelCalls.length, 0);
    assert.equal(await readFile(f.startPath, 'utf8'), f.originalBytes);
    f.assertPreserved();
  });
});

test('a changed current account or drafting model cannot dispatch a retained unsent request', async t => {
  for (const change of ['profile', 'model']) await t.test(change, async t => {
    const f = await admittedUnsentFixture(t), restarted = restartedController(f);
    if (change === 'profile') f.client.getSession = async () => ({ status: 'connected', sharing: true, profileId: 'different-synthetic-profile' });
    else {
      restarted.job.model = 'different-synthetic-writer';
      f.client.listModels = async () => [{ slug: 'different-synthetic-writer' }, { slug: 'synthetic-reviewer' }];
    }
    await assert.rejects(restarted.run(), error => error.code === 'INFERENCE_EVIDENCE_INVALID');
    assert.equal(f.modelCalls.length, 0);
    assert.equal(await readFile(f.startPath, 'utf8'), f.originalBytes);
    f.assertPreserved();
  });
});

test('two fresh controllers racing the same proven unsent UUID dispatch only one source request', async t => {
  const f = await admittedUnsentFixture(t);
  const contenders = [restartedController(f), restartedController(f)];
  // Isolate the inference dispatch race from the unrelated shared jobs.json UI projection.
  for (const item of contenders) item.controller.save = async () => {};
  await Promise.all(contenders.map(item => item.controller.reconcileReceipts(item.job)));
  assert.ok(contenders.every(item => item.controller.undispatchedStarts.has(f.start.id)));
  let providerEntered, releaseProvider;
  const entered = new Promise(resolve => { providerEntered = resolve; });
  const release = new Promise(resolve => { releaseProvider = resolve; });
  const streamResponse = f.client.streamResponse;
  f.client.streamResponse = async request => { providerEntered(); await release; return streamResponse(request); };
  const prefix = f.start.prompt.slice(0, f.start.prompt.indexOf('.') + 1);
  const binding = f.start.prompt.slice(f.start.prompt.indexOf('\n\nExact repository portfolio binding and complete scientific materials:\n'));
  const requests = contenders.map(item => item.controller.repositoryGenerationOnce(item.job, structuredClone(f.workflow),
    'source-analysis', prefix, f.start.prompt, binding, new AbortController().signal));
  const settled = requests.map(promise => promise.then(value => ({ status: 'fulfilled', value }), reason => ({ status: 'rejected', reason })));
  await entered;
  const first = await Promise.race(settled);
  releaseProvider();
  const results = await Promise.all(settled);
  assert.equal(first.status, 'rejected');
  assert.equal(first.reason.code, 'INFERENCE_ALREADY_DISPATCHED', first.reason.stack);
  assert.equal(results.filter(result => result.status === 'fulfilled').length, 1);
  assert.equal(f.modelCalls.length, 1);
  assert.equal(f.workflow.repository_paper.analysis_attempts, 2);
  assert.equal(await readFile(f.startPath, 'utf8'), f.originalBytes);
  f.assertPreserved();
});

test('retained draft 2 survives one common analysis and two independently written/reviewed actual outputs', async t => {
  const f = await fixture(t);
  await f.run();
  assert.equal(f.modelCalls.length, 1 + 2 * catalog.venues.length);
  assert.equal(f.workflow.repository_paper.analysis_attempts, 2);
  assert.equal(f.portfolio.completed, catalog.venues.length);
  assert.equal(new Set(f.portfolio.venues.map(venue => venue.draft.title)).size, catalog.venues.length);
  assert.ok(f.portfolio.venues.every(venue => venue.draft_attempts === 1 && venue.review_attempts === 1 && venue.admitted_drafts === 1));
  assert.equal(f.requests.filter(request => request.method === 'workflow.exportPortfolioDraft').length, catalog.venues.length);
  f.assertPreserved();
  const reads = f.requests.filter(request => request.method === 'workflow.readMaterial').length;
  await f.run();
  assert.equal(f.modelCalls.length, 1 + 2 * catalog.venues.length, 'Completed submissions must not trigger another inference');
  assert.equal(f.requests.filter(request => request.method === 'workflow.exportPortfolioDraft').length, catalog.venues.length);
  assert.equal(f.requests.filter(request => request.method === 'workflow.readMaterial').length, reads,
    'A completed portfolio resume must not reread every source, scholarly body and guidance page');
  f.assertPreserved();
});

test('one failed writer does not block others, and resume reuses a completed admission receipt without retrying failed input', async t => {
  const f = await fixture(t, { failedWriter: catalog.venues[0].id, interruptedAdmission: catalog.venues[1].id });
  await f.run();
  assert.equal(f.portfolio.completed, catalog.venues.length - 2);
  assert.equal(f.modelCalls.length, 2 * catalog.venues.length - 1);
  assert.equal(f.portfolio.venues[0].draft_attempts, 1);
  assert.equal(f.portfolio.venues[0].admitted_drafts, 0);
  assert.equal(f.portfolio.venues[1].draft_attempts, 1);
  assert.equal(f.portfolio.venues[1].admitted_drafts, 0);
  await f.run();
  assert.equal(f.portfolio.completed, catalog.venues.length - 1);
  assert.equal(f.modelCalls.length, 2 * catalog.venues.length, 'Only the newly admitted manuscript receives its first review');
  assert.equal(f.portfolio.venues[0].draft_attempts, 1, 'An incomplete same-input request must not be regenerated');
  assert.equal(f.portfolio.venues[1].draft_attempts, 1, 'Completed writer text must be reused after admission interruption');
  assert.equal(f.portfolio.venues[1].admitted_drafts, 1);
  assert.equal(f.job.code, 'PORTFOLIO_INCOMPLETE');
  f.assertPreserved();
});

test('global material-integrity and account failures stop dispatch before later venues', async t => {
  for (const error of [new EngineError('ARTIFACT_CHANGED', 'Synthetic changed frozen source'),
    new ChatGPTError('invalid_refresh_token', 'Synthetic expired account', false, 401)]) {
    await t.test(error.code, async t => {
      const f = await fixture(t, { globalError: error });
      // Preserve a completed common analysis so the failure exercises the per-venue catch.
      f.portfolio.analysis = structuredClone(analysis); f.portfolio.analysis_binding = null;
      await assert.rejects(f.run(), candidate => candidate === error);
      assert.ok(f.modelCalls.length <= 1, 'A shared auth/integrity failure must not become repeated per-venue model failures');
      assert.equal(f.requests.filter(request => request.method === 'workflow.submitPortfolioManuscript').length, 0);
      f.assertPreserved();
    });
  }
});
