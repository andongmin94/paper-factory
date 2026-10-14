import assert from 'node:assert/strict';
import test from 'node:test';
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

const { outputFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/shared/publication.ts', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22' });
const { inspectRepositoryArticle, inspectRepositoryPublication: publication, inspectRepositoryPortfolioOutputs,
  inspectRepositoryPortfolioWork, inspectRepositoryPortfolioVenueWork, repositoryPortfolioReasoningReady, NEW_RESEARCH_MODE } =
  await import('data:text/javascript;base64,' + Buffer.from(outputFiles[0].text).toString('base64'));
const { outputFiles: venueFiles } = await build({ entryPoints: [fileURLToPath(new URL('../src/shared/venues.ts', import.meta.url))],
  bundle: true, write: false, platform: 'node', format: 'esm', target: 'node22' });
const { PUBLICATION_VENUES, PUBLICATION_CATALOG, getPublicationVenue } =
  await import('data:text/javascript;base64,' + Buffer.from(venueFiles[0].text).toString('base64'));
const target = getPublicationVenue('ieee-software').verified_limits;
const selectedTarget = { venue_id: 'ieee-software', article_category: 'Feature Article', selection_reason: 'Synthetic fixture target.',
  candidates: PUBLICATION_VENUES.map(venue => ({ venue_id: venue.id, fit: venue.id === 'ieee-software' ? 'suitable' : 'needs_evidence',
    reason: 'Synthetic fixture comparison only.', missing_evidence: [] })) };
const inspect = draft => inspectRepositoryArticle(draft, selectedTarget);

test('reasoning readiness preserves an original presentation failure and never promotes it to submission approval', () => {
  const criteria = Object.fromEntries(['supported_findings', 'contribution', 'literature', 'method', 'presentation', 'empirical_claims_absent', 'venue_fit']
    .map(key => [key, { passed: key !== 'presentation', reason: 'Synthetic criterion fixture.' }]));
  const venue = { analysis_current: true, scientific_ready: false, content_ready: false, submission_ready: false,
    review: { criteria, content_assessment: { comparison: { passed: true }, contribution: { passed: true } } } };
  const original = structuredClone(venue);
  assert.equal(repositoryPortfolioReasoningReady(venue), true);
  assert.deepEqual(venue, original);
  assert.equal(repositoryPortfolioReasoningReady({ ...venue, analysis_current: false }), false);
  assert.equal(repositoryPortfolioReasoningReady({ ...venue, review: { ...venue.review,
    criteria: { ...criteria, contribution: { passed: false, reason: 'Actual contribution missing.' } } } }), false);
});

const article = () => ({ title: 'A practical bounded design case',
  sections: [{ heading: 'Abstract', text: 'A bounded design case offers practical guidance.' },
    { heading: 'Discussion', text: 'Prefer an explicit decision when its documented conditions hold.' },
    { heading: 'Actionable Insights', text: '- Trace the actual authority boundary.\n- Compare delivery choices separately.\n- Verify the declared assumptions before applying the design.' }],
  source_evidence: [{ path: 'src/main.ts', sha256: 'a'.repeat(64) }, { path: 'src/main.ts', sha256: 'a'.repeat(64) }],
  literature_evidence: [{ source_id: 'primary-one' }], document_evidence: [{ source_id: 'official-one' }] });

test('IEEE article inspection counts the rendered bibliography and requires all three insights', () => {
  const draft = article(), before = structuredClone(draft);
  assert.equal(NEW_RESEARCH_MODE, 'repository_analysis');
  assert.equal(inspect(draft).references, 3);
  assert.equal(inspect(draft).formatReady, true);
  assert.deepEqual(draft, before);
  draft.sections.pop();
  assert.equal(inspect(draft).formatReady, false);
  assert.match(inspect(draft).blockers.join(' '), /Actionable Insights/);
});

test('tables and figures use the fixed allowance without counting table cells twice', () => {
  const draft = article();
  const plain = inspect(draft).estimatedWords;
  draft.sections[1].text += '\n\n| Decision | Condition |\n| --- | --- |\n| ' + 'cell '.repeat(800) + ' | trace |\n\n![Boundary diagram](diagram.svg)';
  const result = inspect(draft);
  assert.equal(result.tables, 1);
  assert.equal(result.figures, 1);
  assert.equal(result.estimatedWords, plain + 2 * target.visual_word_cost);
});

test('literal code tables are prose while separate Markdown tables retain their allowance', () => {
  const draft = article();
  draft.sections[1].text = '```text\n| key | value |\n| --- | --- |\n| one | two |\n```\n\nkey | value\n--- | ---\none | two';
  assert.equal(inspect(draft).tables, 1);
});

test('overlong prose, abstract and native bibliography are reported separately from approval', () => {
  const draft = article();
  draft.sections[0].text = 'abstract '.repeat(target.max_abstract_words + 1);
  draft.sections[1].text = 'body '.repeat(target.max_words + 1);
  draft.document_evidence = Array.from({ length: 16 }, (_, i) => ({ source_id: 'doc-' + i }));
  const result = inspect(draft);
  assert.equal(result.formatReady, false);
  assert.equal(result.blockers.length, 3);
  assert.equal(result.references, 18);
  assert.equal(Object.hasOwn(result, 'submissionReady'), false);
  assert.equal(Object.hasOwn(result, 'scientificReady'), false);
});

const artifact = (id, character = 'a') => ({ id, sha256: character.repeat(64), size: 120 });
const readyJob = () => {
  const criteria = Object.fromEntries(['supported_findings', 'contribution', 'literature', 'method', 'presentation', 'empirical_claims_absent', 'venue_fit']
    .map(name => [name, { passed: true, reason: 'Synthetic bounded analysis criterion.' }]));
  return { draftAttempt: 1, authorMetadata: null,
    artifacts: [artifact('repository-draft-1'), artifact('repository-draft-md-1', 'b'), artifact('repository-review-1', 'c'),
      artifact('repository-draft-pdf-1', 'd'), artifact('repository-draft-docx-1', 'e')],
    repositoryPaper: { plan: { publication_target: selectedTarget }, draft: article(), draft_sha256: 'a'.repeat(64), scientific_ready: true, content_ready: true,
      review: { criteria, issues: [], next_actions: [] },
      content_assessment: { comparison: { passed: true, reason: 'Synthetic complete comparison.' },
        contribution: { passed: true, reason: 'Synthetic bounded contribution.' }, issues: [] },
      artifact_ids: { draft: 'repository-draft-1', draft_markdown: 'repository-draft-md-1', review: 'repository-review-1',
        pdf: 'repository-draft-pdf-1', docx: 'repository-draft-docx-1' }, next_actions: [], formatting_receipts: [] } };
};
function author(job, character = 'f') {
  const id = 'author-metadata-' + character.repeat(12);
  job.artifacts.push(artifact(id, character));
  job.authorMetadata = { origin: 'explicit_human_author_metadata', artifact_id: id, sha256: character.repeat(64),
    value: { display_name: 'Synthetic Author', email: 'author@example.test', affiliation: 'Synthetic Institute' } };
}
function format(job, attempt = 1, status = 'completed', extensions = ['pdf', 'docx']) {
  const number = job.draftAttempt, input = `repository-draft-md-${number}-format-${attempt}`;
  const receipt = { artifact_id: `repository-draft-format-${status === 'reserved' ? 'intent-' : ''}${number}-format-${attempt}`,
    draft_attempt: number, attempt, status, markdown_sha256: 'b'.repeat(64), draft_sha256: 'a'.repeat(64), review_sha256: 'c'.repeat(64),
    input_artifact_id: input, input_sha256: 'a'.repeat(64), author_artifact_id: job.authorMetadata?.artifact_id ?? null,
    author_sha256: job.authorMetadata?.sha256 ?? null, outputs: {}, errors: [] };
  job.artifacts.push(artifact(input), artifact(receipt.artifact_id));
  for (const extension of extensions) {
    const id = `repository-draft-${extension}-${number}-format-${attempt}`, conversion = id + '-conversion';
    job.artifacts.push(artifact(id, 'd'), artifact(conversion));
    receipt.outputs[extension] = { artifact_id: id, sha256: 'd'.repeat(64), conversion_artifact_id: conversion };
    if (status === 'completed') job.repositoryPaper.artifact_ids[extension] = id;
  }
  job.repositoryPaper.formatting_receipts.push(receipt);
  return receipt;
}

test('anonymous current exports remain inspectable and require actual author review without submission approval', () => {
  const job = readyJob(), before = structuredClone(job), status = publication(job);
  assert.equal(status.stage, 'author_review_pending'); assert.equal(status.outputCurrent, true);
  assert.equal(status.authorOutputCurrent, false); assert.equal(status.formattingRemaining, 3);
  assert.deepEqual(status.currentOutputIds, ['repository-draft-pdf-1', 'repository-draft-docx-1']);
  assert.match(status.nextAction, /AI.*권리.*사진.*PDF 모든 페이지/);
  assert.equal(Object.hasOwn(status, 'submissionReady'), false); assert.deepEqual(job, before);
});

test('actual manuscript format and scientific content override stale optimistic format summaries', () => {
  const job = readyJob(); job.repositoryPaper.venueFormat = { formatReady: true, blockers: [] };
  job.repositoryPaper.draft.sections[0].text = 'abstract '.repeat(151);
  assert.equal(publication(job).stage, 'editorial_revision');
  assert.match(publication(job).blockers.join(' '), /151/);
  job.repositoryPaper.content_assessment.comparison.passed = false;
  assert.equal(publication(job).stage, 'content_revision');
  job.repositoryPaper.review = null; assert.equal(publication(job).stage, 'editorial_revision');
  job.repositoryPaper.draft = article(); assert.equal(publication(job).stage, 'review_pending');
  job.repositoryPaper.draft = null; assert.equal(publication(job).stage, 'draft_pending');
});

test('human or infeasible requirements hold automatic rewriting and retain concrete verification instructions', () => {
  const job = readyJob(); job.repositoryPaper.next_actions = [{ action: 'human_validation', target: 'Observed effect',
    required_change: 'Confirm the actual observation independently.', verification: 'Inspect the original measurement record.' }];
  const status = publication(job);
  assert.equal(status.stage, 'human_hold'); assert.match(status.nextAction, /Observed effect.*measurement record/);
});

test('native unconfirmed content remains a blocker even with optimistic assessment fields', () => {
  for (const flag of [false, null, undefined]) {
    const job = readyJob(); job.repositoryPaper.content_ready = flag;
    const status = publication(job);
    assert.equal(status.stage, 'content_revision');
    assert.match(status.blockers.join(' '), /내용 평가의 통과 상태가 확인되지/);
  }
});

test('current author metadata requires outputs bound to the same author, draft, markdown and review', () => {
  const job = readyJob(); author(job);
  assert.equal(publication(job).stage, 'author_output_pending');
  const receipt = format(job); const status = publication(job);
  assert.equal(status.stage, 'author_review_pending'); assert.equal(status.authorOutputCurrent, true);
  assert.equal(status.formattingRemaining, 2);
  for (const [key, value] of [['draft_sha256', 'b'.repeat(64)], ['markdown_sha256', 'a'.repeat(64)], ['review_sha256', 'a'.repeat(64)],
    ['author_sha256', 'a'.repeat(64)], ['input_sha256', 'b'.repeat(64)]]) {
    const copy = structuredClone(job); copy.repositoryPaper.formatting_receipts[0][key] = value;
    assert.equal(publication(copy).stage, 'author_output_pending', key);
    assert.deepEqual(publication(copy).currentOutputIds, [], key);
  }
  author(job, 'e'); assert.equal(publication(job).stage, 'author_output_pending');
  assert.equal(receipt.author_sha256, 'f'.repeat(64), 'Original receipt remains frozen after a new author selection.');
});

test('anonymous formatted output still describes the current body when author metadata is added later', () => {
  const job = readyJob(); format(job); author(job);
  const status = publication(job);
  assert.equal(status.stage, 'author_output_pending'); assert.equal(status.outputCurrent, true);
  assert.equal(status.authorOutputCurrent, false);
  assert.deepEqual(status.currentOutputIds, ['repository-draft-pdf-1-format-1', 'repository-draft-docx-1-format-1']);
});

test('incomplete author identity requests corrected metadata before another formatting attempt', () => {
  const job = readyJob(); author(job); job.authorMetadata.value.email = '';
  const status = publication(job);
  assert.equal(status.stage, 'author_output_pending');
  assert.match(status.nextAction, /올바르게 입력·보존한 뒤/); assert.equal(status.formattingRemaining, 3);
});

test('a latest reserved or partial formatting attempt supersedes older success without spending manuscript attempts', () => {
  const job = readyJob(); author(job); format(job);
  assert.equal(publication(job).authorOutputCurrent, true);
  format(job, 2, 'reserved');
  const reserved = publication(job);
  assert.equal(reserved.stage, 'author_output_pending'); assert.equal(reserved.outputCurrent, false);
  assert.deepEqual(reserved.currentOutputIds, []); assert.equal(reserved.previousOutputIds.length, 6);
  assert.equal(reserved.formattingRemaining, 1); assert.equal(job.draftAttempt, 1);
  const receipt = format(job, 3, 'completed', ['pdf']); receipt.errors = [{ format: 'docx', message: 'Synthetic conversion failure.' }];
  const partial = publication(job);
  assert.equal(partial.outputCurrent, false); assert.equal(partial.formattingRemaining, 0);
  assert.deepEqual(partial.currentOutputIds, ['repository-draft-pdf-1-format-3']);
  assert.match(partial.blockers.join(' '), /conversion failure/); assert.match(partial.nextAction, /3회 한도/);
});

test('prior-draft outputs cannot replace a missing new-draft export or consume its formatting allowance', () => {
  const job = readyJob(); format(job); job.draftAttempt = 2;
  job.artifacts.push(artifact('repository-draft-2'), artifact('repository-draft-md-2', 'b'), artifact('repository-review-2', 'c'));
  Object.assign(job.repositoryPaper.artifact_ids, { draft: 'repository-draft-2', draft_markdown: 'repository-draft-md-2', review: 'repository-review-2' });
  const status = publication(job);
  assert.equal(status.stage, 'output_pending'); assert.equal(status.outputCurrent, false);
  assert.deepEqual(status.currentOutputIds, []); assert.equal(status.previousOutputIds.length, 4);
  assert.equal(status.formattingRemaining, 3);
});

test('an output SHA mismatch cannot appear as the current author package', () => {
  const job = readyJob(); author(job); const receipt = format(job);
  job.artifacts.find(item => item.id === receipt.outputs.pdf.artifact_id).sha256 = 'b'.repeat(64);
  const status = publication(job);
  assert.equal(status.stage, 'author_output_pending'); assert.equal(status.outputCurrent, false);
  assert.deepEqual(status.currentOutputIds, ['repository-draft-docx-1-format-1']);
});

test('unchecked S&P guidance reports actual table text without borrowing Software numerical limits', () => {
  const catalog = structuredClone(PUBLICATION_CATALOG);
  const profile = catalog.venues.find(venue => venue.id === 'ieee-security-privacy');
  profile.verified_limits = {}; profile.requirements_status = 'checked_scope';
  const draft = article(); draft.sections = draft.sections.slice(0, 2);
  draft.sections[0].text = 'abstract '.repeat(180);
  const target = { ...selectedTarget, venue_id: 'ieee-security-privacy' };
  const before = inspectRepositoryArticle(draft, target, catalog);
  draft.sections[1].text += '\n\n| Quality | Condition |\n| --- | --- |\n| ' + 'observation '.repeat(800) + ' | trace |';
  const format = inspectRepositoryArticle(draft, target, catalog);
  assert.equal(format.tables, 1); assert.ok(format.estimatedWords > before.estimatedWords + 800);
  assert.equal(format.insights, 0); assert.equal(format.formatReady, true);
  assert.equal(format.numericGuidanceVerified, false); assert.equal(format.uncheckedRequirements.length, 1);
  assert.equal(format.blockers.length, 0, 'An unverified official numerical limit cannot become a blocking rule.');
});

test('whole-article S&P scope adds actual table text and visual allowance while Software substitutes its allowance', () => {
  const catalog = structuredClone(PUBLICATION_CATALOG), profile = catalog.venues.find(venue => venue.id === 'ieee-security-privacy');
  profile.verified_limits = { min_words: 4900, max_words: 7200, max_abstract_words: 50, max_references: 15,
    visual_word_cost: 250, word_count_scope: 'whole_article' };
  profile.requirements_status = 'checked_numeric_guidance';
  const draft = article(), target = { venue_id: profile.id, article_category: 'Feature Article' };
  const before = inspectRepositoryArticle(draft, target, catalog);
  draft.sections[1].text += '\n\n| Decision | Condition |\n| --- | --- |\n| ' + 'cell '.repeat(800) + ' | trace |';
  const format = inspectRepositoryArticle(draft, target, catalog);
  assert.equal(format.tables, 1);
  assert.equal(format.estimatedWords, before.estimatedWords + 803 + 250);
  assert.match(format.blockers.join(' '), /4900/);
  assert.equal(format.numericGuidanceVerified, true);
});

test('minimum words use whitespace rather than inflating code identifiers and paths into evidence of sufficient length', () => {
  const catalog = structuredClone(PUBLICATION_CATALOG), profile = catalog.venues.find(venue => venue.id === 'ieee-security-privacy');
  profile.verified_limits = { min_words: 4900, max_words: 30000, word_count_scope: 'whole_article' };
  const draft = article();
  draft.sections[1].text = '`src/main/native_bridge.open_file` '.repeat(1300);
  const format = inspectRepositoryArticle(draft, { venue_id: profile.id, article_category: 'Feature Article' }, catalog);
  assert.ok(format.estimatedWords < 1400);
  assert.ok(format.maximumWordsEstimate > 4900);
  assert.match(format.blockers.join(' '), /최소 분량.*4900/);
});

test('exact native Markdown supplies canonical reference and bio text for whole-article count without inventing their lengths', () => {
  const catalog = structuredClone(PUBLICATION_CATALOG), profile = catalog.venues.find(venue => venue.id === 'ieee-security-privacy');
  profile.verified_limits = { word_count_scope: 'whole_article' };
  const draft = article(), target = { venue_id: profile.id, article_category: 'Feature Article' };
  const body = '# ' + draft.title + '\n' + draft.sections.map(section => '## ' + section.heading + '\n' + section.text).join('\n');
  const references = '\n## References\n[1] A real supplied reference title with author and year.\n## Author Biographies\nA supplied author biography.';
  const before = inspectRepositoryArticle(draft, target, catalog, body);
  const after = inspectRepositoryArticle(draft, target, catalog, body + references);
  assert.ok(after.estimatedWords > before.estimatedWords);
  profile.verified_limits.min_words = before.estimatedWords + 1;
  assert.equal(inspectRepositoryArticle(draft, target, catalog).formatReady, false);
  assert.equal(inspectRepositoryArticle(draft, target, catalog, body + references).formatReady, true);
  assert.equal(inspectRepositoryArticle(draft, selectedTarget, catalog, body).estimatedWords,
    inspectRepositoryArticle(draft, selectedTarget, catalog, body + references).estimatedWords, 'Software excludes those same reference and biography sections');
});

test('missing or unknown target cannot silently acquire an IEEE publication policy', () => {
  for (const value of [null, { ...selectedTarget, venue_id: 'unlisted-journal' }]) {
    const format = inspectRepositoryArticle(article(), value);
    assert.equal(format.venueId, null); assert.equal(format.formatReady, false);
    assert.match(format.blockers.join(' '), /투고처 선택 기록/);
  }
  const historical = readyJob(); historical.repositoryPaper.plan = null;
  assert.equal(publication(historical).stage, 'target_pending');
  assert.equal(historical.repositoryPaper.plan, null);
});

test('a selected venue cannot use another journal article category', () => {
  const format = inspectRepositoryArticle(article(), { ...selectedTarget, article_category: 'Research Track' });
  assert.equal(format.formatReady, false); assert.match(format.blockers.join(' '), /지원 논문 유형/);
});

test('retained publication rules govern a paper without mutating the current catalog', () => {
  const snapshot = structuredClone(PUBLICATION_CATALOG);
  snapshot.venues.find(venue => venue.id === 'ieee-software').verified_limits.max_abstract_words = 3;
  const job = readyJob(); job.repositoryPaper.publication_venues = snapshot;
  assert.equal(publication(job).stage, 'editorial_revision');
  assert.match(publication(job).blockers.join(' '), /3단어/);
  assert.equal(inspect(article()).formatReady, true, 'A retained rule snapshot cannot rewrite the current catalog.');
});

function portfolioOutputFixture() {
  const venue = { venue_id: 'ieee-security-privacy', article_category: 'Feature Article', admitted_drafts: 1,
    draft: article(), draft_sha256: 'b'.repeat(64), artifact_ids: {}, export_repair_available: false, export_repair_attempts: 0 };
  const prefix = `repository-portfolio-${venue.venue_id}`;
  const artifacts = ['draft', 'markdown', 'pdf', 'docx'].map(format => {
    const id = `${prefix}-${format}-1`; venue.artifact_ids[format] = id;
    return { id, sha256: format === 'draft' ? venue.draft_sha256 : 'c'.repeat(64), size: 180 };
  });
  return { venue, artifacts };
}

test('portfolio output files belong to the admitted venue draft and leave the retained study unchanged', () => {
  const fixture = portfolioOutputFixture(), before = structuredClone(fixture);
  assert.deepEqual(inspectRepositoryPortfolioOutputs(fixture.venue, fixture.artifacts).map(item => item.format), ['markdown', 'pdf', 'docx']);
  assert.deepEqual(fixture, before);
});

function correctedPortfolioOutputFixture(kind) {
  const f = portfolioOutputFixture(), prefix = `repository-portfolio-${f.venue.venue_id}`;
  const receipt = { artifact_id: `${prefix}-export-${kind}-1`, sha256: 'd'.repeat(64), status: 'completed',
    original_draft_sha256: f.venue.draft_sha256, input_artifact_id: `${prefix}-export-markdown-${kind}-1`,
    input_sha256: 'e'.repeat(64), outputs: {} };
  f.venue[`${kind}_export`] = receipt; f.venue[`${kind}_export_attempts`] = 1;
  f.artifacts.push({ id: receipt.artifact_id, sha256: receipt.sha256, size: 200 },
    { id: receipt.input_artifact_id, sha256: receipt.input_sha256, size: 230 });
  for (const format of ['pdf', 'docx']) {
    const id = `${prefix}-${format}-${kind}-1`;
    f.venue.artifact_ids[format] = id;
    f.artifacts.push({ id, sha256: 'f'.repeat(64), size: 250 });
    receipt.outputs[format] = { artifact_id: id, sha256: 'f'.repeat(64) };
  }
  return f;
}

for (const kind of ['format', 'layout']) {
  test(`actual ${kind} PDF and Word pointers are visible when bound to their completed retained receipt`, () => {
    const f = correctedPortfolioOutputFixture(kind), before = structuredClone(f);
    assert.deepEqual(inspectRepositoryPortfolioOutputs(f.venue, f.artifacts).map(item => item.format), ['markdown', 'pdf', 'docx']);
    assert.deepEqual(f, before);
  });
  test(`invalid ${kind} output proofs cannot expose corrected files`, () => {
    const mutations = [
      f => { f.venue[`${kind}_export`].status = 'failed'; },
      f => { f.venue[`${kind}_export_attempts`] = 0; },
      f => { f.venue[`${kind}_export`].original_draft_sha256 = '0'.repeat(64); },
      f => { f.venue[`${kind}_export`].sha256 = '0'.repeat(64); },
      f => { f.venue[`${kind}_export`].input_sha256 = '0'.repeat(64); },
      f => { f.artifacts = f.artifacts.filter(a => a.id !== f.venue[`${kind}_export`].artifact_id); },
      f => { f.venue[`${kind}_export`].outputs = {}; },
    ];
    for (const mutate of mutations) {
      const f = correctedPortfolioOutputFixture(kind); mutate(f);
      assert.deepEqual(inspectRepositoryPortfolioOutputs(f.venue, f.artifacts).map(item => item.format), ['markdown']);
    }
    const f = correctedPortfolioOutputFixture(kind);
    f.venue[`${kind}_export`].outputs.pdf.sha256 = '0'.repeat(64);
    assert.deepEqual(inspectRepositoryPortfolioOutputs(f.venue, f.artifacts).map(item => item.format), ['markdown', 'docx']);
  });
}

test('a base manuscript or another venue export cannot masquerade as a portfolio submission', () => {
  for (const foreign of ['repository-draft-pdf-2-format-1', 'repository-portfolio-ieee-software-pdf-1']) {
    const { venue, artifacts } = portfolioOutputFixture();
    venue.artifact_ids.pdf = foreign; artifacts.push({ id: foreign, sha256: 'd'.repeat(64), size: 180 });
    assert.deepEqual(inspectRepositoryPortfolioOutputs(venue, artifacts).map(item => item.format), ['markdown', 'docx']);
  }
});

test('an old admitted draft and a changed current draft cannot lend their exports to a new portfolio draft', () => {
  const { venue, artifacts } = portfolioOutputFixture();
  venue.admitted_drafts = 2;
  assert.deepEqual(inspectRepositoryPortfolioOutputs(venue, artifacts), []);
  venue.admitted_drafts = 1; venue.draft_sha256 = 'f'.repeat(64);
  assert.deepEqual(inspectRepositoryPortfolioOutputs(venue, artifacts), []);
});

test('missing, empty and malformed portfolio export descriptors stay unavailable without hiding valid other formats', () => {
  for (const corrupt of [{ size: 0 }, { size: 1.5 }, { sha256: 'not-a-sha' }]) {
    const { venue, artifacts } = portfolioOutputFixture();
    Object.assign(artifacts.find(item => item.id === venue.artifact_ids.pdf), corrupt);
    assert.deepEqual(inspectRepositoryPortfolioOutputs(venue, artifacts).map(item => item.format), ['markdown', 'docx']);
  }
  const { venue, artifacts } = portfolioOutputFixture();
  assert.deepEqual(inspectRepositoryPortfolioOutputs(venue, artifacts.filter(item => item.id !== venue.artifact_ids.pdf))
    .map(item => item.format), ['markdown', 'docx']);
});

function portfolioWorkFixture() {
  const { venue } = portfolioOutputFixture();
  Object.assign(venue, { status: 'content_ready', review: { next_actions: [], content_assessment: { next_actions: [] } },
    writer_binding: null, reviewer_binding: null, writer_outcome: null, reviewer_outcome: null,
    repair_attempts: 0, repair_binding: null, repair_outcome: null,
    revise_available: false, revise_reason: '이 원고·심사는 공통 분석 보완 전 기록입니다. 추가 근거를 확인하고 기존 파일과 횟수를 보존하세요.',
    draft_attempts: 1, review_attempts: 1, analysis_current: true, scientific_ready: true, content_ready: true, export_status: 'completed', export: null });
  const paper = { plan: {}, analysis: {}, draft: {}, review: {}, analysis_attempts: 2,
    portfolio: { guidance: {}, analysis: {}, analysis_binding: null, analysis_outcome: null, literature_collections: [], venues: [venue],
      analysis_revision_required: false, analysis_revision_available: false, analysis_revision: null,
      literature_followup_available: false, documentation_followup_available: false,
      all_content_ready: false, literature_budget: { used: 2, limit: 3 } } };
  return { paper, venue };
}

test('completed IEEE feature work and external evidence holds have no automatic resume task', () => {
  const { paper, venue } = portfolioWorkFixture();
  paper.portfolio.venues = PUBLICATION_VENUES.map(profile => ({ ...structuredClone(venue), venue_id: profile.id }));
  paper.portfolio.all_content_ready = true;
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  assert.deepEqual(paper, before);
  for (const action of ['retrieve_literature', 'retrieve_documentation', 'revise_source_analysis', 'human_validation', 'infeasible']) {
    paper.portfolio.all_content_ready = false;
    const held = paper.portfolio.venues[0];
    Object.assign(held, { status: 'needs_revision', content_ready: false, writer_binding: { attempt: 2 },
      review: { next_actions: [], content_assessment: { next_actions: [{ action }] } } });
    assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
    assert.match(inspectRepositoryPortfolioVenueWork(held).reason, /추가 근거/);
  }
});

test('IEEE features start from a retained plan without a duplicate common manuscript or analysis', () => {
  const paper = { plan: { publication_target: selectedTarget }, analysis: null, draft: null, review: null, portfolio: null };
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'start');
  assert.deepEqual(paper, before);
  assert.equal(inspectRepositoryPortfolioWork({ ...paper, plan: null }).action, null);
});

test('an admitted feature gets its first Word/PDF before reserving an independent review', () => {
  const { paper, venue } = portfolioWorkFixture();
  Object.assign(venue, { review: null, reviewer_binding: { attempt: 1 }, export_status: 'not_started' });
  venue.artifact_ids.pdf = null; venue.artifact_ids.docx = null;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'export');
  venue.export_status = 'completed';
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'review');
});

test('same-input failures and uncertain starts stay held while completed third responses and proven unsent starts can resume', () => {
  const { venue } = portfolioWorkFixture();
  Object.assign(venue, { draft: null, review: null, writer_binding: { attempt: 3 }, draft_attempts: 3 });
  for (const outcome of ['failed', 'interrupted', 'started']) {
    venue.writer_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null);
  }
  assert.equal(inspectRepositoryPortfolioVenueWork(venue, true).action, 'draft', 'Only a process-local proven unsent request can dispatch its retained start');
  venue.writer_outcome = 'completed';
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'draft', 'Completed third writer text can be admitted without a fourth request');
  venue.writer_binding.attempt = 4;
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null);
  Object.assign(venue, { draft: article(), reviewer_binding: { attempt: 3 }, reviewer_outcome: 'completed' });
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'review');
  venue.reviewer_outcome = 'failed';
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null);
});

function interruptedTailFixture() {
  const { paper, venue } = portfolioWorkFixture();
  Object.assign(venue, { draft: null, review: null, admitted_drafts: 0, status: 'writing_interrupted',
    writer_binding: { attempt: 3 }, writer_outcome: 'failed', draft_attempts: 3, review_attempts: 0,
    repair_binding: { phase: 'venue-manuscript-repair', attempt: 1, venue_id: venue.venue_id,
      repair: { original_inference_artifact_id: 'model-evidence-original-failed', original_inference_sha256: 'd'.repeat(64),
        original_prompt_sha256: 'e'.repeat(64), partial_text_sha256: 'f'.repeat(64), original_attempt: 3 } } });
  return { paper, venue };
}

test('native eligible tail repair precedes a failed writer hold and preserves all original study and writer counts', () => {
  const { paper, venue } = interruptedTailFixture(), before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'repair');
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'repair');
  assert.match(inspectRepositoryPortfolioVenueWork(venue).reason, /꼬리.*1회/);
  assert.deepEqual(paper, before, 'Availability checks cannot rewrite the failed original or reset counters');
  assert.equal(venue.writer_outcome, 'failed');
  assert.equal(venue.draft_attempts, 3, 'Repair has its own one-attempt budget, independent of the writer budget');
  venue.repair_attempts = 1; venue.repair_outcome = 'completed';
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'repair', 'Retained repair completion can still be admitted at its limit');
  assert.equal(venue.admitted_drafts, 0, 'A completed repair receipt does not fabricate an admitted draft');
});

test('failed, interrupted and uncertain tail repairs cannot request another repair; proven unsent start alone may dispatch', () => {
  const { venue } = interruptedTailFixture();
  venue.repair_attempts = 1;
  for (const outcome of ['failed', 'interrupted', 'started']) {
    venue.repair_outcome = outcome;
    const before = structuredClone(venue), work = inspectRepositoryPortfolioVenueWork(venue);
    assert.equal(work.action, null);
    assert.match(work.reason, /복구 1회 한도/);
    assert.deepEqual(venue, before);
  }
  assert.equal(inspectRepositoryPortfolioVenueWork(venue, true).action, 'repair');
  for (const outcome of ['failed', 'interrupted']) {
    venue.repair_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioVenueWork(venue, true).action, null, 'Unsent evidence cannot turn a terminal repair failure into retry permission');
  }
});

test('tail repair is not inferred from a failed writer and is limited to one native bound repair of an unadmitted draft', () => {
  const { venue } = interruptedTailFixture();
  for (const change of [
    { repair_attempts: 2 },
    { repair_binding: { ...venue.repair_binding, attempt: 2 } },
    { repair_binding: { ...venue.repair_binding, attempt: 0 } },
    { repair_binding: { ...venue.repair_binding, phase: 'venue-manuscript' } },
    { repair_binding: { ...venue.repair_binding, repair: undefined } },
    { repair_binding: null },
  ]) assert.equal(inspectRepositoryPortfolioVenueWork({ ...venue, ...change }).action, null);
  venue.draft = article();
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'repair', 'A current native repair can restore a later writer without deleting the prior draft');
  Object.assign(venue, { repair_binding: null, repair_outcome: null, repair_attempts: 1, reviewer_binding: { attempt: 1 }, reviewer_outcome: null });
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'review', 'An admitted repaired draft uses its normal independent review, never another repair');
});

test('a held manuscript gets its initial files before prose revision and failed exports do not promise a retry', () => {
  const { venue } = portfolioWorkFixture();
  Object.assign(venue, { status: 'needs_revision', content_ready: false, writer_binding: { attempt: 2 },
    revise_available: true, revise_reason: '실제 심사와 새 근거에 결속된 문장 보완이 가능합니다.',
    review: { next_actions: [{ action: 'revise_manuscript' }], content_assessment: { next_actions: [] } },
    export_status: 'not_started' });
  venue.artifact_ids.pdf = venue.artifact_ids.docx = null;
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'export');
  venue.export_status = 'completed';
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'revision');
  venue.writer_outcome = 'failed';
  for (const status of ['failed', 'interrupted']) {
    venue.export_status = status;
    assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null);
    assert.match(inspectRepositoryPortfolioVenueWork(venue).reason, /변환.*다시 실행하지/);
  }
  venue.review = null; venue.reviewer_binding = null; venue.export_status = 'not_started';
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'export', 'A failed review cannot suppress the real draft output');
});

test('only native-confirmed output repair can resume a retained failure without a model request or counter reset', () => {
  const { paper, venue } = portfolioWorkFixture();
  venue.export_status = 'failed';
  venue.export = { artifact_id: `repository-portfolio-${venue.venue_id}-export-1`, sha256: 'd'.repeat(64),
    errors: [{ format: 'pdf', message: 'Synthetic retained converter failure.' }] };
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null, 'A failed export alone is not repair permission');
  venue.export_repair_available = true;
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'repair_export');
  assert.match(inspectRepositoryPortfolioVenueWork(venue).reason, /모델 호출 없이/);
  assert.deepEqual(paper, before, 'The original failed receipt, draft, review, analysis and counts are preserved');
  for (const change of [{ draft: null }, { export_status: 'completed' }, { export_status: 'not_started' },
    { export_repair_available: false }, { export_repair_attempts: 1 }, { export_repair_attempts: 2 }]) {
    assert.notEqual(inspectRepositoryPortfolioVenueWork({ ...venue, ...change }).action, 'repair_export');
  }
  venue.export_repair_attempts = 1;
  assert.match(inspectRepositoryPortfolioVenueWork(venue).reason, /출력 복구 1회 한도/);
});

test('confirmed historical-output repair precedes stale-science holds and new common-analysis planning', () => {
  const { paper, venue } = commonRevisionFixture();
  Object.assign(venue, { analysis_current: false, export_status: 'failed', export_repair_available: true });
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'repair_export');
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'repair_export');
  assert.deepEqual(paper, before, 'Output repair does not revive historical scientific approval or change analysis budgets');
  venue.export_repair_attempts = 1;
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null, 'A failed repair cannot repeat even when old availability is inconsistent');
  venue.analysis_current = true; venue.export_status = 'completed'; venue.export_repair_available = false;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revise_analysis', 'Output completion is separate from the remaining research work');
});

function repairedPortfolioOutputFixture() {
  const { venue, artifacts } = portfolioOutputFixture();
  const prefix = `repository-portfolio-${venue.venue_id}`;
  const original = { id: `${prefix}-export-1`, sha256: 'd'.repeat(64), size: 240 };
  const receipt = { id: `${prefix}-export-repair-1`, sha256: 'e'.repeat(64), size: 260 };
  Object.assign(venue, { export_repair_attempts: 1, export_status: 'completed', export: { artifact_id: receipt.id,
    sha256: receipt.sha256, original_artifact_id: original.id, original_sha256: original.sha256, errors: [] } });
  artifacts.push(original, receipt);
  for (const format of ['pdf', 'docx']) {
    const id = `${prefix}-${format}-repair-1`; venue.artifact_ids[format] = id;
    artifacts.push({ id, sha256: 'f'.repeat(64), size: 280 });
  }
  return { venue, artifacts, receipt, original };
}

test('repaired files require the exact current-venue receipt and its retained hash, preserving original failure descriptors', () => {
  const fixture = repairedPortfolioOutputFixture(), before = structuredClone(fixture);
  assert.deepEqual(inspectRepositoryPortfolioOutputs(fixture.venue, fixture.artifacts).map(item => item.format), ['markdown', 'pdf', 'docx']);
  assert.deepEqual(fixture, before);
  for (const corrupt of [
    f => { f.venue.export_repair_attempts = 0; },
    f => { f.venue.export_repair_attempts = 2; },
    f => { f.venue.export.artifact_id = f.original.id; },
    f => { f.venue.export.sha256 = 'a'.repeat(64); },
    f => { f.receipt.sha256 = 'invalid'; f.venue.export.sha256 = 'invalid'; },
    f => { f.receipt.size = 0; },
    f => { f.receipt.size = 1.5; },
    f => { f.artifacts = f.artifacts.filter(item => item.id !== f.receipt.id); },
  ]) {
    const f = repairedPortfolioOutputFixture(); corrupt(f);
    assert.deepEqual(inspectRepositoryPortfolioOutputs(f.venue, f.artifacts).map(item => item.format), ['markdown']);
  }
  for (const foreign of ['repository-portfolio-ieee-software-pdf-repair-1',
    'repository-portfolio-ieee-security-privacy-pdf-repair-2', 'repository-draft-pdf-2-format-1']) {
    const f = repairedPortfolioOutputFixture(); f.venue.artifact_ids.pdf = foreign;
    f.artifacts.push({ id: foreign, sha256: 'f'.repeat(64), size: 280 });
    assert.deepEqual(inspectRepositoryPortfolioOutputs(f.venue, f.artifacts).map(item => item.format), ['markdown', 'docx']);
  }
});

test('the common analysis uses the original budget and cannot hide a failed or interrupted collection', () => {
  const { paper } = portfolioWorkFixture();
  Object.assign(paper.portfolio, { analysis: null, analysis_binding: { attempt: 3 }, analysis_outcome: null });
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis');
  paper.analysis_attempts = 3;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  paper.portfolio.analysis_outcome = 'completed';
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis');
  for (const outcome of ['failed', 'interrupted', 'started']) {
    paper.portfolio.analysis_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  }
  assert.equal(inspectRepositoryPortfolioWork(paper, true).action, 'analysis');
  paper.portfolio.literature_collections.push({ status: 'interrupted' });
  assert.equal(inspectRepositoryPortfolioWork(paper, true).action, null);
});

test('initial analysis schema repair requires native availability, its exact binding and the original shared budget', () => {
  const { paper } = portfolioWorkFixture();
  Object.assign(paper.portfolio, { analysis: null, analysis_binding: { phase: 'source-analysis', attempt: 1 },
    analysis_outcome: 'completed', analysis_repair_available: true,
    analysis_repair_candidate_artifact_id: 'model-evidence-synthetic-completed', analysis_repair: null });
  paper.analysis_attempts = 1;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'repair_analysis');
  paper.analysis_attempts = 3;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis', 'Only a retained completion may be read at the exhausted limit; no new repair is available');
  const repair = { artifact_id: 'repository-portfolio-analysis-schema-repair', sha256: 'e'.repeat(64), status: 'planned' };
  Object.assign(paper.portfolio, { analysis_repair: repair, analysis_repair_available: false,
    analysis_repair_candidate_artifact_id: null, analysis_outcome: null,
    analysis_binding: { phase: 'source-analysis', attempt: 2, analysis_schema_repair_sha256: repair.sha256 } });
  paper.analysis_attempts = 1;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis');
  paper.portfolio.analysis_binding.analysis_schema_repair_sha256 = 'f'.repeat(64);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  paper.portfolio.analysis_binding.analysis_schema_repair_sha256 = repair.sha256;
  paper.analysis_attempts = 3;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  paper.portfolio.analysis_outcome = 'completed';
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis', 'A valid completed repair is admitted without another model request');
  for (const outcome of ['failed', 'interrupted', 'started']) {
    paper.portfolio.analysis_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  }
  assert.equal(inspectRepositoryPortfolioWork(paper, true).action, 'analysis', 'Only a proven undispatched reservation may send its original UUID');
  paper.portfolio.analysis_repair.status = 'incomplete';
  assert.equal(inspectRepositoryPortfolioWork(paper, true).action, null, 'Schema-valid but unsupported source admission cannot reopen repair');
});

test('positive or unreviewed venue feedback requires its native pending binding and cannot replay failed revision requests', () => {
  const { paper, venue } = portfolioWorkFixture();
  paper.portfolio.all_content_ready = false;
  const receipt = { artifact_id: 'repository-portfolio-ieee-security-privacy-revision-feedback-1', sha256: 'e'.repeat(64) };
  Object.assign(venue, { revision_feedback_pending: true, revision_feedback: receipt,
    writer_binding: { phase: 'venue-manuscript', attempt: 2, revision_feedback_sha256: receipt.sha256 }, writer_outcome: null });
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'revision', 'An old positive review cannot suppress the explicitly bound correction');
  venue.review = null;
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'revision', 'Unreviewed numeric preflight can correct prose before spending its first review');
  venue.writer_binding.revision_feedback_sha256 = 'f'.repeat(64);
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null);
  venue.writer_binding.revision_feedback_sha256 = receipt.sha256;
  for (const outcome of ['failed', 'interrupted', 'started']) {
    venue.writer_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, null);
  }
  assert.equal(inspectRepositoryPortfolioVenueWork(venue, true).action, 'revision');
  venue.writer_binding.attempt = 4;
  assert.equal(inspectRepositoryPortfolioVenueWork(venue, true).action, null);
});

function commonRevisionFixture() {
  const { paper, venue } = portfolioWorkFixture();
  const actions = [{ action: 'revise_source_analysis', target: 'Trust and constrained authority',
    required_change: 'Apply explicit policies before and after trusted mediation.', verification: 'Compare all policy judgments.' },
    { action: 'retrieve_literature', target: 'Closest methods', required_change: 'Read the nearest primary bodies.', verification: 'Retain exact body evidence.' }];
  Object.assign(venue, { status: 'needs_revision', scientific_ready: false, content_ready: false,
    review: { next_actions: actions, content_assessment: { next_actions: [] } }, writer_binding: { attempt: 2 } });
  Object.assign(paper.portfolio, { analysis_revision_required: true, analysis_revision_available: true,
    pdf_budget: { base_used: 2, additional_limit: 2, additional_used: 2, total_used: 4 } });
  return { paper, venue, plan: { artifact_id: 'repository-portfolio-analysis-revision', sha256: 'e'.repeat(64),
    prior_analysis_sha256: 'd'.repeat(64), affected_venues: [venue.venue_id], actions, status: 'planned' } };
}

test('review-bound common repair uses native availability and the original remaining budget without changing prior studies', () => {
  const { paper } = commonRevisionFixture(), before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revise_analysis');
  assert.deepEqual(paper, before);
  paper.portfolio.analysis_revision_available = false;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null, 'A review request alone cannot invent native availability');
  paper.portfolio.analysis_revision_available = true; paper.analysis_attempts = 3;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null, 'A proposed repair cannot reset or expand the original three-analysis budget');
});

test('original pending writer, review, tail and first files precede common research repair', () => {
  const { paper, venue } = commonRevisionFixture();
  venue.draft = null; venue.writer_outcome = null;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'draft');
  venue.writer_outcome = 'failed';
  venue.repair_binding = interruptedTailFixture().venue.repair_binding;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'repair');
  venue.repair_binding = null; venue.draft = article(); venue.review = null; venue.reviewer_binding = { attempt: 1 };
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'review');
  venue.reviewer_binding = null; venue.export_status = 'not_started'; venue.artifact_ids.pdf = null;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'export');
});

test('a planned common repair runs despite retained prior analysis and admits its exact third completion without another model request', () => {
  const { paper, plan } = commonRevisionFixture();
  Object.assign(paper.portfolio, { analysis_revision: plan, analysis_revision_available: false,
    analysis_binding: { phase: 'source-analysis', attempt: 3, analysis_revision_sha256: plan.sha256 }, analysis_outcome: null });
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis');
  assert.deepEqual(paper, before, 'Starting work does not overwrite the retained prior analysis, reviews or PDF reservations');
  paper.analysis_attempts = 3;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  paper.portfolio.analysis_outcome = 'completed';
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'analysis');
  paper.portfolio.analysis_binding.analysis_revision_sha256 = 'f'.repeat(64);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null, 'A receipt for another plan cannot resume this repair');
  paper.portfolio.analysis_binding.analysis_revision_sha256 = plan.sha256;
  for (const outcome of ['failed', 'interrupted', 'started']) {
    paper.portfolio.analysis_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  }
  assert.equal(inspectRepositoryPortfolioWork(paper, true).action, 'analysis', 'Only a proven unsent reservation can dispatch its retained start');
});

test('completed or incomplete common repair neither repeats analysis nor recycles historical positive reviews into bulk prose', () => {
  const { paper, venue, plan } = commonRevisionFixture();
  Object.assign(venue, { analysis_current: false, review: { criteria: { contribution: { passed: true } },
    next_actions: [{ action: 'revise_manuscript' }], content_assessment: { next_actions: [] } } });
  paper.analysis_attempts = 3;
  for (const status of ['completed', 'incomplete']) {
    paper.portfolio.analysis_revision = { ...plan, status };
    const before = structuredClone(paper);
    assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
    assert.match(inspectRepositoryPortfolioVenueWork(venue).reason, /공통 분석 보완 전/);
    assert.deepEqual(paper, before, 'Historical review criteria and outputs remain intact and are not upgraded');
    assert.equal(venue.review.criteria.contribution.passed, true);
  }
  const { artifacts } = portfolioOutputFixture();
  assert.equal(inspectRepositoryPortfolioOutputs(venue, artifacts).length, 3, 'Stale scientific approval does not erase actual old manuscript files');
  venue.export_status = 'not_started'; venue.artifact_ids.pdf = null;
  assert.equal(inspectRepositoryPortfolioVenueWork(venue).action, 'export', 'First output of the actual historical manuscript remains available');
});

function localEvidenceRevisionFixture() {
  const { paper, venue, plan } = commonRevisionFixture();
  paper.analysis_attempts = 3;
  paper.portfolio.analysis_revision = { ...plan, status: 'incomplete' };
  paper.portfolio.venues = PUBLICATION_VENUES.map(profile => ({ ...structuredClone(venue), venue_id: profile.id,
    analysis_current: false, writer_binding: null, revise_available: false,
    revise_reason: '이 학술지의 추가 연구 근거가 아직 없습니다.' }));
  const feature = paper.portfolio.venues.find(item => item.venue_id === 'ieee-software');
  Object.assign(feature, { revise_available: true, revise_reason: '실제 비교 문헌과 수정 분석을 읽어 이 학술지 원고를 보완할 수 있습니다.',
    writer_binding: { attempt: 2, phase: 'venue-manuscript', prior_review_sha256: 'c'.repeat(64) },
    review: { criteria: { contribution: { passed: true }, literature: { passed: false } },
      next_actions: [{ action: 'retrieve_literature' }, { action: 'revise_manuscript' }], content_assessment: { next_actions: [] } } });
  const security = paper.portfolio.venues.find(item => item.venue_id === 'ieee-security-privacy');
  security.review.next_actions = [{ action: 'human_validation' }, { action: 'revise_source_analysis' }];
  return { paper, feature, security };
}

test('native evidenced local revision can proceed while another venue and the common plan remain scientifically held', () => {
  const { paper, feature, security } = localEvidenceRevisionFixture(), before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioVenueWork(feature).action, 'revision');
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revision');
  assert.equal(inspectRepositoryPortfolioVenueWork(security).action, null);
  assert.deepEqual(paper, before, 'Availability cannot replace old manuscripts, upgrade scientific flags or consume another analysis');
  assert.equal(feature.analysis_current, false);
  assert.equal(feature.scientific_ready, false);
  assert.equal(feature.review.criteria.contribution.passed, true, 'The exact historical review is preserved, even when the current study is held');
  feature.revise_available = false;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null, 'Changed analysis and a negative review alone do not invent native permission');
});

test('evidenced revision still requires an admissible reserved outcome and never expands writing limits', () => {
  const { feature } = localEvidenceRevisionFixture();
  for (const outcome of ['failed', 'interrupted', 'started']) {
    feature.writer_outcome = outcome;
    assert.equal(inspectRepositoryPortfolioVenueWork(feature).action, null);
  }
  assert.equal(inspectRepositoryPortfolioVenueWork(feature, true).action, 'revision', 'A proven unsent reservation may dispatch once');
  feature.writer_binding.attempt = 3; feature.writer_outcome = 'completed'; feature.draft_attempts = 3;
  assert.equal(inspectRepositoryPortfolioVenueWork(feature).action, 'revision', 'The completed third response can be admitted without a fourth request');
  feature.writer_binding.attempt = 4;
  assert.equal(inspectRepositoryPortfolioVenueWork(feature).action, null);
  feature.writer_binding = null;
  assert.equal(inspectRepositoryPortfolioVenueWork(feature).action, null);
});

test('native new-body followup uses the preserved literature budget before writing and cannot replace output repair', () => {
  const { paper, feature } = localEvidenceRevisionFixture();
  paper.portfolio.literature_followup_available = true;
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'collect_literature');
  assert.deepEqual(paper, before, 'Planning retrieval cannot reset collection or PDF reservations, clear review actions or claim new evidence');
  paper.portfolio.literature_followup_available = false;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revision', 'An old retrieval action cannot open another collection without native permission');
  paper.portfolio.literature_followup_available = true; paper.portfolio.literature_budget.used = 3;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revision', 'The collection limit remains three, independently of manuscript allowance');
  feature.revise_available = false;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null);
  paper.portfolio.literature_budget.used = 2;
  Object.assign(feature, { export_status: 'failed', export_repair_available: true });
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'repair_export', 'A native-authorized model-free repair preserves the actual old output before new research work');
});

test('native documentation followup precedes local and common revisions while original exports and reviews finish first', () => {
  const { paper, feature } = localEvidenceRevisionFixture();
  paper.portfolio.analysis_revision.status = 'planned';
  paper.portfolio.analysis_binding = { attempt: 3, analysis_revision_sha256: paper.portfolio.analysis_revision.sha256 };
  paper.portfolio.analysis_outcome = 'failed';
  paper.portfolio.documentation_followup_available = true;
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'collect_documentation');
  assert.deepEqual(paper, before, 'Documentation permission cannot alter failed analysis receipts, reviews or counters');
  paper.portfolio.documentation_followup_available = false;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revision', 'A native-authorized local rederivation does not replay the failed common analysis');
  paper.portfolio.documentation_followup_available = true;
  feature.export_status = 'not_started'; feature.artifact_ids.pdf = feature.artifact_ids.docx = null;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'export');
  feature.export_status = 'completed'; feature.review = null; feature.analysis_current = true;
  feature.reviewer_binding = { attempt: 2 }; feature.reviewer_outcome = null;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'review');
});

test('an old documentation request cannot collect without native permission and full content approval ends automatic followup', () => {
  const { paper, feature } = localEvidenceRevisionFixture();
  feature.review.next_actions = [{ action: 'retrieve_documentation', target: 'https://www.electronjs.org/docs/latest/tutorial/security' }];
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'revision', 'A retained URL cannot invent collection permission or bypass its bound budget');
  Object.assign(paper.portfolio, { all_content_ready: true, documentation_followup_available: true,
    literature_followup_available: true, analysis_revision_available: true });
  const before = structuredClone(paper);
  assert.equal(inspectRepositoryPortfolioWork(paper).action, null, 'Accepted limits and optional advice do not spend another model request');
  assert.deepEqual(paper, before);
  feature.export_status = 'failed'; feature.export_repair_available = true;
  assert.equal(inspectRepositoryPortfolioWork(paper).action, 'repair_export', 'Approval cannot conceal a pending original file repair');
});
